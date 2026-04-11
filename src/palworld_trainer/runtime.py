from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Sequence

from .models import RuntimeBookmarkSpec, RuntimeCommandSpec, RuntimePresetSpec, SessionSummary


SESSION_LINE_PATTERN = re.compile(r"^\[(?P<timestamp>[^\]]+)\]\s+\[[^\]]+\]\s+(?P<message>.+)$")
LOCATION_PATTERN = re.compile(r"X=[-0-9.]+\s+Y=[-0-9.]+\s+Z=[-0-9.]+")
SNAPSHOT_PATTERN = re.compile(r"^(?P<title>.+)\s+\((?P<shown>\d+)\s+shown\s+/\s+(?P<total>\d+)\s+total\)$")
REPLICATED_PATTERN = re.compile(r"^Replicated players:\s+(?P<count>\d+)$")


def get_runtime_command_specs() -> list[RuntimeCommandSpec]:
    return [
        RuntimeCommandSpec(
            command="pt_help",
            description="Print the available bridge commands and hotkeys.",
            usage="pt_help",
            example="pt_help",
            mode="Console",
        ),
        RuntimeCommandSpec(
            command="pt_status",
            description="Show bridge version, player/controller validity, and local coordinates.",
            usage="pt_status",
            example="pt_status",
            mode="Console",
        ),
        RuntimeCommandSpec(
            command="pt_pos",
            description="Print the local player position.",
            usage="pt_pos",
            example="pt_pos",
            mode="Console / CTRL+F6",
        ),
        RuntimeCommandSpec(
            command="pt_world",
            description="Print a quick world snapshot including level and replicated player counts.",
            usage="pt_world",
            example="pt_world",
            mode="Console / CTRL+F7",
        ),
        RuntimeCommandSpec(
            command="pt_players [limit]",
            description="List nearby player pawns known to the local client.",
            usage="pt_players [limit]",
            example="pt_players 8",
            mode="Console",
        ),
        RuntimeCommandSpec(
            command="pt_find <ShortClassName> [limit]",
            description="Run a generic FindAllOf query, sort by local distance when possible, and print the nearest results.",
            usage="pt_find PalCharacter 12",
            example="pt_find PalCharacter 12",
            mode="Console",
        ),
        RuntimeCommandSpec(
            command="pt_presets",
            description="List the built-in runtime scan presets and their underlying class queries.",
            usage="pt_presets",
            example="pt_presets",
            mode="Console",
        ),
        RuntimeCommandSpec(
            command="pt_scan <preset> [limit]",
            description="Run one of the built-in scan presets without typing the raw class name.",
            usage="pt_scan pal_spawners 12",
            example="pt_scan supply_spawners 10",
            mode="Console",
        ),
        RuntimeCommandSpec(
            command="pt_repeat",
            description="Repeat the last pt_find query without retyping it.",
            usage="pt_repeat",
            example="pt_repeat",
            mode="Console / CTRL+F8",
        ),
        RuntimeCommandSpec(
            command="pt_log_status",
            description="Report the bridge session log path and write health.",
            usage="pt_log_status",
            example="pt_log_status",
            mode="Console",
        ),
        RuntimeCommandSpec(
            command="pt_log_clear",
            description="Clear the bridge session log and start a fresh capture.",
            usage="pt_log_clear",
            example="pt_log_clear",
            mode="Console",
        ),
    ]


def get_runtime_preset_specs() -> list[RuntimePresetSpec]:
    return [
        RuntimePresetSpec(
            key="characters",
            title="Nearby Characters",
            query="Character",
            description="Broad replicated character scan for anything deriving from UE Character.",
            source="UE base class",
        ),
        RuntimePresetSpec(
            key="controllers",
            title="Player Controllers",
            query="PlayerController",
            description="Useful for validating controller presence on the local client.",
            source="UE base class",
        ),
        RuntimePresetSpec(
            key="pal_player_controller",
            title="Pal Player Controller",
            query="BP_PalPlayerController_C",
            description="Asset-derived Palworld player controller class.",
            source="Manifest-derived asset name",
        ),
        RuntimePresetSpec(
            key="pal_spawners",
            title="Pal Spawners",
            query="BP_PalSpawner_Standard_C",
            description="Manifest-derived standard Pal spawn points.",
            source="Manifest-derived asset name",
        ),
        RuntimePresetSpec(
            key="npc_spawners",
            title="NPC Spawners",
            query="BP_MonoNPCSpawner_C",
            description="Manifest-derived NPC spawner class.",
            source="Manifest-derived asset name",
        ),
        RuntimePresetSpec(
            key="supply_spawners",
            title="Supply Spawners",
            query="BP_SupplySpawnerBase_C",
            description="Manifest-derived supply drop spawner base class.",
            source="Manifest-derived asset name",
        ),
        RuntimePresetSpec(
            key="pal_managers",
            title="Pal Managers",
            query="BP_PalCharacterManager_C",
            description="Manifest-derived character manager class for world-level state checks.",
            source="Manifest-derived asset name",
        ),
    ]


