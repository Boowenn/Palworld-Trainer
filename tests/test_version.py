from __future__ import annotations

import tomllib
import unittest
from pathlib import Path

from tests import _bootstrap  # noqa: F401
from palworld_trainer import __version__


class VersionTests(unittest.TestCase):
    def test_package_version_matches_pyproject(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        pyproject = repo_root / "pyproject.toml"

        with pyproject.open("rb") as handle:
            data = tomllib.load(handle)

        self.assertEqual(__version__, data["project"]["version"])


if __name__ == "__main__":
    unittest.main()
