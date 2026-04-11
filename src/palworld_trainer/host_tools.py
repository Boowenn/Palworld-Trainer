from __future__ import annotations

from pathlib import Path

from .catalog import get_catalog_title, load_catalog, normalize_catalog_kind, search_catalog
from .models import CatalogEntry, HostCommandSpec, HostCommandTemplateSpec


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


def get_host_command_template_specs() -> list[HostCommandTemplateSpec]:
    return [
        HostCommandTemplateSpec(
            key="self_item",
            title="Give Item to Self",
            description="Build an @!giveme command with asset-aware item defaults.",
            category="Inventory",
            arguments=("item_id", "count"),
            example="@!giveme Shield_Ultra 1",
            asset_kind="item",
            asset_argument_index=0,
        ),
        HostCommandTemplateSpec(
            key="target_item",
            title="Give Item to Player",
            description="Build a targeted @!give command for host-side item delivery.",
            category="Inventory",
            arguments=("player", "item_id", "count"),
            example="@!give <player> Head016 1",
            asset_kind="item",
            asset_argument_index=1,
        ),
        HostCommandTemplateSpec(
            key="spawn_pal",
            title="Spawn Pal",
            description="Build an @!spawn command with the selected pal key when available.",
            category="Summons",
            arguments=("pal_id", "count"),
            example="@!spawn Anubis 1",
            asset_kind="pal",
            asset_argument_index=0,
        ),
        HostCommandTemplateSpec(
            key="unlock_tech",
            title="Unlock Technology",
            description="Build an @!unlocktech command from the selected technology entry.",
            category="Progression",
            arguments=("tech_id",),
            example="@!unlocktech GlobalPalStorage",
            asset_kind="technology",
            asset_argument_index=0,
        ),
        HostCommandTemplateSpec(
            key="give_exp",
            title="Give Experience",
            description="Build an @!giveexp command for fast progression tests.",
            category="Progression",
            arguments=("amount",),
            example="@!giveexp 100000",
        ),
        HostCommandTemplateSpec(
            key="teleport_xyz",
            title="Teleport to Coordinates",
            description="Build an @!teleport command using explicit world coordinates.",
            category="Travel",
            arguments=("x", "y", "z"),
            example="@!teleport -12345 6789 250",
        ),
        HostCommandTemplateSpec(
            key="goto_player",
            title="Goto Player",
            description="Build an @!goto command for a player name or identifier.",
            category="Travel",
            arguments=("player",),
            example="@!goto <player>",
        ),
        HostCommandTemplateSpec(
            key="unlock_fast_travel",
            title="Unlock Fast Travel",
            description="Build an @!unlockft command with no extra arguments.",
            category="Travel",
            arguments=(),
            example="@!unlockft",
        ),
        HostCommandTemplateSpec(
            key="set_time",
            title="Set World Time",
            description="Build an @!settime command for event or lighting checks.",
            category="World",
            arguments=("hour",),
            example="@!settime 12",
        ),
        HostCommandTemplateSpec(
            key="fly_toggle",
            title="Toggle Fly",
            description="Build an @!fly command with on/off control.",
            category="Traversal",
            arguments=("state",),
            example="@!fly on",
        ),
        HostCommandTemplateSpec(
            key="get_position",
            title="Get Position",
            description="Build an @!getpos diagnostic command.",
            category="Diagnostics",
            arguments=(),
            example="@!getpos",
        ),
        HostCommandTemplateSpec(
            key="unstuck",
            title="Unstuck Player",
            description="Build an @!unstuck recovery command.",
            category="Diagnostics",
            arguments=(),
            example="@!unstuck",
        ),
    ]


def get_host_command_template(key: str) -> HostCommandTemplateSpec:
    for spec in get_host_command_template_specs():
        if spec.key == key:
            return spec
    supported = ", ".join(spec.key for spec in get_host_command_template_specs())
    raise ValueError(f"Unsupported host command template '{key}'. Supported templates: {supported}")


def _normalized_values(values: list[str] | tuple[str, ...]) -> list[str]:
    return [value.strip() for value in values]


def _value(values: list[str], index: int, default: str) -> str:
    if index < len(values) and values[index]:
        return values[index]
    return default


