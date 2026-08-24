import unittest

from gbcforge.models import GeneratedContent
from gbcforge.novelty import similarity
from tests.test_models import VALID


class NoveltyTests(unittest.TestCase):
    def test_identical_content_scores_one(self) -> None:
        content = GeneratedContent.from_mapping(VALID)
        self.assertEqual(similarity(content, content.to_dict()), 1.0)

    def test_unrelated_content_scores_low(self) -> None:
        content = GeneratedContent.from_mapping(VALID)
        other = {
            "name": "Cinder Newt",
            "description": "A cave animal that stores heat and cracks frozen gates.",
            "hook": "It appears only when every torch has gone dark.",
            "tags": ["cave", "heat", "animal"],
        }
        self.assertLess(similarity(content, other), 0.55)


if __name__ == "__main__":
    unittest.main()

