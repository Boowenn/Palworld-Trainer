# Palworld-Trainer

`Palworld-Trainer` is being built in staged modules so we can ship useful slices of the project without waiting for the full trainer stack.

## Current module

Module 1 delivers:

- A desktop trainer shell built with `tkinter`
- Automatic Palworld game root detection
- UE4SS environment scanning
- Settings persistence
- A PyInstaller packaging entry point

Module 2 now adds:

- A repository-managed `UE4SS` bridge mod
- Desktop deployment support for the bridge
- Bridge deployment state in the desktop shell and CLI self-check
- A simple in-game diagnostic command set:
  - `pt_help`
  - `pt_status`
  - `pt_pos`
  - `CTRL+F6` hotkey logging
- A live GitHub Actions Windows build workflow

Module 3 now adds:

- A desktop Runtime tab with command references for the deployed bridge features
- Runtime command export through `--list-runtime-commands`
- Client-side world and player snapshots
- Generic `FindAllOf` scans through `pt_find <ShortClassName> [limit]`
- Quick repeat scans through `pt_repeat` and `CTRL+F8`

Module 4 now adds:

- Unified project versioning
- A local release packager that creates a zip archive plus SHA256 checksum
- A GitHub Releases workflow triggered by version tags
- Release-ready Windows packaging from CI

Module 5 now adds:

- Runtime preset scans derived from Palworld asset names and UE base classes
- `pt_presets` and `pt_scan <preset> [limit]` for faster in-game diagnostics
- A bridge session log mirrored to `Mods/NativeMods/UE4SS/Mods/PalworldTrainerBridge/session.log`
- Runtime tab shortcuts to open the deployed bridge folder and session log

Module 6 now adds:

- A desktop `Host Tools` tab for searchable `ClientCheatCommands` asset catalogs
- Local enum parsing for `item`, `pal`, `technology`, and `npc` catalogs
- Copy-ready starter command templates for `@!giveme`, `@!spawn`, and `@!unlocktech`
- Host command export through `--list-host-commands`
- Asset search export through `--search-assets KIND QUERY`

Module 7 now adds:

- A host command composer with adjustable arguments for inventory, spawn, travel, and world commands
- Template export through `--list-host-templates`
- Direct command composition through `--compose-host-command TEMPLATE [args...]`
- Node 24-ready GitHub Actions workflow upgrades for `checkout`, `setup-python`, and `upload-artifact`

Module 8 now adds:

- Runtime scan bookmarks aimed at non-host multiplayer visibility
- A desktop session monitor that parses `session.log` into player position, replicated player counts, recent scans, and recent events
- Runtime bookmark export through `--list-runtime-bookmarks`
- Session summary export through `--session-summary`

Module 9 now adds:

- A persistent saved runtime bookmark library layered on top of the built-in client-safe scan deck
- Runtime bookmark import and export through JSON so scouting routes can move between installs
- A Runtime tab editor for cloning built-ins into reusable non-host multiplayer scan presets
- Saved bookmark export through `--list-saved-runtime-bookmarks`, `--export-runtime-bookmarks PATH`, and `--import-runtime-bookmarks PATH`

Module 10 now adds:

- A Session Explorer that turns `session.log` into structured client-visible event categories
- Runtime-side event filtering for scans, players, world snapshots, bridge status, and other captured messages
- Session event export through `--session-events`, `--session-filter TEXT`, and `--export-session-events PATH`
- Release packaging that now includes a raw `exe` asset alongside the `zip`
- Local build mirroring to the Palworld game root when the repository is inside the game folder

## Local run

```powershell
python .\run_trainer.py
```

## Local self-check

```powershell
python .\run_trainer.py --self-check
```

The self-check now reports bridge availability and whether the bridge has already been deployed into the active game directory.

## Deploy the UE4SS bridge

```powershell
python .\run_trainer.py --deploy-ue4ss-bridge
```

## List runtime commands

```powershell
python .\run_trainer.py --list-runtime-commands
```

## List runtime presets

```powershell
python .\run_trainer.py --list-runtime-presets
```

## List runtime bookmarks

```powershell
python .\run_trainer.py --list-runtime-bookmarks
```

## List saved runtime bookmarks

```powershell
python .\run_trainer.py --list-saved-runtime-bookmarks
```

## Print the current session summary

```powershell
python .\run_trainer.py --session-summary
```

## Explore filtered session events

```powershell
python .\run_trainer.py --session-events
python .\run_trainer.py --session-events --session-filter player
python .\run_trainer.py --export-session-events .\session-events.json --session-filter scan
```

## Export or import saved runtime bookmarks

```powershell
python .\run_trainer.py --export-runtime-bookmarks .\runtime-bookmarks.json
python .\run_trainer.py --import-runtime-bookmarks .\runtime-bookmarks.json
```

## List host commands

```powershell
python .\run_trainer.py --list-host-commands
```

## List host templates

```powershell
python .\run_trainer.py --list-host-templates
```

## Search asset catalogs

```powershell
python .\run_trainer.py --search-assets item shield
python .\run_trainer.py --search-assets pal anubis
python .\run_trainer.py --search-assets technology palbox
```

## Compose host commands

```powershell
python .\run_trainer.py --compose-host-command self_item Shield_Ultra 10
python .\run_trainer.py --compose-host-command teleport_xyz -12345 6789 250
python .\run_trainer.py --compose-host-command set_time 12
```

## Local build

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build.ps1 -Clean
```

## Local release package

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\package_release.ps1 -Clean
```

The local build now writes [PalworldTrainer.exe](/D:/steam/steamapps/common/Palworld/Palworld-Trainer/dist/PalworldTrainer.exe), mirrors a copy to [PalworldTrainer.exe](/D:/steam/steamapps/common/Palworld/PalworldTrainer.exe) when the repo lives under the game directory, and packages both a raw `exe` asset and a `zip` under the `release` folder.

## CI build

The repository now includes an active workflow at `.github/workflows/build.yml`.
The original template is also kept at `docs/build-workflow.yml.example` for reference.

## Release automation

Push a tag such as `v0.10.0` and GitHub Actions will build the Windows package and publish a GitHub Release with the generated `exe`, `zip`, and checksum files.

## Planned modules

1. Desktop shell and packaging scaffold
2. UE4SS bridge and script deployment
3. Runtime diagnostics and command catalog
4. Final packaging, release automation, and versioned builds
5. Preset scans, session logging, and runtime shortcuts
6. Host command tooling and searchable asset catalogs
7. Command composer and Node 24-ready CI workflows
8. Session monitor and client-safe runtime bookmarks
9. Persistent runtime bookmark library and import/export workflows
10. Session explorer, filtered event export, and direct `exe` release assets
