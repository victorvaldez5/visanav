import asyncio
from datetime import date, timedelta
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
    result = asyncio.run(resource_lookup(ctx, region="Arizona", pro_bono_only=True))

    assert result["count"] == 1
    assert result["note"] is None
    match = result["matches"][0]
    assert match["name"] == "Florence Project"
    assert match["pro_bono"] is True
    assert match["region"] == "Arizona"
    assert match["city"] == "Phoenix"
    assert match["phones"] == ["+1-520-868-0191"]


@pytest.mark.django_db(transaction=True)
def test_resource_lookup_region_accepts_postal_code():
    """A 2-letter state code resolves the same as the spelled-out name."""
    addr = _arizona_address()
    _make_org("florence-project", pro_bono=True, address=addr)

    ctx = SimpleNamespace(deps=SimpleNamespace(namespace="us"))
    result = asyncio.run(resource_lookup(ctx, region="AZ"))

    assert [m["name"] for m in result["matches"]] == ["Florence Project"]


@pytest.mark.django_db(transaction=True)
def test_resource_lookup_filters_by_service_when_tagged():
    """When some org IS tagged for the service, only tagged orgs come back."""
    _make_org("asylum-org", services=["asylum"])
    _make_org("family-org", services=["family-petitions"])

    ctx = SimpleNamespace(deps=SimpleNamespace(namespace="us"))
    result = asyncio.run(resource_lookup(ctx, service="asylum"))

    assert [m["name"] for m in result["matches"]] == ["Asylum Org"]
    assert result["note"] is None


@pytest.mark.django_db(transaction=True)
def test_resource_lookup_broadens_when_service_untagged():
    """Roster data carries no service tags: rather than return nothing, the
    lookup broadens to general help and flags it in `note` (the fix for Javi
    reciting provider contacts from memory when a service filter emptied out)."""
    _make_org("general-help", pro_bono=True, phones=["+1-555-000-0000"])

    ctx = SimpleNamespace(deps=SimpleNamespace(namespace="us"))
    result = asyncio.run(resource_lookup(ctx, service="asylum"))

    assert [m["name"] for m in result["matches"]] == ["General Help"]
    assert result["note"] and "asylum" in result["note"]


@pytest.mark.django_db(transaction=True)
def test_resource_lookup_orders_contactable_pro_bono_first():
    """Entries that can actually be contacted, and pro-bono help, rank first."""
    _make_org("no-contact-nonprofit", pro_bono=True)
    _make_org("paid-with-phone", pro_bono=False, phones=["+1-555-111-2222"])
    _make_org("probono-with-phone", pro_bono=True, phones=["+1-555-333-4444"])

    ctx = SimpleNamespace(deps=SimpleNamespace(namespace="us"))
    result = asyncio.run(resource_lookup(ctx))

    # contactable+pro-bono, then contactable, then the no-contact org last.
    assert [m["name"] for m in result["matches"]] == [
        "Probono With Phone",
        "Paid With Phone",
        "No Contact Nonprofit",
    ]


@pytest.mark.django_db(transaction=True)
def test_resource_lookup_excludes_inactive():
    _make_org("inactive-org", is_active=False)

    ctx = SimpleNamespace(deps=SimpleNamespace(namespace="us"))
    result = asyncio.run(resource_lookup(ctx))

    assert result["matches"] == []
    assert result["count"] == 0


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


@pytest.mark.django_db
def test_organizations_cost_filter_ors_pro_bono_and_fee_models():
    """The cost chips widen (OR), not narrow: pro-bono OR the picked fee models."""
    _make_org("pb", pro_bono=True)
    _make_org("free", pro_bono=False, fee_model="free")
    _make_org("low", pro_bono=False, fee_model="low-cost")
    _make_org("paid", pro_bono=False, fee_model="paid")

    client = APIClient()

    resp = client.get(ORGS_URL, {"cost": ["pro_bono", "free"]})
    assert {r["slug"] for r in resp.data["results"]} == {"pb", "free"}

    resp = client.get(ORGS_URL, {"cost": ["low-cost"]})
    assert {r["slug"] for r in resp.data["results"]} == {"low"}


