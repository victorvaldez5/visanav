import asyncio
import logging
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Optional, Dict, Any, List

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from pgvector.django import CosineDistance
from pydantic import BaseModel
from pydantic_ai import Agent, RunContext

logger = logging.getLogger(__name__)

# Per-provider default chat models: the cheapest capable option for each
# provider. Override with the CHAT_MODEL env var.
DEFAULT_MODELS = {
    "anthropic": "claude-haiku-4-5",
    "openai": "gpt-5-nano",
}

INSTRUCTIONS = """
    You are Javi, a free assistant for U.S. immigration and visa INFORMATION. You
    help immigrants and undocumented people find official government information,
    forms, and government-approved representatives. You are NOT a lawyer and you do
    NOT give legal advice.

    Language:
    - Always reply in the same language the user writes in (e.g. English or
      Spanish). Match their language for the entire response.

    Tools:
    - For any specific immigration question, call semantic_search first and base
      your answer on what it returns. The UI shows the retrieved sources to the
      user, so ground your answer in them.
    - Use resource_lookup to surface free/low-cost nonprofit and pro-bono help and
      DOJ-recognized providers, especially when the user names a state or asks who
      can help them.

    INFORMATION vs. ADVICE — your most important rule:
    - Legal INFORMATION (allowed): what a form is and does, what the law says in
      general, general eligibility criteria, how a process works, general
      deadlines, and where to find official resources.
    - Legal ADVICE (never): do NOT tell a user which form THEY should file, whether
      THEY qualify, what THEY specifically should do or say, do NOT predict the
      outcome of their case, and NEVER tell them they don't need a lawyer.
    - The test: if a reply applies the law to this specific person's facts, or
      recommends an action for them, it is advice — don't give it.

    When a user shares personal details or asks "what should I do", "do I qualify",
    or "what are my chances":
      (a) Give the relevant GENERAL rule or how the process works, with its
          official source (via semantic_search).
      (b) Say clearly that whether it applies to THEM depends on specifics only an
          accredited representative or immigration attorney can assess.
      (c) Point them to a representative (use resource_lookup / the DOJ roster).
      Do not steer them toward a specific choice as if it were right for them, and
      do not ask them for sensitive identifiers (A-number, SSN, exact dates, case
      numbers) — you don't need them to explain the general rule.

    Citations & sourcing (strict):
    - Ground every factual claim in semantic_search results.
    - If semantic_search returns has_confident_source = false (or no matches), do
      NOT answer from general knowledge. Say plainly you couldn't find this in an
      official source, then point the user to the official government site
      (uscis.gov / travel.state.gov) and to an accredited representative. Follow
      the tool result's `note`.
    - Never invent a source, URL, or form number, and never cite a document
      semantic_search did not return.

    Fraud — never help, and warn when relevant:
    - Never help with anything fraudulent: using someone else's documents or
      identity (e.g. another person's SSN or green card), lying or entering false
      information on a form, sham marriages, or fake documents. If asked, decline
      briefly and WITHOUT judgment, then redirect to lawful options and to a
      representative. Don't lecture or moralize.
    - Warn about "notario" fraud when relevant: in the U.S. a "notary public" /
      "notario" is NOT a lawyer and cannot give immigration legal advice. Only a
      licensed attorney or a DOJ-accredited representative at a DOJ-recognized
      organization can give immigration legal help or represent someone. No one can
      guarantee approval or a faster case for a fee, and official government forms
      are free to download. Point users to uscis.gov/avoid-scams.

    Tone & format:
    - Empathetic, patient, respectful, non-judgmental. Plain language; define
      technical terms. Use short paragraphs, headings, bullets, or numbered steps.
    - You may ask a clarifying question about GENERAL facts (e.g. which visa
      category), but never solicit sensitive personal identifiers.

    Scope:
    - U.S. immigration information only. No tax, medical, or other legal advice; no
      guarantees of approval. Acknowledge and redirect out-of-scope questions.
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
def get_model():
    """Return the configured chat model, built on first use."""
    return build_model(
        settings.LLM_PROVIDER,
        settings.CHAT_MODEL
        or DEFAULT_MODELS.get(settings.LLM_PROVIDER, DEFAULT_MODELS["anthropic"]),
    )


@dataclass
class Deps:
    # Country whose curated corpus to search (KnowledgeChunk.country). ingest
    # writes curated knowledge per country (e.g. "us"), so this scopes retrieval
    # to a populated corpus.
    country: str
    # Confident sources retrieved during this turn, collected so the streaming
    # view can surface them to the UI as clickable citations. Mutated by
    # semantic_search; one Deps instance per chat turn (never shared).
    sources: list = field(default_factory=list)


class SearchMatch(BaseModel):
    id: str
    score: Optional[float] = None
    topic: Optional[str] = None
    title: Optional[str] = None
    source_url: Optional[str] = None
    # ISO date (YYYY-MM-DD) the source was last checked, shown next to the link.
    last_verified: Optional[str] = None
    text: Optional[str] = None


class SemanticSearchResult(BaseModel):
    country: str
    query: str
    matches: List[SearchMatch]
    # False when no retrieved document met the confidence threshold. When False,
    # matches carry no text and Javi must NOT answer from general knowledge —
    # see the tool result's `note` and the citation rules in INSTRUCTIONS.
    has_confident_source: bool = True
    note: Optional[str] = None


async def semantic_search(ctx: RunContext[Deps], search_query: str):
    """
    Perform a semantic similarity search over the curated knowledge corpus
    (pgvector) to fetch the top-k documents relevant to the user's query.

    Args:
        search_query: A standalone search query for the user's current
            question. Include details from earlier in the conversation that
            the question depends on, such as visa category or country.
    """
    from core.embeddings import embed_query
    from knowledge.models import KnowledgeChunk

    top_k = 3
    country = ctx.deps.country
    min_score = settings.RAG_MIN_SCORE

    # Voyage's client is synchronous; embed off the event loop (as the Pinecone
    # call used to be), then rank by cosine distance in Postgres.
    vector = await asyncio.to_thread(embed_query, search_query)
    qs = (
        KnowledgeChunk.objects.filter(country=country)
        .annotate(distance=CosineDistance("embedding", vector))
        .order_by("distance")[:top_k]
        .values(
            "chunk_id", "topic", "title", "source_url", "last_verified",
            "text", "distance",
        )
    )
    matches = [
        SearchMatch(
            id=row["chunk_id"],
            # Cosine similarity in [0,1] is friendlier for the model than raw
            # distance; higher = more relevant.
            score=1.0 - row["distance"],
            topic=row["topic"],
            title=row["title"],
            source_url=row["source_url"],
            last_verified=(
                row["last_verified"].isoformat() if row["last_verified"] else None
            ),
            text=row["text"],
        )
        async for row in qs
    ]

    # Confidence gate: only matches at/above the threshold count as a real
    # official source. Below it, we withhold the chunk text from the model and
    # signal the fallback, so Javi can't dress up a weak/irrelevant hit (or its
    # own general knowledge) as if it were sourced.
    confident = [m for m in matches if (m.score or 0.0) >= min_score]

    # Content-free retrieval diagnostic: which documents were retrieved, how they
    # scored, and whether any cleared the threshold. We log the corpus chunk ids
    # + scores only — never the search query (model-generated, may paraphrase the
    # user) or the chunk text. Tune RAG_MIN_SCORE against these on real traffic.
    logger.info(
        "semantic_search country=%s min_score=%.2f confident=%d hits=%s",
        country,
        min_score,
        len(confident),
        [
            (m.id, round(m.score, 3) if m.score is not None else None)
            for m in matches
        ],
    )

    if not confident:
        return SemanticSearchResult(
            country=country,
            query=search_query,
            matches=[],
            has_confident_source=False,
            note=(
                "No official source in the knowledge base met the confidence "
                "threshold for this query. Do NOT answer from general knowledge. "
                "Tell the user you couldn't find this in an official source, and "
                "point them to the relevant official government site (e.g. "
                "uscis.gov or travel.state.gov) and to an accredited "
                "representative (use resource_lookup)."
            ),
        ).model_dump()

    # Collect confident sources (deduped by chunk id, keep the strongest) so the
    # streaming view can surface them to the UI. Store citation metadata only —
    # no chunk text.
    existing = {s["id"] for s in ctx.deps.sources}
    for m in confident:
        if m.id in existing:
            continue
        existing.add(m.id)
        ctx.deps.sources.append(
            {
                "id": m.id,
                "title": m.title,
                "source_url": m.source_url,
                "last_verified": m.last_verified,
                "score": round(m.score, 3) if m.score is not None else None,
                "topic": m.topic,
            }
        )

    return SemanticSearchResult(
        country=country, query=search_query, matches=confident
    ).model_dump()


class ResourceMatch(BaseModel):
    name: str
    org_type: str
    pro_bono: bool
    fee_model: str
    description: str
    websites: List[str]
    emails: List[str]
    phones: List[str]
    city: Optional[str] = None
    region: Optional[str] = None


async def resource_lookup(
    ctx: RunContext[Deps],
    region: Optional[str] = None,
    pro_bono_only: bool = False,
    service: Optional[str] = None,
):
    """
    Find free/low-cost nonprofit and pro-bono immigration help and
    DOJ-recognized providers from the resource directory.

    Args:
        region: US state to filter by, spelled out in full (e.g. "Arizona").
        pro_bono_only: If true, only return organizations offering free pro-bono
            help.
        service: A single area of help to filter by, e.g. "asylum",
            "removal-defense", "family-petitions".
    """

    def _query() -> List[Dict[str, Any]]:
        # Imported here so this module stays importable without a DB configured.
        from django.db import connection
        from network.models import Organization

        try:
            qs = Organization.objects.filter(is_active=True)
            if pro_bono_only:
                qs = qs.filter(pro_bono=True)
            if region:
                qs = qs.filter(address__subdivision__name__iexact=region)
            if service:
                qs = qs.filter(services__contains=[service])
            qs = qs.select_related("address", "address__subdivision")[:5]

            matches = []
            for org in qs:
                addr = org.address
                subdivision = addr.subdivision if addr else None
                matches.append(
                    ResourceMatch(
                        name=org.name,
                        org_type=org.organization_type,
                        pro_bono=org.pro_bono,
                        fee_model=org.fee_model,
                        description=org.description,
                        websites=list(org.websites or []),
                        emails=list(org.emails or []),
                        phones=list(org.phones or []),
                        city=addr.city if addr else None,
                        region=subdivision.name if subdivision else None,
                    ).model_dump()
                )
            return matches
        finally:
            # Close the connection opened in this worker thread so the pooled
            # thread doesn't hold a DB connection open between calls.
            connection.close()

    # The Django ORM is synchronous; run it off the event loop. US-only for now.
    return await asyncio.to_thread(_query)


@lru_cache(maxsize=1)
def get_agent() -> Agent:
    """Build the chat agent on first use and register its tools.

    Lazy so importing this module never constructs a model client (see
    ``get_pinecone``). The tool is registered here rather than via a module-level
    ``@agent.tool`` decorator so the agent (and its model) can be built lazily.
    """
    agent = Agent(model=get_model(), deps_type=Deps, instructions=INSTRUCTIONS)
    agent.tool(semantic_search)
    agent.tool(resource_lookup)
    return agent
