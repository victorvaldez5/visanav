"""Application-layer encryption for sensitive model fields.

Conversation content (people's immigration questions) is encrypted before it is
written to Postgres, so a database dump, a stolen backup, or a leaked read
replica does not expose plaintext.

What this is and is NOT:
  - It is defence-in-depth for data *at rest*. The key lives in the API
    process's environment, so a Postgres-only compromise yields ciphertext.
  - It is NOT end-to-end encryption. The server must decrypt a turn to run the
    model, and whoever holds the key (including us, under legal process) can
    read stored conversations. The strongest privacy lever remains short
    retention + deletion (see ``Conversation.apply_retention_policy`` and the
    ``purge_expired_conversations`` command); encryption only shrinks the blast
    radius of a storage breach.

Keys are Fernet keys (32 url-safe base64 bytes). ``CONVERSATION_ENCRYPTION_KEYS``
may list several, comma-separated: the first encrypts, all are tried on
decrypt. Rotate by prepending a fresh key and re-saving rows. Generate one with:

    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
"""
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

__all__ = ["encrypt", "decrypt", "InvalidToken"]


@lru_cache(maxsize=4)
def _multifernet(keys: str) -> MultiFernet:
    """Build a MultiFernet from a comma-separated key string.

    Cached by the key string so a settings override (e.g. in tests) yields a
    distinct instance rather than a stale one. Built lazily — importing this
    module never touches the key, so management commands and migrations import
    ``conversation.models`` without a valid key present.
    """
    parts = [k.strip() for k in keys.split(",") if k.strip()]
    if not parts:
        raise ImproperlyConfigured(
            "CONVERSATION_ENCRYPTION_KEYS is empty; a Fernet key is required to "
            "read or write encrypted conversation content."
        )
    try:
        return MultiFernet([Fernet(k.encode("ascii")) for k in parts])
    except (ValueError, TypeError) as exc:
        raise ImproperlyConfigured(
            "CONVERSATION_ENCRYPTION_KEYS contains an invalid Fernet key "
            "(expected 32 url-safe base64 bytes)."
        ) from exc


def _fernet() -> MultiFernet:
    return _multifernet(settings.CONVERSATION_ENCRYPTION_KEYS)


def encrypt(text: str) -> str:
    """Encrypt a string, returning an ASCII Fernet token."""
    return _fernet().encrypt(text.encode("utf-8")).decode("ascii")


def decrypt(token: str) -> str:
    """Decrypt a Fernet token back to the original string.

    Raises ``InvalidToken`` if the value is not a token this key set produced
    (used by ``EncryptedJSONField`` to detect legacy plaintext rows).
    """
    return _fernet().decrypt(token.encode("ascii")).decode("utf-8")
