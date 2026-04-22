from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from tests import _bootstrap  # noqa: F401
from palworld_trainer.coord_presets import (
    ALL_GROUPS_LABEL,
    flatten_coord_groups,
    load_coord_groups,
    parse_coord_groups_text,
    pick_coord_file,
    search_coord_presets,
)


SAMPLE_COORDS = """
[
  {
    "name": "基地选址",
    "items": [
      { "name": "忘却之岛-初始基地", "value": [ -161827.5, -60595.4297, -855.960571 ] }
    ]
  },
  {
    "name": "战斗--Boss位置",
    "items": [
      { "name": "Lv11-叶泥泥", "value": [ -405723.5, 104713.297, -668.362122 ] },
      { "name": "Lv38-阿努比斯", "value": [ -233211.0, 111111.0, 5220.0 ] }
    ]
  }
]
""".strip()

SAMPLE_COORDS_WITH_NOTE = """
[
  {
    "name": "Boss note group",
    "items": [
      { "name": "前面带*表示会出传奇图纸", "value": [ 0, 0, 0 ] },
      { "name": "Lv11 boss", "value": [ -405723.5, 104713.297, -668.362122 ] }
    ]
  }
]
""".strip()


class ParseCoordGroupsTests(unittest.TestCase):
    def test_parse_coord_groups_text(self) -> None:
        groups = parse_coord_groups_text(SAMPLE_COORDS)
        self.assertEqual(len(groups), 2)
        self.assertEqual(groups[0].name, "基地选址")
        self.assertEqual(groups[1].items[0].label, "[战斗--Boss位置] Lv11-叶泥泥")

    def test_flatten_and_search(self) -> None:
        entries = flatten_coord_groups(parse_coord_groups_text(SAMPLE_COORDS))
        self.assertEqual(len(entries), 3)
        results = search_coord_presets(entries, "阿努比斯")
        self.assertEqual(len(results), 1)
        self.assertIn("阿努比斯", results[0].name)


    def test_parse_coord_groups_text_skips_zero_placeholder_rows(self) -> None:
        entries = flatten_coord_groups(parse_coord_groups_text(SAMPLE_COORDS_WITH_NOTE))

        self.assertEqual(1, len(entries))
        self.assertEqual("Lv11 boss", entries[0].name)


class LoadCoordGroupsTests(unittest.TestCase):
    def test_pick_coord_file_prefers_game_root_override(self) -> None:
        with TemporaryDirectory() as tmp:
            game_root = Path(tmp) / "Palworld"
            game_root.mkdir(parents=True, exist_ok=True)
            override = game_root / "Palworld.Coords.json"
            bundled = Path(tmp) / "bundled.json"
            override.write_text(SAMPLE_COORDS, encoding="utf-8")
            bundled.write_text("[]", encoding="utf-8")

            with mock.patch(
                "palworld_trainer.coord_presets.get_bundled_coord_file",
                return_value=bundled,
            ):
                picked = pick_coord_file(game_root)
            self.assertEqual(picked, override)

    def test_load_coord_groups_reads_existing_file(self) -> None:
        with TemporaryDirectory() as tmp:
            game_root = Path(tmp) / "Palworld"
            game_root.mkdir(parents=True, exist_ok=True)
            path = game_root / "Palworld.Coords.json"
            path.write_text(SAMPLE_COORDS, encoding="utf-8")
            loaded_path, groups = load_coord_groups(game_root)
            self.assertEqual(loaded_path, path)
            self.assertEqual(groups[0].name, "基地选址")
            self.assertNotEqual(ALL_GROUPS_LABEL, groups[0].name)


if __name__ == "__main__":
    unittest.main()
