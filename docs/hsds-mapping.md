# The directory in HSDS 3.1

The legal-help directory (`network.Organization`) can be exported as
[Open Referral HSDS 3.1](https://docs.openreferral.org/en/latest/), the data
standard that 211 networks, findhelp, Unite Us and most resource-referral tools
read. Exporting in HSDS means a partner can load VisaNav's directory without
writing a custom importer.

```bash
just manage export_hsds --output hsds.json     # every active US organization
just manage export_hsds --country us           # same, to stdout
```

(`just manage` runs from `api/`, so a relative `--output` lands there.)

The command is `network/management/commands/export_hsds.py`; the mapping itself
is `network/hsds.py`, and this document describes it.

## Output shape

One JSON document in the shape of the HSDS API's paginated list response
(`GET /organizations?full_service=true`), with every organization on one page:

```json
{
  "total_items": 995, "total_pages": 1, "page_number": 1, "size": 995,
  "first_page": true, "last_page": true, "empty": false,
  "contents": [ { "id": "…", "name": "…", "services": [ … ], "locations": [ … ] } ]
}
```

Each item in `contents` validates against HSDS's compiled
`schema/compiled/organization.json` (organization with its services, locations,
phones and attributes nested).

Only active organizations are exported. Representatives (individual attorneys
and DOJ-accredited representatives) are **not** exported: they are people, not
services, and HSDS has no good home for them beyond named contacts.

## Identifiers

HSDS requires a UUID on every object. VisaNav has none, so the export derives
**deterministic UUIDv5s** from the organization slug under a fixed namespace
(`uuid5(NAMESPACE_URL, "https://www.visanav.org/hsds")`). The same organization
always gets the same ids, so a partner re-importing a newer export updates its
records instead of duplicating them. Changing an organization's slug changes its
ids; treat slugs as permanent.

## Organization → HSDS

Each VisaNav organization becomes one HSDS `organization` with one `service`
(VisaNav lists each organization for one thing: immigration legal help) and, when
it has a complete address, one `location` linked to that service through a
`service_at_location`.

| VisaNav (`Organization`) | HSDS | Notes |
|---|---|---|
| `slug` | `organization.id` (UUIDv5) | Also the seed for every nested id. |
| `name` | `organization.name` | |
| `description` | `organization.description`, `service.description` | Required by HSDS. When blank (most roster rows), a factual sentence is built from the type, accreditation and pro bono flag, e.g. "DOJ-recognized non-profit offering immigration legal services. Offers free legal help to those who qualify." |
| `organization_type` | `organization.legal_status` | The display label, e.g. "Non-profit". |
| `websites[0]` | `organization.website`, `service.url` | |
| `websites[1:]` | `organization.additional_websites[]` (`url`) | |
| `emails[0]` | `organization.email`, `service.email` | |
| `emails[1:]` | `organization.contacts[]` (email only) | |
| `phones[]` | `organization.phones[]` (`type: voice`) | |
| `address` | `location` (`location_type: physical`) + `address` | Only when `line1`, `city`, state and `postal_code` are all present, since HSDS requires them; otherwise there is no location. A P.O. box becomes `address_type: postal`. `state_province` is the two-letter code (`AZ`). |
| `country` | `address.country` | ISO 3166-1 alpha-2, as HSDS asks. |
| (fixed) | `service.name` | "Immigration legal services". |
| `is_active` | `service.status` | Always `active`: inactive organizations are not exported. |
| `fee_model`, `pro_bono` | `service.fees_description` | Free text, e.g. "Free" or "Sliding-scale fees. Free legal help for those who qualify." |
| `accreditation` | `service.accreditations` | e.g. "DOJ-recognized". |
| `languages[]` | `service.languages[]` | ISO 639-1 `code` plus the English `name`. |
| `services[]` (tags) | `service.attributes[]` → taxonomy term | VisaNav service tags are published as terms of a "VisaNav immigration services" taxonomy (`code` is the tag, e.g. `removal-defense`). |
| `source_url` | `service.attributes[]` → "VisaNav provenance" `source` term, `value` = URL | HSDS has no source field; this keeps the citation with the record. |
| `last_verified` | `service.assured_date` | When the listing was last checked. |
| `updated_at` | `service.last_modified` | |

## Not mapped

- **Opening hours, eligibility, required documents, service areas.** VisaNav does
  not collect them yet.
- **Latitude and longitude.** Addresses are not geocoded.
- **`organization.uri`.** The directory has no stable per-organization URL yet.
- **HSDS `metadata` (the change log).** VisaNav keeps no field-level history.
- **The 211 / AIRS taxonomy.** VisaNav uses its own service tags. Mapping them to
  AIRS codes (e.g. the "Immigration/Naturalization Legal Services" terms) would
  let 211 systems file the records automatically; that needs an AIRS license
  check first.

## Checking an export

The tests in `network/test_hsds.py` check the required fields and id stability.
For a full check against the official schema, validate an export with
`jsonschema` and HSDS's compiled organization schema:

```bash
curl -sLO https://raw.githubusercontent.com/openreferral/specification/3.1/schema/compiled/organization.json
uv run --with jsonschema python -c "
import json, jsonschema
schema = json.load(open('organization.json'))
for org in json.load(open('hsds.json'))['contents']:
    jsonschema.validate(org, schema)
print('ok')"
```
