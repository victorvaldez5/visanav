"""Tests for the pgvector retrieval path.

The Voyage client is always mocked, so these need no API key or network. The DB
tests exercise real pgvector cosine ranking, so they require the `vector`
extension (seeded via api/conftest.py + the pgvector Postgres image in CI).
"""
import asyncio
from datetime import date

import pytest

from core import embeddings
from core.llm import Deps, semantic_search
from knowledge.models import KnowledgeChunk


class _FakeResp:
    def __init__(self, embeddings):
        self.embeddings = embeddings


class _FakeVoyage:
    """Records calls and returns a fixed-per-text vector."""

    def __init__(self):
        self.calls = []

    def embed(self, texts, model, input_type):
        self.calls.append({"texts": list(texts), "model": model, "input_type": input_type})
        # 1024-dim vectors; content is irrelevant for the embed-shape tests.
        return _FakeResp([[float(len(t))] * 1024 for t in texts])


@pytest.fixture
def fake_voyage(monkeypatch):
    fake = _FakeVoyage()
    monkeypatch.setattr(embeddings, "get_voyage_client", lambda: fake)
    return fake


def test_embed_query_uses_query_input_type(fake_voyage):
    vec = embeddings.embed_query("how do I renew my green card?")
    assert len(vec) == 1024
    assert fake_voyage.calls[0]["input_type"] == "query"
    assert len(fake_voyage.calls) == 1


def test_embed_documents_batches_over_128(fake_voyage):
    texts = [f"chunk {i}" for i in range(200)]
    vecs = embeddings.embed_documents(texts)
    assert len(vecs) == 200
    # 200 inputs -> two batches (128 + 72), all as documents.
    assert [len(c["texts"]) for c in fake_voyage.calls] == [128, 72]
    assert all(c["input_type"] == "document" for c in fake_voyage.calls)


def _chunk(chunk_id, country, vector, **meta):
    return KnowledgeChunk.objects.create(
        chunk_id=chunk_id, doc_id="d1", country=country, text=meta.pop("text", chunk_id),
        embedding=vector, **meta,
    )


@pytest.mark.django_db(transaction=True)
def test_semantic_search_ranks_scopes_and_gates_by_confidence(fake_voyage, settings):
    # Query embeds to [1, 0, 0, ...]; nearest by cosine is the aligned vector.
    settings.RAG_MIN_SCORE = 0.5
    dims = 1024
    q = [1.0] + [0.0] * (dims - 1)
    monkey_vec = q

    def fake_embed(texts, model, input_type):
        return _FakeResp([monkey_vec for _ in texts])

    fake_voyage.embed = fake_embed

    near = [1.0] + [0.0] * (dims - 1)          # cosine sim 1.0  -> confident
    mid = [0.5, 0.5] + [0.0] * (dims - 2)      # cosine sim ~0.707 -> confident
    far = [0.0, 1.0] + [0.0] * (dims - 2)      # cosine sim 0.0  -> gated out
    _chunk("us-near", "us", near, topic="near", title="Near",
           source_url="https://uscis.gov/a", last_verified=date(2026, 2, 10),
           authority="Department of Homeland Security", instrument="regulation")
    _chunk("us-mid", "us", mid, topic="mid")
    _chunk("us-far", "us", far, topic="far")
    _chunk("ca-near", "ca", near, topic="other-country")  # must be excluded by scope

    deps = Deps(country="us")
    result = asyncio.run(semantic_search_ctx(deps, "any query"))

    # Ranked by cosine, scoped to the country, and the sub-threshold hit (us-far,
    # sim 0.0) is gated out — its text never reaches the model.
    ids = [m["id"] for m in result["matches"]]
    assert ids == ["us-near", "us-mid"]
    assert "us-far" not in ids
    assert "ca-near" not in ids
    assert result["has_confident_source"] is True

    top = result["matches"][0]
    assert top["title"] == "Near"
    assert top["source_url"] == "https://uscis.gov/a"
    assert top["last_verified"] == "2026-02-10"  # ISO date surfaced for the UI
    assert top["score"] == pytest.approx(1.0, abs=1e-4)  # identical vectors
    # Who issued it and what kind of document it is reach the model, so it can
    # weigh a regulation against guidance; a curated chunk has no instrument.
    assert top["authority"] == "Department of Homeland Security"
    assert top["instrument"] == "regulation"
    assert result["matches"][1]["instrument"] is None

    # Confident sources are collected on Deps for the streaming view to emit,
    # with citation metadata only (no chunk text).
    assert [s["id"] for s in deps.sources] == ["us-near", "us-mid"]
    assert deps.sources[0]["last_verified"] == "2026-02-10"
    assert "text" not in deps.sources[0]


@pytest.mark.django_db(transaction=True)
def test_semantic_search_confidence_gate_triggers_fallback(fake_voyage, settings):
    # Only an off-axis (irrelevant) chunk exists, so nothing clears the floor.
    settings.RAG_MIN_SCORE = 0.5
    dims = 1024
    q = [1.0] + [0.0] * (dims - 1)
    fake_voyage.embed = lambda texts, model, input_type: _FakeResp([q for _ in texts])

    far = [0.0, 1.0] + [0.0] * (dims - 2)  # cosine sim 0.0
    _chunk("us-far", "us", far, topic="far", title="Irrelevant",
           source_url="https://uscis.gov/z")

    deps = Deps(country="us")
    result = asyncio.run(semantic_search_ctx(deps, "any query"))

    # No confident source: no matches/text returned, the fallback is signalled,
    # and nothing is collected for citation.
    assert result["matches"] == []
    assert result["has_confident_source"] is False
    assert result["note"]  # non-empty fallback instruction for the model
    assert deps.sources == []


