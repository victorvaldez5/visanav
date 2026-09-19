from django.core.exceptions import ImproperlyConfigured

from .base import *


def required_env(name: str) -> str:
    val = os.environ.get(name)
    if not val:
        raise ImproperlyConfigured(f"Missing required environment variable: {name}")
    return val


DEBUG = False
SECRET_KEY = required_env("DJANGO_SECRET_KEY")

# Hosts and CSRF
ALLOWED_HOSTS = [h for h in os.environ.get("ALLOWED_HOSTS", "").split(",") if h]
if not ALLOWED_HOSTS:
    raise ImproperlyConfigured("ALLOWED_HOSTS must be set (comma-separated).")

CSRF_TRUSTED_ORIGINS = [
    o for o in os.environ.get("CSRF_TRUSTED_ORIGINS", "").split(",") if o
]

# Database: PostgreSQL from env
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": required_env("POSTGRES_DB"),
        "USER": required_env("POSTGRES_USER"),
        "PASSWORD": required_env("POSTGRES_PASSWORD"),
        "HOST": os.environ.get("POSTGRES_HOST", "localhost"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
        "CONN_MAX_AGE": int(os.environ.get("PG_CONN_MAX_AGE", "60")),
        "OPTIONS": {
            # Example: enable SSL if your provider requires it
            "sslmode": os.environ.get("POSTGRES_SSLMODE", "require"),
        },
    }
}

# Security hardening
SECURE_SSL_REDIRECT = os.environ.get("SECURE_SSL_REDIRECT", "true").lower() == "true"
SESSION_COOKIE_SECURE = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True  # if you do host canonicalization
CSRF_COOKIE_SECURE = True

SECURE_HSTS_SECONDS = int(os.environ.get("SECURE_HSTS_SECONDS", "31536000"))  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

# CORS: lock down to explicit origins
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = [
    o for o in os.environ.get("CSRF_TRUSTED_ORIGINS", "").split(",") if o
]
CORS_ALLOW_CREDENTIALS = True

# Static files via WhiteNoise (already configured in base)
# Ensure you run `collectstatic` during deployment

# Logging: the shared, privacy-first config in base.py (console handler, root at
# LOG_LEVEL, and third-party LLM/HTTP loggers pinned so bodies never leak) is
# already container-friendly, so prod inherits it unchanged.

# Email (configure your SMTP in env, else fail loudly)
# EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
# EMAIL_HOST = required_env("EMAIL_HOST")
# EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
# EMAIL_HOST_USER = required_env("EMAIL_HOST_USER")
# EMAIL_HOST_PASSWORD = required_env("EMAIL_HOST_PASSWORD")
# EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "true").lower() == "true"
# DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", EMAIL_HOST_USER)

# Optionally, tighten DRF default permissions in prod:
REST_FRAMEWORK["DEFAULT_PERMISSION_CLASSES"] = (
    "rest_framework.permissions.IsAuthenticated",
)

# Conversation content is encrypted at rest (core/encryption.py). Require an
# explicit key in production — base.py's dev fallback is derived from the public
# dev SECRET_KEY and must never protect real data. Losing this key makes every
# stored conversation unreadable, so back it up.
CONVERSATION_ENCRYPTION_KEYS = required_env("CONVERSATION_ENCRYPTION_KEYS")
