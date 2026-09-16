"""Delete conversations whose retention window has passed.

This is the enforcement half of the retention policy set on each conversation
(``Conversation.apply_retention_policy``). Run it on a schedule — e.g. a daily
Railway cron service or a scheduled GitHub Action:

    python manage.py purge_expired_conversations

Rows with ``legal_hold=True`` are never deleted, and rows with a NULL
``expires_at`` (opted-in history, disabled window) are kept. Deleting a
Conversation cascades to its Messages and Feedback.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone

from conversation.models import Conversation


class Command(BaseCommand):
    help = "Delete conversations past their retention window (skips legal holds)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would be deleted without deleting anything.",
        )

    def handle(self, *args, **options):
        now = timezone.now()
        expired = Conversation.objects.filter(
            expires_at__isnull=False,
            expires_at__lt=now,
            legal_hold=False,
        )
        count = expired.count()

        if options["dry_run"]:
            self.stdout.write(
                f"[dry-run] {count} conversation(s) past retention would be deleted."
            )
            return

        if not count:
            self.stdout.write("No conversations past retention.")
            return

        deleted, by_model = expired.delete()
        messages = by_model.get("conversation.Message", 0)
        self.stdout.write(
            self.style.SUCCESS(
                f"Deleted {count} expired conversation(s) "
                f"({messages} message(s), {deleted} rows total)."
            )
        )
