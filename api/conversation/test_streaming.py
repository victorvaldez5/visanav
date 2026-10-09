"""Request-level tests for the SSE chat endpoint (`conversation.streaming.chat_stream`).

These are the first async tests in the suite: they use pytest-asyncio
(`asyncio_mode = "strict"` + `@pytest.mark.asyncio`, applied module-wide) and
Django's `AsyncClient` to drive the real `/api/chat/` URL. The agent is replaced
with a `FunctionModel` that streams canned text and calls no tools, so no LLM or
Voyage network call happens; `ALLOW_MODEL_REQUESTS = False` guards against an
accidental real request. `transaction=True` is required because the view does its
ORM work through `sync_to_async`/`asyncio.to_thread` on separate connections.
"""
import json
import uuid

import pytest
from asgiref.sync import sync_to_async
from django.core.cache import cache
from django.test import AsyncClient, override_settings
from django.urls import reverse
from pydantic_ai import Agent, models
from pydantic_ai.models.function import DeltaToolCall, FunctionModel
from rest_framework_simplejwt.tokens import AccessToken

from conversation import streaming
from conversation.models import Conversation, Message
from core.llm import Deps

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.asyncio]

CHAT_URL = reverse("chat_stream")


# --- fake agent --------------------------------------------------------------


async def _stream_reply(messages, info):
    """A FunctionModel stream function: emit plain text, never a tool call."""
    yield "Hola. "
    yield "Puedo explicarte el proceso."


def _fake_agent():
    return Agent(FunctionModel(stream_function=_stream_reply), deps_type=Deps)


async def _stream_tool_call(messages, info):
    """A FunctionModel stream function that never stops calling a tool.

    Every model turn streams one `ping` tool call, so the agent's tool-calling
    loop never terminates on its own — the only thing that can end the run is a
    usage limit.
    """
    yield {0: DeltaToolCall(name="ping", json_args="{}", tool_call_id=uuid.uuid4().hex)}


def _tool_looping_agent():
    """An agent whose model calls `ping` forever; bound it with a tool-calls limit."""
    agent = Agent(FunctionModel(stream_function=_stream_tool_call), deps_type=Deps)

    @agent.tool_plain
    def ping() -> str:
        return "pong"

    return agent


@pytest.fixture
def use_fake_agent(monkeypatch):
    """Swap the real agent for the FunctionModel one and block real requests."""
    agent = _fake_agent()
    monkeypatch.setattr(streaming, "get_agent", lambda: agent)
    monkeypatch.setattr(models, "ALLOW_MODEL_REQUESTS", False)
    return agent


# --- fixtures ----------------------------------------------------------------


@pytest.fixture(autouse=True)
def clear_rate_limit_cache():
    """LocMemCache is per-process; isolate the rate limiter between tests."""
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def user(transactional_db, django_user_model):
    return django_user_model.objects.create_user(
        username="carla", email="carla@example.com", password="pw12345!"
    )


@pytest.fixture
def other_user(transactional_db, django_user_model):
    return django_user_model.objects.create_user(
        username="mateo", email="mateo@example.com", password="pw12345!"
    )


@pytest.fixture
def anon_conv(transactional_db):
    return Conversation.objects.create()


@pytest.fixture
def owned_conv(transactional_db, user):
    return Conversation.objects.create(user=user)


def bearer(user):
    return f"Bearer {AccessToken.for_user(user)}"


def body(conversation="", message="Hello, how do I renew my green card?"):
    return json.dumps({"user_message": message, "conversation": str(conversation)})


async def drain(response):
    text = ""
    async for chunk in response.streaming_content:
        text += chunk.decode() if isinstance(chunk, (bytes, bytearray)) else chunk
    return text


# --- method / validation gate ------------------------------------------------


async def test_options_preflight_returns_204():
    resp = await AsyncClient().options(CHAT_URL)
    assert resp.status_code == 204


async def test_get_is_method_not_allowed():
    resp = await AsyncClient().get(CHAT_URL)
    assert resp.status_code == 405


async def test_invalid_json_body_is_400():
    resp = await AsyncClient().post(CHAT_URL, data="{not json", content_type="application/json")
    assert resp.status_code == 400


async def test_empty_message_is_400(anon_conv):
    resp = await AsyncClient().post(
        CHAT_URL, data=body(anon_conv.uuid, message="   "), content_type="application/json"
    )
    assert resp.status_code == 400