@pytest.mark.django_db
def test_representative_serializer_surfaces_org_details_and_days_left():
    """A rep carries no contact/location of its own — the API fills them in
    from the linked organization, and computes days_left from the expiry."""
    addr = _arizona_address()
    org = _make_org(
        "az-help",
        name="Arizona Immigration Help",
        phones=["+1-602-555-0100"],
        address=addr,
    )
    Representative.objects.create(
        name="Doe, Jane",
        provider_type="doj-accredited-rep",
        organization=org,
        dhs_only=True,
        accreditation_expiration=date.today() + timedelta(days=30),
        is_active=True,
    )

    row = APIClient().get(REPS_URL).data["results"][0]
    assert row["organization_name"] == "Arizona Immigration Help"
    assert row["organization_phone"] == "+1-602-555-0100"
    assert row["city"] == "Phoenix"
    assert row["state"] == "Arizona"
    assert row["days_left"] == 30


@pytest.mark.django_db
def test_representatives_hide_expired_but_keep_undated():
    Representative.objects.create(
        name="Expired Rep", provider_type="doj-accredited-rep",
        accreditation_expiration=date.today() - timedelta(days=1), is_active=True,
    )
    Representative.objects.create(
        name="Future Rep", provider_type="doj-accredited-rep",
        accreditation_expiration=date.today() + timedelta(days=1), is_active=True,
    )
    Representative.objects.create(
        name="Undated Rep", provider_type="doj-accredited-rep", is_active=True,
    )

    resp = APIClient().get(REPS_URL)
    assert {r["name"] for r in resp.data["results"]} == {"Future Rep", "Undated Rep"}


@pytest.mark.django_db
def test_representatives_filter_region_expires_within_and_ordering():
    az = _arizona_address()
    az_org = _make_org("az-org", name="AZ Org", address=az)
    country = Country.objects.get(country_code="US")
    tx_sub = Subdivision.objects.create(code="US-TX", name="Texas", country=country)
    tx_addr = Address.objects.create(line1="1 Main", city="Austin", subdivision=tx_sub)
    tx_org = _make_org("tx-org", name="TX Org", address=tx_addr)

    today = date.today()
    Representative.objects.create(
        name="Soon AZ", provider_type="doj-accredited-rep", organization=az_org,
        accreditation_expiration=today + timedelta(days=10), is_active=True,
    )
    Representative.objects.create(
        name="Later AZ", provider_type="doj-accredited-rep", organization=az_org,
        accreditation_expiration=today + timedelta(days=200), is_active=True,
    )
    Representative.objects.create(
        name="Soon TX", provider_type="doj-accredited-rep", organization=tx_org,
        accreditation_expiration=today + timedelta(days=20), is_active=True,
    )

    client = APIClient()

    # region filters by the organization's state.
    resp = client.get(REPS_URL, {"region": "Arizona"})
    assert {r["name"] for r in resp.data["results"]} == {"Soon AZ", "Later AZ"}

    # expires_within drops the one outside the 90-day window.
    resp = client.get(REPS_URL, {"expires_within": "90"})
    assert {r["name"] for r in resp.data["results"]} == {"Soon AZ", "Soon TX"}

    # default ordering is soonest-to-expire first.
    resp = client.get(REPS_URL)
    assert [r["name"] for r in resp.data["results"]] == ["Soon AZ", "Soon TX", "Later AZ"]

    # ordering=name overrides it.
    resp = client.get(REPS_URL, {"ordering": "name"})
    assert [r["name"] for r in resp.data["results"]] == ["Later AZ", "Soon AZ", "Soon TX"]


