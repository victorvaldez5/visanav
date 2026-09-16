from datetime import datetime, timedelta, timezone as dt_timezone
from io import StringIO
from types import SimpleNamespace

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from conversation.models import Conversation, Message

NOW = datetime(2026, 1, 1, tzinfo=dt_timezone.utc)


class RetentionPolicyTests(SimpleTestCase):
    """compute_expiry is pure (no DB) for these branches."""

    @override_settings(CONVERSATION_ANON_RETENTION_DAYS=7)
    def test_anonymous_expires_after_anon_window(self):
        conv = Conversation()  # user_id is None
        conv.apply_retention_policy(now=NOW)
        self.assertEqual(conv.expires_at, NOW + timedelta(days=7))

    def test_legal_hold_never_expires(self):
        conv = Conversation(legal_hold=True)
        conv.apply_retention_policy(now=NOW)
        self.assertIsNone(conv.expires_at)

    @override_settings(CONVERSATION_USER_RETENTION_DAYS=30)
    def test_signed_in_without_optin_expires(self):
        conv = Conversation(user_id=1)
        conv._profile = lambda: SimpleNamespace(retain_history=False)
        conv.apply_retention_policy(now=NOW)
        self.assertEqual(conv.expires_at, NOW + timedelta(days=30))

    def test_signed_in_optin_is_kept(self):
        conv = Conversation(user_id=1)
        conv._profile = lambda: SimpleNamespace(retain_history=True)
        conv.apply_retention_policy(now=NOW)
        self.assertIsNone(conv.expires_at)

    @override_settings(CONVERSATION_ANON_RETENTION_DAYS=0)
    def test_zero_window_disables_expiry(self):
        conv = Conversation()
        conv.apply_retention_policy(now=NOW)
        self.assertIsNone(conv.expires_at)


class PurgeCommandTests(TestCase):
    def test_purges_only_expired_and_unheld(self):
        past = timezone.now() - timedelta(days=1)
        future = timezone.now() + timedelta(days=1)

        expired = Conversation.objects.create(expires_at=past)
        Message.objects.create(
            conversation=expired, parts={"content": "sensitive"}, kind="request"
        )
        held = Conversation.objects.create(expires_at=past, legal_hold=True)
        fresh = Conversation.objects.create(expires_at=future)
        kept = Conversation.objects.create(expires_at=None)

        call_command("purge_expired_conversations", stdout=StringIO())

        surviving = set(Conversation.objects.values_list("id", flat=True))
        self.assertEqual(surviving, {held.id, fresh.id, kept.id})
        # Deleting the conversation cascaded to its (encrypted) message.
        self.assertEqual(Message.objects.count(), 0)

    def test_dry_run_deletes_nothing(self):
        Conversation.objects.create(expires_at=timezone.now() - timedelta(days=1))
        call_command("purge_expired_conversations", "--dry-run", stdout=StringIO())
        self.assertEqual(Conversation.objects.count(), 1)


class EncryptedRoundTripThroughORMTests(TestCase):
    def test_message_parts_round_trip(self):
        conv = Conversation.objects.create()
        payload = [{"role": "user", "content": "How do I renew my green card?"}]
        Message.objects.create(conversation=conv, parts=payload, kind="request")

        # Read back through the ORM: decrypts to the original native JSON.
        stored = Message.objects.get(conversation=conv)
        self.assertEqual(stored.parts, payload)

        # And the raw column is ciphertext, not the plaintext question.
        from django.db import connection

        with connection.cursor() as cur:
            cur.execute(
                "SELECT parts FROM conversation_message WHERE id = %s", [stored.id]
            )
            raw = cur.fetchone()[0]
        self.assertNotIn("green card", raw)