async def test_message_too_long_is_400(anon_conv):
    with override_settings(CHAT_MAX_MESSAGE_CHARS=10):
        resp = await AsyncClient().post(
            CHAT_URL, data=body(anon_conv.uuid, message="x" * 11), content_type="application/json"
        )
    assert resp.status_code == 400


async def test_bad_conversation_uuid_is_400():
    resp = await AsyncClient().post(
        CHAT_URL, data=body("not-a-uuid"), content_type="application/json"
    )
    assert resp.status_code == 400


# --- auth / authorization ----------------------------------------------------


async def test_invalid_token_is_401(anon_conv):
    # Note: AsyncClient (ASGI) reads auth from the `headers=` kwarg, not the
    # WSGI-style HTTP_AUTHORIZATION extra (which it silently ignores).
    resp = await AsyncClient().post(
        CHAT_URL,
        data=body(anon_conv.uuid),
        content_type="application/json",
        headers={"Authorization": "Bearer not.a.real.jwt"},
    )
    assert resp.status_code == 401


async def test_conversation_not_found_is_404():
    resp = await AsyncClient().post(
        CHAT_URL, data=body(uuid.uuid4()), content_type="application/json"
    )
    assert resp.status_code == 404


async def test_owned_conversation_forbidden_for_anonymous(owned_conv):
    resp = await AsyncClient().post(
        CHAT_URL, data=body(owned_conv.uuid), content_type="application/json"
    )
    assert resp.status_code == 403


async def test_owned_conversation_forbidden_for_other_user(owned_conv, other_user):
    resp = await AsyncClient().post(
        CHAT_URL,
        data=body(owned_conv.uuid),
        content_type="application/json",
        headers={"Authorization": bearer(other_user)},
    )
    assert resp.status_code == 403


async def test_owner_may_post_to_their_conversation(owned_conv, user, use_fake_agent):
    # A valid token must resolve to the owner and pass the ownership check — the
    # two 403 cases can't prove that on their own (anonymous also yields 403).
    resp = await AsyncClient().post(
        CHAT_URL,
        data=body(owned_conv.uuid),
        content_type="application/json",
        headers={"Authorization": bearer(user)},
    )
    assert resp.status_code == 200


# --- rate limiting -----------------------------------------------------------


async def test_rate_limit_returns_429_json(anon_conv):
    # Limit of 1: the first POST consumes the window (its stream is left undrained,
    # so the agent never runs), the second trips the limiter.
    with override_settings(CHAT_RATE_LIMIT_PER_MINUTE=1):
        first = await AsyncClient().post(
            CHAT_URL, data=body(anon_conv.uuid), content_type="application/json"
        )
        second = await AsyncClient().post(
            CHAT_URL, data=body(anon_conv.uuid), content_type="application/json"
        )
    assert first.status_code == 200
    assert second.status_code == 429
    assert second.json()["detail"].startswith("Rate limit")


async def test_rate_limit_disabled_when_zero(anon_conv):
    with override_settings(CHAT_RATE_LIMIT_PER_MINUTE=0):
        for _ in range(3):
            resp = await AsyncClient().post(
                CHAT_URL, data=body(anon_conv.uuid), content_type="application/json"
            )
            assert resp.status_code != 429


# --- happy path --------------------------------------------------------------


async def test_streams_frames_and_persists_the_turn(anon_conv, use_fake_agent):
    resp = await AsyncClient().post(
        CHAT_URL, data=body(anon_conv.uuid), content_type="application/json"
    )
    assert resp.status_code == 200
    assert resp["Content-Type"] == "text/event-stream"

    stream = await drain(resp)
    assert "event: status\ndata: {\"step\": \"writing\"}" in stream
    assert "event: delta" in stream
    assert f'event: done\ndata: {{"conversation": "{anon_conv.uuid}"}}' in stream

    # The turn (user request + assistant response) was persisted.
    count = await sync_to_async(Message.objects.filter(conversation_id=anon_conv.id).count)()
    assert count >= 1
    refreshed = await sync_to_async(Conversation.objects.get)(id=anon_conv.id)
    assert refreshed.expires_at is not None  # retention window was touched


# --- reply language ----------------------------------------------------------


