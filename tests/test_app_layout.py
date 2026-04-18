from __future__ import annotations

import unittest
import tkinter as tk

from tests import _bootstrap  # noqa: F401
from palworld_trainer.app import TAB_NAMES, TrainerApp


class AppLayoutTests(unittest.TestCase):
    def test_main_tabs_expose_full_click_driven_flow(self) -> None:
        root = tk.Tk()
        root.withdraw()
        try:
            app = TrainerApp(root, "test")
            self.assertEqual(
                TAB_NAMES,
                (
                    "common",
                    "character",
                    "items",
                    "pals",
                    "tech",
                    "world",
                    "coords",
                    "enhance",
                    "chat",
                    "settings",
                ),
            )
            self.assertEqual(len(app.notebook.tabs()), len(TAB_NAMES))

            self.assertTrue(hasattr(app, "item_favorite_box"))
            self.assertTrue(hasattr(app, "pal_favorite_box"))
            self.assertTrue(hasattr(app, "coord_favorite_box"))
            self.assertTrue(hasattr(app, "tech_listbox"))
            self.assertTrue(hasattr(app, "world_time_label"))
            self.assertTrue(hasattr(app, "mem_status_label"))
            self.assertTrue(hasattr(app, "chat_history_listbox"))
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()
