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
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework import status
from rest_framework.test import APIClient

from accounts import views as account_views
from accounts.models import Profile
from locations.models import Country, Language, Subdivision

pytestmark = pytest.mark.django_db

User = get_user_model()
PW = "Sup3r-Secret-Pw!"

REGISTER_URL = reverse("register_view")
VERIFY_URL = reverse("verify_email")
TOKEN_URL = reverse("token_obtain_pair")
REFRESH_URL = reverse("token_refresh")
USERS_URL = reverse("user-list")
PROFILES_URL = reverse("profile-list")


def _verify_payload(user):
    """The uid/token pair the emailed verification link carries (see
    core/mail.send_verification_email)."""
    return {
        "uid": urlsafe_base64_encode(force_bytes(str(user.pk))),
        "token": PasswordResetTokenGenerator().make_token(user),
    }


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


@pytest.fixture
def inactive_user(django_user_model):
    """A freshly-registered, not-yet-verified account."""
    user = django_user_model.objects.create_user(
        username="pending@example.com", email="pending@example.com", password=PW
    )
    user.is_active = False
    user.save(update_fields=["is_active"])
    return user


# --- registration ------------------------------------------------------------


def test_register_creates_inactive_user_and_sends_verification(api_client, stub_verification_email):
    resp = api_client.post(
        REGISTER_URL,
        {"email": "new@example.com", "password": PW, "password2": PW},
        format="json",
    )

    assert resp.status_code == status.HTTP_201_CREATED
    assert resp.data["email"] == "new@example.com"
    assert resp.data["detail"]  # "check your email" message
    # No session is issued until the email is verified.
    assert "access" not in resp.data
    assert "refresh" not in resp.data

    created = User.objects.get(email="new@example.com")
    assert created.is_active is False  # gated until verification
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


def test_inactive_user_cannot_log_in(api_client, inactive_user):
    # SimpleJWT's default USER_AUTHENTICATION_RULE rejects inactive accounts.
    resp = api_client.post(
        TOKEN_URL, {"username": inactive_user.username, "password": PW}, format="json"
    )
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED


# --- email verification ------------------------------------------------------


def test_verify_activates_account_and_returns_session(api_client, inactive_user):
    resp = api_client.post(VERIFY_URL, _verify_payload(inactive_user), format="json")

    assert resp.status_code == status.HTTP_200_OK
    assert resp.data["userId"] == inactive_user.id
    assert resp.data["access"]
    assert resp.data["refresh"]

    inactive_user.refresh_from_db()
    assert inactive_user.is_active is True
    assert inactive_user.is_verified is True

    # Verification unblocks login.
    login = api_client.post(
        TOKEN_URL, {"username": inactive_user.username, "password": PW}, format="json"
    )
    assert login.status_code == status.HTTP_200_OK


def test_verify_tokens_carry_the_same_identity_claims_as_login(api_client, inactive_user):
    """The app labels the signed-in user from the token's username/email claims, so a
    session started by the emailed link must carry them just like a password login."""
    from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

    resp = api_client.post(VERIFY_URL, _verify_payload(inactive_user), format="json")

    for token in (AccessToken(resp.data["access"]), RefreshToken(resp.data["refresh"])):
        assert token["username"] == inactive_user.username
        assert token["email"] == inactive_user.email


def test_verify_rejects_a_bad_token(api_client, inactive_user):
    payload = {
        "uid": urlsafe_base64_encode(force_bytes(str(inactive_user.pk))),
        "token": "not-a-valid-token",
    }
    resp = api_client.post(VERIFY_URL, payload, format="json")

    assert resp.status_code == status.HTTP_400_BAD_REQUEST
    inactive_user.refresh_from_db()
    assert inactive_user.is_active is False  # nothing was activated


def test_verify_rejects_a_malformed_uid(api_client):
    resp = api_client.post(VERIFY_URL, {"uid": "!!not-base64!!", "token": "x"}, format="json")
    assert resp.status_code == status.HTTP_400_BAD_REQUEST


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


# ── preferred_language (the UI locale write-through) ──────────────────────────


@pytest.fixture
def locale_languages():
    return (
        Language.objects.create(name="English", code="en"),
        Language.objects.create(name="Spanish", code="es"),
        Language.objects.create(name="French", code="fr"),  # a row, but not allowlisted
    )


def test_profile_patch_with_only_preferred_language(api_client, user, locale_languages):
    # The language switcher PATCHes just this one field, on a profile with no
    # country/subdivision yet. That used to 500 on the hand-built response.
    api_client.force_authenticate(user=user)
    url = reverse("profile-detail", kwargs={"pk": user.profile.pk})

    resp = api_client.patch(url, {"preferred_language": "es"}, format="json")

    assert resp.status_code == status.HTTP_200_OK
    assert resp.data["preferred_language"] == "es"
    assert resp.data["country"] is None
    assert resp.data["email"] == user.email
    user.profile.refresh_from_db()
    assert user.profile.preferred_language_id == "es"


def test_profile_rejects_a_language_outside_the_allowlist(api_client, user, locale_languages):
    api_client.force_authenticate(user=user)
    url = reverse("profile-detail", kwargs={"pk": user.profile.pk})

    resp = api_client.patch(url, {"preferred_language": "fr"}, format="json")

    assert resp.status_code == status.HTTP_400_BAD_REQUEST
    assert "preferred_language" in resp.data


def test_profile_preferred_language_can_be_cleared(api_client, user, locale_languages):
    profile = user.profile
    profile.preferred_language = locale_languages[1]
    profile.save()
    api_client.force_authenticate(user=user)
    url = reverse("profile-detail", kwargs={"pk": profile.pk})

    resp = api_client.patch(url, {"preferred_language": None}, format="json")

    assert resp.status_code == status.HTTP_200_OK
    assert resp.data["preferred_language"] is None


def test_profile_patch_is_atomic_across_user_and_profile(api_client, user, locale_languages):
    # An invalid user field must not leave the profile half-saved.
    api_client.force_authenticate(user=user)
    url = reverse("profile-detail", kwargs={"pk": user.profile.pk})

    resp = api_client.patch(url, {"preferred_language": "es", "email": "not-an-email"}, format="json")

    assert resp.status_code == status.HTTP_400_BAD_REQUEST
    user.profile.refresh_from_db()
    assert user.profile.preferred_language_id is None
