from __future__ import annotations

import unittest

from tests import _bootstrap  # noqa: F401

from palworld_trainer.teleport_points import BOSS_TELEPORT_POINTS, BossTeleportPoint


class BossTeleportPointTests(unittest.TestCase):
    def test_map_to_world_conversion_matches_known_example(self) -> None:
        point = BossTeleportPoint(
            key="example",
            title="Example",
            category="测试",
            map_x=373,
            map_y=-359,
        )
        self.assertEqual(point.world_x, -288669)
        self.assertEqual(point.world_y, 329207)

    def test_labels_are_unique(self) -> None:
        labels = [point.label for point in BOSS_TELEPORT_POINTS]
        self.assertEqual(len(labels), len(set(labels)))

    def test_contains_tower_and_world_bosses(self) -> None:
        categories = {point.category for point in BOSS_TELEPORT_POINTS}
        self.assertIn("塔主", categories)
        self.assertIn("世界 Boss", categories)


if __name__ == "__main__":
    unittest.main()
