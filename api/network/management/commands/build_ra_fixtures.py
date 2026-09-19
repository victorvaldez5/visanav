"""Parse the EOIR R&A rosters (PDF) into the committed JSON seed fixtures.

This is an offline, dev-time step: it turns the source PDFs the DOJ publishes into
the ``ra-orgs.json`` / ``ra-reps.json`` fixtures that the ``extract_ra_orgs`` and
``extract_ra_reps`` seed commands read at boot. Re-run it only when the DOJ
publishes fresh rosters; the committed JSON is the source of truth for seeding.

Text is always *extracted first* (via pdfplumber's word geometry) and only the
extracted words are analysed — the raw PDF is never interpreted directly. The
rosters are fixed-column tables whose cells wrap over several lines, so we cluster
words into rows by their y-position and into columns by their x-position (both are
stable across pages, unlike a flat ``pdftotext`` dump).

Sources (drop the PDFs in ``data/raw/``):
  * ``recognized_org_..._by_state_and_city*.pdf`` -> ra-orgs.json  (orgs + addresses + phones)
  * ``raroster-reps.pdf``                          -> ra-reps.json   (accredited representatives)

Usage (inside the api container, which has pdfplumber + the mounted data/):
    python manage.py build_ra_fixtures            # parse the PDFs already in data/raw/
    python manage.py build_ra_fixtures --download  # fetch the latest first, then parse
"""
import json
import logging
import re
from datetime import date
from pathlib import Path

import pdfplumber
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

from ._seed_utils import repo_data_dir

# pdfminer logs every parsed object at DEBUG; keep the roster parse quiet.
logging.getLogger("pdfminer").setLevel(logging.WARNING)

FIXTURES_DIR = Path(__file__).resolve().parent.parent.parent / "fixtures"

DATE_RE = re.compile(r"^(\d{2})/(\d{2})/(\d{2})(\*?)$")
# The ZIP is sometimes rendered malformed: ZIP+4 without its hyphen ("482102416")
# or a low ZIP with its leading zero dropped ("8611" for Trenton). Capture 4-9
# digits and normalise below.
CITY_STATE_ZIP_RE = re.compile(r"^(.*),\s+([A-Z]{2})\s+(\d{4,9}(?:-\d{4})?)$")
PHONE_RE = re.compile(r"^\(?\d{3}\)?[\s.\-]*\d{3}[\s.\-]*\d{4}$")


def _norm_zip(z: str) -> str:
    if "-" in z:
        return z
    if len(z) == 4:
        return z.zfill(5)  # dropped leading zero (NJ/RI/VT…)
    if len(z) >= 9:
        return f"{z[:5]}-{z[5:9]}"  # ZIP+4 with the hyphen dropped
    return z
LAST_UPDATED_RE = re.compile(r"Report Last Updated on:\s*(\d{2})/(\d{2})/(\d{2})")

# US states + DC + territories, so a centered ALL-CAPS section header can be told
# apart from a wrapped org name.
US_STATES = {
    "ALABAMA", "ALASKA", "ARIZONA", "ARKANSAS", "CALIFORNIA", "COLORADO",
    "CONNECTICUT", "DELAWARE", "DISTRICT OF COLUMBIA", "FLORIDA", "GEORGIA",
    "GUAM", "HAWAII", "IDAHO", "ILLINOIS", "INDIANA", "IOWA", "KANSAS",
    "KENTUCKY", "LOUISIANA", "MAINE", "MARYLAND", "MASSACHUSETTS", "MICHIGAN",
    "MINNESOTA", "MISSISSIPPI", "MISSOURI", "MONTANA", "NEBRASKA", "NEVADA",
    "NEW HAMPSHIRE", "NEW JERSEY", "NEW MEXICO", "NEW YORK", "NORTH CAROLINA",
    "NORTH DAKOTA", "OHIO", "OKLAHOMA", "OREGON", "PENNSYLVANIA", "PUERTO RICO",
    "RHODE ISLAND", "SOUTH CAROLINA", "SOUTH DAKOTA", "TENNESSEE", "TEXAS",
    "UTAH", "VERMONT", "VIRGIN ISLANDS", "VIRGINIA", "WASHINGTON",
    "WEST VIRGINIA", "WISCONSIN", "WYOMING",
}


