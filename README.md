# Palworld-Trainer

`Palworld-Trainer` is being built in staged modules so we can ship useful slices of the project without waiting for the full trainer stack.

## Current module

Module 1 delivers:

- A desktop trainer shell built with `tkinter`
- Automatic Palworld game root detection
- UE4SS environment scanning
- Settings persistence
- A PyInstaller packaging entry point
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

## Local build

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build.ps1 -Clean
```

## CI build

The repository now includes an active workflow at `.github/workflows/build.yml`.
The original template is also kept at `docs/build-workflow.yml.example` for reference.

## Planned modules

1. Desktop shell and packaging scaffold
2. UE4SS bridge and script deployment
3. Runtime overlay and trainer actions
4. Final packaging, release automation, and versioned builds
