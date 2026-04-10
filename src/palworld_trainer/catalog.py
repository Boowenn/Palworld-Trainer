from __future__ import annotations

import re
from pathlib import Path

from .models import CatalogEntry


CATALOG_FILE_NAMES: dict[str, str] = {
    "item": "itemdata.lua",
    "pal": "paldata.lua",
    "technology": "technologydata.lua",
    "npc": "npcdata.lua",
}

CATALOG_TITLES: dict[str, str] = {
    "item": "Items",
    "pal": "Pals",
    "technology": "Technology",
    "npc": "NPCs",
}

ENTRY_PATTERN = re.compile(r'^\s*([A-Za-z0-9_]+)\s*=\s*"([^"]+)",?\s*$')


def get_catalog_kinds() -> list[str]:
    return list(CATALOG_FILE_NAMES)


def normalize_catalog_kind(kind: str) -> str:
    normalized = kind.strip().lower()
    if normalized not in CATALOG_FILE_NAMES:
        supported = ", ".join(get_catalog_kinds())
        raise ValueError(f"Unsupported catalog kind '{kind}'. Supported kinds: {supported}")
    return normalized


def get_catalog_title(kind: str) -> str:
    return CATALOG_TITLES[normalize_catalog_kind(kind)]


def get_catalog_file_path(enum_dir: Path, kind: str) -> Path:
    normalized = normalize_catalog_kind(kind)
    return enum_dir / CATALOG_FILE_NAMES[normalized]


def parse_catalog_text(kind: str, content: str) -> list[CatalogEntry]:
    normalized = normalize_catalog_kind(kind)
    entries: list[CatalogEntry] = []

    for line in content.splitlines():
        match = ENTRY_PATTERN.match(line)
        if not match:
            continue

        key, label = match.groups()
        entries.append(CatalogEntry(kind=normalized, key=key, label=label))

    entries.sort(key=lambda entry: (entry.label.casefold(), entry.key.casefold()))
    return entries


def load_catalog(enum_dir: Path, kind: str) -> list[CatalogEntry]:
    path = get_catalog_file_path(enum_dir, kind)
    content = path.read_text(encoding="utf-8")
    return parse_catalog_text(kind, content)


def load_all_catalogs(enum_dir: Path) -> dict[str, list[CatalogEntry]]:
    return {kind: load_catalog(enum_dir, kind) for kind in get_catalog_kinds()}


def search_catalog(entries: list[CatalogEntry], query: str, limit: int = 50) -> list[CatalogEntry]:
    normalized_query = query.strip().casefold()
    safe_limit = max(limit, 1)

    if not normalized_query:
        return entries[:safe_limit]

    terms = [term for term in normalized_query.split() if term]
    ranked: list[tuple[tuple[int, int, str, str], CatalogEntry]] = []

    for entry in entries:
        key = entry.key.casefold()
        label = entry.label.casefold()
        combined = f"{key} {label}"

        if not all(term in combined for term in terms):
            continue

        exact_match = key == normalized_query or label == normalized_query
        starts_with = key.startswith(normalized_query) or label.startswith(normalized_query)
        contains_whole_query = normalized_query in key or normalized_query in label

        if exact_match:
            priority = 0
        elif starts_with:
            priority = 1
        elif contains_whole_query:
            priority = 2
        else:
            priority = 3

        positions = [position for position in (key.find(normalized_query), label.find(normalized_query)) if position >= 0]
        first_position = min(positions) if positions else 9999

        ranked.append(
            (
                (
                    priority,
                    first_position,
                    entry.label.casefold(),
                    entry.key.casefold(),
                ),
                entry,
            )
        )

    ranked.sort(key=lambda item: item[0])
    return [entry for _, entry in ranked[:safe_limit]]
