"""Teleport preset loader for categorized Palworld coordinate libraries."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path


COORD_FILE_NAME = "Palworld.Coords.json"
ALL_GROUPS_LABEL = "全部分类"


@dataclass(frozen=True)
class CoordPreset:
    group: str
    name: str
    x: float
    y: float
    z: float

    @property
    def label(self) -> str:
        return f"[{self.group}] {self.name}"


@dataclass(frozen=True)
class CoordPresetGroup:
    name: str
    items: tuple[CoordPreset, ...]


def get_bundled_coord_file() -> Path:
    """Return the coordinate library bundled with the trainer."""

    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
        return base / "palworld_trainer" / "data" / "coords" / COORD_FILE_NAME
    return Path(__file__).resolve().parent / "data" / "coords" / COORD_FILE_NAME


def coord_file_candidates(game_root: Path | None) -> list[Path]:
    """Return possible coordinate-library files ordered by preference."""

    candidates: list[Path] = []
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).parent
        candidates.append(exe_dir / COORD_FILE_NAME)

    if game_root is not None:
        candidates.append(game_root / COORD_FILE_NAME)

    candidates.append(Path.cwd() / COORD_FILE_NAME)
    candidates.append(get_bundled_coord_file())

    ordered: list[Path] = []
    seen: set[Path] = set()
    for candidate in candidates:
        try:
            resolved = candidate.resolve(strict=False)
        except OSError:
            resolved = candidate
        if resolved in seen:
            continue
        seen.add(resolved)
        ordered.append(candidate)
    return ordered


def pick_coord_file(game_root: Path | None) -> Path | None:
    """Pick the first existing coordinate-library file, if any."""

    for candidate in coord_file_candidates(game_root):
        if candidate.exists():
            return candidate
    return None


def parse_coord_groups_text(content: str) -> tuple[CoordPresetGroup, ...]:
    """Parse the chenstack-style ``Palworld.Coords.json`` payload."""

    try:
        payload = json.loads(content)
    except json.JSONDecodeError:
        return ()
    if not isinstance(payload, list):
        return ()

    groups: list[CoordPresetGroup] = []
    for raw_group in payload:
        if not isinstance(raw_group, dict):
            continue
        group_name = str(raw_group.get("name") or "未命名分类").strip() or "未命名分类"
        raw_items = raw_group.get("items")
        if not isinstance(raw_items, list):
            groups.append(CoordPresetGroup(name=group_name, items=()))
            continue

        items: list[CoordPreset] = []
        for index, raw_item in enumerate(raw_items, start=1):
            if not isinstance(raw_item, dict):
                continue
            item_name = str(raw_item.get("name") or f"坐标点 {index}").strip() or f"坐标点 {index}"
            value = raw_item.get("value")
            if not isinstance(value, list) or len(value) < 3:
                continue
            try:
                x = float(value[0])
                y = float(value[1])
                z = float(value[2])
            except (TypeError, ValueError):
                continue
            items.append(CoordPreset(group=group_name, name=item_name, x=x, y=y, z=z))
        groups.append(CoordPresetGroup(name=group_name, items=tuple(items)))

    return tuple(groups)


def load_coord_groups(game_root: Path | None) -> tuple[Path | None, tuple[CoordPresetGroup, ...]]:
    """Load the coordinate library from disk."""

    path = pick_coord_file(game_root)
    if path is None:
        return None, ()
    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return path, ()
    return path, parse_coord_groups_text(content)


def flatten_coord_groups(groups: tuple[CoordPresetGroup, ...]) -> list[CoordPreset]:
    """Flatten all non-empty groups into a single preset list."""

    return [item for group in groups for item in group.items]


def search_coord_presets(
    entries: list[CoordPreset], query: str, limit: int = 300
) -> list[CoordPreset]:
    """Search coordinate presets by name/group with stable ranking."""

    normalized = query.strip().casefold()
    if not normalized:
        return entries[:limit]

    terms = [term for term in normalized.split() if term]
    ranked: list[tuple[tuple[int, int, str, str], CoordPreset]] = []
    for entry in entries:
        group = entry.group.casefold()
        name = entry.name.casefold()
        combined = f"{group} {name}"
        if not all(term in combined for term in terms):
            continue

        if name == normalized or group == normalized:
            priority = 0
        elif name.startswith(normalized) or group.startswith(normalized):
            priority = 1
        else:
            priority = 2

        positions = [pos for pos in (name.find(normalized), group.find(normalized)) if pos >= 0]
        first_position = min(positions) if positions else 9999
        ranked.append(
            (
                (priority, first_position, entry.group.casefold(), entry.name.casefold()),
                entry,
            )
        )

    ranked.sort(key=lambda item: item[0])
    return [entry for _, entry in ranked[:limit]]
