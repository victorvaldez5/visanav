import logging

from scrapy.commands.crawl import Command as ScrapyCrawlCommand
from scrapy.exceptions import UsageError

from ..health import crawl_problems

logger = logging.getLogger(__name__)


class Command(ScrapyCrawlCommand):
    """`scrapy crawl <spider>`, but a crawl that cannot be trusted exits non-zero.

    Replaces Scrapy's own `crawl` (via COMMANDS_MODULE), so every entry point
    (Railway, compose, the manual workflow, `just crawl`) gets the check without
    changing its command line.
    """

    def run(self, args, opts):
        if len(args) != 1:
            raise UsageError("give exactly one spider to crawl")

        crawler = self._create_crawler(args[0])
        self.crawler_process.crawl(crawler, **opts.spargs)
        self.crawler_process.start()
        if self.crawler_process.bootstrap_failed:
            self.exitcode = 1
            return

        problems = crawl_problems(crawler.stats.get_stats(), crawler.spider)
        for problem in problems:
            logger.error("crawl of %s failed its health check: %s", args[0], problem)
        if problems:
            self.exitcode = 1
