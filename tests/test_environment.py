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

    def test_reports_when_live_process_has_not_loaded_ue4ss(self) -> None:
        root = Path("D:/fake/Palworld")

        def fake_exists(path: Path) -> bool:
            normalized = str(path).replace("\\", "/")
            suffixes = {
                "/Palworld",
                "/Palworld.exe",
                "/Pal/Binaries/Win64/Palworld-Win64-Shipping.exe",
                "/Mods/NativeMods/UE4SS",
                "/Mods/NativeMods/UE4SS/Mods/ClientCheatCommands",
                "/Mods/NativeMods/UE4SS/Mods/ClientCheatCommands/Scripts/enums",
                "/Mods/PalModSettings.ini",
            }
            return any(normalized.endswith(suffix) for suffix in suffixes)

        with (
            patch("palworld_trainer.environment.resolve_game_root", return_value=root),
            patch("pathlib.Path.exists", autospec=True, side_effect=fake_exists),
            patch(
                "pathlib.Path.read_text",
                autospec=True,
                return_value="[PalModSettings]\nbGlobalEnableMod=True\nActiveModList=ClientCheatCommands\n",
            ),
            patch(
                "palworld_trainer.environment._detect_live_ue4ss_loader",
                return_value=(8040, False, None),
            ),
        ):
            report = scan_environment(None)

        self.assertTrue(report.client_cheat_commands_active)
        self.assertEqual(report.game_pid, 8040)
        self.assertFalse(report.ue4ss_live_loaded)
        self.assertTrue(any("没有加载 UE4SS" in note for note in report.notes))

    def test_global_mod_toggle_must_be_enabled(self) -> None:
        root = Path("D:/fake/Palworld")

        def fake_exists(path: Path) -> bool:
            normalized = str(path).replace("\\", "/")
            suffixes = {
                "/Palworld",
                "/Palworld.exe",
                "/Pal/Binaries/Win64/Palworld-Win64-Shipping.exe",
                "/Mods/NativeMods/UE4SS",
                "/Mods/NativeMods/UE4SS/Mods/ClientCheatCommands",
                "/Mods/NativeMods/UE4SS/Mods/ClientCheatCommands/Scripts/enums",
                "/Mods/PalModSettings.ini",
            }
            return any(normalized.endswith(suffix) for suffix in suffixes)

        with (
            patch("palworld_trainer.environment.resolve_game_root", return_value=root),
            patch("pathlib.Path.exists", autospec=True, side_effect=fake_exists),
            patch(
                "pathlib.Path.read_text",
                autospec=True,
                return_value="[PalModSettings]\nbGlobalEnableMod=False\nActiveModList=ClientCheatCommands\n",
            ),
            patch(
                "palworld_trainer.environment._detect_live_ue4ss_loader",
                return_value=(8040, False, None),
            ),
        ):
            report = scan_environment(None)

        self.assertFalse(report.mods_globally_enabled)
        self.assertFalse(report.client_cheat_commands_active)
        self.assertTrue(any("bGlobalEnableMod" in note for note in report.notes))


if __name__ == "__main__":
    unittest.main()
