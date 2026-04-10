from __future__ import annotations

from .models import RuntimeCommandSpec


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
            command="pt_repeat",
            description="Repeat the last pt_find query without retyping it.",
            usage="pt_repeat",
            example="pt_repeat",
            mode="Console / CTRL+F8",
        ),
    ]


def render_runtime_commands_text() -> str:
    lines = [
        "Runtime diagnostics",
        "-------------------",
        "Module 3 focuses on pure client-side runtime commands that remain useful outside host-only flows.",
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
            "Tips",
            "----",
            "Use pt_find with short UE class names such as PalCharacter, PlayerController, or Character.",
            "Distance output is reported in meters when the queried object exposes actor world coordinates.",
            "pt_repeat and CTRL+F8 replay the most recent pt_find query for quick rescans.",
        ]
    )
    return "\n".join(lines)
