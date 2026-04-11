from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from tests import _bootstrap  # noqa: F401
from palworld_trainer.config import load_settings, save_settings
from palworld_trainer.map_tools import build_collectible_spec, build_map_bookmark, build_route_spec
from palworld_trainer.runtime import build_saved_runtime_bookmark
from palworld_trainer.models import TrainerSettings


class ConfigTests(unittest.TestCase):
    def test_settings_round_trip_saved_runtime_bookmarks(self) -> None:
        fake_settings_path = Path("D:/fake/settings.json")
        settings = TrainerSettings(
            game_root="D:/steam/steamapps/common/Palworld",
            last_selected_tab="Map Tools",
            runtime_saved_bookmarks=[
                build_saved_runtime_bookmark(
                    "Saved Players",
                    "pt_players 12",
                    "Repeatable player visibility bookmark.",
                )
            ],
            map_saved_bookmarks=[
                build_map_bookmark("Ore Ridge", "100", "200", "300", "resource", "Ore farming anchor.")
            ],
            map_saved_routes=[
                build_route_spec("Ore Loop", ["ore_ridge"], "Short ore farming circuit.")
            ],
            tracked_collectibles=[
                build_collectible_spec("Statue Sweep", "ore_ridge", "lifmunk", "tracking", "Check ridge statue.")
            ],
        )

        written_payload: dict[str, str] = {}

        def fake_write_text(self: Path, payload: str, encoding: str = "utf-8") -> int:
            written_payload["text"] = payload
            return len(payload)

        with patch("palworld_trainer.config.get_settings_path", return_value=fake_settings_path):
            with patch("pathlib.Path.write_text", autospec=True, side_effect=fake_write_text):
                save_settings(settings)

            with patch("pathlib.Path.exists", autospec=True, return_value=True):
                with patch("pathlib.Path.read_text", autospec=True, return_value=written_payload["text"]):
                    loaded = load_settings()

        self.assertEqual("Map Tools", loaded.last_selected_tab)
        self.assertEqual(1, len(loaded.runtime_saved_bookmarks))
        self.assertEqual("Saved Players", loaded.runtime_saved_bookmarks[0].title)
        self.assertEqual("pt_players 12", loaded.runtime_saved_bookmarks[0].command)
        self.assertEqual(1, len(loaded.map_saved_bookmarks))
        self.assertEqual("Ore Ridge", loaded.map_saved_bookmarks[0].title)
        self.assertEqual(1, len(loaded.map_saved_routes))
        self.assertEqual("Ore Loop", loaded.map_saved_routes[0].title)
        self.assertEqual(1, len(loaded.tracked_collectibles))
        self.assertEqual("Statue Sweep", loaded.tracked_collectibles[0].title)


if __name__ == "__main__":
    unittest.main()
