"""Ingest curated knowledge Markdown into the pgvector store.

    python manage.py ingest us            # DRY RUN: chunk + preview, no keys/DB
    python manage.py ingest us --upsert   # embed (Voyage) + write KnowledgeChunk rows

--upsert transactionally replaces the country's curated chunks (delete + bulk insert),
mirroring the old Pinecone per-namespace overwrite so re-ingesting reaps chunks
whose content changed. Needs VOYAGE_API_KEY and a reachable database.

Reads Markdown from settings.KNOWLEDGE_DATA_DIR (a full repo checkout), so run it
locally or from CI — not inside the slim prod web image, which omits data/.
"""
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from knowledge.ingest_utils import records_for_country
from knowledge.models import KnowledgeChunk

_EMBED_BATCH = 128


class Command(BaseCommand):
    help = "Chunk + embed curated knowledge Markdown into the pgvector store."

    def add_arguments(self, parser):
        parser.add_argument("country", help="ISO alpha-2 country code, e.g. us")
        parser.add_argument(
            "--upsert",
            action="store_true",
            help="embed + write to the database (default: dry run)",
        )

    def handle(self, *args, **options):
        code = options["country"].lower()
        cdir = Path(settings.KNOWLEDGE_DATA_DIR) / code
        if not cdir.exists():
            raise CommandError(f"No such country under {settings.KNOWLEDGE_DATA_DIR}: {code}")

        records = records_for_country(code)
        self.stdout.write(f"{code.upper()}: {len(records)} chunk(s)")

        if not options["upsert"]:
            for r in records[:3]:
                preview = r["text"][:100].replace("\n", " ")
                self.stdout.write(f"  [{r.get('topic')}] {r['chunk_id']}: {preview}...")
            if len(records) > 3:
                self.stdout.write(
                    f"  ... and {len(records) - 3} more (dry run; pass --upsert to write)"
                )
            return

        if not settings.VOYAGE_API_KEY:
            raise CommandError("--upsert requires VOYAGE_API_KEY")
        if not records:
            raise CommandError(f"No knowledge chunks found for {code}")

        # Embed here (not in ingest_utils) so the dry run stays key/network-free.
        from core.embeddings import embed_documents

        vectors = embed_documents([r["text"] for r in records])
        objs = [KnowledgeChunk(embedding=vec, **rec) for rec, vec in zip(records, vectors)]

        with transaction.atomic():
            deleted, _ = KnowledgeChunk.objects.filter(country=code, corpus="curated").delete()
            KnowledgeChunk.objects.bulk_create(objs, batch_size=_EMBED_BATCH)

        self.stdout.write(
            self.style.SUCCESS(
                f"✓ upserted {len(objs)} chunk(s) for '{code}' "
                f"(replaced {deleted} existing row(s)) using {settings.EMBEDDING_MODEL}"
            )
        )
