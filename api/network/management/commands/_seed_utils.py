"""Shared helpers for the directory-seeding management commands.

Named with a leading underscore so Django's command discovery skips it.
"""
import os
import re
from pathlib import Path
from typing import Optional

from locations.models import Address, Subdivision


def repo_data_dir() -> Path:
    """Return the repo's top-level ``data/`` directory.

    Resolution order:
    1. the ``DATA_DIR`` env var, if set (explicit escape hatch);
    2. the nearest ancestor holding a ``data/countries/`` dir — works both from
       the repo checkout (host) and from the container, where the image copies
       ``data/`` in next to ``api/`` at ``/app/data`` (see api/Dockerfile);
    3. a repo-root-relative fallback.
    """
    env = os.environ.get("DATA_DIR")
    if env:
        return Path(env)
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "data"
        if (candidate / "countries").is_dir():
            return candidate
    return here.parents[4] / "data"


def normalize_url(url: str) -> str:
    """Prepend a scheme so bare hosts (``www.example.org``) are valid URLs."""
    url = (url or "").strip()
    if url and not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url


def resolve_subdivision(region: Optional[str], country: str = "US") -> Optional[Subdivision]:
    """Look up a Subdivision by its ``<country>-<region>`` code (e.g. US-AZ)."""
    if not region:
        return None
    code = f"{country}-{region.strip().upper()}"
    return Subdivision.objects.filter(code=code).first()


# --- cross-source dedup ---------------------------------------------------
# The three seeders draw from independent sources (curated data/ YAML, the DOJ
# recognized-org roster, the DOJ pro-bono roster) that mint slugs differently, so
# the same real org can arrive under different slugs. These helpers give every
# source one identity key — normalized name + region — so it collapses to a
# single row, with curated data winning.


def normalize_name(name: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace — a fuzzy match key."""
    return re.sub(r"[^a-z0-9]+", " ", (name or "").lower()).strip()


def region_code_for(region: Optional[str], country: str = "US") -> str:
    """The subdivision code suffix (e.g. 'AZ') if resolvable, else ''.

    Resolved through the same Subdivision lookup ``build_org_index`` reads back
    from, so a row's key is identical whichever source computes it (both fall
    back to '' when the subdivision is unknown).
    """
    subdivision = resolve_subdivision(region, country)
    return subdivision.code.split("-")[-1] if subdivision else ""


def dedup_key(name: str, region_code: str):
    return (normalize_name(name), (region_code or "").upper())


def build_org_index() -> dict:
    """Map ``dedup_key`` -> Organization over the current directory.

    Built once per command so each seed row can find an existing org (from any
    source) in memory instead of re-querying.
    """
    from network.models import Organization

    index = {}
    for org in Organization.objects.select_related("address__subdivision"):
        region = ""
        if org.address and org.address.subdivision:
            region = org.address.subdivision.code.split("-")[-1]
        index[dedup_key(org.name, region)] = org
    return index


def resolve_org(name: str, slug: str, region_code: str, index: dict):
    """Find the Organization a seed row maps to, deduping across sources.

    Returns ``(org, origin)``:
      - ``"own"``     — matched by ``slug`` (a row this loader owns, or a
        same-slug roster overlap): safe to fully (re)populate.
      - ``"foreign"`` — matched by normalized name + region under a *different*
        slug (typically a curated ``data/`` row): enrich only, don't clobber.
      - ``"new"``     — no match: a fresh, unsaved ``Organization(slug, name)``.
    """
    from network.models import Organization

    if slug:
        own = Organization.objects.filter(slug=slug).first()
        if own is not None:
            return own, "own"
    foreign = index.get(dedup_key(name, region_code))
    if foreign is not None:
        return foreign, "foreign"
    return Organization(slug=slug, name=name), "new"


def index_org(index: dict, org, region_code: str) -> None:
    """Register a just-saved org so later rows in the same run dedup against it."""
    index[dedup_key(org.name, region_code)] = org


def union_list(existing, new) -> list:
    """Append new items to existing, preserving order and dropping blanks/dupes."""
    out = list(existing or [])
    for item in new or []:
        if item and item not in out:
            out.append(item)
    return out


def upsert_address(
    existing: Optional[Address],
    *,
    line1: str = "",
    line2: str = "",
    city: str = "",
    region: Optional[str] = None,
    postal_code: str = "",
    country: str = "US",
    address_name: str = "Primary Address",
) -> Optional[Address]:
    """Create or update an Address in place.

    Reusing ``existing`` (an org's current address) keeps re-seeding idempotent —
    no orphan Address rows pile up on repeated runs. Returns ``None`` when there's
    no street line to store.
    """
    if not line1:
        return None

    subdivision = resolve_subdivision(region, country)
    fields = {
        "address_name": address_name or "Primary Address",
        "line1": line1,
        "line2": line2 or "",
        "city": city or "",
        "postal_code": postal_code or "",
        "subdivision": subdivision,
    }
    if existing is not None:
        for key, value in fields.items():
            setattr(existing, key, value)
        existing.save()
        return existing
    return Address.objects.create(**fields)
