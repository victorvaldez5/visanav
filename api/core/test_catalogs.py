"""The committed gettext catalogs. A missing or stale django.mo makes Django fall
back to English without any error, so these fail loudly instead."""
import ast
import re

import pytest
from django.conf import settings
from django.utils import translation

NON_DEFAULT = [code for code, _name in settings.LANGUAGES if code != settings.LANGUAGE_CODE]


def _po_msgids(path):
    """Non-empty msgids of a .po file (single-line entries, as `makemessages
    --no-wrap` writes them)."""
    text = path.read_text(encoding="utf-8")
    return [
        ast.literal_eval(f'"{m}"')
        for m in re.findall(r'^msgid "((?:[^"\\]|\\.)+)"$', text, re.M)
    ]


@pytest.mark.parametrize("code", NON_DEFAULT)
def test_compiled_catalog_is_present_and_current(code):
    """Every msgid in the committed .po must translate, i.e. be in django.mo. Fix
    with `uv run python manage.py compilemessages` after editing a .po."""
    po = settings.LOCALE_PATHS[0] / code / "LC_MESSAGES" / "django.po"
    msgids = _po_msgids(po)
    assert msgids, f"{po} has no entries"
    with translation.override(code):
        untranslated = [m for m in msgids if translation.gettext(m) == m]
    assert not untranslated, f"{code}: not in django.mo (run compilemessages): {untranslated}"
