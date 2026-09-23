#!/usr/bin/env python3
"""Preview curated knowledge Markdown as vector-store chunks (dry run only).

It works on human-contributed Markdown (rather than scraped HTML/PDF):

    frontmatter + body  ->  cleaned text  ->  ~200-word chunks

Each chunk carries the document's frontmatter as metadata (country, authority,
topic, source_url, last_verified, ...). This script is a dependency-light preview
for contributors and CI — it needs no keys, no database, and no Django.

**Authoritative ingestion lives in the API** (it embeds via Voyage and writes to
pgvector, which this script deliberately does not depend on):

    cd api && python manage.py ingest us            # dry run
    cd api && python manage.py ingest us --upsert    # embed + write to pgvector

Usage:
    python data/scripts/ingest.py us                 # preview chunks for US
"""
from __future__ import annotations

import argparse
import re
import sys
import uuid
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.exit("Missing pyyaml. Run: uv run --package visanav-data python data/scripts/ingest.py")

DATA_DIR = Path(__file__).resolve().parent.parent
COUNTRIES_DIR = DATA_DIR / "countries"

MAX_WORDS = 200
META_FIELDS = ("doc_id", "country", "authority", "topic", "title", "lang",
               "source_url", "source_type", "last_verified", "forms")


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


def records_for_country(code: str) -> list[dict]:
    cdir = COUNTRIES_DIR / code / "knowledge"
    records: list[dict] = []
    for md in sorted(cdir.rglob("*.md")):
        fm, body = split_frontmatter(md.read_text(encoding="utf-8"))
        meta = {k: fm[k] for k in META_FIELDS if k in fm}
        for text in chunk(clean_text(body)):
            records.append({
                "_id": f"{fm['doc_id']}-{uuid.uuid5(uuid.NAMESPACE_URL, text).hex[:8]}",
                "chunk_text": text,
                **meta,
            })
    return records


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("country", help="ISO alpha-2 country code, e.g. us")
    args = ap.parse_args()

    code = args.country.lower()
    if not (COUNTRIES_DIR / code).exists():
        sys.exit(f"No such country: {code}")

    records = records_for_country(code)
    print(f"{code.upper()}: {len(records)} chunk(s)")
    for r in records[:3]:
        preview = r["chunk_text"][:100].replace("\n", " ")
        print(f"  [{r.get('topic')}] {r['_id']}: {preview}...")
    if len(records) > 3:
        print(f"  ... and {len(records) - 3} more")
    print("\nTo embed + write to pgvector: cd api && python manage.py ingest "
          f"{code} --upsert")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
