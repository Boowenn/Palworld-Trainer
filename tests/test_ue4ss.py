from __future__ import annotations

import unittest

from tests import _bootstrap  # noqa: F401
from palworld_trainer.ue4ss import upsert_mods_txt


class UE4SSTests(unittest.TestCase):
    def test_upsert_mods_txt_inserts_before_keybinds(self) -> None:
        content = "ClientCheatCommands : 1\nKeybinds : 0\n"
        updated = upsert_mods_txt(content, "PalworldTrainerBridge", enabled=True)

        self.assertIn("PalworldTrainerBridge : 1\nKeybinds : 0\n", updated)

    def test_upsert_mods_txt_replaces_existing_value(self) -> None:
        content = "PalworldTrainerBridge : 0\nKeybinds : 0\n"
        updated = upsert_mods_txt(content, "PalworldTrainerBridge", enabled=True)

        self.assertIn("PalworldTrainerBridge : 1", updated)
        self.assertNotIn("PalworldTrainerBridge : 0", updated)


if __name__ == "__main__":
    unittest.main()
