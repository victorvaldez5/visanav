"""Async, streaming chat endpoint.

Replaces the previous Celery + Redis "enqueue a task and poll" flow. Because a
chat turn is almost entirely I/O-bound (waiting on OpenAI / Pinecone), a single
async view can hold many concurrent in-flight turns cheaply, and stream tokens
back over Server-Sent Events (SSE) as they are produced.
"""
import json
import logging
import uuid

from asgiref.sync import sync_to_async
from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponse, JsonResponse, StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt
from pydantic_ai import Agent
from pydantic_ai.messages import (
    FunctionToolCallEvent,
    ModelMessagesTypeAdapter,
    PartDeltaEvent,
    PartStartEvent,
    TextPart,
    TextPartDelta,
)
from pydantic_core import to_jsonable_python
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError

from core.llm import Deps, get_agent
from .models import Conversation, Message

logger = logging.getLogger(__name__)


def _sse(event: str, data: dict) -> str:
    """Format a single Server-Sent Event frame."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _client_ip(request) -> str:
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "unknown")


@sync_to_async
def _authenticate(request):
    """Resolve the request user from a JWT bearer token, allowing anonymous."""
    auth = JWTAuthentication()
    header = auth.get_header(request)
    if header is None:
        return None
    raw_token = auth.get_raw_token(header)
    if raw_token is None:
        return None
    validated = auth.get_validated_token(raw_token)
    return auth.get_user(validated)


@sync_to_async
def _get_conversation(conversation_uuid):
    """Look a conversation up by its public UUID.

    Anonymous conversations are readable by anyone who knows their key, so the
    key must be unguessable: the sequential integer id would let a client
    enumerate other people's chats and pull their history into a reply.
    """
    return Conversation.objects.filter(uuid=conversation_uuid).first()


# The persisted fields that make up a pydantic-ai message. Notably this excludes
# the Django-only columns (`id` and the `conversation` FK): pydantic-ai's message
# models define their own `conversation_id` field (a str), so feeding it our FK
# column — an int — makes ModelMessagesTypeAdapter reject the whole history.
_MESSAGE_FIELDS = ("parts", "instructions", "kind", "timestamp", "model_name")


@sync_to_async
def _load_history(conversation_id):
    qs = (
        Message.objects.filter(conversation_id=conversation_id)
        .order_by("id")
        .values(*_MESSAGE_FIELDS)
    )
    return ModelMessagesTypeAdapter.validate_python(
        to_jsonable_python(list(qs))
    )


@sync_to_async
def _persist_messages(conversation_id, new_messages):
    """Persist the new messages produced by an agent run (user request +
    tool calls + assistant response), mirroring the old task's shape."""
    for message in new_messages:
        if message.get("kind") == "response":
            Message.objects.create(
                conversation_id=conversation_id,
                parts=message.get("parts"),
                timestamp=message.get("timestamp"),
                model_name=message.get("model_name"),
                kind=message.get("kind"),
            )
        else:
            Message.objects.create(
                conversation_id=conversation_id,
                parts=message.get("parts"),
                instructions=message.get("instructions"),
                kind=message.get("kind"),
            )


@sync_to_async
def _touch_retention(conversation_id):
    """Refresh the conversation's retention window after a new turn.

    Retention is measured from the last message, so an active chat keeps
    resetting its clock and an abandoned one ages out. A legal hold or an
    opted-in owner resolves to expires_at = NULL (kept).
    """
    conversation = (
        Conversation.objects.select_related("user__profile")
        .filter(id=conversation_id)
        .first()
    )
    if conversation is None:
        return
    conversation.apply_retention_policy()
    conversation.save(update_fields=["expires_at"])


@sync_to_async
def _check_rate_limit(identity: str, limit: int, window: int = 60) -> bool:
    """Soft fixed-window limiter to cap LLM spend from any one client.

    Backed by the default cache (LocMemCache in the single-box deployment), so
    the limit is per-process rather than global; it is a cost safety net, not a
    hard quota. Pair it with a hard monthly budget cap at the LLM provider.
    """
    if limit <= 0:
        return True
    key = f"chat-rate:{identity}"
    count = cache.get(key, 0)
    if count >= limit:
        return False
    cache.set(key, count + 1, timeout=window)
    return True


