import json

from cryptography.fernet import Fernet
from django.test import SimpleTestCase, override_settings

from core import encryption
from core.fields import EncryptedJSONField


class EncryptionTests(SimpleTestCase):
    def test_encrypt_then_decrypt_returns_original(self):
        token = encryption.encrypt("Am I eligible for asylum?")
        self.assertNotEqual(token, "Am I eligible for asylum?")
        self.assertEqual(encryption.decrypt(token), "Am I eligible for asylum?")

    def test_rotation_decrypts_under_retired_key(self):
        old = Fernet.generate_key().decode()
        new = Fernet.generate_key().decode()
        with override_settings(CONVERSATION_ENCRYPTION_KEYS=old):
            token = encryption.encrypt("secret")
        # Rotate: prepend the new key, keep the old for decrypt.
        with override_settings(CONVERSATION_ENCRYPTION_KEYS=f"{new},{old}"):
            self.assertEqual(encryption.decrypt(token), "secret")


class EncryptedJSONFieldTests(SimpleTestCase):
    def setUp(self):
        self.field = EncryptedJSONField()

    def test_payload_is_not_stored_in_plaintext(self):
        payload = {"parts": [{"content": "questions about my visa status"}]}
        stored = self.field.get_prep_value(payload)
        self.assertNotIn("visa status", stored)
        self.assertEqual(self.field.from_db_value(stored, None, None), payload)

    def test_reads_legacy_plaintext_json(self):
        # A row written (or cast from jsonb) before encryption still reads.
        legacy = json.dumps({"kind": "request"})
        self.assertEqual(
            self.field.from_db_value(legacy, None, None), {"kind": "request"}
        )

    def test_none_passes_through(self):
        self.assertIsNone(self.field.get_prep_value(None))
        self.assertIsNone(self.field.from_db_value(None, None, None))
