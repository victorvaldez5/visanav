"""Turn the USCIS scraper's JSONL feeds into KnowledgeChunk records.

The `uscis` spider (scrapers/uscis_scraper) writes one JSONL feed per crawl to
R2 at raw/items/uscis/<timestamp>.jsonl, each line carrying the page ``url`` and
its main-content ``html``. Crawls are incremental (unchanged pages are dropped),
so a single feed is only a delta: ``latest_pages`` merges every feed oldest to
newest to rebuild the current snapshot.

Three page kinds are extracted, each keeping only the substantive text:
  - Policy Manual chapters: the "Guidance" tab (not resources/updates tabs).
  - U.S. Code (INA, 8 U.S.C.): the statute text, without the editorial notes.
  - Form pages: the page body (what the form is for, who files, fees, editions).
PDF items carry no text in the feed and are skipped.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import uuid
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from bs4 import BeautifulSoup

from knowledge.ingest_utils import chunk, clean_text

CORPUS = "uscis"
# Pages this short are nav stubs / empty shells, not worth a chunk.
_MIN_WORDS = 30


def _feed_date(path: Path) -> dt.date | None:
    # Feed files are named by crawl time, e.g. 2026-09-21T12-21-07+00-00.jsonl.
    try:
        return dt.date.fromisoformat(path.name[:10])
    except ValueError:
        return None


def latest_pages(feed_paths: list[Path]) -> tuple[dict[str, str], dt.date | None]:
    """Merge feeds oldest→newest into {url: html}; also return the newest crawl date.

    An incremental crawl omits unchanged pages, so a page's newest copy may live
    in an older feed; later feeds override earlier ones.
    """
    pages: dict[str, str] = {}
    paths = sorted(feed_paths, key=lambda p: p.name)
    for path in paths:
        with path.open(encoding="utf-8") as f:
            for line in f:
                item = json.loads(line)
                if item.get("content_type") == "text/html" and item.get("content"):
                    pages[item["url"]] = item["content"]
    return pages, (_feed_date(paths[-1]) if paths else None)


def _text(node) -> str:
    return clean_text(node.get_text(" ", strip=True)) if node else ""


def _policy_manual(url: str, soup: BeautifulSoup) -> dict | None:
    # Slug like volume-12-part-l-chapter-2; the h1 only names the chapter.
    slug = urlparse(url).path.rsplit("/", 1)[-1]
    m = re.match(r"volume-(\d+)-part-([a-z]+)-chapter-(\d+)", slug)
    heading = _text(soup.select_one("h1"))
    if m:
        vol, part, _ = m.groups()
        title = f"USCIS Policy Manual, Vol. {vol}, Part {part.upper()}, {heading}"
    else:
        title = f"USCIS Policy Manual, {heading}"
    return {
        "doc_id": f"uscis/policy-manual/{slug}",
        "title": title,
        "topic": "policy-manual",
        "authority": "USCIS",
        "text": _text(soup.select_one("#guidance") or soup.select_one("#book-content")),
    }


def _us_code(url: str, html: str) -> dict | None:
    # uscode.house.gov marks regions with <!-- field-start:X --> comments; keep
    # only the statute itself, not the amendment/notes apparatus (often 5x longer).
    m = re.search(r"<!-- field-start:statute -->(.*?)<!-- field-end:statute -->", html, re.S)
    if not m:
        return None
    soup = BeautifulSoup(html, "html.parser")
    # "8 USC 1537: Custody and ..." (the cite sits in its own comment-delimited span)
    title = _text(soup.select_one(".contextHeadline")).replace(" :", ":")
    granule = parse_qs(urlparse(url).query).get("req", [""])[0]
    section = re.search(r"title(\d+)-section(\w+)", granule)
    if section:
        doc_id = f"usc/{section.group(1)}-{section.group(2)}"
    else:
        doc_id = f"usc/{uuid.uuid5(uuid.NAMESPACE_URL, url).hex[:12]}"
    return {
        "doc_id": doc_id,
        "title": title or doc_id,
        "topic": "statute",
        "authority": "U.S. Code (INA)",
        "text": _text(BeautifulSoup(m.group(1), "html.parser")),
    }


def _form_page(url: str, soup: BeautifulSoup) -> dict | None:
    slug = urlparse(url).path.strip("/")
    title = _text(soup.select_one("h1"))
    article = soup.select_one("article") or soup
    for junk in article.select("h1, .files-listing, nav, script, style"):
        junk.decompose()
    doc = {
        "doc_id": f"uscis/{slug}",
        "title": title,
        "topic": "forms",
        "authority": "USCIS",
        "text": _text(article),
    }
    # "I-485, Application to ..." → forms=["I-485"]
    form = re.match(r"([A-Z]{1,4}-\d+[A-Z]*)", title)
    if form:
        doc["forms"] = [form.group(1)]
    return doc


def extract(url: str, html: str) -> dict | None:
    """Return {doc_id, title, topic, authority, text[, forms]} or None to skip."""
    if "uscode.house.gov" in url:
        return _us_code(url, html)
    soup = BeautifulSoup(html, "html.parser")
    if "/policy-manual/" in url:
        return _policy_manual(url, soup)
    return _form_page(url, soup)


def records_from_feeds(feed_paths: list[Path], country: str = "us") -> list[dict]:
    """Chunk every scraped page into KnowledgeChunk field dicts (minus embedding).

    Each chunk is prefixed with its page title so it stays self-describing once
    retrieved on its own (a bare "(b) Terms ..." paragraph means nothing without
    "8 USC 1537"). Duplicate chunks within a doc are collapsed by chunk_id.
    """
    pages, crawled = latest_pages(feed_paths)
    records: dict[str, dict] = {}
    for url, html in sorted(pages.items()):
        doc = extract(url, html)
        if not doc or len(doc["text"].split()) < _MIN_WORDS:
            continue
        for body in chunk(doc["text"]):
            text = f"{doc['title']}: {body}" if doc["title"] else body
            chunk_id = f"{doc['doc_id']}-{uuid.uuid5(uuid.NAMESPACE_URL, text).hex[:8]}"
            records[chunk_id] = {
                "chunk_id": chunk_id,
                "doc_id": doc["doc_id"],
                "country": country,
                "corpus": CORPUS,
                "text": text,
                "title": doc["title"][:512] or None,
                "topic": doc["topic"],
                "authority": doc["authority"],
                "lang": "en",
                "source_url": url,
                "source_type": "official",
                "last_verified": crawled,
                "forms": doc.get("forms"),
            }
    return list(records.values())
