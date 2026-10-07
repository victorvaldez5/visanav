#!/usr/bin/env bash
set -e

# Apply database migrations on boot. On Railway, the service's pre-deploy command (.railway/railway.ts)
# runs `migrate` instead (once per release, before the new version takes
# traffic, and a failed migration blocks the deploy), so the service sets
# SKIP_MIGRATE_ON_START=1 to avoid migrating again on every cold start. Locally
# and anywhere the var is unset this still migrates on boot; migrate is
# idempotent, so running it in both places is harmless.
if [ "${SKIP_MIGRATE_ON_START:-}" = "1" ]; then
  echo "SKIP_MIGRATE_ON_START=1: skipping migrate (handled by the pre-deploy command)."
else
  python manage.py migrate --no-input
fi

# Optionally seed the public-resources directory. The seed commands are
# idempotent (upsert + cross-source dedup), so this is safe to leave on, but it
# is gated behind SEED_DIRECTORY=1 to keep normal boots fast. Order matters:
# load_resources first so curated data/ rows win, then the DOJ org rosters enrich
# them, and finally the accredited-rep roster links to the seeded orgs. Seeding
# failure is non-fatal — the web process still starts.
if [ "${SEED_DIRECTORY:-}" = "1" ]; then
  echo "SEED_DIRECTORY=1: seeding public-resources directory..."
  python manage.py load_resources "${SEED_COUNTRY:-us}" \
    && python manage.py extract_ra_orgs --insert_to_db \
    && python manage.py extract_probono --insert_to_db \
    && python manage.py extract_ra_reps --insert_to_db \
    || echo "WARNING: directory seeding failed; continuing boot."
fi

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