def get_runtime_bookmark_specs() -> list[RuntimeBookmarkSpec]:
    return [
        RuntimeBookmarkSpec(
            key="status",
            title="Bridge Status",
            command="pt_status",
            description="Validate whether the local controller and player objects are ready.",
            mode="Client-safe",
            origin="Built-in",
        ),
        RuntimeBookmarkSpec(
            key="position",
            title="Local Position",
            command="pt_pos",
            description="Capture the current player position for notes, travel, or debugging.",
            mode="Client-safe",
            origin="Built-in",
        ),
        RuntimeBookmarkSpec(
            key="world_snapshot",
            title="World Snapshot",
            command="pt_world",
            description="Refresh the current world summary and replicated player count.",
            mode="Client-safe",
            origin="Built-in",
        ),
        RuntimeBookmarkSpec(
            key="nearby_players",
            title="Nearby Players",
            command="pt_players 12",
            description="List nearby player pawns visible to the local client.",
            mode="Client-safe",
            origin="Built-in",
        ),
        RuntimeBookmarkSpec(
            key="pal_spawners",
            title="Pal Spawners",
            command="pt_scan pal_spawners 12",
            description="Check local visibility of Pal spawner actors around the player.",
            mode="Client-safe",
            origin="Built-in",
        ),
        RuntimeBookmarkSpec(
            key="supply_spawners",
            title="Supply Spawners",
            command="pt_scan supply_spawners 12",
            description="Scan for supply drop spawners that the client can currently resolve.",
            mode="Client-safe",
            origin="Built-in",
        ),
        RuntimeBookmarkSpec(
            key="npc_spawners",
            title="NPC Spawners",
            command="pt_scan npc_spawners 12",
            description="Scan for nearby NPC spawners without remembering the raw class name.",
            mode="Client-safe",
            origin="Built-in",
        ),
        RuntimeBookmarkSpec(
            key="player_controller",
            title="Player Controller",
            command="pt_scan pal_player_controller 4",
            description="Verify the Palworld player controller class is present on the local client.",
            mode="Client-safe",
            origin="Built-in",
        ),
        RuntimeBookmarkSpec(
            key="repeat_scan",
            title="Repeat Last Scan",
            command="pt_repeat",
            description="Re-run the previous FindAllOf query after moving to a new area.",
            mode="Client-safe",
            origin="Built-in",
        ),
        RuntimeBookmarkSpec(
            key="log_status",
            title="Session Log Status",
            command="pt_log_status",
            description="Confirm the session log path and write health before a long play session.",
            mode="Client-safe",
            origin="Built-in",
        ),
    ]


def build_saved_runtime_bookmark(
    title: str,
    command: str,
    description: str,
    *,
    key: str | None = None,
) -> RuntimeBookmarkSpec:
    normalized_title = title.strip()
    normalized_command = command.strip()
    normalized_description = description.strip() or "Saved runtime bookmark."

    if not normalized_title:
        raise ValueError("Runtime bookmark title cannot be empty.")

    if not normalized_command:
        raise ValueError("Runtime bookmark command cannot be empty.")

    return RuntimeBookmarkSpec(
        key=key or _normalize_runtime_bookmark_key(normalized_title),
        title=normalized_title,
        command=normalized_command,
        description=normalized_description,
        mode="Saved library",
        origin="Saved",
        editable=True,
    )


