"""Seed pro-bono legal-service providers from the committed roster fixture.

Reads network/fixtures/probono_clean.json (the parsed EOIR "List of Pro Bono
Legal Service Providers") and upserts each into the flat Organization model with
pro_bono=True. Idempotent by slug. The JSON is the source of truth.
"""
import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.utils.text import slugify

from network.models import OrganizationType

from ._seed_utils import (
    build_org_index,
    index_org,
    normalize_url,
    region_code_for,
    resolve_org,
    union_list,
    upsert_address,
)

# The EOIR roster this data is sourced from.
SOURCE_URL = "https://www.justice.gov/eoir/list-pro-bono-legal-service-providers"

# The fixture's free-text org types map onto the enum's slugs.
ORG_TYPE_CHOICES = set(OrganizationType.values)


def _load_fixture() -> list:
    path = Path(__file__).resolve().parent.parent.parent / "fixtures" / "probono_clean.json"
    if not path.exists():
        raise CommandError(f"Fixture not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _org_type(raw: str) -> str:
    slug = slugify(raw or "")
    return slug if slug in ORG_TYPE_CHOICES else OrganizationType.COMMUNITY_ORGANIZATION


class Command(BaseCommand):
    help = "Seed pro-bono legal-service providers from probono_clean.json into Organization."

    def add_arguments(self, parser):
        parser.add_argument(
            "--insert_to_db",
            action="store_true",
            help="Write to the DB (otherwise a dry-run count is printed).",
        )

    def handle(self, *args, **options):
        data = [r for r in _load_fixture() if r.get("organization_name")]

        if not options["insert_to_db"]:
            self.stdout.write(f"DRY RUN: would seed {len(data)} pro-bono organizations.")
            return

        created = updated = enriched = 0
        index = build_org_index()
        for row in data:
            name = row["organization_name"]
            slug = slugify(name[:50])
            region = region_code_for(row.get("state"))
            emails = row.get("email_addresses", []) or []
            phones = row.get("telephone_numbers", []) or []
            websites = [normalize_url(w) for w in row.get("websites", []) if w]
            notes = " ".join(row.get("notes") or []).strip()

            org, origin = resolve_org(name, slug, region, index)

            if origin == "foreign":
                # Matched a curated (or otherwise richer) row: flag it pro-bono
                # and add contacts, but keep its own fee_model/description/type.
                org.pro_bono = True
                org.fee_model = org.fee_model or "free"
                org.emails = union_list(org.emails, emails)
                org.phones = union_list(org.phones, phones)
                org.websites = union_list(org.websites, websites)
                org.description = org.description or notes
                org.source_url = org.source_url or SOURCE_URL
                org.is_active = True
                org.save()
                enriched += 1
                continue

            # Own or new row: fully (re)populate from the roster.
            org.name = name
            org.organization_type = _org_type(row.get("organization_type"))
            org.description = notes
            org.pro_bono = True
            org.fee_model = "free"
            org.emails = emails
            org.phones = phones
            org.websites = websites
            org.country = "US"
            org.source_url = SOURCE_URL
            org.is_active = True
            org.address = upsert_address(
                org.address,
                line1=row.get("address", "") or "",
                city=row.get("city", "") or "",
                region=row.get("state"),
                postal_code=row.get("zip_code", "") or "",
            )
            org.save()
            index_org(index, org, region)

            created += origin == "new"
            updated += origin == "own"

        self.stdout.write(
            self.style.SUCCESS(
                f"Pro-bono orgs: {created} created, {updated} updated, {enriched} enriched existing"
            )
        )
