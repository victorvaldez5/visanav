import uuid
from django.conf import settings
from django.db import models
from django.utils import timezone


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

    def __str__(self):
        return self.title or f"Conversation {self.pk}"


class Message(models.Model):
    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="messages"
    )
    parts = models.JSONField()
    timestamp = models.DateTimeField(default=timezone.now)
    model_name = models.CharField(max_length=255, blank=True, null=True)
    instructions = models.TextField(blank=True, null=True)
    kind = models.CharField(max_length=100)

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