async def semantic_search_ctx(deps, query):
    """Call the agent tool with a minimal RunContext stand-in."""
    class _Ctx:
        pass

    ctx = _Ctx()
    ctx.deps = deps
    return await semantic_search(ctx, query)


# -- scraped-corpus ingest (knowledge.scrape_utils / ingest_scrape) -------------

_PM_HTML = """<div id="page-content"><article><h1><span>Chapter 2 - Revocation</span></h1>
<div id="guidance"><h2>A. Background</h2><p>{body}</p></div>
<div id="updates"><p>Technical update, do not index.</p></div></article></div>"""

_USC_HTML = """<div id="docViewer"><span class="contextHeadline">
<!-- field-start:cite -->8 USC 1537<!-- field-end:cite -->: Custody and release</span>
<!-- field-start:statute --><p>(a) {body}</p><!-- field-end:statute -->
<!-- field-start:notes --><p>Amendments note, do not index.</p><!-- field-end:notes --></div>"""

_FORM_HTML = """<div id="page-content"><article><h1>I-485, <span>Adjust Status</span></h1>
<p>{body}</p><section class="files-listing"><a>Form I-485 (PDF, 1.74 MB)</a></section>
</article></div>"""

_BODY = "Words about immigration law and procedure. " * 12


def _write_feed(path, pages):
    import json

    path.write_text(
        "\n".join(
            json.dumps({"url": u, "content_type": "text/html", "content": h})
            for u, h in pages
        )
        + "\n",
        encoding="utf-8",
    )


def test_scrape_extract_keeps_only_substantive_text():
    from knowledge.scrape_utils import extract

    pm = extract(
        "https://www.uscis.gov/policy-manual/volume-12-part-l-chapter-2",
        _PM_HTML.format(body=_BODY),
    )
    assert pm["title"] == "USCIS Policy Manual, Vol. 12, Part L, Chapter 2 - Revocation"
    assert pm["doc_id"] == "uscis/policy-manual/volume-12-part-l-chapter-2"
    assert "Background" in pm["text"] and "Technical update" not in pm["text"]

    usc = extract(
        "https://uscode.house.gov/view.xhtml?req=granuleid:USC-prelim-title8-section1537&num=0",
        _USC_HTML.format(body=_BODY),
    )
    assert usc["doc_id"] == "usc/8-1537"
    assert usc["title"] == "8 USC 1537: Custody and release"
    assert "Amendments" not in usc["text"]

    form = extract("https://www.uscis.gov/i-485", _FORM_HTML.format(body=_BODY))
    assert form["forms"] == ["I-485"]
    assert "PDF" not in form["text"]


def test_scrape_records_merge_incremental_feeds(tmp_path):
    from knowledge.scrape_utils import records_from_feeds

    url = "https://www.uscis.gov/i-485"
    # Older full crawl has two pages; the newer incremental crawl only re-emits
    # the one that changed, so the other must still come from the older feed.
    _write_feed(
        tmp_path / "2026-09-14T00-00-00+00-00.jsonl",
        [(url, _FORM_HTML.format(body="Old text. " * 40)),
         ("https://www.uscis.gov/n-400", _FORM_HTML.format(body=_BODY))],
    )
    _write_feed(
        tmp_path / "2026-09-21T00-00-00+00-00.jsonl",
        [(url, _FORM_HTML.format(body="New text. " * 40))],
    )
    records = records_from_feeds(sorted(tmp_path.glob("*.jsonl")))
    by_url = {r["source_url"]: r for r in records}
    assert "New text" in by_url[url]["text"] and "Old text" not in by_url[url]["text"]
    assert "https://www.uscis.gov/n-400" in by_url
    assert all(r["corpus"] == "uscis" and r["source_type"] == "official" for r in records)
    assert all(r["last_verified"] == date(2026, 9, 21) for r in records)
    assert all(r["text"].startswith("I-485, Adjust Status: ") for r in records if r["source_url"] == url)


def test_scrape_records_say_what_kind_of_document_each_chunk_is(tmp_path):
    from knowledge.scrape_utils import records_from_feeds

    _write_feed(
        tmp_path / "2026-09-21T00-00-00+00-00.jsonl",
        [("https://www.uscis.gov/i-485", _FORM_HTML.format(body=_BODY)),
         ("https://www.uscis.gov/policy-manual/volume-12-part-l-chapter-2",
          _PM_HTML.format(body=_BODY)),
         ("https://uscode.house.gov/view.xhtml?req=granuleid:USC-prelim-title8-section1537&num=0",
          _USC_HTML.format(body=_BODY))],
    )
    records = records_from_feeds(sorted(tmp_path.glob("*.jsonl")))
    assert {(r["topic"], r["instrument"]) for r in records} == {
        ("forms", "form"), ("policy-manual", "agency-guidance"), ("statute", "statute"),
    }
    # Every chunk id is rooted at its corpus, so sources can never collide.
    assert all(r["chunk_id"].startswith("uscis/") for r in records)


# -- multi-source ingest (the ingest_scrape command over a feeds root) ------------

