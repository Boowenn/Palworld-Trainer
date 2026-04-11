from __future__ import annotations

import json
import math
import re
from typing import Sequence

from .models import CollectibleSpec, MapBookmarkSpec, RouteSpec


LOCATION_PATTERN = re.compile(
    r"X=(?P<x>-?[0-9]+(?:\.[0-9]+)?)\s+Y=(?P<y>-?[0-9]+(?:\.[0-9]+)?)\s+Z=(?P<z>-?[0-9]+(?:\.[0-9]+)?)"
)
COLLECTIBLE_STATUSES = ("planned", "tracking", "found")


def extract_coordinates_from_location_text(location_text: str) -> tuple[float, float, float]:
    match = LOCATION_PATTERN.search(location_text.strip())
    if not match:
        raise ValueError("Location text must include X=, Y=, and Z= coordinates.")

    return (float(match.group("x")), float(match.group("y")), float(match.group("z")))


def build_map_bookmark(
    title: str,
    x: str | float,
    y: str | float,
    z: str | float,
    category: str,
    notes: str,
    *,
    key: str | None = None,
) -> MapBookmarkSpec:
    normalized_title = title.strip()
    normalized_category = category.strip() or "note"
    normalized_notes = notes.strip() or "Saved map bookmark."

    if not normalized_title:
        raise ValueError("Map bookmark title cannot be empty.")

    return MapBookmarkSpec(
        key=key or _normalize_key(normalized_title, "map_bookmark"),
        title=normalized_title,
        category=normalized_category,
        x=_parse_coordinate_component(x, "X"),
        y=_parse_coordinate_component(y, "Y"),
        z=_parse_coordinate_component(z, "Z"),
        notes=normalized_notes,
        origin="Saved",
        editable=True,
    )


def build_map_bookmark_from_location_text(
    title: str,
    location_text: str,
    category: str,
    notes: str,
    *,
    key: str | None = None,
) -> MapBookmarkSpec:
    x, y, z = extract_coordinates_from_location_text(location_text)
    return build_map_bookmark(title, x, y, z, category, notes, key=key)


def build_route_spec(
    title: str,
    bookmark_keys: Sequence[str] | str,
    description: str,
    *,
    key: str | None = None,
) -> RouteSpec:
    normalized_title = title.strip()
    normalized_description = description.strip() or "Saved route library entry."
    normalized_keys = _normalize_bookmark_keys(bookmark_keys)

    if not normalized_title:
        raise ValueError("Route title cannot be empty.")
    if not normalized_keys:
        raise ValueError("Route must include at least one bookmark key.")

    return RouteSpec(
        key=key or _normalize_key(normalized_title, "route"),
        title=normalized_title,
        bookmark_keys=normalized_keys,
        description=normalized_description,
        origin="Saved",
        editable=True,
    )


def build_collectible_spec(
    title: str,
    bookmark_key: str,
    category: str,
    status: str,
    notes: str,
    *,
    key: str | None = None,
) -> CollectibleSpec:
    normalized_title = title.strip()
    normalized_bookmark_key = bookmark_key.strip()
    normalized_category = category.strip() or "collectible"
    normalized_status = status.strip().casefold() or "planned"
    normalized_notes = notes.strip() or "Tracked collectible entry."

    if not normalized_title:
        raise ValueError("Tracked spot title cannot be empty.")
    if not normalized_bookmark_key:
        raise ValueError("Tracked spot bookmark key cannot be empty.")
    if normalized_status not in COLLECTIBLE_STATUSES:
        raise ValueError(
            f"Tracked spot status must be one of: {', '.join(COLLECTIBLE_STATUSES)}."
        )

    return CollectibleSpec(
        key=key or _normalize_key(normalized_title, "collectible"),
        title=normalized_title,
        bookmark_key=normalized_bookmark_key,
        category=normalized_category,
        status=normalized_status,
        notes=normalized_notes,
        origin="Saved",
        editable=True,
    )


def merge_map_bookmarks(
    existing: Sequence[MapBookmarkSpec],
    incoming: Sequence[MapBookmarkSpec],
) -> list[MapBookmarkSpec]:
    return _merge_keyed_specs(existing, incoming, _map_bookmark_signature)


def merge_route_specs(existing: Sequence[RouteSpec], incoming: Sequence[RouteSpec]) -> list[RouteSpec]:
    return _merge_keyed_specs(existing, incoming, _route_signature)


def merge_collectible_specs(
    existing: Sequence[CollectibleSpec],
    incoming: Sequence[CollectibleSpec],
) -> list[CollectibleSpec]:
    return _merge_keyed_specs(existing, incoming, _collectible_signature)


