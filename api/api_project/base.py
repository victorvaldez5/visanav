import base64
import hashlib
import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
# Environment lives in the repo-root config/ directory (see config/.env.example).
load_dotenv(BASE_DIR.parent / "config" / ".env")
# Secure-by-default: base is locked down and dev.py opens things up. This way a
# misconfigured DJANGO_SETTINGS_MODULE (or a new settings module that forgets to
# override) never accidentally ships DEBUG/open hosts/open CORS. prod.py hardens
# further and requires a real secret key.
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-secret-key-change-me")
DEBUG = False
ALLOWED_HOSTS = []

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    "rest_framework",
    "django_filters",
    "phonenumber_field",
    "corsheaders",
    "accounts",
    "conversation",
    "locations",
    "network",
    'core',
    "knowledge",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",  # admin needs CSRF
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
]

AUTH_USER_MODEL = "accounts.User"

ROOT_URLCONF = "api_project.urls"

# Minimal template config (admin needs this)
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],  # add your own template dirs here if needed
        "APP_DIRS": True,  # loads admin templates
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "api_project.wsgi.application"
ASGI_APPLICATION = "api_project.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("POSTGRES_DB"),
        "USER": os.environ.get("POSTGRES_USER"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD"),
        "HOST": os.environ.get("POSTGRES_HOST", "0.0.0.0"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
    }
}

# Local in-process cache. The app no longer depends on Redis: chat runs
# synchronously in an async streaming view instead of a Celery worker. This
# cache is per-process, which is fine for the light use it gets (conversation
# list caching, soft chat rate limiting).
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "TIMEOUT": 60,
        "KEY_PREFIX": "api",
    }
}

# Global TTL for middleware caching (can be different from CACHES['default'].TIMEOUT)
CACHE_MIDDLEWARE_SECONDS = 60  # start small;

# Soft per-client rate limit on the chat endpoint (requests/minute) to cap
# LLM spend. 0 disables it. Pair with a hard monthly budget at the LLM provider.
# `... or "<default>"` so a var present-but-blank (e.g. a freshly copied
# .env.example) falls back to the default instead of crashing int("") at boot.
CHAT_RATE_LIMIT_PER_MINUTE = int(os.environ.get("CHAT_RATE_LIMIT_PER_MINUTE") or "10")
# Hard cap on a single chat message so one request can't burn a huge prompt.
CHAT_MAX_MESSAGE_CHARS = int(os.environ.get("CHAT_MAX_MESSAGE_CHARS") or "4000")

# ── Logging: privacy-first ───────────────────────────────────────────────────
# VisaNav serves a vulnerable population, so logs must NEVER contain the text of
# a user's question or the model's answer. Two rules enforce that:
#   1. Application code logs only content-free diagnostics — request ids, latency,
#      error codes, retrieval scores, retrieved document ids. It never logs
#      message text, the (model-generated) search query, IP addresses, or user
#      agents. (The chat endpoint uses the client IP only as an in-memory
#      rate-limit key; abuse events log a salted hash of it, never the raw IP.)
#   2. Third-party HTTP/LLM clients that CAN dump full request/response bodies
#      (the Anthropic/OpenAI SDKs, httpx, urllib3) are pinned to a floor at/above
#      INFO here, so raising the root level to DEBUG to troubleshoot can never
#      leak prompt or completion content through them, and neither can an
#      ANTHROPIC_LOG=debug / OPENAI_LOG=debug env var.
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "standard"},
    },
    "root": {"handlers": ["console"], "level": LOG_LEVEL},
    "loggers": {
        # These emit full HTTP request/response bodies — which include the user's
        # message and the model's reply — when their level is DEBUG. Pin them so
        # that never happens regardless of the root level.
        "anthropic": {"level": "INFO", "propagate": True},
        "openai": {"level": "INFO", "propagate": True},
        "httpx": {"level": "WARNING", "propagate": True},
        "httpcore": {"level": "WARNING", "propagate": True},
        "urllib3": {"level": "WARNING", "propagate": True},
    },
}

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
PHONENUMBER_DEFAULT_REGION = "US"

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"  # for collectstatic (production)
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"
# DRF Settings
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PAGINATION_CLASS": "core.pagination.StandardResultsSetPagination",
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {"anon": "1000/day", "user": "10000/day"},
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=10),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
}

