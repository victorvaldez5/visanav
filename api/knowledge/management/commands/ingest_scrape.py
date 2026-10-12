"""Ingest the scrapers' JSONL feeds into the pgvector store.

    python manage.py ingest_scrape path/to/items/            # DRY RUN: extract + chunk
    python manage.py ingest_scrape path/to/items/ --upsert   # embed (Voyage) + write
    python manage.py ingest_scrape path/to/items/ --source ecfr --upsert
    python manage.py ingest_scrape --from-r2 --only-due --upsert   # what the scheduler runs

The feeds come from a feeds root on disk (one subdirectory of *.jsonl feeds per
source: uscis/, ecfr/, federal-register/, the layout of raw/items/ in R2 and of
a LOCAL_TEST crawl's output/items/; pull it with
scrapers/uscis_scraper/pull_feeds.py), or with --from-r2 straight from the
bucket the crawls write to. Every feed of a source is read, not just the newest:
crawls are incremental, so each snapshot is rebuilt by merging them all.

One run ingests every source (--source narrows it). Each source's corpus is
replaced in its own transaction, so one source never touches another's rows or
the curated chunks written by `ingest`. A source with no feeds is skipped and
keeps its rows; if a source fails, the others still commit and the command
exits non-zero.

--only-due skips a source whose newest feed was already ingested successfully.
--force overrides the shrink guard, which otherwise refuses to replace a corpus
with a much smaller one. Only new or changed chunks are embedded. See
knowledge/corpus.py.
"""
import tempfile
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from knowledge.corpus import ingest_lock, refresh_scraped
from knowledge.feed_store import LocalFeeds, R2Feeds
from knowledge.scrape_utils import SOURCES


class Command(BaseCommand):
    help = "Chunk + embed scraped pages (JSONL feeds, one directory per source) into the pgvector store."

    def add_arguments(self, parser):
        parser.add_argument(
            "feeds_root", nargs="?",
            help="directory holding one subdirectory of JSONL feeds per source",
        )
        parser.add_argument(
            "--from-r2", action="store_true",
            help="read the feeds from the R2 bucket instead of a local feeds root",
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
        parser.add_argument(
            "--only-due", action="store_true",
            help="skip a source whose newest feed was already ingested successfully",
        )
        parser.add_argument(
            "--force", action="store_true",
            help="replace a corpus even if the new one is much smaller",
        )

    def handle(self, *args, **options):
        names = options["sources"] or list(SOURCES)
        unknown = [n for n in names if n not in SOURCES]
        if unknown:
            raise CommandError(
                f"Unknown source(s): {', '.join(unknown)}. Valid sources: {', '.join(SOURCES)}"
            )
        if bool(options["feeds_root"]) == options["from_r2"]:
            raise CommandError("Give a feeds root directory or --from-r2 (one of them)")
        upsert = options["upsert"]
        if upsert and not settings.VOYAGE_API_KEY:
            raise CommandError("--upsert requires VOYAGE_API_KEY")

        with tempfile.TemporaryDirectory() as workdir:
            store = self._store(options, Path(workdir))
            kwargs = dict(
                upsert=upsert, only_due=options["only_due"], force=options["force"],
                out=self.stdout.write,
            )
            if not upsert:
                results = refresh_scraped(store, names, options["country"].lower(), **kwargs)
                self.stdout.write("(dry run; pass --upsert to embed + write)")
            else:
                with ingest_lock() as acquired:
                    if not acquired:
                        self.stdout.write("Another ingestion run is in progress; nothing done.")
                        return
                    results = refresh_scraped(store, names, options["country"].lower(), **kwargs)

        bad = [r.corpus for r in results if r.bad]
        if bad:
            raise CommandError(f"{len(bad)} source(s) failed: {', '.join(bad)}")

    def _store(self, options, workdir):
        if options["from_r2"]:
            return R2Feeds.from_settings(workdir)
        root = Path(options["feeds_root"])
        if not root.is_dir():
            raise CommandError(f"Feeds root not found: {root}")
        if any(root.glob("*.jsonl")) and not any((root / n).is_dir() for n in SOURCES):
            raise CommandError(
                f"{root} holds feed files directly. Pass the feeds root instead: the "
                f"directory containing one subdirectory per source ({', '.join(SOURCES)})."
            )
        return LocalFeeds(root)
