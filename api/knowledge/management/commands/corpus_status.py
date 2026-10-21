"""What is in the vector store, and how fresh each corpus is.

    python manage.py corpus_status      # also: just db-status
"""
from django.core.management.base import BaseCommand
from django.db.models import Count

from knowledge.corpus import last_success
from knowledge.models import IngestRun, KnowledgeChunk


class Command(BaseCommand):
    help = "Chunk counts per country / corpus / topic, and each corpus's last ingestion."

    def handle(self, *args, **options):
        out = self.stdout.write
        rows = (
            KnowledgeChunk.objects.values("country", "corpus", "topic")
            .annotate(n=Count("id"))
            .order_by("country", "corpus", "topic")
        )
        for r in rows:
            out(f"{r['country']:3} {r['corpus']:17} {r['topic'] or '-':17} {r['n']:6}")
        out(f"total chunks: {KnowledgeChunk.objects.count()}")

        out("")
        out("last ingestion per corpus:")
        pairs = sorted(
            set(KnowledgeChunk.objects.values_list("country", "corpus").distinct())
            | set(IngestRun.objects.values_list("country", "corpus").distinct())
        )
        for country, corpus in pairs:
            ok = last_success(country, corpus)
            latest = IngestRun.objects.filter(country=country, corpus=corpus).first()
            if ok is None:
                line = "never ingested on record"
            else:
                line = (
                    f"{ok.finished_at:%Y-%m-%d %H:%M} UTC, {ok.chunks} chunk(s) "
                    f"({ok.embedded} embedded), marker {ok.marker}"
                )
            if latest is not None and latest.status != IngestRun.SUCCEEDED:
                line += (
                    f"  | latest attempt {latest.status} at "
                    f"{latest.started_at:%Y-%m-%d %H:%M} UTC: {latest.error[:120]}"
                )
            out(f"{country:3} {corpus:17} {line}")
