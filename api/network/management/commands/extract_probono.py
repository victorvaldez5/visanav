import json
import re
from collections import OrderedDict
from pathlib import Path
from typing import List, Dict

from bs4 import BeautifulSoup
from django.core.management.base import BaseCommand, CommandError
from django.utils.text import slugify

from locations.models import Subdivision, Address
from network.models import Organization, OrganizationAddress, OrganizationWebsites, OrganizationPhoneNumber, \
    OrganizationEmail

EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)
PHONE_RE = re.compile(
    r"(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}(?:\s*(?:x|ext\.?|#)\s*\d+)?",
    re.IGNORECASE,
)
URL_RE = re.compile(r"(?:https?://|www\.)[^\s/$.?#].[^\s]*", re.IGNORECASE)
CITY_STATE_ZIP_RE = re.compile(r"(.+?),\s*([A-Z]{2})\s+(\d{5}(?:-\d{4})?)\b")


def detect_org_type(text: str):
    # Per spec: '**' => referral service ; '*' => non-profit
    if "**" in text:
        return "referral service"
    if "*" in text:
        return "non-profit"
    return None


def extract_fields(block_text: str):
    lines = [re.sub(r"\s+", " ", ln).strip() for ln in block_text.splitlines()]
    lines = [ln for ln in lines if ln]
    full_text = "\n".join(lines)

    org_type = detect_org_type(full_text)

    org_name = None
    for ln in lines:
        candidate = re.sub(r"^[\*\-\u2022\•\s]+", "", ln.strip())
        if not EMAIL_RE.search(candidate) and not PHONE_RE.search(candidate) and not URL_RE.search(candidate):
            org_name = candidate
            break

    emails = list(OrderedDict.fromkeys(EMAIL_RE.findall(full_text)))
    phones = list(OrderedDict.fromkeys(PHONE_RE.findall(full_text)))
    websites = list(OrderedDict.fromkeys(URL_RE.findall(full_text)))

    city = state = zipcode = None
    address = None
    csz_idx = None
    for i, ln in enumerate(lines):
        m = CITY_STATE_ZIP_RE.search(ln)
        if m:
            city, state, zipcode = m.group(1).strip(), m.group(2), m.group(3)
            csz_idx = i
            break

    if csz_idx is not None and csz_idx - 1 >= 0:
        street_line = lines[csz_idx - 1]
        if not EMAIL_RE.search(street_line) and not PHONE_RE.search(street_line) and not URL_RE.search(street_line):
            address = street_line

    used_lines = set(filter(None, [org_name, address, lines[csz_idx] if csz_idx is not None else None]))
    for ln in list(lines):
        if EMAIL_RE.search(ln) or PHONE_RE.search(ln) or URL_RE.search(ln):
            used_lines.add(ln)
    notes = [ln for ln in lines if ln not in used_lines]

    if org_name:
        org_name = org_name.replace("**", "").replace("*", "").strip(" -•\u2022")

    return {
        "organization_name": org_name,
        "organization_type": org_type,
        "address": address,
        "city": city,
        "state": state,
        "zip_code": zipcode,
        "email_addresses": emails,
        "telephone_numbers": phones,
        "websites": websites,
        "notes": notes,
    }


def safe_first(seq):
    try:
        return next((x for x in seq if x), None)
    except Exception:
        return None


def key_fn(r: dict):
    name = (r.get("organization_name") or "").lower().strip()
    city = (r.get("city") or "").lower().strip()
    state = (r.get("state") or "").upper().strip()
    email = safe_first(r.get("email_addresses") or [])
    site = safe_first(r.get("websites") or [])
    phone = safe_first(r.get("telephone_numbers") or [])
    return name, city, state, email, site, phone


def parse_json(html_path: Path) -> List[Dict]:
    soup = BeautifulSoup(html_path.read_text(encoding="utf-8", errors="ignore"), "html.parser")
    tds = soup.find_all("td")

    rows = []
    for td in tds:
        # noinspection PyArgumentList
        txt = td.get_text(separator="\n", strip=True)
        if txt:
            rows.append(extract_fields(txt))

    rows = [r for r in rows if r.get("organization_type")]

    seen = set()
    deduped = []
    for r in rows:
        k = key_fn(r)
        if k in seen:
            continue
        seen.add(k)
        deduped.append(r)
    return deduped


class Command(BaseCommand):
    help = "Extract & clean pro bono legal service providers from an HTML table into JSON and writes to file or database"

    def handle_write(self, data: List[Dict], out_path: Path):
        out_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        self.stdout.write(self.style.SUCCESS(f"Wrote {len(data)} records to {out_path}"))

    def handle_db(self, data: List[Dict]):
        for org in data:
            telephone_numbers = org.get('telephone_numbers', [])
            emails = org.get('email_addresses', [])
            websites = org.get('websites', [])
            notes = org.get('notes', [])
            address_line = org.get('address', '')
            city = org.get('city', '')
            state = org.get('state', '')
            zip_code = org.get('zip_code', '')
            org_name = org.get('organization_name', '')
            org_type = slugify(org.get('organization_type', ''))
            org_slug = slugify(org_name[:50])

            organization = Organization.objects.filter(slug=org_slug).first()
            if organization is None:
                organization = Organization.objects.create(
                    name=org_name,
                    slug=org_slug,
                    organization_type=org_type,
                    notes=notes,
                    is_active=True,
                    has_pro_bono=True,
                )
            else:
                organization.organization_type = org_type
                organization.notes = notes
                organization.has_pro_bono = True
                organization.save()
                self.stdout.write(self.style.SUCCESS(f"Updated {org_name}"))

            for website in websites:
                OrganizationWebsites.objects.get_or_create(organization=organization, website=website)
            for phone_number in telephone_numbers:
                OrganizationPhoneNumber.objects.get_or_create(organization=organization, phone_number=phone_number)

            for email in emails:
                OrganizationEmail.objects.get_or_create(organization=organization, email=email)

            subdivision = Subdivision.objects.filter(code=f"US-{state}").first()
            if subdivision is None:
                self.stdout.write(self.style.WARNING(f"Skipping {org_name} address due to missing subdivision"))
                continue

            existing_address = organization.addresses.filter(address__line1=address_line, address__city=city,
                                                             address__postal_code=zip_code)
            if not existing_address.exists():
                address = Address.objects.filter(line1=address_line, city=city, postal_code=zip_code,
                                                 subdivision=subdivision).first()
                if address is None:
                    address = Address.objects.get(
                        line1=address_line,
                        city=city,
                        subdivision=subdivision,
                        postal_code=zip_code,
                    )

                OrganizationAddress.objects.create(organization=organization, address=address, is_primary=True)

    def add_arguments(self, parser):
        parser.add_argument("html_path", type=str, help="Path to the HTML file")
        parser.add_argument("--out", type=str, required=False, default="probono_clean.json", help="Output JSON path")
        parser.add_argument('--insert_to_db', required=False, type=bool, default=False, help='Insert to DB')

    def handle(self, *args, **opts):
        html_path = Path('network', 'fixtures', opts["html_path"])
        out_path = Path('network', 'fixtures', opts["out"])

        if not html_path.exists():
            raise CommandError(f"Input file not found: {html_path}")
        organization_data = parse_json(html_path)
        if out_path:
            self.handle_write(organization_data, out_path)

        if opts["insert_to_db"]:
            self.handle_db(organization_data)
