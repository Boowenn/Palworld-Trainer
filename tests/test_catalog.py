from __future__ import annotations

import unittest

from tests import _bootstrap  # noqa: F401
from palworld_trainer.catalog import parse_catalog_text, search_catalog


ITEM_SAMPLE = """-- Auto-generated from Palworld Dataminer
local items = {
    Shield_Ultra = "Ultra Shield",
    Head016 = "Penking Cap",
    Head017 = "Katress Cap",
    Bow = "Bow",
}
"""


class CatalogTests(unittest.TestCase):
    def test_parse_catalog_text_reads_key_value_pairs(self) -> None:
        entries = parse_catalog_text("item", ITEM_SAMPLE)
        by_key = {entry.key: entry.label for entry in entries}

        self.assertEqual("Ultra Shield", by_key["Shield_Ultra"])
        self.assertEqual("Penking Cap", by_key["Head016"])
        self.assertEqual("Bow", by_key["Bow"])

    def test_search_catalog_prioritizes_prefix_matches(self) -> None:
        entries = parse_catalog_text("item", ITEM_SAMPLE)

        results = search_catalog(entries, "kat", limit=2)

        self.assertEqual("Katress Cap", results[0].label)

    def test_search_catalog_empty_query_returns_all_up_to_limit(self) -> None:
        entries = parse_catalog_text("item", ITEM_SAMPLE)
        results = search_catalog(entries, "", limit=10)
        self.assertEqual(4, len(results))

    def test_search_catalog_no_match_returns_empty(self) -> None:
        entries = parse_catalog_text("item", ITEM_SAMPLE)
        self.assertEqual([], search_catalog(entries, "zzzzz"))


if __name__ == "__main__":
    unittest.main()
