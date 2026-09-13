from django.urls import path
from rest_framework.routers import DefaultRouter

from .streaming import chat_stream
from .views import ConversationViewSet

conversation_router = DefaultRouter(use_regex_path=False)
conversation_router.register(r"conversations", ConversationViewSet, basename="conversation")

urlpatterns = conversation_router.urls

urlpatterns += [
    path("chat/", chat_stream, name="chat_stream"),
]
