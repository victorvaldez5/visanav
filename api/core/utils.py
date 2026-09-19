import json
import logging
import urllib.parse
import urllib.request

from django.conf import settings

logger = logging.getLogger(__name__)

TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


def per_user_cache_key(base, user):
    """Returns a cache key built from a base name and user (or 'anon')."""
    user_part = getattr(user, "id", None) or "anon"
    return f"{base}:{user_part}"


def client_ip(request):
    """Best-effort client IP. Behind Railway's proxy the real address is the
    first hop of X-Forwarded-For; fall back to REMOTE_ADDR."""
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def verify_turnstile(token, remoteip=None):
    """Validate a Cloudflare Turnstile token against Cloudflare's siteverify API.

    - No secret configured -> returns True (protection disabled), so local dev,
      tests, and CI run without Turnstile.
    - Empty token with a secret set -> False.
    - Transport/parse error -> fails OPEN (True) and logs: we'd rather not block
      real people during a Cloudflare hiccup, and the honeypot + throttle still
      apply. A definitive negative from Cloudflare fails CLOSED (False).
    """
    secret = getattr(settings, "TURNSTILE_SECRET_KEY", "")
    if not secret:
        return True
    if not token:
        return False

    data = {"secret": secret, "response": token}
    if remoteip:
        data["remoteip"] = remoteip
    body = urllib.parse.urlencode(data).encode()
    request = urllib.request.Request(TURNSTILE_VERIFY_URL, data=body, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=5) as resp:
            result = json.loads(resp.read().decode())
    except Exception as exc:  # network / timeout / bad JSON
        logger.warning("Turnstile verification unavailable, allowing: %s", exc)
        return True
    return bool(result.get("success"))


def assert_turnstile(token, request, field="turnstile_token"):
    """DRF helper: raise a ValidationError if the Turnstile token is invalid.

    A no-op when TURNSTILE_SECRET_KEY is unset (dev/CI/tests). Call from a
    serializer's validate(); imported here to keep the check identical across
    the intake form, registration, and login."""
    from rest_framework import serializers as drf_serializers

    if not getattr(settings, "TURNSTILE_SECRET_KEY", ""):
        return
    remoteip = client_ip(request) if request is not None else None
    if not verify_turnstile(token, remoteip):
        raise drf_serializers.ValidationError(
            {field: "Bot verification failed. Please try again."}
        )
