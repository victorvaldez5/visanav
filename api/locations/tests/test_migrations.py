"""The Language-table prune (0007) run directly against the current models.

Tests build the schema with --no-migrations, so the data migration never runs on
its own here; call its function with the live app registry instead.
"""
import importlib

import pytest
from django.apps import apps
from django.contrib.auth import get_user_model

from locations.models import Language

pytestmark = pytest.mark.django_db

prune_languages = importlib.import_module("locations.migrations.0007_prune_languages").prune_languages


def _user(name, language):
    user = get_user_model().objects.create_user(username=name, email=f"{name}@example.com", password="x")
    user.profile.preferred_language = language
    user.profile.save()
    return user


def test_prune_keeps_only_the_allowlist_and_remaps_profiles():
    es_mx = Language.objects.create(code="es-mx", name="Mexican Spanish")
    fr = Language.objects.create(code="fr", name="French")
    en = Language.objects.create(code="en", name="English")
    mexican, french, english, unset = (
        _user("mx", es_mx),
        _user("fr", fr),
        _user("en", en),
        _user("none", None),
    )

    prune_languages(apps, None)

    assert set(Language.objects.values_list("code", flat=True)) == {"en", "es"}
    for user, expected in [(mexican, "es"), (french, None), (english, "en"), (unset, None)]:
        user.profile.refresh_from_db()
        assert user.profile.preferred_language_id == expected
