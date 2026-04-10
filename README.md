# Palworld-Trainer

`Palworld-Trainer` is being built in staged modules so we can ship useful slices of the project without waiting for the full trainer stack.

## Current module

Module 1 delivers:

- A desktop trainer shell built with `tkinter`
- Automatic Palworld game root detection
- UE4SS environment scanning
- Settings persistence
- A PyInstaller packaging entry point
- A GitHub Actions workflow template for Windows builds

## Local run

```powershell
python .\run_trainer.py
```

## Local self-check

```powershell
python .\run_trainer.py --self-check
```

## Local build

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build.ps1 -Clean
```

## CI template

The repository includes a ready-to-use workflow template at `docs/build-workflow.yml.example`.
It can be copied into `.github/workflows/build.yml` when the repository token or PAT used for pushes includes the `workflow` scope.

## Planned modules

1. Desktop shell and packaging scaffold
2. UE4SS bridge and script deployment
3. Runtime overlay and trainer actions
4. Final packaging, release automation, and versioned builds
