from __future__ import annotations

from dataclasses import dataclass

from .catalog import CatalogEntry


REFERENCE_PAL_ITEM_GROUP_KEYS: tuple[str, ...] = (
    "skill_fruits",
    "passive_implants",
    "support_items",
)


REFERENCE_ITEM_TABS: tuple[str, ...] = (
    "新物品(0.7.0)",
    "次新物品(0.6.0)",
    "次新物品(0.5.0)",
    "素材",
    "食材",
    "消耗品",
    "技能果实",
    "重要物品",
    "设计图",
    "帕鲁球",
    "滑翔伞",
    "武器",
    "弹药",
    "防具",
    "装饰",
    "全部",
)

REFERENCE_ADD_PAL_TABS: tuple[str, ...] = (
    "塔主",
    "帕鲁",
    "狂暴",
    "NPC 人类",
    "NPC 通缉犯",
)

REFERENCE_ONLINE_TABS: tuple[str, ...] = (
    "玩家修改",
    "其他",
    "*透视",
)

REFERENCE_PAL_EDIT_TABS: tuple[str, ...] = (
    "基本属性",
    "更多数据",
    "主动技能",
    "习得技能",
    "被动词条",
)

REFERENCE_ADD_PAL_DETAIL_TABS: tuple[str, ...] = (
    "基础",
    "习得技能",
    "更多数据",
)


ITEM_VERSION_070_TOKENS: tuple[str, ...] = (
    "yakushima",
    "hallowed",
    "hexolite",
    "v1 armor",
    "v2 armor",
    "moon lord",
    "cthulhu",
    "pal recruiter",
    "bounty",
    "feybreak",
)

ITEM_VERSION_060_TOKENS: tuple[str, ...] = (
    "plastic",
    "plasteel",
    "crudeoil",
    "crude oil",
    "oilrig",
    "laser",
    "multi climate",
    "air dash",
    "anti-gravity",
)

ITEM_VERSION_050_TOKENS: tuple[str, ...] = (
    "sakurajima",
    "dog coin",
    "dogcoin",
    "lotus",
    "katana",
    "grenade",
    "recovery med",
    "ability glasses",
    "ring of mercy",
)

ITEM_MATERIAL_TOKENS: tuple[str, ...] = (
    "ingot",
    "ore",
    "fragment",
    "cloth",
    "fiber",
    "coal",
    "wood",
    "stone",
    "oil",
    "plastic",
    "pal fluid",
    "fluid",
    "leather",
    "wool",
    "nail",
    "bone",
    "organ",
    "circuit",
    "plasma",
    "bar",
    "plank",
    "cement",
    "gunpowder",
    "crystal",
    "ice organ",
    "electric organ",
    "venom gland",
    "flame organ",
)

ITEM_FOOD_TOKENS: tuple[str, ...] = (
    "berry",
    "egg",
    "milk",
    "wheat",
    "tomato",
    "lettuce",
    "mushroom",
    "meat",
    "venison",
    "flour",
    "honey",
    "water",
)

ITEM_CONSUMABLE_TOKENS: tuple[str, ...] = (
    "potion",
    "medicine",
    "revive",
    "repair",
    "cake",
    "salad",
    "pizza",
    "hamburger",
    "soup",
    "juice",
    "tea",
    "coffee",
    "jam",
    "bread",
    "stew",
    "mushroom saute",
)

ITEM_IMPORTANT_TOKENS: tuple[str, ...] = (
    "technology book",
    "manual",
    "ancient technology",
    "ancient civilization",
    "coin",
    "ticket",
    "medal",
    "passport",
    "key",
    "map",
    "memo",
    "emblem",
    "recruit",
)

ITEM_SKILL_FRUIT_TOKENS: tuple[str, ...] = (
    "fruit",
    "skill fruit",
    "skill card",
)

ITEM_DECOR_TOKENS: tuple[str, ...] = (
    "mask",
    "hat",
    "hood",
    "headgear",
    "hair band",
    "ring",
    "amulet",
    "belt",
    "boots",
    "glasses",
    "kigurumi",
    "costume",
)

ITEM_ARMOR_TOKENS: tuple[str, ...] = (
    "armor",
    "helmet",
    "helm",
    "mail",
    "outfit",
    "shield",
    "head equip",
)

ITEM_WEAPON_TOKENS: tuple[str, ...] = (
    "rifle",
    "shotgun",
    "launcher",
    "bowgun",
    "handgun",
    "smg",
    "katana",
    "spear",
    "bat",
    "sword",
    "rocket",
    "grenade launcher",
    "flamethrower",
    "laser",
)

