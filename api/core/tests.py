import json

from cryptography.fernet import Fernet
from django.test import SimpleTestCase, override_settings

from conversation import streaming
from core import encryption, llm
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


class ToolArgHardeningTests(SimpleTestCase):
    """Model-generated tool arguments and citation URLs are untrusted input."""

    def test_clip_arg_strips_and_caps_length(self):
        with override_settings(CHAT_TOOL_ARG_MAX_CHARS=8):
            self.assertEqual(llm._clip_arg("  hello world  "), "hello wo")
        self.assertEqual(llm._clip_arg("  asylum  "), "asylum")

    def test_clip_arg_explicit_max_len_and_none(self):
        self.assertEqual(llm._clip_arg("arizona-state", 3), "ari")
        self.assertIsNone(llm._clip_arg(None))

    def test_safe_url_allows_only_http_https(self):
        self.assertEqual(llm._safe_url("https://uscis.gov"), "https://uscis.gov")
        self.assertEqual(llm._safe_url("  http://x.test  "), "http://x.test")

    def test_safe_url_rejects_dangerous_schemes(self):
        for bad in (
            "javascript:alert(1)",
            "JavaScript:alert(1)",
            "data:text/html,<script>alert(1)</script>",
            "vbscript:msgbox(1)",
            "//evil.example",
            None,
            "",
        ):
            self.assertIsNone(llm._safe_url(bad), bad)


class InstructionsHardeningTests(SimpleTestCase):
    """The system prompt must keep its anti-prompt-injection frame."""

    def test_instructions_carry_the_injection_defenses(self):
        text = llm.INSTRUCTIONS.lower()
        self.assertIn("untrusted content", text)
        self.assertIn("ignore previous instructions", text)
        # Do not reveal / paraphrase the instructions.
        self.assertIn("do not reveal", text)
        # Declining must not narrate the rules themselves (no meta-commentary).
        self.assertIn("not even to justify a refusal", text)


class InstructionsSourceWeighingTests(SimpleTestCase):
    """How Javi is told to rank the kinds of document semantic_search returns."""

    def _section(self, heading):
        start = llm.INSTRUCTIONS.index(heading)
        end = llm.INSTRUCTIONS.find("\n\n", start)
        return " ".join(llm.INSTRUCTIONS[start:end].split())

    def test_final_rules_are_ranked_with_binding_law(self):
        ranking = self._section("Weighing sources").split(" - ")[1]
        self.assertIn("outrank", ranking)
        for instrument in ("statute", "regulation", "final-rule"):
            self.assertIn(instrument, ranking)

    def test_referral_rule_stays_with_the_sourcing_rules(self):
        self.assertIn("resource_lookup", self._section("Citations & sourcing"))
        self.assertNotIn("resource_lookup", self._section("Weighing sources"))


class TurnUsageLimitTests(SimpleTestCase):
    """Every agent run is bounded so one turn can't spend unbounded LLM budget."""

    @override_settings(
        CHAT_REQUEST_LIMIT=6,
        CHAT_TOOL_CALLS_LIMIT=8,
        CHAT_TOTAL_TOKENS_LIMIT=60000,
    )
    def test_limits_map_from_settings(self):
        limits = streaming._turn_usage_limits()
        self.assertEqual(limits.request_limit, 6)
        self.assertEqual(limits.tool_calls_limit, 8)
        self.assertEqual(limits.total_tokens_limit, 60000)

    @override_settings(
        CHAT_REQUEST_LIMIT=0,
        CHAT_TOOL_CALLS_LIMIT=0,
        CHAT_TOTAL_TOKENS_LIMIT=0,
    )
    def test_zero_disables_a_limit(self):
        limits = streaming._turn_usage_limits()
        self.assertIsNone(limits.request_limit)
        self.assertIsNone(limits.tool_calls_limit)
        self.assertIsNone(limits.total_tokens_limit)
