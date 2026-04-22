"""ClientCheatCommands 指令与傻瓜式推荐数据。"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class QuickPreset:
    """一键礼包。"""

    key: str
    title: str
    description: str
    items: tuple[tuple[str, int], ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class QuickChoice:
    """推荐列表里的单个条目。"""

    key: str
    title: str


@dataclass(frozen=True)
class QuickChoiceGroup:
    """傻瓜式点选分组。"""

    key: str
    title: str
    choices: tuple[QuickChoice, ...] = field(default_factory=tuple)


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


def unlock_recipes() -> str:
    return "@!unlockrecipes"


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


def duplicate_last_pal() -> str:
    return "@!duplast"


def give_all_statues() -> str:
    return "@!giveallstatues"


def sanitize_command(raw: str) -> str:
    """把自由输入修成标准 @! 指令。"""

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
    """社区里常见但不一定所有版本都支持的命令。"""

    key: str
    title: str
    command: str
    description: str


EXPERIMENTAL_COMMANDS: tuple[ExperimentalCommand, ...] = (
    ExperimentalCommand(
        "godmode",
        "开启无敌",
        "@!godmode",
        "切换无敌模式。",
    ),
    ExperimentalCommand(
        "infstam",
        "无限体力",
        "@!infstam",
        "切换无限体力。",
    ),
    ExperimentalCommand(
        "infammo",
        "无限弹药",
        "@!infammo",
        "切换无限弹药。",
    ),
    ExperimentalCommand(
        "nodur",
        "无限耐久",
        "@!nodur",
        "切换装备耐久不掉。",
    ),
    ExperimentalCommand(
        "noclip",
        "穿墙模式",
        "@!noclip",
        "切换穿墙移动。",
    ),
    ExperimentalCommand(
        "unlockrecipes",
        "解锁全部配方",
        "@!unlockrecipes",
        "尝试解锁建造和制作配方。",
    ),
    ExperimentalCommand(
        "duplast",
        "复制上次物品",
        "@!duplast",
        "复制最近一次交互的物品。",
    ),
    ExperimentalCommand(
        "giveallstatues",
        "给满绿胖子像",
        "@!giveallstatues",
        "补齐常见能力雕像。",
    ),
)


DISPLAY_NAME_OVERRIDES: dict[str, dict[str, str]] = {
    "item": {
        "Wood": "木材",
        "Stone": "石头",
        "Fiber": "纤维",
        "PalFluid": "帕鲁体液",
        "Pal_crystal_S": "帕金碎块",
        "PalSphere_Mega": "超级帕鲁球",
        "PalSphere_Tera": "高级帕鲁球",
        "PalSphere_Master": "终极帕鲁球",
        "PalSphere_Legend": "传说帕鲁球",
        "Shield_01": "普通护盾",
        "Shield_Ultra": "终极护盾",
        "Arrow": "箭矢",
        "Arrow_Poison": "毒箭",
        "Pan": "面包",
        "Bat": "木棒",
        "Spear": "石矛",
        "Cloth": "布",
        "Cloth2": "高级布",
        "Leather": "皮革",
        "Coal": "煤炭",
        "IronIngot": "精炼金属锭",
        "StealIngot": "帕鲁金属锭",
        "CarbonFiber": "碳纤维",
        "PalOil": "优质帕鲁油",
        "Plastic": "塑钢",
        "PlasticArmor_5": "塑钢护甲 +4",
        "PlasticHelmet_5": "塑钢头盔 +4",
        "LaserRifle_5": "激光步枪 +4",
        "Launcher_Default_5": "火箭筒 +4",
        "Accessory_HP_3": "生命吊坠 +2",
        "Accessory_AT_3": "攻击吊坠 +2",
        "ShotgunBullet": "霰弹",
        "HandgunBullet": "手枪弹",
        "AssaultRifleBullet": "突击步枪弹",
        "RifleBullet": "步枪弹",
        "ExplosiveBullet": "火箭弹",
        "FlamethrowerBullet": "喷火器燃料",
        "Hamburger": "汉堡",
        "Pizza": "披萨",
        "Cake": "蛋糕",
        "Salad": "沙拉",
        "BakedMushroom": "烤蘑菇",
        "Milk": "牛奶",
        "Potion_High": "高品质回复药",
        "Potion_Extreme": "高级回复药",
        "PalRevive": "复活药",
        "TechnologyBook_G1": "高阶技术手册",
        "TechnologyBook_G2": "创新技术手册",
        "TechnologyBook_G3": "未来技术手册",
        "AncientTechnologyBook_G1": "古代技术手册",
    },
    "pal": {
        "Anubis": "阿努比斯",
        "WeaselDragon": "企丸丸",
        "FengyunDeeper": "云海鹿",
        "GuardianDog": "八云犬",
        "Mutant": "鲁娜蒂斯",
        "BlueDragon": "覆海龙",
        "JetDragon": "空涡龙",
        "BlackGriffon": "黑月女王",
        "NightLady_Dark": "贝菈露洁·自由",
        "KingBahamut_Dragon": "腾炎龙·赤魂",
        "DarkMechaDragon": "异构格里芬",
        "IceHorse": "唤冬兽",
        "MoonQueen": "赛琳",
        "SaintCentaur": "圣光骑士",
        "BlackCentaur": "混沌骑士",
        "MimicDog": "米米狗",
        "Suzaku": "朱雀",
    },
    "technology": {
        "BreedFarm": "配种牧场",
        "Special_HatchingPalEgg": "孵蛋器",
        "MultiElectricHatchingPalEgg": "大型电动孵蛋器",
        "Product_Factory_Hard_Grade_03": "生产流水线 II",
        "Product_WeaponFactory_Dirty_Grade_03": "武器流水线 II",
        "Special_SphereFactory_Black_Grade_03": "球体流水线 II",
        "Product_CopperPit_2": "采矿场 II",
        "OilPump": "原油提取机",
        "ElectricGenerator_Large": "大型发电机",
        "Product_Medicine_Grade_02": "电力制药台",
        "Battle_RangeWeapon_AssaultRifle": "突击步枪",
        "Battle_RangeWeapon_Rifle": "单发步枪",
        "Battle_RangeWeapon_ShotGun_Multi": "泵动式霰弹枪",
        "Battle_RangeWeapon_RocketLauncher": "火箭筒",
        "Battle_RangeWeapon_LaserRifle": "激光步枪",
        "Battle_RangeWeapon_HomingSphereLauncher": "追踪球发射器",
        "Special_PalSphere_Grade_02": "超级帕鲁球",
        "Special_PalSphere_Grade_03": "特级帕鲁球",
        "Special_PalSphere_Grade_04": "高级帕鲁球",
        "Special_PalSphere_Grade_06": "传说帕鲁球",
        "SphereFactory_Black_04": "高级球体流水线",
    },
}


QUICK_PRESETS: tuple[QuickPreset, ...] = (
    QuickPreset(
        key="starter_kit",
        title="新手大礼包",
        description="木石纤维、帕金和基础球，开荒点一下就够用。",
        items=(
            ("Wood", 500),
            ("Stone", 500),
            ("Fiber", 300),
            ("PalFluid", 100),
            ("Pal_crystal_S", 200),
            ("PalSphere_Mega", 50),
            ("Pan", 80),
            ("Shield_01", 2),
            ("Spear", 1),
        ),
    ),
    QuickPreset(
        key="advanced_materials",
        title="高级材料包",
        description="中后期常用材料，做装备和流水线省事。",
        items=(
            ("IronIngot", 500),
            ("StealIngot", 300),
            ("Coal", 500),
            ("Cloth", 300),
            ("Cloth2", 200),
            ("Leather", 300),
            ("PalOil", 150),
            ("CarbonFiber", 200),
            ("Plastic", 200),
        ),
    ),
    QuickPreset(
        key="top_gear",
        title="顶级装备包",
        description="护甲、头盔、终极护盾和毕业武器一起补齐。",
        items=(
            ("Shield_Ultra", 3),
            ("PlasticArmor_5", 1),
            ("PlasticHelmet_5", 1),
            ("LaserRifle_5", 1),
            ("Launcher_Default_5", 1),
            ("Accessory_HP_3", 1),
            ("Accessory_AT_3", 1),
        ),
    ),
    QuickPreset(
        key="ammo_pack",
        title="弹药补给包",
        description="常用远程弹药和火箭弹一次补足。",
        items=(
            ("Arrow", 500),
            ("Arrow_Poison", 200),
            ("ShotgunBullet", 500),
            ("HandgunBullet", 500),
            ("AssaultRifleBullet", 500),
            ("RifleBullet", 400),
            ("ExplosiveBullet", 80),
            ("FlamethrowerBullet", 300),
        ),
    ),
    QuickPreset(
        key="food_pack",
        title="食物补给包",
        description="常用料理和补给食物，适合长时间刷图。",
        items=(
            ("Pan", 200),
            ("Hamburger", 120),
            ("Pizza", 80),
            ("Cake", 40),
            ("Salad", 120),
            ("BakedMushroom", 120),
            ("Milk", 200),
        ),
    ),
    QuickPreset(
        key="capture_kit",
        title="捕获大礼包",
        description="高级球、终极球、传说球和恢复药一套到位。",
        items=(
            ("PalSphere_Tera", 150),
            ("PalSphere_Master", 120),
            ("PalSphere_Legend", 80),
            ("Potion_High", 60),
            ("Potion_Extreme", 40),
            ("PalRevive", 20),
        ),
    ),
    QuickPreset(
        key="technology_points",
        title="科技补给包",
        description="各种技术手册直接补，方便追科技。",
        items=(
            ("TechnologyBook_G1", 20),
            ("TechnologyBook_G2", 20),
            ("TechnologyBook_G3", 20),
            ("AncientTechnologyBook_G1", 20),
        ),
    ),
)


ITEM_GUIDE_GROUPS: tuple[QuickChoiceGroup, ...] = (
    QuickChoiceGroup(
        key="starter_materials",
        title="开荒材料",
        choices=(
            QuickChoice("Wood", "木材"),
            QuickChoice("Stone", "石头"),
            QuickChoice("Fiber", "纤维"),
            QuickChoice("PalFluid", "帕鲁体液"),
            QuickChoice("Pal_crystal_S", "帕金碎块"),
            QuickChoice("Pan", "面包"),
        ),
    ),
    QuickChoiceGroup(
        key="advanced_materials",
        title="高级材料",
        choices=(
            QuickChoice("IronIngot", "精炼金属锭"),
            QuickChoice("StealIngot", "帕鲁金属锭"),
            QuickChoice("CarbonFiber", "碳纤维"),
            QuickChoice("PalOil", "优质帕鲁油"),
            QuickChoice("Cloth2", "高级布"),
            QuickChoice("Plastic", "塑钢"),
        ),
    ),
    QuickChoiceGroup(
        key="battle_supplies",
        title="战斗补给",
        choices=(
            QuickChoice("Shield_Ultra", "终极护盾"),
            QuickChoice("LaserRifle_5", "激光步枪 +4"),
            QuickChoice("ShotgunBullet", "霰弹"),
            QuickChoice("AssaultRifleBullet", "突击步枪弹"),
            QuickChoice("ExplosiveBullet", "火箭弹"),
            QuickChoice("FlamethrowerBullet", "喷火器燃料"),
        ),
    ),
    QuickChoiceGroup(
        key="capture_and_meds",
        title="抓宠和药品",
        choices=(
            QuickChoice("PalSphere_Tera", "高级帕鲁球"),
            QuickChoice("PalSphere_Master", "终极帕鲁球"),
            QuickChoice("PalSphere_Legend", "传说帕鲁球"),
            QuickChoice("Potion_High", "高品质回复药"),
            QuickChoice("Potion_Extreme", "高级回复药"),
            QuickChoice("PalRevive", "复活药"),
        ),
    ),
)


PAL_GUIDE_GROUPS: tuple[QuickChoiceGroup, ...] = (
    QuickChoiceGroup(
        key="practical_pals",
        title="开局好用",
        choices=(
            QuickChoice("Anubis", "阿努比斯"),
            QuickChoice("WeaselDragon", "企丸丸"),
            QuickChoice("FengyunDeeper", "云海鹿"),
            QuickChoice("GuardianDog", "八云犬"),
            QuickChoice("Mutant", "鲁娜蒂斯"),
            QuickChoice("BlueDragon", "覆海龙"),
        ),
    ),
    QuickChoiceGroup(
        key="battle_pals",
        title="毕业战斗",
        choices=(
            QuickChoice("JetDragon", "空涡龙"),
            QuickChoice("BlackGriffon", "黑月女王"),
            QuickChoice("NightLady_Dark", "贝菈露洁·自由"),
            QuickChoice("KingBahamut_Dragon", "腾炎龙·赤魂"),
            QuickChoice("DarkMechaDragon", "异构格里芬"),
            QuickChoice("IceHorse", "唤冬兽"),
        ),
    ),
    QuickChoiceGroup(
        key="rare_pals",
        title="热门稀有",
        choices=(
            QuickChoice("MoonQueen", "赛琳"),
            QuickChoice("SaintCentaur", "圣光骑士"),
            QuickChoice("BlackCentaur", "混沌骑士"),
            QuickChoice("MimicDog", "米米狗"),
            QuickChoice("Suzaku", "朱雀"),
            QuickChoice("GuardianDog", "八云犬"),
        ),
    ),
)


TECH_GUIDE_GROUPS: tuple[QuickChoiceGroup, ...] = (
    QuickChoiceGroup(
        key="base_building",
        title="基建必开",
        choices=(
            QuickChoice("BreedFarm", "配种牧场"),
            QuickChoice("Special_HatchingPalEgg", "孵蛋器"),
            QuickChoice("MultiElectricHatchingPalEgg", "大型电动孵蛋器"),
            QuickChoice("Product_Factory_Hard_Grade_03", "生产流水线 II"),
            QuickChoice("Product_WeaponFactory_Dirty_Grade_03", "武器流水线 II"),
            QuickChoice("Special_SphereFactory_Black_Grade_03", "球体流水线 II"),
            QuickChoice("Product_CopperPit_2", "采矿场 II"),
            QuickChoice("OilPump", "原油提取机"),
            QuickChoice("ElectricGenerator_Large", "大型发电机"),
            QuickChoice("Product_Medicine_Grade_02", "电力制药台"),
        ),
    ),
    QuickChoiceGroup(
        key="hot_weapons",
        title="热门武器",
        choices=(
            QuickChoice("Battle_RangeWeapon_AssaultRifle", "突击步枪"),
            QuickChoice("Battle_RangeWeapon_Rifle", "单发步枪"),
            QuickChoice("Battle_RangeWeapon_ShotGun_Multi", "泵动式霰弹枪"),
            QuickChoice("Battle_RangeWeapon_RocketLauncher", "火箭筒"),
            QuickChoice("Battle_RangeWeapon_LaserRifle", "激光步枪"),
            QuickChoice("Battle_RangeWeapon_HomingSphereLauncher", "追踪球发射器"),
        ),
    ),
    QuickChoiceGroup(
        key="sphere_unlocks",
        title="抓宠和球",
        choices=(
            QuickChoice("Special_PalSphere_Grade_02", "超级帕鲁球"),
            QuickChoice("Special_PalSphere_Grade_03", "特级帕鲁球"),
            QuickChoice("Special_PalSphere_Grade_04", "高级帕鲁球"),
            QuickChoice("Special_PalSphere_Grade_06", "传说帕鲁球"),
            QuickChoice("SphereFactory_Black_04", "高级球体流水线"),
        ),
    ),
)


def display_name(kind: str, key: str, fallback: str) -> str:
    return DISPLAY_NAME_OVERRIDES.get(kind, {}).get(key, fallback)


def preset_commands(preset: QuickPreset) -> list[str]:
    return [giveme(item_id, count) for item_id, count in preset.items]


def find_preset(key: str) -> QuickPreset | None:
    for preset in QUICK_PRESETS:
        if preset.key == key:
            return preset
    return None
