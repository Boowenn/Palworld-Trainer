from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from tests import _bootstrap  # noqa: F401
from palworld_trainer.environment import _looks_like_game_root, scan_environment


class LooksLikeGameRootTests(unittest.TestCase):
    def test_true_when_required_files_exist(self) -> None:
        root = Path("D:/fake/Palworld")

        def fake_exists(path: Path) -> bool:
            normalized = str(path).replace("\\", "/")
            return normalized.endswith("/Palworld.exe") or normalized.endswith(
                "/Pal/Binaries/Win64/Palworld-Win64-Shipping.exe"
            )

        with patch("pathlib.Path.exists", autospec=True, side_effect=fake_exists):
            self.assertTrue(_looks_like_game_root(root))

    def test_false_when_files_missing(self) -> None:
        with patch("pathlib.Path.exists", autospec=True, return_value=False):
            self.assertFalse(_looks_like_game_root(Path("D:/fake/Palworld")))


class ScanEnvironmentTests(unittest.TestCase):
    def test_missing_game_root_yields_helpful_note(self) -> None:
        with patch(
            "palworld_trainer.environment.resolve_game_root", return_value=None
        ):
            report = scan_environment(None)
        self.assertFalse(report.game_root_exists)
        self.assertTrue(any("Palworld" in note for note in report.notes))


if __name__ == "__main__":
    unittest.main()