@pytest.fixture
def captured_deps(monkeypatch):
    """Spy on the view's Deps construction; returns the kwargs it was built with."""
    captured = {}
    real_deps = streaming.Deps

    def spy(**kwargs):
        captured.update(kwargs)
        return real_deps(**kwargs)

    monkeypatch.setattr(streaming, "Deps", spy)
    return captured


@pytest.mark.parametrize(
    ("accept_language", "expected"),
    [
        ("es", "es"),
        ("ES", "es"),  # case-insensitive
        ("es-MX", "es"),  # regional variant -> base language
        ("fr", "en"),  # unsupported -> LANGUAGE_CODE
        (None, "en"),  # no header -> LANGUAGE_CODE
    ],
)
async def test_accept_language_sets_the_reply_locale(
    anon_conv, use_fake_agent, captured_deps, accept_language, expected
):
    """The Accept-Language header reaches Deps.locale via LocaleMiddleware.

    The frontends send the active UI locale as Accept-Language; LocaleMiddleware
    negotiates it onto settings.LANGUAGES, and the view hands the result to the
    agent as Deps.locale (which drives the reply language).
    """
    headers = {"Accept-Language": accept_language} if accept_language else {}
    resp = await AsyncClient().post(
        CHAT_URL, data=body(anon_conv.uuid), content_type="application/json", headers=headers
    )
    assert resp.status_code == 200
    await drain(resp)  # Deps is built inside the stream, so drive the generator
    assert captured_deps["locale"] == expected


# --- per-turn agent budget ---------------------------------------------------


async def test_tool_calls_limit_breach_ends_with_content_free_error(anon_conv, monkeypatch):
    """A tool-calls-limit breach ends the turn with the generic error frame.

    CHAT_TOOL_CALLS_LIMIT caps how many tools a single run may call; a runaway or
    adversarial loop trips it and pydantic-ai raises UsageLimitExceeded from
    inside the streaming graph. The view must turn that into the content-free
    `error` frame — never a `done`, and never echoing the library's limit message
    (which embeds the internal counters) to the client. This is a regression
    guard: the breach reaches the error path through a pydantic-ai internal
    (the tool-node error is re-raised on the next graph advance, past the view's
    best-effort tool-status `except`), so a library bump could silently drop it.
    """
    agent = _tool_looping_agent()
    monkeypatch.setattr(streaming, "get_agent", lambda: agent)
    monkeypatch.setattr(models, "ALLOW_MODEL_REQUESTS", False)

    # Isolate the tool-calls cap: disable the request/token caps so the ONLY
    # thing that can stop the infinite ping loop is CHAT_TOOL_CALLS_LIMIT.
    with override_settings(
        CHAT_TOOL_CALLS_LIMIT=1, CHAT_REQUEST_LIMIT=0, CHAT_TOTAL_TOKENS_LIMIT=0
    ):
        resp = await AsyncClient().post(
            CHAT_URL, data=body(anon_conv.uuid), content_type="application/json"
        )
        assert resp.status_code == 200
        stream = await drain(resp)

    # The turn ends with the generic, content-free error frame...
    assert "event: error" in stream
    assert '"detail": "The assistant failed to respond. Please try again."' in stream
    # ...not a success, and without leaking the library's limit message/counters.
    assert "event: done" not in stream
    assert "tool_calls_limit" not in stream
    assert "UsageLimitExceeded" not in stream

    # A breached turn persists no partial/garbage assistant message.
    count = await sync_to_async(
        Message.objects.filter(conversation_id=anon_conv.id).count
    )()
    assert count == 0


# --- localized errors ---------------------------------------------------------


async def test_validation_errors_follow_accept_language():
    es = await AsyncClient().post(
        CHAT_URL, data="{not json", content_type="application/json", headers={"Accept-Language": "es"}
    )
    en = await AsyncClient().post(CHAT_URL, data="{not json", content_type="application/json")

    assert es.json()["detail"] == "El cuerpo de la solicitud no es un JSON válido"
    assert en.json()["detail"] == "Invalid JSON body"


async def test_too_long_message_error_interpolates_the_limit_in_spanish(anon_conv):
    with override_settings(CHAT_MAX_MESSAGE_CHARS=10):
        resp = await AsyncClient().post(
            CHAT_URL,
            data=body(anon_conv.uuid, message="x" * 11),
            content_type="application/json",
            headers={"Accept-Language": "es"},
        )

    assert resp.json()["detail"] == "El mensaje es demasiado largo (máximo 10 caracteres)."
