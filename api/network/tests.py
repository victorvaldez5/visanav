import asyncio
from types import SimpleNamespace

import pytest
import yaml
from django.core.management import call_command
from rest_framework.test import APIClient

from core.llm import resource_lookup
from locations.models import Address, Country, Subdivision
from network.models import Organization, Representative

ORGS_URL = "/api/network/organizations/"
REPS_URL = "/api/network/representatives/"


def _arizona_address():
    country = Country.objects.create(country_code="US", name="United States")
    subdivision = Subdivision.objects.create(code="US-AZ", name="Arizona", country=country)
    return Address.objects.create(line1="P.O. Box 1", city="Phoenix", subdivision=subdivision)


def _make_org(slug, **kwargs):
    defaults = dict(
        name=slug.replace("-", " ").title(),
        organization_type="non-profit",
        is_active=True,
    )
    defaults.update(kwargs)
    return Organization.objects.create(slug=slug, **defaults)


# --- resource_lookup tool -------------------------------------------------
# transaction=True: resource_lookup runs its ORM query in asyncio.to_thread, a
# worker thread with its own DB connection, so the test data must be committed.

@pytest.mark.django_db(transaction=True)
def test_resource_lookup_filters_pro_bono_and_region():
    addr = _arizona_address()
    _make_org(
        "florence-project",
        pro_bono=True,
        fee_model="free",
        services=["removal-defense", "detention"],
        phones=["+1-520-868-0191"],
        websites=["https://www.firrp.org"],
        address=addr,
    )
    _make_org("paid-firm-tx", pro_bono=False, fee_model="paid")

    ctx = SimpleNamespace(deps=SimpleNamespace(namespace="us"))
    results = asyncio.run(resource_lookup(ctx, region="Arizona", pro_bono_only=True))

    assert len(results) == 1
    match = results[0]
    assert match["name"] == "Florence Project"
    assert match["pro_bono"] is True
    assert match["region"] == "Arizona"
    assert match["city"] == "Phoenix"
    assert match["phones"] == ["+1-520-868-0191"]


@pytest.mark.django_db(transaction=True)
def test_resource_lookup_filters_by_service():
    _make_org("asylum-org", services=["asylum"])
    _make_org("family-org", services=["family-petitions"])

    ctx = SimpleNamespace(deps=SimpleNamespace(namespace="us"))
    results = asyncio.run(resource_lookup(ctx, service="asylum"))

    assert [m["name"] for m in results] == ["Asylum Org"]


@pytest.mark.django_db(transaction=True)
def test_resource_lookup_excludes_inactive():
    _make_org("inactive-org", is_active=False)

    ctx = SimpleNamespace(deps=SimpleNamespace(namespace="us"))
    results = asyncio.run(resource_lookup(ctx))

    assert results == []


# --- load_resources command ----------------------------------------------

RESOURCE_YAML = [
    {
        "org_id": "test-firrp",
        "name": "Test Florence Project",
        "org_type": "non-profit",
        "country": "US",
        "pro_bono": True,
        "fee_model": "free",
        "services": ["removal-defense", "detention"],
        "description": "Free legal services.",
        "languages": ["en", "es"],
        "contact": {
            "websites": ["https://www.firrp.org"],
            "emails": ["firrp@firrp.org"],
            "phones": ["+1-520-868-0191"],
        },
        "address": {
            "line1": "P.O. Box 32670",
            "city": "Phoenix",
            "region": "AZ",
            "postal_code": "85064",
            "country": "US",
        },
        "source_url": "https://www.firrp.org",
        "last_verified": "2026-02-10",
    }
]


def _write_resource_tree(tmp_path):
    resources = tmp_path / "countries" / "us" / "resources"
    resources.mkdir(parents=True, exist_ok=True)
    (resources / "test.yaml").write_text(yaml.safe_dump(RESOURCE_YAML), encoding="utf-8")
    return tmp_path


@pytest.mark.django_db
def test_load_resources_populates_flat_fields(tmp_path, monkeypatch):
    _write_resource_tree(tmp_path)
    monkeypatch.setattr(
        "network.management.commands.load_resources.repo_data_dir",
        lambda: tmp_path,
    )
    # Subdivision so the address links to a region.
    country = Country.objects.create(country_code="US", name="United States")
    Subdivision.objects.create(code="US-AZ", name="Arizona", country=country)

    call_command("load_resources", "us")

    org = Organization.objects.get(slug="test-firrp")
    assert org.name == "Test Florence Project"
    assert org.organization_type == "non-profit"
    assert org.pro_bono is True
    assert org.fee_model == "free"
    assert org.services == ["removal-defense", "detention"]
    assert org.languages == ["en", "es"]
    assert org.emails == ["firrp@firrp.org"]
    assert org.phones == ["+1-520-868-0191"]
    assert org.source_url == "https://www.firrp.org"
    assert str(org.last_verified) == "2026-02-10"
    assert org.address is not None
    assert org.address.city == "Phoenix"
    assert org.address.subdivision.name == "Arizona"