def _asset_value(values: list[str], index: int, selected_asset_key: str | None, placeholder: str) -> str:
    if index < len(values) and values[index]:
        return values[index]
    if selected_asset_key:
        return selected_asset_key
    return placeholder


def compose_host_command(template_key: str, values: list[str] | tuple[str, ...], selected_asset_key: str | None = None) -> str:
    normalized = _normalized_values(values)
    spec = get_host_command_template(template_key)
    _ = spec

    if template_key == "self_item":
        item_id = _asset_value(normalized, 0, selected_asset_key, "<item_id>")
        count = _value(normalized, 1, "1")
        return f"@!giveme {item_id} {count}"

    if template_key == "target_item":
        player = _value(normalized, 0, "<player>")
        item_id = _asset_value(normalized, 1, selected_asset_key, "<item_id>")
        count = _value(normalized, 2, "1")
        return f"@!give {player} {item_id} {count}"

    if template_key == "spawn_pal":
        pal_id = _asset_value(normalized, 0, selected_asset_key, "<pal_id>")
        count = _value(normalized, 1, "1")
        return f"@!spawn {pal_id} {count}"

    if template_key == "unlock_tech":
        tech_id = _asset_value(normalized, 0, selected_asset_key, "<tech_id>")
        return f"@!unlocktech {tech_id}"

    if template_key == "give_exp":
        amount = _value(normalized, 0, "100000")
        return f"@!giveexp {amount}"

    if template_key == "teleport_xyz":
        x_value = _value(normalized, 0, "<x>")
        y_value = _value(normalized, 1, "<y>")
        z_value = _value(normalized, 2, "<z>")
        return f"@!teleport {x_value} {y_value} {z_value}"

    if template_key == "goto_player":
        player = _value(normalized, 0, "<player>")
        return f"@!goto {player}"

    if template_key == "unlock_fast_travel":
        return "@!unlockft"

    if template_key == "set_time":
        hour = _value(normalized, 0, "12")
        return f"@!settime {hour}"

    if template_key == "fly_toggle":
        state = _value(normalized, 0, "on")
        return f"@!fly {state}"

    if template_key == "get_position":
        return "@!getpos"

    if template_key == "unstuck":
        return "@!unstuck"

    raise ValueError(f"Unsupported host command template '{template_key}'")


def build_entry_command_suggestions(entry: CatalogEntry) -> list[str]:
    if entry.kind == "item":
        return [
            compose_host_command("self_item", [], selected_asset_key=entry.key),
            compose_host_command("target_item", ["<player>"], selected_asset_key=entry.key),
        ]

    if entry.kind == "pal":
        return [compose_host_command("spawn_pal", [], selected_asset_key=entry.key)]

    if entry.kind == "technology":
        return [compose_host_command("unlock_tech", [], selected_asset_key=entry.key)]

    return []


def get_primary_entry_command(entry: CatalogEntry) -> str | None:
    suggestions = build_entry_command_suggestions(entry)
    if not suggestions:
        return None
    return suggestions[0]


def render_host_templates_text() -> str:
    lines = [
        "Command composer templates",
        "--------------------------",
        "The desktop composer can fill placeholders, adopt the selected asset key, and copy the final command line.",
        "",
    ]

    for spec in get_host_command_template_specs():
        arguments = ", ".join(spec.arguments) if spec.arguments else "none"
        lines.extend(
            [
                f"{spec.key}",
                f"  Title      : {spec.title}",
                f"  Category   : {spec.category}",
                f"  Arguments  : {arguments}",
                f"  Description: {spec.description}",
                f"  Example    : {spec.example}",
                "",
            ]
        )

    return "\n".join(lines)


def render_host_commands_text() -> str:
    lines = [
        "Host command deck",
        "-----------------",
        "Module 6+ adds a searchable host/solo command layer around ClientCheatCommands and local enum catalogs.",
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
            "Use the composer presets to edit count, player, coordinate, or time arguments before copying.",
            "NPC catalogs are exposed mainly as searchable IDs because command syntax can vary between builds.",
            "Treat the examples as starter templates if your installed ClientCheatCommands build expects a different argument order.",
            "",
        ]
    )

    lines.extend(render_host_templates_text().splitlines())
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
            "The desktop composer can reuse this asset key in a compatible template with one click.",
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
