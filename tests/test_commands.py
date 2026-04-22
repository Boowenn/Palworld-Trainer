from __future__ import annotations

import unittest

from tests import _bootstrap  # noqa: F401
from palworld_trainer import commands as cmd
from palworld_trainer.catalog import get_bundled_enum_dir, load_all_catalogs


class CommandBuilderTests(unittest.TestCase):
    def test_giveme_formats_item_and_count(self) -> None:
        self.assertEqual("@!giveme Shield_Ultra 5", cmd.giveme("Shield_Ultra", 5))

    def test_giveme_clamps_count_to_at_least_1(self) -> None:
        self.assertEqual("@!giveme Bow 1", cmd.giveme("Bow", 0))
        self.assertEqual("@!giveme Bow 1", cmd.giveme("Bow", -3))

    def test_spawn_pal_formats_correctly(self) -> None:
        self.assertEqual("@!spawn Anubis 2", cmd.spawn_pal("Anubis", 2))

    def test_give_exp_uses_absolute_amount(self) -> None:
        self.assertEqual("@!giveexp 100000", cmd.give_exp(100000))

    def test_unlock_all_tech(self) -> None:
        self.assertEqual("@!unlockalltech", cmd.unlock_all_tech())

    def test_unlock_recipes(self) -> None:
        self.assertEqual("@!unlockrecipes", cmd.unlock_recipes())

    def test_unlock_fast_travel(self) -> None:
        self.assertEqual("@!unlockft", cmd.unlock_fast_travel())

    def test_duplicate_last_pal(self) -> None:
        self.assertEqual("@!duplast", cmd.duplicate_last_pal())

    def test_give_all_statues(self) -> None:
        self.assertEqual("@!giveallstatues", cmd.give_all_statues())

    def test_set_time_clamps_hour(self) -> None:
        self.assertEqual("@!settime 0", cmd.set_time(-1))
        self.assertEqual("@!settime 23", cmd.set_time(50))
        self.assertEqual("@!settime 12", cmd.set_time(12))

    def test_fly_toggles(self) -> None:
        self.assertEqual("@!fly on", cmd.fly(True))
        self.assertEqual("@!fly off", cmd.fly(False))

    def test_teleport_rounds_to_integers(self) -> None:
        self.assertEqual("@!teleport -12345 6789 250", cmd.teleport(-12345.9, 6789.1, 250.5))


class QuickPresetTests(unittest.TestCase):
    def test_presets_are_not_empty(self) -> None:
        self.assertTrue(len(cmd.QUICK_PRESETS) > 0)
        for preset in cmd.QUICK_PRESETS:
            self.assertTrue(preset.items, f"preset {preset.key} has no items")

    def test_preset_commands_emit_giveme_strings(self) -> None:
        preset = cmd.QUICK_PRESETS[0]
        commands = cmd.preset_commands(preset)
        self.assertEqual(len(preset.items), len(commands))
        for line in commands:
            self.assertTrue(line.startswith("@!giveme "))

    def test_find_preset_by_key(self) -> None:
        preset = cmd.QUICK_PRESETS[0]
        self.assertIs(preset, cmd.find_preset(preset.key))
        self.assertIsNone(cmd.find_preset("not_a_preset"))

    def test_presets_only_use_known_bundled_item_keys(self) -> None:
        catalogs = load_all_catalogs(get_bundled_enum_dir())
        item_keys = {entry.key for entry in catalogs["item"]}
        for preset in cmd.QUICK_PRESETS:
            for item_key, _count in preset.items:
                self.assertIn(item_key, item_keys, f"{preset.key} contains missing item {item_key}")

    def test_quick_choice_groups_only_use_known_catalog_keys(self) -> None:
        catalogs = load_all_catalogs(get_bundled_enum_dir())
        lookup = {
            "item": {entry.key for entry in catalogs["item"]},
            "pal": {entry.key for entry in catalogs["pal"]},
            "technology": {entry.key for entry in catalogs["technology"]},
        }
        for group in cmd.ITEM_GUIDE_GROUPS:
            for choice in group.choices:
                self.assertIn(choice.key, lookup["item"], f"item guide {group.key} missing {choice.key}")
        for group in cmd.PAL_GUIDE_GROUPS:
            for choice in group.choices:
                self.assertIn(choice.key, lookup["pal"], f"pal guide {group.key} missing {choice.key}")
        for group in cmd.TECH_GUIDE_GROUPS:
            for choice in group.choices:
                self.assertIn(
                    choice.key,
                    lookup["technology"],
                    f"tech guide {group.key} missing {choice.key}",
                )


if __name__ == "__main__":
    unittest.main()
