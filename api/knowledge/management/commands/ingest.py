"""Ingest curated knowledge Markdown into the pgvector store.

    python manage.py ingest us            # DRY RUN: chunk + preview, no keys/DB
    python manage.py ingest us --upsert   # embed (Voyage) + write KnowledgeChunk rows

--upsert transactionally replaces the country's curated chunks (delete + bulk
insert), so re-ingesting reaps chunks whose content changed. Only new or changed
chunks are embedded. Needs VOYAGE_API_KEY and a reachable database.

--only-due does nothing when the chunks are the same as the last successful
ingest. --force overrides the shrink guard (see knowledge/corpus.py).

Reads Markdown from settings.KNOWLEDGE_DATA_DIR: a repo checkout, or /app/data
in the API and ingest images. In production the scheduled `refresh_corpus`
command runs this for you after each deploy.
"""
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from knowledge.corpus import ingest_lock, refresh_curated


class Command(BaseCommand):
    help = "Chunk + embed curated knowledge Markdown into the pgvector store."

    def add_arguments(self, parser):
        parser.add_argument("country", help="ISO alpha-2 country code, e.g. us")
        parser.add_argument(
            "--upsert",
            action="store_true",
            help="embed + write to the database (default: dry run)",
        )
        parser.add_argument(
            "--only-due", action="store_true",
            help="do nothing if the chunks are unchanged since the last successful ingest",
        )
        parser.add_argument(
            "--force", action="store_true",
            help="replace the corpus even if the new one is much smaller",
        )

    def handle(self, *args, **options):
        code = options["country"].lower()
        cdir = Path(settings.KNOWLEDGE_DATA_DIR) / code
        if not cdir.exists():
            raise CommandError(f"No such country under {settings.KNOWLEDGE_DATA_DIR}: {code}")
        upsert = options["upsert"]
        if not upsert:
            refresh_curated(code, upsert=False, only_due=options["only_due"], out=self.stdout.write)
            self.stdout.write("(dry run; pass --upsert to embed + write)")
            return
        if not settings.VOYAGE_API_KEY:
            raise CommandError("--upsert requires VOYAGE_API_KEY")

        with ingest_lock() as acquired:
            if not acquired:
                self.stdout.write("Another ingestion run is in progress; nothing done.")
                return
            result = refresh_curated(
                code, upsert=True, only_due=options["only_due"], force=options["force"],
                out=self.stdout.write,
            )
        if result.bad:
            raise CommandError(f"curated corpus for '{code}' was not replaced ({result.status})")
