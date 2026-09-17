"""Seed DOJ-accredited representatives from the committed roster fixture.

Reads network/fixtures/ra-reps.json (the parsed EOIR "Accredited Representatives"
roster) and upserts each into the Representative model, linking to the
Organization it is accredited through by normalized name. Idempotent by
(name, organization). The JSON is the source of truth; regenerate it from the
source PDFs with ``build_ra_fixtures``.

Run after the org seeders (load_resources / extract_ra_orgs), so reps can link to
existing organizations. A rep whose organization is not in the directory (e.g. a
recognized org with no geographic listing) is still seeded, unlinked.
"""
import json
from datetime import date
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from network.models import ProviderType, Representative

from ._seed_utils import normalize_name

# The EOIR roster this data is sourced from.
SOURCE_URL = "https://www.justice.gov/eoir/recognition-and-accreditation-program"


def _load_fixture() -> list:
    path = Path(__file__).resolve().parent.parent.parent / "fixtures" / "ra-reps.json"
    if not path.exists():
        raise CommandError(f"Fixture not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _to_date(value):
    if isinstance(value, str) and value.strip():
        return date.fromisoformat(value.strip())
    return None


def _org_index() -> dict:
    """Map normalized org name -> Organization id (reps carry no region)."""
    from network.models import Organization

    index = {}
    for org in Organization.objects.all():
        index.setdefault(normalize_name(org.name), org.id)
    return index


class Command(BaseCommand):
    help = "Seed DOJ-accredited representatives from ra-reps.json into Representative."

    def add_arguments(self, parser):
        parser.add_argument(
            "--insert_to_db",
            action="store_true",
            help="Write to the DB (otherwise a dry-run count is printed).",
        )

    def handle(self, *args, **options):
        rows = [r for r in _load_fixture() if r.get("name")]

        if not options["insert_to_db"]:
            self.stdout.write(f"DRY RUN: would seed {len(rows)} accredited representatives.")
            return

        org_index = _org_index()
        created = updated = unlinked = 0
        for row in rows:
            name = row["name"]
            org_id = org_index.get(normalize_name(row.get("organization_name", "")))
            if org_id is None:
                unlinked += 1

            defaults = {
                "provider_type": ProviderType.DOJ_ACCREDITED_REP,
                "dhs_only": bool(row.get("dhs_only")),
                "accreditation_expiration": _to_date(row.get("accreditation_expiration")),
                "is_active": row.get("status", "Active") == "Active",
                "source_url": SOURCE_URL,
                "last_verified": _to_date(row.get("last_verified")),
            }
            _, was_created = Representative.objects.update_or_create(
                name=name, organization_id=org_id, defaults=defaults
            )
            created += was_created
            updated += not was_created

        self.stdout.write(
            self.style.SUCCESS(
                f"RA reps: {created} created, {updated} updated "
                f"({unlinked} not linked to a directory organization)"
            )
        )
