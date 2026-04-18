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
# Experimental commands — supported by ClientCheatCommands v2+ (and forks).
# Not all installations will have these. If the mod doesn't recognize the
# command, the game just prints "unknown command" in chat; nothing breaks.
# Names here come from the public chenstack-referenced command set and the
# trainer community docs; trainer sends them as-is without validation.
# ---------------------------------------------------------------------------


def sanitize_command(raw: str) -> str:
    """Normalize a free-form user-typed command.

    - strips whitespace
    - prepends ``@!`` if the user forgot
    - collapses multiple leading ``@!`` / ``/`` tokens
    """

    text = raw.strip()
    if not text:
        return ""
    while text.startswith("/"):
        text = text[1:].lstrip()
    if text.startswith("@!"):
        return text
    if text.startswith("!"):
        return "@" + text
    return "@!" + text


@dataclass(frozen=True)
class ExperimentalCommand:
    """Metadata for a community-documented @! command.

    The trainer bundles a canonical button for it, but explicitly marks
    them as experimental because the installed ClientCheatCommands build
    may or may not recognize them.
    """

    key: str
    title: str
    command: str
    description: str


EXPERIMENTAL_COMMANDS: tuple[ExperimentalCommand, ...] = (
    ExperimentalCommand(
        "godmode", "🛡 无敌 (God Mode)", "@!godmode",
        "切换无敌状态，所有伤害免疫。",
    ),
    ExperimentalCommand(
        "infstam", "⚡ 无限体力", "@!infstam",
        "切换无限体力（不消耗 SP）。",
    ),
    ExperimentalCommand(
        "infammo", "🔫 无限弹药", "@!infammo",
        "切换无限弹药（背包和武器都不扣）。",
    ),
    ExperimentalCommand(
        "nodur", "🛠 无耐久消耗", "@!nodur",
        "切换装备/武器/工具耐久不减少。",
    ),
    ExperimentalCommand(
        "noclip", "👻 穿墙 (Noclip)", "@!noclip",
        "切换穿墙模式，可无视碰撞穿过建筑和地形。",
    ),
    ExperimentalCommand(
        "unlockmap", "🗺 一键开图", "@!unlockmap",
        "清除迷雾、解锁整张世界地图。",
    ),
    ExperimentalCommand(
        "unlockrecipes", "📜 解锁所有配方", "@!unlockrecipes",
        "解锁所有建造与制作配方（不消耗科技点）。",
    ),
    ExperimentalCommand(
        "healfull", "❤ 全额治疗", "@!healfull",
        "把玩家 HP/SP/饱食度/饮水度/体温全部补满。",
    ),
    ExperimentalCommand(
        "fillstatus", "💊 清除负面状态", "@!fillstatus",
        "清除中毒/冰冻/燃烧等所有负面状态。",
    ),
    ExperimentalCommand(
        "homepoint", "🏠 回家", "@!homepoint",
        "传送回上一次记录的家/营地。",
    ),
    ExperimentalCommand(
        "duplast", "🔁 复制上次物品", "@!duplast",
        "复制一份上次拖动/给予的物品（部分 mod 版本支持）。",
    ),
    ExperimentalCommand(
        "giveallstatues", "🗿 全部翠叶鼠雕像", "@!giveallstatues",
        "一次给予全部翠叶鼠（Lifmunk）雕像。",
    ),
    ExperimentalCommand(
        "giveallnotes", "📖 全部手记", "@!giveallnotes",
        "一次给予全部地图手记收集品。",
    ),
)


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
