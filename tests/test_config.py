from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests import _bootstrap  # noqa: F401
from palworld_trainer.config import TrainerSettings, load_settings, save_settings


class ConfigTests(unittest.TestCase):
    def test_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "settings.json"
            settings = TrainerSettings(
                game_root="D:/steam/steamapps/common/Palworld",
                last_tab="items",
                custom_item_count=10,
                custom_pal_count=3,
                custom_exp_amount=250000,
                recent_item_ids=["Shield_Ultra", "Bow"],
                recent_pal_ids=["Anubis"],
                favorite_item_ids=["Cake"],
                favorite_pal_ids=["JetDragon"],
                favorite_coord_labels=["[地图--商人] 沙漠商人"],
            )

            with patch("palworld_trainer.config.get_settings_path", return_value=path):
                save_settings(settings)
                loaded = load_settings()

            self.assertEqual(settings.game_root, loaded.game_root)
            self.assertEqual("items", loaded.last_tab)
            self.assertEqual(10, loaded.custom_item_count)
            self.assertEqual(3, loaded.custom_pal_count)
            self.assertEqual(250000, loaded.custom_exp_amount)
            self.assertEqual(["Shield_Ultra", "Bow"], loaded.recent_item_ids)
            self.assertEqual(["Anubis"], loaded.recent_pal_ids)
            self.assertEqual(["Cake"], loaded.favorite_item_ids)
            self.assertEqual(["JetDragon"], loaded.favorite_pal_ids)
            self.assertEqual(["[地图--商人] 沙漠商人"], loaded.favorite_coord_labels)

    def test_missing_file_returns_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "nothing.json"
            with patch("palworld_trainer.config.get_settings_path", return_value=path):
                loaded = load_settings()
        self.assertIsNone(loaded.game_root)
        self.assertEqual("common", loaded.last_tab)

    def test_corrupt_file_returns_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "settings.json"
            path.write_text("{ not json", encoding="utf-8")
            with patch("palworld_trainer.config.get_settings_path", return_value=path):
                loaded = load_settings()
            self.assertIsNone(loaded.game_root)

    def test_saved_payload_is_valid_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "settings.json"
            with patch("palworld_trainer.config.get_settings_path", return_value=path):
                save_settings(TrainerSettings(game_root="X:/Palworld"))
            parsed = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual("X:/Palworld", parsed["game_root"])


if __name__ == "__main__":
    unittest.main()
