"""Load curated resource YAML into the flat Organization model.

Reads ``data/countries/<cc>/resources/*.yaml`` (the human-curated directory that
mirrors data/schema/resource.schema.json) and upserts each entry by slug, so the
data maps 1:1 onto the model and re-running is idempotent.
"""
from datetime import date

import yaml
from django.core.management.base import BaseCommand, CommandError

from ._seed_utils import (
    build_org_index,
    index_org,
    region_code_for,
    repo_data_dir,
    resolve_org,
    upsert_address,
)


def _iter_resource_files(cc: str):
    """Yield every resource YAML for a country (national + by-region)."""
    resources_dir = repo_data_dir() / "countries" / cc / "resources"
    if not resources_dir.is_dir():
        raise CommandError(f"No resources directory at {resources_dir}")
    return sorted(resources_dir.rglob("*.yaml"))


def _to_date(value):
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value.strip():
        return date.fromisoformat(value.strip())
    return None


class Command(BaseCommand):
    help = "Load curated resource YAML (data/countries/<cc>/resources/) into Organization."

    def add_arguments(self, parser):
        parser.add_argument("country_code", type=str, help="ISO 3166-1 alpha-2, e.g. 'us'")

    def handle(self, *args, **options):
        cc = options["country_code"].lower()
        created = updated = 0
        index = build_org_index()

        for path in _iter_resource_files(cc):
            entries = yaml.safe_load(path.read_text(encoding="utf-8")) or []
            for entry in entries:
                slug = entry["org_id"]
                contact = entry.get("contact") or {}
                addr = entry.get("address") or {}
                region = region_code_for(addr.get("region"), addr.get("country", cc.upper()))

                # Curated data is authoritative: match by org_id, else adopt a
                # roster-seeded row for the same org, then fully (re)populate it.
                org, origin = resolve_org(entry["name"], slug, region, index)
                org.slug = slug
                org.name = entry["name"]
                org.organization_type = entry["org_type"]
                org.description = entry.get("description", "") or ""
                org.pro_bono = bool(entry.get("pro_bono", False))
                org.fee_model = entry.get("fee_model", "") or ""
                org.accreditation = entry.get("accreditation", "") or ""
                org.services = entry.get("services", []) or []
                org.languages = entry.get("languages", []) or []
                org.websites = contact.get("websites", []) or []
                org.emails = contact.get("emails", []) or []
                org.phones = contact.get("phones", []) or []
                org.country = entry.get("country", cc.upper())
                org.source_url = entry.get("source_url", "") or ""
                org.last_verified = _to_date(entry.get("last_verified"))
                org.is_active = True
                org.address = upsert_address(
                    org.address,
                    line1=addr.get("line1", ""),
                    line2=addr.get("line2", ""),
                    city=addr.get("city", ""),
                    region=addr.get("region"),
                    postal_code=addr.get("postal_code", ""),
                    country=addr.get("country", org.country),
                )
                org.save()
                index_org(index, org, region)

                created += origin == "new"
                updated += origin != "new"

        self.stdout.write(
            self.style.SUCCESS(f"load_resources {cc}: {created} created, {updated} updated")
        )
