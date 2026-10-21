"""Replacing a corpus in the vector store: safely, cheaply and on the record.

Shared by the `ingest` (curated), `ingest_scrape` (scrape sources) and
`refresh_corpus` (both, for the scheduler) commands. Each corpus of a country is
replaced as a unit, in its own transaction, and every attempt is written down as
an IngestRun.

- Due: a corpus is due when what is on offer (its *marker*: the newest feed's
  name, or a fingerprint of the curated chunks) differs from the marker of its
  last successful run, or when that run used another embedding model.
- Shrink guard: a corpus is never replaced by nothing, nor (unless forced) by
  one much smaller than it is now.
- Embedding reuse: a chunk id is derived from the chunk's text, so a chunk whose
  id is already stored keeps its vector. Only new or changed chunks are embedded,
  which is what makes it affordable to run this on a schedule.
- One at a time: an advisory lock keeps a manual run and a scheduled run from
  interleaving their deletes and inserts. The lock belongs to the database
  connection, so it is checked again before every write: if the connection was
  dropped meanwhile, the lock is taken again or the corpus is left alone.
"""
from __future__ import annotations

import hashlib
import json
import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Callable

from django.conf import settings
from django.db import connection, transaction
from django.utils import timezone

from knowledge.ingest_utils import records_for_country
from knowledge.models import IngestRun, KnowledgeChunk
from knowledge.scrape_utils import SOURCES, records_from_feeds

CURATED = "curated"
# Any constant will do; it only has to be the same for every ingestion run.
_LOCK_ID = 7_141_592
_RETRIES = 5
# The backend (connection) that holds the ingestion lock for this process, if any.
_lock_pid: int | None = None

# Outcomes of refreshing one corpus. The first two mean the run should exit non-zero.
FAILED, SKIPPED = IngestRun.FAILED, IngestRun.SKIPPED
SUCCEEDED, NOT_DUE, NO_FEEDS, DRY_RUN = IngestRun.SUCCEEDED, "not-due", "no-feeds", "dry-run"


@dataclass(frozen=True)
class Result:
    corpus: str
    status: str

    @property
    def bad(self) -> bool:
        return self.status in (FAILED, SKIPPED)


class LockLost(RuntimeError):
    """The ingestion lock went with a dropped connection and another run has it."""


