import os

from .base import *

# Development defaults
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-secret-key-change-me")
DEBUG = True
ALLOWED_HOSTS = ["*"]

# Open CORS in dev for ease of testing
CORS_ALLOW_ALL_ORIGINS = True

# Dev never delivers real mail: it goes to the team's Mailtrap sandbox inbox
# unless MAILTRAP_SANDBOX_INBOX_ID names another one.
MAILTRAP_API_KEY = os.environ.get("MAILTRAP_API_KEY")
MAILTRAP_SANDBOX_INBOX_ID = os.environ.get("MAILTRAP_SANDBOX_INBOX_ID") or "3972833"
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:3000")

# Verbose app logs in dev, but keep base.py's third-party logger floors so even a
# DEBUG root never dumps LLM request/response bodies (see base.py LOGGING).
LOGGING["root"]["level"] = "DEBUG"
