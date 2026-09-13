# Controlled vocabularies

These are the fixed value lists the schemas enforce. Keeping everyone on the
same terms is what lets data from dozens of contributors stay consistent and
searchable. If a value you need is missing, **open an issue proposing it** rather
than inventing one — adding a term is a deliberate, reviewed change (it usually
means updating the JSON Schema too).

## Country codes (`country`)

ISO 3166-1 **alpha-2**, uppercase. Examples: `US`, `CA`, `MX`, `GB`, `DE`, `IN`, `PH`.
The code must match the `countries/<code>/` folder the file lives in.

## Language codes (`lang`, `languages`)

ISO 639-1 **two-letter**, lowercase. Examples: `en`, `es`, `fr`, `zh`, `ar`, `tl`, `pt`.

## Knowledge topics (`topic`)

| value | use for |
|-------|---------|
| `green-card` | Permanent residence / settlement pathways |
| `visas` | Temporary/non-immigrant visa categories |
| `citizenship` | Naturalization, citizenship by descent |
| `asylum-refugee` | Asylum, refugee, humanitarian protection |
| `work-authorization` | Work permits, employment eligibility |
| `family` | Family sponsorship / petitions |
| `forms` | Guidance about specific forms |
| `fees` | Filing fees, fee waivers |
| `appeals` | Appeals, motions, denials |
| `enforcement` | Detention, removal, rights during enforcement |
| `rights` | Know-your-rights material |
| `glossary` | Definitions of terms |
| `other` | Anything not yet covered (prefer proposing a new topic) |

## Source types (`source_type`)

| value | meaning |
|-------|---------|
| `official` | Straight from a government authority. **Must** cite a URL whose domain is listed in the country's `meta.yaml` `official_domains`. |
| `secondary` | A reputable non-government source (e.g. a law-school clinic explainer). Still requires a real `source_url`. |

## Organization types (`org_type`)

Mirrors the app's `Organization.OrganizationType`:

`self-owned`, `public-company`, `private-company`, `partnership`,
`educational`, `referral-service`, `community-organization`, `non-profit`.

## Fee models (`fee_model`)

`free`, `sliding-scale`, `low-cost`, `paid`, `unknown`.

## Service tags (`services`)

Free-form lowercase-hyphenated keywords, but prefer these common ones so filtering
works across countries:

`removal-defense`, `asylum`, `family-petitions`, `citizenship`,
`work-authorization`, `detention`, `victims-of-crime`, `daca`,
`unaccompanied-minors`, `appeals`, `know-your-rights`, `general-consultation`.
