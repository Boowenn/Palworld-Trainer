from __future__ import annotations

import time
import tkinter as tk
import unittest
from unittest import mock

from tests import _bootstrap  # noqa: F401
from palworld_trainer import commands as cmd
from palworld_trainer.app import TAB_NAMES, TrainerApp
from palworld_trainer.cheats import BridgeStatus


class AppLayoutTests(unittest.TestCase):
    def test_main_tabs_follow_reference_style_flow(self) -> None:
        root = tk.Tk()
        root.withdraw()
        try:
            app = TrainerApp(root, "test")
            self.assertEqual(
                TAB_NAMES,
                (
                    "about",
                    "common",
                    "build",
                    "character",
                    "pal_edit",
                    "online_pal",
                    "items",
                    "pals",
                    "coords",
                    "online",
                    "changelog",
                ),
            )
            self.assertEqual(len(app.notebook.tabs()), len(TAB_NAMES))
            self.assertEqual(
                [app.notebook.tab(tab_id, "text") for tab_id in app.notebook.tabs()],
                [
                    "关于",
                    "常用功能",
                    "制作和建造",
                    "角色属性",
                    "帕鲁修改",
                    "*联机帕鲁修改",
                    "*添加物品",
                    "*添加帕鲁",
                    "传送和移速",
                    "联机功能",
                    "更新记录",
                ],
            )

            self.assertTrue(hasattr(app, "item_favorite_box"))
            self.assertTrue(hasattr(app, "pal_favorite_box"))
            self.assertTrue(hasattr(app, "coord_favorite_box"))
            self.assertTrue(hasattr(app, "tech_listbox"))
            self.assertTrue(hasattr(app, "env_text"))
            self.assertTrue(hasattr(app, "changelog_text"))
        finally:
            root.destroy()

    def test_fly_prefers_bridge_request_when_runtime_ready(self) -> None:
        root = tk.Tk()
        root.withdraw()
        try:
            app = TrainerApp(root, "test")
            with (
                mock.patch.object(app, "_bridge_runtime_ready", return_value=True),
                mock.patch.object(
                    app,
                    "_write_bridge_fly_request",
                    return_value=(True, "ok"),
                ) as write_req,
                mock.patch.object(app, "_send_with_label") as send_cmd,
            ):
                app._on_mem_fly(True)

            write_req.assert_called_once_with(True)
            send_cmd.assert_not_called()
        finally:
            root.destroy()

    def test_fly_requires_bridge_instead_of_visible_chat_fallback(self) -> None:
        root = tk.Tk()
        root.withdraw()
        try:
            app = TrainerApp(root, "test")
            with (
                mock.patch.object(app, "_bridge_runtime_ready", return_value=False),
                mock.patch.object(app, "_send_with_label") as send_cmd,
                mock.patch.object(app, "_show_result") as show_result,
            ):
                app._on_mem_fly(True)

            send_cmd.assert_not_called()
            show_result.assert_called_once()
            self.assertIn("不会再自动往游戏聊天框输入命令", show_result.call_args.args[0])
        finally:
            root.destroy()

    def test_bridge_request_ids_seed_from_time(self) -> None:
        root = tk.Tk()
        root.withdraw()
        try:
            with mock.patch("palworld_trainer.app.time.time", return_value=1234.567):
                app = TrainerApp(root, "test")

            self.assertEqual(1234568, app._next_bridge_request_id())
        finally:
            root.destroy()

    def test_ui_queue_drains_during_headless_updates(self) -> None:
        root = tk.Tk()
        root.withdraw()
        try:
            app = TrainerApp(root, "test")
            seen: list[str] = []
            app._queue_ui_call(lambda: seen.append("done"))
            deadline = time.time() + 1.0
            while time.time() < deadline and not seen:
                root.update()
                time.sleep(0.05)

            self.assertEqual(["done"], seen)
        finally:
            root.destroy()

    def test_hidden_commands_require_new_enough_bridge_version(self) -> None:
        root = tk.Tk()
        root.withdraw()
        try:
            app = TrainerApp(root, "test")
            with (
                mock.patch.object(app, "_bridge_runtime_ready", return_value=True),
                mock.patch.object(
                    app,
                    "_read_bridge_status",
                    return_value=BridgeStatus(
                        bridge_version="1.2.0",
                        hidden_registry_ready=True,
                    ),
                ),
            ):
                self.assertTrue(app._bridge_supports_hidden_commands())

            with (
                mock.patch.object(app, "_bridge_runtime_ready", return_value=True),
                mock.patch.object(
                    app,
                    "_read_bridge_status",
                    return_value=BridgeStatus(
                        bridge_version="1.2.0",
                        hidden_registry_ready=False,
                    ),
                ),
            ):
                self.assertFalse(app._bridge_supports_hidden_commands())

            with (
                mock.patch.object(app, "_bridge_runtime_ready", return_value=True),
                mock.patch.object(
                    app,
                    "_read_bridge_status",
                    return_value=BridgeStatus(bridge_version="1.1.2"),
                ),
            ):
                self.assertFalse(app._bridge_supports_hidden_commands())
        finally:
            root.destroy()

    def test_unlock_fast_travel_prefers_hidden_bridge_request_when_supported(self) -> None:
        root = tk.Tk()
        root.withdraw()
        try:
            app = TrainerApp(root, "test")
            with (
                mock.patch.object(app, "_bridge_supports_hidden_commands", return_value=True),
                mock.patch.object(
                    app,
                    "_write_bridge_hidden_commands",
                    return_value=(True, "ok"),
                ) as hidden_req,
                mock.patch.object(app, "_send_with_label") as send_one,
                mock.patch.object(app, "_send_many") as send_many,
            ):
                app._on_unlock_fast_travel()

            hidden_req.assert_called_once_with([cmd.unlock_fast_travel()])
            send_one.assert_not_called()
            send_many.assert_not_called()
        finally:
            root.destroy()

    def test_hidden_commands_fall_back_to_reference_compatible_chat_path(self) -> None:
        root = tk.Tk()
        root.withdraw()
        try:
            app = TrainerApp(root, "test")
            with (
                mock.patch.object(app, "_bridge_supports_hidden_commands", return_value=False),
                mock.patch.object(app, "_bridge_can_hide_chat_commands", return_value=True),
                mock.patch(
                    "palworld_trainer.app.game_control.send_chat_commands",
                    return_value=[mock.Mock(ok=True, message="Sent")],
                ) as send_many,
                mock.patch.object(app, "_show_result") as show_result,
            ):
                app._dispatch_hidden_commands(
                    [cmd.giveme("Wood", 2)],
                    label="发放物品 x2",
                )

            send_many.assert_called_once_with([cmd.giveme("Wood", 2)])
            show_result.assert_called_once()
            shown_text = show_result.call_args.args[0]
            self.assertIn("兼容模式", shown_text)
        finally:
            root.destroy()

    def test_hidden_commands_report_when_bridge_and_fallback_both_unavailable(self) -> None:
        root = tk.Tk()
        root.withdraw()
        try:
            app = TrainerApp(root, "test")
            with (
                mock.patch.object(app, "_bridge_supports_hidden_commands", return_value=False),
                mock.patch.object(app, "_bridge_can_hide_chat_commands", return_value=False),
                mock.patch.object(app, "_bridge_runtime_ready", return_value=True),
                mock.patch.object(
                    app,
                    "_read_bridge_status",
                    return_value=BridgeStatus(bridge_version="1.1.2"),
                ),
                mock.patch(
                    "palworld_trainer.app.game_control.send_chat_commands"
                ) as send_many,
                mock.patch.object(app, "_show_result") as show_result,
            ):
                app._dispatch_hidden_commands(
                    [cmd.giveme("Wood", 2)],
                    label="发放物品 x2",
                )

            send_many.assert_not_called()
            show_result.assert_called_once()
            shown_text = show_result.call_args.args[0]
            self.assertIn("1.1.2", shown_text)
            self.assertIn("兼容模式也不可用", shown_text)
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()
