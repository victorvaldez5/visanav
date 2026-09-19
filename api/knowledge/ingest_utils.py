"""Authoritative chunking + frontmatter parsing for the curated corpus.

Moved out of data/scripts/ingest.py so the app owns the real ingestion logic
(the standalone script keeps a copy only for its dependency-light dry-run
preview). The `ingest` management command turns these records into embedded
KnowledgeChunk rows.
"""
from __future__ import annotations

import datetime as dt
import re
import uuid
from pathlib import Path

import yaml
from django.conf import settings

MAX_WORDS = 200
# Frontmatter fields carried onto each chunk. Mirrors KnowledgeChunk's columns
# (country is set from the CLI arg, not the frontmatter).
META_FIELDS = (
    "doc_id", "authority", "topic", "title", "lang",
    "source_url", "source_type", "last_verified", "forms",
)


def split_frontmatter(text: str) -> tuple[dict, str]:
    parts = text.split("---", 2)
    if len(parts) < 3 or not text.startswith("---"):
        raise ValueError("missing frontmatter")
    return (yaml.safe_load(parts[1]) or {}), parts[2].strip()


def clean_text(text: str) -> str:
    """Normalize text: de-hyphenate, collapse whitespace."""
    text = re.sub(r"(\w+)-\s+(\w+)", r"\1\2", text)
    text = re.sub(r"\s+", " ", text).strip()
    return "".join(c for c in text if c.isprintable())


def split_sentences(text: str) -> list[str]:
    # Lightweight sentence split (no nltk dependency for contributors).
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


def chunk(text: str, max_words: int = MAX_WORDS) -> list[str]:
    chunks, current, count = [], [], 0
    for sent in split_sentences(text):
        words = sent.split()
        if count + len(words) > max_words and current:
            chunks.append(" ".join(current))
            current, count = [], 0
        current.append(sent)
        count += len(words)
    if current:
        chunks.append(" ".join(current))
    return chunks


def _coerce_date(value):
    """Frontmatter dates parse to datetime.date via yaml; accept ISO strings too."""
    if isinstance(value, dt.date):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return dt.date.fromisoformat(value.strip())
        except ValueError:
            return None
    return None


def records_for_country(code: str) -> list[dict]:
    """Chunk every knowledge doc for ``code`` into per-chunk field dicts.

    Each dict has the KnowledgeChunk fields except ``embedding`` (added by the
    command after embedding ``text``).
    """
    cdir = Path(settings.KNOWLEDGE_DATA_DIR) / code / "knowledge"
    records: list[dict] = []
    for md in sorted(cdir.rglob("*.md")):
        fm, body = split_frontmatter(md.read_text(encoding="utf-8"))
        meta = {k: fm[k] for k in META_FIELDS if k in fm}
        if "last_verified" in meta:
            meta["last_verified"] = _coerce_date(meta["last_verified"])
        for text in chunk(clean_text(body)):
            records.append({
                "chunk_id": f"{fm['doc_id']}-{uuid.uuid5(uuid.NAMESPACE_URL, text).hex[:8]}",
                "country": code,
                "text": text,
                **meta,
            })
    return records
