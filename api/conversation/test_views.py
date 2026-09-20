"""Request-level tests for the conversation REST viewset (``ConversationViewSet``).

This is the REST half of the core feature — listing/retrieving conversation
history and the ownership rules that keep conversations private — as opposed to
the SSE stream (test_streaming.py) and the retention model (test_privacy.py).

Ownership shape worth keeping in mind while reading:
- ``get_queryset`` scopes an authenticated user to *their own* conversations, so
  another user's row is simply *not found* (404), never a 403.
- An anonymous caller may retrieve/delete an *anonymous* conversation by UUID
  (they are public and un-owned), but an owned conversation is filtered out (404).
"""
import pytest
from django.core.cache import cache
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from conversation.models import Conversation, Message

pytestmark = pytest.mark.django_db

LIST_URL = reverse("conversation-list")


def detail_url(conv):
    return reverse("conversation-detail", kwargs={"uuid": conv.uuid})


def _rows(resp):
    data = resp.json()
    return data["results"] if isinstance(data, dict) and "results" in data else data


@pytest.fixture(autouse=True)
def clear_cache():
    """The per-user list cache and DRF throttles share the process LocMemCache;
    isolate every test from bleed."""
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user(django_user_model):
    return django_user_model.objects.create_user(
        username="carla", email="carla@example.com", password="pw12345!"
    )


@pytest.fixture
def other_user(django_user_model):
    return django_user_model.objects.create_user(
        username="mateo", email="mateo@example.com", password="pw12345!"
    )


# --- list --------------------------------------------------------------------


def test_anonymous_list_is_empty(api_client):
    Conversation.objects.create()  # an anonymous conversation exists...
    rows = _rows(api_client.get(LIST_URL))
    assert rows == []  # ...but listing is not an enumeration endpoint for anon


def test_list_returns_only_the_callers_conversations(api_client, user, other_user):
    Conversation.objects.create(user=user, title="mine 1")
    Conversation.objects.create(user=user, title="mine 2")
    Conversation.objects.create(user=other_user, title="not mine")

    api_client.force_authenticate(user=user)
    rows = _rows(api_client.get(LIST_URL))

    assert {r["title"] for r in rows} == {"mine 1", "mine 2"}


def test_list_is_cached_per_user_until_busted(api_client, user):
    Conversation.objects.create(user=user, title="first")
    api_client.force_authenticate(user=user)

    assert len(_rows(api_client.get(LIST_URL))) == 1  # populates the cache

    # A row added out-of-band doesn't bust the cache, so the list is still stale.
    Conversation.objects.create(user=user, title="second")
    assert len(_rows(api_client.get(LIST_URL))) == 1

    cache.clear()  # after invalidation the new row shows up
    assert len(_rows(api_client.get(LIST_URL))) == 2


# --- create ------------------------------------------------------------------


def test_authenticated_create_owns_conversation_and_stamps_expiry(api_client, user):
    api_client.force_authenticate(user=user)

    resp = api_client.post(LIST_URL, {"title": "Green card renewal"}, format="json")

    assert resp.status_code == status.HTTP_201_CREATED
    conv = Conversation.objects.get(uuid=resp.data["uuid"])
    assert conv.user == user
    assert conv.expires_at is not None  # user retention window applied on create


def test_anonymous_create_is_unowned_and_stamps_expiry(api_client):
    resp = api_client.post(LIST_URL, {"title": "Anon question"}, format="json")

    assert resp.status_code == status.HTTP_201_CREATED
    conv = Conversation.objects.get(uuid=resp.data["uuid"])
    assert conv.user is None
    assert conv.expires_at is not None  # anon retention window applied on create


# --- retrieve ----------------------------------------------------------------


def test_owner_can_retrieve_their_conversation_with_messages(api_client, user):
    conv = Conversation.objects.create(user=user, title="mine")
    Message.objects.create(conversation=conv, parts={"content": "hi"}, kind="request")

    api_client.force_authenticate(user=user)
    resp = api_client.get(detail_url(conv))

    assert resp.status_code == status.HTTP_200_OK
    assert resp.data["uuid"] == str(conv.uuid)
    assert len(resp.data["messages"]) == 1


def test_anonymous_can_retrieve_an_anonymous_conversation(api_client):
    conv = Conversation.objects.create(title="public")
    resp = api_client.get(detail_url(conv))
    assert resp.status_code == status.HTTP_200_OK


def test_anonymous_cannot_retrieve_an_owned_conversation(api_client, user):
    conv = Conversation.objects.create(user=user)
    resp = api_client.get(detail_url(conv))
    assert resp.status_code == status.HTTP_404_NOT_FOUND


def test_other_user_cannot_retrieve_someone_elses_conversation(api_client, user, other_user):
    conv = Conversation.objects.create(user=user)
    api_client.force_authenticate(user=other_user)
    resp = api_client.get(detail_url(conv))
    assert resp.status_code == status.HTTP_404_NOT_FOUND


# --- delete / ownership ------------------------------------------------------


def test_owner_can_delete_their_conversation(api_client, user):
    conv = Conversation.objects.create(user=user)
    api_client.force_authenticate(user=user)

    resp = api_client.delete(detail_url(conv))

    assert resp.status_code == status.HTTP_204_NO_CONTENT
    assert not Conversation.objects.filter(pk=conv.pk).exists()


def test_anonymous_conversation_is_publicly_deletable_by_uuid(api_client):
    conv = Conversation.objects.create()
    resp = api_client.delete(detail_url(conv))
    assert resp.status_code == status.HTTP_204_NO_CONTENT
    assert not Conversation.objects.filter(pk=conv.pk).exists()


def test_other_user_cannot_delete_someone_elses_conversation(api_client, user, other_user):
    conv = Conversation.objects.create(user=user)
    api_client.force_authenticate(user=other_user)

    resp = api_client.delete(detail_url(conv))

    assert resp.status_code == status.HTTP_404_NOT_FOUND
    assert Conversation.objects.filter(pk=conv.pk).exists()
