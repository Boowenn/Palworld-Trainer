from __future__ import annotations

import unittest
import tkinter as tk

from tests import _bootstrap  # noqa: F401
from palworld_trainer.app import TrainerApp


class AppLayoutTests(unittest.TestCase):
    def test_main_tabs_match_simplified_flow(self) -> None:
        root = tk.Tk()
        root.withdraw()
        try:
            app = TrainerApp(root, "test")
            tab_labels = [app.notebook.tab(tab_id, "text") for tab_id in app.notebook.tabs()]
            self.assertEqual(
                tab_labels,
                ["常用", "角色", "物品", "帕鲁", "坐标", "设置"],
            )
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()
