from __future__ import annotations

import base64
import json
import os
import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from tests import _bootstrap  # noqa: F401
from palworld_trainer.game_control import (
    CHAT_HELPER_PAYLOAD_ENV,
    CHAT_HELPER_RESULT_ENV,
    SendResult,
    send_chat_command,
    run_chat_helper_from_env,
    send_chat_commands_isolated,
)


class GameControlHelperTests(unittest.TestCase):
    def test_send_chat_command_clears_chat_before_typing(self) -> None:
        events: list[str] = []

        with (
            mock.patch(
                "palworld_trainer.game_control.find_palworld_window",
                return_value=123,
            ),
            mock.patch(
                "palworld_trainer.game_control._focus_window",
                return_value=True,
            ),
            mock.patch(
                "palworld_trainer.game_control.user32.GetForegroundWindow",
                return_value=0,
            ),
            mock.patch(
                "palworld_trainer.game_control._tap_vk",
                side_effect=lambda vk, delay_ms=30: events.append(f"tap:{vk}:{delay_ms}"),
            ),
            mock.patch(
                "palworld_trainer.game_control._tap_chord",
                side_effect=lambda modifiers, vk, delay_ms=30: events.append(
                    f"chord:{modifiers}:{vk}:{delay_ms}"
                ),
            ),
            mock.patch(
                "palworld_trainer.game_control._type_unicode",
                side_effect=lambda text, delay_ms=5: events.append(f"type:{text}:{delay_ms}"),
            ),
            mock.patch("palworld_trainer.game_control.time.sleep"),
        ):
            result = send_chat_command("@!unlocktech BreedFarm", restore_focus=False)

        self.assertEqual(SendResult(True, "Sent: @!unlocktech BreedFarm", "@!unlocktech BreedFarm"), result)
        self.assertEqual(
            [
                "tap:13:30",
                "chord:[17]:65:20",
                "tap:8:20",
                "type:@!unlocktech BreedFarm:8",
                "tap:13:30",
            ],
            events,
        )

    def test_send_chat_commands_isolated_reads_helper_results(self) -> None:
        def fake_run(_command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
            env = kwargs["env"]
            assert isinstance(env, dict)
            payload = json.loads(
                base64.b64decode(env[CHAT_HELPER_PAYLOAD_ENV]).decode("utf-8")
            )
            self.assertEqual(["@!unlockft"], payload["commands"])
            result_path = Path(env[CHAT_HELPER_RESULT_ENV])
            result_path.write_text(
                json.dumps(
                    [{"ok": True, "message": "ok", "command": "@!unlockft"}],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            return subprocess.CompletedProcess([], 0)

        with mock.patch("palworld_trainer.game_control.subprocess.run", side_effect=fake_run):
            results = send_chat_commands_isolated(["@!unlockft"])

        self.assertEqual([SendResult(True, "ok", "@!unlockft")], results)

    def test_run_chat_helper_from_env_writes_result_file(self) -> None:
        payload = {
            "commands": ["@!giveme Wood 2"],
            "between_ms": 250,
            "restore_focus": False,
        }
        payload_b64 = base64.b64encode(
            json.dumps(payload, ensure_ascii=False).encode("utf-8")
        ).decode("ascii")

        with TemporaryDirectory() as tmp:
            result_path = Path(tmp) / "result.json"
            with (
                mock.patch(
                    "palworld_trainer.game_control.send_chat_commands",
                    return_value=[SendResult(True, "Sent", "@!giveme Wood 2")],
                ) as send_many,
                mock.patch.dict(
                    os.environ,
                    {
                        CHAT_HELPER_PAYLOAD_ENV: payload_b64,
                        CHAT_HELPER_RESULT_ENV: str(result_path),
                    },
                    clear=False,
                ),
            ):
                exit_code = run_chat_helper_from_env()
                written = json.loads(result_path.read_text(encoding="utf-8"))

        self.assertEqual(0, exit_code)
        send_many.assert_called_once_with(
            ["@!giveme Wood 2"],
            between_ms=250,
            restore_focus=False,
        )
        self.assertEqual(
            [{"ok": True, "message": "Sent", "command": "@!giveme Wood 2"}],
            written,
        )


if __name__ == "__main__":
    unittest.main()
