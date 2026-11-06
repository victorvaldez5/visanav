"""Export the legal-help directory as Open Referral HSDS 3.1 JSON.

Writes every active organization for a country as one HSDS paginated list
(see network/hsds.py and docs/hsds-mapping.md), to a file or stdout.
"""
import json
from pathlib import Path

from django.core.management.base import BaseCommand

from network.hsds import export_organizations
from network.models import Organization


class Command(BaseCommand):
    help = "Export active organizations as Open Referral HSDS 3.1 JSON."

    def add_arguments(self, parser):
        parser.add_argument(
            "--country", default="us", help="ISO 3166-1 alpha-2 country to export (default: us)."
        )
        parser.add_argument("--output", help="File to write. Defaults to stdout.")

    def handle(self, *args, **options):
        queryset = Organization.objects.filter(
            is_active=True, country=options["country"].upper()
        )
        document = json.dumps(export_organizations(queryset), ensure_ascii=False, indent=2)
        if options["output"]:
            path = Path(options["output"])
            path.write_text(document + "\n", encoding="utf-8")
            self.stderr.write(f"Wrote {queryset.count()} organizations to {path}")
        else:
            self.stdout.write(document)
