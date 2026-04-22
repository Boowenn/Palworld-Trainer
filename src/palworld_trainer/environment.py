"""Environment discovery and UE4SS bridge deployment.

The trainer needs to know three things:

1. Where the Palworld install lives (auto-detected, overridable in Settings).
2. Whether UE4SS + ClientCheatCommands are present — cheat commands cannot
   reach the game without them.
3. Whether our own PalworldTrainerBridge Lua mod has been deployed into the
   UE4SS Mods folder (optional, but nice for diagnostics).
"""

from __future__ import annotations

import json
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path


BRIDGE_MOD_NAME = "PalworldTrainerBridge"
CLIENT_CHEAT_COMMANDS_MOD_NAME = "ClientCheatCommands"
UE4SS_PROXY_DLL_NAMES = {
    "xinput1_3.dll",
    "dinput8.dll",
    "dxgi.dll",
    "dsound.dll",
    "version.dll",
    "winmm.dll",
}


@dataclass
class EnvironmentReport:
    game_root: Path | None
    game_root_exists: bool = False
    launcher_exists: bool = False
    shipping_exists: bool = False
    game_pid: int | None = None
    ue4ss_root_exists: bool = False
    ue4ss_live_loaded: bool = False
    ue4ss_loader_path: Path | None = None
    mods_globally_enabled: bool = False
    client_cheat_commands_present: bool = False
    client_cheat_commands_active: bool = False
    client_cheat_commands_enum_dir: Path | None = None
    trainer_bridge_deployed: bool = False
    trainer_bridge_enabled: bool = False
    trainer_bridge_target: Path | None = None
    trainer_bridge_runtime_target: Path | None = None
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


def _path_is_inside(root: Path, candidate: Path) -> bool:
    try:
        candidate.resolve().relative_to(root.resolve())
    except (OSError, ValueError):
        return False
    return True


def _is_mod_enabled_in_mods_txt(path: Path, mod_name: str) -> bool:
    if not path.exists():
        return False
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return False

    wanted = mod_name.casefold()
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith(";") or stripped.startswith("#"):
            continue
        name, sep, value = stripped.partition(":")
        if sep and name.strip().casefold() == wanted:
            return value.strip().startswith("1")
    return False


def _is_mod_enabled_in_mods_json(path: Path, mod_name: str) -> bool:
    if not path.exists():
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(payload, list):
        return False

    wanted = mod_name.casefold()
    for item in payload:
        if not isinstance(item, dict):
            continue
        name = item.get("mod_name")
        if isinstance(name, str) and name.casefold() == wanted:
            return bool(item.get("mod_enabled"))
    return False


def _write_mods_txt_enabled(path: Path, mod_name: str) -> None:
    lines: list[str]
    if path.exists():
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            lines = []
    else:
        lines = []

    wanted = mod_name.casefold()
    found = False
    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith(";") or stripped.startswith("#"):
            continue
        name, sep, _value = stripped.partition(":")
        if sep and name.strip().casefold() == wanted:
            lines[index] = f"{mod_name} : 1"
            found = True
            break

    if not found:
        if lines and lines[-1].strip():
            lines.append("")
        lines.append(f"{mod_name} : 1")

    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _write_mods_json_enabled(path: Path, mod_name: str) -> None:
    payload: list[dict[str, object]]
    if path.exists():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            raw = []
        if isinstance(raw, list):
            payload = [item for item in raw if isinstance(item, dict)]
        else:
            payload = []
    else:
        payload = []

    wanted = mod_name.casefold()
    for item in payload:
        name = item.get("mod_name")
        if isinstance(name, str) and name.casefold() == wanted:
            item["mod_enabled"] = True
            break
    else:
        payload.append({"mod_name": mod_name, "mod_enabled": True})

    path.write_text(json.dumps(payload, indent=4, ensure_ascii=False) + "\n", encoding="utf-8")


def _ensure_mod_enabled(mods_root: Path, mod_name: str) -> None:
    mods_root.mkdir(parents=True, exist_ok=True)
    _write_mods_txt_enabled(mods_root / "mods.txt", mod_name)
    _write_mods_json_enabled(mods_root / "mods.json", mod_name)


def _bridge_runtime_candidates(game_root: Path, deployed_target: Path) -> list[Path]:
    win64_root = game_root / "Pal" / "Binaries" / "Win64"
    raw_candidates = [
        deployed_target,
        game_root / "Mods" / BRIDGE_MOD_NAME,
        win64_root / "Mods" / BRIDGE_MOD_NAME,
        win64_root / "Mods" / "NativeMods" / "UE4SS" / "Mods" / BRIDGE_MOD_NAME,
        deployed_target.parent / "NativeMods" / "UE4SS" / "Mods" / BRIDGE_MOD_NAME,
    ]

    candidates: list[Path] = []
    seen: set[Path] = set()
    for candidate in raw_candidates:
        try:
            resolved = candidate.resolve(strict=False)
        except OSError:
            resolved = candidate
        if resolved in seen:
            continue
        seen.add(resolved)
        candidates.append(candidate)
    return candidates


