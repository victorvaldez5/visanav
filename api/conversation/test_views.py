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


# --- feedback ----------------------------------------------------------------

from conversation.models import Feedback, FeedbackDaily  # noqa: E402

TEXT_PARTS = [{"part_kind": "text", "content": "Here is how."}]


def feedback_url(conv):
    return reverse("conversation-feedback", kwargs={"uuid": conv.uuid})


def make_response(conv, parts=TEXT_PARTS, kind="response"):
    return Message.objects.create(conversation=conv, kind=kind, parts=parts)


def vote(client, conv, message_id, is_helpful):
    return client.post(
        feedback_url(conv),
        {"message": message_id, "is_helpful": is_helpful},
        format="json",
    )


def tally():
    row = FeedbackDaily.objects.first()
    return (row.helpful, row.not_helpful) if row else (0, 0)


def test_feedback_happy_path_for_owner(api_client, user):
    conv = Conversation.objects.create(user=user)
    msg = make_response(conv)
    api_client.force_authenticate(user)
    resp = vote(api_client, conv, msg.id, True)
    assert resp.status_code == 200
    assert resp.json() == {"message": msg.id, "is_helpful": True}
    assert Feedback.objects.get(message=msg).is_helpful is True
    assert tally() == (1, 0)
    # The conversation payload now carries the vote.
    detail = api_client.get(detail_url(conv)).json()
    assert [m["feedback"] for m in detail["messages"]] == [True]


def test_feedback_is_idempotent_toggles_and_clears(api_client, user):
    conv = Conversation.objects.create(user=user)
    msg = make_response(conv)
    api_client.force_authenticate(user)
    vote(api_client, conv, msg.id, True)
    vote(api_client, conv, msg.id, True)
    assert tally() == (1, 0)
    vote(api_client, conv, msg.id, False)
    assert tally() == (0, 1)
    assert Feedback.objects.count() == 1
    resp = vote(api_client, conv, msg.id, None)
    assert resp.status_code == 200 and resp.json()["is_helpful"] is None
    assert tally() == (0, 0)
    assert Feedback.objects.count() == 0
    vote(api_client, conv, msg.id, None)  # clearing nothing is a no-op
    assert tally() == (0, 0)
    detail = api_client.get(detail_url(conv)).json()
    assert detail["messages"][0]["feedback"] is None


def test_feedback_on_anonymous_conversation_by_uuid(api_client):
    conv = Conversation.objects.create()
    msg = make_response(conv)
    resp = vote(api_client, conv, msg.id, False)
    assert resp.status_code == 200
    assert tally() == (0, 1)


def test_feedback_404_for_another_users_conversation(api_client, user, other_user):
    conv = Conversation.objects.create(user=other_user)
    msg = make_response(conv)
    api_client.force_authenticate(user)
    assert vote(api_client, conv, msg.id, True).status_code == 404
    assert Feedback.objects.count() == 0


def test_feedback_404_for_owned_conversation_when_anonymous(api_client, user):
    conv = Conversation.objects.create(user=user)
    msg = make_response(conv)
    assert vote(api_client, conv, msg.id, True).status_code == 404


def test_feedback_404_for_message_in_another_conversation(api_client):
    conv = Conversation.objects.create()
    other = Conversation.objects.create()
    foreign = make_response(other)
    resp = vote(api_client, conv, foreign.id, True)
    assert resp.status_code == 404
    assert Feedback.objects.count() == 0


def test_feedback_404s_are_identical(api_client):
    conv = Conversation.objects.create()
    request_row = make_response(conv, kind="request", parts=TEXT_PARTS)
    tool_only = make_response(conv, parts=[{"part_kind": "tool-call", "tool_name": "x"}])
    bodies = {
        vote(api_client, conv, request_row.id, True).content,
        vote(api_client, conv, tool_only.id, True).content,
        vote(api_client, conv, 999999, True).content,
    }
    assert len(bodies) == 1
    assert vote(api_client, conv, request_row.id, True).status_code == 404
    assert vote(api_client, conv, tool_only.id, True).status_code == 404
    assert Feedback.objects.count() == 0


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"message": 1},
        {"is_helpful": True},
        {"message": "1", "is_helpful": True},
        {"message": True, "is_helpful": True},
        {"message": 1, "is_helpful": "yes"},
        {"message": 1, "is_helpful": 1},
    ],
)
def test_feedback_bad_body_is_400(api_client, payload):
    conv = Conversation.objects.create()
    make_response(conv)
    resp = api_client.post(feedback_url(conv), payload, format="json")
    assert resp.status_code == 400


def test_feedback_is_throttled(api_client, settings):
    from rest_framework.settings import api_settings

    conv = Conversation.objects.create()
    msg = make_response(conv)
    rates = dict(api_settings.DEFAULT_THROTTLE_RATES, feedback="2/hour")
    from rest_framework.throttling import ScopedRateThrottle

    ScopedRateThrottle.THROTTLE_RATES = rates
    try:
        codes = [vote(api_client, conv, msg.id, True).status_code for _ in range(3)]
    finally:
        ScopedRateThrottle.THROTTLE_RATES = api_settings.DEFAULT_THROTTLE_RATES
    assert codes == [200, 200, 429]


def test_error_logs_never_contain_the_conversation_uuid(api_client, caplog):
    import logging

    from rest_framework.throttling import ScopedRateThrottle

    conv = Conversation.objects.create()
    msg = make_response(conv)
    missing = Conversation.objects.create()
    missing_url = feedback_url(missing)
    missing.delete()
    with caplog.at_level(logging.DEBUG):
        assert api_client.post(
            missing_url, {"message": 1, "is_helpful": True}, format="json"
        ).status_code == 404
        assert vote(api_client, conv, 999999, True).status_code == 404
        ScopedRateThrottle.THROTTLE_RATES = dict(
            ScopedRateThrottle.THROTTLE_RATES, feedback="1/hour"
        )
        try:
            vote(api_client, conv, msg.id, True)
            assert vote(api_client, conv, msg.id, True).status_code == 429
        finally:
            ScopedRateThrottle.THROTTLE_RATES = dict(
                ScopedRateThrottle.THROTTLE_RATES, feedback="60/hour"
            )
    # caplog's handler sits on the root logger, after the logger-level filter.
    lines = [r.getMessage() for r in caplog.records]
    assert any("Too Many Requests" in m or "Not Found" in m for m in lines)
    for uuid_text in (str(conv.uuid), str(missing.uuid)):
        assert not any(uuid_text in m for m in lines)


def test_feedback_throttle_ignores_spoofed_leftmost_xff(api_client):
    from rest_framework.throttling import ScopedRateThrottle

    conv = Conversation.objects.create()
    msg = make_response(conv)
    original = ScopedRateThrottle.THROTTLE_RATES
    ScopedRateThrottle.THROTTLE_RATES = dict(original, feedback="2/hour")
    try:
        codes = [
            api_client.post(
                feedback_url(conv),
                {"message": msg.id, "is_helpful": True},
                format="json",
                HTTP_X_FORWARDED_FOR=f"7.7.7.{i}, 203.0.113.9",
            ).status_code
            for i in range(3)
        ]
    finally:
        ScopedRateThrottle.THROTTLE_RATES = original
    assert codes == [200, 200, 429]
