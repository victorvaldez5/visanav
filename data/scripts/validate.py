#!/usr/bin/env python3
"""Validate every data file under data/countries/ against the schemas.

What it checks:
  * Knowledge Markdown frontmatter + resource YAML entries validate against
    their JSON Schemas (data/schema/*.json).
  * `country` in each file matches the countries/<code>/ folder it lives in.
  * `official` knowledge sources cite a domain declared in that country's
    meta.yaml `official_domains` (the trust rule).
  * `doc_id` / `org_id` are unique within a country.
  * `last_verified` parses as a real date.

Exit code is non-zero if anything fails, so CI can gate pull requests.

Usage:
    python data/scripts/validate.py            # validate all countries
    python data/scripts/validate.py us ca      # validate only these countries

Dependencies: pyyaml, jsonschema  (see data/scripts/requirements.txt)
"""
from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path
from urllib.parse import urlparse

try:
    import yaml
    from jsonschema import Draft202012Validator
except ImportError:  # pragma: no cover
    sys.exit(
        "Missing dependencies. Run:\n"
        "    pip install -r data/scripts/requirements.txt"
    )

DATA_DIR = Path(__file__).resolve().parent.parent
SCHEMA_DIR = DATA_DIR / "schema"
COUNTRIES_DIR = DATA_DIR / "countries"

errors: list[str] = []


def err(where: str, msg: str) -> None:
    errors.append(f"  ✗ {where}: {msg}")


def load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def split_frontmatter(text: str) -> dict | None:
    """Return the parsed YAML frontmatter of a Markdown file, or None if absent."""
    if not text.startswith("---"):
        return None
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None
    return yaml.safe_load(parts[1]) or {}


def check_date(where: str, value) -> None:
    if not isinstance(value, (str,)):
        # PyYAML may already parse an unquoted date into a date object.
        if isinstance(value, dt.date):
            return
        err(where, f"last_verified must be a YYYY-MM-DD string, got {value!r}")
        return
    try:
        dt.date.fromisoformat(value)
    except ValueError:
        err(where, f"last_verified is not a valid ISO date: {value!r}")


def domain_of(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def official_domain_ok(url: str, allowed: list[str]) -> bool:
    host = domain_of(url)
    return any(host == d or host.endswith("." + d) for d in allowed)


def validate_country(code: str, k_validator, r_validator) -> None:
    cdir = COUNTRIES_DIR / code
    meta_path = cdir / "meta.yaml"
    if not meta_path.exists():
        err(str(cdir), "missing meta.yaml")
        return

    meta = yaml.safe_load(meta_path.read_text(encoding="utf-8")) or {}
    if meta.get("country") != code.upper():
        err(str(meta_path), f"country '{meta.get('country')}' != folder '{code.upper()}'")
    allowed_domains = [
        d.lower()
        for a in meta.get("authorities", [])
        for d in a.get("official_domains", [])
    ]

    seen_doc_ids: set[str] = set()
    seen_org_ids: set[str] = set()

    # --- knowledge documents ---
    for md in sorted((cdir / "knowledge").rglob("*.md")):
        rel = md.relative_to(DATA_DIR)
        fm = split_frontmatter(md.read_text(encoding="utf-8"))
        if fm is None:
            err(str(rel), "missing or malformed YAML frontmatter (--- ... ---)")
            continue
        # jsonschema needs plain strings for date/uri formats.
        fm_norm = {k: (v.isoformat() if isinstance(v, dt.date) else v) for k, v in fm.items()}
        schema_errors = sorted(k_validator.iter_errors(fm_norm), key=lambda e: e.path)
        for e in schema_errors:
            err(str(rel), e.message)
        if schema_errors:
            continue
        if fm_norm["country"] != code.upper():
            err(str(rel), f"country '{fm_norm['country']}' != folder '{code.upper()}'")
        if fm_norm["doc_id"] in seen_doc_ids:
            err(str(rel), f"duplicate doc_id '{fm_norm['doc_id']}'")
        seen_doc_ids.add(fm_norm["doc_id"])
        check_date(str(rel), fm.get("last_verified"))
        if fm_norm["source_type"] == "official":
            if not allowed_domains:
                err(str(rel), "source_type=official but country meta.yaml lists no official_domains")
            elif not official_domain_ok(fm_norm["source_url"], allowed_domains):
                err(
                    str(rel),
                    f"official source_url domain '{domain_of(fm_norm['source_url'])}' "
                    f"not in official_domains {allowed_domains}",
                )

    # --- resource files ---
    for yml in sorted((cdir / "resources").rglob("*.yaml")):
        rel = yml.relative_to(DATA_DIR)
        entries = yaml.safe_load(yml.read_text(encoding="utf-8"))
        if not isinstance(entries, list):
            err(str(rel), "resource file must be a YAML list of organizations")
            continue
        entries_norm = json.loads(json.dumps(entries, default=str))
        schema_errors = sorted(r_validator.iter_errors(entries_norm), key=lambda e: list(e.path))
        for e in schema_errors:
            loc = "/".join(str(p) for p in e.path)
            err(str(rel), f"[{loc}] {e.message}")
        if schema_errors:
            continue
        for entry in entries_norm:
            if entry["country"] != code.upper():
                err(str(rel), f"{entry['org_id']}: country != folder '{code.upper()}'")
            if entry["org_id"] in seen_org_ids:
                err(str(rel), f"duplicate org_id '{entry['org_id']}'")
            seen_org_ids.add(entry["org_id"])
            check_date(f"{rel}:{entry['org_id']}", entry.get("last_verified"))


def main() -> int:
    if not COUNTRIES_DIR.exists():
        print(f"No countries directory at {COUNTRIES_DIR}")
        return 1

    k_validator = Draft202012Validator(load_json(SCHEMA_DIR / "knowledge.schema.json"))
    r_validator = Draft202012Validator(load_json(SCHEMA_DIR / "resource.schema.json"))

    requested = [c.lower() for c in sys.argv[1:]]
    codes = [
        p.name
        for p in sorted(COUNTRIES_DIR.iterdir())
        if p.is_dir() and not p.name.startswith("_")
    ]
    if requested:
        codes = [c for c in codes if c in requested]

    if not codes:
        print("Nothing to validate.")
        return 0

    for code in codes:
        validate_country(code, k_validator, r_validator)

    if errors:
        print(f"Validation FAILED with {len(errors)} problem(s):\n")
        print("\n".join(errors))
        return 1

    print(f"✓ All data valid ({', '.join(c.upper() for c in codes)}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
