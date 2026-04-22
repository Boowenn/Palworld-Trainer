from __future__ import annotations

import unittest

from tests import _bootstrap  # noqa: F401
from palworld_trainer.catalog import CatalogEntry
from palworld_trainer.reference_parity import (
    REFERENCE_ADD_PAL_TABS,
    REFERENCE_ITEM_TABS,
    REFERENCE_PAL_ITEM_GROUP_KEYS,
    ReferenceCoordEntry,
    build_reference_item_groups,
    build_reference_pal_item_groups,
    build_reference_spawn_groups,
)


class ReferenceParityTests(unittest.TestCase):
    def test_reference_item_groups_cover_expected_tabs(self) -> None:
        entries = [
            CatalogEntry("item", "YakushimaArmor001", "Hallowed Plate Mail"),
            CatalogEntry("item", "TechnologyBook_G1", "Technology Book"),
            CatalogEntry("item", "PalSphere_Master", "Master Sphere"),
            CatalogEntry("item", "Arrow", "Arrow"),
            CatalogEntry("item", "Spear", "Spear"),
            CatalogEntry("item", "Hamburger", "Hamburger"),
            CatalogEntry("item", "SkillFruit_Fire", "Fire Fruit"),
        ]

        groups = build_reference_item_groups(entries)

        self.assertEqual(set(REFERENCE_ITEM_TABS), set(groups))
        self.assertEqual(["YakushimaArmor001"], [entry.key for entry in groups["新物品(0.7.0)"]])
        self.assertEqual(["TechnologyBook_G1"], [entry.key for entry in groups["重要物品"]])
        self.assertEqual(["PalSphere_Master"], [entry.key for entry in groups["帕鲁球"]])
        self.assertEqual(["Arrow"], [entry.key for entry in groups["弹药"]])
        self.assertEqual(["Spear"], [entry.key for entry in groups["武器"]])
        self.assertEqual(["Hamburger"], [entry.key for entry in groups["消耗品"]])
        self.assertEqual(["SkillFruit_Fire"], [entry.key for entry in groups["技能果实"]])
        self.assertEqual(len(entries), len(groups["全部"]))

    def test_reference_spawn_groups_match_reference_tabs(self) -> None:
        pal_entries = [
            CatalogEntry("pal", "GYM_SnowTigerBeastman", "Bastigor (Gym)"),
            CatalogEntry("pal", "PREDATOR_Ronin_Dark", "Bushi Noct (Predator)"),
            CatalogEntry("pal", "Lamball", "Lamball"),
        ]
        npc_entries = [
            CatalogEntry("npc", "Hunter_Rifle", "Syndicate Gunner"),
            CatalogEntry("npc", "BOSS_Hunter_Rifle", "Hawk"),
        ]

        groups = build_reference_spawn_groups(pal_entries, npc_entries)

        self.assertEqual(set(REFERENCE_ADD_PAL_TABS), set(groups))
        self.assertEqual(["GYM_SnowTigerBeastman"], [entry.key for entry in groups["塔主"]])
        self.assertEqual(["Lamball"], [entry.key for entry in groups["帕鲁"]])
        self.assertEqual(["PREDATOR_Ronin_Dark"], [entry.key for entry in groups["狂暴"]])
        self.assertEqual(["Hunter_Rifle"], [entry.key for entry in groups["NPC 人类"]])
        self.assertEqual(["BOSS_Hunter_Rifle"], [entry.key for entry in groups["NPC 通缉犯"]])

    def test_reference_coord_entry_stores_workspace_payload(self) -> None:
        entry = ReferenceCoordEntry(group="默认", label="Home", x=1.0, y=2.0, z=3.0)
        self.assertEqual("默认", entry.group)
        self.assertEqual("Home", entry.label)
        self.assertEqual(1.0, entry.x)
        self.assertEqual(2.0, entry.y)
        self.assertEqual(3.0, entry.z)

    def test_reference_pal_item_groups_split_skill_passive_and_support_items(self) -> None:
        entries = [
            CatalogEntry("item", "SkillCard_AirBlade", "Skill Fruit: Air Blade"),
            CatalogEntry(
                "item",
                "PalPassiveSkillChange_PAL_ALLAttack_up1",
                "Implant: Brave",
            ),
            CatalogEntry("item", "ExpBoost_03", "Training Manual (L)"),
            CatalogEntry("item", "PAL_Growth_Stone_L", "Growth Stone L"),
            CatalogEntry("item", "PalRevive", "Revival Potion"),
            CatalogEntry("item", "Wood", "Wood"),
        ]

        groups = build_reference_pal_item_groups(entries)

        self.assertEqual(set(REFERENCE_PAL_ITEM_GROUP_KEYS), set(groups))
        self.assertEqual(["SkillCard_AirBlade"], [entry.key for entry in groups["skill_fruits"]])
        self.assertEqual(
            ["PalPassiveSkillChange_PAL_ALLAttack_up1"],
            [entry.key for entry in groups["passive_implants"]],
        )
        self.assertEqual(
            ["PAL_Growth_Stone_L", "PalRevive", "ExpBoost_03"],
            [entry.key for entry in groups["support_items"]],
        )


if __name__ == "__main__":
    unittest.main()
