import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv()
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-secret-key-change-me")
DEBUG = True
ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "django_filters",
    "phonenumber_field",
    "corsheaders",
    "accounts",
    "conversation",
    "locations",
    "network",
    'core',
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
# OpenAI spend. 0 disables it. Pair with a hard monthly budget in OpenAI.
CHAT_RATE_LIMIT_PER_MINUTE = int(os.environ.get("CHAT_RATE_LIMIT_PER_MINUTE", "10"))
# Hard cap on a single chat message so one request can't burn a huge prompt.
CHAT_MAX_MESSAGE_CHARS = int(os.environ.get("CHAT_MAX_MESSAGE_CHARS", "4000"))

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

CORS_ALLOW_ALL_ORIGINS = True

# MAILTRAP SETTINGS
MAILTRAP_API_KEY = os.environ.get("MAILTRAP_API_KEY")
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:3000")

# AWS SETTINGS
AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID")
AWS_SECRET_KEY = os.environ.get("AWS_SECRET_KEY")
AWS_S3_BUCKET = os.environ.get("AWS_S3_BUCKET")
AWS_REGION = os.environ.get("AWS_REGION")

# PINECONE SETTINGS
PINECONE_API_KEY = os.environ.get("PINECONE_API_KEY")
PINECONE_INDEX = os.environ.get("PINECONE_INDEX_HOST") or os.environ.get("INDEX_HOST")

# OPEN_AI_SETTINGS
OPEN_AI_API_KEY = os.environ.get("OPEN_AI_API_KEY")

# ANTHROPIC / CLAUDE SETTINGS
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")

# LLM provider for the chat agent: "anthropic" | "openai" | "bedrock".
# Defaults to Anthropic (Claude). The model name has a per-provider default in
# core/llm.py and can be overridden with CHAT_MODEL.
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "anthropic").lower()
CHAT_MODEL = os.environ.get("CHAT_MODEL")