_CFR_URL = "https://www.ecfr.gov/current/title-8/section-274a.12"
_CFR_XML = """<DIV8 N="§ 274a.12" TYPE="SECTION">
<HEAD>§ 274a.12   Classes of aliens authorized to accept employment.</HEAD>
<P>(a) <I>Aliens authorized employment incident to status.</I> {body}</P>
<CITA TYPE="N">[52 FR 16221, May 1, 1987, do not index]</CITA>
<EDNOTE><HED>Editorial Note:</HED><PSPACE>For citations, do not index.</PSPACE></EDNOTE></DIV8>"""
_CFR_META = {"citation": "8 CFR 274a.12", "kind": "section", "title": 8, "chapter": "I",
             "part": "274a", "heading": "Classes of aliens authorized to accept employment."}

_FR_URL = "https://www.federalregister.gov/documents/2026/09/29/2026-19000/extension-of-tps"
_FR_HTML = """<div class="preamble"><div class="document-headings"><p>Masthead, do not index.</p></div>
<div id="summary"><h1>SUMMARY:</h1><p>{body}</p></div>
<div id="addresses"><h1>ADDRESSES:</h1><p>Mail comments here, do not index.</p></div></div>
<div class="supplemental-info"><p>Supplementary detail. {body}</p></div>
<div class="signature"><p>Signed, do not index.</p></div>"""


def _fr_meta(days_ago, **extra):
    from datetime import timedelta

    return {
        "document_number": "2026-19000",
        "title": "Extension of the Designation of Honduras for Temporary Protected Status",
        "type": "Notice",
        "publication_date": (date.today() - timedelta(days=days_ago)).isoformat(),
        "effective_on": None,
        "agencies": ["Homeland Security Department", "U.S. Citizenship and Immigration Services"],
        "cfr_references": [],
        **extra,
    }


def _write_lines(path, lines):
    import json

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(line) for line in lines) + "\n", encoding="utf-8")


def _page(url, content, meta=None, content_type="text/html"):
    line = {"url": url, "content_type": content_type, "content": content}
    if meta is not None:
        line["meta"] = meta
    return line


_FEED = "2026-09-21T00-00-00+00-00.jsonl"
_LATER_FEED = "2026-09-28T00-00-00+00-00.jsonl"


def _feeds_root(tmp_path, sources=("uscis", "ecfr", "federal-register")):
    """A feeds root as pulled from R2: one directory of feeds per source."""
    root = tmp_path / "items"
    if "uscis" in sources:
        # No `meta`: the shape USCIS feeds have always had.
        _write_lines(root / "uscis" / _FEED,
                     [_page("https://www.uscis.gov/i-485", _FORM_HTML.format(body=_BODY))])
    if "ecfr" in sources:
        _write_lines(root / "ecfr" / _FEED,
                     [_page(_CFR_URL, _CFR_XML.format(body=_BODY), _CFR_META, "application/xml")])
    if "federal-register" in sources:
        _write_lines(root / "federal-register" / _FEED,
                     [_page(_FR_URL, _FR_HTML.format(body=_BODY), _fr_meta(days_ago=10))])
    return root


def _ingest_scrape(root, *args):
    from django.core.management import call_command

    call_command("ingest_scrape", str(root), "--upsert", *args)


def _seed(chunk_id, corpus):
    return KnowledgeChunk.objects.create(
        chunk_id=chunk_id, doc_id=chunk_id, country="us", corpus=corpus, text=chunk_id,
        embedding=[0.0] * 1024,
    )


@pytest.fixture
def voyage_key(fake_voyage, settings):
    settings.VOYAGE_API_KEY = "test"
    return fake_voyage


@pytest.mark.django_db
def test_ingest_scrape_one_run_ingests_every_source(voyage_key, tmp_path):
    _seed("curated-1", "curated")
    _seed("stale-scrape", "uscis")
    _ingest_scrape(_feeds_root(tmp_path))

    assert KnowledgeChunk.objects.filter(chunk_id="curated-1").exists()
    assert not KnowledgeChunk.objects.filter(chunk_id="stale-scrape").exists()
    assert KnowledgeChunk.objects.filter(corpus="uscis", doc_id="uscis/i-485").exists()

    cfr = KnowledgeChunk.objects.filter(corpus="ecfr").first()
    assert cfr.title == "8 CFR 274a.12: Classes of aliens authorized to accept employment."
    assert cfr.text.startswith(cfr.title + ": (a) Aliens authorized employment incident")
    assert "do not index" not in cfr.text
    assert (cfr.instrument, cfr.topic) == ("regulation", "regulation")
    assert cfr.authority == "Department of Homeland Security"
    assert cfr.source_url == _CFR_URL and cfr.source_type == "official"
    assert cfr.last_verified == date(2026, 9, 21)  # the crawl date

    notice = KnowledgeChunk.objects.filter(corpus="federal-register").first()
    published = _fr_meta(days_ago=10)["publication_date"]
    assert notice.title == (
        f"Federal Register Notice (published {published}): "
        "Extension of the Designation of Honduras for Temporary Protected Status"
    )
    assert "Supplementary detail" in notice.text and "do not index" not in notice.text
    assert (notice.instrument, notice.topic) == ("notice", "federal-register")
    assert notice.authority == "U.S. Citizenship and Immigration Services"
    assert notice.source_url == _FR_URL
    # A notice is as fresh as its publication, not as the crawl that fetched it.
    assert notice.last_verified.isoformat() == published