# --- EOIR roster parser (build_ra_fixtures) -------------------------------
# The parser works on pre-clustered rows (lists of {"x0", "text"} words), so its
# wrapping / divider / malformed-data handling is testable without a real PDF.

from network.management.commands.build_ra_fixtures import (  # noqa: E402
    _iso,
    _norm_zip,
    parse_orgs,
    parse_reps,
)


def _w(x, text):
    return {"x0": float(x), "top": 0.0, "text": text}


def _row(*pairs):
    return [_w(x, t) for x, t in pairs]


# Column x-positions mirror the real rosters (org dates at 362+, rep cells at
# 38/126/192/276).
def _org_header(name_words, date="01/02/20"):
    return [_w(x, t) for x, t in name_words] + _row((362, date), (434, "01/02/26"), (506, "Active"))


def test_norm_zip_handles_malformed_codes():
    assert _norm_zip("85001") == "85001"
    assert _norm_zip("482102416") == "48210-2416"  # ZIP+4 without the hyphen
    assert _norm_zip("8611") == "08611"  # dropped leading zero
    assert _norm_zip("85001-1234") == "85001-1234"


def test_iso_pivots_two_digit_year():
    assert _iso("11", "01", "27") == "2027-11-01"
    assert _iso("01", "13", "96") == "1996-01-13"  # org recognition dates reach back


def test_parse_orgs_wrapped_name_and_multi_office_and_zip():
    rows = [
        _org_header([(38, "Very"), (70, "Long"), (120, "Org")]),
        _row((38, "Name"), (70, "Continued")),  # wrapped org name (no office keyword)
        _row((38, "Principal"), (72, "Office")),
        _row((38, "123"), (60, "Main"), (90, "St")),
        _row((38, "Detroit,"), (70, "MI"), (90, "482102416")),  # malformed ZIP+4
        _row((38, "(313)"), (60, "555-1000")),
        _row((38, "Very"), (70, "Long"), (120, "Org"), (170, "Name"), (200, "Continued")),  # divider
        _row((38, "Wayne"), (60, "Extension"), (100, "Office")),
        _row((38, "9"), (50, "Elm"), (70, "Ave")),
        _row((38, "Ferndale,"), (80, "MI"), (100, "48220")),
    ]
    orgs = parse_orgs(rows)

    assert len(orgs) == 1
    org = orgs[0]
    assert org["organization_name"] == "Very Long Org Name Continued"
    assert [a["address_name"] for a in org["addresses"]] == ["Principal Office", "Wayne Extension Office"]
    principal = org["addresses"][0]
    assert principal["line1"] == "123 Main St"
    assert principal["city"] == "Detroit"
    assert principal["postal_code"] == "48210-2416"  # normalized
    assert principal["phone_number"] == "(313) 555-1000"


def test_parse_orgs_stops_at_section_boundary():
    rows = [
        _org_header([(38, "Real"), (60, "Org")]),
        _row((38, "Principal"), (72, "Office")),
        _row((38, "1"), (50, "A"), (70, "St")),
        _row((38, "Reno,"), (70, "NV"), (90, "89501")),
        # The combined export's second section starts here.
        _row((38, "Recognized"), (280, "Accreditation"), (360, "Expiration")),
        _org_header([(38, "Ghost"), (60, "Org")]),
        _row((38, "Principal"), (72, "Office")),
    ]
    orgs = parse_orgs(rows)
    assert [o["organization_name"] for o in orgs] == ["Real Org"]


