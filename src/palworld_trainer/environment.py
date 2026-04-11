from __future__ import annotations

from pathlib import Path

from .models import EnvironmentReport, ModuleStatus, TrainerSettings


BRIDGE_MOD_NAME = "PalworldTrainerBridge"
BRIDGE_LOG_NAME = "session.log"
CLIENT_CHEAT_COMMANDS_MOD_NAME = "ClientCheatCommands"


def get_repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def detect_default_game_root(repo_root: Path) -> Path | None:
    candidates: list[Path] = []

    parent = repo_root.parent
    candidates.append(parent)

    env_root = Path.cwd()
    candidates.append(env_root)

    for candidate in candidates:
        if _looks_like_game_root(candidate):
            return candidate
    return None


def _looks_like_game_root(path: Path) -> bool:
    return (
        (path / "Palworld.exe").exists()
        and (path / "Pal" / "Binaries" / "Win64" / "Palworld-Win64-Shipping.exe").exists()
    )


def resolve_game_root(settings: TrainerSettings, repo_root: Path) -> Path | None:
    if settings.game_root:
        configured = Path(settings.game_root)
        if configured.exists():
            return configured
    return detect_default_game_root(repo_root)


def scan_environment(settings: TrainerSettings) -> EnvironmentReport:
    repo_root = get_repo_root()
    game_root = resolve_game_root(settings, repo_root)
    trainer_bridge_source = repo_root / "integrations" / "ue4ss" / BRIDGE_MOD_NAME

    launcher = game_root / "Palworld.exe" if game_root else None
    shipping = game_root / "Pal" / "Binaries" / "Win64" / "Palworld-Win64-Shipping.exe" if game_root else None
    mods_root = game_root / "Mods" if game_root else None
    ue4ss_root = mods_root / "NativeMods" / "UE4SS" if mods_root else None
    ue4ss_mods = ue4ss_root / "Mods" if ue4ss_root else None
    client_cheat_commands_mod = ue4ss_mods / CLIENT_CHEAT_COMMANDS_MOD_NAME if ue4ss_mods else None
    client_cheat_commands_enum_dir = (
        client_cheat_commands_mod / "Scripts" / "enums" if client_cheat_commands_mod else None
    )
    trainer_bridge_target = ue4ss_mods / BRIDGE_MOD_NAME if ue4ss_mods else None
    trainer_bridge_log = trainer_bridge_target / BRIDGE_LOG_NAME if trainer_bridge_target else None
    pal_mod_settings = mods_root / "PalModSettings.ini" if mods_root else None

    report = EnvironmentReport(
        game_root=game_root,
        repo_root=repo_root,
        game_root_exists=bool(game_root and game_root.exists()),
        launcher_exists=bool(launcher and launcher.exists()),
        shipping_exists=bool(shipping and shipping.exists()),
        mods_root_exists=bool(mods_root and mods_root.exists()),
        ue4ss_root_exists=bool(ue4ss_root and ue4ss_root.exists()),
        ue4ss_mods_exists=bool(ue4ss_mods and ue4ss_mods.exists()),
        active_client_cheat_commands=False,
        active_ue4ss_experimental=False,
        client_cheat_commands_mod_exists=bool(client_cheat_commands_mod and client_cheat_commands_mod.exists()),
        client_cheat_commands_enum_dir_exists=bool(
            client_cheat_commands_enum_dir and client_cheat_commands_enum_dir.exists()
        ),
        client_cheat_commands_enum_dir=client_cheat_commands_enum_dir,
        trainer_bridge_source_exists=trainer_bridge_source.exists(),
        trainer_bridge_deployed=bool(trainer_bridge_target and trainer_bridge_target.exists()),
        trainer_bridge_target=trainer_bridge_target,
        trainer_bridge_log_exists=bool(trainer_bridge_log and trainer_bridge_log.exists()),
        trainer_bridge_log_path=trainer_bridge_log,
    )

    if not report.game_root_exists:
        report.notes.append("Palworld game root was not detected automatically.")
        return report

    if pal_mod_settings and pal_mod_settings.exists():
        try:
            contents = pal_mod_settings.read_text(encoding="utf-8")
        except OSError:
            contents = ""

        report.active_client_cheat_commands = "ActiveModList=ClientCheatCommands" in contents
        report.active_ue4ss_experimental = "ActiveModList=UE4SSExperimentalPW" in contents

    if report.ue4ss_root_exists:
        report.notes.append("UE4SS runtime detected.")
    else:
        report.notes.append("UE4SS runtime not detected in Mods/NativeMods/UE4SS.")

    if report.active_client_cheat_commands:
        report.notes.append("ClientCheatCommands is already enabled in PalModSettings.ini.")

    if report.active_ue4ss_experimental:
        report.notes.append("UE4SSExperimentalPW is already enabled in PalModSettings.ini.")

    if report.client_cheat_commands_mod_exists:
        report.notes.append("ClientCheatCommands mod files are present in the UE4SS Mods folder.")
    else:
        report.notes.append("ClientCheatCommands mod files were not found under Mods/NativeMods/UE4SS/Mods.")

    if report.client_cheat_commands_enum_dir_exists and report.client_cheat_commands_enum_dir:
        report.notes.append(
            f"ClientCheatCommands enum catalogs are available at {report.client_cheat_commands_enum_dir}."
        )

    if report.trainer_bridge_source_exists:
        report.notes.append("PalworldTrainerBridge source is available in the repository.")

    if report.trainer_bridge_deployed:
        report.notes.append("PalworldTrainerBridge is already deployed into the game UE4SS Mods folder.")

    if report.trainer_bridge_log_exists:
        report.notes.append("PalworldTrainerBridge session.log is present and can be opened from the Runtime tab.")

    return report


