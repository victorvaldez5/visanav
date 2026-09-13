#!/usr/bin/env bash
set -e

# Apply database migrations
python manage.py migrate --no-input

# Collect static files
python manage.py collectstatic --no-input

# Create superuser if it doesn't exist (uses env vars: DJANGO_SUPERUSER_USERNAME, DJANGO_SUPERUSER_EMAIL, DJANGO_SUPERUSER_PASSWORD)
python - <<'PYCODE'
import os
from django.core.management import execute_from_command_line

# Ensure Django is setup
os.environ.setdefault("DJANGO_SETTINGS_MODULE", os.environ.get("DJANGO_SETTINGS_MODULE", "api_project.prod"))
execute_from_command_line(["manage.py", "shell", "-c", ""])

import django
django.setup()

from django.contrib.auth import get_user_model
User = get_user_model()

username = os.getenv("DJANGO_SUPERUSER_USERNAME")
email = os.getenv("DJANGO_SUPERUSER_EMAIL")
password = os.getenv("DJANGO_SUPERUSER_PASSWORD")

if username and email and password:
    if not User.objects.filter(username=username).exists():
        User.objects.create_superuser(username=username, email=email, password=password)
else:
    # If any var missing, skip silently (avoids crashing on cold starts)
    pass
PYCODE

# Finally, launch the passed command (Gunicorn by default)
exec "$@"

# Finally, launch the passed command (Gunicorn by default)
exec "$@"