@pytest.mark.django_db
def test_ingest_scrape_narrowed_to_one_source_leaves_the_rest(voyage_key, tmp_path):
    for corpus in ("curated", "uscis", "ecfr", "federal-register"):
        _seed(f"old-{corpus}", corpus)
    _ingest_scrape(_feeds_root(tmp_path), "--source", "ecfr")

    kept = set(KnowledgeChunk.objects.filter(chunk_id__startswith="old-")
               .values_list("chunk_id", flat=True))
    assert kept == {"old-curated", "old-uscis", "old-federal-register"}
    assert KnowledgeChunk.objects.filter(corpus="ecfr").count() >= 1


@pytest.mark.django_db
def test_ingest_scrape_skips_a_source_with_no_feeds(voyage_key, tmp_path):
    _seed("old-ecfr", "ecfr")
    # Nothing was pulled for ecfr (no directory at all): its rows must survive.
    _ingest_scrape(_feeds_root(tmp_path, sources=("uscis", "federal-register")))

    assert KnowledgeChunk.objects.filter(chunk_id="old-ecfr").exists()
    assert KnowledgeChunk.objects.filter(corpus="uscis", doc_id="uscis/i-485").exists()
    assert KnowledgeChunk.objects.filter(corpus="federal-register").exists()


@pytest.mark.django_db
def test_ingest_scrape_one_bad_source_fails_the_run_but_not_the_others(voyage_key, tmp_path):
    from django.core.management.base import CommandError

    _seed("old-ecfr", "ecfr")
    root = _feeds_root(tmp_path)
    (root / "ecfr" / _LATER_FEED).write_text("{not json\n", encoding="utf-8")

    with pytest.raises(CommandError, match="ecfr"):
        _ingest_scrape(root)

    # The broken source keeps what it had; the healthy ones were still replaced.
    assert set(KnowledgeChunk.objects.filter(corpus="ecfr")
               .values_list("chunk_id", flat=True)) == {"old-ecfr"}
    assert KnowledgeChunk.objects.filter(corpus="uscis", doc_id="uscis/i-485").exists()
    assert KnowledgeChunk.objects.filter(corpus="federal-register").exists()


@pytest.mark.django_db
def test_ingest_scrape_never_replaces_a_corpus_with_nothing(voyage_key, tmp_path):
    from django.core.management.base import CommandError

    _seed("old-ecfr", "ecfr")
    root = _feeds_root(tmp_path, sources=("ecfr",))
    # Feeds exist but nothing can be extracted from them (a broken crawl).
    _write_lines(root / "ecfr" / _FEED, [_page(_CFR_URL, "<DIV8/>", _CFR_META)])

    with pytest.raises(CommandError, match="ecfr"):
        _ingest_scrape(root)
    assert KnowledgeChunk.objects.filter(chunk_id="old-ecfr").exists()


@pytest.mark.django_db
def test_ingest_scrape_rejects_an_unknown_source(voyage_key, tmp_path):
    from django.core.management.base import CommandError

    _seed("old-ecfr", "ecfr")
    with pytest.raises(CommandError, match="ecrf.*Valid sources: uscis, ecfr, federal-register"):
        _ingest_scrape(_feeds_root(tmp_path), "--source", "ecrf")
    assert KnowledgeChunk.objects.count() == 1  # nothing was ingested


@pytest.mark.django_db
def test_ingest_scrape_rejects_a_single_source_directory(voyage_key, tmp_path):
    from django.core.management.base import CommandError

    # The old calling convention (the uscis feed directory itself) would
    # otherwise look like a root in which every source has no feeds.
    root = _feeds_root(tmp_path)
    with pytest.raises(CommandError, match="feeds root"):
        _ingest_scrape(root / "uscis")


@pytest.mark.django_db
def test_ingest_scrape_dry_run_writes_nothing(voyage_key, tmp_path, capsys):
    from django.core.management import call_command

    _seed("old-ecfr", "ecfr")
    call_command("ingest_scrape", str(_feeds_root(tmp_path)))

    assert list(KnowledgeChunk.objects.values_list("chunk_id", flat=True)) == ["old-ecfr"]
    assert voyage_key.calls == []  # nothing was embedded, so nothing was spent
    out = capsys.readouterr().out
    for source in ("uscis", "ecfr", "federal-register"):
        assert f"{source}: 1 chunk(s) from 1 page(s)" in out


@pytest.mark.django_db
def test_ingest_scrape_removed_section_leaves_the_corpus(voyage_key, tmp_path):
    other_url = "https://www.ecfr.gov/current/title-8/section-274a.13"
    other_meta = {**_CFR_META, "citation": "8 CFR 274a.13", "heading": "Application."}
    root = _feeds_root(tmp_path, sources=("ecfr",))
    _write_lines(root / "ecfr" / _FEED, [
        _page(_CFR_URL, _CFR_XML.format(body=_BODY), _CFR_META, "application/xml"),
        _page(other_url, _CFR_XML.format(body=_BODY), other_meta, "application/xml"),
    ])
    # The next crawl found 274a.12 gone and says so with a tombstone.
    _write_lines(root / "ecfr" / _LATER_FEED, [{"url": _CFR_URL, "removed": True}])
    _ingest_scrape(root)
    assert set(KnowledgeChunk.objects.filter(corpus="ecfr")
               .values_list("source_url", flat=True)) == {other_url}

    # A still-later crawl that sees the section again restores it.
    _write_lines(root / "ecfr" / "2026-10-05T00-00-00+00-00.jsonl", [
        _page(_CFR_URL, _CFR_XML.format(body=_BODY), _CFR_META, "application/xml"),
    ])
    _ingest_scrape(root)
    assert set(KnowledgeChunk.objects.filter(corpus="ecfr")
               .values_list("source_url", flat=True)) == {_CFR_URL, other_url}


