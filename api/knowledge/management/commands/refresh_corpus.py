"""Bring the whole vector store up to date. This is what the scheduler runs.

    python manage.py refresh_corpus

Ingests whatever is due and nothing else:
  - the curated data/ corpus, when its chunks differ from the last ingest (in
    practice: after a deploy that changed data/), and
  - each scrape source whose newest feed in R2 has not been ingested yet (in
    practice: after that source's crawl finishes).

With nothing due it exits in seconds, so it is safe to run every hour. Each
corpus is replaced independently; if any fails or is held back by the shrink
guard, the others still commit and the command exits non-zero. It is the same
work as `ingest <cc> --only-due --upsert` followed by
`ingest_scrape --from-r2 --only-due --upsert`, under one lock.
"""
import tempfile
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from knowledge.corpus import (
    FAILED,
    Result,
    ingest_lock,
    record_failure,
    refresh_curated,
    refresh_scraped,
)
from knowledge.feed_store import R2Feeds
from knowledge.scrape_utils import SOURCES


class Command(BaseCommand):
    help = "Ingest every corpus that is due: curated data/ and each scrape source's new feeds from R2."

    def add_arguments(self, parser):
        parser.add_argument("--country", default=settings.KNOWLEDGE_COUNTRY)
        parser.add_argument(
            "--force", action="store_true",
            help="replace a corpus even if the new one is much smaller",
        )

    def handle(self, *args, **options):
        if not settings.VOYAGE_API_KEY:
            raise CommandError("refresh_corpus requires VOYAGE_API_KEY")
        country, out = options["country"].lower(), self.stdout.write
        kwargs = dict(upsert=True, only_due=True, force=options["force"], out=out)

        with ingest_lock() as acquired:
            if not acquired:
                out("Another ingestion run is in progress; nothing done.")
                return
            results = [refresh_curated(country, **kwargs)]
            with tempfile.TemporaryDirectory() as workdir:
                try:
                    store = R2Feeds.from_settings(Path(workdir))
                except Exception as exc:
                    out(f"scrape sources: FAILED, cannot read feeds: {exc!r}")
                    for source in SOURCES.values():
                        record_failure(country, source.corpus, exc)
                        results.append(Result(source.corpus, FAILED))
                else:
                    results += refresh_scraped(store, list(SOURCES), country, **kwargs)

        out("summary: " + ", ".join(f"{r.corpus}={r.status}" for r in results))
        bad = [r.corpus for r in results if r.bad]
        if bad:
            raise CommandError(f"{len(bad)} corpus(es) not refreshed: {', '.join(bad)}")
