from __future__ import annotations

import unittest

from palworld_trainer.runtime import (
    get_runtime_command_specs,
    get_runtime_preset_specs,
    render_runtime_commands_text,
    render_runtime_presets_text,
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


if __name__ == "__main__":
    unittest.main()