@pytest.mark.django_db
def test_ingest_scrape_page_removed_from_uscis_leaves_the_corpus(voyage_key, tmp_path):
    form, chapter = "https://www.uscis.gov/i-485", (
        "https://www.uscis.gov/policy-manual/volume-12-part-l-chapter-3"
    )
    root = _feeds_root(tmp_path, sources=())
    _write_lines(root / "uscis" / _FEED, [
        _page(form, _FORM_HTML.format(body=_BODY)),
        _page(chapter, _PM_HTML.format(body=_BODY)),
    ])
    # USCIS withdrew the chapter; after it stayed away the crawl said so.
    _write_lines(root / "uscis" / _LATER_FEED, [{"url": chapter, "files": [], "removed": True}])
    _ingest_scrape(root)
    assert set(KnowledgeChunk.objects.filter(corpus="uscis")
               .values_list("source_url", flat=True)) == {form}

    # If the chapter is published again, a later crawl emits it as a new page.
    _write_lines(root / "uscis" / "2026-10-05T00-00-00+00-00.jsonl",
                 [_page(chapter, _PM_HTML.format(body=_BODY))])
    _ingest_scrape(root)
    assert set(KnowledgeChunk.objects.filter(corpus="uscis")
               .values_list("source_url", flat=True)) == {form, chapter}


@pytest.mark.django_db
def test_ingest_scrape_federal_register_ages_out_and_labels_rules(voyage_key, settings, tmp_path):
    settings.FEDERAL_REGISTER_RETENTION_DAYS = 365
    old_url = _FR_URL.replace("2026-19000", "2025-00001")
    rule_url = _FR_URL.replace("2026-19000", "2026-20000")
    effective = _fr_meta(days_ago=0)["publication_date"]
    root = _feeds_root(tmp_path, sources=())
    _write_lines(root / "federal-register" / _FEED, [
        # Published before the retention window: an expired notice must not linger.
        _page(old_url, _FR_HTML.format(body=_BODY),
              _fr_meta(days_ago=400, document_number="2025-00001")),
        _page(rule_url, _FR_HTML.format(body=_BODY),
              _fr_meta(days_ago=5, document_number="2026-20000", type="Proposed Rule",
                       title="Optional Practical Training Fees")),
        _page(_FR_URL, _FR_HTML.format(body=_BODY),
              _fr_meta(days_ago=10, type="Rule", effective_on=effective,
                       agencies=["Justice Department", "Executive Office for Immigration Review"])),
    ])
    _ingest_scrape(root)

    rows = {r.source_url: r for r in KnowledgeChunk.objects.filter(corpus="federal-register")}
    assert old_url not in rows
    assert rows[rule_url].instrument == "proposed-rule"
    assert rows[rule_url].title.startswith("Federal Register Proposed Rule (published ")
    final = rows[_FR_URL]
    assert final.instrument == "final-rule"
    assert f", effective {effective})" in final.title
    assert final.authority == "Executive Office for Immigration Review"


def test_scrape_ecfr_authority_follows_the_chapter():
    from knowledge.scrape_utils import extract_ecfr

    xml = _CFR_XML.format(body=_BODY)
    eoir = extract_ecfr(_CFR_URL, xml, {**_CFR_META, "citation": "8 CFR 1003.1", "chapter": "V"})
    state = extract_ecfr(_CFR_URL, xml, {**_CFR_META, "citation": "22 CFR 41.0", "title": 22})
    labor = extract_ecfr(_CFR_URL, xml, {**_CFR_META, "citation": "20 CFR 655.1",
                                         "title": 20, "chapter": "V"})
    assert eoir["authority"] == "Executive Office for Immigration Review (DOJ)"
    assert state["authority"] == "Department of State"
    assert labor["authority"] == "Department of Labor"
    assert eoir["doc_id"] == "ecfr/8-cfr-1003.1"


# -- scheduled ingestion: due detection, the record, guards (knowledge/corpus.py) --


def _runs(corpus, **filters):
    from knowledge.models import IngestRun

    return list(IngestRun.objects.filter(corpus=corpus, **filters).order_by("started_at"))


def _embedded(fake):
    """How many texts have been sent to Voyage so far."""
    return sum(len(call["texts"]) for call in fake.calls)


