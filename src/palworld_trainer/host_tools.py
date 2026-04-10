from __future__ import annotations

from pathlib import Path

from .catalog import get_catalog_title, load_catalog, normalize_catalog_kind, search_catalog
from .models import CatalogEntry, HostCommandSpec


HOST_COMMAND_SOURCE = "ClientCheatCommands public command list plus local enum catalogs"


def get_host_command_specs() -> list[HostCommandSpec]:
    return [
        HostCommandSpec(
            command="@!help",
            description="Print the public ClientCheatCommands command list in chat.",
            example="@!help",
            category="Reference",
            source=HOST_COMMAND_SOURCE,
        ),
        HostCommandSpec(
            command="@!giveme <itemId> [count]",
            description="Give the local player items using keys from itemdata.lua.",
            example="@!giveme Shield_Ultra 1",
            category="Inventory",
            source=HOST_COMMAND_SOURCE,
        ),
        HostCommandSpec(
            command="@!give <player> <itemId> [count]",
            description="Give items to another player when the installed build exposes targeted give support.",
            example="@!give <player> Head016 1",
            category="Inventory",
            source=HOST_COMMAND_SOURCE,
        ),
        HostCommandSpec(
            command="@!giveexp <amount>",
            description="Grant experience for quick level-up and unlock testing.",
            example="@!giveexp 100000",
            category="Progression",
            source=HOST_COMMAND_SOURCE,
        ),
        HostCommandSpec(
            command="@!spawn <palId> [count]",
            description="Spawn pals using keys from paldata.lua.",
            example="@!spawn Anubis 1",
            category="Summons",
            source=HOST_COMMAND_SOURCE,
        ),
        HostCommandSpec(
            command="@!teleport <x> <y> <z>",
            description="Teleport to a specific world coordinate.",
            example="@!teleport -12345 6789 250",
            category="Travel",
            source=HOST_COMMAND_SOURCE,
        ),
        HostCommandSpec(
            command="@!goto <player>",
            description="Snap to another player without entering raw coordinates.",
            example="@!goto <player>",
            category="Travel",
            source=HOST_COMMAND_SOURCE,
        ),
        HostCommandSpec(
            command="@!fly [on|off]",
            description="Toggle free-flight style traversal for host-side testing.",
            example="@!fly on",
            category="Traversal",
            source=HOST_COMMAND_SOURCE,
        ),
        HostCommandSpec(
            command="@!settime <hour>",
            description="Jump the world clock to a target hour for event checks.",
            example="@!settime 12",
            category="World",
            source=HOST_COMMAND_SOURCE,
        ),
        HostCommandSpec(
            command="@!getpos",
            description="Print the current player position for travel macros and bookmarks.",
            example="@!getpos",
            category="Diagnostics",
            source=HOST_COMMAND_SOURCE,
        ),
        HostCommandSpec(
            command="@!unstuck",
            description="Recover the local player from bad movement states.",
            example="@!unstuck",
            category="Diagnostics",
            source=HOST_COMMAND_SOURCE,
        ),
        HostCommandSpec(
            command="@!unlocktech <techId>",
            description="Unlock a specific technology using keys from technologydata.lua.",
            example="@!unlocktech GlobalPalStorage",
            category="Progression",
            source=HOST_COMMAND_SOURCE,
        ),
        HostCommandSpec(
            command="@!unlockalltech",
            description="Unlock the full technology list exposed by the current command build.",
            example="@!unlockalltech",
            category="Progression",
            source=HOST_COMMAND_SOURCE,
        ),
        HostCommandSpec(
            command="@!unlockft",
            description="Unlock fast-travel points for movement-heavy testing.",
            example="@!unlockft",
            category="Travel",
            source=HOST_COMMAND_SOURCE,
        ),
    ]


def build_entry_command_suggestions(entry: CatalogEntry) -> list[str]:
    if entry.kind == "item":
        return [
            f"@!giveme {entry.key} 1",
            f"@!give <player> {entry.key} 1",
        ]

    if entry.kind == "pal":
        return [f"@!spawn {entry.key} 1"]

    if entry.kind == "technology":
        return [f"@!unlocktech {entry.key}"]

    return []


def get_primary_entry_command(entry: CatalogEntry) -> str | None:
    suggestions = build_entry_command_suggestions(entry)
    if not suggestions:
        return None
    return suggestions[0]


def render_host_commands_text() -> str:
    lines = [
        "Host command deck",
        "-----------------",
        "Module 6 adds a searchable host/solo command layer around ClientCheatCommands and local enum catalogs.",
        "",
    ]

    for spec in get_host_command_specs():
        lines.extend(
            [
                f"{spec.command}",
                f"  Category   : {spec.category}",
                f"  Description: {spec.description}",
                f"  Example    : {spec.example}",
                f"  Source     : {spec.source}",
                "",
            ]
        )

    lines.extend(
        [
            "Tips",
            "----",
            "Use item search results with @!giveme for fast inventory tests.",
            "Use pal search results with @!spawn for summon templates.",
            "Use technology search results with @!unlocktech for targeted unlocks.",
            "NPC catalogs are exposed mainly as searchable IDs because command syntax can vary between builds.",
            "Treat the examples as ready-to-edit templates if your installed ClientCheatCommands build expects a different argument order.",
        ]
    )
    return "\n".join(lines)


def render_host_entry_text(entry: CatalogEntry) -> str:
    lines = [
        "Selected catalog entry",
        "----------------------",
        f"Kind       : {get_catalog_title(entry.kind)}",
        f"Label      : {entry.label}",
        f"Key        : {entry.key}",
        f"Source     : {entry.kind} enum catalog",
        "",
        "Suggested commands",
        "------------------",
    ]

    suggestions = build_entry_command_suggestions(entry)
    if suggestions:
        lines.extend(suggestions)
    else:
        lines.append("No ready-made command template is shipped for this catalog kind yet.")

    lines.extend(
        [
            "",
            "Notes",
            "-----",
            "These templates are meant for host or solo command flows.",
            "If your installed command build uses a different argument order, treat the copied line as a starter template.",
        ]
    )
    return "\n".join(lines)


def render_host_search_text(enum_dir: Path | None, kind: str, query: str, limit: int = 20) -> str:
    normalized = normalize_catalog_kind(kind)
    title = get_catalog_title(normalized)
    stripped_query = query.strip()

    lines = [
        "Host asset search",
        "-----------------",
        f"Catalog kind : {title} ({normalized})",
        f"Query        : {stripped_query or '<empty>'}",
    ]

    if not enum_dir or not enum_dir.exists():
        lines.extend(
            [
                "Enum dir     : Not available",
                "",
                "ClientCheatCommands enum catalogs were not detected under the configured game root.",
            ]
        )
        return "\n".join(lines)

    lines.extend(
        [
            f"Enum dir     : {enum_dir}",
            "",
        ]
    )

    entries = load_catalog(enum_dir, normalized)
    matches = search_catalog(entries, stripped_query, limit=limit)

    if not matches:
        lines.append("No matching assets were found.")
        return "\n".join(lines)

    for index, entry in enumerate(matches, start=1):
        lines.append(f"{index}. {entry.label} [{entry.key}]")
        suggestions = build_entry_command_suggestions(entry)
        if suggestions:
            lines.append(f"   Suggested: {suggestions[0]}")

    return "\n".join(lines)
