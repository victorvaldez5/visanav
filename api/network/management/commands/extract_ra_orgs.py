import json
import re
from typing import List, Dict

import pdfplumber
from django.core.management import BaseCommand
from django.utils.text import slugify

from locations.models import Subdivision, Address
from network.models import Organization, OrganizationAddress, OrganizationPhoneNumber

PHONE_RE = re.compile(r"(?:\+?1[\s\-\.]?)?\(?\d{3}\)?[\s\-\.]?\d{3}[\s\-\.]?\d{4}")
CSZ_RE = re.compile(r"^\s*(?P<city>.*?),\s*(?P<state>[A-Z]{2})\s+(?P<zip>\d{5}(?:-\d{4})?)\s*$")


def normalize_phone(phone: str) -> str:
    return re.sub(r"\D", "", phone)


def parse_city_state_zip(line: str):
    m = CSZ_RE.match(line.strip())
    if not m:
        return None
    return m.group("city"), m.group("state"), m.group("zip")


def _next_nonempty(lines: List[str], i: int) -> int:
    while i < len(lines) and not lines[i].strip():
        i += 1
    return i


def parse_cell(cell_text: str) -> Dict:
    lines = [ln.rstrip() for ln in cell_text.splitlines()]
    i = _next_nonempty(lines, 0)
    if i >= len(lines):
        raise ValueError("Empty cell")
    organization_name = lines[i].strip()
    i += 1

    addresses = []
    while True:
        i = _next_nonempty(lines, i)
        if i >= len(lines):
            break

        name_line = lines[i].strip()
        i += 1
        i = _next_nonempty(lines, i)
        if i >= len(lines):
            break
        street_line = lines[i].strip()
        i += 1

        i = _next_nonempty(lines, i)
        if i >= len(lines):
            break
        csz_line = lines[i].strip()
        i += 1

        csz = parse_city_state_zip(csz_line)
        if not csz and i < len(lines):
            # Try treating the previous 'csz_line' as a continuation of the street
            maybe = parse_city_state_zip(lines[i].strip())
            if maybe:
                street_line = (street_line + " " + csz_line).strip()
                csz = maybe
                i += 1

        if not csz:
            # Couldn’t validate this block, skip
            continue
        city, state, postal_code = csz

        i = _next_nonempty(lines, i)
        if i >= len(lines):
            break
        phone_line = lines[i].strip()
        i += 1

        if not PHONE_RE.search(phone_line) and i < len(lines):
            # Peek ahead one line for the phone
            j = _next_nonempty(lines, i)
            if j < len(lines) and PHONE_RE.search(lines[j].strip()):
                phone_line = lines[j].strip()
                i = j + 1
            else:
                continue

        phone_number = normalize_phone(phone_line)
        address_name_out = name_line if name_line.lower() != "principal office" else name_line.lower()

        addresses.append({
            "address_name": address_name_out,
            "line1": street_line,
            "city": city,
            "state": state,
            "postal_code": postal_code,
            "phone_number": phone_number
        })

    return {
        "organization_name": organization_name,
        "addresses": addresses
    }


def extract_cells_from_pdf(path):
    cells = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            # Try table extraction first
            tables = page.extract_tables()
            if tables:
                for table in tables:
                    for row in table:
                        # each 'row' is a list of cell strings; if a cell contains a full block, parse it:
                        for cell in row:
                            if cell and cell.strip():
                                cells.append(cell.strip())
            else:
                # Fallback: page text. TODO: split page.extract_text() into cell
                # strings per this PDF's layout, then cells.extend(...).
                pass
    return cells


def parse_pdf_to_json(pdf_path, out_path) -> List[Dict]:
    cell_texts = extract_cells_from_pdf(pdf_path)
    parsed = []
    for cell in cell_texts:
        try:
            parsed.append(parse_cell(cell))
        except Exception:
            # Skip or log problematic cells
            pass
    if out_path is not None:
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(parsed, f, indent=2, ensure_ascii=False)
    return parsed


def insert_to_db(data: List[Dict]):
    for organization in data:
        organization_name = organization.get("organization_name")
        addresses = organization.get("addresses", [])

        if organization_name == 'Recognized Organization Address':
            continue

        if len(addresses) == 0:
            continue

        organization = Organization.objects.filter(slug=slugify(organization_name[:50])).first()
        if organization is None:
            organization, _created = Organization.objects.get_or_create(
                name=organization_name,
                slug=slugify(organization_name[:50]),
                organization_type="community-organization",
                is_active=True
            )

        for (index, address) in enumerate(addresses):
            is_primary = index == 0
            subdivision_code = f"US-{address.get("state")}"
            phone_number = address.get("phone_number")
            address_name = address.get("address_name")
            line1 = address.get("line1")
            city = address.get("city")
            postal_code = address.get("postal_code")
            subdivision = Subdivision.objects.filter(code=subdivision_code).first()

            address = Address.objects.create(
                address_name=address_name,
                line1=line1,
                city=city,
                postal_code=postal_code,
                subdivision=subdivision,
            )
            OrganizationAddress.objects.get_or_create(
                organization=organization,
                address=address,
                is_primary=is_primary,
            )
            org_phone_number = OrganizationPhoneNumber.objects.filter(organization=organization,
                                                                      phone_number=phone_number).first()
            if org_phone_number is None:
                OrganizationPhoneNumber.objects.create(
                    organization=organization,
                    phone_number=phone_number,
                    is_primary=is_primary,
                )


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument("pdf_path", type=str, help="Path to the PDF file")
        parser.add_argument("--out_path", required=False, type=str, default="ra_orgs_clean.json",
                            help="Output JSON path")
        parser.add_argument('--insert_to_db', required=False, type=bool, default=False, help='Insert to DB')

    def handle(self, *args, **options):
        html_path = options["pdf_path"]
        out_path = options["out_path"]
        output = parse_pdf_to_json(html_path, out_path)

        if options["insert_to_db"]:
            insert_to_db(output)
