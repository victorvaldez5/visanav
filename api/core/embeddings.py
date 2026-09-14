"""Embedding provider for the RAG pipeline.

Pinecone used to embed text server-side on both query and ingest; pgvector stores
vectors but never embeds, so this module is the single, shared source of the
embedding call. Retrieval (core/llm.py) and ingestion (knowledge `ingest` command)
both go through here, so the model/dimension can never drift between the two — a
mismatch would make retrieval silently return nothing.

The client is built lazily (mirroring core.llm.get_pinecone's old pattern) so
importing this module needs no API key: management commands, migrations and tests
import it fine, and a bad/missing key surfaces on the first embed call rather than
at import time.
"""
from functools import lru_cache
from typing import List

from django.conf import settings

# Voyage caps a single embed call at 128 inputs.
_MAX_BATCH = 128


@lru_cache(maxsize=1)
def get_voyage_client():
    """Return a process-wide Voyage client, built on first use."""
    import voyageai

    return voyageai.Client(api_key=settings.VOYAGE_API_KEY)


def _embed(texts: List[str], input_type: str) -> List[List[float]]:
    """Embed ``texts`` with the configured model.

    ``input_type`` is "query" or "document": Voyage embeds the two asymmetrically,
    which is what makes short questions match long passages well. Ingest and query
    MUST pass the matching type.
    """
    if not texts:
        return []
    client = get_voyage_client()
    out: List[List[float]] = []
    for i in range(0, len(texts), _MAX_BATCH):
        batch = texts[i:i + _MAX_BATCH]
        resp = client.embed(batch, model=settings.EMBEDDING_MODEL, input_type=input_type)
        out.extend(resp.embeddings)
    return out


def embed_documents(texts: List[str]) -> List[List[float]]:
    """Embed corpus chunks for storage (batched)."""
    return _embed(texts, "document")


def embed_query(text: str) -> List[float]:
    """Embed a single search query."""
    return _embed([text], "query")[0]
