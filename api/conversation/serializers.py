from rest_framework import serializers

from .models import Conversation, Message


class MessageSerializer(serializers.ModelSerializer):
    # parts/sources are EncryptedJSONField (stored as text); declare them
    # explicitly so DRF serializes the decrypted native JSON rather than a
    # stringified column.
    parts = serializers.JSONField()
    sources = serializers.JSONField(required=False)

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
        ]


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
