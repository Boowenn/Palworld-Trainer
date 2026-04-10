from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from tests import _bootstrap  # noqa: F401
from palworld_trainer.catalog import load_all_catalogs, parse_catalog_text, search_catalog


ITEM_SAMPLE = """-- Auto-generated from Palworld Dataminer
local items = {
    Shield_Ultra = "Ultra Shield",
    Head016 = "Penking Cap",
    Head017 = "Katress Cap",
}
"""


class CatalogTests(unittest.TestCase):
    def test_parse_catalog_text_reads_key_value_pairs(self) -> None:
        entries = parse_catalog_text("item", ITEM_SAMPLE)
        by_key = {entry.key: entry.label for entry in entries}

        self.assertEqual("Ultra Shield", by_key["Shield_Ultra"])
        self.assertEqual("Penking Cap", by_key["Head016"])

    def test_search_catalog_prioritizes_prefix_matches(self) -> None:
        entries = parse_catalog_text("item", ITEM_SAMPLE)

        results = search_catalog(entries, "kat", limit=2)

        self.assertEqual("Katress Cap", results[0].label)

    def test_load_all_catalogs_reads_every_supported_kind(self) -> None:
        root = Path("D:/fake/enums")
        files = {
            "itemdata.lua": ITEM_SAMPLE,
            "paldata.lua": 'local pals = {\n    Anubis = "Anubis",\n}\n',
            "technologydata.lua": 'local technology = {\n    GlobalPalStorage = "Global Palbox",\n}\n',
            "npcdata.lua": 'local npcs = {\n    SalesPerson = "Wandering Merchant",\n}\n',
        }

        def fake_read_text(path: Path, encoding: str = "utf-8") -> str:
            _ = encoding
            return files[path.name]

        with patch("pathlib.Path.read_text", autospec=True, side_effect=fake_read_text):
            catalogs = load_all_catalogs(root)

        self.assertEqual(["item", "npc", "pal", "technology"], sorted(catalogs))
        self.assertEqual("Anubis", catalogs["pal"][0].label)


if __name__ == "__main__":
    unittest.main()
