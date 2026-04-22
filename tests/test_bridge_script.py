from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BRIDGE_SCRIPT = (
    ROOT
    / "integrations"
    / "ue4ss"
    / "PalworldTrainerBridge"
    / "Scripts"
    / "main.lua"
)


class BridgeScriptTests(unittest.TestCase):
    def test_chat_hook_fallback_runs_before_pal_ui_chat(self) -> None:
        text = BRIDGE_SCRIPT.read_text(encoding="utf-8")
        chat_hook_call = "ok, error_message = execute_hidden_via_chat_hook(command_name, args_text)"
        pal_ui_call = "ok, error_message = execute_hidden_via_pal_ui_chat(command_name, args_text)"

        self.assertIn(chat_hook_call, text)
        self.assertIn(pal_ui_call, text)
        self.assertLess(text.index(chat_hook_call), text.index(pal_ui_call))


if __name__ == "__main__":
    unittest.main()
