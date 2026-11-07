"""Privacy-safe usage counters and feedback tallies.

    python manage.py usage_stats [--days 30]      # also: just usage-stats
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from conversation.models import FeedbackDaily, UsageDaily

COLUMNS = (
    "turns",
    "new_conversations",
    "turns_searched",
    "turns_with_sources",
    "turns_with_resources",
    "failed_turns",
)


class Command(BaseCommand):
    help = "Per-day usage counters (by locale) and feedback totals for the last N days."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=30)

    def handle(self, *args, **options):
        out = self.stdout.write
        since = timezone.now().date() - timedelta(days=options["days"] - 1)

        rows = UsageDaily.objects.filter(date__gte=since).order_by("date", "locale")
        header = f"{'date':10} {'loc':6}" + "".join(f" {c[:12]:>12}" for c in COLUMNS)
        out(header)
        totals = dict.fromkeys(COLUMNS, 0)
        for r in rows:
            out(f"{r.date:%Y-%m-%d} {r.locale:6}" + "".join(f" {getattr(r, c):12}" for c in COLUMNS))
            for c in COLUMNS:
                totals[c] += getattr(r, c)
        out(f"{'total':17}" + "".join(f" {totals[c]:12}" for c in COLUMNS))

        out("")
        helpful = not_helpful = 0
        out(f"{'date':10} {'helpful':>8} {'not_helpful':>12}")
        for r in FeedbackDaily.objects.filter(date__gte=since).order_by("date"):
            out(f"{r.date:%Y-%m-%d} {r.helpful:8} {r.not_helpful:12}")
            helpful += r.helpful
            not_helpful += r.not_helpful
        votes = helpful + not_helpful
        rate = f"{100 * helpful / votes:.0f}%" if votes else "n/a"
        out(f"votes: {votes} (helpful {helpful}, not helpful {not_helpful}); helpful rate: {rate}")
