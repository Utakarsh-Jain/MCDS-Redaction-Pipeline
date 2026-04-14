import unittest

from lib.redaction import EntitySpan, parse_entities, redact_index_safe, placeholder_for


class TestRedaction(unittest.TestCase):
    def test_placeholder_for(self):
        self.assertEqual(placeholder_for("SSN"), "[SSN]")
        self.assertEqual(placeholder_for("unknown"), "[UNKNOWN]")

    def test_parse_entities(self):
        out = parse_entities(
            {"entities": [{"start": 0, "end": 4, "type": "NAME"}, {"start": 10, "end": 12, "type": "SSN"}]}
        )
        self.assertEqual(len(out), 2)
        self.assertEqual(out[0].entity_type, "NAME")

    def test_redact_index_safe_order(self):
        text = "John Doe lives at 123 Main"
        spans = [
            EntitySpan(0, 8, "NAME"),
            EntitySpan(18, 26, "ADDRESS"),
        ]
        redacted = redact_index_safe(text, spans)
        self.assertNotIn("John Doe", redacted)
        self.assertNotIn("123 Main", redacted)
        self.assertIn("[NAME]", redacted)
        self.assertIn("[ADDRESS]", redacted)


if __name__ == "__main__":
    unittest.main()