ITEM_AMMO_TOKENS: tuple[str, ...] = (
    "bullet",
    "arrow",
    "shell",
    "rocket ammo",
    "rocket",
    "missile",
    "grenade",
)


@dataclass(frozen=True)
class ReferenceCoordEntry:
    group: str
    label: str
    x: float
    y: float
    z: float
    editable: bool = True


def _fold(text: str) -> str:
    return text.casefold().strip()


def _contains_any(text: str, tokens: tuple[str, ...]) -> bool:
    return any(token in text for token in tokens)


def _item_bucket(entry: CatalogEntry) -> str:
    key = _fold(entry.key)
    label = _fold(entry.label)
    combined = f"{key} {label}"

    if _contains_any(combined, ITEM_VERSION_070_TOKENS):
        return "新物品(0.7.0)"
    if _contains_any(combined, ITEM_VERSION_060_TOKENS):
        return "次新物品(0.6.0)"
    if _contains_any(combined, ITEM_VERSION_050_TOKENS):
        return "次新物品(0.5.0)"
    if "blueprint" in combined or "design" in combined:
        return "设计图"
    if "sphere" in combined:
        return "帕鲁球"
    if "glider" in combined or "parachute" in combined:
        return "滑翔伞"
    if _contains_any(combined, ITEM_SKILL_FRUIT_TOKENS):
        return "技能果实"
    if _contains_any(combined, ITEM_AMMO_TOKENS):
        return "弹药"
    if _contains_any(combined, ITEM_WEAPON_TOKENS):
        return "武器"
    if _contains_any(combined, ITEM_ARMOR_TOKENS):
        return "防具"
    if _contains_any(combined, ITEM_DECOR_TOKENS):
        return "装饰"
    if _contains_any(combined, ITEM_IMPORTANT_TOKENS):
        return "重要物品"
    if _contains_any(combined, ITEM_CONSUMABLE_TOKENS):
        return "消耗品"
    if _contains_any(combined, ITEM_FOOD_TOKENS):
        return "食材"
    if _contains_any(combined, ITEM_MATERIAL_TOKENS):
        return "素材"
    return "素材"


def build_reference_item_groups(entries: list[CatalogEntry]) -> dict[str, list[CatalogEntry]]:
    groups = {title: [] for title in REFERENCE_ITEM_TABS}
    for entry in entries:
        bucket = _item_bucket(entry)
        groups[bucket].append(entry)
        groups["全部"].append(entry)
    for title in groups:
        groups[title].sort(key=lambda item: (item.label.casefold(), item.key.casefold()))
    return groups


def build_reference_spawn_groups(
    pal_entries: list[CatalogEntry],
    npc_entries: list[CatalogEntry],
) -> dict[str, list[CatalogEntry]]:
    groups = {title: [] for title in REFERENCE_ADD_PAL_TABS}

    for entry in pal_entries:
        key = _fold(entry.key)
        label = _fold(entry.label)
        if key.startswith("gym_") or "(gym)" in label:
            groups["塔主"].append(entry)
        elif key.startswith("predator_") or "(predator)" in label:
            groups["狂暴"].append(entry)
        else:
            groups["帕鲁"].append(entry)

    for entry in npc_entries:
        key = _fold(entry.key)
        label = _fold(entry.label)
        if key.startswith("boss_") or "wanted" in label or "通缉" in label:
            groups["NPC 通缉犯"].append(entry)
        else:
            groups["NPC 人类"].append(entry)

    for title in groups:
        groups[title].sort(key=lambda item: (item.label.casefold(), item.key.casefold()))
    return groups


def build_reference_pal_item_groups(entries: list[CatalogEntry]) -> dict[str, list[CatalogEntry]]:
    groups = {key: [] for key in REFERENCE_PAL_ITEM_GROUP_KEYS}

    for entry in entries:
        key = _fold(entry.key)
        label = _fold(entry.label)
        combined = f"{key} {label}"

        if key.startswith("skillcard_") or "skill fruit" in combined:
            groups["skill_fruits"].append(entry)
            continue
        if key.startswith("palpassiveskillchange_") or "implant:" in combined:
            groups["passive_implants"].append(entry)
            continue
        if (
            key.startswith("expboost_")
            or key.startswith("pal_growth_stone_")
            or key == "palrevive"
            or "training manual" in combined
            or "growth stone" in combined
            or "revival potion" in combined
        ):
            groups["support_items"].append(entry)

    for group_entries in groups.values():
        group_entries.sort(key=lambda item: (item.label.casefold(), item.key.casefold()))
    return groups
