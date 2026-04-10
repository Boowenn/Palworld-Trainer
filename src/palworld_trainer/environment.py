from __future__ import annotations

from pathlib import Path

from .models import EnvironmentReport, ModuleStatus, TrainerSettings


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

    launcher = game_root / "Palworld.exe" if game_root else None
    shipping = game_root / "Pal" / "Binaries" / "Win64" / "Palworld-Win64-Shipping.exe" if game_root else None
    mods_root = game_root / "Mods" if game_root else None
    ue4ss_root = mods_root / "NativeMods" / "UE4SS" if mods_root else None
    ue4ss_mods = ue4ss_root / "Mods" if ue4ss_root else None
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
            status="in progress" if report.ue4ss_root_exists else "blocked",
        ),
        ModuleStatus(
            key="module-3",
            title="Module 3: Runtime Overlay",
            description="Client-side panels, ESP data, and live trainer actions.",
            status="planned",
        ),
        ModuleStatus(
            key="module-4",
            title="Module 4: Release Packaging",
            description="Standalone executable builds and GitHub release automation.",
            status="scaffolded",
        ),
    ]