def get_combined_runtime_bookmark_specs(
    saved_bookmarks: Sequence[RuntimeBookmarkSpec] | None = None,
) -> list[RuntimeBookmarkSpec]:
    bookmarks = list(get_runtime_bookmark_specs())
    if saved_bookmarks:
        bookmarks.extend(saved_bookmarks)
    return bookmarks


def export_runtime_bookmarks(saved_bookmarks: Sequence[RuntimeBookmarkSpec]) -> str:
    payload = {
        "version": 1,
        "bookmarks": [
            {
                "key": bookmark.key,
                "title": bookmark.title,
                "command": bookmark.command,
                "description": bookmark.description,
                "mode": bookmark.mode,
                "origin": bookmark.origin,
                "editable": bookmark.editable,
            }
            for bookmark in saved_bookmarks
        ],
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)


def import_runtime_bookmarks(payload: str) -> list[RuntimeBookmarkSpec]:
    try:
        data = json.loads(payload.lstrip("\ufeff"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid runtime bookmark payload: {exc}") from exc

    if isinstance(data, list):
        raw_bookmarks = data
    elif isinstance(data, dict):
        raw_bookmarks = data.get("bookmarks", [])
    else:
        raise ValueError("Runtime bookmark import payload must be a list or an object with a bookmarks array.")

    if not isinstance(raw_bookmarks, list):
        raise ValueError("Runtime bookmark import payload must contain a bookmarks array.")

    imported: list[RuntimeBookmarkSpec] = []
    for index, item in enumerate(raw_bookmarks, start=1):
        if not isinstance(item, dict):
            continue

        imported.append(
            build_saved_runtime_bookmark(
                str(item.get("title", "")).strip() or f"Imported Bookmark {index}",
                str(item.get("command", "")).strip(),
                str(item.get("description", "")).strip(),
                key=str(item.get("key", "")).strip() or None,
            )
        )

    return merge_runtime_bookmarks([], imported)


def merge_runtime_bookmarks(
    existing: Sequence[RuntimeBookmarkSpec],
    incoming: Sequence[RuntimeBookmarkSpec],
) -> list[RuntimeBookmarkSpec]:
    merged: list[RuntimeBookmarkSpec] = []
    signatures: dict[tuple[str, str], int] = {}

    for bookmark in existing:
        merged.append(bookmark)
        signatures[_runtime_bookmark_signature(bookmark)] = len(merged) - 1

    for bookmark in incoming:
        signature = _runtime_bookmark_signature(bookmark)
        if signature in signatures:
            merged[signatures[signature]] = bookmark
            continue

        key_conflict = next((index for index, existing_bookmark in enumerate(merged) if existing_bookmark.key == bookmark.key), None)
        if key_conflict is not None:
            bookmark = build_saved_runtime_bookmark(
                bookmark.title,
                bookmark.command,
                bookmark.description,
                key=f"{bookmark.key}_{len(merged) + 1}",
            )

        merged.append(bookmark)
        signatures[_runtime_bookmark_signature(bookmark)] = len(merged) - 1

    return merged


def render_saved_runtime_bookmarks_text(saved_bookmarks: Sequence[RuntimeBookmarkSpec]) -> str:
    lines = [
        "Saved runtime bookmarks",
        "-----------------------",
        "Portable client-safe bookmark commands that you can reuse across future solo or non-host multiplayer sessions.",
        "",
    ]

    if not saved_bookmarks:
        lines.append("No saved runtime bookmarks yet.")
        return "\n".join(lines)

    for bookmark in saved_bookmarks:
        lines.extend(
            [
                f"{bookmark.key}",
                f"  Title      : {bookmark.title}",
                f"  Command    : {bookmark.command}",
                f"  Mode       : {bookmark.mode}",
                f"  Description: {bookmark.description}",
                "",
            ]
        )

    return "\n".join(lines)


def parse_session_log(log_path: Path | None) -> SessionSummary:
    summary = SessionSummary(
        log_path=log_path,
        log_exists=bool(log_path and log_path.exists()),
        total_lines=0,
        last_timestamp=None,
        latest_player_location=None,
        latest_world_location=None,
        replicated_players=None,
        latest_scan_title=None,
        latest_scan_shown=None,
        latest_scan_total=None,
        recent_events=[],
    )

    if not log_path or not log_path.exists():
        return summary

    try:
        content = log_path.read_text(encoding="utf-8")
    except OSError:
        return summary

    recent_messages: list[str] = []

    for raw_line in content.splitlines():
        if not raw_line.strip():
            continue

        summary.total_lines += 1
        match = SESSION_LINE_PATTERN.match(raw_line)
        if not match:
            continue

        timestamp = match.group("timestamp")
        message = match.group("message")
        summary.last_timestamp = timestamp
        recent_messages.append(f"[{timestamp}] {message}")
        recent_messages = recent_messages[-8:]

        if message.startswith("Player location: "):
            location_match = LOCATION_PATTERN.search(message)
            if location_match:
                summary.latest_player_location = location_match.group(0)
            continue

        if message.startswith("Local player location: "):
            location_match = LOCATION_PATTERN.search(message)
            if location_match:
                summary.latest_world_location = location_match.group(0)
            continue

        replicated_match = REPLICATED_PATTERN.match(message)
        if replicated_match:
            summary.replicated_players = int(replicated_match.group("count"))
            continue

        snapshot_match = SNAPSHOT_PATTERN.match(message)
        if snapshot_match:
            summary.latest_scan_title = snapshot_match.group("title")
            summary.latest_scan_shown = int(snapshot_match.group("shown"))
            summary.latest_scan_total = int(snapshot_match.group("total"))

    summary.recent_events = recent_messages
    return summary


def render_runtime_commands_text() -> str:
    lines = [
        "Runtime diagnostics",
        "-------------------",
        "Modules 3-8 focus on pure client-side runtime commands that remain useful outside host-only flows.",
        "",
    ]

    for spec in get_runtime_command_specs():
        lines.extend(
            [
                f"{spec.command}",
                f"  Mode       : {spec.mode}",
                f"  Description: {spec.description}",
                f"  Usage      : {spec.usage}",
                f"  Example    : {spec.example}",
                "",
            ]
        )

    lines.extend(
        [
            "Preset scans",
            "------------",
            "Built-in presets wrap common class queries so you do not need to remember the raw names in-game.",
            "",
        ]
    )

    for preset in get_runtime_preset_specs():
        lines.extend(
            [
                f"{preset.key}",
                f"  Title      : {preset.title}",
                f"  Query      : {preset.query}",
                f"  Description: {preset.description}",
                f"  Source     : {preset.source}",
                "",
            ]
        )

    lines.extend(
        [
            "Scan bookmarks",
            "--------------",
            "These copy-friendly shortcuts are tuned for non-host client-side discovery and repeated scans.",
            "",
        ]
    )

    for bookmark in get_runtime_bookmark_specs():
        lines.extend(
            [
                f"{bookmark.title}",
                f"  Command    : {bookmark.command}",
                f"  Mode       : {bookmark.mode}",
                f"  Description: {bookmark.description}",
                "",
            ]
        )

    lines.extend(
        [
            "Tips",
            "----",
            "Use pt_presets to view the built-in aliases before running pt_scan.",
            "Use pt_find with short UE class names such as PalCharacter, PlayerController, or Character.",
            "Distance output is reported in meters when the queried object exposes actor world coordinates.",
            "pt_repeat and CTRL+F8 replay the most recent pt_find query for quick rescans.",
            "Bridge messages are mirrored into a session log under the deployed PalworldTrainerBridge mod folder.",
            "The Session Monitor parses that log so non-host sessions still produce useful client-visible summaries.",
        ]
    )
    return "\n".join(lines)


def render_runtime_presets_text() -> str:
    lines = [
        "Runtime presets",
        "---------------",
        "Built-in aliases for common client-visible classes and manager objects.",
        "",
    ]

    for preset in get_runtime_preset_specs():
        lines.extend(
            [
                f"{preset.key}",
                f"  Title      : {preset.title}",
                f"  Query      : {preset.query}",
                f"  Description: {preset.description}",
                f"  Source     : {preset.source}",
                "",
            ]
        )

    lines.extend(
        [
            "Examples",
            "--------",
            "pt_scan pal_spawners 12",
            "pt_scan supply_spawners 10",
            "pt_scan pal_player_controller 4",
        ]
    )
    return "\n".join(lines)


def render_runtime_bookmarks_text(saved_bookmarks: Sequence[RuntimeBookmarkSpec] | None = None) -> str:
    lines = [
        "Runtime bookmarks",
        "-----------------",
        "Copy-friendly scan shortcuts that stay useful even for non-host players when another player is hosting the session.",
        "",
        "Built-in bookmarks",
        "------------------",
        "",
    ]

    for bookmark in get_runtime_bookmark_specs():
        lines.extend(
            [
                f"{bookmark.key}",
                f"  Title      : {bookmark.title}",
                f"  Command    : {bookmark.command}",
                f"  Mode       : {bookmark.mode}",
                f"  Origin     : {bookmark.origin}",
                f"  Description: {bookmark.description}",
                "",
            ]
        )

    lines.extend(
        [
            "Saved bookmark library",
            "----------------------",
            "Use the Runtime tab to clone built-ins into a reusable personal scan deck, then import or export it between installs.",
            "",
        ]
    )

    if saved_bookmarks:
        for bookmark in saved_bookmarks:
            lines.extend(
                [
                    f"{bookmark.key}",
                    f"  Title      : {bookmark.title}",
                    f"  Command    : {bookmark.command}",
                    f"  Mode       : {bookmark.mode}",
                    f"  Origin     : {bookmark.origin}",
                    f"  Description: {bookmark.description}",
                    "",
                ]
            )
    else:
        lines.append("No saved runtime bookmarks yet.")

    return "\n".join(lines)


def render_session_summary_text(summary: SessionSummary, *, saved_bookmark_count: int = 0) -> str:
    lines = [
        "Session monitor",
        "---------------",
        f"Log path            : {summary.log_path or 'Not available'}",
        f"Log exists          : {'Yes' if summary.log_exists else 'No'}",
        f"Parsed log lines    : {summary.total_lines}",
        f"Last timestamp      : {summary.last_timestamp or 'n/a'}",
        f"Latest player pos   : {summary.latest_player_location or 'n/a'}",
        f"Latest world pos    : {summary.latest_world_location or 'n/a'}",
        f"Replicated players  : {summary.replicated_players if summary.replicated_players is not None else 'n/a'}",
        f"Latest scan title   : {summary.latest_scan_title or 'n/a'}",
        f"Latest scan counts  : "
        f"{f'{summary.latest_scan_shown} shown / {summary.latest_scan_total} total' if summary.latest_scan_title else 'n/a'}",
        f"Saved bookmarks     : {saved_bookmark_count}",
        "",
        "Recent events",
        "-------------",
    ]

    if summary.recent_events:
        lines.extend(summary.recent_events)
    else:
        lines.append("No session log events have been captured yet.")

    lines.extend(
        [
            "",
            "Suggested next scans",
            "--------------------",
            *_build_session_followups(summary),
            "",
            "Usage",
            "-----",
            "Start the game, let the UE4SS bridge load, then press CTRL+F6/F7/F8 or run pt_* commands in the console.",
            "Refresh this monitor after a play session to extract the latest client-visible findings.",
        ]
    )
    return "\n".join(lines)


def _normalize_runtime_bookmark_key(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", value.strip().casefold()).strip("_")
    return normalized or "saved_bookmark"


def _runtime_bookmark_signature(bookmark: RuntimeBookmarkSpec) -> tuple[str, str]:
    return (bookmark.title.casefold(), bookmark.command.casefold())


def _build_session_followups(summary: SessionSummary) -> list[str]:
    suggestions: list[str] = []

    if not summary.log_exists or summary.total_lines == 0:
        suggestions.extend(
            [
                "pt_status  -> validate the bridge before starting a route.",
                "pt_world   -> capture a fresh snapshot for the current area.",
                "pt_players 12 -> check nearby replicated players in non-host sessions.",
            ]
        )
        return suggestions

    if summary.replicated_players and summary.replicated_players > 1:
        suggestions.append("pt_players 12 -> refresh nearby player visibility after moving to a new zone.")

    if summary.latest_scan_title:
        suggestions.append("pt_repeat -> re-run the last scan after repositioning for a new local sample.")
    else:
        suggestions.append("pt_scan pal_spawners 12 -> probe nearby Pal spawn actors around the current location.")

    if summary.latest_player_location:
        suggestions.append("pt_pos -> capture the current local coordinates for your bookmark notes.")

    if not suggestions:
        suggestions.append("pt_world -> grab a baseline world snapshot for this session.")

    return suggestions
