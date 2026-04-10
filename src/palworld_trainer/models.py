from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class ModuleStatus:
    key: str
    title: str
    description: str
    status: str


@dataclass(slots=True)
class RuntimeCommandSpec:
    command: str
    description: str
    usage: str
    example: str
    mode: str


@dataclass(slots=True)
class EnvironmentReport:
    game_root: Path | None
    repo_root: Path
    game_root_exists: bool
    launcher_exists: bool
    shipping_exists: bool
    mods_root_exists: bool
    ue4ss_root_exists: bool
    ue4ss_mods_exists: bool
    active_client_cheat_commands: bool
    active_ue4ss_experimental: bool
    trainer_bridge_source_exists: bool
    trainer_bridge_deployed: bool
    trainer_bridge_target: Path | None
    notes: list[str] = field(default_factory=list)


@dataclass(slots=True)
class TrainerSettings:
    game_root: str | None = None
    last_selected_tab: str = "Overview"
