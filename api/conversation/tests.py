import asyncio
from types import SimpleNamespace
from unittest import mock

import pytest
from django.test import override_settings
from pydantic_ai import models
from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    TextPart,
    UserPromptPart,
)
from pydantic_core import to_jsonable_python

from conversation import streaming
from conversation.models import Conversation
from core import embeddings, llm
from knowledge.models import KnowledgeChunk

_DIMS = 1024


@pytest.mark.django_db(transaction=True)
def test_searches_on_the_query_the_model_wrote_scoped_to_country():
    """The tool must embed the exact query it was handed (not ask an LLM to
    rewrite it) and rank the country's own corpus."""
    aligned = [1.0] + [0.0] * (_DIMS - 1)
    KnowledgeChunk.objects.create(
        chunk_id="i-130-1", doc_id="i-130", country="us",
        text="Use Form I-130 to petition for a relative.", embedding=aligned,
        topic="green-card", title="I-130", source_url="https://uscis.gov/i-130",
    )
    # A different country's chunk must never leak into a US search.
    KnowledgeChunk.objects.create(
        chunk_id="ca-1", doc_id="x", country="ca", text="irrelevant",
        embedding=[0.0] * _DIMS,
    )

    captured = {}

    def fake_embed_query(text):
        captured["query"] = text
        return aligned

    query = "Form I-130 petition for the spouse of a US citizen"
    ctx = SimpleNamespace(deps=llm.Deps(country="us"))

    # Model requests are blocked: the tool must search on the query as given.
    with mock.patch.object(embeddings, "embed_query", fake_embed_query), \
            mock.patch.object(models, "ALLOW_MODEL_REQUESTS", False):
        result = asyncio.run(llm.semantic_search(ctx, query))

    assert captured["query"] == query  # embedded verbatim, no rewrite
    assert result["country"] == "us"
    assert result["query"] == query
    assert [m["id"] for m in result["matches"]] == ["i-130-1"]  # ca chunk excluded
    assert result["matches"][0]["source_url"] == "https://uscis.gov/i-130"


def test_language_instructions_names_the_preferred_locale():
    """The dynamic instruction names the Deps.locale language for the model."""
    ctx = SimpleNamespace(deps=llm.Deps(country="us", locale="es"))
    assert llm.language_instructions(ctx) == (
        "The user's preferred reply language is Spanish (es)."
    )


def test_deps_locale_defaults_to_language_code():
    """Deps built without a locale (management commands, tests) use LANGUAGE_CODE."""
    assert llm.Deps(country="us").locale == "en"
    with override_settings(LANGUAGE_CODE="es"):
        assert llm.Deps(country="us").locale == "es"


@pytest.mark.django_db(transaction=True)
def test_load_history_ignores_django_only_columns():
    """History must rehydrate from the persisted message fields alone.

    Regression: ``_load_history`` used ``.values()`` (every column), so the row's
    Django ``conversation_id`` FK — an int — was fed to pydantic-ai, whose message
    models now define their own ``conversation_id`` field (a str). That collision
    raised a ValidationError and 500'd every follow-up turn on an existing chat.
    """
    conversation = Conversation.objects.create()
    new_messages = to_jsonable_python(
        [
            ModelRequest(parts=[UserPromptPart(content="How do I file an I-130?")]),
            ModelResponse(
                parts=[TextPart(content="Use Form I-130.")],
                model_name="claude-haiku-4-5",
            ),
        ]
    )
    # Persist via the real production path so the stored shape is faithful.
    asyncio.run(streaming._persist_messages(conversation.id, new_messages))

    history = asyncio.run(streaming._load_history(conversation.id))

    assert [type(m).__name__ for m in history] == ["ModelRequest", "ModelResponse"]
    assert history[1].model_name == "claude-haiku-4-5"
