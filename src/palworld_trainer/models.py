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
class RuntimePresetSpec:
    key: str
    title: str
    query: str
    description: str
    source: str


@dataclass(slots=True)
class RuntimeBookmarkSpec:
    key: str
    title: str
    command: str
    description: str
    mode: str
    origin: str = "Built-in"
    editable: bool = False


@dataclass(slots=True)
class SessionEvent:
    timestamp: str
    category: str
    message: str


@dataclass(slots=True)
class SessionSummary:
    log_path: Path | None
    log_exists: bool
    total_lines: int
    last_timestamp: str | None
    latest_player_location: str | None
    latest_world_location: str | None
    replicated_players: int | None
    latest_scan_title: str | None
    latest_scan_shown: int | None
    latest_scan_total: int | None
    recent_events: list[str] = field(default_factory=list)
    category_counts: dict[str, int] = field(default_factory=dict)
    events: list[SessionEvent] = field(default_factory=list)


@dataclass(slots=True)
class MapBookmarkSpec:
    key: str
    title: str
    category: str
    x: float
    y: float
    z: float
    notes: str
    origin: str = "Saved"
    editable: bool = True


@dataclass(slots=True)
class RouteSpec:
    key: str
    title: str
    bookmark_keys: list[str]
    description: str
    origin: str = "Saved"
    editable: bool = True


@dataclass(slots=True)
class CollectibleSpec:
    key: str
    title: str
    bookmark_key: str
    category: str
    status: str
    notes: str
    origin: str = "Saved"
    editable: bool = True


@dataclass(slots=True)
class CatalogEntry:
    kind: str
    key: str
    label: str


@dataclass(slots=True)
class HostCommandSpec:
    command: str
    description: str
    example: str
    category: str
    source: str


@dataclass(slots=True)
class HostCommandTemplateSpec:
    key: str
    title: str
    description: str
    category: str
    arguments: tuple[str, ...]
    example: str
    asset_kind: str | None = None
    asset_argument_index: int | None = None


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
    client_cheat_commands_mod_exists: bool
    client_cheat_commands_enum_dir_exists: bool
    client_cheat_commands_enum_dir: Path | None
    trainer_bridge_source_exists: bool
    trainer_bridge_deployed: bool
    trainer_bridge_target: Path | None
    trainer_bridge_log_exists: bool
    trainer_bridge_log_path: Path | None
    notes: list[str] = field(default_factory=list)


@dataclass(slots=True)
class TrainerSettings:
    game_root: str | None = None
    last_selected_tab: str = "Overview"
    runtime_saved_bookmarks: list[RuntimeBookmarkSpec] = field(default_factory=list)
    map_saved_bookmarks: list[MapBookmarkSpec] = field(default_factory=list)
    map_saved_routes: list[RouteSpec] = field(default_factory=list)
    tracked_collectibles: list[CollectibleSpec] = field(default_factory=list)
