"""Request-level tests for the accounts auth API: registration, login (token
obtain), token refresh, and the self-scoped User/Profile viewsets.

Notes:
- Registration sends a verification email through Mailtrap — a live network call.
  The autouse ``stub_verification_email`` fixture replaces it with a Mock so these
  tests never touch the network (and can assert it was invoked).
- Turnstile is a no-op here: ``TURNSTILE_SECRET_KEY`` is unset in the test
  settings, so ``assert_turnstile`` returns immediately (see core/utils.py).
- List endpoints are paginated (StandardResultsSetPagination), so rows live under
  ``results``; ``_rows`` unwraps either shape.
"""
import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from accounts import views as account_views
from accounts.models import Profile
from locations.models import Country, Language, Subdivision

pytestmark = pytest.mark.django_db

User = get_user_model()
PW = "Sup3r-Secret-Pw!"

REGISTER_URL = reverse("register_view")
TOKEN_URL = reverse("token_obtain_pair")
REFRESH_URL = reverse("token_refresh")
USERS_URL = reverse("user-list")
PROFILES_URL = reverse("profile-list")


def _rows(resp):
    data = resp.json()
    return data["results"] if isinstance(data, dict) and "results" in data else data


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture(autouse=True)
def stub_verification_email(monkeypatch):
    """RegisterView.create() emails via Mailtrap (a real network call). Swap it
    for a Mock so registration tests stay offline and can assert it fired."""
    import unittest.mock as mock

    sent = mock.Mock()
    monkeypatch.setattr(account_views, "send_verification_email", sent)
    return sent


@pytest.fixture(autouse=True)
def clear_cache():
    """DRF throttles + the conversation-list cache share the per-process
    LocMemCache; isolate every test from throttle/cache bleed."""
    from django.core.cache import cache

    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def user(django_user_model):
    return django_user_model.objects.create_user(
        username="ana@example.com", email="ana@example.com", password=PW
    )


@pytest.fixture
def other_user(django_user_model):
    return django_user_model.objects.create_user(
        username="beto@example.com", email="beto@example.com", password=PW
    )


# --- registration ------------------------------------------------------------


def test_register_creates_user_with_profile_and_returns_tokens(api_client, stub_verification_email):
    resp = api_client.post(
        REGISTER_URL,
        {"email": "new@example.com", "password": PW, "password2": PW},
        format="json",
    )

    assert resp.status_code == status.HTTP_201_CREATED
    assert resp.data["email"] == "new@example.com"
    # The client needs to be logged in straight away, so tokens come back.
    assert resp.data["access"]
    assert resp.data["refresh"]

    created = User.objects.get(email="new@example.com")
    assert created.check_password(PW)  # password is hashed, not stored raw
    assert Profile.objects.filter(user=created).exists()  # profile auto-created
    stub_verification_email.assert_called_once_with(created)


def test_register_rejects_duplicate_email(api_client, user):
    resp = api_client.post(
        REGISTER_URL,
        {"email": user.email, "password": PW, "password2": PW},
        format="json",
    )

    assert resp.status_code == status.HTTP_400_BAD_REQUEST
    assert "email" in resp.data
    assert User.objects.filter(email=user.email).count() == 1


def test_register_rejects_mismatched_passwords(api_client):
    resp = api_client.post(
        REGISTER_URL,
        {"email": "mismatch@example.com", "password": PW, "password2": "different!"},
        format="json",
    )

    assert resp.status_code == status.HTTP_400_BAD_REQUEST
    assert not User.objects.filter(email="mismatch@example.com").exists()


def test_register_rejects_weak_password(api_client):
    # Fails Django's Numeric + MinimumLength validators (see AUTH_PASSWORD_VALIDATORS).
    resp = api_client.post(
        REGISTER_URL,
        {"email": "weak@example.com", "password": "12345678", "password2": "12345678"},
        format="json",
    )

    assert resp.status_code == status.HTTP_400_BAD_REQUEST
    assert not User.objects.filter(email="weak@example.com").exists()


# --- login / token refresh ---------------------------------------------------


def test_login_returns_access_and_refresh(api_client, user):
    resp = api_client.post(
        TOKEN_URL, {"username": user.username, "password": PW}, format="json"
    )

    assert resp.status_code == status.HTTP_200_OK
    assert resp.data["access"]
    assert resp.data["refresh"]


def test_login_rejects_wrong_password(api_client, user):
    resp = api_client.post(
        TOKEN_URL, {"username": user.username, "password": "wrong-password"}, format="json"
    )

    assert resp.status_code == status.HTTP_401_UNAUTHORIZED


def test_refresh_issues_a_new_access_token(api_client, user):
    login = api_client.post(
        TOKEN_URL, {"username": user.username, "password": PW}, format="json"
    )
    refresh = login.data["refresh"]

    resp = api_client.post(REFRESH_URL, {"refresh": refresh}, format="json")

    assert resp.status_code == status.HTTP_200_OK
    assert resp.data["access"]


# --- UserViewSet (self-scoped) -----------------------------------------------


def test_users_endpoint_requires_authentication(api_client):
    assert api_client.get(USERS_URL).status_code == status.HTTP_401_UNAUTHORIZED


def test_users_endpoint_returns_only_the_requesting_user(api_client, user, other_user):
    api_client.force_authenticate(user=user)

    rows = _rows(api_client.get(USERS_URL))

    assert [r["email"] for r in rows] == [user.email]


# --- ProfileViewSet (self-scoped) --------------------------------------------


def test_profiles_endpoint_requires_authentication(api_client):
    assert api_client.get(PROFILES_URL).status_code == status.HTTP_401_UNAUTHORIZED


def test_profiles_endpoint_returns_only_the_requesting_users_profile(api_client, user, other_user):
    api_client.force_authenticate(user=user)

    rows = _rows(api_client.get(PROFILES_URL))

    # Only the caller's own profile is visible, not other_user's.
    assert len(rows) == 1


def test_profile_partial_update_routes_profile_and_user_fields(api_client, user):
    # A fully-populated profile: the view's hand-built response reads the locale
    # FKs (country/subdivision/preferred_language), so they must be set.
    usa = Country.objects.create(name="United States", country_code="US")
    ca = Subdivision.objects.create(name="California", code="CA", country=usa)
    en = Language.objects.create(name="English", code="en")
    profile = user.profile
    profile.country = usa
    profile.subdivision = ca
    profile.preferred_language = en
    profile.save()

    api_client.force_authenticate(user=user)
    url = reverse("profile-detail", kwargs={"pk": profile.pk})

    # notify_marketing -> Profile; first_name -> User. partial_update splits them.
    resp = api_client.patch(url, {"notify_marketing": True, "first_name": "Ana"}, format="json")

    assert resp.status_code == status.HTTP_200_OK
    assert resp.data["notify_marketing"] is True
    assert resp.data["first_name"] == "Ana"
    assert resp.data["country"] == "US"

    profile.refresh_from_db()
    user.refresh_from_db()
    assert profile.notify_marketing is True
    assert user.first_name == "Ana"