def _try_lock() -> int | None:
    """Take the lock on the current connection; return its backend pid, or None
    if another connection holds the lock."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_try_advisory_lock(%s), pg_backend_pid()", [_LOCK_ID])
        acquired, pid = cursor.fetchone()
    return pid if acquired else None


@contextmanager
def ingest_lock():
    """Yield True if this process now holds the ingestion lock, False if another
    run already does (the caller should then do nothing)."""
    global _lock_pid
    _lock_pid = _try_lock()
    acquired = _lock_pid is not None
    try:
        yield acquired
    finally:
        if acquired:
            _lock_pid = None
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_unlock(%s)", [_LOCK_ID])


def _keep_lock() -> None:
    """Make sure the lock taken by `ingest_lock` is still held before writing.

    An advisory lock lives and dies with its connection. A run spends minutes
    waiting on Voyage, and if the idle connection is dropped in that time Django
    quietly opens a new one that holds nothing. On a new connection the lock is
    taken again; if another run got there first, this one must not write.
    Does nothing outside `ingest_lock`.
    """
    global _lock_pid
    if _lock_pid is None:
        return
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_backend_pid()")
        if cursor.fetchone()[0] == _lock_pid:
            return
    retaken = _try_lock()
    if retaken is None:
        raise LockLost(
            "the database connection was dropped and another ingestion run now holds the lock"
        )
    _lock_pid = retaken


def last_success(country: str, corpus: str) -> IngestRun | None:
    return (
        IngestRun.objects.filter(country=country, corpus=corpus, status=IngestRun.SUCCEEDED)
        .order_by("-started_at")
        .first()
    )


def is_due(country: str, corpus: str, marker: str) -> bool:
    """True unless the last successful run ingested exactly this marker with
    the current embedding model.

    Vectors from another model cannot be compared with the queries, so a changed
    EMBEDDING_MODEL makes every corpus due even though no feed or chunk changed.

    A failed or guard-skipped run does not settle anything: the corpus stays due
    and the next scheduled run tries (and, if nothing changed, fails) again,
    which keeps the problem visible until someone deals with it.
    """
    last = last_success(country, corpus)
    return (
        last is None
        or last.marker != marker
        or last.embedding_model != settings.EMBEDDING_MODEL
    )


def fingerprint(records: list[dict]) -> str:
    """A marker for a set of chunks: changes when any chunk or its metadata does."""
    canonical = json.dumps(
        sorted(records, key=lambda r: r["chunk_id"]), sort_keys=True, default=str
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:32]


def _embed(texts: list[str], out) -> list:
    """Embed in batches with progress, backing off on Voyage rate limits.

    Every vector is gathered before the DB write, so a failure here leaves the
    existing rows untouched.
    """
    import voyageai.error

    from core.embeddings import _MAX_BATCH, embed_documents

    vectors = []
    for i in range(0, len(texts), _MAX_BATCH):
        batch = texts[i:i + _MAX_BATCH]
        for attempt in range(_RETRIES):
            try:
                vectors.extend(embed_documents(batch))
                break
            except voyageai.error.RateLimitError:
                if attempt == _RETRIES - 1:
                    raise
                wait = 20 * (attempt + 1)
                out(f"  rate limited; retrying in {wait}s")
                time.sleep(wait)
        out(f"  embedded {len(vectors)}/{len(texts)}")
    return vectors


def replace_corpus(
    *, country: str, corpus: str, marker: str, build: Callable[[], list[dict]],
    force: bool = False, out=print,
) -> IngestRun:
    """Replace one corpus with the records ``build()`` returns; record the attempt.

    Returns the IngestRun (succeeded, or skipped by the shrink guard). On any
    error the run is recorded as failed, the existing rows are left as they
    were, and the error is re-raised.
    """
    rows = KnowledgeChunk.objects.filter(country=country, corpus=corpus)
    run = IngestRun(
        country=country, corpus=corpus, marker=marker, started_at=timezone.now(),
        previous_chunks=rows.count(), embedding_model=settings.EMBEDDING_MODEL,
    )
    try:
        _keep_lock()
        records = build()
        # Nothing extracted means a broken crawl or extractor, not an empty source.
        if not records:
            raise ValueError("no chunks to ingest")

        floor = settings.INGEST_MIN_KEEP_RATIO * run.previous_chunks
        if not force and len(records) < floor:
            run.status = IngestRun.SKIPPED
            run.chunks = len(records)
            run.error = (
                f"{len(records)} chunk(s) would replace {run.previous_chunks}, below the "
                f"{settings.INGEST_MIN_KEEP_RATIO:.0%} floor; rerun with --force if that is right"
            )
            out(f"{corpus}: NOT REPLACED: {run.error}")
            return run

        # A chunk id embeds a hash of its text, so the same id is the same text
        # and (under the same model) the same vector.
        previous = last_success(country, corpus)
        reusable = {}
        if previous and previous.embedding_model == settings.EMBEDDING_MODEL:
            reusable = dict(rows.values_list("chunk_id", "embedding"))
        fresh = [r for r in records if r["chunk_id"] not in reusable]
        if fresh:
            out(f"{corpus}: embedding {len(fresh)} new chunk(s), reusing {len(records) - len(fresh)}")
        vectors = dict(zip((r["chunk_id"] for r in fresh), _embed([r["text"] for r in fresh], out)))
        objs = [
            KnowledgeChunk(
                embedding=vectors[r["chunk_id"]] if r["chunk_id"] in vectors else reusable[r["chunk_id"]],
                **r,
            )
            for r in records
        ]

        with transaction.atomic():
            # Checked inside the transaction, which cannot outlive its connection.
            _keep_lock()
            deleted, _ = rows.delete()
            KnowledgeChunk.objects.bulk_create(objs, batch_size=500)

        run.status = IngestRun.SUCCEEDED
        run.chunks, run.embedded = len(objs), len(fresh)
        out(
            f"\u2713 {corpus}: upserted {len(objs)} chunk(s) for '{country}' (replaced {deleted} "
            f"existing row(s), embedded {len(fresh)}) using {settings.EMBEDDING_MODEL}"
        )
        return run
    except Exception as exc:
        run.status = IngestRun.FAILED
        run.error = repr(exc)[:2000]
        raise
    finally:
        run.finished_at = timezone.now()
        run.save()


def record_failure(country: str, corpus: str, exc: Exception, marker: str = "") -> IngestRun:
    """Record an attempt that failed before `replace_corpus` could record it
    (the feeds could not be listed, the bucket is not configured, ...), so that
    `corpus_status` shows it. The marker is empty when it never got that far.
    """
    now = timezone.now()
    return IngestRun.objects.create(
        country=country, corpus=corpus, marker=marker, status=IngestRun.FAILED,
        previous_chunks=KnowledgeChunk.objects.filter(country=country, corpus=corpus).count(),
        embedding_model=settings.EMBEDDING_MODEL, error=repr(exc)[:2000],
        started_at=now, finished_at=now,
    )


def _preview(records: list[dict], out) -> None:
    for r in records[:3]:
        text = r["text"][:100].replace("\n", " ")
        out(f"  [{r.get('topic')}] {r['chunk_id']}: {text}...")


def refresh_curated(country: str, *, upsert: bool, only_due: bool = False,
                    force: bool = False, out=print) -> Result:
    """Ingest the curated data/ corpus for one country."""
    recorded = False
    try:
        records = records_for_country(country)
        marker = fingerprint(records)
        out(f"{CURATED}: {len(records)} chunk(s) for '{country}'")
        if only_due and not is_due(country, CURATED, marker):
            out(f"{CURATED}: unchanged since the last ingest")
            return Result(CURATED, NOT_DUE)
        if not upsert:
            _preview(records, out)
            return Result(CURATED, DRY_RUN)
        recorded = True  # from here on replace_corpus records the attempt itself
        run = replace_corpus(
            country=country, corpus=CURATED, marker=marker, build=lambda: records,
            force=force, out=out,
        )
        return Result(CURATED, run.status)
    except Exception as exc:  # one corpus must not take the others down
        out(f"{CURATED}: FAILED, rows left as they are: {exc!r}")
        if upsert and not recorded:
            record_failure(country, CURATED, exc)
        return Result(CURATED, FAILED)


def refresh_scraped(store, names: list[str], country: str, *, upsert: bool,
                    only_due: bool = False, force: bool = False, out=print) -> list[Result]:
    """Ingest each named scrape source from a feed store, independently."""
    results = []
    for name in dict.fromkeys(names):
        corpus = SOURCES[name].corpus
        recorded = False
        try:
            newest = store.newest(name)
            if newest is None:
                out(f"{name}: no feeds; skipped, rows left as they are")
                results.append(Result(corpus, NO_FEEDS))
                continue
            if only_due and not is_due(country, corpus, newest):
                out(f"{name}: nothing new since {newest}")
                results.append(Result(corpus, NOT_DUE))
                continue

            def build(name=name):
                paths = store.fetch(name)
                records = records_from_feeds(paths, country=country, source=name)
                docs = len({r["doc_id"] for r in records})
                words = sum(len(r["text"].split()) for r in records)
                out(
                    f"{name}: {len(records)} chunk(s) from {docs} page(s) "
                    f"across {len(paths)} feed(s), ~{words:,} words"
                )
                return records

            if not upsert:
                _preview(build(), out)
                results.append(Result(corpus, DRY_RUN))
                continue
            recorded = True  # from here on replace_corpus records the attempt itself
            run = replace_corpus(
                country=country, corpus=corpus, marker=newest, build=build, force=force, out=out
            )
            results.append(Result(corpus, run.status))
        except Exception as exc:  # one source must not take the others down
            out(f"{name}: FAILED, rows left as they are: {exc!r}")
            if upsert and not recorded:
                record_failure(country, corpus, exc)
            results.append(Result(corpus, FAILED))
    return results
