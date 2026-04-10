from __future__ import annotations

import json
import os
from dataclasses import asdict
from pathlib import Path

from .models import TrainerSettings


APP_DIR_NAME = "PalworldTrainer"
SETTINGS_FILE_NAME = "settings.json"


def get_settings_path() -> Path:
    appdata = os.environ.get("APPDATA")
    if appdata:
        root = Path(appdata) / APP_DIR_NAME
    else:
        root = Path.home() / f".{APP_DIR_NAME.lower()}"
    root.mkdir(parents=True, exist_ok=True)
    return root / SETTINGS_FILE_NAME


def load_settings() -> TrainerSettings:
    settings_path = get_settings_path()
    if not settings_path.exists():
        return TrainerSettings()

    try:
        data = json.loads(settings_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return TrainerSettings()

    return TrainerSettings(
        game_root=data.get("game_root"),
        last_selected_tab=data.get("last_selected_tab", "Overview"),
    )


def save_settings(settings: TrainerSettings) -> None:
    settings_path = get_settings_path()
    payload = asdict(settings)
    settings_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

