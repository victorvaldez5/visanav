from django.conf import settings
from django.core.cache import cache
from rest_framework import permissions, status, viewsets
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle

from core.utils import per_user_cache_key
from .models import Conversation
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


# Create your views here.
class ConversationViewSet(viewsets.ModelViewSet):
    lookup_field = 'uuid'
    lookup_value_converter = 'uuid'
    queryset = Conversation.objects.all()
    serializer_class = ConversationSerializer
    permission_classes = [IsOwnerOrReadOnly]
    throttle_classes = [UserRateThrottle, AnonRateThrottle]

    def list(self, request, *args, **kwargs):
        cache_key = per_user_cache_key("conversation-list", request.user)
        cached = cache.get(cache_key)
        if cached:
            return Response(data=cached, status=status.HTTP_200_OK)
        response = super().list(request, *args, **kwargs)
        cache.set(cache_key, response.data, settings.CACHE_MIDDLEWARE_SECONDS)
        return response

    def perform_create(self, serializer):
        user = self.request.user if self.request.user.is_authenticated else None
        # associate the logged-in user
        serializer.save(user=user)
        cache_key = per_user_cache_key("conversation-list", user)
        cache.delete(cache_key)

    def get_queryset(self):
        if self.request.user.is_authenticated:
            return Conversation.objects.filter(
                user=self.request.user.id
            ).select_related("user").prefetch_related("messages")
        conversation = self.kwargs.get(self.lookup_field, None)
        if conversation is not None:
            return Conversation.objects.filter(
                uuid=conversation, user__isnull=True
            ).select_related("user").prefetch_related("messages")
        return Conversation.objects.none()
