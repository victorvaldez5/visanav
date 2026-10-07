"""Shrink the Language reference table to the i18n allowlist.

0004_populate_languages seeded Django's full ~100-language list, because
settings.LANGUAGES was unset at the time. Profile.preferred_language now means
"the UI locale", so only the locales the app ships (i18n/supported-locales.json)
belong here. A profile on a regional variant ("es-mx") keeps its language via its
base code; any other profile's preference is cleared, since the app can't honor it.

The kept codes are hard-coded, not read from settings, so this migration does the
same thing whenever it runs. A locale added later gets its own data migration
(see "Adding a locale" in docs/i18n-architecture.md).
"""
from django.db import migrations

KEEP = {"en": "English", "es": "Spanish"}


def prune_languages(apps, schema_editor):
    Language = apps.get_model("locations", "Language")
    Profile = apps.get_model("accounts", "Profile")

    for code, name in KEEP.items():
        Language.objects.get_or_create(code=code, defaults={"name": name})

    # Regional variants fold into their base locale ("es-mx" -> "es").
    for code in KEEP:
        Profile.objects.filter(preferred_language__code__istartswith=f"{code}-").update(
            preferred_language_id=code
        )

    Profile.objects.exclude(preferred_language__isnull=True).exclude(
        preferred_language_id__in=KEEP
    ).update(preferred_language=None)
    Language.objects.exclude(code__in=KEEP).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("locations", "0006_populate_countries_subdivisions"),
        ("accounts", "0005_profile_retain_history"),
    ]

    operations = [
        migrations.RunPython(prune_languages, migrations.RunPython.noop),
    ]
