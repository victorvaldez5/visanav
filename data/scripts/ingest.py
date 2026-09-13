#!/usr/bin/env python3
"""Turn curated knowledge Markdown into vector-store records.

It works on human-contributed Markdown (rather than scraped HTML/PDF):

    frontmatter + body  ->  cleaned text  ->  ~200-word chunks  ->  upsert

Each chunk carries the document's frontmatter as metadata (country, authority,
topic, source_url, last_verified, ...), and records are upserted into a
**per-country namespace** so retrieval can scope to the user's country.

By default this runs a DRY RUN (no network, no Pinecone needed) and just prints
what would be upserted — handy for contributors and CI. Pass --upsert with the
env vars set to actually write.

Usage:
    python data/scripts/ingest.py us                 # dry run for US
    python data/scripts/ingest.py us --upsert        # write to Pinecone

Env for --upsert:  PINECONE_API_KEY, PINECONE_INDEX
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import re
import sys
import uuid
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.exit("Missing pyyaml. Run: pip install -r data/scripts/requirements.txt")

DATA_DIR = Path(__file__).resolve().parent.parent
COUNTRIES_DIR = DATA_DIR / "countries"

# Optionally load config/.env (only --upsert needs PINECONE_* below). Kept
# optional so validation stays dependency-light; falls back to the shell env.
try:
    from dotenv import load_dotenv

    load_dotenv(DATA_DIR.parent / "config" / ".env")
except ImportError:
    pass

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
        meta = {k: (v.isoformat() if isinstance(v, dt.date) else v) for k, v in meta.items()}
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
    ap.add_argument("--upsert", action="store_true", help="write to Pinecone (default: dry run)")
    args = ap.parse_args()

    code = args.country.lower()
    if not (COUNTRIES_DIR / code).exists():
        sys.exit(f"No such country: {code}")

    records = records_for_country(code)
    namespace = code
    print(f"{code.upper()}: {len(records)} chunk(s) -> namespace '{namespace}'")

    if not args.upsert:
        for r in records[:3]:
            preview = r["chunk_text"][:100].replace("\n", " ")
            print(f"  [{r['topic']}] {r['_id']}: {preview}...")
        if len(records) > 3:
            print(f"  ... and {len(records) - 3} more (dry run; pass --upsert to write)")
        return 0

    api_key, index_name = os.getenv("PINECONE_API_KEY"), os.getenv("PINECONE_INDEX")
    if not api_key or not index_name:
        sys.exit("--upsert requires PINECONE_API_KEY and PINECONE_INDEX env vars")

    from pinecone import Pinecone  # imported lazily so dry runs need no dependency

    index = Pinecone(api_key=api_key).Index(index_name)
    for i in range(0, len(records), 96):
        index.upsert_records(namespace, records[i:i + 96])
    print(f"✓ upserted {len(records)} record(s) into '{index_name}' namespace '{namespace}'")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
