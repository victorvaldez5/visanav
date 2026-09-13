import scrapy

from scrapy.loader import ItemLoader
from ..items import UscisItem


class UscisSpider(scrapy.Spider):
    name = "uscis"
    allowed_domains = ["uscis.gov", "uscode.house.gov"]
    start_urls = [
        "https://www.uscis.gov/forms/all-forms",
        # 'https://www.uscis.gov/forms/filing-guidance',
        # 'https://www.uscis.gov/downloading-and-printing-immigration-forms',
        # 'https://www.uscis.gov/topics',
        # 'https://www.uscis.gov/green-card',
        # # 'https://www.uscis.gov/citizenship',
        # 'https://www.uscis.gov/laws',
        # 'https://www.uscis.gov/policy-manual/',
        "https://www.uscis.gov/laws-and-policy/legislation/immigration-and-nationality-act",
        # 'https://www.uscis.gov/tools',
        # add other entry points as needed
    ]

    def parse(self, response, **kwargs):
        # Route to different parsers by URL pattern
        if "/forms/all-forms" in response.url:
            yield from self.parse_all_forms(response)

        if "legislation" in response.url:
            yield from self.parse_legislation_page(response)

    def parse_all_forms(self, response):
        # Target links like <a href="/ar-11" class="link link--form-title">
        form_links = response.css("a.link--form-title::attr(href)").getall()
        for href in form_links:
            yield response.follow(
                href, callback=self.parse_forms_page, meta={"parent_page": response.url}
            )

    def parse_forms_page(self, response, **kwargs):
        # Yield an item for the HTML page itself
        loader = ItemLoader(item=UscisItem(), response=response)
        pdf_links = response.css("article.media a::attr(href)").getall()
        loader.add_value("url", response.url)
        loader.add_value("content_type", "text/html")
        loader.add_value("content", response.css("#page-content").get())
        loader.add_value("files", pdf_links)
        loader.add_value("parent_page", response.meta.get("parent_page"))
        yield loader.load_item()

        # Follow all links; PDFs go to parse_pdf, other pages recurse
        for href in pdf_links:
            if href.endswith(".pdf"):
                yield response.follow(
                    href, callback=self.parse_pdf, meta={"parent_page": response.url}
                )

    def parse_legislation_page(self, response, **kwargs):
        us_code_links = response.css("td > a::attr(href)").getall()
        for href in us_code_links:
            yield response.follow(
                href,
                callback=self.parse_uscode_page,
                meta={"parent_page": response.url},
            )

    def parse_uscode_page(self, response, **kwargs):
        loader = ItemLoader(item=UscisItem(), response=response)
        loader.add_value("url", response.url)
        loader.add_value("content_type", "text/html")
        loader.add_value("content", response.css("#docViewer").get())
        loader.add_value("files", [])
        loader.add_value("parent_page", response.meta.get("parent_page"))
        yield loader.load_item()

    def parse_pdf(self, response):
        loader = ItemLoader(item=UscisItem(), response=response)
        loader.add_value("url", response.url)
        loader.add_value("content_type", "application/pdf")
        loader.add_value("file_urls", [response.url])
        loader.add_value("files", [response.url])
        loader.add_value("parent_page", response.meta.get("parent_page"))
        yield loader.load_item()
