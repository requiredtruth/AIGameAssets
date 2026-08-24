import random
import unittest

from gbcforge.director import choose_next_kind


class DirectorTests(unittest.TestCase):
    def test_empty_world_begins_with_a_biome(self) -> None:
        direction = choose_next_kind({}, random.Random(1))
        self.assertEqual(direction.kind, "biome")

    def test_scheduler_fills_a_large_coverage_gap(self) -> None:
        counts = {
            "biome": 2,
            "creature": 6,
            "event": 3,
            "item": 6,
            "npc": 3,
            "quest": 0,
            "recipe": 3,
        }
        direction = choose_next_kind(counts, random.Random(1))
        self.assertEqual(direction.kind, "quest")


if __name__ == "__main__":
    unittest.main()

