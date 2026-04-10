from __future__ import annotations

import shutil
from pathlib import Path

from .environment import BRIDGE_MOD_NAME
from .models import EnvironmentReport


def get_bridge_source_dir(repo_root: Path) -> Path:
    return repo_root / "integrations" / "ue4ss" / BRIDGE_MOD_NAME


def get_bridge_target_dir(game_root: Path) -> Path:
    return game_root / "Mods" / "NativeMods" / "UE4SS" / "Mods" / BRIDGE_MOD_NAME


def upsert_mods_txt(content: str, mod_name: str, enabled: bool = True) -> str:
    lines = content.splitlines()
    desired = f"{mod_name} : {1 if enabled else 0}"
    updated = False

    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith(f"{mod_name} :"):
            lines[index] = desired
            updated = True
            break

    if not updated:
        insert_at = None
        for index, line in enumerate(lines):
            if line.strip().startswith("Keybinds :"):
                insert_at = index
                break

        if insert_at is None:
            lines.append(desired)
        else:
            lines.insert(insert_at, desired)

    normalized = "\n".join(lines).rstrip()
    return normalized + "\n"


def deploy_bridge(report: EnvironmentReport) -> str:
    if not report.game_root or not report.game_root.exists():
        raise FileNotFoundError("Game root is not configured.")

    source_dir = get_bridge_source_dir(report.repo_root)
    if not source_dir.exists():
        raise FileNotFoundError(f"Bridge source was not found: {source_dir}")

    target_dir = get_bridge_target_dir(report.game_root)
    target_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source_dir, target_dir, dirs_exist_ok=True)

    mods_txt_path = report.game_root / "Mods" / "NativeMods" / "UE4SS" / "Mods" / "mods.txt"
    mods_txt_path.parent.mkdir(parents=True, exist_ok=True)

    if mods_txt_path.exists():
        current = mods_txt_path.read_text(encoding="utf-8")
    else:
        current = ""

    updated = upsert_mods_txt(current, BRIDGE_MOD_NAME, enabled=True)
    mods_txt_path.write_text(updated, encoding="utf-8")

    return f"Deployed {BRIDGE_MOD_NAME} to {target_dir}"

