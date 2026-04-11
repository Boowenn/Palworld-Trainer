from __future__ import annotations

import unittest

from tests import _bootstrap  # noqa: F401
from palworld_trainer.app import main, parse_args


class AppCliTests(unittest.TestCase):
    def test_parse_args_accepts_smoke_test_flag(self) -> None:
        args = parse_args(["--smoke-test"])

        self.assertTrue(args.smoke_test)

    def test_main_returns_zero_for_smoke_test(self) -> None:
        self.assertEqual(0, main(["--smoke-test"]))

    def test_parse_args_accepts_map_tools_flags(self) -> None:
        args = parse_args(["--list-map-bookmarks", "--list-routes", "--list-collectibles"])

        self.assertTrue(args.list_map_bookmarks)
        self.assertTrue(args.list_routes)
        self.assertTrue(args.list_collectibles)


if __name__ == "__main__":
    unittest.main()
