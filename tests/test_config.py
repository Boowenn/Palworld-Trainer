from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from tests import _bootstrap  # noqa: F401
from palworld_trainer.config import load_settings, save_settings
from palworld_trainer.runtime import build_saved_runtime_bookmark
from palworld_trainer.models import TrainerSettings


class ConfigTests(unittest.TestCase):
    def test_settings_round_trip_saved_runtime_bookmarks(self) -> None:
        fake_settings_path = Path("D:/fake/settings.json")
        settings = TrainerSettings(
            game_root="D:/steam/steamapps/common/Palworld",
            last_selected_tab="Runtime",
            runtime_saved_bookmarks=[
                build_saved_runtime_bookmark(
                    "Saved Players",
                    "pt_players 12",
                    "Repeatable player visibility bookmark.",
                )
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

        self.assertEqual("Runtime", loaded.last_selected_tab)
        self.assertEqual(1, len(loaded.runtime_saved_bookmarks))
        self.assertEqual("Saved Players", loaded.runtime_saved_bookmarks[0].title)
        self.assertEqual("pt_players 12", loaded.runtime_saved_bookmarks[0].command)


if __name__ == "__main__":
    unittest.main()
