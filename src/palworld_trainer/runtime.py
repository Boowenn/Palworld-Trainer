from __future__ import annotations

from .models import RuntimeCommandSpec, RuntimePresetSpec


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


def render_runtime_commands_text() -> str:
    lines = [
        "Runtime diagnostics",
        "-------------------",
        "Modules 3-5 focus on pure client-side runtime commands that remain useful outside host-only flows.",
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
            "Tips",
            "----",
            "Use pt_presets to view the built-in aliases before running pt_scan.",
            "Use pt_find with short UE class names such as PalCharacter, PlayerController, or Character.",
            "Distance output is reported in meters when the queried object exposes actor world coordinates.",
            "pt_repeat and CTRL+F8 replay the most recent pt_find query for quick rescans.",
            "Bridge messages are mirrored into a session log under the deployed PalworldTrainerBridge mod folder.",
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
