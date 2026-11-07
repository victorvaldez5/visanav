"""Usage counters: recorded per completed turn, content-free, never fatal."""
import json
from datetime import date, timedelta
from io import StringIO

import pytest
from asgiref.sync import sync_to_async
from django.core.management import call_command
from django.test import AsyncClient
from django.utils import timezone
from pydantic_ai import Agent, models
from pydantic_ai.models.function import FunctionModel

from conversation import metrics, streaming
from conversation.models import Conversation, FeedbackDaily, Message, UsageDaily
from conversation.test_streaming import CHAT_URL, body, drain, _stream_tool_call
from core.llm import Deps

pytestmark = pytest.mark.django_db(transaction=True)


async def _plain(messages, info):
    yield "Hola."


def _install(monkeypatch, agent):
    monkeypatch.setattr(streaming, "get_agent", lambda: agent)
    monkeypatch.setattr(models, "ALLOW_MODEL_REQUESTS", False)


def _searching_agent():
    """Calls a tool that mimics semantic_search + resource_lookup, then answers."""
    state = {"n": 0}

    async def stream(messages, info):
        from pydantic_ai.models.function import DeltaToolCall

        state["n"] += 1
        if state["n"] == 1:
            yield {0: DeltaToolCall(name="lookup", json_args="{}", tool_call_id="t1")}
        else:
            yield "Listo."

    agent = Agent(FunctionModel(stream_function=stream), deps_type=Deps)

    @agent.tool
    async def lookup(ctx) -> str:
        ctx.deps.searched = True
        ctx.deps.sources.append({"title": "t", "url": "https://x.gov"})
        ctx.deps.resources_suggested = 3
        return "ok"

    return agent


@sync_to_async
def usage_rows():
    return list(UsageDaily.objects.values())


@pytest.mark.asyncio
async def test_first_turn_with_search_and_resources(monkeypatch):
    conv = await sync_to_async(Conversation.objects.create)()
    _install(monkeypatch, _searching_agent())
    resp = await AsyncClient().post(
        CHAT_URL, data=body(conv.uuid), content_type="application/json",
        headers={"Accept-Language": "es"},
    )
    stream = await drain(resp)
    assert "event: done" in stream
    done = json.loads(stream.split("event: done\ndata: ")[1].split("\n")[0])
    mid = done["message"]
    assert isinstance(mid, int)
    kind = await sync_to_async(lambda: Message.objects.get(pk=mid).kind)()
    assert kind == "response"

    (row,) = await usage_rows()
    assert row["locale"] == "es" and row["date"] == timezone.now().date()
    assert (row["turns"], row["new_conversations"], row["turns_searched"]) == (1, 1, 1)
    assert (row["turns_with_sources"], row["turns_with_resources"], row["failed_turns"]) == (1, 1, 0)


@pytest.mark.asyncio
async def test_second_turn_is_not_a_new_conversation(monkeypatch):
    conv = await sync_to_async(Conversation.objects.create)()
    _install(monkeypatch, Agent(FunctionModel(stream_function=_plain), deps_type=Deps))
    for _ in range(2):
        await drain(await AsyncClient().post(
            CHAT_URL, data=body(conv.uuid), content_type="application/json"))
    (row,) = await usage_rows()
    assert (row["turns"], row["new_conversations"], row["turns_searched"]) == (2, 1, 0)
    assert (row["turns_with_sources"], row["turns_with_resources"]) == (0, 0)


@pytest.mark.asyncio
async def test_failed_turn_counts_and_client_sees_usual_error(monkeypatch):
    from django.test import override_settings

    conv = await sync_to_async(Conversation.objects.create)()
    agent = Agent(FunctionModel(stream_function=_stream_tool_call), deps_type=Deps)

    @agent.tool_plain
    def ping() -> str:
        return "pong"

    _install(monkeypatch, agent)
    with override_settings(CHAT_TOOL_CALLS_LIMIT=1, CHAT_REQUEST_LIMIT=0, CHAT_TOTAL_TOKENS_LIMIT=0):
        stream = await drain(await AsyncClient().post(
            CHAT_URL, data=body(conv.uuid), content_type="application/json"))
    assert "event: error" in stream and "event: done" not in stream
    (row,) = await usage_rows()
    assert row["failed_turns"] == 1 and row["turns"] == 0


@pytest.mark.asyncio
async def test_metrics_failure_never_breaks_the_reply(monkeypatch, caplog):
    conv = await sync_to_async(Conversation.objects.create)()
    _install(monkeypatch, Agent(FunctionModel(stream_function=_plain), deps_type=Deps))

    def boom(**kwargs):
        raise RuntimeError("secret detail")

    monkeypatch.setattr(metrics, "record_turn", boom)
    stream = await drain(await AsyncClient().post(
        CHAT_URL, data=body(conv.uuid), content_type="application/json"))
    assert "event: done" in stream and "event: error" not in stream
    lines = [r.getMessage() for r in caplog.records if "usage metrics failed" in r.getMessage()]
    assert lines == ["usage metrics failed error=RuntimeError"]
    assert not any("secret detail" in r.getMessage() for r in caplog.records)
    assert not any(r.exc_info for r in caplog.records if "usage metrics" in r.getMessage())


def test_bump_create_race_retries_as_update(monkeypatch):
    """If another writer creates the row between our update and create, retry."""
    from django.db.models.query import QuerySet

    day = date(2026, 1, 1)
    UsageDaily.objects.create(date=day, locale="en", turns=5)
    real_update = QuerySet.update
    calls = {"n": 0}

    def first_update_misses(self, **kwargs):
        calls["n"] += 1
        return 0 if calls["n"] == 1 else real_update(self, **kwargs)

    monkeypatch.setattr(QuerySet, "update", first_update_misses)
    metrics.bump(UsageDaily, {"date": day, "locale": "en"}, {"turns": 1})
    assert UsageDaily.objects.get(date=day, locale="en").turns == 6


def test_aggregate_models_have_no_identifying_columns():
    for model in (UsageDaily, FeedbackDaily):
        names = {f.name for f in model._meta.get_fields()}
        assert not names & {"conversation", "message", "user", "updated_at"}


def test_usage_stats_command_prints_table_and_helpful_rate():
    today = timezone.now().date()
    UsageDaily.objects.create(date=today, locale="en", turns=4, new_conversations=2)
    UsageDaily.objects.create(date=today - timedelta(days=90), locale="en", turns=99)
    FeedbackDaily.objects.create(date=today, helpful=3, not_helpful=1)
    out = StringIO()
    call_command("usage_stats", "--days", "30", stdout=out)
    text = out.getvalue()
    assert "99" not in text
    assert "helpful rate: 75%" in text
    assert str(today) in text
