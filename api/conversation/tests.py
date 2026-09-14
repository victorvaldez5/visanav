import asyncio
from types import SimpleNamespace
from unittest import mock

import pytest
from pydantic_ai import models

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
