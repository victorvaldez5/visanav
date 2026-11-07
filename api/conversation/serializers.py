from django.core.exceptions import ObjectDoesNotExist
from rest_framework import serializers

from .models import Conversation, Message


class MessageSerializer(serializers.ModelSerializer):
    # parts/sources are EncryptedJSONField (stored as text); declare them
    # explicitly so DRF serializes the decrypted native JSON rather than a
    # stringified column.
    parts = serializers.JSONField()
    sources = serializers.JSONField(required=False)
    feedback = serializers.SerializerMethodField()

    def get_feedback(self, obj):
        # Reverse OneToOne raises when absent; null means "no vote". With
        # prefetch_related("messages__feedback") this costs no extra query.
        try:
            return obj.feedback.is_helpful
        except ObjectDoesNotExist:
            return None

    class Meta:
        model = Message
        fields = [
            "id",
            "conversation",
            "timestamp",
            "model_name",
            "instructions",
            "kind",
            "parts",
            "sources",
            "feedback",
        ]
        read_only_fields = ["feedback"]


class ConversationSerializer(serializers.ModelSerializer):
    messages = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = ["id", "uuid", "title", "user", "created_at", "expires_at", "messages"]
        read_only_fields = ["id", "uuid", "created_at", "expires_at", "user"]

    def get_messages(self, obj):
        # Keep the prefetched rows but guarantee chronological order; the
        # related manager has no default ordering.
        messages = sorted(obj.messages.all(), key=lambda m: m.id)
        return MessageSerializer(messages, many=True).data
