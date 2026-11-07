"""Map the legal-help directory onto Open Referral HSDS 3.1.

HSDS (https://docs.openreferral.org/) is the data standard 211 networks and
resource-referral tools read, so publishing the directory in it lets a partner
load VisaNav's organizations without a custom importer. The field-by-field
mapping, and what is left out, is documented in docs/hsds-mapping.md.

Each Organization becomes one HSDS ``organization`` with one ``service``
(immigration legal help) and, when its address is complete, one ``location``.
Every HSDS object needs a UUID; they are derived deterministically from the
organization slug (UUIDv5), so re-exports keep the same ids and a partner's
import updates records instead of duplicating them.
"""
import re
import uuid

import pycountry

from network.models import FeeModel, Organization

HSDS_VERSION = "3.1"

# Fixed namespace for every id in the export. Never change it: partners key
# their imported records on the ids derived from it.
NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "https://www.visanav.org/hsds")

SERVICE_NAME = "Immigration legal services"

SERVICES_TAXONOMY = {
    "name": "VisaNav immigration services",
    "description": "VisaNav's service tags for immigration legal help (data/schema/vocabularies.md).",
}
PROVENANCE_TAXONOMY = {
    "name": "VisaNav provenance",
    "description": "Where VisaNav sourced or last verified a listing.",
}

_FEES = {
    FeeModel.FREE: "Free",
    FeeModel.SLIDING_SCALE: "Sliding-scale fees",
    FeeModel.LOW_COST: "Low cost",
    FeeModel.PAID: "Fees apply",
}
_PO_BOX = re.compile(r"\bp\.?\s*o\.?\s*box\b", re.IGNORECASE)


def hsds_id(*parts: str) -> str:
    """A stable UUIDv5 for one HSDS object, e.g. hsds_id("phone", slug, number)."""
    return str(uuid.uuid5(NAMESPACE, ":".join(parts)))


def _taxonomy(spec: dict) -> dict:
    return {"id": hsds_id("taxonomy", spec["name"]), **spec}


def _attribute(link_id: str, taxonomy: dict, code: str, name: str, value: str = "") -> dict:
    term = {
        "id": hsds_id("taxonomy_term", taxonomy["name"], code),
        "code": code,
        "name": name,
        "description": name,
        "taxonomy_id": taxonomy["id"],
        "taxonomy_detail": taxonomy,
    }
    attribute = {
        "id": hsds_id("attribute", link_id, term["id"]),
        "link_id": link_id,
        "link_entity": "service",
        "taxonomy_term_id": term["id"],
        "taxonomy_term": term,
    }
    if value:
        attribute["value"] = value
    return attribute


def _description(org: Organization) -> str:
    if org.description.strip():
        return org.description.strip()
    label = org.get_organization_type_display()
    kind = f"{org.accreditation} {label.lower()}" if org.accreditation else label
    text = f"{kind[0].upper()}{kind[1:]} offering immigration legal services."
    if org.pro_bono:
        text += " Offers free legal help to those who qualify."
    return text


def _fees(org: Organization) -> str:
    parts = [_FEES[org.fee_model]] if org.fee_model in _FEES else []
    if org.pro_bono:
        parts.append("Free legal help for those who qualify")
    return ". ".join(parts) + "." if parts else ""


def _language(service_id: str, code: str) -> dict:
    entry = {"id": hsds_id("language", service_id, code), "service_id": service_id, "code": code}
    language = pycountry.languages.get(alpha_2=code)
    if language:
        entry["name"] = language.name
    return entry


def _location(org: Organization, org_id: str):
    """The org's physical location, or None when HSDS's required address
    fields (line 1, city, state, postal code) are not all known."""
    address = org.address
    if address is None or address.subdivision is None:
        return None
    state = address.subdivision.code.split("-")[-1]
    if not (address.line1 and address.city and state and address.postal_code):
        return None
    location_id = hsds_id("location", org.slug)
    return {
        "id": location_id,
        "location_type": "physical",
        "organization_id": org_id,
        "name": org.name,
        "addresses": [
            {
                "id": hsds_id("address", org.slug),
                "location_id": location_id,
                "address_1": address.line1,
                **({"address_2": address.line2} if address.line2 else {}),
                "city": address.city,
                "state_province": state,
                "postal_code": address.postal_code,
                "country": org.country,
                "address_type": "postal" if _PO_BOX.search(address.line1) else "physical",
            }
        ],
    }


def organization_to_hsds(org: Organization) -> dict:
    """One Organization as an HSDS organization with its service and location
    nested (the shape of HSDS's compiled ``organization`` schema)."""
    org_id = hsds_id("organization", org.slug)
    service_id = hsds_id("service", org.slug)
    description = _description(org)
    website = org.websites[0] if org.websites else ""
    email = org.emails[0] if org.emails else ""

    services_taxonomy = _taxonomy(SERVICES_TAXONOMY)
    attributes = [
        _attribute(service_id, services_taxonomy, tag, tag.replace("-", " ").capitalize())
        for tag in org.services
    ]
    if org.source_url:
        attributes.append(
            _attribute(service_id, _taxonomy(PROVENANCE_TAXONOMY), "source", "Source", org.source_url)
        )

    service = {
        "id": service_id,
        "organization_id": org_id,
        "name": SERVICE_NAME,
        "description": description,
        "status": "active",
        "languages": [_language(service_id, code) for code in org.languages],
        "attributes": attributes,
        "last_modified": org.updated_at.isoformat(),
    }
    optional = {
        "url": website,
        "email": email,
        "fees_description": _fees(org),
        "accreditations": org.accreditation,
        "assured_date": org.last_verified.isoformat() if org.last_verified else "",
    }
    service.update({key: value for key, value in optional.items() if value})

    location = _location(org, org_id)
    if location:
        service["service_at_locations"] = [
            {
                "id": hsds_id("service_at_location", org.slug),
                "service_id": service_id,
                "location_id": location["id"],
            }
        ]

    hsds = {
        "id": org_id,
        "name": org.name,
        "description": description,
        "legal_status": org.get_organization_type_display(),
        "additional_websites": [
            {"id": hsds_id("url", org.slug, url), "organization_id": org_id, "url": url}
            for url in org.websites[1:]
        ],
        "contacts": [
            {"id": hsds_id("contact", org.slug, address), "organization_id": org_id, "email": address}
            for address in org.emails[1:]
        ],
        "phones": [
            {"id": hsds_id("phone", org.slug, number), "organization_id": org_id, "number": number, "type": "voice"}
            for number in org.phones
        ],
        "locations": [location] if location else [],
        "services": [service],
    }
    if website:
        hsds["website"] = website
    if email:
        hsds["email"] = email
    return hsds


def export_organizations(queryset) -> dict:
    """Every organization in ``queryset`` as one HSDS paginated list response
    (all items on a single page), like ``GET /organizations?full_service=true``."""
    contents = [
        organization_to_hsds(org)
        for org in queryset.select_related("address__subdivision").order_by("slug")
    ]
    return {
        "total_items": len(contents),
        "total_pages": 1,
        "page_number": 1,
        "size": len(contents),
        "first_page": True,
        "last_page": True,
        "empty": not contents,
        "contents": contents,
    }
