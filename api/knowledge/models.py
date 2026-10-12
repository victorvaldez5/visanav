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
    # scrape source such as "uscis", "ecfr" or "federal-register" (via
    # `ingest_scrape`, see knowledge.scrape_utils.SOURCES). Each corpus is
    # replaced on its own, so re-ingesting one never wipes another.
    corpus = models.CharField(max_length=32, default="curated", db_index=True)
    text = models.TextField()
    embedding = VectorField(dimensions=settings.EMBEDDING_DIM)

    # Frontmatter metadata (see data/scripts META_FIELDS / knowledge.schema.json).
    authority = models.CharField(max_length=255, blank=True, null=True)
    topic = models.CharField(max_length=255, blank=True, null=True, db_index=True)
    # The kind of legal document a scraped chunk comes from (statute, regulation,
    # agency-guidance, final-rule, proposed-rule, notice, presidential, form), so
    # the model can weigh sources that disagree. Curated chunks leave it null.
    instrument = models.CharField(max_length=32, blank=True, null=True, db_index=True)
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


class IngestRun(models.Model):
    """One attempt to replace one corpus (curated, or a scrape source) for a country.

    The record of what is in the vector store and how fresh it is: scheduled
    ingestion reads the latest successful run to decide whether a corpus is due
    (its ``marker`` no longer matches what is on offer), and `corpus_status`
    shows it. Written by every --upsert run, manual or scheduled.
    """

    SUCCEEDED = "succeeded"
    FAILED = "failed"
    # The new corpus was much smaller than the current one, so it was not
    # written (see settings.INGEST_MIN_KEEP_RATIO). Needs a human: --force.
    SKIPPED = "skipped"
    STATUSES = [(SUCCEEDED, "Succeeded"), (FAILED, "Failed"), (SKIPPED, "Skipped by shrink guard")]

    country = models.CharField(max_length=8)
    corpus = models.CharField(max_length=32)
    # What was ingested: the newest feed's file name for a scrape source, a
    # fingerprint of the chunks for the curated corpus.
    marker = models.CharField(max_length=255)
    status = models.CharField(max_length=16, choices=STATUSES)
    # Rows written, how many of them needed a new embedding (the rest reused
    # the vector of an unchanged chunk), and rows the corpus held beforehand.
    chunks = models.PositiveIntegerField(blank=True, null=True)
    embedded = models.PositiveIntegerField(blank=True, null=True)
    previous_chunks = models.PositiveIntegerField(blank=True, null=True)
    # Vectors are only reused while the model that produced them is unchanged.
    embedding_model = models.CharField(max_length=64, blank=True)
    error = models.TextField(blank=True)
    started_at = models.DateTimeField()
    finished_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        indexes = [models.Index(fields=["country", "corpus", "-started_at"])]
        ordering = ["-started_at"]

    def __str__(self):
        return f"{self.corpus}/{self.country} {self.status} ({self.marker})"
