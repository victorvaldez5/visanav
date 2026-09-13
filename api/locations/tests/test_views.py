import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from api.locations.models import Country, Subdivision, Language, Address


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user(django_user_model):
    return django_user_model.objects.create_user(
        username="tester", email="tester@example.com", password="pass1234"
    )


@pytest.fixture
def auth_client(api_client, user):
    api_client.force_authenticate(user=user)
    return api_client


@pytest.fixture
def countries():
    usa = Country.objects.create(name="United States", country_code="US")
    can = Country.objects.create(name="Canada", country_code="CA")
    return usa, can


@pytest.fixture
def subdivisions(countries):
    usa, can = countries
    ca = Subdivision.objects.create(name="California", code="CA", country=usa)
    ny = Subdivision.objects.create(name="New York", code="NY", country=usa)
    on = Subdivision.objects.create(name="Ontario", code="ON", country=can)
    return ca, ny, on


@pytest.fixture
def languages():
    en = Language.objects.create(name="English", code="en")
    fr = Language.objects.create(name="French", code="fr")
    return en, fr


@pytest.fixture
def addresses(countries, subdivisions):
    usa, can = countries
    ca, ny, on = subdivisions
    a1 = Address.objects.create(
        line1="1 Main St", city="San Francisco", postal_code="94105", country=usa, subdivision=ca
    )
    a2 = Address.objects.create(
        line1="2 Broadway", city="New York", postal_code="10004", country=usa, subdivision=ny
    )
    a3 = Address.objects.create(
        line1="10 King St", city="Toronto", postal_code="M5H", country=can, subdivision=on
    )
    return a1, a2, a3


# Authentication required for all viewsets

@pytest.mark.parametrize(
    "urlname",
    [
        "country-list",
        "subdivision-list",
        "language-list",
        "address-list",
    ],
)
def test_requires_auth(api_client, urlname):
    url = reverse(urlname)
    resp = api_client.get(url)
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED


# Country

def test_country_list(auth_client, countries):
    url = reverse("country-list")
    resp = auth_client.get(url)
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 2
    assert {c["country_code"] for c in data} == {"US", "CA"}


# Subdivision

def test_subdivision_list(auth_client, subdivisions):
    url = reverse("subdivision-list")
    resp = auth_client.get(url)
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 3


def test_subdivision_filter_by_country_code_case_insensitive(auth_client, subdivisions):
    url = reverse("subdivision-list")
    resp = auth_client.get(url, {"country": "us"})
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    codes = {s["code"] for s in data}
    assert codes == {"CA", "NY"}  # Only US subdivisions


# Language

def test_language_list(auth_client, languages):
    url = reverse("language-list")
    resp = auth_client.get(url)
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert {l["code"] for l in data} == {"en", "fr"}


# Address

def test_address_list(auth_client, addresses):
    url = reverse("address-list")
    resp = auth_client.get(url)
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert len(data) == 3
    # spot-check fields existence
    sample = data[0]
    for key in ("line1", "city", "postal_code", "country", "subdivision"):
        assert key in sample


# Optional: retrieve endpoints if detail routes are registered

def test_country_retrieve(auth_client, countries):
    usa, _ = countries
    url = reverse("country-detail", args=[usa.id])
    resp = auth_client.get(url)
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json()["country_code"] == "US"


def test_subdivision_retrieve(auth_client, subdivisions):
    ca, _, _ = subdivisions
    url = reverse("subdivision-detail", args=[ca.id])
    resp = auth_client.get(url)
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json()["code"] == "CA"


def test_language_retrieve(auth_client, languages):
    en, _ = languages
    url = reverse("language-detail", args=[en.id])
    resp = auth_client.get(url)
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json()["code"] == "en"


def test_address_retrieve(auth_client, addresses):
    a1, _, _ = addresses
    url = reverse("address-detail", args=[a1.id])
    resp = auth_client.get(url)
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json()["line1"] == "1 Main St"
