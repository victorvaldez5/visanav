import uuid
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from django.utils import timezone

from core.fields import EncryptedJSONField


class Conversation(models.Model):
    title = models.CharField(max_length=255, blank=True, null=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="conversations",
    )
    uuid = models.UUIDField(unique=True, editable=False, auto_created=True, default=uuid.uuid4)
    created_at = models.DateTimeField(auto_now_add=True)

    # Retention: when this conversation becomes eligible for automatic deletion
    # (see the purge_expired_conversations command). NULL means "keep" — set for
    # users who opt into retaining their history, and never touched while a legal
    # hold is in place.
    expires_at = models.DateTimeField(null=True, blank=True, db_index=True)
    # A preservation duty (subpoena / litigation hold) exempts a conversation
    # from auto-deletion. Toggled by ops in the admin; the purge command skips
    # any row with this set. See README "Data retention".
    legal_hold = models.BooleanField(default=False)

    def __str__(self):
        return self.title or f"Conversation {self.pk}"

    def _profile(self):
        """The owner's profile, or None (anonymous, or no profile row)."""
        if self.user_id is None:
            return None
        try:
            return self.user.profile
        except ObjectDoesNotExist:
            return None

    def compute_expiry(self, *, now=None):
        """Return the expires_at this conversation should carry under policy.

        NULL (keep) when it is under legal hold, when its owner opted into
        retaining history, or when the applicable retention window is disabled
        (0 days). Otherwise a window measured from ``now``.
        """
        if self.legal_hold:
            return None
        if self.user_id is None:
            days = settings.CONVERSATION_ANON_RETENTION_DAYS
        else:
            profile = self._profile()
            if profile is not None and profile.retain_history:
                return None
            days = settings.CONVERSATION_USER_RETENTION_DAYS
        if not days or days <= 0:
            return None
        return (now or timezone.now()) + timedelta(days=days)

    def apply_retention_policy(self, *, now=None):
        """Set expires_at from policy. Call on create and on each new turn."""
        self.expires_at = self.compute_expiry(now=now)


class Message(models.Model):
    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="messages"
    )
    # Encrypted at rest: the raw pydantic-ai message dicts hold the actual
    # conversation content (the user's questions and the assistant's replies).
    # See core/encryption.py for what this does and does not protect against.
    parts = EncryptedJSONField()
    timestamp = models.DateTimeField(default=timezone.now)
    model_name = models.CharField(max_length=255, blank=True, null=True)
    instructions = models.TextField(blank=True, null=True)
    kind = models.CharField(max_length=100)
    # Official sources cited for an assistant reply (title, url, last_verified,
    # score) — the retrieval results that grounded the answer, shown in the UI as
    # clickable citations. Encrypted at rest like `parts` since which sources a
    # turn cited can hint at what the user asked; only response messages set it.
    sources = EncryptedJSONField(blank=True, null=True)

    def __str__(self):
        return f"Message {self.pk} ({self.kind})"


class Feedback(models.Model):
    message = models.OneToOneField(
        Message, on_delete=models.CASCADE, related_name="feedback"
    )
    is_helpful = models.BooleanField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Feedback for Message {self.message.id}: {self.is_helpful}"
