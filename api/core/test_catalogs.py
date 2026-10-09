"""The committed gettext catalogs. A missing or stale django.mo makes Django fall
back to English without any error, so these fail loudly instead."""
import ast
import re

import pytest
from django.conf import settings
from django.utils import translation

NON_DEFAULT = [code for code, _name in settings.LANGUAGES if code != settings.LANGUAGE_CODE]

ENTRY = re.compile(r'^msgid "((?:[^"\\]|\\.)+)"\nmsgstr "((?:[^"\\]|\\.)*)"$', re.M)


def _po_entries(path):
    """msgid -> msgstr of a .po file (single-line entries, as `just messages`
    writes them)."""
    text = path.read_text(encoding="utf-8")
    return {ast.literal_eval(f'"{i}"'): ast.literal_eval(f'"{s}"') for i, s in ENTRY.findall(text)}


@pytest.mark.parametrize("code", NON_DEFAULT)
def test_compiled_catalog_matches_the_po(code):
    """django.mo must serve exactly what the committed .po says, with nothing left
    untranslated. Fix with `just compile-messages` after editing a .po."""
    po = settings.LOCALE_PATHS[0] / code / "LC_MESSAGES" / "django.po"
    entries = _po_entries(po)
    assert entries, f"{po} has no entries"
    untranslated = [msgid for msgid, msgstr in entries.items() if not msgstr]
    assert not untranslated, f"{code}: no translation in django.po: {untranslated}"
    with translation.override(code):
        stale = [msgid for msgid, msgstr in entries.items() if translation.gettext(msgid) != msgstr]
    assert not stale, f"{code}: django.mo is stale (run `just compile-messages`): {stale}"