def build_module_statuses(report: EnvironmentReport) -> list[ModuleStatus]:
    return [
        ModuleStatus(
            key="module-1",
            title="Module 1: Desktop Shell",
            description="Desktop UI, settings persistence, environment scan, and packaging skeleton.",
            status="ready",
        ),
        ModuleStatus(
            key="module-2",
            title="Module 2: UE4SS Bridge",
            description="Deploy and manage our trainer Lua scripts inside the Palworld UE4SS runtime.",
            status=(
                "ready"
                if report.trainer_bridge_deployed
                else "available"
                if report.ue4ss_root_exists and report.trainer_bridge_source_exists
                else "blocked"
            ),
        ),
        ModuleStatus(
            key="module-3",
            title="Module 3: Runtime Diagnostics",
            description="Pure client-side commands for world snapshots, player lists, and generic FindAllOf scans.",
            status=(
                "ready"
                if report.trainer_bridge_deployed
                else "available"
                if report.ue4ss_root_exists and report.trainer_bridge_source_exists
                else "blocked"
            ),
        ),
        ModuleStatus(
            key="module-4",
            title="Module 4: Release Packaging",
            description="Standalone executable builds and GitHub release automation.",
            status="ready",
        ),
        ModuleStatus(
            key="module-5",
            title="Module 5: Preset Scans",
            description="Preset runtime scans, session logging, and desktop shortcuts for common UE4SS diagnostics.",
            status=(
                "ready"
                if report.trainer_bridge_deployed
                else "available"
                if report.ue4ss_root_exists and report.trainer_bridge_source_exists
                else "blocked"
            ),
        ),
        ModuleStatus(
            key="module-6",
            title="Module 6: Host Tools",
            description="Host command deck plus searchable ClientCheatCommands asset catalogs for items, pals, technology, and NPC IDs.",
            status=(
                "ready"
                if report.client_cheat_commands_enum_dir_exists
                else "available"
                if report.client_cheat_commands_mod_exists
                else "blocked"
            ),
        ),
        ModuleStatus(
            key="module-7",
            title="Module 7: Command Composer",
            description="Composable host command presets plus Node 24-ready GitHub Actions workflows.",
            status="ready" if report.game_root_exists else "blocked",
        ),
        ModuleStatus(
            key="module-8",
            title="Module 8: Session Monitor",
            description="Client-side scan bookmarks plus session log summaries for non-host multiplayer visibility.",
            status=(
                "ready"
                if report.trainer_bridge_deployed
                else "available"
                if report.ue4ss_root_exists and report.trainer_bridge_source_exists
                else "blocked"
            ),
        ),
        ModuleStatus(
            key="module-9",
            title="Module 9: Bookmark Library",
            description="Persistent runtime bookmark libraries with import/export support for repeatable non-host scouting routes.",
            status=(
                "ready"
                if report.trainer_bridge_deployed
                else "available"
                if report.ue4ss_root_exists and report.trainer_bridge_source_exists
                else "blocked"
            ),
        ),
    ]
