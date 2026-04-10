from __future__ import annotations

import unittest

from palworld_trainer.runtime import get_runtime_command_specs, render_runtime_commands_text


class RuntimeTests(unittest.TestCase):
    def test_runtime_specs_include_expected_commands(self) -> None:
        commands = [spec.command for spec in get_runtime_command_specs()]

        self.assertIn("pt_world", commands)
        self.assertIn("pt_find <ShortClassName> [limit]", commands)
        self.assertIn("pt_repeat", commands)

    def test_render_runtime_commands_text_mentions_hotkeys(self) -> None:
        rendered = render_runtime_commands_text()

        self.assertIn("CTRL+F6", rendered)
        self.assertIn("CTRL+F8", rendered)
        self.assertIn("PalCharacter", rendered)


if __name__ == "__main__":
    unittest.main()