def _iso(mm: str, dd: str, yy: str) -> str:
    """MM/DD/YY -> ISO date. Two-digit years pivot at 70 (roster spans 1976-2032)."""
    year = 2000 + int(yy) if int(yy) < 70 else 1900 + int(yy)
    return date(year, int(mm), int(dd)).isoformat()


def _cluster_lines(words, y_tol: float = 3.0):
    """Group extracted words into visual rows, each sorted left-to-right.

    pdfplumber yields one dict per word with ``x0``/``top``; a roster row is every
    word sharing a baseline (within ``y_tol`` points).
    """
    rows: dict[int, list] = {}
    for w in words:
        key = round(w["top"] / y_tol)
        rows.setdefault(key, []).append(w)
    return [sorted(rows[k], key=lambda w: w["x0"]) for k in sorted(rows)]


def _text_at(row, lo: float, hi: float) -> str:
    """Join the words whose left edge falls in the ``[lo, hi)`` column band."""
    return " ".join(w["text"] for w in row if lo <= w["x0"] < hi).strip()


def _iter_page_rows(pdf):
    for page in pdf.pages:
        words = page.extract_words(
            use_text_flow=False, keep_blank_chars=False, x_tolerance=1.5, y_tolerance=2
        )
        for row in _cluster_lines(words):
            yield row


def _roster_last_updated(pdf) -> str:
    text = pdf.pages[0].extract_text() or ""
    m = LAST_UPDATED_RE.search(text)
    return _iso(*m.groups()) if m else ""


# --- by-state/city roster -> orgs + addresses -----------------------------
# Column x-bands (points): left column (org name / address block) < 340; the
# recognition dates sit at ~362/434/506.
ORG_LEFT_HI = 340.0
ORG_DATE_LO = 345.0
# The first line of an address block is its office label; matching one lets us
# tell a wrapped-org-name continuation apart from the start of the address block.
OFFICE_LABEL_RE = re.compile(
    r"\b(office|extension|principal|sub-?office|satellite|branch)\b", re.IGNORECASE
)


def _new_office(label: str) -> dict:
    return {"address_name": label, "line1": "", "city": "",
            "state": "", "postal_code": "", "phone_number": ""}


