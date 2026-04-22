from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from tests import _bootstrap  # noqa: F401 - ensures src on sys.path

from palworld_trainer.cheats import (
    BridgeStatus,
    CheatState,
    describe_state,
    read_status,
    read_toggles,
    request_path_for,
    status_path_for,
    toggles_path_for,
    write_request,
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

    def test_status_and_request_paths_share_bridge_root(self) -> None:
        with TemporaryDirectory() as tmp:
            bridge = Path(tmp) / "PalworldTrainerBridge"
            report = EnvironmentReport(game_root=Path(tmp), trainer_bridge_target=bridge)
            status = status_path_for(report)
            request = request_path_for(report)
            self.assertIsNotNone(status)
            self.assertIsNotNone(request)
            assert status is not None
            assert request is not None
            self.assertEqual(status.parent, bridge)
            self.assertEqual(status.name, "status.json")
            self.assertEqual(request.parent, bridge)
            self.assertEqual(request.name, "request.json")

    def test_runtime_target_overrides_deployed_target(self) -> None:
        with TemporaryDirectory() as tmp:
            deployed = Path(tmp) / "deployed"
            runtime = Path(tmp) / "runtime"
            report = EnvironmentReport(
                game_root=Path(tmp),
                trainer_bridge_target=deployed,
                trainer_bridge_runtime_target=runtime,
            )
            toggles = toggles_path_for(report)
            status = status_path_for(report)
            request = request_path_for(report)
            self.assertEqual(toggles, runtime / "toggles.json")
            self.assertEqual(status, runtime / "status.json")
            self.assertEqual(request, runtime / "request.json")


class BridgeStatusTests(unittest.TestCase):
    def test_read_status_missing_file_returns_default(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "missing-status.json"
            status = read_status(path)
            self.assertEqual(status, BridgeStatus())

    def test_read_status_parses_position(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "status.json"
            path.write_text(
                json.dumps(
                    {
                        "player_valid": True,
                        "controller_valid": True,
                        "bridge_version": "1.2.0",
                        "hidden_registry_ready": True,
                        "hidden_dispatch_ready": False,
                        "chat_suppression_ready": True,
                        "position_x": -123.5,
                        "position_y": 456.0,
                        "position_z": 789.25,
                    }
                ),
                encoding="utf-8",
            )
            status = read_status(path)
            self.assertTrue(status.player_valid)
            self.assertTrue(status.controller_valid)
            self.assertEqual(status.bridge_version, "1.2.0")
            self.assertTrue(status.hidden_registry_ready)
            self.assertFalse(status.hidden_dispatch_ready)
            self.assertTrue(status.chat_suppression_ready)
            self.assertAlmostEqual(status.position_x, -123.5)
            self.assertAlmostEqual(status.position_y, 456.0)
            self.assertAlmostEqual(status.position_z, 789.25)

    def test_read_status_parses_nearby_players(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "status.json"
            path.write_text(
                json.dumps(
                    {
                        "player_valid": True,
                        "nearby_players": [
                            {
                                "name": "BP_PlayerPawn_C_214",
                                "class_name": "BP_PlayerPawn_C",
                                "location": "X=-10.0 Y=20.0 Z=30.0",
                                "distance_meters": 42.5,
                                "world_x": -10.0,
                                "world_y": 20.0,
                                "world_z": 30.0,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            status = read_status(path)

        self.assertEqual(1, len(status.nearby_players))
        self.assertEqual("BP_PlayerPawn_C_214", status.nearby_players[0].name)
        self.assertEqual("BP_PlayerPawn_C", status.nearby_players[0].class_name)
        self.assertEqual("X=-10.0 Y=20.0 Z=30.0", status.nearby_players[0].location)
        self.assertAlmostEqual(42.5, status.nearby_players[0].distance_meters)
        self.assertAlmostEqual(-10.0, status.nearby_players[0].world_x)
        self.assertAlmostEqual(20.0, status.nearby_players[0].world_y)
        self.assertAlmostEqual(30.0, status.nearby_players[0].world_z)

    def test_read_status_parses_camera_and_runtime_state(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "status.json"
            path.write_text(
                json.dumps(
                    {
                        "player_valid": True,
                        "camera_valid": True,
                        "camera_x": 1.0,
                        "camera_y": 2.0,
                        "camera_z": 3.0,
                        "camera_pitch": 4.0,
                        "camera_yaw": 5.0,
                        "camera_roll": 6.0,
                        "camera_fov": 75.0,
                        "runtime_godmode": True,
                        "runtime_inf_stamina": True,
                        "runtime_weight_zero": False,
                        "runtime_inf_ammo": True,
                        "runtime_no_durability": False,
                        "runtime_speed_multiplier": 1.7,
                        "runtime_jump_multiplier": 1.3,
                    }
                ),
                encoding="utf-8",
            )

            status = read_status(path)

        self.assertTrue(status.camera_valid)
        self.assertAlmostEqual(1.0, status.camera_x)
        self.assertAlmostEqual(2.0, status.camera_y)
        self.assertAlmostEqual(3.0, status.camera_z)
        self.assertAlmostEqual(4.0, status.camera_pitch)
        self.assertAlmostEqual(5.0, status.camera_yaw)
        self.assertAlmostEqual(6.0, status.camera_roll)
        self.assertAlmostEqual(75.0, status.camera_fov)
        self.assertTrue(status.runtime_godmode)
        self.assertTrue(status.runtime_inf_stamina)
        self.assertFalse(status.runtime_weight_zero)
        self.assertTrue(status.runtime_inf_ammo)
        self.assertFalse(status.runtime_no_durability)
        runtime_state = status.runtime_cheat_state()
        self.assertTrue(runtime_state.godmode)
        self.assertTrue(runtime_state.inf_stamina)
        self.assertAlmostEqual(1.7, runtime_state.speed_multiplier)
        self.assertAlmostEqual(1.3, runtime_state.jump_multiplier)

    def test_read_status_retries_transient_empty_read(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "status.json"
            path.write_text("{}", encoding="utf-8")
            with mock.patch(
                "pathlib.Path.read_text",
                autospec=True,
                side_effect=[
                    "",
                    json.dumps(
                        {
                            "player_valid": True,
                            "bridge_version": "1.2.7",
                            "hidden_registry_ready": True,
                            "hidden_dispatch_ready": False,
                        }
                    ),
                ],
            ):
                status = read_status(path)

        self.assertTrue(status.player_valid)
        self.assertEqual(status.bridge_version, "1.2.7")
        self.assertTrue(status.hidden_registry_ready)
        self.assertFalse(status.hidden_dispatch_ready)


class WriteRequestTests(unittest.TestCase):
    def test_write_request_creates_request_file(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "bridge" / "request.json"
            ok, message = write_request(
                path,
                action="teleport",
                request_id=42,
                x=-100.5,
                y=200.25,
                z=300.75,
            )
            self.assertTrue(ok, message)
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(payload["action"], "teleport")
            self.assertEqual(payload["request_id"], 42)
            self.assertAlmostEqual(payload["x"], -100.5)
            self.assertAlmostEqual(payload["y"], 200.25)
            self.assertAlmostEqual(payload["z"], 300.75)

    def test_write_request_keeps_extra_bool_fields(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "bridge" / "request.json"
            ok, message = write_request(
                path,
                action="set_fly",
                request_id=43,
                enabled=True,
            )
            self.assertTrue(ok, message)
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(payload["action"], "set_fly")
            self.assertEqual(payload["request_id"], 43)
            self.assertIs(payload["enabled"], True)

    def test_write_request_keeps_extra_string_fields(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "bridge" / "request.json"
            ok, message = write_request(
                path,
                action="run_hidden_commands",
                request_id=44,
                commands_text="@!giveme Wood 2\n@!settime 6",
            )
            self.assertTrue(ok, message)
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(payload["action"], "run_hidden_commands")
            self.assertEqual(payload["request_id"], 44)
            self.assertEqual(payload["commands_text"], "@!giveme Wood 2\n@!settime 6")


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