@pytest.mark.django_db
def test_only_due_ingests_a_source_once_per_new_feed(voyage_key, tmp_path):
    root = _feeds_root(tmp_path)
    _ingest_scrape(root, "--only-due")

    (run,) = _runs("ecfr")
    assert (run.status, run.marker, run.chunks, run.embedded) == ("succeeded", _FEED, 1, 1)
    assert run.previous_chunks == 0 and run.finished_at is not None
    assert all(len(_runs(c)) == 1 for c in ("uscis", "federal-register"))

    # The next scheduled run finds no new feed: nothing is embedded or rewritten.
    spent = _embedded(voyage_key)
    stamps = dict(KnowledgeChunk.objects.values_list("chunk_id", "updated_at"))
    _ingest_scrape(root, "--only-due")
    assert _embedded(voyage_key) == spent
    assert dict(KnowledgeChunk.objects.values_list("chunk_id", "updated_at")) == stamps
    assert len(_runs("ecfr")) == 1

    # One source's crawl finishes and leaves a newer feed: only that source runs.
    other_url = "https://www.ecfr.gov/current/title-8/section-274a.13"
    _write_lines(root / "ecfr" / _LATER_FEED, [
        _page(other_url, _CFR_XML.format(body=_BODY),
              {**_CFR_META, "citation": "8 CFR 274a.13", "heading": "Application."},
              "application/xml"),
    ])
    _ingest_scrape(root, "--only-due")
    assert [r.marker for r in _runs("ecfr")] == [_FEED, _LATER_FEED]
    assert len(_runs("uscis")) == 1 and len(_runs("federal-register")) == 1
    assert KnowledgeChunk.objects.filter(corpus="ecfr").count() == 2


@pytest.mark.django_db
def test_unchanged_chunks_keep_their_embeddings(voyage_key, settings, tmp_path):
    other_url = "https://www.ecfr.gov/current/title-8/section-274a.13"
    other_meta = {**_CFR_META, "citation": "8 CFR 274a.13", "heading": "Application."}
    root = _feeds_root(tmp_path, sources=("ecfr",))
    _ingest_scrape(root)
    assert _embedded(voyage_key) == 1

    # A later crawl adds one section. The section already stored is not sent to
    # Voyage again, but its row is still rewritten with the new crawl's date.
    _write_lines(root / "ecfr" / _LATER_FEED,
                 [_page(other_url, _CFR_XML.format(body=_BODY), other_meta, "application/xml")])
    _ingest_scrape(root)
    assert _embedded(voyage_key) == 2
    assert _runs("ecfr")[-1].embedded == 1 and _runs("ecfr")[-1].chunks == 2
    assert set(KnowledgeChunk.objects.filter(corpus="ecfr")
               .values_list("last_verified", flat=True)) == {date(2026, 9, 28)}

    # A different embedding model makes every stored vector unusable.
    settings.EMBEDDING_MODEL = "voyage-law-2"
    _ingest_scrape(root)
    assert _embedded(voyage_key) == 4


@pytest.mark.django_db
def test_a_new_embedding_model_makes_every_corpus_due(voyage_key, curated_dir, settings, tmp_path):
    from django.core.management import call_command

    root = _feeds_root(tmp_path, sources=("ecfr",))
    _ingest_scrape(root, "--only-due")
    call_command("ingest", "us", "--upsert", "--only-due")
    assert _embedded(voyage_key) == 2

    # No new feed and no edit to data/, but the stored vectors no longer match
    # what queries are embedded with: the scheduled run re-embeds both corpora.
    settings.EMBEDDING_MODEL = "voyage-law-2"
    _ingest_scrape(root, "--only-due")
    call_command("ingest", "us", "--upsert", "--only-due")
    assert _embedded(voyage_key) == 4
    assert [r.embedding_model for r in _runs("ecfr")] == ["voyage-3", "voyage-law-2"]
    assert [r.embedding_model for r in _runs("curated")] == ["voyage-3", "voyage-law-2"]

    # Once that is done, it settles again.
    _ingest_scrape(root, "--only-due")
    call_command("ingest", "us", "--upsert", "--only-due")
    assert _embedded(voyage_key) == 4 and len(_runs("ecfr")) == 2


@pytest.mark.django_db
def test_failed_source_is_recorded_and_retried(voyage_key, tmp_path):
    from django.core.management.base import CommandError

    root = _feeds_root(tmp_path)
    _ingest_scrape(root, "--only-due")
    (root / "ecfr" / _LATER_FEED).write_text("{not json\n", encoding="utf-8")

    for _ in range(2):  # it stays due, so every scheduled run fails loudly
        with pytest.raises(CommandError, match="ecfr"):
            _ingest_scrape(root, "--only-due")
    statuses = [r.status for r in _runs("ecfr")]
    assert statuses == ["succeeded", "failed", "failed"]
    assert "JSONDecodeError" in _runs("ecfr")[-1].error
    assert KnowledgeChunk.objects.filter(corpus="ecfr").count() == 1  # the good rows stand

    # Once the feed is fixed the next run picks it up without anyone forcing it.
    (root / "ecfr" / _LATER_FEED).write_text("", encoding="utf-8")
    _ingest_scrape(root, "--only-due")
    assert _runs("ecfr")[-1].status == "succeeded"


@pytest.mark.django_db
def test_shrink_guard_refuses_a_much_smaller_corpus(voyage_key, tmp_path):
    from django.core.management.base import CommandError

    for n in range(10):
        _seed(f"old-ecfr-{n}", "ecfr")
    root = _feeds_root(tmp_path, sources=("ecfr",))

    # One chunk would replace ten: that is a broken crawl, not ten repeals.
    with pytest.raises(CommandError, match="ecfr"):
        _ingest_scrape(root)
    assert KnowledgeChunk.objects.filter(corpus="ecfr").count() == 10
    (run,) = _runs("ecfr")
    assert (run.status, run.chunks, run.previous_chunks) == ("skipped", 1, 10)
    assert "--force" in run.error
    assert _embedded(voyage_key) == 0  # refused before spending anything

    # Unless a person says the shrink is real.
    _ingest_scrape(root, "--force")
    assert KnowledgeChunk.objects.filter(corpus="ecfr").count() == 1
    assert _runs("ecfr")[-1].status == "succeeded"


