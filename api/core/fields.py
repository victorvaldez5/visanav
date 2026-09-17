"""Model fields that transparently encrypt their value at rest."""
import json

from django.db import models

from core.encryption import InvalidToken, decrypt, encrypt


class EncryptedJSONField(models.TextField):
    """A JSON field whose value is stored as a Fernet-encrypted string.

    In Python it behaves like ``models.JSONField`` (you get and set native
    dicts/lists), but the database column holds ciphertext, so the payload is
    never at rest in plaintext. See ``core.encryption`` for the threat model.

    Reads tolerate a legacy *plaintext* JSON value — a row written before this
    field was encrypted, or one freshly cast from a ``jsonb`` column by the
    migration: decryption is attempted first, and a non-token value falls back
    to being parsed as plain JSON. New writes are always encrypted.
    """

    description = "JSON data, encrypted at rest"

    def get_internal_type(self):
        # Stored as text; the encryption happens in get_prep_value.
        return "TextField"

    def from_db_value(self, value, expression, connection):
        if value is None:
            return None
        return self._loads(value)

    def to_python(self, value):
        # Already-native values (e.g. assigned in Python, or a fixture dict)
        # pass through; only stored strings need decoding.
        if value is None or not isinstance(value, str):
            return value
        return self._loads(value)

    def get_prep_value(self, value):
        if value is None:
            return None
        return encrypt(json.dumps(value))

    @staticmethod
    def _loads(value):
        try:
            return json.loads(decrypt(value))
        except (InvalidToken, UnicodeEncodeError):
            # Legacy / not-yet-encrypted row: parse as plaintext JSON. A
            # non-Fernet-token value either fails MultiFernet validation
            # (InvalidToken) or, if it contains non-ASCII characters, fails
            # earlier at token.encode("ascii") in decrypt() with
            # UnicodeEncodeError — both indicate this is plaintext JSON, not
            # an encrypted token. If plaintext parsing also fails, the JSON
            # error propagates (a genuinely unreadable value — e.g.
            # ciphertext under a key this process does not hold).
            return json.loads(value)
