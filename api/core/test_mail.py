"""send_verification_email: the language it is written in, and what it links to."""
from types import SimpleNamespace
from unittest import mock
from urllib.parse import parse_qs, urlparse

import pytest
from django.utils import translation

from core import mail


@pytest.fixture
def mailtrap(monkeypatch):
    """Capture the Mailtrap Mail instead of sending it."""
    fake = mock.Mock()
    monkeypatch.setattr(mail.mt, "MailtrapClient", mock.Mock(return_value=fake))
    # The real generator needs a saved user; the token's value is irrelevant here.
    monkeypatch.setattr(mail, "email_verification_token", SimpleNamespace(make_token=lambda user: "tok-123"))
    return fake


def _user(preferred=None):
    profile = SimpleNamespace(preferred_language_id=preferred)
    return SimpleNamespace(pk=7, email="ana@example.com", profile=profile)


def _sent(mailtrap):
    return mailtrap.send.call_args.args[0]


def _link(text):
    return next(line for line in text.splitlines() if line.startswith("http"))


def test_defaults_to_english(mailtrap):
    mail.send_verification_email(_user())

    sent = _sent(mailtrap)
    assert sent.subject == "Verify your VisaNav account"
    assert "verify your account" in sent.text


def test_explicit_locale_wins_and_is_translated(mailtrap):
    mail.send_verification_email(_user(preferred="en"), locale="es")

    sent = _sent(mailtrap)
    assert sent.subject == "Verifica tu cuenta de VisaNav"
    assert "Gracias por registrarte" in sent.text
    # The link hands the language to the app, so it opens in Spanish on any device.
    query = parse_qs(urlparse(_link(sent.text)).query)
    assert query["lang"] == ["es"]
    assert set(query) == {"uid", "token", "lang"}


def test_falls_back_to_the_profile_language(mailtrap):
    mail.send_verification_email(_user(preferred="es"))

    assert _sent(mailtrap).subject == "Verifica tu cuenta de VisaNav"


def test_unsupported_locale_falls_back_rather_than_failing(mailtrap):
    mail.send_verification_email(_user(preferred="xx"), locale="fr")

    assert _sent(mailtrap).subject == "Verify your VisaNav account"


def test_delivers_for_real_unless_a_sandbox_inbox_is_configured(mailtrap, settings):
    settings.MAILTRAP_SANDBOX_INBOX_ID = ""
    mail.send_verification_email(_user())
    assert "sandbox" not in mail.mt.MailtrapClient.call_args.kwargs

    settings.MAILTRAP_SANDBOX_INBOX_ID = "42"
    mail.send_verification_email(_user())
    assert mail.mt.MailtrapClient.call_args.kwargs["sandbox"] is True
    assert mail.mt.MailtrapClient.call_args.kwargs["inbox_id"] == "42"
    assert _sent(mailtrap).sender.email == settings.DEFAULT_FROM_EMAIL


def test_does_not_leak_the_language_into_the_calling_thread(mailtrap):
    with translation.override("en"):
        mail.send_verification_email(_user(), locale="es")

        assert translation.get_language() == "en"
