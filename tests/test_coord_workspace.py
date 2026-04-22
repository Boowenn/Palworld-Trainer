from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests import _bootstrap  # noqa: F401
from palworld_trainer.coord_workspace import (
    CoordWorkspaceGroup,
    load_coord_workspace,
    save_coord_workspace,
    seed_groups_from_entries,
)
from palworld_trainer.reference_parity import ReferenceCoordEntry


class CoordWorkspaceTests(unittest.TestCase):
    def test_seed_groups_from_entries_groups_and_sorts(self) -> None:
        entries = [
            ReferenceCoordEntry(group="B", label="Beta", x=4, y=5, z=6),
            ReferenceCoordEntry(group="默认", label="Home", x=1, y=2, z=3),
            ReferenceCoordEntry(group="B", label="Alpha", x=7, y=8, z=9),
        ]

        groups = seed_groups_from_entries(entries)

        self.assertEqual(["默认", "B"], [group.name for group in groups])
        self.assertEqual(["Alpha", "Beta"], [item.label for item in groups[1].items])

    def test_load_and_save_coord_workspace_round_trip(self) -> None:
        entries = [ReferenceCoordEntry(group="默认", label="Home", x=1, y=2, z=3)]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "coord_workspace.json"
            with patch("palworld_trainer.coord_workspace.workspace_path", return_value=path):
                groups = load_coord_workspace(entries)
                groups.append(
                    CoordWorkspaceGroup(
                        name="Boss 直达",
                        items=[ReferenceCoordEntry(group="Boss 直达", label="Tower", x=4, y=5, z=6)],
                    )
                )
                save_coord_workspace(groups)
                loaded = load_coord_workspace(entries)

        self.assertEqual(["默认", "Boss 直达"], [group.name for group in loaded])
        self.assertEqual("Tower", loaded[1].items[0].label)
        self.assertEqual(4.0, loaded[1].items[0].x)


if __name__ == "__main__":
    unittest.main()
