"""Tests for the pgvector retrieval path.

The Voyage client is always mocked, so these need no API key or network. The DB
tests exercise real pgvector cosine ranking, so they require the `vector`
extension (seeded via api/conftest.py + the pgvector Postgres image in CI).
"""
import asyncio
from datetime import date

import pytest

from core import embeddings
from core.llm import Deps, semantic_search
from knowledge.models import KnowledgeChunk


class _FakeResp:
    def __init__(self, embeddings):
        self.embeddings = embeddings


class _FakeVoyage:
    """Records calls and returns a fixed-per-text vector."""

    def __init__(self):
        self.calls = []

    def embed(self, texts, model, input_type):
        self.calls.append({"texts": list(texts), "model": model, "input_type": input_type})
        # 1024-dim vectors; content is irrelevant for the embed-shape tests.
        return _FakeResp([[float(len(t))] * 1024 for t in texts])


@pytest.fixture
def fake_voyage(monkeypatch):
    fake = _FakeVoyage()
    monkeypatch.setattr(embeddings, "get_voyage_client", lambda: fake)
    return fake


def test_embed_query_uses_query_input_type(fake_voyage):
    vec = embeddings.embed_query("how do I renew my green card?")
    assert len(vec) == 1024
    assert fake_voyage.calls[0]["input_type"] == "query"
    assert len(fake_voyage.calls) == 1


def test_embed_documents_batches_over_128(fake_voyage):
    texts = [f"chunk {i}" for i in range(200)]
    vecs = embeddings.embed_documents(texts)
    assert len(vecs) == 200
    # 200 inputs -> two batches (128 + 72), all as documents.
    assert [len(c["texts"]) for c in fake_voyage.calls] == [128, 72]
    assert all(c["input_type"] == "document" for c in fake_voyage.calls)


def _chunk(chunk_id, country, vector, **meta):
    return KnowledgeChunk.objects.create(
        chunk_id=chunk_id, doc_id="d1", country=country, text=meta.pop("text", chunk_id),
        embedding=vector, **meta,
    )


@pytest.mark.django_db(transaction=True)
def test_semantic_search_ranks_scopes_and_gates_by_confidence(fake_voyage, settings):
    # Query embeds to [1, 0, 0, ...]; nearest by cosine is the aligned vector.
    settings.RAG_MIN_SCORE = 0.5
    dims = 1024
    q = [1.0] + [0.0] * (dims - 1)
    monkey_vec = q

    def fake_embed(texts, model, input_type):
        return _FakeResp([monkey_vec for _ in texts])

    fake_voyage.embed = fake_embed

    near = [1.0] + [0.0] * (dims - 1)          # cosine sim 1.0  -> confident
    mid = [0.5, 0.5] + [0.0] * (dims - 2)      # cosine sim ~0.707 -> confident
    far = [0.0, 1.0] + [0.0] * (dims - 2)      # cosine sim 0.0  -> gated out
    _chunk("us-near", "us", near, topic="near", title="Near",
           source_url="https://uscis.gov/a", last_verified=date(2026, 2, 10))
    _chunk("us-mid", "us", mid, topic="mid")
    _chunk("us-far", "us", far, topic="far")
    _chunk("ca-near", "ca", near, topic="other-country")  # must be excluded by scope

    deps = Deps(country="us")
    result = asyncio.run(semantic_search_ctx(deps, "any query"))

    # Ranked by cosine, scoped to the country, and the sub-threshold hit (us-far,
    # sim 0.0) is gated out — its text never reaches the model.
    ids = [m["id"] for m in result["matches"]]
    assert ids == ["us-near", "us-mid"]
    assert "us-far" not in ids
    assert "ca-near" not in ids
    assert result["has_confident_source"] is True

    top = result["matches"][0]
    assert top["title"] == "Near"
    assert top["source_url"] == "https://uscis.gov/a"
    assert top["last_verified"] == "2026-02-10"  # ISO date surfaced for the UI
    assert top["score"] == pytest.approx(1.0, abs=1e-4)  # identical vectors

    # Confident sources are collected on Deps for the streaming view to emit,
    # with citation metadata only (no chunk text).
    assert [s["id"] for s in deps.sources] == ["us-near", "us-mid"]
    assert deps.sources[0]["last_verified"] == "2026-02-10"
    assert "text" not in deps.sources[0]


@pytest.mark.django_db(transaction=True)
def test_semantic_search_confidence_gate_triggers_fallback(fake_voyage, settings):
    # Only an off-axis (irrelevant) chunk exists, so nothing clears the floor.
    settings.RAG_MIN_SCORE = 0.5
    dims = 1024
    q = [1.0] + [0.0] * (dims - 1)
    fake_voyage.embed = lambda texts, model, input_type: _FakeResp([q for _ in texts])

    far = [0.0, 1.0] + [0.0] * (dims - 2)  # cosine sim 0.0
    _chunk("us-far", "us", far, topic="far", title="Irrelevant",
           source_url="https://uscis.gov/z")

    deps = Deps(country="us")
    result = asyncio.run(semantic_search_ctx(deps, "any query"))

    # No confident source: no matches/text returned, the fallback is signalled,
    # and nothing is collected for citation.
    assert result["matches"] == []
    assert result["has_confident_source"] is False
    assert result["note"]  # non-empty fallback instruction for the model
    assert deps.sources == []


async def semantic_search_ctx(deps, query):
    """Call the agent tool with a minimal RunContext stand-in."""
    class _Ctx:
        pass

    ctx = _Ctx()
    ctx.deps = deps
    return await semantic_search(ctx, query)
