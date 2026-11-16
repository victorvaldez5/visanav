import logging

from scrapy.commands.crawl import Command as ScrapyCrawlCommand
from scrapy.exceptions import UsageError

from ..health import crawl_problems
from ..r2 import R2ConfigError, check_settings

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
        # Scrapy's own S3 feed export builds its client from these settings too,
        # so a bad endpoint is caught here, before a crawl spends hours on it.
        if not self.settings.getbool("LOCAL_TEST"):
            try:
                check_settings(self.settings)
            except R2ConfigError as exc:
                logger.error("crawl of %s refused: %s", args[0], exc)
                self.exitcode = 1
                return

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
