"""Ingest the USCIS scraper's JSONL feeds into the pgvector store.

    python manage.py ingest_scrape path/to/feeds/            # DRY RUN: extract + chunk
    python manage.py ingest_scrape path/to/feeds/ --upsert   # embed (Voyage) + write

Feeds are the scraper's raw/items/uscis/*.jsonl (pull them from R2 with
scrapers/uscis_scraper/pull_feeds.py, or point at a LOCAL_TEST crawl's
output/items/uscis/). Pass every feed, not just the newest: crawls are
incremental, so the snapshot is rebuilt by merging them all.

--upsert transactionally replaces only the country's "uscis" corpus rows, so the
curated chunks written by `ingest` are left alone (and vice versa).
"""
import time
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from knowledge.models import KnowledgeChunk
from knowledge.scrape_utils import CORPUS, records_from_feeds

_EMBED_BATCH = 128
_RETRIES = 5


class Command(BaseCommand):
    help = "Chunk + embed scraped USCIS pages (JSONL feeds) into the pgvector store."

    def add_arguments(self, parser):
        parser.add_argument(
            "feeds", nargs="+", help="JSONL feed files, or directories of them"
        )
        parser.add_argument("--country", default="us")
        parser.add_argument(
            "--upsert",
            action="store_true",
            help="embed + write to the database (default: dry run)",
        )

    def handle(self, *args, **options):
        paths = []
        for arg in options["feeds"]:
            p = Path(arg)
            paths.extend(sorted(p.glob("*.jsonl")) if p.is_dir() else [p])
        missing = [p for p in paths if not p.is_file()]
        if missing or not paths:
            raise CommandError(f"No feed files found (missing: {missing or options['feeds']})")

        code = options["country"].lower()
        records = records_from_feeds(paths, country=code)
        docs = len({r["doc_id"] for r in records})
        words = sum(len(r["text"].split()) for r in records)
        self.stdout.write(
            f"{code.upper()}: {len(records)} chunk(s) from {docs} page(s) "
            f"across {len(paths)} feed(s), ~{words:,} words"
        )

        if not options["upsert"]:
            for r in records[:3]:
                self.stdout.write(f"  [{r['topic']}] {r['chunk_id']}: {r['text'][:100]}...")
            self.stdout.write("  (dry run; pass --upsert to embed + write)")
            return

        if not settings.VOYAGE_API_KEY:
            raise CommandError("--upsert requires VOYAGE_API_KEY")
        if not records:
            raise CommandError("No chunks extracted from the feeds")

        vectors = self._embed([r["text"] for r in records])
        objs = [KnowledgeChunk(embedding=vec, **rec) for rec, vec in zip(records, vectors)]

        with transaction.atomic():
            deleted, _ = KnowledgeChunk.objects.filter(country=code, corpus=CORPUS).delete()
            KnowledgeChunk.objects.bulk_create(objs, batch_size=500)

        self.stdout.write(
            self.style.SUCCESS(
                f"✓ upserted {len(objs)} '{CORPUS}' chunk(s) for '{code}' "
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
