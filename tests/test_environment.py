from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from tests import _bootstrap  # noqa: F401
from palworld_trainer.environment import (
    BRIDGE_MOD_NAME,
    EnvironmentReport,
    _detect_bridge_runtime_target,
    _looks_like_game_root,
    deploy_bridge,
    scan_environment,
)


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


class DeployBridgeTests(unittest.TestCase):
    def test_deploy_bridge_copies_files_and_enables_mod(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo_root = root / "repo"
            source = repo_root / "integrations" / "ue4ss" / BRIDGE_MOD_NAME
            scripts = source / "Scripts"
            scripts.mkdir(parents=True, exist_ok=True)
            (scripts / "main.lua").write_text("-- bridge", encoding="utf-8")
            (source / "README.md").write_text("bridge readme", encoding="utf-8")

            target = root / "game" / "Mods" / "NativeMods" / "UE4SS" / "Mods" / BRIDGE_MOD_NAME
            report = EnvironmentReport(game_root=root / "game", trainer_bridge_target=target)

            with patch("palworld_trainer.environment.get_repo_root", return_value=repo_root):
                ok, message = deploy_bridge(report)

            self.assertTrue(ok, message)
            self.assertTrue((target / "Scripts" / "main.lua").exists())

            mods_root = target.parent
            mods_txt = (mods_root / "mods.txt").read_text(encoding="utf-8")
            self.assertIn(f"{BRIDGE_MOD_NAME} : 1", mods_txt)

            mods_json = json.loads((mods_root / "mods.json").read_text(encoding="utf-8"))
            bridge_entry = next(
                item for item in mods_json if item.get("mod_name") == BRIDGE_MOD_NAME
            )
            self.assertTrue(bridge_entry["mod_enabled"])


class BridgeRuntimeTargetTests(unittest.TestCase):
    def test_prefers_runtime_artifact_under_shipping_workdir(self) -> None:
        with TemporaryDirectory() as tmp:
            game_root = Path(tmp) / "Palworld"
            deployed = (
                game_root
                / "Mods"
                / "NativeMods"
                / "UE4SS"
                / "Mods"
                / BRIDGE_MOD_NAME
            )
            runtime = (
                game_root
                / "Pal"
                / "Binaries"
                / "Win64"
                / "Mods"
                / "NativeMods"
                / "UE4SS"
                / "Mods"
                / BRIDGE_MOD_NAME
            )
            deployed.mkdir(parents=True, exist_ok=True)
            runtime.mkdir(parents=True, exist_ok=True)
            (runtime / "status.json").write_text("{}", encoding="utf-8")

            detected = _detect_bridge_runtime_target(game_root, deployed)
            self.assertEqual(detected, runtime)

    def test_falls_back_to_deployed_target_without_runtime_artifacts(self) -> None:
        with TemporaryDirectory() as tmp:
            game_root = Path(tmp) / "Palworld"
            deployed = (
                game_root
                / "Mods"
                / "NativeMods"
                / "UE4SS"
                / "Mods"
                / BRIDGE_MOD_NAME
            )
            deployed.mkdir(parents=True, exist_ok=True)

            detected = _detect_bridge_runtime_target(game_root, deployed)
            self.assertEqual(detected, deployed)


if __name__ == "__main__":
    unittest.main()