@csrf_exempt
async def chat_stream(request):
    """POST {conversation: <uuid>, user_message} -> text/event-stream reply.

    SSE events emitted:
      - status: {"step": "researching" | "writing"}
      - delta:  {"text": "<token chunk>"}
      - done:   {"conversation": "<uuid>"}
      - error:  {"detail": "<message>"}
    """
    if request.method == "OPTIONS":
        # CORS preflight; CorsMiddleware attaches the headers.
        return HttpResponse(status=204)
    if request.method != "POST":
        return JsonResponse({"detail": "Method not allowed"}, status=405)

    try:
        body = json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"detail": "Invalid JSON body"}, status=400)

    user_message = (body.get("user_message") or "").strip()
    if not user_message:
        return JsonResponse({"detail": "user_message is required"}, status=400)
    if len(user_message) > settings.CHAT_MAX_MESSAGE_CHARS:
        return JsonResponse(
            {
                "detail": (
                    f"Message too long (max {settings.CHAT_MAX_MESSAGE_CHARS} "
                    "characters)."
                )
            },
            status=400,
        )
    try:
        conversation_uuid = uuid.UUID(str(body.get("conversation") or ""))
    except ValueError:
        return JsonResponse(
            {"detail": "conversation must be a conversation uuid"}, status=400
        )

    try:
        user = await _authenticate(request)
    except (InvalidToken, TokenError):
        return JsonResponse({"detail": "Invalid or expired token"}, status=401)

    identity = f"user:{user.id}" if user is not None else f"ip:{_client_ip(request)}"
    if not await _check_rate_limit(identity, settings.CHAT_RATE_LIMIT_PER_MINUTE):
        return JsonResponse(
            {"detail": "Rate limit exceeded. Please wait a moment and try again."},
            status=429,
        )

    conversation = await _get_conversation(conversation_uuid)
    if conversation is None:
        return JsonResponse({"detail": "Conversation not found"}, status=404)

    # Authorization mirrors IsOwnerOrReadOnly: user-less conversations are
    # public; owned conversations require their owner.
    if conversation.user_id is not None:
        if user is None or conversation.user_id != user.id:
            return JsonResponse({"detail": "Forbidden"}, status=403)

    conversation_id = conversation.id
    history = await _load_history(conversation_id)

    async def event_stream():
        # Scope retrieval to a populated country corpus. Curated knowledge is
        # ingested per country, so default to KNOWLEDGE_COUNTRY; this is where the
        # user's own country could be threaded through in future.
        deps = Deps(country=settings.KNOWLEDGE_COUNTRY)
        started_text = False
        try:
            async with get_agent().iter(
                user_message, message_history=history, deps=deps
            ) as run:
                async for node in run:
                    if Agent.is_model_request_node(node):
                        async with node.stream(run.ctx) as request_stream:
                            async for event in request_stream:
                                text = None
                                if isinstance(event, PartStartEvent) and isinstance(
                                    event.part, TextPart
                                ):
                                    text = event.part.content
                                elif isinstance(event, PartDeltaEvent) and isinstance(
                                    event.delta, TextPartDelta
                                ):
                                    text = event.delta.content_delta
                                if text:
                                    if not started_text:
                                        started_text = True
                                        yield _sse("status", {"step": "writing"})
                                    yield _sse("delta", {"text": text})
                    elif Agent.is_call_tools_node(node):
                        # Tool-progress status is best-effort: never let it
                        # break the actual reply.
                        try:
                            async with node.stream(run.ctx) as tool_stream:
                                async for event in tool_stream:
                                    if isinstance(event, FunctionToolCallEvent):
                                        yield _sse("status", {"step": "researching"})
                        except Exception:  # noqa: BLE001
                            logger.debug(
                                "tool status stream failed", exc_info=True
                            )

            new_messages = json.loads(run.result.new_messages_json())
            await _persist_messages(conversation_id, new_messages)
            await _touch_retention(conversation_id)
            yield _sse("done", {"conversation": str(conversation_uuid)})
        except Exception:  # noqa: BLE001 - surface a clean error, log the rest
            logger.exception(
                "chat stream failed for conversation %s", conversation_uuid
            )
            yield _sse(
                "error",
                {"detail": "The assistant failed to respond. Please try again."},
            )

    response = StreamingHttpResponse(
        event_stream(), content_type="text/event-stream"
    )
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"  # disable proxy buffering (nginx, etc.)
    return response