@pytest.mark.django_db(transaction=True)
def test_ingestion_does_nothing_while_another_run_holds_the_lock(voyage_key, tmp_path, capsys):
    from django.db import connection

    from knowledge.corpus import _LOCK_ID

    _seed("old-ecfr", "ecfr")
    other = connection.copy()  # another process, as far as Postgres can tell
    try:
        with other.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_lock(%s)", [_LOCK_ID])
        _ingest_scrape(_feeds_root(tmp_path))  # exits cleanly: no error raised
        assert "Another ingestion run is in progress" in capsys.readouterr().out
        assert list(KnowledgeChunk.objects.values_list("chunk_id", flat=True)) == ["old-ecfr"]
        assert _runs("ecfr") == []
    finally:
        other.close()

    # With the other run finished, it goes ahead.
    _ingest_scrape(_feeds_root(tmp_path))
    assert not KnowledgeChunk.objects.filter(chunk_id="old-ecfr").exists()


_CURATED_DOC = """---
doc_id: us-green-card-renewal
authority: USCIS
topic: green-card
title: Renewing a green card
lang: en
source_url: https://www.uscis.gov/i-90
source_type: official
last_verified: 2026-09-01
---
{body}
"""


@pytest.fixture
def curated_dir(tmp_path, settings):
    """A data/countries tree with one curated document for `us`."""
    doc = tmp_path / "countries" / "us" / "knowledge" / "green-card.md"
    doc.parent.mkdir(parents=True)
    doc.write_text(_CURATED_DOC.format(body="A permanent resident files Form I-90 to renew."))
    settings.KNOWLEDGE_DATA_DIR = str(tmp_path / "countries")
    return doc


@pytest.mark.django_db
def test_curated_ingest_runs_only_when_the_data_changed(voyage_key, curated_dir):
    from django.core.management import call_command

    _seed("old-ecfr", "ecfr")
    call_command("ingest", "us", "--upsert", "--only-due")
    row = KnowledgeChunk.objects.get(corpus="curated")
    assert row.title == "Renewing a green card" and row.last_verified == date(2026, 9, 1)
    (run,) = _runs("curated")
    assert (run.status, run.chunks) == ("succeeded", 1)
    assert KnowledgeChunk.objects.filter(chunk_id="old-ecfr").exists()  # other corpora untouched

    # Nothing in data/ changed (every scheduled run between deploys).
    spent = _embedded(voyage_key)
    call_command("ingest", "us", "--upsert", "--only-due")
    assert _embedded(voyage_key) == spent and len(_runs("curated")) == 1

    # A deploy ships an edit to the document.
    curated_dir.write_text(_CURATED_DOC.format(body="File Form I-90 online or by mail to renew."))
    call_command("ingest", "us", "--upsert", "--only-due")
    assert "online or by mail" in KnowledgeChunk.objects.get(corpus="curated").text
    assert len(_runs("curated")) == 2

    # A metadata-only edit (the source was re-checked) is a change too, and
    # costs no embedding.
    spent = _embedded(voyage_key)
    curated_dir.write_text(
        curated_dir.read_text().replace("last_verified: 2026-09-01", "last_verified: 2026-10-01")
    )
    call_command("ingest", "us", "--upsert", "--only-due")
    assert KnowledgeChunk.objects.get(corpus="curated").last_verified == date(2026, 10, 1)
    assert _embedded(voyage_key) == spent


@pytest.fixture
def r2_is(monkeypatch):
    """Make the R2 feed store read a local feeds root instead of the bucket."""
    from knowledge import feed_store

    def use(root):
        monkeypatch.setattr(
            feed_store.R2Feeds, "from_settings",
            classmethod(lambda cls, workdir: feed_store.LocalFeeds(root)),
        )

    return use


@pytest.mark.django_db
def test_refresh_corpus_brings_everything_up_to_date_then_idles(
        voyage_key, curated_dir, r2_is, tmp_path, capsys):
    from django.core.management import call_command

    root = _feeds_root(tmp_path, sources=("uscis", "ecfr"))  # no Federal Register crawl yet
    r2_is(root)
    call_command("refresh_corpus")

    assert set(KnowledgeChunk.objects.values_list("corpus", flat=True)) == {
        "curated", "uscis", "ecfr"
    }
    assert "summary: curated=succeeded, uscis=succeeded, ecfr=succeeded, " \
           "federal-register=no-feeds" in capsys.readouterr().out

    # An hour later nothing is new: no embeddings, no writes, a clean exit.
    spent = _embedded(voyage_key)
    call_command("refresh_corpus")
    assert _embedded(voyage_key) == spent
    assert "summary: curated=not-due, uscis=not-due, ecfr=not-due, " \
           "federal-register=no-feeds" in capsys.readouterr().out

    # Then the Federal Register crawl finishes.
    _write_lines(root / "federal-register" / _FEED,
                 [_page(_FR_URL, _FR_HTML.format(body=_BODY), _fr_meta(days_ago=10))])
    call_command("refresh_corpus")
    assert KnowledgeChunk.objects.filter(corpus="federal-register").exists()
    assert len(_runs("uscis")) == 1 and len(_runs("curated")) == 1


