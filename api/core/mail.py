from urllib.parse import urlencode

import mailtrap as mt
from django.conf import settings
from django.utils import translation
from django.utils.http import urlsafe_base64_encode
from django.utils.translation import gettext as _
from jwt.utils import force_bytes

from accounts.tokens import email_verification_token


def _email_locale(user, locale=None):
    """The language to write to this user in: an explicit one (the language the
    registering browser sent), else their profile's preferred language, else the
    default. Always one of settings.LANGUAGES."""
    supported = {code for code, _name in settings.LANGUAGES}
    if locale in supported:
        return locale
    profile = getattr(user, "profile", None)
    preferred = getattr(profile, "preferred_language_id", None)
    return preferred if preferred in supported else settings.LANGUAGE_CODE


def send_verification_email(user, locale=None):
    lang = _email_locale(user, locale)
    uid = urlsafe_base64_encode(force_bytes(str(user.pk)))
    token = email_verification_token.make_token(user)
    # `lang` is the app's cross-origin handoff param: whoever opens the link, on
    # whatever device, lands in the language this email was written in.
    query = urlencode({"uid": uid, "token": token, "lang": lang})
    url = f"{settings.FRONTEND_URL}/verify?{query}"

    # Translate under an explicit override: this can run outside a request (or in
    # a worker) where the active language is not the recipient's.
    with translation.override(lang):
        subject = _("Verify your VisaNav account")
        text = "\n\n".join(
            [
                _("Hello,"),
                _("Thanks for signing up for VisaNav. Please verify your account by opening the link below:"),
                url,
                _("If you did not create this account, you can ignore this email."),
            ]
        )

    mail = mt.Mail(
        sender=mt.Address(email=settings.DEFAULT_FROM_EMAIL, name="VisaNav"),
        to=[mt.Address(email=user.email, name=user.email)],
        subject=subject,
        text=text,
        category="Account verification",
    )

    _mailtrap_client().send(mail)


def _mailtrap_client():
    """Real delivery by default; with MAILTRAP_SANDBOX_INBOX_ID set, mail is
    captured in that Mailtrap sandbox inbox instead (local dev, staging)."""
    inbox_id = settings.MAILTRAP_SANDBOX_INBOX_ID
    if inbox_id:
        return mt.MailtrapClient(token=settings.MAILTRAP_API_KEY, sandbox=True, inbox_id=inbox_id)
    return mt.MailtrapClient(token=settings.MAILTRAP_API_KEY)
