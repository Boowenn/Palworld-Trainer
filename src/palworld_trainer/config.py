from __future__ import annotations

import json
import os
from dataclasses import asdict
from pathlib import Path

from .models import CollectibleSpec, MapBookmarkSpec, RouteSpec, RuntimeBookmarkSpec, TrainerSettings


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


def _load_map_saved_bookmarks(data: object) -> list[MapBookmarkSpec]:
    if not isinstance(data, list):
        return []

    bookmarks: list[MapBookmarkSpec] = []
    for index, item in enumerate(data, start=1):
        if not isinstance(item, dict):
            continue

        title = str(item.get("title", "")).strip() or f"Map Bookmark {index}"
        category = str(item.get("category", "")).strip() or "note"
        notes = str(item.get("notes", "")).strip() or "Saved map bookmark."
        key = str(item.get("key", "")).strip() or f"map_bookmark_{index}"

        try:
            x = float(item.get("x", 0.0))
            y = float(item.get("y", 0.0))
            z = float(item.get("z", 0.0))
        except (TypeError, ValueError):
            continue

        bookmarks.append(
            MapBookmarkSpec(
                key=key,
                title=title,
                category=category,
                x=x,
                y=y,
                z=z,
                notes=notes,
                origin=str(item.get("origin", "")).strip() or "Saved",
                editable=bool(item.get("editable", True)),
            )
        )

    return bookmarks


def _load_map_saved_routes(data: object) -> list[RouteSpec]:
    if not isinstance(data, list):
        return []

    routes: list[RouteSpec] = []
    for index, item in enumerate(data, start=1):
        if not isinstance(item, dict):
            continue

        raw_bookmark_keys = item.get("bookmark_keys", [])
        if not isinstance(raw_bookmark_keys, list):
            continue

        bookmark_keys = [str(value).strip() for value in raw_bookmark_keys if str(value).strip()]
        if not bookmark_keys:
            continue

        routes.append(
            RouteSpec(
                key=str(item.get("key", "")).strip() or f"route_{index}",
                title=str(item.get("title", "")).strip() or f"Route {index}",
                bookmark_keys=bookmark_keys,
                description=str(item.get("description", "")).strip() or "Saved route library entry.",
                origin=str(item.get("origin", "")).strip() or "Saved",
                editable=bool(item.get("editable", True)),
            )
        )

    return routes


def _load_tracked_collectibles(data: object) -> list[CollectibleSpec]:
    if not isinstance(data, list):
        return []

    collectibles: list[CollectibleSpec] = []
    for index, item in enumerate(data, start=1):
        if not isinstance(item, dict):
            continue

        bookmark_key = str(item.get("bookmark_key", "")).strip()
        if not bookmark_key:
            continue

        collectibles.append(
            CollectibleSpec(
                key=str(item.get("key", "")).strip() or f"collectible_{index}",
                title=str(item.get("title", "")).strip() or f"Collectible {index}",
                bookmark_key=bookmark_key,
                category=str(item.get("category", "")).strip() or "collectible",
                status=str(item.get("status", "")).strip() or "planned",
                notes=str(item.get("notes", "")).strip() or "Tracked collectible entry.",
                origin=str(item.get("origin", "")).strip() or "Saved",
                editable=bool(item.get("editable", True)),
            )
        )

    return collectibles


def get_settings_path() -> Path:
    candidates: list[Path] = []
    appdata = os.environ.get("APPDATA")
    if appdata:
        candidates.append(Path(appdata) / APP_DIR_NAME)

    candidates.append(Path.home() / f".{APP_DIR_NAME.lower()}")
    candidates.append(Path.cwd() / f".{APP_DIR_NAME.lower()}")

    for root in candidates:
        try:
            root.mkdir(parents=True, exist_ok=True)
        except OSError:
            continue
        return root / SETTINGS_FILE_NAME

    return candidates[-1] / SETTINGS_FILE_NAME


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
        map_saved_bookmarks=_load_map_saved_bookmarks(data.get("map_saved_bookmarks", [])),
        map_saved_routes=_load_map_saved_routes(data.get("map_saved_routes", [])),
        tracked_collectibles=_load_tracked_collectibles(data.get("tracked_collectibles", [])),
    )


def save_settings(settings: TrainerSettings) -> None:
    settings_path = get_settings_path()
    payload = asdict(settings)
    settings_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
