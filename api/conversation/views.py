from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle, ScopedRateThrottle, UserRateThrottle

from core.utils import per_user_cache_key
from . import metrics
from .models import Conversation, Feedback, Message
from .serializers import ConversationSerializer


class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    Object-level permission to only allow owners of an object to edit it.
    Assumes the model instance has an `owner` attribute.
    """

    def has_object_permission(self, request, view, obj):
        # Read permissions are allowed to any request,
        # so we'll always allow GET, HEAD or OPTIONS requests.
        if request.method in permissions.SAFE_METHODS:
            return True

        # Instance must have an attribute named `owner`.
        user = getattr(obj, "user")
        if user is None:
            # anonymous user can create and their conversations are public
            return True
        return obj.user == request.user


def _has_text(message) -> bool:
    """True when a response row carries a text part (not just tool calls)."""
    parts = message.parts
    return isinstance(parts, list) and any(
        isinstance(p, dict) and p.get("part_kind") == "text" and p.get("content")
        for p in parts
    )


# Create your views here.
class ConversationViewSet(viewsets.ModelViewSet):
    lookup_field = 'uuid'
    lookup_value_converter = 'uuid'
    queryset = Conversation.objects.all()
    serializer_class = ConversationSerializer
    permission_classes = [IsOwnerOrReadOnly]
    throttle_classes = [UserRateThrottle, AnonRateThrottle]

    @property
    def throttle_scope(self):
        # Read by ScopedRateThrottle; only the feedback action is scoped.
        return "feedback" if getattr(self, "action", None) == "feedback" else None

    def list(self, request, *args, **kwargs):
        cache_key = per_user_cache_key("conversation-list", request.user)
        cached = cache.get(cache_key)
        if cached:
            return Response(data=cached, status=status.HTTP_200_OK)
        response = super().list(request, *args, **kwargs)
        cache.set(cache_key, response.data, settings.CACHE_MIDDLEWARE_SECONDS)
        return response

    @action(
        detail=True,
        methods=["post"],
        throttle_classes=[ScopedRateThrottle, AnonRateThrottle, UserRateThrottle],
    )
    def feedback(self, request, uuid=None):
        """Vote on (or clear the vote on) one assistant reply.

        Never log the conversation uuid or message id alongside a vote.
        """
        # Conversation visibility and write permission come only from here.
        conversation = self.get_object()

        data = request.data if isinstance(request.data, dict) else {}
        message_id = data.get("message")
        if (
            "message" not in data
            or "is_helpful" not in data
            or isinstance(message_id, bool)
            or not isinstance(message_id, int)
            or not (data["is_helpful"] is None or isinstance(data["is_helpful"], bool))
        ):
            return Response(
                {"detail": "Expected {message: int, is_helpful: true|false|null}."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        new = data["is_helpful"]
        not_found = Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        with transaction.atomic():
            message = (
                Message.objects.select_for_update()
                .filter(pk=message_id, conversation=conversation, kind="response")
                .first()
            )
            if message is None or not _has_text(message):
                return not_found
            existing = Feedback.objects.filter(message=message).first()
            old = existing.is_helpful if existing else None
            if new is None:
                if existing:
                    existing.delete()
            elif existing:
                if old != new:
                    existing.is_helpful = new
                    existing.save(update_fields=["is_helpful"])
            else:
                Feedback.objects.create(message=message, is_helpful=new)
            metrics.apply_vote(message, old, new)
        return Response({"message": message_id, "is_helpful": new})

    def perform_create(self, serializer):
        user = self.request.user if self.request.user.is_authenticated else None
        # associate the logged-in user
        conversation = serializer.save(user=user)
        # Stamp the initial retention window (refreshed each turn in streaming).
        conversation.apply_retention_policy()
        conversation.save(update_fields=["expires_at"])
        cache_key = per_user_cache_key("conversation-list", user)
        cache.delete(cache_key)

    def get_queryset(self):
        if self.request.user.is_authenticated:
            return Conversation.objects.filter(
                user=self.request.user.id
            ).select_related("user").prefetch_related("messages__feedback")
        conversation = self.kwargs.get(self.lookup_field, None)
        if conversation is not None:
            return Conversation.objects.filter(
                uuid=conversation, user__isnull=True
            ).select_related("user").prefetch_related("messages__feedback")
        return Conversation.objects.none()
