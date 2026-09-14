"""pytest fixtures/config for the API test suite.

pgvector gotcha: the suite runs `--no-migrations` (schema built from models via
syncdb), which skips the `VectorExtension` migration. So the `vector` type must
already exist in the test database before its tables are built. Postgres' CREATE
DATABASE inherits from template1, so we seed the extension into template1 in
pytest_configure — before pytest-django creates the test DB — and otherwise leave
pytest-django's own DB setup (which honors --no-migrations) untouched. Requires
the pgvector Postgres image.
"""
import psycopg2
import pytest


@pytest.hookimpl(trylast=True)  # after pytest-django's pytest_configure sets up Django
def pytest_configure(config):
    from django.conf import settings

    db = settings.DATABASES["default"]
    conn = psycopg2.connect(
        dbname="template1",
        user=db["USER"],
        password=db["PASSWORD"],
        host=db.get("HOST") or "localhost",
        port=db.get("PORT") or "5432",
    )
    try:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
    finally:
        conn.close()