CORS_ALLOW_ALL_ORIGINS = False  # dev.py opens this; prod.py keeps it locked

# MAILTRAP SETTINGS
MAILTRAP_API_KEY = os.environ.get("MAILTRAP_API_KEY")
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:3000")

# VECTOR STORE / EMBEDDINGS (pgvector + Voyage AI)
# Retrieval lives in Postgres (pgvector); embeddings are generated explicitly on
# both ingest and query by core/embeddings.py. Pinecone (which embedded
# server-side) has been removed.
#
# Embedding provider + model. voyage-3 and voyage-law-2 are both 1024-dim, so
# EMBEDDING_MODEL can be swapped between them with only a re-embed. EMBEDDING_DIM
# is fixed to the KnowledgeChunk.embedding column type — changing it needs a
# schema migration + full re-embed, so it lives here only as documentation/guard.
EMBEDDING_PROVIDER = os.environ.get("EMBEDDING_PROVIDER", "voyage").lower()
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "voyage-3")
EMBEDDING_DIM = int(os.environ.get("EMBEDDING_DIM") or "1024")
VOYAGE_API_KEY = os.environ.get("VOYAGE_API_KEY")
# Country whose curated corpus the chat agent searches. Replaces the old Pinecone
# namespace; matches KnowledgeChunk.country rows written by `manage.py ingest`.
KNOWLEDGE_COUNTRY = os.environ.get("KNOWLEDGE_COUNTRY", "us")
# Where the ingest command reads curated Markdown from. Defaults to the repo's
# data/countries (reachable from a full checkout; ingestion is not run in the
# slim prod web image).
KNOWLEDGE_DATA_DIR = os.environ.get("KNOWLEDGE_DATA_DIR") or str(
    BASE_DIR.parent / "data" / "countries"
)

# OPEN_AI_SETTINGS
OPEN_AI_API_KEY = os.environ.get("OPEN_AI_API_KEY")

# ANTHROPIC / CLAUDE SETTINGS
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")

# LLM provider for the chat agent: "anthropic" | "openai".
# Defaults to Anthropic (Claude). The model name has a per-provider default in
# core/llm.py and can be overridden with CHAT_MODEL.
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "anthropic").lower()
CHAT_MODEL = os.environ.get("CHAT_MODEL")

# ── Conversation privacy: retention + at-rest encryption ─────────────────────
# Auto-delete windows (in days) enforced by the `purge_expired_conversations`
# management command. Retention is measured from the last message and refreshed
# each turn, so an active chat stays alive and an abandoned one ages out. A
# value of 0 (or blank) disables auto-expiry for that class of conversation.
#   - Anonymous chats keep nothing tied to an account; expire them quickly.
#   - Signed-in chats age out too, UNLESS the user opts into keeping their
#     history (accounts.Profile.retain_history), which sets expires_at = NULL.
CONVERSATION_ANON_RETENTION_DAYS = int(
    os.environ.get("CONVERSATION_ANON_RETENTION_DAYS") or "7"
)
CONVERSATION_USER_RETENTION_DAYS = int(
    os.environ.get("CONVERSATION_USER_RETENTION_DAYS") or "30"
)

# Fernet key(s) encrypting conversation content at rest (core/encryption.py).
# Comma-separated: the first encrypts, all are tried on decrypt, so rotate by
# prepending a new key and re-saving rows. In prod this MUST be set explicitly
# (prod.py fails to boot otherwise). In dev/CI/tests, rather than committing any
# key material, derive a deterministic throwaway key from the (already public,
# non-secret) dev SECRET_KEY — so local runs need zero setup and nothing
# key-shaped lives in the repo. Generate a real prod key with:
#   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
CONVERSATION_ENCRYPTION_KEYS = os.environ.get("CONVERSATION_ENCRYPTION_KEYS") or (
    base64.urlsafe_b64encode(
        hashlib.sha256(f"conversation-fernet-dev:{SECRET_KEY}".encode()).digest()
    ).decode()
)