@pytest.mark.django_db
def test_probono_enriches_curated_org_without_duplicating(monkeypatch):
    # A curated row already exists (same org, hand-picked slug + richer fields).
    addr = _arizona_address()
    _make_org(
        "florence-project",
        name="Florence Immigrant and Refugee Rights Project",
        organization_type="non-profit",
        fee_model="sliding-scale",
        pro_bono=False,
        description="Curated description.",
        services=["removal-defense", "detention"],
        emails=["curated@firrp.org"],
        address=addr,
    )
    # The DOJ pro-bono roster lists the same org under a name-derived slug.
    row = {
        "organization_name": "Florence Immigrant and Refugee Rights Project",
        "organization_type": "non-profit",
        "address": "P.O. Box 2",
        "city": "Phoenix",
        "state": "AZ",
        "zip_code": "85064",
        "email_addresses": ["intake@firrp.org"],
        "telephone_numbers": ["+1-520-868-0191"],
        "websites": ["www.firrp.org"],
        "notes": ["roster note"],
    }
    monkeypatch.setattr(
        "network.management.commands.extract_probono._load_fixture", lambda: [row]
    )
    call_command("extract_probono", "--insert_to_db")

    # One row, not two.
    florence = Organization.objects.filter(name__icontains="Florence")
    assert florence.count() == 1
    org = florence.get()
    assert org.slug == "florence-project"  # curated identity wins
    assert org.pro_bono is True  # roster signal applied
    assert org.fee_model == "sliding-scale"  # curated value NOT clobbered
    assert org.description == "Curated description."  # curated value preserved
    assert org.services == ["removal-defense", "detention"]  # preserved
    assert "curated@firrp.org" in org.emails and "intake@firrp.org" in org.emails  # unioned


@pytest.mark.django_db
def test_ra_orgs_enriches_curated_org_without_duplicating(monkeypatch):
    addr = _arizona_address()
    _make_org(
        "florence-project",
        name="Florence Immigrant and Refugee Rights Project",
        organization_type="non-profit",
        services=["removal-defense"],
        address=addr,
    )
    row = {
        "organization_name": "Florence Immigrant and Refugee Rights Project",
        "addresses": [
            {"line1": "P.O. Box 3", "city": "Phoenix", "state": "AZ",
             "postal_code": "85064", "phone_number": "+1-602-307-1008"},
        ],
    }
    monkeypatch.setattr(
        "network.management.commands.extract_ra_orgs._load_fixture", lambda: [row]
    )
    call_command("extract_ra_orgs", "--insert_to_db")

    florence = Organization.objects.filter(name__icontains="Florence")
    assert florence.count() == 1
    org = florence.get()
    assert org.slug == "florence-project"
    assert org.accreditation == "DOJ-recognized"  # roster signal applied
    assert org.organization_type == "non-profit"  # curated type NOT clobbered
    assert org.services == ["removal-defense"]  # preserved
    assert "+1-602-307-1008" in org.phones


@pytest.mark.django_db
def test_load_resources_is_idempotent(tmp_path, monkeypatch):
    _write_resource_tree(tmp_path)
    monkeypatch.setattr(
        "network.management.commands.load_resources.repo_data_dir",
        lambda: tmp_path,
    )
    call_command("load_resources", "us")
    call_command("load_resources", "us")

    assert Organization.objects.filter(slug="test-firrp").count() == 1
    # The address is updated in place, not duplicated.
    assert Address.objects.count() == 1


# --- endpoints ------------------------------------------------------------

@pytest.mark.django_db
def test_organizations_endpoint_returns_flat_shape_and_filters():
    addr = _arizona_address()
    _make_org(
        "az-pro-bono",
        pro_bono=True,
        services=["asylum"],
        emails=["help@example.org"],
        phones=["+1-555-000-1111"],
        websites=["https://example.org"],
        address=addr,
    )
    _make_org("tx-paid", pro_bono=False, services=["family-petitions"])
    _make_org("hidden", is_active=False)

    client = APIClient()

    # Flat shape + only active rows.
    resp = client.get(ORGS_URL)
    assert resp.status_code == 200
    results = resp.data["results"]
    slugs = {r["slug"] for r in results}
    assert slugs == {"az-pro-bono", "tx-paid"}
    row = next(r for r in results if r["slug"] == "az-pro-bono")
    assert row["emails"] == ["help@example.org"]
    assert row["phones"] == ["+1-555-000-1111"]
    assert row["websites"] == ["https://example.org"]
    assert row["address"]["subdivision"]["name"] == "Arizona"

    # pro_bono filter.
    resp = client.get(ORGS_URL, {"pro_bono": "true"})
    assert {r["slug"] for r in resp.data["results"]} == {"az-pro-bono"}

    # region filter (subdivision name).
    resp = client.get(ORGS_URL, {"region": "Arizona"})
    assert {r["slug"] for r in resp.data["results"]} == {"az-pro-bono"}

    # service filter (array contains).
    resp = client.get(ORGS_URL, {"service": "family-petitions"})
    assert {r["slug"] for r in resp.data["results"]} == {"tx-paid"}


@pytest.mark.django_db
def test_representatives_endpoint_empty_and_active_only():
    client = APIClient()

    resp = client.get(REPS_URL)
    assert resp.status_code == 200
    assert resp.data["results"] == []

    Representative.objects.create(name="Jane Doe", provider_type="attorney", is_active=True)
    Representative.objects.create(name="Hidden Rep", provider_type="attorney", is_active=False)

    resp = client.get(REPS_URL)
    results = resp.data["results"]
    assert [r["name"] for r in results] == ["Jane Doe"]
    assert results[0]["provider_type"] == "attorney"
