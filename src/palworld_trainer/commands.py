"""Command builders for the ClientCheatCommands chat command set.

Every button in the trainer GUI eventually lands here. Keeping the actual
command strings in one file means GUI code can stay pure presentation and
the cheat vocabulary is easy to audit.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class QuickPreset:
    """A named bundle of items that can be handed out in one click."""

    key: str
    title: str
    description: str
    items: tuple[tuple[str, int], ...] = field(default_factory=tuple)


# ---------------------------------------------------------------------------
# Single command builders
# ---------------------------------------------------------------------------


def giveme(item_id: str, count: int = 1) -> str:
    return f"@!giveme {item_id} {max(1, int(count))}"


def give_player(player: str, item_id: str, count: int = 1) -> str:
    target = player.strip() or "<player>"
    return f"@!give {target} {item_id} {max(1, int(count))}"


def spawn_pal(pal_id: str, count: int = 1) -> str:
    return f"@!spawn {pal_id} {max(1, int(count))}"


def give_exp(amount: int) -> str:
    return f"@!giveexp {max(1, int(amount))}"


def unlock_tech(tech_id: str) -> str:
    return f"@!unlocktech {tech_id}"


def unlock_all_tech() -> str:
    return "@!unlockalltech"


def unlock_fast_travel() -> str:
    return "@!unlockft"


def set_time(hour: int) -> str:
    safe_hour = max(0, min(23, int(hour)))
    return f"@!settime {safe_hour}"


def fly(on: bool) -> str:
    return f"@!fly {'on' if on else 'off'}"


def get_position() -> str:
    return "@!getpos"


def unstuck() -> str:
    return "@!unstuck"


def teleport(x: float, y: float, z: float) -> str:
    return f"@!teleport {int(x)} {int(y)} {int(z)}"


def goto_player(player: str) -> str:
    return f"@!goto {player.strip() or '<player>'}"


def help_command() -> str:
    return "@!help"


# ---------------------------------------------------------------------------
# Quick preset bundles
#
# The item keys used here come straight from the ClientCheatCommands
# ``itemdata.lua`` catalog. If a particular build of the mod renames a key
# the command will just be a no-op — the trainer still sends everything else
# in the bundle.
# ---------------------------------------------------------------------------


QUICK_PRESETS: tuple[QuickPreset, ...] = (
    QuickPreset(
        key="starter_kit",
        title="新手大礼包",
        description="基础材料、补给和一把早期武器，快速搭起家底。",
        items=(
            ("WoodLog", 500),
            ("Stone", 500),
            ("Fiber", 300),
            ("PalFluids", 100),
            ("Paldium", 200),
            ("SphereMega", 30),
            ("BerryFruit", 200),
            ("Bread", 50),
            ("CommonShield", 3),
            ("Bow", 1),
            ("WoodArrow", 200),
        ),
    ),
    QuickPreset(
        key="advanced_materials",
        title="高级材料包",
        description="中后期建造与锻造材料，一次性给够一大堆。",
        items=(
            ("IngotIron", 500),
            ("Coal", 500),
            ("IngotRefined", 300),
            ("Cloth", 300),
            ("Leather", 300),
            ("HighQualityCloth", 200),
            ("HighQualityPalOil", 100),
            ("CarbonFiber", 200),
            ("IngotAluminum", 300),
            ("IngotCopper", 300),
        ),
    ),
    QuickPreset(
        key="top_gear",
        title="顶级装备包",
        description="末期盾牌、护甲和近战武器各一份，直接满配。",
        items=(
            ("Shield_Ultra", 5),
            ("ChestArmor_Metal_5", 1),
            ("Head_Metal_5", 1),
            ("ClothArmor_5", 1),
            ("Weapon_MeleeClub_Metal_5", 1),
            ("Accessary_Necklace_Heat", 1),
            ("Accessary_Necklace_Cold", 1),
        ),
    ),
    QuickPreset(
        key="ammo_pack",
        title="弹药补给包",
        description="覆盖弓箭、手枪、步枪、火箭筒的弹药。",
        items=(
            ("WoodArrow", 500),
            ("StoneArrow", 500),
            ("PoisonArrow", 200),
            ("ShotgunBullet", 500),
            ("HandgunBullet", 500),
            ("AssaultRifleBullet", 500),
            ("SniperRifleBullet", 200),
            ("RocketBullet", 50),
            ("FlameThrowerBullet", 300),
        ),
    ),
    QuickPreset(
        key="food_pack",
        title="食物补给包",
        description="一大堆食物，应付长时间冒险不用再跑回基地。",
        items=(
            ("Bread", 200),
            ("GrilledBerry", 200),
            ("Hamburger", 100),
            ("CakeCooked", 50),
            ("PizzaCooked", 50),
            ("MilkCooked", 200),
            ("HoneyCakeCooked", 100),
            ("MushroomCooked", 200),
        ),
    ),
    QuickPreset(
        key="capture_kit",
        title="捕获大礼包",
        description="各种等级的球 + 药水，抓帕鲁不愁。",
        items=(
            ("SphereHyper", 200),
            ("SphereUltra", 200),
            ("SphereLegend", 100),
            ("Medicine_Recover", 50),
            ("Medicine_StatusDown", 30),
        ),
    ),
    QuickPreset(
        key="technology_points",
        title="科技补给包",
        description="科技点 + 古代科技点道具（若当前版本支持）。",
        items=(
            ("TechnologyBook1", 20),
            ("TechnologyBook2", 20),
            ("AncientTechnologyPoint", 20),
        ),
    ),
)


def preset_commands(preset: QuickPreset) -> list[str]:
    return [giveme(item_id, count) for item_id, count in preset.items]


def find_preset(key: str) -> QuickPreset | None:
    for preset in QUICK_PRESETS:
        if preset.key == key:
            return preset
    return None
