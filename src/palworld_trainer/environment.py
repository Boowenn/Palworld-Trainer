"""Environment discovery and UE4SS bridge deployment.

The trainer needs to know three things:

1. Where the Palworld install lives (auto-detected, overridable in Settings).
2. Whether UE4SS + ClientCheatCommands are present — cheat commands cannot
   reach the game without them.
3. Whether our own PalworldTrainerBridge Lua mod has been deployed into the
   UE4SS Mods folder (optional, but nice for diagnostics).
"""

from __future__ import annotations

import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path


BRIDGE_MOD_NAME = "PalworldTrainerBridge"
CLIENT_CHEAT_COMMANDS_MOD_NAME = "ClientCheatCommands"


@dataclass
class EnvironmentReport:
    game_root: Path | None
    game_root_exists: bool = False
    launcher_exists: bool = False
    shipping_exists: bool = False
    ue4ss_root_exists: bool = False
    client_cheat_commands_present: bool = False
    client_cheat_commands_active: bool = False
    client_cheat_commands_enum_dir: Path | None = None
    trainer_bridge_deployed: bool = False
    trainer_bridge_target: Path | None = None
    notes: list[str] = field(default_factory=list)

    @property
    def ready_for_cheats(self) -> bool:
        return self.game_root_exists and self.client_cheat_commands_present


def get_repo_root() -> Path:
    """Return the project root (two levels up from this file in dev)."""
    return Path(__file__).resolve().parents[2]


def _looks_like_game_root(path: Path) -> bool:
    return (
        (path / "Palworld.exe").exists()
        and (path / "Pal" / "Binaries" / "Win64" / "Palworld-Win64-Shipping.exe").exists()
    )


def detect_default_game_root() -> Path | None:
    """Best-effort auto-detection of the Palworld install directory."""

    candidates: list[Path] = []

    # When running from source inside the game directory (common during dev).
    repo_root = get_repo_root()
    candidates.append(repo_root.parent)
    candidates.append(repo_root)

    # When running as a packaged exe dropped anywhere.
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).parent
        candidates.append(exe_dir)
        candidates.append(exe_dir.parent)

    candidates.append(Path.cwd())

    # Common Steam install paths on Windows.
    for drive in ("C", "D", "E", "F"):
        candidates.append(Path(f"{drive}:/Program Files (x86)/Steam/steamapps/common/Palworld"))
        candidates.append(Path(f"{drive}:/Steam/steamapps/common/Palworld"))
        candidates.append(Path(f"{drive}:/SteamLibrary/steamapps/common/Palworld"))
        candidates.append(Path(f"{drive}:/steam/steamapps/common/Palworld"))

    seen: set[Path] = set()
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        if resolved in seen:
            continue
        seen.add(resolved)
        if _looks_like_game_root(resolved):
            return resolved
    return None


def resolve_game_root(configured_path: str | None) -> Path | None:
    if configured_path:
        candidate = Path(configured_path)
        if _looks_like_game_root(candidate):
            return candidate
    return detect_default_game_root()


def scan_environment(configured_game_root: str | None) -> EnvironmentReport:
    game_root = resolve_game_root(configured_game_root)

    report = EnvironmentReport(game_root=game_root)
    if not game_root:
        report.notes.append("未能自动定位 Palworld 安装目录，请在 设置 里手动填。")
        return report

    report.game_root_exists = game_root.exists()
    report.launcher_exists = (game_root / "Palworld.exe").exists()
    report.shipping_exists = (
        game_root / "Pal" / "Binaries" / "Win64" / "Palworld-Win64-Shipping.exe"
    ).exists()

    ue4ss_root = game_root / "Mods" / "NativeMods" / "UE4SS"
    report.ue4ss_root_exists = ue4ss_root.exists()

    ccc_mod = ue4ss_root / "Mods" / CLIENT_CHEAT_COMMANDS_MOD_NAME
    report.client_cheat_commands_present = ccc_mod.exists()
    enum_dir = ccc_mod / "Scripts" / "enums"
    if enum_dir.exists():
        report.client_cheat_commands_enum_dir = enum_dir

    pal_mod_settings = game_root / "Mods" / "PalModSettings.ini"
    if pal_mod_settings.exists():
        try:
            contents = pal_mod_settings.read_text(encoding="utf-8")
        except OSError:
            contents = ""
        report.client_cheat_commands_active = "ActiveModList=ClientCheatCommands" in contents

    bridge_target = ue4ss_root / "Mods" / BRIDGE_MOD_NAME
    report.trainer_bridge_target = bridge_target
    report.trainer_bridge_deployed = bridge_target.exists()

    if not report.ue4ss_root_exists:
        report.notes.append(
            "没检测到 UE4SS。请先装 UE4SS Experimental (Palworld) 和 ClientCheatCommands。"
        )
    elif not report.client_cheat_commands_present:
        report.notes.append(
            "UE4SS 已安装但没发现 ClientCheatCommands，大部分作弊命令会失效。"
        )
    elif not report.client_cheat_commands_active:
        report.notes.append(
            "ClientCheatCommands 已存在但未在 PalModSettings.ini 中启用。"
        )
    else:
        report.notes.append("环境就绪：UE4SS + ClientCheatCommands 均已启用。")

    return report


def deploy_bridge(report: EnvironmentReport) -> tuple[bool, str]:
    """Copy the bundled bridge mod into the game's UE4SS Mods folder."""

    if not report.trainer_bridge_target:
        return False, "没定位到 UE4SS Mods 目录。"

    if getattr(sys, "frozen", False):
        # Packaged mode: try exe-adjacent integrations, then MEIPASS.
        exe_dir = Path(sys.executable).parent
        source_candidates = [
            exe_dir / "integrations" / "ue4ss" / BRIDGE_MOD_NAME,
            Path(getattr(sys, "_MEIPASS", exe_dir)) / "integrations" / "ue4ss" / BRIDGE_MOD_NAME,
        ]
    else:
        source_candidates = [
            get_repo_root() / "integrations" / "ue4ss" / BRIDGE_MOD_NAME,
        ]

    source: Path | None = None
    for candidate in source_candidates:
        if candidate.exists():
            source = candidate
            break

    if not source:
        return False, "找不到 bridge 源文件。"

    target = report.trainer_bridge_target
    try:
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(source, target)
    except OSError as error:
        return False, f"部署失败：{error}"

    return True, f"Bridge 已部署到 {target}"