def _bridge_runtime_has_artifacts(target: Path) -> bool:
    return any(
        (target / filename).exists()
        for filename in ("status.json", "request.json", "toggles.json", "session.log")
    )


def _detect_bridge_runtime_target(game_root: Path, deployed_target: Path) -> Path:
    candidates = _bridge_runtime_candidates(game_root, deployed_target)
    for candidate in candidates:
        if _bridge_runtime_has_artifacts(candidate):
            return candidate
    return deployed_target


def _detect_live_ue4ss_loader(game_root: Path) -> tuple[int | None, bool, Path | None]:
    """Inspect the live Palworld process and see whether UE4SS really loaded."""

    from . import memory

    pid = memory.find_process_id()
    if pid is None:
        return None, False, None

    try:
        with memory.ProcessHandle(pid, writable=False) as handle:
            for module in handle.iter_modules():
                name = module.name.lower()
                path = Path(module.path) if module.path else None
                if name == "ue4ss.dll":
                    return pid, True, path
                if (
                    name in UE4SS_PROXY_DLL_NAMES
                    and path is not None
                    and _path_is_inside(game_root, path)
                ):
                    return pid, True, path
    except (OSError, RuntimeError):
        pass

    return pid, False, None


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
        normalized_contents = contents.replace(" ", "").lower()
        report.mods_globally_enabled = "bglobalenablemod=true" in normalized_contents
        report.client_cheat_commands_active = (
            report.mods_globally_enabled
            and "activemodlist=clientcheatcommands" in normalized_contents
        )

    report.game_pid, report.ue4ss_live_loaded, report.ue4ss_loader_path = _detect_live_ue4ss_loader(
        game_root
    )

    mods_root = ue4ss_root / "Mods"
    bridge_target = mods_root / BRIDGE_MOD_NAME
    report.trainer_bridge_target = bridge_target
    report.trainer_bridge_deployed = bridge_target.exists()
    report.trainer_bridge_runtime_target = _detect_bridge_runtime_target(game_root, bridge_target)
    report.trainer_bridge_enabled = _is_mod_enabled_in_mods_txt(
        mods_root / "mods.txt", BRIDGE_MOD_NAME
    ) or _is_mod_enabled_in_mods_json(mods_root / "mods.json", BRIDGE_MOD_NAME)

    if not report.ue4ss_root_exists:
        report.notes.append(
            "没检测到 UE4SS，请先装好 UE4SS 和聊天命令模组（CCC）。"
        )
    elif not report.mods_globally_enabled:
        report.notes.append(
            "模组总开关目前是关闭状态；这次启动里 UE4SS 和聊天命令都不会生效。"
        )
    elif not report.client_cheat_commands_present:
        report.notes.append(
            "UE4SS 已安装，但没发现聊天命令模组（CCC），大部分功能会失效。"
        )
    elif not report.client_cheat_commands_active:
        report.notes.append(
            "聊天命令模组（CCC）已安装，但当前没有启用。"
        )
    elif report.game_pid is not None and not report.ue4ss_live_loaded:
        report.notes.append(
            "当前这次游戏进程没有加载 UE4SS/代理 DLL。聊天命令类功能会完全无效；请先修好 UE4SS 安装，或在确认安装正确后重启游戏。"
        )
    else:
        if report.ue4ss_loader_path is not None:
            report.notes.append(
                f"环境就绪：UE4SS 和聊天命令模组已启用，当前进程已载入 {report.ue4ss_loader_path.name}。"
            )
        else:
            report.notes.append("环境就绪：UE4SS 和聊天命令模组均已启用。")

    if report.trainer_bridge_deployed and not report.trainer_bridge_enabled:
        report.notes.append(
            "增强模块已经复制到 UE4SS 模组目录，重启游戏后就会生效。"
        )

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
        return False, "找不到增强模块源文件。"

    targets: list[Path] = []
    seen: set[Path] = set()
    for candidate in (
        report.trainer_bridge_target,
        report.trainer_bridge_runtime_target,
    ):
        if candidate is None:
            continue
        try:
            resolved = candidate.resolve(strict=False)
        except OSError:
            resolved = candidate
        if resolved in seen:
            continue
        seen.add(resolved)
        targets.append(candidate)

    if not targets:
        return False, "没定位到增强模块目录。"

    try:
        deployed_paths: list[str] = []
        for target in targets:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(source, target, dirs_exist_ok=True)
            _ensure_mod_enabled(target.parent, BRIDGE_MOD_NAME)
            deployed_paths.append(str(target))
        return True, "增强模块已部署并启用: " + " / ".join(deployed_paths)
    except OSError as error:
        return False, f"部署失败：{error}"
