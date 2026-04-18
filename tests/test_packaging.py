from __future__ import annotations

import unittest
from pathlib import Path


class PackagingTests(unittest.TestCase):
    def test_icon_assets_exist(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        self.assertTrue((repo_root / "assets" / "palworld-trainer.ico").exists())
        self.assertTrue((repo_root / "assets" / "palworld-trainer-icon.png").exists())

    def test_spec_mentions_icon_and_integrations(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        spec_text = (repo_root / "PalworldTrainer.spec").read_text(encoding="utf-8")
        self.assertIn("palworld-trainer.ico", spec_text)
        self.assertIn("integrations", spec_text)
        self.assertIn("PalworldTrainerBridge", spec_text)


if __name__ == "__main__":
    unittest.main()