def parse_orgs(rows) -> list[dict]:
    """Parse the 'by State and City' roster into ``{organization_name, addresses[]}``.

    An org can appear under several cities (one office each); those collapse into a
    single record whose ``addresses`` list gathers every office. Each org's block is
    ``<header w/ dates> [<office label> <street…> <City, ST ZIP> <phone?>]…`` — the
    office label is always the first line of an address block, so we run a small
    state machine over the left column rather than guessing which lines are labels.

    The ``by_state_and_city`` PDF is a combined export: the geographic roster is
    followed by a second, org-by-rep section (its header says "Accreditation
    Expiration"). We stop at that boundary.
    """
    orgs: dict[str, dict] = {}
    order: list[str] = []
    current = None  # org dict currently being filled
    office = None  # address dict currently being filled
    mode = "label"  # label -> street -> expect_phone

    def flush_office():
        nonlocal office
        if office and current is not None and (office.get("line1") or office.get("city")):
            current["addresses"].append(office)
        office = None

    for row in rows:
        left = _text_at(row, 0, ORG_LEFT_HI)
        if not left:
            continue  # right-side "(Pending Renewal)" status fragments, etc.
        # The second (org-by-rep) section's header lives in the right-hand columns.
        if "Accreditation Expiration" in " ".join(w["text"] for w in row):
            break

        has_date = any(DATE_RE.match(w["text"]) and w["x0"] >= ORG_DATE_LO for w in row)

        # Centered section header (state / city): no true left-margin word.
        if min(w["x0"] for w in row) > 200 and not has_date:
            continue
        # Column header rows repeat on every page.
        if not has_date and (left.startswith("Recognized") or left.startswith("Organization")):
            continue

        if has_date:
            # New org header: the name is the left text (dates sit on the right).
            # A long name may wrap onto the next lines, before the first office
            # label — "name" appends those; "reskip" ignores them when the org was
            # already seen (in another city) and its name is already captured.
            flush_office()
            key = left.lower()
            if key not in orgs:
                orgs[key] = {"organization_name": left, "addresses": []}
                order.append(key)
                mode = "name"
            else:
                mode = "reskip"
            current = orgs[key]
            continue

        if current is None:
            continue

        if mode == "street":
            m = CITY_STATE_ZIP_RE.match(left)
            if m:
                head, state, zip_raw = m.group(1).strip(), m.group(2), m.group(3)
                # A leading street number means the street collapsed onto this
                # line; peel it into line1, leaving the trailing word as the city.
                if re.match(r"^\d", head) and " " in head:
                    street, _, city = head.rpartition(" ")
                    office["line1"] = f"{office['line1']} {street}".strip() if office["line1"] else street
                else:
                    city = head
                office["city"], office["state"], office["postal_code"] = (
                    city, state, _norm_zip(zip_raw)
                )
                mode = "expect_phone"
                continue
            office["line1"] = f"{office['line1']} {left}".strip() if office["line1"] else left
            continue

        if mode == "expect_phone":
            # A phone closes the current address; then hunt for the next office.
            if PHONE_RE.match(left):
                office["phone_number"] = left
                flush_office()
                mode = "reskip"
                continue
            flush_office()
            mode = "reskip"
            # fall through: this line may already be the next office label.

        # mode in ("name", "reskip"): skip lines until the next office label. Its
        # first line always carries an office keyword, so this also skips EOIR's
        # habit of repeating the org name before each extra office, plus any
        # wrapped-name continuation. In "name" mode those continuations extend the
        # (possibly wrapped) organization name.
        if OFFICE_LABEL_RE.search(left):
            office = _new_office(left)
            mode = "street"
        elif mode == "name":
            current["organization_name"] += f" {left}"
        continue

    flush_office()

    # Put the principal office first so downstream seeding treats it as primary.
    for org in orgs.values():
        org["addresses"].sort(key=lambda a: 0 if "principal" in a["address_name"].lower() else 1)
    return [orgs[k] for k in order]


# --- accredited-representatives roster -> reps ----------------------------
# Column x-bands (points): rep name < 120; accreditation-expiration 120-185;
# rep status 185-265; recognized organization 265-388; org dates >= 388.
REP_NAME_HI = 120.0
REP_EXP_LO, REP_EXP_HI = 120.0, 185.0
REP_STATUS_LO, REP_STATUS_HI = 185.0, 265.0
REP_ORG_LO, REP_ORG_HI = 265.0, 388.0

DHS_ONLY_RE = re.compile(r"\(\s*DHS\s+only\s*\)", re.IGNORECASE)

# Header / divider furniture that repeats atop every page. A rep whose name or
# organization wraps across a page break would otherwise swallow it (e.g. the
# centered "F" divider and the "Recognized Organization" header). None of these
# words occur in real rep or organization names.
_FURNITURE_KEYWORDS = (
    "expiration", "accreditation", "recognized organization",
    "accredited representative", "representative status", "report last updated",
    "number of accredited", "search by alphabetical", "asterisk", "disclaimer",
)


def _is_furniture(full: str) -> bool:
    if len(full) == 1 and full.isalpha():
        return True  # centered A-Z alphabetical divider
    low = full.lower()
    return any(kw in low for kw in _FURNITURE_KEYWORDS)


