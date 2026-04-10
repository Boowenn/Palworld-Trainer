from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from tests import _bootstrap  # noqa: F401
from palworld_trainer.host_tools import (
    build_entry_command_suggestions,
    get_primary_entry_command,
    render_host_commands_text,
    render_host_search_text,
)
from palworld_trainer.models import CatalogEntry


class HostToolsTests(unittest.TestCase):
    def test_item_entry_suggestions_include_giveme_template(self) -> None:
        entry = CatalogEntry(kind="item", key="Shield_Ultra", label="Ultra Shield")

        suggestions = build_entry_command_suggestions(entry)

        self.assertIn("@!giveme Shield_Ultra 1", suggestions)
        self.assertEqual("@!giveme Shield_Ultra 1", get_primary_entry_command(entry))

    def test_npc_entry_has_no_ready_made_command_template(self) -> None:
        entry = CatalogEntry(kind="npc", key="SalesPerson", label="Wandering Merchant")

        self.assertEqual([], build_entry_command_suggestions(entry))
        self.assertIsNone(get_primary_entry_command(entry))

    def test_render_host_commands_text_mentions_key_commands(self) -> None:
        rendered = render_host_commands_text()

        self.assertIn("@!giveme <itemId> [count]", rendered)
        self.assertIn("@!unlockalltech", rendered)
        self.assertIn("NPC catalogs are exposed mainly as searchable IDs", rendered)

    def test_render_host_search_text_prints_suggestions(self) -> None:
        root = Path("D:/fake/enums")

        def fake_read_text(path: Path, encoding: str = "utf-8") -> str:
            _ = encoding
            self.assertEqual("itemdata.lua", path.name)
            return 'local items = {\n    Shield_Ultra = "Ultra Shield",\n}\n'

        with patch("pathlib.Path.exists", autospec=True, return_value=True):
            with patch("pathlib.Path.read_text", autospec=True, side_effect=fake_read_text):
                rendered = render_host_search_text(root, "item", "shield", limit=5)

        self.assertIn("Ultra Shield [Shield_Ultra]", rendered)
        self.assertIn("@!giveme Shield_Ultra 1", rendered)


if __name__ == "__main__":
    unittest.main()