def test_parse_reps_wrapped_name_org_and_dhs_scope():
    rows = [
        _row((38, "F")),  # centered alphabetical divider — furniture
        _row((38, "Accredited"), (126, "Accreditation"), (180, "Expiration")),  # header — furniture
        _row((38, "Doe,"), (70, "Jane"), (126, "11/01/27"), (192, "Active"),
             (276, "Some"), (310, "Org"), (393, "01/01/20"), (453, "01/01/26"), (515, "Active")),
        _row((38, "(DHS"), (70, "only)"), (276, "Inc.")),  # wrapped name + org
        _row((38, "Roe,"), (70, "Ann"), (126, "05/18/26*"), (192, "Active"),
             (276, "Other"), (310, "Group"), (393, "02/02/22"), (453, "02/02/28"), (515, "Active")),
        _row((200, "Recognized"), (300, "Organization"), (360, "Address")),  # section boundary
        _row((38, "Ghost,"), (70, "Rep"), (126, "01/01/30"), (192, "Active"), (276, "Nope")),
    ]
    reps = parse_reps(rows, last_verified="2026-09-13")

    assert [r["name"] for r in reps] == ["Doe, Jane", "Roe, Ann"]
    doe = reps[0]
    assert doe["organization_name"] == "Some Org Inc."
    assert doe["dhs_only"] is True
    assert doe["accreditation_expiration"] == "2027-11-01"
    assert doe["last_verified"] == "2026-09-13"
    assert reps[1]["dhs_only"] is False  # no "(DHS only)" fragment


# --- extract_ra_reps command ----------------------------------------------

@pytest.mark.django_db
def test_extract_ra_reps_links_by_name_and_is_idempotent(monkeypatch):
    org = _make_org("firrp", name="Florence Immigrant and Refugee Rights Project")
    rows = [
        {
            "name": "Doe, Jane",
            "organization_name": "florence immigrant and refugee rights project",  # loose case
            "accreditation_expiration": "2027-11-01",
            "dhs_only": True,
            "status": "Active",
            "last_verified": "2026-09-13",
        }
    ]
    monkeypatch.setattr(
        "network.management.commands.extract_ra_reps._load_fixture", lambda: rows
    )
    call_command("extract_ra_reps", "--insert_to_db")
    call_command("extract_ra_reps", "--insert_to_db")  # idempotent

    reps = Representative.objects.all()
    assert reps.count() == 1
    rep = reps.get()
    assert rep.organization_id == org.id  # linked by normalized name
    assert rep.provider_type == "doj-accredited-rep"
    assert rep.dhs_only is True
    assert str(rep.accreditation_expiration) == "2027-11-01"
    assert rep.is_active is True


@pytest.mark.django_db
def test_extract_ra_reps_seeds_unlinked_when_org_absent(monkeypatch):
    rows = [
        {"name": "Solo, Rep", "organization_name": "An Org With No Listing",
         "status": "Active", "last_verified": "2026-09-13"}
    ]
    monkeypatch.setattr(
        "network.management.commands.extract_ra_reps._load_fixture", lambda: rows
    )
    call_command("extract_ra_reps", "--insert_to_db")

    rep = Representative.objects.get()
    assert rep.organization_id is None  # no matching org, still seeded
    assert rep.is_active is True


# --- download_ra_rosters command ------------------------------------------

def test_download_ra_rosters_matches_links_by_text(tmp_path, monkeypatch):
    page = """
      <a href="/eoir/media/1/dl?inline">Organizations and Representatives, Listed by State</a>
      <a href="/media/2/dl?inline">Accredited Representatives List</a>
      <a href="/media/3/dl?inline">Recognized Organizations List</a>
      <a href="http://twitter.com/x">Share</a>
    """

    def fake_fetch(url):
        return page.encode() if url.endswith("roster-reports") else b"%PDF-1.7 stub"

    monkeypatch.setattr(
        "network.management.commands.download_ra_rosters._fetch", fake_fetch
    )
    call_command("download_ra_rosters", "--raw-dir", str(tmp_path))

    # Only the two rosters the parser needs are saved (the org-by-rep list and
    # non-roster social links are skipped).
    saved = sorted(p.name for p in tmp_path.glob("*.pdf"))
    assert saved == [
        "raroster-reps.pdf",
        "recognized_org_and_accredited_rep_roster_by_state_and_city.pdf",
    ]
    assert (tmp_path / "raroster-reps.pdf").read_bytes().startswith(b"%PDF")