def parse_reps(rows, last_verified: str) -> list[dict]:
    """Parse the accredited-representatives roster into rep records.

    Each rep's row starts on the line carrying its accreditation-expiration date
    (in the second column); the rep-name and organization cells then wrap over the
    following lines until the next date appears.
    """
    reps: list[dict] = []
    current = None

    def finalize():
        if current is None:
            return
        raw_name = re.sub(r"\s+", " ", current["_name"]).strip()
        dhs_only = bool(DHS_ONLY_RE.search(raw_name))
        name = DHS_ONLY_RE.sub("", raw_name).strip().rstrip(",").strip()
        org = re.sub(r"\s+", " ", current["_org"]).strip()
        if name:
            reps.append({
                "name": name,
                "organization_name": org,
                "accreditation_expiration": current["exp"],
                "dhs_only": dhs_only,
                "status": current["status"],
                "last_verified": last_verified,
            })

    for row in rows:
        full = " ".join(w["text"] for w in row).strip()
        # raroster-reps.pdf is a combined export: after the last rep comes an
        # org-address section headed "Recognized Organization Address". Stop there,
        # or its rows bleed into the final record.
        if "Recognized Organization Address" in full:
            break
        if _is_furniture(full):
            continue
        name_frag = _text_at(row, 0, REP_NAME_HI)
        org_frag = _text_at(row, REP_ORG_LO, REP_ORG_HI)

        # The accreditation-expiration date marks the start of a new rep.
        exp_word = next(
            (w["text"] for w in row if REP_EXP_LO <= w["x0"] < REP_EXP_HI and DATE_RE.match(w["text"])),
            None,
        )
        if exp_word:
            finalize()
            # Skip the two column-header lines ("Accredited"/"Representative").
            m = DATE_RE.match(exp_word)
            status = _text_at(row, REP_STATUS_LO, REP_STATUS_HI)
            current = {
                "_name": name_frag,
                "_org": org_frag,
                "exp": _iso(m.group(1), m.group(2), m.group(3)),
                "status": status or "Active",
            }
            continue

        if current is None:
            continue
        # Continuation line: extend the wrapped name / organization cells.
        if name_frag:
            current["_name"] += " " + name_frag
        if org_frag:
            current["_org"] += " " + org_frag

    finalize()
    return reps


def _find_pdf(raw_dir: Path, *patterns: str) -> Path:
    for pattern in patterns:
        matches = sorted(raw_dir.glob(pattern))
        if matches:
            return matches[0]
    raise CommandError(
        f"No PDF matching {patterns} in {raw_dir}. Drop the EOIR roster PDFs there."
    )


class Command(BaseCommand):
    help = "Parse the EOIR R&A roster PDFs in data/raw/ into ra-orgs.json + ra-reps.json."

    def add_arguments(self, parser):
        parser.add_argument(
            "--raw-dir",
            default=None,
            help="Directory holding the roster PDFs (default: <repo>/data/raw).",
        )
        parser.add_argument(
            "--download",
            action="store_true",
            help="Fetch the latest roster PDFs (download_ra_rosters) before parsing.",
        )

    def handle(self, *args, **options):
        raw_dir = Path(options["raw_dir"]) if options["raw_dir"] else repo_data_dir() / "raw"
        if options["download"]:
            call_command("download_ra_rosters", "--raw-dir", str(raw_dir))
        if not raw_dir.is_dir():
            raise CommandError(f"Raw PDF directory not found: {raw_dir}")

        orgs_pdf = _find_pdf(raw_dir, "*by_state_and_city*.pdf", "*state_and_city*.pdf")
        reps_pdf = _find_pdf(raw_dir, "raroster-reps.pdf", "*accredited*rep*roster*.pdf")

        with pdfplumber.open(orgs_pdf) as pdf:
            orgs = parse_orgs(_iter_page_rows(pdf))
        with pdfplumber.open(reps_pdf) as pdf:
            last_verified = _roster_last_updated(pdf)
            reps = parse_reps(_iter_page_rows(pdf), last_verified)

        addresses = sum(len(o["addresses"]) for o in orgs)
        FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
        (FIXTURES_DIR / "ra-orgs.json").write_text(
            json.dumps(orgs, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        (FIXTURES_DIR / "ra-reps.json").write_text(
            json.dumps(reps, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"ra-orgs.json: {len(orgs)} organizations, {addresses} addresses\n"
                f"ra-reps.json: {len(reps)} representatives (roster updated {last_verified})"
            )
        )
