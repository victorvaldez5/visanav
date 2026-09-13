from rest_framework import serializers

from .models import Conversation, Message


class MessageSerializer(serializers.ModelSerializer):
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
        ]


class ConversationSerializer(serializers.ModelSerializer):
    messages = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = ["id", "uuid", "title", "user", "created_at", "messages"]
        read_only_fields = ["id", "uuid", "created_at", "user"]

    def get_messages(self, obj):
        # Keep the prefetched rows but guarantee chronological order; the
        # related manager has no default ordering.
        messages = sorted(obj.messages.all(), key=lambda m: m.id)
        return MessageSerializer(messages, many=True).data
