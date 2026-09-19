"""Download the latest EOIR R&A roster PDFs into data/raw/.

Fetches the DOJ EOIR "Recognition & Accreditation Roster Reports" page and saves
the two rosters ``build_ra_fixtures`` parses, under the filenames it looks for:

  * "Organizations and Representatives, Listed by State" -> the geographic roster
    (recognized organizations with their office addresses)
  * "Accredited Representatives List"                    -> the reps roster

Run this, then ``build_ra_fixtures``, to refresh the committed JSON fixtures from
the current source (or ``build_ra_fixtures --download`` to do both). The links are
matched by their visible text, so a report's media id changing does not break it.
"""
import html
import re
import urllib.request
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from ._seed_utils import repo_data_dir

ROSTER_PAGE = "https://www.justice.gov/eoir/recognition-accreditation-roster-reports"
BASE_URL = "https://www.justice.gov"
USER_AGENT = "Mozilla/5.0 (compatible; VisaNav roster fetch; +https://visanav.org)"

# (destination filename, predicate over the anchor's lowercased text). The
# filenames match the globs build_ra_fixtures._find_pdf resolves.
TARGETS = [
    (
        "recognized_org_and_accredited_rep_roster_by_state_and_city.pdf",
        lambda t: "state" in t and "represent" in t,  # "…Representatives, Listed by State"
    ),
    (
        "raroster-reps.pdf",
        lambda t: "accredited representatives" in t and "state" not in t,
    ),
]

_ANCHOR_RE = re.compile(r"<a\b([^>]*)>(.*?)</a>", re.I | re.S)
_HREF_RE = re.compile(r'href="([^"]+)"', re.I)


def _fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:  # noqa: S310 (fixed gov host)
        return response.read()


def _anchors(page_html: str):
    """Yield (href, visible_text) for every <a> on the page."""
    for match in _ANCHOR_RE.finditer(page_html):
        href = _HREF_RE.search(match.group(1))
        if href:
            text = html.unescape(re.sub(r"<[^>]+>", "", match.group(2))).strip()
            yield href.group(1), text


class Command(BaseCommand):
    help = "Download the latest EOIR R&A roster PDFs into data/raw/."

    def add_arguments(self, parser):
        parser.add_argument(
            "--raw-dir",
            default=None,
            help="Directory to save the PDFs into (default: <repo>/data/raw).",
        )

    def handle(self, *args, **options):
        raw_dir = Path(options["raw_dir"]) if options["raw_dir"] else repo_data_dir() / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)

        anchors = list(_anchors(_fetch(ROSTER_PAGE).decode("utf-8", "replace")))

        for filename, matches in TARGETS:
            hits = [(href, text) for href, text in anchors if matches(text.lower())]
            if not hits:
                raise CommandError(
                    f"No link matched '{filename}' on {ROSTER_PAGE} — the page layout "
                    f"may have changed; update download_ra_rosters.TARGETS."
                )
            if len(hits) > 1:
                labels = ", ".join(repr(t) for _, t in hits)
                raise CommandError(f"Ambiguous links for '{filename}': {labels}")

            href, label = hits[0]
            url = href if href.startswith("http") else BASE_URL + href
            data = _fetch(url)
            if not data.startswith(b"%PDF"):
                raise CommandError(f"{url} did not return a PDF (got {data[:16]!r}).")

            (raw_dir / filename).write_bytes(data)
            self.stdout.write(
                self.style.SUCCESS(f"{filename}: {len(data) // 1024} KB  <- {url}  ({label})")
            )
