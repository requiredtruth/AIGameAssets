import unittest

from gbcforge.models import ContentValidationError, GeneratedContent


VALID = {
    "kind": "item",
    "name": "Moss Compass",
    "description": "A pocket compass that points toward the nearest safe camp after dusk.",
    "rarity": "uncommon",
    "tags": ["travel", "moss", "utility"],
    "stats": {"range": 8, "charges": 3},
    "hook": "A lost courier traded it for one warm meal.",
}


class GeneratedContentTests(unittest.TestCase):
    def test_valid_mapping_is_normalized(self) -> None:
        content = GeneratedContent.from_mapping(VALID, source="test-model")
        self.assertEqual(content.kind, "item")
        self.assertEqual(content.tags, ("travel", "moss", "utility"))
        self.assertEqual(len(content.signature), 64)
        self.assertGreaterEqual(content.quality_score(), 0.60)

    def test_signature_uses_kind_and_normalized_name(self) -> None:
        first = GeneratedContent.from_mapping(VALID)
        second_payload = dict(VALID)
        second_payload["name"] = "moss--compass"
        second = GeneratedContent.from_mapping(second_payload)
        self.assertEqual(first.signature, second.signature)

    def test_rejects_unbounded_stats(self) -> None:
        payload = dict(VALID)
        payload["stats"] = {"damage": 1_000_000}
        with self.assertRaises(ContentValidationError):
            GeneratedContent.from_mapping(payload)

    def test_rejects_unknown_kind(self) -> None:
        payload = dict(VALID)
        payload["kind"] = "advertisement"
        with self.assertRaises(ContentValidationError):
            GeneratedContent.from_mapping(payload)


if __name__ == "__main__":
    unittest.main()

