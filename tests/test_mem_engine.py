"""Tests for the pure-Python parts of :mod:`palworld_trainer.mem_engine`.

Anything here avoids attaching to a live process — it covers the
dataclasses, calibration persistence, and the slot-wise state helpers.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from tests import _bootstrap  # noqa: F401

from palworld_trainer.mem_engine import (
    DEFAULT_FREEZE,
    SLOTS,
    Calibration,
    MemCheatState,
    calibration_path,
    load_calibration,
    save_calibration,
)


class MemCheatStateTests(unittest.TestCase):
    def test_defaults_match_defaults_table(self) -> None:
        state = MemCheatState()
        for slot in SLOTS:
            self.assertFalse(state.is_slot_enabled(slot))
            self.assertAlmostEqual(state.target_for(slot), DEFAULT_FREEZE[slot])

    def test_set_slot_and_target(self) -> None:
        state = MemCheatState()
        state.set_slot("hp", True)
        state.set_target("hp", 5000.0)
        self.assertTrue(state.is_slot_enabled("hp"))
        self.assertAlmostEqual(state.target_for("hp"), 5000.0)
        # Unrelated slots untouched
        self.assertFalse(state.is_slot_enabled("sp"))


class CalibrationTests(unittest.TestCase):
    def test_default_not_locked(self) -> None:
        cal = Calibration()
        for slot in SLOTS:
            self.assertFalse(cal.is_locked(slot))
            self.assertEqual(cal.address_for(slot), 0)

    def test_set_and_query(self) -> None:
        cal = Calibration()
        cal.set_address("walk_speed", 0xDEADBEEF)
        self.assertTrue(cal.is_locked("walk_speed"))
        self.assertEqual(cal.address_for("walk_speed"), 0xDEADBEEF)
        self.assertFalse(cal.is_locked("hp"))


class CalibrationRoundTripTests(unittest.TestCase):
    def test_save_and_load(self) -> None:
        with TemporaryDirectory() as tmp:
            path = calibration_path(Path(tmp))
            cal = Calibration(hp_addr=0x1000, sp_addr=0x2000)
            save_calibration(path, cal)
            self.assertTrue(path.exists())

            loaded = load_calibration(path)
            self.assertEqual(loaded.hp_addr, 0x1000)
            self.assertEqual(loaded.sp_addr, 0x2000)
            # Missing slots default to 0
            self.assertEqual(loaded.walk_speed_addr, 0)

    def test_load_missing_file_returns_default(self) -> None:
        with TemporaryDirectory() as tmp:
            missing = Path(tmp) / "nope.json"
            cal = load_calibration(missing)
            self.assertEqual(cal, Calibration())

    def test_load_bad_json_returns_default(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "cal.json"
            path.write_text("{not-json", encoding="utf-8")
            cal = load_calibration(path)
            self.assertEqual(cal, Calibration())

    def test_load_non_dict_returns_default(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "cal.json"
            path.write_text(json.dumps(["not", "a", "dict"]), encoding="utf-8")
            cal = load_calibration(path)
            self.assertEqual(cal, Calibration())

    def test_save_creates_parent_dirs(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "a" / "b" / "cal.json"
            save_calibration(path, Calibration(hp_addr=0x55))
            self.assertTrue(path.exists())
            self.assertEqual(load_calibration(path).hp_addr, 0x55)


if __name__ == "__main__":
    unittest.main()
