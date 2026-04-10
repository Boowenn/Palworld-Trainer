from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from palworld_trainer.environment import _looks_like_game_root


class EnvironmentTests(unittest.TestCase):
    def test_looks_like_game_root_when_required_files_exist(self) -> None:
        root = Path("D:/fake/Palworld")

        def fake_exists(path: Path) -> bool:
            normalized = str(path).replace("\\", "/")
            return normalized.endswith("/Palworld.exe") or normalized.endswith(
                "/Pal/Binaries/Win64/Palworld-Win64-Shipping.exe"
            )

        with patch("pathlib.Path.exists", autospec=True, side_effect=fake_exists):
            self.assertTrue(_looks_like_game_root(root))

    def test_looks_like_game_root_when_files_are_missing(self) -> None:
        root = Path("D:/fake/Palworld")

        with patch("pathlib.Path.exists", autospec=True, return_value=False):
            self.assertFalse(_looks_like_game_root(root))


if __name__ == "__main__":
    unittest.main()
