from __future__ import annotations

from dataclasses import dataclass


DEFAULT_SAFE_Z = 12000.0


@dataclass(frozen=True)
class BossTeleportPoint:
    key: str
    title: str
    category: str
    map_x: int
    map_y: int
    safe_z: float = DEFAULT_SAFE_Z

    @property
    def world_x(self) -> int:
        # Palworld's displayed map coordinates are axis-flipped relative to
        # the world/save coordinates used by getpos and save data.
        return int(round(self.map_y * 459 - 123888))

    @property
    def world_y(self) -> int:
        return int(round(self.map_x * 459 + 158000))

    @property
    def label(self) -> str:
        return f"[{self.category}] {self.title}"


BOSS_TELEPORT_POINTS: tuple[BossTeleportPoint, ...] = (
    BossTeleportPoint("tower_zoe_grizzbolt", "Zoe & Grizzbolt", "塔主", 112, -434),
    BossTeleportPoint("tower_lily_lyleen", "Lily & Lyleen", "塔主", 185, 28),
    BossTeleportPoint("tower_axel_orserk", "Axel & Orserk", "塔主", -588, -518, 14000.0),
    BossTeleportPoint("tower_marcus_faleris", "Marcus & Faleris", "塔主", 561, 334, 14000.0),
    BossTeleportPoint("tower_victor_shadowbeak", "Victor & Shadowbeak", "塔主", -149, 445, 14000.0),
    BossTeleportPoint("alpha_chillet", "Chillet", "世界 Boss", 171, -416),
    BossTeleportPoint("alpha_gumoss", "Gumoss", "世界 Boss", -110, -628),
    BossTeleportPoint("alpha_sweepa", "Sweepa", "世界 Boss", -228, -595),
    BossTeleportPoint("alpha_penking", "Penking", "世界 Boss", 113, -353),
    BossTeleportPoint("alpha_grintale", "Grintale", "世界 Boss", 359, -245),
    BossTeleportPoint("alpha_azurobe", "Azurobe", "世界 Boss", -23, -386),
    BossTeleportPoint("alpha_nitewing", "Nitewing", "世界 Boss", -273, -69),
    BossTeleportPoint("alpha_kingpaca", "Kingpaca", "世界 Boss", 47, -464),
    BossTeleportPoint("alpha_katress", "Katress", "世界 Boss", 241, -335),
    BossTeleportPoint("alpha_felbat", "Felbat", "世界 Boss", -408, -54),
    BossTeleportPoint("alpha_quivern", "Quivern", "世界 Boss", -258, -129),
    BossTeleportPoint("alpha_bushi", "Bushi", "世界 Boss", -119, -392),
    BossTeleportPoint("alpha_fenglope", "Fenglope", "世界 Boss", -256, -457),
    BossTeleportPoint("alpha_petallia", "Petallia", "世界 Boss", -20, -226),
    BossTeleportPoint("alpha_beakon", "Beakon", "世界 Boss", -346, -254),
    BossTeleportPoint("alpha_warsect", "Warsect", "世界 Boss", 160, -226),
    BossTeleportPoint("alpha_elphidran", "Elphidran", "世界 Boss", 45, -285),
    BossTeleportPoint("alpha_broncherry_aqua", "Broncherry Aqua", "世界 Boss", -166, -447),
    BossTeleportPoint("alpha_relaxaurus_lux", "Relaxaurus Lux", "世界 Boss", -204, -347),
    BossTeleportPoint("alpha_mossanda_lux", "Mossanda Lux", "世界 Boss", 442, -180),
    BossTeleportPoint("alpha_univolt", "Univolt", "世界 Boss", -123, -538),
    BossTeleportPoint("alpha_elizabee", "Elizabee", "世界 Boss", 20, -161),
    BossTeleportPoint("alpha_lunaris", "Lunaris", "世界 Boss", -150, -660),
    BossTeleportPoint("alpha_verdash", "Verdash", "世界 Boss", 286, 8),
    BossTeleportPoint("alpha_vaelet", "Vaelet", "世界 Boss", 129, -52),
    BossTeleportPoint("alpha_mammorest", "Mammorest", "世界 Boss", 176, -474),
    BossTeleportPoint("alpha_sibelyx", "Sibelyx", "世界 Boss", 251, 72, 14000.0),
    BossTeleportPoint("alpha_jormuntide", "Jormuntide", "世界 Boss", -176, -272),
    BossTeleportPoint("alpha_anubis", "Anubis", "世界 Boss", -134, -95),
    BossTeleportPoint("alpha_menasting", "Menasting", "世界 Boss", 513, 100, 14000.0),
    BossTeleportPoint("alpha_suzaku", "Suzaku", "世界 Boss", 403, 254, 14000.0),
    BossTeleportPoint("alpha_dinossom_lux", "Dinossom Lux", "世界 Boss", 349, 533, 14000.0),
    BossTeleportPoint("alpha_paladius", "Paladius", "世界 Boss", 443, 676, 15000.0),
    BossTeleportPoint("alpha_necromus", "Necromus", "世界 Boss", 443, 676, 15000.0),
    BossTeleportPoint("alpha_ice_kingpaca", "Ice Kingpaca", "世界 Boss", -235, 474, 15000.0),
    BossTeleportPoint("alpha_lyleen_noct", "Lyleen Noct", "世界 Boss", -163, 339, 15000.0),
    BossTeleportPoint("alpha_frostallion", "Frostallion", "世界 Boss", -354, 499, 15000.0),
    BossTeleportPoint("alpha_astegon", "Astegon", "世界 Boss", -615, -426, 14000.0),
    BossTeleportPoint("alpha_blazamut", "Blazamut", "世界 Boss", -442, -559, 14000.0),
    BossTeleportPoint("alpha_jetragon", "Jetragon", "世界 Boss", -784, -319, 15000.0),
)
