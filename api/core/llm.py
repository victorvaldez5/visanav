import asyncio
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional, Dict, Any, List

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from pinecone import Pinecone
from pydantic import BaseModel
from pydantic_ai import Agent, RunContext

# Per-provider default chat models: the cheapest capable option for each
# provider. Override with the CHAT_MODEL env var.
DEFAULT_MODELS = {
    "anthropic": "claude-haiku-4-5",
    "openai": "gpt-5-nano",
}

INSTRUCTIONS = """
    You are Javi, a chat assistant for US immigration and visas support.
    Follow rules:
    Tools:
    - Use the semantic search tool when asked a specific question about immigration.

    Role & Purpose:
    - Give clear, current info on processes, categories, forms, fees.
    - Explain eligibility, docs, next steps.
    - Note you're not a lawyer; refer users to official sources or attorneys.
    Tone & Style:
    - Empathetic, patient, respectful.
    - Plain language; define technical terms.
    - Use headings, bullets, or numbered steps.
    Accuracy:
    - Base answers on USCIS, State Dept, CBP sources.
    - Cite form numbers or official pages when possible.
    - If unsure, advise verification on uscis.gov or travel.state.gov.
    Scope:
    - No tax, medical, or non-immigration legal advice.
    - Acknowledge and redirect questions outside this scope.
    - No guarantees of approval; outcomes vary by case.
    Clarification:
    - Ask follow-up for missing details (e.g., nationality, status).
    - Summarize with "Key Takeaways" or "Next Steps."
    Privacy & Ethics:
    - Avoid bias; stay fact-based.
"""


def build_model(provider: str, model_name: str):
    """Construct a pydantic-ai model for the given provider.

    Only the selected provider's client is constructed, so the unused
    provider never breaks startup.
    """
    provider = provider.lower()
    if provider == "anthropic":
        from pydantic_ai.models.anthropic import AnthropicModel
        from pydantic_ai.providers.anthropic import AnthropicProvider

        return AnthropicModel(
            model_name,
            provider=AnthropicProvider(api_key=settings.ANTHROPIC_API_KEY),
        )
    if provider == "openai":
        from pydantic_ai.models.openai import OpenAIChatModel
        from pydantic_ai.providers.openai import OpenAIProvider

        return OpenAIChatModel(
            model_name, provider=OpenAIProvider(api_key=settings.OPEN_AI_API_KEY)
        )
    raise ImproperlyConfigured(
        f"Unsupported LLM_PROVIDER: {provider!r} (expected anthropic or openai)"
    )


@lru_cache(maxsize=1)
def get_pinecone() -> Pinecone:
    """Return a process-wide Pinecone client, built on first use.

    Constructing this lazily (rather than at import time) keeps the API
    importable — and management commands, migrations and tests runnable —
    without the Pinecone/provider keys present, and means a bad key surfaces on
    the first chat request instead of crashing the process at boot.
    """
    return Pinecone(api_key=settings.PINECONE_API_KEY)


@lru_cache(maxsize=1)
def get_model():
    """Return the configured chat model, built on first use."""
    return build_model(
        settings.LLM_PROVIDER,
        settings.CHAT_MODEL
        or DEFAULT_MODELS.get(settings.LLM_PROVIDER, DEFAULT_MODELS["anthropic"]),
    )


@dataclass
class Deps:
    pinecone: Pinecone
    # Pinecone namespace to search. ingest.py upserts curated knowledge per
    # country (e.g. "us"), so this scopes retrieval to a populated corpus.
    namespace: str


class SearchMatch(BaseModel):
    id: str
    score: Optional[float] = None
    category: Optional[str] = None
    text: Optional[str] = None


class SemanticSearchResult(BaseModel):
    namespace: str
    query: str
    matches: List[SearchMatch]


def search_result_to_dict(obj: Any, query: str, namespace: str) -> Dict[str, Any]:
    matches = []
    # The Pinecone SDK returns the hits under a singular ``result`` key;
    # accept the plural too in case the response shape changes.
    data = obj.to_dict() if hasattr(obj, "to_dict") else obj
    results = data.get('result') or data.get('results') or {}
    hits = results.get('hits', [])
    for hit in hits:
        _match = {}
        _match['id'] = hit.get('_id')
        _match['score'] = hit.get('_score')
        fields = hit.get('fields', {})
        _match['category'] = fields.get('category')
        _match['text'] = fields.get('chunk_text')
        matches.append(_match)

    return {
        "namespace": namespace,
        "query": query,
        "matches": matches
    }


async def semantic_search(ctx: RunContext[Deps], search_query: str):
    """
    Perform a semantic similarity search on Pinecone to fetch the top‐k
    documents relevant to the user's query.

    Args:
        search_query: A standalone search query for the user's current
            question. Include details from earlier in the conversation that
            the question depends on, such as visa category or country.
    """
    top_k = 3
    namespace = ctx.deps.namespace
    index = ctx.deps.pinecone.Index(host=settings.PINECONE_INDEX_HOST)

    # Pinecone's client is synchronous; run it off the event loop.
    results = await asyncio.to_thread(
        index.search,
        namespace=namespace,
        query={"inputs": {"text": search_query}, "top_k": top_k},
        fields=["category", "chunk_text"],
    )
    raw = search_result_to_dict(results, search_query, namespace)
    return SemanticSearchResult(**raw).model_dump()


@lru_cache(maxsize=1)
def get_agent() -> Agent:
    """Build the chat agent on first use and register its tools.

    Lazy so importing this module never constructs a model client (see
    ``get_pinecone``). The tool is registered here rather than via a module-level
    ``@agent.tool`` decorator so the agent (and its model) can be built lazily.
    """
    agent = Agent(model=get_model(), deps_type=Deps, instructions=INSTRUCTIONS)
    agent.tool(semantic_search)
    return agent
