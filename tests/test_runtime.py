from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from tests import _bootstrap  # noqa: F401
from palworld_trainer.runtime import (
    get_runtime_bookmark_specs,
    parse_session_log,
    render_runtime_bookmarks_text,
    get_runtime_command_specs,
    get_runtime_preset_specs,
    render_runtime_commands_text,
    render_runtime_presets_text,
    render_session_summary_text,
)


class RuntimeTests(unittest.TestCase):
    def test_runtime_specs_include_expected_commands(self) -> None:
        commands = [spec.command for spec in get_runtime_command_specs()]

        self.assertIn("pt_world", commands)
        self.assertIn("pt_find <ShortClassName> [limit]", commands)
        self.assertIn("pt_scan <preset> [limit]", commands)
        self.assertIn("pt_repeat", commands)

    def test_render_runtime_commands_text_mentions_hotkeys(self) -> None:
        rendered = render_runtime_commands_text()

        self.assertIn("CTRL+F6", rendered)
        self.assertIn("CTRL+F8", rendered)
        self.assertIn("Bridge messages are mirrored", rendered)

    def test_runtime_presets_include_manifest_derived_scans(self) -> None:
        presets = {preset.key: preset.query for preset in get_runtime_preset_specs()}

        self.assertEqual("BP_PalSpawner_Standard_C", presets["pal_spawners"])
        self.assertEqual("BP_SupplySpawnerBase_C", presets["supply_spawners"])

    def test_render_runtime_presets_text_mentions_examples(self) -> None:
        rendered = render_runtime_presets_text()

        self.assertIn("pt_scan pal_spawners 12", rendered)
        self.assertIn("pal_player_controller", rendered)

    def test_runtime_bookmarks_include_client_safe_scans(self) -> None:
        bookmarks = {bookmark.key: bookmark.command for bookmark in get_runtime_bookmark_specs()}

        self.assertEqual("pt_players 12", bookmarks["nearby_players"])
        self.assertEqual("pt_scan supply_spawners 12", bookmarks["supply_spawners"])

    def test_render_runtime_bookmarks_mentions_non_host_value(self) -> None:
        rendered = render_runtime_bookmarks_text()

        self.assertIn("Runtime bookmarks", rendered)
        self.assertIn("non-host", rendered)
        self.assertIn("pt_repeat", rendered)

    def test_parse_session_log_extracts_latest_summary(self) -> None:
        sample = "\n".join(
            [
                "[2026-04-11 12:00:00] [PalworldTrainerBridge] Bridge loaded.",
                "[2026-04-11 12:00:05] [PalworldTrainerBridge] Player location: X=100.0 Y=200.0 Z=300.0",
                "[2026-04-11 12:00:07] [PalworldTrainerBridge] Replicated players: 3",
                "[2026-04-11 12:00:10] [PalworldTrainerBridge] Preset 'pal_spawners' => BP_PalSpawner_Standard_C (6 shown / 8 total)",
                "[2026-04-11 12:00:12] [PalworldTrainerBridge] Local player location: X=150.0 Y=250.0 Z=350.0",
            ]
        )

        fake_path = Path("D:/fake/session.log")
        with patch("pathlib.Path.exists", autospec=True, return_value=True):
            with patch("pathlib.Path.read_text", autospec=True, return_value=sample):
                summary = parse_session_log(fake_path)

        self.assertTrue(summary.log_exists)
        self.assertEqual("X=100.0 Y=200.0 Z=300.0", summary.latest_player_location)
        self.assertEqual("X=150.0 Y=250.0 Z=350.0", summary.latest_world_location)
        self.assertEqual(3, summary.replicated_players)
        self.assertEqual("Preset 'pal_spawners' => BP_PalSpawner_Standard_C", summary.latest_scan_title)
        self.assertEqual(6, summary.latest_scan_shown)
        self.assertEqual(8, summary.latest_scan_total)

    def test_render_session_summary_text_mentions_recent_events(self) -> None:
        sample = "\n".join(
            [
                "[2026-04-11 12:00:00] [PalworldTrainerBridge] Bridge loaded.",
                "[2026-04-11 12:00:05] [PalworldTrainerBridge] Player location: X=100.0 Y=200.0 Z=300.0",
            ]
        )
        fake_path = Path("D:/fake/session.log")
        with patch("pathlib.Path.exists", autospec=True, return_value=True):
            with patch("pathlib.Path.read_text", autospec=True, return_value=sample):
                summary = parse_session_log(fake_path)

        rendered = render_session_summary_text(summary)
        self.assertIn("Session monitor", rendered)
        self.assertIn("Bridge loaded.", rendered)
        self.assertIn("X=100.0 Y=200.0 Z=300.0", rendered)


if __name__ == "__main__":
    unittest.main()
