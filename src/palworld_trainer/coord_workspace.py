from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable

from .config import config_dir
from .reference_parity import ReferenceCoordEntry


WORKSPACE_FILE_NAME = "coord_workspace.json"
DEFAULT_GROUP_NAME = "默认"


@dataclass
class CoordWorkspaceGroup:
    name: str
    items: list[ReferenceCoordEntry] = field(default_factory=list)


def workspace_path() -> Path:
    return config_dir() / WORKSPACE_FILE_NAME


def seed_groups_from_entries(entries: Iterable[ReferenceCoordEntry]) -> list[CoordWorkspaceGroup]:
    grouped: dict[str, list[ReferenceCoordEntry]] = {}
    for entry in entries:
        grouped.setdefault(entry.group, []).append(entry)
    result: list[CoordWorkspaceGroup] = []
    for name, items in grouped.items():
        result.append(
            CoordWorkspaceGroup(
                name=name,
                items=sorted(items, key=lambda item: item.label.casefold()),
            )
        )
    result.sort(key=lambda item: (item.name != DEFAULT_GROUP_NAME, item.name.casefold()))
    return result


def load_coord_workspace(seed_entries: Iterable[ReferenceCoordEntry]) -> list[CoordWorkspaceGroup]:
    path = workspace_path()
    if not path.exists():
        groups = seed_groups_from_entries(seed_entries)
        save_coord_workspace(groups)
        return groups

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        groups = seed_groups_from_entries(seed_entries)
        save_coord_workspace(groups)
        return groups

    if not isinstance(payload, list):
        groups = seed_groups_from_entries(seed_entries)
        save_coord_workspace(groups)
        return groups

    groups: list[CoordWorkspaceGroup] = []
    for raw_group in payload:
        if not isinstance(raw_group, dict):
            continue
        name = raw_group.get("name")
        raw_items = raw_group.get("items", [])
        if not isinstance(name, str) or not isinstance(raw_items, list):
            continue
        items: list[ReferenceCoordEntry] = []
        for raw_item in raw_items:
            if not isinstance(raw_item, dict):
                continue
            label = raw_item.get("label")
            group = raw_item.get("group", name)
            x = raw_item.get("x")
            y = raw_item.get("y")
            z = raw_item.get("z")
            editable = raw_item.get("editable", True)
            if not isinstance(label, str):
                continue
            try:
                items.append(
                    ReferenceCoordEntry(
                        group=str(group),
                        label=label,
                        x=float(x),
                        y=float(y),
                        z=float(z),
                        editable=bool(editable),
                    )
                )
            except (TypeError, ValueError):
                continue
        groups.append(CoordWorkspaceGroup(name=name, items=items))

    if groups:
        return groups

    groups = seed_groups_from_entries(seed_entries)
    save_coord_workspace(groups)
    return groups


def save_coord_workspace(groups: list[CoordWorkspaceGroup]) -> None:
    serializable = [asdict(group) for group in groups]
    try:
        workspace_path().write_text(
            json.dumps(serializable, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except OSError:
        return
