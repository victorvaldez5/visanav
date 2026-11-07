import json
import uuid
from datetime import date

import pytest
from django.core.management import call_command

from locations.models import Address, Country, Subdivision
from network.hsds import SERVICE_NAME, hsds_id, organization_to_hsds
from network.models import Organization


def _address(line1="100 Main St", postal_code="85001"):
    country, _ = Country.objects.get_or_create(country_code="US", defaults={"name": "United States"})
    subdivision, _ = Subdivision.objects.get_or_create(
        code="US-AZ", defaults={"name": "Arizona", "country": country}
    )
    return Address.objects.create(
        line1=line1, city="Phoenix", subdivision=subdivision, postal_code=postal_code
    )


def _org(slug="florence-project", **kwargs):
    defaults = dict(
        name="Florence Project",
        organization_type="non-profit",
        is_active=True,
        country="US",
    )
    defaults.update(kwargs)
    return Organization.objects.create(slug=slug, **defaults)


def _is_uuid(value):
    return str(uuid.UUID(value)) == value


@pytest.mark.django_db
def test_full_organization_maps_to_hsds():
    org = _org(
        description="Free legal services for detained adults and children.",
        accreditation="DOJ-recognized",
        pro_bono=True,
        fee_model="free",
        services=["removal-defense", "asylum"],
        languages=["en", "es"],
        websites=["https://firrp.org", "https://firrp.org/es"],
        emails=["info@firrp.org", "intake@firrp.org"],
        phones=["+1-520-868-0191"],
        address=_address(),
        source_url="https://www.justice.gov/eoir/recognition-and-accreditation-program",
        last_verified=date(2026, 10, 1),
    )

    hsds = organization_to_hsds(org)

    assert hsds["id"] == hsds_id("organization", "florence-project")
    assert _is_uuid(hsds["id"])
    assert hsds["name"] == "Florence Project"
    assert hsds["description"] == org.description
    assert hsds["website"] == "https://firrp.org"
    assert [u["url"] for u in hsds["additional_websites"]] == ["https://firrp.org/es"]
    assert hsds["email"] == "info@firrp.org"
    assert [c["email"] for c in hsds["contacts"]] == ["intake@firrp.org"]
    assert hsds["phones"][0]["number"] == "+1-520-868-0191"

    (location,) = hsds["locations"]
    (address,) = location["addresses"]
    assert address["state_province"] == "AZ"
    assert address["country"] == "US"
    assert address["address_type"] == "physical"

    (service,) = hsds["services"]
    assert service["name"] == SERVICE_NAME
    assert service["status"] == "active"
    assert service["organization_id"] == hsds["id"]
    assert service["accreditations"] == "DOJ-recognized"
    assert service["fees_description"] == "Free. Free legal help for those who qualify."
    assert service["assured_date"] == "2026-10-01"
    assert service["service_at_locations"][0]["location_id"] == location["id"]
    assert {(lang["code"], lang["name"]) for lang in service["languages"]} == {
        ("en", "English"),
        ("es", "Spanish"),
    }
    codes = {a["taxonomy_term"]["code"]: a.get("value") for a in service["attributes"]}
    assert codes == {"removal-defense": None, "asylum": None, "source": org.source_url}


@pytest.mark.django_db
def test_ids_are_stable_across_exports():
    org = _org(phones=["555-0100"], address=_address())
    first, second = organization_to_hsds(org), organization_to_hsds(org)
    assert first == second
    assert first["services"][0]["id"] == hsds_id("service", "florence-project")


@pytest.mark.django_db
def test_blank_description_gets_factual_fallback():
    org = _org(accreditation="DOJ-recognized", pro_bono=True)
    hsds = organization_to_hsds(org)
    assert hsds["description"] == (
        "DOJ-recognized non-profit offering immigration legal services. "
        "Offers free legal help to those who qualify."
    )
    assert "fees_description" in hsds["services"][0]


@pytest.mark.django_db
def test_incomplete_address_has_no_location_and_po_box_is_postal():
    no_zip = organization_to_hsds(_org(address=_address(postal_code="")))
    assert no_zip["locations"] == []
    assert "service_at_locations" not in no_zip["services"][0]

    po_box = organization_to_hsds(_org(slug="po-box-org", address=_address(line1="P.O. Box 86299")))
    assert po_box["locations"][0]["addresses"][0]["address_type"] == "postal"


@pytest.mark.django_db
def test_export_command_writes_active_orgs_for_country(tmp_path):
    _org(slug="active-us")
    _org(slug="inactive-us", is_active=False)
    _org(slug="active-ca", country="CA")
    out = tmp_path / "hsds.json"

    call_command("export_hsds", "--output", str(out))

    document = json.loads(out.read_text(encoding="utf-8"))
    assert document["total_items"] == 1
    assert document["contents"][0]["id"] == hsds_id("organization", "active-us")
    for org in document["contents"]:
        assert {"id", "name", "description"} <= org.keys()
        for service in org["services"]:
            assert {"id", "name", "status"} <= service.keys()
