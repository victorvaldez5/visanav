"""Turn the scrapers' JSONL feeds into KnowledgeChunk records.

Each spider (scrapers/uscis_scraper) writes one JSONL feed per crawl to R2 at
raw/items/<source>/<timestamp>.jsonl, each line carrying the page ``url``, its
main ``content`` and, for newer sources, a ``meta`` mapping. Crawls are
incremental (unchanged pages are dropped), so a single feed is only a delta:
``latest_pages`` merges every feed oldest to newest to rebuild the current
snapshot, honouring ``removed`` lines for pages that have gone.

``SOURCES`` maps each source (the spider name, which is also its feed directory
and its ``KnowledgeChunk.corpus``) to the extractor that keeps only the
substantive text of its pages:
  - uscis: Policy Manual chapters (the "Guidance" tab), U.S. Code sections (the
    statute text, without the editorial notes) and form pages (the page body).
  - ecfr: one CFR section or appendix per page, without the editorial apparatus.
  - federal-register: one published document per page, within a retention window.
PDF items carry no text in the feed and are skipped.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from urllib.parse import parse_qs, urlparse

from bs4 import BeautifulSoup
from django.conf import settings

from knowledge.ingest_utils import chunk, clean_text

# Pages this short are nav stubs / empty shells, not worth a chunk.
_MIN_WORDS = 30
# A final rule's preamble can run to hundreds of pages of comment responses.
# The summary, dates and opening of the supplementary information say what the
# document does; the rule text itself lands in the CFR (the ecfr source).
_FEDERAL_REGISTER_MAX_WORDS = 6000


def _feed_date(path: Path) -> dt.date | None:
    # Feed files are named by crawl time, e.g. 2026-09-21T12-21-07+00-00.jsonl.
    try:
        return dt.date.fromisoformat(path.name[:10])
    except ValueError:
        return None


def latest_pages(
    feed_paths: list[Path],
) -> tuple[dict[str, tuple[str, dict]], dt.date | None]:
    """Merge feeds oldest→newest into {url: (content, meta)}; also return the
    newest crawl date.

    An incremental crawl omits unchanged pages, so a page's newest copy may live
    in an older feed; later feeds override earlier ones. A ``removed`` line
    drops the page (until a later feed brings it back).
    """
    pages: dict[str, tuple[str, dict]] = {}
    paths = sorted(feed_paths, key=lambda p: p.name)
    for path in paths:
        with path.open(encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                item = json.loads(line)
                if item.get("removed"):
                    pages.pop(item["url"], None)
                elif item.get("content"):
                    pages[item["url"]] = (item["content"], item.get("meta") or {})
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
        "instrument": "agency-guidance",
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
        "instrument": "statute",
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
        "instrument": "form",
        "authority": "USCIS",
        "text": _text(article),
    }
    # "I-485, Application to ..." → forms=["I-485"]
    form = re.match(r"([A-Z]{1,4}-\d+[A-Z]*)", title)
    if form:
        doc["forms"] = [form.group(1)]
    return doc


def extract(url: str, html: str, meta: dict | None = None) -> dict | None:
    """USCIS pages: return {doc_id, title, topic, instrument, authority, text[, forms]}
    or None to skip."""
    if "uscode.house.gov" in url:
        return _us_code(url, html)
    soup = BeautifulSoup(html, "html.parser")
    if "/policy-manual/" in url:
        return _policy_manual(url, soup)
    return _form_page(url, soup)


# Who issues each CFR chapter we cover: (title, chapter) -> authority.
_CFR_AUTHORITIES = {
    (8, "I"): "Department of Homeland Security",
    (8, "V"): "Executive Office for Immigration Review (DOJ)",
    (20, "V"): "Department of Labor",
    (22, "I"): "Department of State",
}
# Editorial apparatus around a section's text: source citations, notes on
# pending amendments' Federal Register history, authority lines, OMB approvals.
_CFR_APPARATUS = "cita, ednote, secauth, auth, source, appro"


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9.]+", "-", value.lower()).strip("-")


def extract_ecfr(url: str, xml: str, meta: dict | None = None) -> dict | None:
    """One CFR section or appendix (the eCFR bulk XML for that node)."""
    meta = meta or {}
    citation = meta.get("citation")
    if not citation:
        return None
    # html.parser copes with this XML (it only lower-cases the tag names), so
    # the API image needs no XML parser.
    soup = BeautifulSoup(xml, "html.parser")
    for junk in soup.select(f"head, {_CFR_APPARATUS}"):
        junk.decompose()
    heading = (meta.get("heading") or "").strip()
    try:
        title_number = int(meta.get("title"))
    except (TypeError, ValueError):
        title_number = None
    return {
        "doc_id": f"ecfr/{_slug(citation)}",
        "title": f"{citation}: {heading}" if heading else citation,
        "topic": "regulation",
        "instrument": "regulation",
        "authority": _CFR_AUTHORITIES.get(
            (title_number, meta.get("chapter")), "Code of Federal Regulations"
        ),
        "text": _text(soup),
    }


# Federal Register document type -> (label for the title, instrument).
_FEDERAL_REGISTER_TYPES = {
    "Rule": ("Final Rule", "final-rule"),
    "Proposed Rule": ("Proposed Rule", "proposed-rule"),
    "Notice": ("Notice", "notice"),
    "Presidential Document": ("Presidential Document", "presidential"),
}
# Boilerplate around the document body: the masthead, where to send comments,
# who to call, signatures and the printing office's end matter.
_FEDERAL_REGISTER_BOILERPLATE = (
    ".document-headings, #addresses, #for-further-information-contact, "
    ".signature, .end-matter, .printed-page, .footnotes, script, style"
)


def _iso_date(value) -> dt.date | None:
    try:
        return dt.date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def extract_federal_register(
    url: str, html: str, meta: dict | None = None, *, today: dt.date | None = None
) -> dict | None:
    """One published Federal Register document, if still inside the retention window."""
    meta = meta or {}
    published = _iso_date(meta.get("publication_date"))
    number = meta.get("document_number")
    if not published or not number:
        return None
    # A notice goes stale in substance (a TPS period ends) without the document
    # ever changing, so old ones age out of the corpus.
    cutoff = (today or dt.date.today()) - dt.timedelta(
        days=settings.FEDERAL_REGISTER_RETENTION_DAYS
    )
    if published < cutoff:
        return None

    soup = BeautifulSoup(html, "html.parser")
    for junk in soup.select(_FEDERAL_REGISTER_BOILERPLATE):
        junk.decompose()
    words = _text(soup).split()

    label, instrument = _FEDERAL_REGISTER_TYPES.get(meta.get("type"), ("Document", "notice"))
    # The date is part of every chunk's title so the model (and the user) can
    # judge how current the document is.
    dated = f"published {published.isoformat()}"
    effective = _iso_date(meta.get("effective_on"))
    if effective:
        dated += f", effective {effective.isoformat()}"
    agencies = meta.get("agencies") or []
    return {
        "doc_id": f"federal-register/{number}",
        "title": f"Federal Register {label} ({dated}): {meta.get('title') or number}",
        "topic": "federal-register",
        "instrument": instrument,
        # The most specific issuer is listed last (department, then agency).
        "authority": agencies[-1] if agencies else "Federal Register",
        "text": " ".join(words[:_FEDERAL_REGISTER_MAX_WORDS]),
        "last_verified": published,
    }


@dataclass(frozen=True)
class Source:
    """One scrape source. ``name`` is the spider's name, the feed directory under
    the feeds root, and the ``KnowledgeChunk.corpus`` its rows are written with."""

    name: str
    # (url, content, meta) -> {doc_id, title, topic, instrument, authority, text
    # [, forms][, last_verified]} or None to skip the page.
    extract: Callable[[str, str, dict], dict | None]

    @property
    def corpus(self) -> str:
        return self.name


SOURCES: dict[str, Source] = {
    source.name: source
    for source in (
        Source("uscis", extract),
        Source("ecfr", extract_ecfr),
        Source("federal-register", extract_federal_register),
    )
}


def records_from_feeds(
    feed_paths: list[Path], country: str = "us", source: str = "uscis"
) -> list[dict]:
    """Chunk every scraped page of one source into KnowledgeChunk field dicts
    (minus embedding).

    Each chunk is prefixed with its page title so it stays self-describing once
    retrieved on its own (a bare "(b) Terms ..." paragraph means nothing without
    "8 USC 1537"). Duplicate chunks within a doc are collapsed by chunk_id.
    """
    src = SOURCES[source]
    pages, crawled = latest_pages(feed_paths)
    records: dict[str, dict] = {}
    for url, (content, meta) in sorted(pages.items()):
        doc = src.extract(url, content, meta)
        if not doc or len(doc["text"].split()) < _MIN_WORDS:
            continue
        # Chunk ids are unique across sources: every doc_id is rooted at its corpus.
        root = doc["doc_id"]
        if not root.startswith(f"{src.corpus}/"):
            root = f"{src.corpus}/{root}"
        for body in chunk(doc["text"]):
            text = f"{doc['title']}: {body}" if doc["title"] else body
            chunk_id = f"{root}-{uuid.uuid5(uuid.NAMESPACE_URL, text).hex[:8]}"
            records[chunk_id] = {
                "chunk_id": chunk_id,
                "doc_id": doc["doc_id"],
                "country": country,
                "corpus": src.corpus,
                "text": text,
                "title": doc["title"][:512] or None,
                "topic": doc["topic"],
                "instrument": doc.get("instrument"),
                "authority": doc["authority"],
                "lang": "en",
                "source_url": url,
                "source_type": "official",
                "last_verified": doc.get("last_verified") or crawled,
                "forms": doc.get("forms"),
            }
    return list(records.values())
