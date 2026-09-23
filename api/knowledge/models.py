from django.conf import settings
from django.db import models
from pgvector.django import HnswIndex, VectorField


class KnowledgeChunk(models.Model):
    """One embedded chunk of curated immigration knowledge.

    Replaces the Pinecone corpus: rows are scoped by ``country`` (the old
    per-country namespace) and carry the frontmatter metadata the ingest command
    actually writes, so retrieval can surface real sources (title/source_url)
    instead of the always-null ``category`` the Pinecone path used to read.

    The embedding column is a fixed 1024-dim vector; ``settings.EMBEDDING_MODEL``
    must be a 1024-dim Voyage model (voyage-3 / voyage-law-2). Both ingest and
    query embed via core.embeddings, so they cannot drift.
    """

    # Stable id from the source doc + content hash ({doc_id}-{hash8}); a changed
    # chunk gets a new id, so a full re-ingest of a country reaps stale rows.
    chunk_id = models.CharField(max_length=128, unique=True)
    doc_id = models.CharField(max_length=255)
    country = models.CharField(max_length=8, db_index=True)
    # Which producer wrote the row: "curated" (data/ Markdown via `ingest`) or a
    # scrape source such as "uscis" (via `ingest_scrape`). Each command replaces
    # only its own corpus, so re-ingesting one never wipes the other.
    corpus = models.CharField(max_length=32, default="curated", db_index=True)
    text = models.TextField()
    embedding = VectorField(dimensions=settings.EMBEDDING_DIM)

    # Frontmatter metadata (see data/scripts META_FIELDS / knowledge.schema.json).
    authority = models.CharField(max_length=255, blank=True, null=True)
    topic = models.CharField(max_length=255, blank=True, null=True, db_index=True)
    title = models.CharField(max_length=512, blank=True, null=True)
    lang = models.CharField(max_length=16, blank=True, null=True)
    source_url = models.URLField(max_length=1024, blank=True, null=True)
    source_type = models.CharField(max_length=64, blank=True, null=True)
    last_verified = models.DateField(blank=True, null=True)
    forms = models.JSONField(blank=True, null=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            # Voyage embeddings are unit-normalized, so cosine distance is the
            # right operator. HNSW gives good recall/latency without a training
            # step; trivial to build at this corpus size (~10-12k rows).
            HnswIndex(
                name="knowledge_embedding_hnsw",
                fields=["embedding"],
                m=16,
                ef_construction=64,
                opclasses=["vector_cosine_ops"],
            ),
        ]

    def __str__(self):
        return f"{self.chunk_id} ({self.country})"
