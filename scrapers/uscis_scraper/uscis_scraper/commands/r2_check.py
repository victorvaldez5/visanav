from scrapy.commands import ScrapyCommand
from scrapy.exceptions import UsageError

from ..r2 import R2ConfigError, build_s3_client, check_settings, newest_feed, probe


class Command(ScrapyCommand):
    """`scrapy r2_check`: prove, against the real bucket, that crawls can write to R2.

    Writes, reads back and deletes one object under raw/healthcheck/, then lists
    each spider's feeds under raw/items/<spider>/. Exits non-zero on any failure,
    or (with --require-feeds) when a spider has no feed yet. Run it after changing
    any R2 variable: `just r2-check` here, or `scrapy r2_check` on a scraper service.
    """

    requires_project = True

    def short_desc(self):
        return "Check that the configured R2 bucket can be written, read and listed"

    def add_options(self, parser):
        super().add_options(parser)
        parser.add_argument(
            "--require-feeds", action="store_true",
            help="also fail when a spider has no feed in R2",
        )

    def process_options(self, args, opts):
        super().process_options(args, opts)
        # settings.py sets LOG_STDOUT, which would turn this report into log lines;
        # the project's settings outrank a command's defaults, so set it as -s would.
        self.settings.set("LOG_STDOUT", False, priority="cmdline")
        self.settings.set("LOG_LEVEL", "WARNING", priority="cmdline")

    def run(self, args, opts):
        if args:
            raise UsageError("r2_check takes no arguments")
        try:
            check_settings(self.settings)
        except R2ConfigError as exc:
            print(f"R2 is misconfigured: {exc}")
            self.exitcode = 1
            return

        bucket = self.settings.get("R2_BUCKET")
        client = build_s3_client(self.settings)
        print(f"bucket: {bucket}")
        try:
            key = probe(client, bucket)
            print(f"write, read and delete: ok ({key})")
            empty = []
            for spider in sorted(self.crawler_process.spider_loader.list()):
                newest = newest_feed(client, bucket, spider)
                if newest is None:
                    empty.append(spider)
                print(f"{spider}: {newest or 'no feeds'}")
        except Exception as exc:  # botocore's errors carry the R2 code and message
            print(f"R2 check failed: {exc}")
            self.exitcode = 1
            return
        if empty and opts.require_feeds:
            print(f"no feeds for {', '.join(empty)}")
            self.exitcode = 1
            return
        print("R2 is reachable")
