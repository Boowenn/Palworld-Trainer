from __future__ import annotations

import unittest

from tests import _bootstrap  # noqa: F401
from palworld_trainer.map_tools import (
    append_route_stop,
    build_collectible_spec,
    build_map_bookmark,
    build_map_bookmark_from_location_text,
    build_route_spec,
    calculate_route_distance,
    export_map_library,
    import_map_library,
    merge_collectible_specs,
    merge_map_bookmarks,
    merge_route_specs,
    render_collectible_tracker_text,
    render_map_bookmarks_text,
    render_map_tools_text,
    render_route_library_text,
)


class MapToolsTests(unittest.TestCase):
    def test_build_map_bookmark_from_location_text_extracts_coordinates(self) -> None:
        bookmark = build_map_bookmark_from_location_text(
            "Alpha Dune",
            "Player location: X=1200.5 Y=-88.0 Z=45.25",
            "boss",
            "Alpha spawn ridge.",
        )

        self.assertEqual("Alpha Dune", bookmark.title)
        self.assertAlmostEqual(1200.5, bookmark.x)
        self.assertAlmostEqual(-88.0, bookmark.y)
        self.assertAlmostEqual(45.25, bookmark.z)

    def test_map_library_can_be_exported_and_imported(self) -> None:
        bookmarks = [
            build_map_bookmark("Ore Ridge", "100", "200", "300", "resource", "Ore loop anchor."),
            build_map_bookmark("Statue Pass", "150", "250", "325", "lifmunk", "Statue checkpoint."),
        ]
        routes = [build_route_spec("Ore Loop", ["ore_ridge", "statue_pass"], "Short mining run.")]
        collectibles = [build_collectible_spec("Pass Statue", "statue_pass", "lifmunk", "tracking", "Check at dusk.")]

        payload = export_map_library(bookmarks, routes, collectibles)
        imported_bookmarks, imported_routes, imported_collectibles = import_map_library(payload)

        self.assertEqual(2, len(imported_bookmarks))
        self.assertEqual(1, len(imported_routes))
        self.assertEqual(1, len(imported_collectibles))
        self.assertIn('"routes"', payload)
        self.assertEqual("Pass Statue", imported_collectibles[0].title)

    def test_merge_helpers_replace_matching_entries(self) -> None:
        existing_bookmarks = [build_map_bookmark("Ore Ridge", "100", "200", "300", "resource", "Old note.")]
        incoming_bookmarks = [build_map_bookmark("Ore Ridge", "100", "200", "300", "resource", "New note.")]

        merged_bookmarks = merge_map_bookmarks(existing_bookmarks, incoming_bookmarks)
        self.assertEqual(1, len(merged_bookmarks))
        self.assertEqual("New note.", merged_bookmarks[0].notes)

        existing_routes = [build_route_spec("Ore Loop", ["ore_ridge"], "Old route.")]
        incoming_routes = [build_route_spec("Ore Loop", ["ore_ridge"], "Updated route.")]
        merged_routes = merge_route_specs(existing_routes, incoming_routes)
        self.assertEqual(1, len(merged_routes))
        self.assertEqual("Updated route.", merged_routes[0].description)

        existing_collectibles = [
            build_collectible_spec("Pass Statue", "ore_ridge", "lifmunk", "planned", "Old tracker.")
        ]
        incoming_collectibles = [
            build_collectible_spec("Pass Statue", "ore_ridge", "lifmunk", "found", "Updated tracker.")
        ]
        merged_collectibles = merge_collectible_specs(existing_collectibles, incoming_collectibles)
        self.assertEqual(1, len(merged_collectibles))
        self.assertEqual("found", merged_collectibles[0].status)

    def test_route_distance_uses_bookmark_coordinates(self) -> None:
        ore = build_map_bookmark("Ore Ridge", "0", "0", "0", "resource", "Start")
        statue = build_map_bookmark("Statue Pass", "3", "4", "0", "lifmunk", "Checkpoint")
        route = build_route_spec("Ore Loop", [ore.key, statue.key], "Test route.")

        distance = calculate_route_distance(route, {ore.key: ore, statue.key: statue})

        self.assertAlmostEqual(5.0, distance)

    def test_renderers_surface_non_host_scouting_language(self) -> None:
        bookmarks = [build_map_bookmark("Ore Ridge", "100", "200", "300", "resource", "Ore loop anchor.")]
        routes = [build_route_spec("Ore Loop", [bookmarks[0].key], "Solo scouting.")]
        collectibles = [build_collectible_spec("Pass Statue", bookmarks[0].key, "lifmunk", "planned", "Check soon.")]

        bookmarks_text = render_map_bookmarks_text(bookmarks)
        routes_text = render_route_library_text(routes, bookmarks)
        collectibles_text = render_collectible_tracker_text(collectibles, bookmarks)
        overview_text = render_map_tools_text(bookmarks, routes, collectibles)

        self.assertIn("Map bookmarks", bookmarks_text)
        self.assertIn("Route library", routes_text)
        self.assertIn("Collectible tracker", collectibles_text)
        self.assertIn("non-host multiplayer", overview_text)

    def test_append_route_stop_deduplicates_bookmark_keys(self) -> None:
        updated = append_route_stop("ore_ridge, statue_pass", "ore_ridge")
        appended = append_route_stop(updated, "dune_pass")

        self.assertEqual("ore_ridge, statue_pass, dune_pass", appended)


if __name__ == "__main__":
    unittest.main()
