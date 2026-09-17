"""Seed DOJ-recognized organizations from the committed roster fixture.

Reads network/fixtures/ra-orgs.json (the parsed EOIR "Recognized Organizations"
list, with addresses + phones) and upserts each into the flat Organization
model, tagged accreditation="DOJ-recognized". Idempotent by slug. Regenerate the
fixture from the source roster PDFs with the ``build_ra_fixtures`` command.
"""
import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.utils.text import slugify

from network.models import OrganizationType

from ._seed_utils import (
    build_org_index,
    index_org,
    region_code_for,
    resolve_org,
    union_list,
    upsert_address,
)

# The EOIR roster this data is sourced from.
SOURCE_URL = "https://www.justice.gov/eoir/recognition-and-accreditation-program"
HEADER_ROW = "Recognized Organization Address"


def _load_fixture() -> list:
    path = Path(__file__).resolve().parent.parent.parent / "fixtures" / "ra-orgs.json"
    if not path.exists():
        raise CommandError(f"Fixture not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


class Command(BaseCommand):
    help = "Seed DOJ-recognized organizations from ra-orgs.json into Organization."

    def add_arguments(self, parser):
        parser.add_argument(
            "--insert_to_db",
            action="store_true",
            help="Write to the DB (otherwise a dry-run count is printed).",
        )

    def handle(self, *args, **options):
        data = _load_fixture()
        rows = [
            r
            for r in data
            if r.get("organization_name")
            and r["organization_name"] != HEADER_ROW
            and r.get("addresses")
        ]

        if not options["insert_to_db"]:
            self.stdout.write(f"DRY RUN: would seed {len(rows)} DOJ-recognized organizations.")
            return

        created = updated = enriched = 0
        index = build_org_index()
        for row in rows:
            name = row["organization_name"]
            addresses = row.get("addresses", [])
            slug = slugify(name[:50])
            primary = addresses[0]
            region = region_code_for(primary.get("state"))

            phones = []
            for addr in addresses:
                phone = (addr.get("phone_number") or "").strip()
                if phone and phone not in phones:
                    phones.append(phone)

            org, origin = resolve_org(name, slug, region, index)

            if origin == "foreign":
                # Matched a curated (or otherwise richer) row: add only the DOJ
                # trust signals, never clobber its name/type/description/services.
                org.accreditation = org.accreditation or "DOJ-recognized"
                org.phones = union_list(org.phones, phones)
                org.source_url = org.source_url or SOURCE_URL
                org.is_active = True
                org.save()
                enriched += 1
                continue

            # Own or new row: fully (re)populate from the roster.
            org.name = name
            org.organization_type = OrganizationType.COMMUNITY_ORGANIZATION
            org.accreditation = "DOJ-recognized"
            org.fee_model = "low-cost"  # RA orgs may charge only nominal fees.
            org.phones = phones
            org.country = "US"
            org.source_url = SOURCE_URL
            org.is_active = True
            org.address = upsert_address(
                org.address,
                line1=primary.get("line1", ""),
                city=primary.get("city", ""),
                region=primary.get("state"),
                postal_code=primary.get("postal_code", ""),
                address_name=primary.get("address_name") or "Primary Address",
            )
            org.save()
            index_org(index, org, region)

            created += origin == "new"
            updated += origin == "own"

        self.stdout.write(
            self.style.SUCCESS(
                f"RA orgs: {created} created, {updated} updated, {enriched} enriched existing"
            )
        )