@pytest.mark.django_db
def test_refresh_corpus_fails_loudly_but_keeps_what_it_can(
        voyage_key, curated_dir, tmp_path, settings):
    from django.core.management import call_command
    from django.core.management.base import CommandError

    # The bucket is not configured on this service: the scrape sources cannot
    # be read, but the curated corpus is still brought up to date.
    settings.R2_BUCKET = None
    with pytest.raises(CommandError, match="uscis, ecfr, federal-register"):
        call_command("refresh_corpus")
    assert KnowledgeChunk.objects.filter(corpus="curated").exists()
    # Each source it could not look at has a failed run on record.
    for corpus in ("uscis", "ecfr", "federal-register"):
        (run,) = _runs(corpus)
        assert run.status == "failed" and "R2_BUCKET" in run.error


@pytest.mark.django_db
def test_a_source_whose_feeds_cannot_be_listed_is_recorded_as_failed(
        voyage_key, curated_dir, tmp_path, monkeypatch, capsys):
    from django.core.management import call_command
    from django.core.management.base import CommandError

    from knowledge import feed_store

    class _EcfrListingFails(feed_store.LocalFeeds):
        def newest(self, source):
            if source == "ecfr":
                raise ConnectionError("R2 is unreachable")
            return super().newest(source)

    root = _feeds_root(tmp_path)
    monkeypatch.setattr(
        feed_store.R2Feeds, "from_settings",
        classmethod(lambda cls, workdir: _EcfrListingFails(root)),
    )
    with pytest.raises(CommandError, match="ecfr"):
        call_command("refresh_corpus")

    (run,) = _runs("ecfr")
    assert run.status == "failed" and "R2 is unreachable" in run.error
    assert run.finished_at is not None
    assert _runs("uscis")[-1].status == "succeeded"  # the others still went ahead

    capsys.readouterr()
    call_command("corpus_status")
    (line,) = [ln for ln in capsys.readouterr().out.splitlines() if ln.startswith("us  ecfr")]
    assert "latest attempt failed" in line and "R2 is unreachable" in line

    # A dry run that hits the same error writes nothing down.
    with pytest.raises(CommandError):
        call_command("ingest_scrape", "--from-r2")
    assert len(_runs("ecfr")) == 1


class _StubS3:
    """The two S3 calls R2Feeds makes, over a dict of {key: bytes}."""

    def __init__(self, objects):
        self.objects = objects
        self.listed = []

    def get_paginator(self, operation):
        assert operation == "list_objects_v2"
        stub = self

        class _Paginator:
            def paginate(self, Bucket, Prefix):
                stub.listed.append(Prefix)
                keys = sorted(k for k in stub.objects if k.startswith(Prefix))
                # two pages, to prove pagination is followed
                yield {"Contents": [{"Key": k, "Size": len(stub.objects[k])} for k in keys[:1]]}
                yield {"Contents": [{"Key": k, "Size": len(stub.objects[k])} for k in keys[1:]]}

        return _Paginator()

    def download_file(self, bucket, key, filename):
        with open(filename, "wb") as f:
            f.write(self.objects[key])


def test_r2_feed_store_lists_and_downloads_one_source(tmp_path):
    from knowledge.feed_store import R2Feeds

    s3 = _StubS3({
        "raw/items/ecfr/2026-09-21T00-00-00+00-00.jsonl": b"old\n",
        "raw/items/ecfr/2026-09-28T00-00-00+00-00.jsonl": b"new\n",
        "raw/items/ecfr/notes.txt": b"not a feed",
        "raw/items/ecfr-archive/2026-12-01T00-00-00+00-00.jsonl": b"another source",
        "raw/items/uscis/2026-10-05T00-00-00+00-00.jsonl": b"uscis\n",
    })
    store = R2Feeds("bucket", s3, tmp_path)

    assert store.newest("ecfr") == "2026-09-28T00-00-00+00-00.jsonl"
    assert store.newest("federal-register") is None
    assert s3.listed == ["raw/items/ecfr/", "raw/items/federal-register/"]

    paths = store.fetch("ecfr")
    # Oldest first, in the per-source layout, and nothing from other prefixes.
    assert [p.relative_to(tmp_path).as_posix() for p in paths] == [
        "ecfr/2026-09-21T00-00-00+00-00.jsonl", "ecfr/2026-09-28T00-00-00+00-00.jsonl",
    ]
    assert paths[-1].read_bytes() == b"new\n"
    assert not (tmp_path / "uscis").exists()


@pytest.mark.django_db
def test_corpus_status_shows_how_fresh_each_corpus_is(voyage_key, tmp_path, capsys):
    from django.core.management import call_command
    from django.core.management.base import CommandError

    _seed("unrecorded", "curated")  # ingested before runs were recorded
    root = _feeds_root(tmp_path, sources=("uscis", "ecfr"))
    _ingest_scrape(root)
    (root / "ecfr" / _LATER_FEED).write_text("{not json\n", encoding="utf-8")
    with pytest.raises(CommandError):
        _ingest_scrape(root, "--source", "ecfr")
    capsys.readouterr()

    call_command("corpus_status")
    out = capsys.readouterr().out
    assert "total chunks: 3" in out
    status = {line.split()[1]: line for line in out.split("last ingestion per corpus:")[1].splitlines() if line}
    assert "never ingested on record" in status["curated"]
    assert f"1 chunk(s) (1 embedded), marker {_FEED}" in status["uscis"]
    assert "latest attempt" not in status["uscis"]
    assert f"marker {_FEED}" in status["ecfr"] and "latest attempt failed" in status["ecfr"]
