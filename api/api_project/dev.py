import os

from .base import *

# Development defaults
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-secret-key-change-me")
DEBUG = True
ALLOWED_HOSTS = ["*"]

# Open CORS in dev for ease of testing
CORS_ALLOW_ALL_ORIGINS = True

# Emails to console in dev
MAILTRAP_API_KEY = os.environ.get("MAILTRAP_API_KEY")
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:3000")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "DEBUG"},
}
