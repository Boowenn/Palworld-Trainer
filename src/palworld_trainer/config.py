from __future__ import annotations

import json
import os
from dataclasses import asdict
from pathlib import Path

from .models import RuntimeBookmarkSpec, TrainerSettings


APP_DIR_NAME = "PalworldTrainer"
SETTINGS_FILE_NAME = "settings.json"


def _load_runtime_saved_bookmarks(data: object) -> list[RuntimeBookmarkSpec]:
    if not isinstance(data, list):
        return []

    bookmarks: list[RuntimeBookmarkSpec] = []
    for index, item in enumerate(data, start=1):
        if not isinstance(item, dict):
            continue

        title = str(item.get("title", "")).strip() or f"Saved Bookmark {index}"
        command = str(item.get("command", "")).strip()
        if not command:
            continue

        description = str(item.get("description", "")).strip() or "Saved runtime bookmark."
        key = str(item.get("key", "")).strip() or f"saved_{index}"
        mode = str(item.get("mode", "")).strip() or "Saved library"
        origin = str(item.get("origin", "")).strip() or "Saved"

        bookmarks.append(
            RuntimeBookmarkSpec(
                key=key,
                title=title,
                command=command,
                description=description,
                mode=mode,
                origin=origin,
                editable=bool(item.get("editable", True)),
            )
        )

    return bookmarks


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
        runtime_saved_bookmarks=_load_runtime_saved_bookmarks(data.get("runtime_saved_bookmarks", [])),
    )


def save_settings(settings: TrainerSettings) -> None:
    settings_path = get_settings_path()
    payload = asdict(settings)
    settings_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
