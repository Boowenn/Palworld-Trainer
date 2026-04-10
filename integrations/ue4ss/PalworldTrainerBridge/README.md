# PalworldTrainerBridge

This UE4SS bridge is the runtime integration module for the desktop trainer.

It currently provides:

- `pt_help`
- `pt_status`
- `pt_pos`
- `pt_world`
- `pt_players [limit]`
- `pt_find <ShortClassName> [limit]`
- `pt_repeat`
- `CTRL+F6` to print the local player position
- `CTRL+F7` to print a world snapshot
- `CTRL+F8` to repeat the last `pt_find` scan

Examples:

- `pt_find PalCharacter 12`
- `pt_find PlayerController 8`
- `pt_players 8`

The desktop shell can deploy this folder directly into:

`Mods/NativeMods/UE4SS/Mods/PalworldTrainerBridge`
