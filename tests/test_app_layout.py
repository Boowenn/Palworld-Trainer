from __future__ import annotations

import time
import tkinter as tk
import unittest
from unittest import mock

from tests import _bootstrap  # noqa: F401
from palworld_trainer import commands as cmd
from palworld_trainer.app import TAB_NAMES, TrainerApp
from palworld_trainer.cheats import BridgeNearbyEntry, BridgeStatus, CheatState
from palworld_trainer.coord_presets import CoordPreset
from palworld_trainer.reference_parity import (
    REFERENCE_ADD_PAL_DETAIL_TABS,
    REFERENCE_ADD_PAL_TABS,
)


def _make_root() -> tk.Tk:
    last_error: Exception | None = None
    for _ in range(3):
        try:
            root = tk.Tk()
            root.withdraw()
            return root
        except tk.TclError as error:
            last_error = error
            time.sleep(0.1)
    raise last_error  # type: ignore[misc]


class AppLayoutTests(unittest.TestCase):
    def test_main_tabs_follow_reference_style_flow(self) -> None:
        root = _make_root()
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

            self.assertTrue(hasattr(app, "item_category_notebook"))
            self.assertTrue(hasattr(app, "pal_category_notebook"))
            self.assertEqual(
                [app.pal_category_notebook.tab(tab_id, "text") for tab_id in app.pal_category_notebook.tabs()],
                list(REFERENCE_ADD_PAL_TABS),
            )
            self.assertTrue(hasattr(app, "pal_favorite_listbox"))
            self.assertTrue(hasattr(app, "pal_detail_notebook"))
            self.assertEqual(
                [app.pal_detail_notebook.tab(tab_id, "text") for tab_id in app.pal_detail_notebook.tabs()],
                list(REFERENCE_ADD_PAL_DETAIL_TABS),
            )
            self.assertTrue(hasattr(app, "coord_group_listbox"))
            self.assertTrue(hasattr(app, "coord_item_listbox"))
            self.assertTrue(hasattr(app, "common_ref_godmode_var"))
            self.assertTrue(hasattr(app, "online_fly_var"))
            self.assertTrue(hasattr(app, "online_esp_text"))
            self.assertTrue(hasattr(app, "mem_attach_label"))
            self.assertTrue(hasattr(app, "pal_skill_listbox"))
            self.assertTrue(hasattr(app, "pal_passive_listbox"))
            self.assertTrue(hasattr(app, "online_pal_skill_listbox"))
            self.assertTrue(hasattr(app, "tech_quick_group_box"))
            self.assertTrue(hasattr(app, "env_text"))
            self.assertTrue(hasattr(app, "changelog_text"))
        finally:
            root.destroy()

    def test_add_pal_reference_tabs_keep_spawn_list_and_sync_detail_tabs(self) -> None:
        root = _make_root()
        try:
            app = TrainerApp(root, "test")
            favorite_key = app.pal_entries[0].key
            app.settings.favorite_pal_ids = [favorite_key]
            app._refresh_pal_reference_favorites()

            detail_index = REFERENCE_ADD_PAL_TABS.index("习得技能")
            app.pal_category_notebook.select(detail_index)
            app._on_pal_reference_tab_changed()

            self.assertGreater(len(app._current_pal_results), 0)
            active_detail = app.pal_detail_notebook.tab(app.pal_detail_notebook.select(), "text")
            self.assertEqual("习得技能", active_detail)

            favorite_index = REFERENCE_ADD_PAL_TABS.index("收藏夹")
            app.pal_category_notebook.select(favorite_index)
            app._on_pal_reference_tab_changed()

            self.assertEqual([favorite_key], [entry.key for entry in app._current_pal_results])
        finally:
            root.destroy()

    def test_fly_prefers_bridge_request_when_runtime_ready(self) -> None:
        root = _make_root()
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
        root = _make_root()
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
        root = _make_root()
        try:
            with mock.patch("palworld_trainer.app.time.time", return_value=1234.567):
                app = TrainerApp(root, "test")

            self.assertEqual(1234568, app._next_bridge_request_id())
        finally:
            root.destroy()

    def test_common_shortcuts_use_supported_bridge_toggles(self) -> None:
        root = _make_root()
        try:
            app = TrainerApp(root, "test")
            app.bridge_dura_var.set(False)
            app.bridge_ammo_var.set(False)
            with mock.patch.object(app, "_apply_player_cheats") as apply_cheats:
                app._on_enable_no_durability_shortcut()
                app._on_enable_inf_ammo_shortcut()
                app._on_enable_no_durability_shortcut()
                app._on_enable_inf_ammo_shortcut()

            self.assertFalse(app.bridge_dura_var.get())
            self.assertFalse(app.bridge_ammo_var.get())
            self.assertEqual(4, apply_cheats.call_count)
        finally:
            root.destroy()

    def test_recipe_and_statue_shortcuts_use_supported_commands(self) -> None:
        root = _make_root()
        try:
            app = TrainerApp(root, "test")
            with mock.patch.object(app, "_dispatch_hidden_commands") as dispatch:
                app._on_unlock_recipes_shortcut()
                app._on_give_all_statues_shortcut()

            self.assertEqual(
                [
                    mock.call([cmd.unlock_recipes()], label="解锁全部配方"),
                    mock.call([cmd.give_all_statues()], label="给满绿胖子像"),
                ],
                dispatch.call_args_list,
            )
        finally:
            root.destroy()

    def test_apply_player_cheats_syncs_reference_toggle_commands(self) -> None:
        root = _make_root()
        try:
            app = TrainerApp(root, "test")
            app.cheat_state = CheatState()
            app.bridge_godmode_var.set(True)
            app.bridge_stamina_var.set(True)
            app.bridge_weight_var.set(False)
            app.bridge_ammo_var.set(True)
            app.bridge_dura_var.set(True)
            app.bridge_speed_var.set("1")
            app.bridge_jump_var.set("1")

            with (
                mock.patch.object(app, "_ensure_player_bridge", return_value=(True, "ok")),
                mock.patch.object(app, "_bridge_toggles_path", return_value=mock.Mock()),
                mock.patch("palworld_trainer.app.write_toggles", return_value=(True, "ok")),
                mock.patch.object(app, "_hidden_command_block_reason", return_value=None),
                mock.patch.object(
                    app,
                    "_execute_hidden_commands",
                    return_value=(True, "ok", "bridge"),
                ) as execute_hidden,
                mock.patch.object(app, "_refresh_player_bridge_status"),
                mock.patch.object(app, "_show_result"),
            ):
                app._apply_player_cheats()

            execute_hidden.assert_called_once_with(
                [
                    cmd.toggle_godmode(),
                    cmd.toggle_inf_stamina(),
                    cmd.toggle_inf_ammo(),
                    cmd.toggle_no_durability(),
                ]
            )
        finally:
            root.destroy()

    def test_duplicate_current_pal_uses_recent_spawned_pal(self) -> None:
        root = _make_root()
        try:
            app = TrainerApp(root, "test")
            app.settings.recent_pal_ids = ["SheepBall"]
            with mock.patch.object(app, "_dispatch_hidden_commands") as dispatch:
                app._on_duplicate_current_pal()

            dispatch.assert_called_once()
            self.assertEqual([cmd.spawn_pal("SheepBall", 1)], dispatch.call_args.args[0])
        finally:
            root.destroy()

    def test_collect_player_cheat_state_includes_ammo_and_durability(self) -> None:
        root = _make_root()
        try:
            app = TrainerApp(root, "test")
            app.bridge_ammo_var.set(True)
            app.bridge_dura_var.set(True)
            state = app._collect_player_cheat_state_impl()

            assert state is not None
            self.assertTrue(state.inf_ammo)
            self.assertTrue(state.no_durability)
        finally:
            root.destroy()

    def test_refresh_esp_views_renders_players_and_static_hits(self) -> None:
        root = _make_root()
        try:
            app = TrainerApp(root, "test")
            app._coord_entries = (
                CoordPreset(group="帕鲁蛋", name="测试蛋", x=100.0, y=0.0, z=0.0),
                CoordPreset(group="宝箱", name="测试宝箱", x=200.0, y=0.0, z=0.0),
            )
            status = BridgeStatus(
                player_valid=True,
                controller_valid=True,
                camera_valid=True,
                position_x=0.0,
                position_y=0.0,
                position_z=0.0,
                camera_x=0.0,
                camera_y=0.0,
                camera_z=0.0,
                camera_pitch=0.0,
                camera_yaw=0.0,
                camera_roll=0.0,
                camera_fov=90.0,
                nearby_players=(
                    BridgeNearbyEntry(
                        name="BP_PlayerPawn_C_12",
                        class_name="BP_PlayerPawn_C",
                        location="(100,0,0)",
                        distance_meters=1.0,
                        world_x=100.0,
                        world_y=0.0,
                        world_z=0.0,
                    ),
                ),
            )
            with mock.patch.object(app, "_read_bridge_status", return_value=status):
                app._refresh_esp_views()

            text = app.online_esp_text.get("1.0", "end")
            self.assertIn("BP_PlayerPawn_C_12", text)
            self.assertIn("测试蛋", text)
            self.assertIn("测试宝箱", text)
        finally:
            root.destroy()

    def test_esp_overlay_open_and_close_are_safe(self) -> None:
        root = _make_root()
        try:
            app = TrainerApp(root, "test")
            status = BridgeStatus(
                player_valid=True,
                controller_valid=True,
                camera_valid=True,
                camera_x=0.0,
                camera_y=0.0,
                camera_z=0.0,
                camera_pitch=0.0,
                camera_yaw=0.0,
                camera_roll=0.0,
                camera_fov=90.0,
                nearby_players=(
                    BridgeNearbyEntry(
                        name="BP_PlayerPawn_C_12",
                        class_name="BP_PlayerPawn_C",
                        location="(100,0,0)",
                        distance_meters=1.0,
                        world_x=100.0,
                        world_y=0.0,
                        world_z=0.0,
                    ),
                ),
            )
            with (
                mock.patch.object(app, "_read_bridge_status", return_value=status),
                mock.patch(
                    "palworld_trainer.app.game_control.get_palworld_window_client_rect",
                    return_value=(0, 0, 1280, 720),
                ),
                mock.patch("palworld_trainer.app.game_control.make_window_clickthrough"),
            ):
                app._open_esp_overlay()

            assert app._esp_overlay_window is not None
            self.assertTrue(app._esp_overlay_window.winfo_exists())
            self.assertIsNone(app._esp_overlay_canvas)
            self.assertGreater(app._esp_overlay_marker_count(), 0)

            app._close_esp_overlay()

            self.assertIsNone(app._esp_overlay_window)
            self.assertIsNone(app._esp_overlay_canvas)
            self.assertEqual(0, app._esp_overlay_marker_count())
        finally:
            root.destroy()

    def test_project_world_to_viewport_centers_forward_target(self) -> None:
        root = _make_root()
        try:
            app = TrainerApp(root, "test")
            status = BridgeStatus(
                camera_valid=True,
                camera_x=0.0,
                camera_y=0.0,
                camera_z=0.0,
                camera_pitch=0.0,
                camera_yaw=0.0,
                camera_roll=0.0,
                camera_fov=90.0,
            )

            projected = app._project_world_to_viewport(status, 100.0, 0.0, 0.0, 1000, 600)

            assert projected is not None
            screen_x, screen_y, depth_meters = projected
            self.assertAlmostEqual(500.0, screen_x, delta=0.5)
            self.assertAlmostEqual(300.0, screen_y, delta=0.5)
            self.assertGreater(depth_meters, 0.0)
        finally:
            root.destroy()

    def test_hidden_fallback_dispatch_skips_focus_restore(self) -> None:
        root = _make_root()
        try:
            app = TrainerApp(root, "test")
            root.withdraw()
            with (
                mock.patch.object(app, "_bridge_runtime_ready", return_value=False),
                mock.patch.object(app, "_hidden_command_dispatch_mode", return_value="fallback"),
                mock.patch(
                    "palworld_trainer.app.game_control.send_chat_commands_isolated",
                    return_value=[mock.Mock(ok=True, message="ok")],
                ) as send_chat_commands,
            ):
                app._dispatch_hidden_commands(["@!unlockft"], label="解锁全部传送点")

            send_chat_commands.assert_called_once_with(
                ["@!unlockft"],
                restore_focus=False,
            )
        finally:
            root.destroy()

    def test_ui_queue_drains_during_headless_updates(self) -> None:
        root = _make_root()
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
        root = _make_root()
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
                        hidden_dispatch_ready=True,
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
                        hidden_dispatch_ready=False,
                    ),
                ),
            ):
                self.assertFalse(app._bridge_supports_hidden_commands())

            with (
                mock.patch.object(app, "_bridge_runtime_ready", return_value=True),
                mock.patch.object(
                    app,
                    "_read_bridge_status",
                    return_value=BridgeStatus(bridge_version="1.1.2", player_valid=True),
                ),
            ):
                self.assertFalse(app._bridge_supports_hidden_commands())
        finally:
            root.destroy()

    def test_unlock_fast_travel_prefers_hidden_bridge_request_when_supported(self) -> None:
        root = _make_root()
        try:
            app = TrainerApp(root, "test")
            with (
                mock.patch.object(app, "_bridge_runtime_ready", return_value=False),
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
        root = _make_root()
        try:
            app = TrainerApp(root, "test")
            with (
                mock.patch.object(app, "_bridge_runtime_ready", return_value=False),
                mock.patch.object(app, "_bridge_supports_hidden_commands", return_value=False),
                mock.patch.object(app, "_bridge_can_hide_chat_commands", return_value=True),
                mock.patch(
                    "palworld_trainer.app.game_control.send_chat_commands_isolated",
                    return_value=[mock.Mock(ok=True, message="Sent")],
                ) as send_many,
                mock.patch.object(app, "_show_result") as show_result,
            ):
                app._dispatch_hidden_commands(
                    [cmd.giveme("Wood", 2)],
                    label="发放物品 x2",
                )

            send_many.assert_called_once_with(
                [cmd.giveme("Wood", 2)],
                restore_focus=False,
            )
            show_result.assert_called_once()
            shown_text = show_result.call_args.args[0]
            self.assertIn("兼容模式", shown_text)
        finally:
            root.destroy()

    def test_hidden_commands_report_when_bridge_and_fallback_both_unavailable(self) -> None:
        root = _make_root()
        try:
            app = TrainerApp(root, "test")
            with (
                mock.patch.object(app, "_bridge_supports_hidden_commands", return_value=False),
                mock.patch.object(app, "_bridge_can_hide_chat_commands", return_value=False),
                mock.patch.object(app, "_bridge_runtime_ready", return_value=True),
                mock.patch.object(
                    app,
                    "_read_bridge_status",
                    return_value=BridgeStatus(bridge_version="1.1.2", player_valid=True),
                ),
                mock.patch(
                    "palworld_trainer.app.game_control.send_chat_commands_isolated"
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

    def test_hidden_commands_require_world_loaded_before_dispatch(self) -> None:
        root = _make_root()
        try:
            app = TrainerApp(root, "test")
            with (
                mock.patch.object(app, "_bridge_runtime_ready", return_value=True),
                mock.patch.object(
                    app,
                    "_read_bridge_status",
                    return_value=BridgeStatus(
                        bridge_version="1.2.9",
                        controller_valid=True,
                        player_valid=False,
                        chat_suppression_ready=True,
                    ),
                ),
                mock.patch(
                    "palworld_trainer.app.game_control.send_chat_commands_isolated"
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
            self.assertIn("先进入存档/世界", shown_text)
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()
