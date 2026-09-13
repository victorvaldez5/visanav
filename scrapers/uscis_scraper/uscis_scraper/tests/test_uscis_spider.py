# tests/test_uscis_spider.py
import pytest
from scrapy.http import HtmlResponse, Response, Request
from ..spiders.uscis_spider import UscisSpider
from ..items import UscisItem


@pytest.fixture
def spider():
    return UscisSpider()


def make_html_response(url: str, body: str) -> HtmlResponse:
    return HtmlResponse(url=url, body=body.encode("utf-8"), encoding="utf-8")


def make_pdf_response(url: str) -> Response:
    # PDF responses are binary, but FilesPipeline only cares about URL and headers
    headers = {"Content-Type": "application/pdf"}
    return Response(url=url, headers=headers, body=b"%PDF-1.4")


def test_parse_all_forms_generates_follow_requests(spider):
    html = """
    <html>
      <body>
        <a class="link--form-title" href="/form1">F1</a>
        <a class="link--form-title" href="/form2">F2</a>
      </body>
    </html>
    """
    resp = make_html_response("https://www.uscis.gov/forms/all-forms", html)
    results = list(spider.parse_all_forms(resp))

    # we expect two follow requests with correct callbacks and meta
    assert len(results) == 2
    for req, expected_path in zip(results, ["/form1", "/form2"]):
        assert isinstance(req, Request)
        assert req.callback == spider.parse_forms_page
        assert req.url.endswith(expected_path)
        assert req.meta["parent_page"] == resp.url


def test_parse_forms_page_yields_html_item_and_pdf_requests(spider):
    html = """
    <html>
      <body>
        <article class="media">
          <a href="https://example.com/doc1.pdf">PDF1</a>
          <a href="/internal/page.html">HTML</a>
        </article>
      </body>
    </html>
    """
    parent = "https://parent.page/"
    resp = make_html_response("https://www.uscis.gov/forms/ar-11", html)
    resp.request = Request(resp.url, meta={"parent_page": parent})
    results = list(spider.parse_forms_page(resp))

    # First result is the HTML item
    html_item = results[0]
    assert isinstance(html_item, UscisItem)
    assert html_item["url"] == resp.url
    assert html_item["content_type"] == "text/html"
    assert 'article class="media"' in html_item["content"]
    assert html_item["parent_page"] == parent
    # files field is a list containing the list of hrefs
    assert html_item["files"] == ["https://example.com/doc1.pdf", "/internal/page.html"]

    # Remaining results are follow-requests for PDFs only
    pdf_reqs = results[1:]
    assert len(pdf_reqs) == 1
    pdf_req = pdf_reqs[0]
    assert isinstance(pdf_req, Request)
    assert pdf_req.callback == spider.parse_pdf
    assert pdf_req.url == "https://example.com/doc1.pdf"
    assert pdf_req.meta["parent_page"] == resp.url


def test_parse_legislation_page_generates_uscode_followers(spider):
    html = """
    <html>
      <body>
        <table>
          <tr><td><a href="/uscode1">USC1</a></td></tr>
          <tr><td><a href="https://uscode.house.gov/uscode2">USC2</a></td></tr>
        </table>
      </body>
    </html>
    """
    resp = make_html_response(
        "https://www.uscis.gov/laws-and-policy/legislation/immigration-and-nationality-act",
        html,
    )
    resp.request = Request(resp.url, meta={"parent_page": "parent-url"})
    results = list(spider.parse_legislation_page(resp))

    assert len(results) == 2
    for req, expected in zip(results, ["/uscode1", "https://uscode.house.gov/uscode2"]):
        assert isinstance(req, Request)
        assert req.callback == spider.parse_uscode_page
        assert req.url.endswith(expected)
        assert req.meta["parent_page"] == resp.url


def test_parse_uscode_page_yields_html_item(spider):
    body = "<html><head><title>USC</title></head><body>Content</body></html>"
    parent = "legislation-parent"
    resp = make_html_response("https://example.com/uscode1", body)
    resp.request = Request(resp.url, meta={"parent_page": parent})
    items = list(spider.parse_uscode_page(resp))

    assert len(items) == 1
    item = items[0]
    assert isinstance(item, UscisItem)
    assert item["url"] == resp.url
    assert item["content_type"] == "text/html"
    assert "Content" in item["content"]
    assert item.get("files") is None
    assert item["parent_page"] == parent


def test_parse_pdf_yields_pdf_item(spider):
    url = "https://example.com/foo.pdf"
    parent = "forms-page"
    resp = make_pdf_response(url)
    resp.request = Request(url, meta={"parent_page": parent})
    items = list(spider.parse_pdf(resp))

    assert len(items) == 1
    pdf_item = items[0]
    assert isinstance(pdf_item, UscisItem)
    assert pdf_item["url"] == url
    assert pdf_item["content_type"] == "application/pdf"
    assert pdf_item["file_urls"] == [url]
    assert pdf_item["parent_page"] == parent
