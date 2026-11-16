"""Check, against the real bucket, that ingestion can read the crawls' feeds.

    python manage.py r2_check                   # also: just r2-check
    python manage.py r2_check --require-feeds   # also fail when a source has no feed

Uses the same settings and client as `ingest_scrape --from-r2`, and only reads
(the ingest service's credentials are read-only). For each source it lists
raw/items/<source>/ and prints the newest feed. Run it after changing any R2
variable, here or as `python manage.py r2_check` on the visanav-ingest service.
It needs boto3: use the ingest image or `uv sync --group ingest`.
"""
from tempfile import TemporaryDirectory

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.management.base import BaseCommand, CommandError

from knowledge.feed_store import R2Feeds
from knowledge.scrape_utils import SOURCES


class Command(BaseCommand):
    help = "List each scrape source's feeds in R2 and report the newest one."

    def add_arguments(self, parser):
        parser.add_argument(
            "--require-feeds", action="store_true",
            help="Fail when a source has no feed at all (expected once every crawl has run).",
        )

    def handle(self, *args, **options):
        with TemporaryDirectory() as workdir:
            try:
                store = R2Feeds.from_settings(workdir)
            except ImproperlyConfigured as exc:
                raise CommandError(f"R2 is misconfigured: {exc}") from exc
            self.stdout.write(f"bucket: {settings.R2_BUCKET}")
            empty = []
            for source in SOURCES:
                try:
                    newest = store.newest(source)
                except Exception as exc:  # botocore's errors carry the R2 code and message
                    raise CommandError(f"{source}: cannot list {R2Feeds.PREFIX}{source}/: {exc}") from exc
                if newest is None:
                    empty.append(source)
                self.stdout.write(f"{source}: {newest or 'no feeds'}")
        if empty and options["require_feeds"]:
            raise CommandError(f"no feeds for {', '.join(empty)}")
        self.stdout.write(self.style.SUCCESS("R2 is reachable"))
