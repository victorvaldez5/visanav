"""Tests for the pgvector retrieval path.

The Voyage client is always mocked, so these need no API key or network. The DB
tests exercise real pgvector cosine ranking, so they require the `vector`
extension (seeded via api/conftest.py + the pgvector Postgres image in CI).
"""
import asyncio

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
def test_semantic_search_ranks_by_cosine_and_scopes_country(fake_voyage):
    # Query embeds to [1, 0, 0, ...]; nearest by cosine is the aligned vector.
    dims = 1024
    q = [1.0] + [0.0] * (dims - 1)
    monkey_vec = q

    def fake_embed(texts, model, input_type):
        return _FakeResp([monkey_vec for _ in texts])

    fake_voyage.embed = fake_embed

    near = [1.0] + [0.0] * (dims - 1)
    mid = [0.5, 0.5] + [0.0] * (dims - 2)
    far = [0.0, 1.0] + [0.0] * (dims - 2)
    _chunk("us-near", "us", near, topic="near", title="Near", source_url="https://uscis.gov/a")
    _chunk("us-mid", "us", mid, topic="mid")
    _chunk("us-far", "us", far, topic="far")
    _chunk("ca-near", "ca", near, topic="other-country")  # must be excluded by scope

    result = asyncio.run(semantic_search_ctx(Deps(country="us"), "any query"))

    ids = [m["id"] for m in result["matches"]]
    assert ids == ["us-near", "us-mid", "us-far"]
    assert "ca-near" not in ids
    top = result["matches"][0]
    assert top["title"] == "Near"
    assert top["source_url"] == "https://uscis.gov/a"
    assert top["score"] == pytest.approx(1.0, abs=1e-4)  # cosine sim of identical vectors


async def semantic_search_ctx(deps, query):
    """Call the agent tool with a minimal RunContext stand-in."""
    class _Ctx:
        pass

    ctx = _Ctx()
    ctx.deps = deps
    return await semantic_search(ctx, query)
