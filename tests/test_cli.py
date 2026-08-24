import json
from pathlib import Path
import tempfile
import unittest

from gbcforge.cli import main


class CliTests(unittest.TestCase):
    def test_offline_pipeline_writes_requested_records(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            status = main(
                [
                    "--offline",
                    "--jobs",
                    "4",
                    "--seed",
                    "19",
                    "--db",
                    str(root / "content.sqlite3"),
                    "--out",
                    str(root / "content.jsonl"),
                    "--manifest",
                    str(root / "world.manifest.json"),
                ]
            )
            self.assertEqual(status, 0)
            records = [
                json.loads(line)
                for line in (root / "content.jsonl").read_text(encoding="utf-8").splitlines()
            ]
            self.assertEqual(len(records), 4)
            self.assertEqual(len({record["signature"] for record in records}), 4)
            manifest = json.loads(
                (root / "world.manifest.json").read_text(encoding="utf-8")
            )
            self.assertEqual(manifest["revision"], 4)
            self.assertEqual(len(manifest["content"]), 4)


if __name__ == "__main__":
    unittest.main()