def export_map_library(
    bookmarks: Sequence[MapBookmarkSpec],
    routes: Sequence[RouteSpec],
    collectibles: Sequence[CollectibleSpec],
) -> str:
    payload = {
        "version": 1,
        "bookmarks": [
            {
                "key": bookmark.key,
                "title": bookmark.title,
                "category": bookmark.category,
                "x": bookmark.x,
                "y": bookmark.y,
                "z": bookmark.z,
                "notes": bookmark.notes,
                "origin": bookmark.origin,
                "editable": bookmark.editable,
            }
            for bookmark in bookmarks
        ],
        "routes": [
            {
                "key": route.key,
                "title": route.title,
                "bookmark_keys": route.bookmark_keys,
                "description": route.description,
                "origin": route.origin,
                "editable": route.editable,
            }
            for route in routes
        ],
        "collectibles": [
            {
                "key": collectible.key,
                "title": collectible.title,
                "bookmark_key": collectible.bookmark_key,
                "category": collectible.category,
                "status": collectible.status,
                "notes": collectible.notes,
                "origin": collectible.origin,
                "editable": collectible.editable,
            }
            for collectible in collectibles
        ],
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)


def import_map_library(payload: str) -> tuple[list[MapBookmarkSpec], list[RouteSpec], list[CollectibleSpec]]:
    try:
        data = json.loads(payload.lstrip("\ufeff"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid map library payload: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError("Map library import payload must be an object.")

    raw_bookmarks = data.get("bookmarks", [])
    raw_routes = data.get("routes", [])
    raw_collectibles = data.get("collectibles", [])

    if not isinstance(raw_bookmarks, list) or not isinstance(raw_routes, list) or not isinstance(raw_collectibles, list):
        raise ValueError("Map library import payload must include bookmarks, routes, and collectibles arrays.")

    bookmarks: list[MapBookmarkSpec] = []
    for index, item in enumerate(raw_bookmarks, start=1):
        if not isinstance(item, dict):
            continue
        bookmarks.append(
            build_map_bookmark(
                str(item.get("title", "")).strip() or f"Imported Bookmark {index}",
                item.get("x", 0.0),
                item.get("y", 0.0),
                item.get("z", 0.0),
                str(item.get("category", "")).strip(),
                str(item.get("notes", "")).strip(),
                key=str(item.get("key", "")).strip() or None,
            )
        )

    routes: list[RouteSpec] = []
    for index, item in enumerate(raw_routes, start=1):
        if not isinstance(item, dict):
            continue
        routes.append(
            build_route_spec(
                str(item.get("title", "")).strip() or f"Imported Route {index}",
                item.get("bookmark_keys", []),
                str(item.get("description", "")).strip(),
                key=str(item.get("key", "")).strip() or None,
            )
        )

    collectibles: list[CollectibleSpec] = []
    for index, item in enumerate(raw_collectibles, start=1):
        if not isinstance(item, dict):
            continue
        collectibles.append(
            build_collectible_spec(
                str(item.get("title", "")).strip() or f"Imported Collectible {index}",
                str(item.get("bookmark_key", "")).strip(),
                str(item.get("category", "")).strip(),
                str(item.get("status", "")).strip(),
                str(item.get("notes", "")).strip(),
                key=str(item.get("key", "")).strip() or None,
            )
        )

    return (
        merge_map_bookmarks([], bookmarks),
        merge_route_specs([], routes),
        merge_collectible_specs([], collectibles),
    )


def render_map_bookmarks_text(bookmarks: Sequence[MapBookmarkSpec]) -> str:
    lines = [
        "Map bookmarks",
        "-------------",
        "Persistent coordinate anchors that stay useful in solo play and non-host multiplayer sessions.",
        "",
    ]

    if not bookmarks:
        lines.append("No map bookmarks saved yet.")
        return "\n".join(lines)

    for bookmark in bookmarks:
        lines.extend(
            [
                f"{bookmark.key}",
                f"  Title      : {bookmark.title}",
                f"  Category   : {bookmark.category}",
                f"  Coordinates: {format_coordinates(bookmark)}",
                f"  Notes      : {bookmark.notes}",
                "",
            ]
        )

    return "\n".join(lines)


def render_route_library_text(routes: Sequence[RouteSpec], bookmarks: Sequence[MapBookmarkSpec]) -> str:
    bookmark_index = {bookmark.key: bookmark for bookmark in bookmarks}
    lines = [
        "Route library",
        "-------------",
        "Reusable waypoint loops that build on your saved map bookmarks.",
        "",
    ]

    if not routes:
        lines.append("No routes saved yet.")
        return "\n".join(lines)

    for route in routes:
        distance = calculate_route_distance(route, bookmark_index)
        missing_keys = [key for key in route.bookmark_keys if key not in bookmark_index]
        lines.extend(
            [
                f"{route.key}",
                f"  Title      : {route.title}",
                f"  Stops      : {len(route.bookmark_keys)}",
                f"  Path       : {' -> '.join(route.bookmark_keys)}",
                f"  Distance   : {distance:.1f} m",
                f"  Description: {route.description}",
                f"  Missing    : {', '.join(missing_keys) if missing_keys else 'None'}",
                "",
            ]
        )

    return "\n".join(lines)


def render_collectible_tracker_text(
    collectibles: Sequence[CollectibleSpec],
    bookmarks: Sequence[MapBookmarkSpec],
) -> str:
    bookmark_index = {bookmark.key: bookmark for bookmark in bookmarks}
    lines = [
        "Collectible tracker",
        "-------------------",
        "Track statues, eggs, alpha pals, dungeon entries, or custom scavenging goals against saved bookmarks.",
        "",
    ]

    if not collectibles:
        lines.append("No tracked collectibles saved yet.")
        return "\n".join(lines)

    for collectible in collectibles:
        bookmark = bookmark_index.get(collectible.bookmark_key)
        location_label = format_coordinates(bookmark) if bookmark else "Missing bookmark"
        lines.extend(
            [
                f"{collectible.key}",
                f"  Title      : {collectible.title}",
                f"  Category   : {collectible.category}",
                f"  Status     : {collectible.status}",
                f"  Bookmark   : {collectible.bookmark_key}",
                f"  Location   : {location_label}",
                f"  Notes      : {collectible.notes}",
                "",
            ]
        )

    return "\n".join(lines)


def render_map_tools_text(
    bookmarks: Sequence[MapBookmarkSpec],
    routes: Sequence[RouteSpec],
    collectibles: Sequence[CollectibleSpec],
) -> str:
    status_counts = {status: 0 for status in COLLECTIBLE_STATUSES}
    for collectible in collectibles:
        status_counts[collectible.status] = status_counts.get(collectible.status, 0) + 1

    total_route_distance = sum(
        calculate_route_distance(route, {bookmark.key: bookmark for bookmark in bookmarks})
        for route in routes
    )

    lines = [
        "Map tools overview",
        "------------------",
        f"Saved map bookmarks : {len(bookmarks)}",
        f"Saved routes        : {len(routes)}",
        f"Tracked collectibles: {len(collectibles)}",
        (
            "Collectible states  : "
            f"planned={status_counts.get('planned', 0)}, "
            f"tracking={status_counts.get('tracking', 0)}, "
            f"found={status_counts.get('found', 0)}"
        ),
        f"Total route distance: {total_route_distance:.1f} m",
        "",
        "Usage",
        "-----",
        "Use the latest Runtime session coordinates to seed a bookmark, then assemble reusable routes and attach tracked spots to those anchors.",
        "These workflows remain useful even in non-host multiplayer sessions, because the data lives in your local scouting library.",
    ]
    return "\n".join(lines)


def render_map_bookmark_detail_text(
    bookmark: MapBookmarkSpec,
    *,
    tracked_count: int = 0,
) -> str:
    return "\n".join(
        [
            bookmark.title,
            "-" * len(bookmark.title),
            f"Category   : {bookmark.category}",
            f"Coordinates: {format_coordinates(bookmark)}",
            f"Tracked use : {tracked_count} collectible(s)",
            f"Origin     : {bookmark.origin}",
            f"Editable   : {'Yes' if bookmark.editable else 'No'}",
            f"Notes      : {bookmark.notes}",
            "",
            "Tips",
            "----",
            "Bookmarks can be captured from the latest session location and reused by routes or tracked collectibles.",
        ]
    )


def render_route_detail_text(route: RouteSpec, bookmarks: Sequence[MapBookmarkSpec]) -> str:
    bookmark_index = {bookmark.key: bookmark for bookmark in bookmarks}
    missing_keys = [key for key in route.bookmark_keys if key not in bookmark_index]
    distance = calculate_route_distance(route, bookmark_index)
    stop_lines = [f"{index}. {key}" for index, key in enumerate(route.bookmark_keys, start=1)]
    if not stop_lines:
        stop_lines = ["No stops recorded."]

    return "\n".join(
        [
            route.title,
            "-" * len(route.title),
            f"Stops      : {len(route.bookmark_keys)}",
            f"Distance   : {distance:.1f} m",
            f"Origin     : {route.origin}",
            f"Editable   : {'Yes' if route.editable else 'No'}",
            f"Missing    : {', '.join(missing_keys) if missing_keys else 'None'}",
            f"Description: {route.description}",
            "",
            "Stops",
            "-----",
            *stop_lines,
        ]
    )


def render_collectible_detail_text(
    collectible: CollectibleSpec,
    bookmarks: Sequence[MapBookmarkSpec],
) -> str:
    bookmark_index = {bookmark.key: bookmark for bookmark in bookmarks}
    bookmark = bookmark_index.get(collectible.bookmark_key)

    return "\n".join(
        [
            collectible.title,
            "-" * len(collectible.title),
            f"Category   : {collectible.category}",
            f"Status     : {collectible.status}",
            f"Bookmark   : {collectible.bookmark_key}",
            f"Location   : {format_coordinates(bookmark) if bookmark else 'Missing bookmark'}",
            f"Origin     : {collectible.origin}",
            f"Editable   : {'Yes' if collectible.editable else 'No'}",
            f"Notes      : {collectible.notes}",
            "",
            "Tips",
            "----",
            "Mark tracked spots as found after you confirm them in-session, or keep them in tracking while you are validating a route.",
        ]
    )


def calculate_route_distance(
    route: RouteSpec,
    bookmark_index: dict[str, MapBookmarkSpec],
) -> float:
    points = [bookmark_index[key] for key in route.bookmark_keys if key in bookmark_index]
    if len(points) < 2:
        return 0.0

    total = 0.0
    for current, following in zip(points, points[1:]):
        total += math.dist((current.x, current.y, current.z), (following.x, following.y, following.z))
    return total


def format_coordinates(bookmark: MapBookmarkSpec | None) -> str:
    if not bookmark:
        return "n/a"
    return f"X={bookmark.x:.1f} Y={bookmark.y:.1f} Z={bookmark.z:.1f}"


def append_route_stop(existing: str, bookmark_key: str) -> str:
    normalized_key = bookmark_key.strip()
    existing_keys = _normalize_bookmark_keys(existing)
    if normalized_key and normalized_key not in existing_keys:
        existing_keys.append(normalized_key)
    return ", ".join(existing_keys)


def _normalize_bookmark_keys(value: Sequence[str] | str) -> list[str]:
    if isinstance(value, str):
        candidates = re.split(r"[\s,;]+", value.strip())
    else:
        candidates = list(value)
    normalized: list[str] = []
    for candidate in candidates:
        item = str(candidate).strip()
        if item and item not in normalized:
            normalized.append(item)
    return normalized


def _parse_coordinate_component(value: str | float, label: str) -> float:
    if isinstance(value, (int, float)):
        return float(value)

    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{label} coordinate cannot be empty.")

    try:
        return float(normalized)
    except ValueError as exc:
        raise ValueError(f"{label} coordinate must be numeric.") from exc


def _normalize_key(value: str, default_prefix: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", value.strip().casefold()).strip("_")
    return normalized or default_prefix


def _map_bookmark_signature(bookmark: MapBookmarkSpec) -> tuple[str, float, float, float]:
    return (bookmark.title.casefold(), bookmark.x, bookmark.y, bookmark.z)


def _route_signature(route: RouteSpec) -> tuple[str, tuple[str, ...]]:
    return (route.title.casefold(), tuple(route.bookmark_keys))


def _collectible_signature(collectible: CollectibleSpec) -> tuple[str, str]:
    return (collectible.title.casefold(), collectible.bookmark_key.casefold())


def _merge_keyed_specs(existing: Sequence[object], incoming: Sequence[object], signature_builder: object) -> list[object]:
    merged: list[object] = []
    signatures: dict[object, int] = {}

    for spec in existing:
        merged.append(spec)
        signatures[signature_builder(spec)] = len(merged) - 1

    for spec in incoming:
        signature = signature_builder(spec)
        if signature in signatures:
            merged[signatures[signature]] = spec
            continue

        key = getattr(spec, "key")
        key_conflict = next((index for index, existing_spec in enumerate(merged) if getattr(existing_spec, "key") == key), None)
        if key_conflict is not None:
            cloned = _clone_with_new_key(spec, f"{key}_{len(merged) + 1}")
            spec = cloned

        merged.append(spec)
        signatures[signature_builder(spec)] = len(merged) - 1

    return list(merged)


def _clone_with_new_key(spec: object, new_key: str) -> object:
    if isinstance(spec, MapBookmarkSpec):
        return MapBookmarkSpec(
            key=new_key,
            title=spec.title,
            category=spec.category,
            x=spec.x,
            y=spec.y,
            z=spec.z,
            notes=spec.notes,
            origin=spec.origin,
            editable=spec.editable,
        )
    if isinstance(spec, RouteSpec):
        return RouteSpec(
            key=new_key,
            title=spec.title,
            bookmark_keys=list(spec.bookmark_keys),
            description=spec.description,
            origin=spec.origin,
            editable=spec.editable,
        )
    if isinstance(spec, CollectibleSpec):
        return CollectibleSpec(
            key=new_key,
            title=spec.title,
            bookmark_key=spec.bookmark_key,
            category=spec.category,
            status=spec.status,
            notes=spec.notes,
            origin=spec.origin,
            editable=spec.editable,
        )
    raise TypeError(f"Unsupported spec type for clone: {type(spec)!r}")
