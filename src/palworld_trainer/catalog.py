"""Item/Pal/Technology/NPC catalog loader.

Catalog data is parsed from the ``*.lua`` enum files shipped by the
ClientCheatCommands mod. The trainer bundles a snapshot of those files under
``palworld_trainer/data/enums`` so the GUI lists work even before the mod is
installed into the game directory.

If the user *does* have ClientCheatCommands installed, the live files under
``Mods/NativeMods/UE4SS/Mods/ClientCheatCommands/Scripts/enums`` are loaded
instead so new game updates are picked up without rebuilding the trainer.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CatalogEntry:
    kind: str
    key: str
    label: str


CATALOG_FILE_NAMES: dict[str, str] = {
    "item": "itemdata.lua",
    "pal": "paldata.lua",
    "technology": "technologydata.lua",
    "npc": "npcdata.lua",
}

CATALOG_TITLES: dict[str, str] = {
    "item": "物品",
    "pal": "帕鲁",
    "technology": "科技",
    "npc": "NPC",
}

ENTRY_PATTERN = re.compile(r'^\s*([A-Za-z0-9_]+)\s*=\s*"([^"]+)",?\s*$')

PAL_VARIANT_PREFIXES: tuple[str, ...] = (
    "boss_",
    "gym_",
    "predator_",
    "quest_",
    "raid_",
)


def get_catalog_kinds() -> list[str]:
    return list(CATALOG_FILE_NAMES)


def get_catalog_title(kind: str) -> str:
    return CATALOG_TITLES[kind]


def get_bundled_enum_dir() -> Path:
    """Return the catalog directory bundled with the app.

    Works both when running from source and from a PyInstaller one-file exe.
    """

    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
        return base / "palworld_trainer" / "data" / "enums"
    return Path(__file__).resolve().parent / "data" / "enums"


def pick_enum_dir(game_enum_dir: Path | None) -> Path:
    """Prefer the game's live enum directory when available; fall back to bundled."""

    if game_enum_dir and game_enum_dir.exists():
        return game_enum_dir
    return get_bundled_enum_dir()


def parse_catalog_text(kind: str, content: str) -> list[CatalogEntry]:
    entries: list[CatalogEntry] = []
    for line in content.splitlines():
        match = ENTRY_PATTERN.match(line)
        if not match:
            continue
        key, label = match.groups()
        entries.append(CatalogEntry(kind=kind, key=key, label=label))

    entries.sort(key=lambda entry: (entry.label.casefold(), entry.key.casefold()))
    return entries


def load_catalog(enum_dir: Path, kind: str) -> list[CatalogEntry]:
    path = enum_dir / CATALOG_FILE_NAMES[kind]
    if not path.exists():
        return []
    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return []
    return parse_catalog_text(kind, content)


def load_all_catalogs(enum_dir: Path) -> dict[str, list[CatalogEntry]]:
    return {kind: load_catalog(enum_dir, kind) for kind in get_catalog_kinds()}


def _variant_penalty(entry: CatalogEntry) -> int:
    """Prefer the plain catalog key over quest/boss/raid variants."""

    if entry.kind != "pal":
        return 0

    key = entry.key.casefold()
    return 1 if key.startswith(PAL_VARIANT_PREFIXES) else 0


def search_catalog(entries: list[CatalogEntry], query: str, limit: int = 200) -> list[CatalogEntry]:
    normalized = query.strip().casefold()
    if not normalized:
        return entries[:limit]

    terms = [term for term in normalized.split() if term]
    ranked: list[tuple[tuple[int, int, str, str], CatalogEntry]] = []

    for entry in entries:
        key = entry.key.casefold()
        label = entry.label.casefold()
        combined = f"{key} {label}"

        if not all(term in combined for term in terms):
            continue

        if key == normalized or label == normalized:
            priority = 0
        elif key.startswith(normalized) or label.startswith(normalized):
            priority = 1
        elif normalized in key or normalized in label:
            priority = 2
        else:
            priority = 3

        positions = [
            position
            for position in (key.find(normalized), label.find(normalized))
            if position >= 0
        ]
        first_position = min(positions) if positions else 9999

        ranked.append(
            (
                (
                    priority,
                    first_position,
                    _variant_penalty(entry),
                    entry.label.casefold(),
                    entry.key.casefold(),
                ),
                entry,
            )
        )

    ranked.sort(key=lambda item: item[0])
    return [entry for _, entry in ranked[:limit]]
