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
    # Negotiates the active language from the request's Accept-Language header
    # (the frontends set it explicitly from the active UI locale) into
    # request.LANGUAGE_CODE, and activates gettext for the response. Django
    # requires it after SessionMiddleware and before CommonMiddleware. We do NOT
    # use i18n_patterns, so it performs no URL-prefix redirects.
    "django.middleware.locale.LocaleMiddleware",
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
        # localhost = the compose db's published port, for commands run on the
        # host; docker-compose sets POSTGRES_HOST=db for the api container.
        "HOST": os.environ.get("POSTGRES_HOST", "localhost"),
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

# Per-turn agent budget. One chat turn drives an autonomous tool-calling loop, so
# a crafted prompt (or a model that gets stuck re-calling a tool) could otherwise
# spend unbounded model requests/tokens. These cap a SINGLE agent run; pair them
# with CHAT_RATE_LIMIT_PER_MINUTE (across turns) and a hard monthly cap at the
# provider. 0 disables a given limit. `... or "<default>"` guards a blank env var.
CHAT_REQUEST_LIMIT = int(os.environ.get("CHAT_REQUEST_LIMIT") or "6")
CHAT_TOOL_CALLS_LIMIT = int(os.environ.get("CHAT_TOOL_CALLS_LIMIT") or "8")
CHAT_TOTAL_TOKENS_LIMIT = int(os.environ.get("CHAT_TOTAL_TOKENS_LIMIT") or "60000")
# Cap the length of a model-generated tool argument (search query, region,
# service) before it reaches Voyage or the ORM, so a runaway or adversarial tool
# call can't embed a giant string or probe with absurd inputs.
CHAT_TOOL_ARG_MAX_CHARS = int(os.environ.get("CHAT_TOOL_ARG_MAX_CHARS") or "512")

# ── Logging: privacy-first ───────────────────────────────────────────────────
# VisaNav serves a vulnerable population, so logs must NEVER contain the text of
# a user's question or the model's answer. Two rules enforce that:
#   1. Application code logs only content-free diagnostics — request ids, latency,
#      error codes, retrieval scores, retrieved document ids. It never logs
#      message text, the (model-generated) search query, IP addresses, or user
#      agents. (The chat endpoint uses the client IP only as an in-memory
#      rate-limit key; abuse events log a salted hash of it, never the raw IP.)
#   2. The Anthropic/OpenAI SDKs and the HTTP clients they use log the request
#      body (which contains the user's message and the model's reply) at DEBUG.
#      They are pinned to an INFO/WARNING floor below, so raising the root level
#      to DEBUG to troubleshoot can never leak prompt/completion content through
#      them. The one bypass is the SDKs' own ANTHROPIC_LOG / OPENAI_LOG=debug env
#      vars, which force their own loggers to DEBUG at import — so never set those
#      in any environment that handles real user data.
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
        # The LLM SDKs log the request body (user message + model reply) via
        # `log.debug("Request options: ...")` under their own logger; pinning to
        # INFO drops that DEBUG line regardless of the root level. The HTTP
        # clients log request URLs/lifecycle (not bodies) — quieted for cleaner
        # logs. NOTE: the Anthropic SDK vendors its HTTP stack and logs it under
        # httpx2/httpcore2, not httpx/httpcore, so both spellings are pinned.
        "anthropic": {"level": "INFO", "propagate": True},
        "openai": {"level": "INFO", "propagate": True},
        "httpx": {"level": "WARNING", "propagate": True},
        "httpcore": {"level": "WARNING", "propagate": True},
        "httpx2": {"level": "WARNING", "propagate": True},
        "httpcore2": {"level": "WARNING", "propagate": True},
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

# Default locale: the "default" in /i18n/supported-locales.json, and one of
# LANGUAGES (CI checks both). LocaleMiddleware falls back to it when a request
# carries no supported Accept-Language.
LANGUAGE_CODE = "en"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
PHONENUMBER_DEFAULT_REGION = "US"

# Supported UI/content locales. Keep in sync with /i18n/supported-locales.json
# (CI enforces parity via scripts/check_i18n_parity.mjs). LocaleMiddleware maps
# every request onto one of these, so request.LANGUAGE_CODE is always a code
# listed here. locations.0004_populate_languages seeds the Language table from
# this setting only when it runs, so the list bounds that table on a NEW database
# only; existing databases keep the rows seeded before. See "Locale model" and
# "Adding a locale" in docs/i18n-architecture.md.
LANGUAGES = [
    ("en", "English"),
    ("es", "Spanish"),
]
# Where gettext catalogs (.po/.mo) live. Populated incrementally as user-facing
# strings get wrapped in gettext (_()); manage.py makemessages/compilemessages
# read and write here.
LOCALE_PATHS = [BASE_DIR / "locale"]

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
    "DEFAULT_THROTTLE_RATES": {"anon": "1000/day", "user": "10000/day", "submission": "20/day"},
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
# Retrieval confidence floor. semantic_search scores matches as cosine similarity
# in [0,1] (1 = identical). A match below this is treated as "not a confident
# official source": its text is withheld from the model and Javi must fall back
# to pointing at the official site / a representative rather than answering from
# general knowledge. 0.5 is a conservative starting point for voyage-3; tune it
# against the retrieval scores now logged by semantic_search (see core/llm.py).
RAG_MIN_SCORE = float(os.environ.get("RAG_MIN_SCORE") or "0.5")
# Where the ingest command reads curated Markdown from. Defaults to the repo's
# data/countries (reachable from a full checkout; ingestion is not run in the
# slim prod web image).
KNOWLEDGE_DATA_DIR = os.environ.get("KNOWLEDGE_DATA_DIR") or str(
    BASE_DIR.parent / "data" / "countries"
)

# Cloudflare Turnstile — bot protection on the public NGO intake form.
# Set the secret key in production; empty disables server-side verification so
# local dev, tests, and CI run without it. Pairs with PUBLIC_TURNSTILE_SITE_KEY
# on the marketing site (both must be real keys in prod, or both test keys).
TURNSTILE_SECRET_KEY = os.environ.get("TURNSTILE_SECRET_KEY", "")

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
