from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from tests import _bootstrap  # noqa: F401 - ensures src on sys.path

from palworld_trainer.cheats import (
    CheatState,
    describe_state,
    read_toggles,
    toggles_path_for,
    write_toggles,
)
from palworld_trainer.environment import EnvironmentReport


class CheatStateRoundTripTests(unittest.TestCase):
    def test_defaults(self) -> None:
        state = CheatState()
        self.assertFalse(state.godmode)
        self.assertFalse(state.inf_stamina)
        self.assertFalse(state.weight_zero)
        self.assertFalse(state.inf_ammo)
        self.assertFalse(state.no_durability)
        self.assertEqual(state.speed_multiplier, 1.0)
        self.assertEqual(state.jump_multiplier, 1.0)

    def test_json_schema_flat_and_parseable(self) -> None:
        state = CheatState(
            godmode=True,
            inf_stamina=True,
            weight_zero=False,
            inf_ammo=False,
            no_durability=True,
            speed_multiplier=2.5,
            jump_multiplier=3.0,
        )
        text = state.to_json()
        payload = json.loads(text)
        self.assertTrue(payload["godmode"])
        self.assertTrue(payload["inf_stamina"])
        self.assertFalse(payload["weight_zero"])
        self.assertAlmostEqual(payload["speed_multiplier"], 2.5)
        self.assertAlmostEqual(payload["jump_multiplier"], 3.0)

        # The Lua bridge uses naive pattern matching, so the schema must
        # stay flat with only primitives. No nested dicts / arrays allowed.
        for value in payload.values():
            self.assertIsInstance(value, (bool, int, float))

    def test_from_payload_ignores_unknown_and_coerces(self) -> None:
        payload = {
            "godmode": 1,
            "inf_stamina": "nope",
            "speed_multiplier": "4.5",
            "bogus_field": "ignored",
        }
        state = CheatState.from_payload(payload)
        self.assertTrue(state.godmode)
        # "nope" is truthy for bool() so this will be True — documenting behavior.
        self.assertTrue(state.inf_stamina)
        self.assertEqual(state.speed_multiplier, 4.5)
        self.assertFalse(hasattr(state, "bogus_field"))


class WriteReadTogglesTests(unittest.TestCase):
    def test_write_then_read_restores_state(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "bridge" / "toggles.json"
            original = CheatState(godmode=True, speed_multiplier=1.75)
            ok, message = write_toggles(path, original)
            self.assertTrue(ok, message)
            self.assertTrue(path.exists())

            restored = read_toggles(path)
            self.assertTrue(restored.godmode)
            self.assertAlmostEqual(restored.speed_multiplier, 1.75)

    def test_read_missing_file_returns_default(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "does_not_exist.json"
            state = read_toggles(path)
            self.assertEqual(state, CheatState())

    def test_read_corrupt_file_returns_default(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "corrupt.json"
            path.write_text("{not json", encoding="utf-8")
            state = read_toggles(path)
            self.assertEqual(state, CheatState())

    def test_write_creates_parent_dirs(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "a" / "b" / "c" / "toggles.json"
            ok, _ = write_toggles(path, CheatState(godmode=True))
            self.assertTrue(ok)
            self.assertTrue(path.exists())


class TogglesPathForTests(unittest.TestCase):
    def test_none_when_bridge_target_missing(self) -> None:
        report = EnvironmentReport(game_root=None)
        self.assertIsNone(toggles_path_for(report))

    def test_appends_toggles_filename(self) -> None:
        with TemporaryDirectory() as tmp:
            bridge = Path(tmp) / "PalworldTrainerBridge"
            report = EnvironmentReport(game_root=Path(tmp), trainer_bridge_target=bridge)
            result = toggles_path_for(report)
            self.assertIsNotNone(result)
            assert result is not None  # for type checker
            self.assertEqual(result.parent, bridge)
            self.assertEqual(result.name, "toggles.json")


class DescribeStateTests(unittest.TestCase):
    def test_empty_state(self) -> None:
        self.assertIn("未启用", describe_state(CheatState()))

    def test_flags_appear_in_description(self) -> None:
        state = CheatState(godmode=True, inf_stamina=True, speed_multiplier=2.0)
        text = describe_state(state)
        self.assertIn("无敌", text)
        self.assertIn("无限体力", text)
        self.assertIn("移速×2.0", text)


if __name__ == "__main__":
    unittest.main()
