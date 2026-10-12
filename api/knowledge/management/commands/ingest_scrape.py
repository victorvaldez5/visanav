"""Ingest the scrapers' JSONL feeds into the pgvector store.

    python manage.py ingest_scrape path/to/items/            # DRY RUN: extract + chunk
    python manage.py ingest_scrape path/to/items/ --upsert   # embed (Voyage) + write
    python manage.py ingest_scrape path/to/items/ --source ecfr --upsert

The argument is the feeds root: one subdirectory of *.jsonl feeds per source
(uscis/, ecfr/, federal-register/), the layout of raw/items/ in R2 and of a
LOCAL_TEST crawl's output/items/. Pull it from R2 with
scrapers/uscis_scraper/pull_feeds.py. Keep every feed, not just the newest:
crawls are incremental, so each snapshot is rebuilt by merging them all.

One run ingests every source (--source narrows it). Each source's corpus is
replaced in its own transaction, so one source never touches another's rows or
the curated chunks written by `ingest`. A source with no feeds is skipped and
keeps its rows; if a source fails, the others still commit and the command
exits non-zero.
"""
import time
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from knowledge.models import KnowledgeChunk
from knowledge.scrape_utils import SOURCES, records_from_feeds

_EMBED_BATCH = 128
_RETRIES = 5


class Command(BaseCommand):
    help = "Chunk + embed scraped pages (JSONL feeds, one directory per source) into the pgvector store."

    def add_arguments(self, parser):
        parser.add_argument(
            "feeds_root",
            help="directory holding one subdirectory of JSONL feeds per source",
        )
        parser.add_argument(
            "--source",
            action="append",
            dest="sources",
            metavar="NAME",
            help=f"only this source (repeatable; default: all of {', '.join(SOURCES)})",
        )
        parser.add_argument("--country", default="us")
        parser.add_argument(
            "--upsert",
            action="store_true",
            help="embed + write to the database (default: dry run)",
        )

    def handle(self, *args, **options):
        root = Path(options["feeds_root"])
        names = options["sources"] or list(SOURCES)
        unknown = [n for n in names if n not in SOURCES]
        if unknown:
            raise CommandError(
                f"Unknown source(s): {', '.join(unknown)}. Valid sources: {', '.join(SOURCES)}"
            )
        if not root.is_dir():
            raise CommandError(f"Feeds root not found: {root}")
        if any(root.glob("*.jsonl")) and not any((root / n).is_dir() for n in SOURCES):
            raise CommandError(
                f"{root} holds feed files directly. Pass the feeds root instead: the "
                f"directory containing one subdirectory per source ({', '.join(SOURCES)})."
            )
        upsert = options["upsert"]
        if upsert and not settings.VOYAGE_API_KEY:
            raise CommandError("--upsert requires VOYAGE_API_KEY")

        code = options["country"].lower()
        failed = []
        for name in dict.fromkeys(names):
            paths = sorted((root / name).glob("*.jsonl"))
            if not paths:
                self.stdout.write(
                    self.style.WARNING(f"{name}: no feeds in {root / name}; skipped, rows left as they are")
                )
                continue
            try:
                self._ingest(name, paths, code, upsert)
            except Exception as exc:  # one source must not take the others down
                failed.append(name)
                self.stderr.write(self.style.ERROR(f"{name}: FAILED, rows left as they are: {exc!r}"))

        if not upsert:
            self.stdout.write("(dry run; pass --upsert to embed + write)")
        if failed:
            raise CommandError(f"{len(failed)} source(s) failed: {', '.join(failed)}")

    def _ingest(self, name, paths, code, upsert):
        corpus = SOURCES[name].corpus
        records = records_from_feeds(paths, country=code, source=name)
        docs = len({r["doc_id"] for r in records})
        words = sum(len(r["text"].split()) for r in records)
        self.stdout.write(
            f"{name}: {len(records)} chunk(s) from {docs} page(s) "
            f"across {len(paths)} feed(s), ~{words:,} words"
        )

        if not upsert:
            for r in records[:3]:
                self.stdout.write(f"  [{r['topic']}] {r['chunk_id']}: {r['text'][:100]}...")
            return

        # Feeds that yield nothing mean a broken crawl or extractor, not an empty
        # source: never replace a corpus with nothing.
        if not records:
            raise CommandError("no chunks extracted from the feeds")

        vectors = self._embed([r["text"] for r in records])
        objs = [KnowledgeChunk(embedding=vec, **rec) for rec, vec in zip(records, vectors)]

        with transaction.atomic():
            deleted, _ = KnowledgeChunk.objects.filter(country=code, corpus=corpus).delete()
            KnowledgeChunk.objects.bulk_create(objs, batch_size=500)

        self.stdout.write(
            self.style.SUCCESS(
                f"✓ upserted {len(objs)} '{corpus}' chunk(s) for '{code}' "
                f"(replaced {deleted} existing row(s)) using {settings.EMBEDDING_MODEL}"
            )
        )

    def _embed(self, texts):
        """Embed in batches with progress, backing off on Voyage rate limits.

        A full corpus is dozens of calls, enough to hit a low-tier rate limit;
        every vector is gathered before the DB write, so a failure here leaves
        the existing rows untouched.
        """
        import voyageai.error

        from core.embeddings import embed_documents

        out = []
        for i in range(0, len(texts), _EMBED_BATCH):
            batch = texts[i:i + _EMBED_BATCH]
            for attempt in range(_RETRIES):
                try:
                    out.extend(embed_documents(batch))
                    break
                except voyageai.error.RateLimitError:
                    if attempt == _RETRIES - 1:
                        raise
                    wait = 20 * (attempt + 1)
                    self.stdout.write(f"  rate limited; retrying in {wait}s")
                    time.sleep(wait)
            self.stdout.write(f"  embedded {len(out)}/{len(texts)}")
        return out
