"""Minimal settings persistence for the trainer."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path


APP_DIR_NAME = "PalworldTrainer"
SETTINGS_FILE_NAME = "settings.json"


@dataclass
class TrainerSettings:
    game_root: str | None = None
    last_tab: str = "common"
    custom_item_count: int = 1
    custom_pal_count: int = 1
    custom_exp_amount: int = 100000
    recent_item_ids: list[str] = field(default_factory=list)
    recent_pal_ids: list[str] = field(default_factory=list)
    favorite_item_ids: list[str] = field(default_factory=list)
    favorite_pal_ids: list[str] = field(default_factory=list)
    favorite_coord_labels: list[str] = field(default_factory=list)


def _settings_dir_candidates() -> list[Path]:
    candidates: list[Path] = []
    appdata = os.environ.get("APPDATA")
    if appdata:
        candidates.append(Path(appdata) / APP_DIR_NAME)
    candidates.append(Path.home() / f".{APP_DIR_NAME.lower()}")
    candidates.append(Path.cwd() / f".{APP_DIR_NAME.lower()}")
    return candidates


def config_dir() -> Path:
    """Return the writable config directory for the trainer.

    Used both for ``settings.json`` and for sidecar files the engine wants
    to keep across runs (``calibration.json``).
    """

    for root in _settings_dir_candidates():
        try:
            root.mkdir(parents=True, exist_ok=True)
        except OSError:
            continue
        return root
    return _settings_dir_candidates()[-1]


def get_settings_path() -> Path:
    return config_dir() / SETTINGS_FILE_NAME


def load_settings() -> TrainerSettings:
    path = get_settings_path()
    if not path.exists():
        return TrainerSettings()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return TrainerSettings()
    if not isinstance(data, dict):
        return TrainerSettings()

    def _str_list(value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        return [str(item) for item in value if isinstance(item, str)]

    return TrainerSettings(
        game_root=data.get("game_root") if isinstance(data.get("game_root"), str) else None,
        last_tab=str(data.get("last_tab", "common")) or "common",
        custom_item_count=int(data.get("custom_item_count", 1) or 1),
        custom_pal_count=int(data.get("custom_pal_count", 1) or 1),
        custom_exp_amount=int(data.get("custom_exp_amount", 100000) or 100000),
        recent_item_ids=_str_list(data.get("recent_item_ids", [])),
        recent_pal_ids=_str_list(data.get("recent_pal_ids", [])),
        favorite_item_ids=_str_list(data.get("favorite_item_ids", [])),
        favorite_pal_ids=_str_list(data.get("favorite_pal_ids", [])),
        favorite_coord_labels=_str_list(data.get("favorite_coord_labels", [])),
    )


def save_settings(settings: TrainerSettings) -> None:
    path = get_settings_path()
    try:
        path.write_text(
            json.dumps(asdict(settings), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except OSError:
        pass
