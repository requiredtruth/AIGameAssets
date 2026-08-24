import json
from pathlib import Path
import tempfile
import unittest

from gbcforge.generator import offline_seed
from gbcforge.store import ContentStore, append_jsonl
import random


class StoreTests(unittest.TestCase):
    def test_deduplicates_and_exports(self) -> None:
        content = offline_seed("quest", random.Random(3))
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with ContentStore(root / "state" / "content.sqlite3") as store:
                self.assertTrue(store.add(content))
                self.assertFalse(store.add(content))
                self.assertEqual(store.count(), 1)
                self.assertEqual(store.recent_names(), [content.name])
                self.assertEqual(store.kind_counts(), {"quest": 1})
                score, name = store.closest_match(content)
                self.assertEqual(score, 1.0)
                self.assertEqual(name, content.name)

            output = root / "generated" / "content.jsonl"
            append_jsonl(output, content)
            decoded = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(decoded["name"], content.name)


if __name__ == "__main__":
    unittest.main()
