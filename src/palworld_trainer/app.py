"""幻兽帕鲁修改器主界面。

主界面优先展示点击式常用流程，手动命令和调试入口只作为补充页签保留。
"""

from __future__ import annotations

import os
import json
from queue import Empty, SimpleQueue
import subprocess
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, simpledialog, ttk
from typing import Callable

from . import commands as cmd
from . import game_control
from .catalog import (
    CatalogEntry,
    load_all_catalogs,
    pick_enum_dir,
    search_catalog,
)
from .cheats import (
    BridgeStatus,
    CheatState,
    read_status,
    read_toggles,
    request_path_for,
    status_path_for,
    toggles_path_for,
    write_request,
    write_toggles,
)
from .coord_presets import (
    ALL_GROUPS_LABEL,
    CoordPreset,
    flatten_coord_groups,
    load_coord_groups,
    search_coord_presets,
)
from .config import TrainerSettings, config_dir, load_settings, save_settings
from .coord_workspace import (
    DEFAULT_GROUP_NAME,
    CoordWorkspaceGroup,
    load_coord_workspace,
    save_coord_workspace,
)
from .environment import EnvironmentReport, deploy_bridge, scan_environment
from .mem_engine import (
    CUSTOM_SLOT_TEMPLATES,
    DEFAULT_FREEZE,
    DTYPE_LABELS_CN,
    SLOT_LABELS_CN,
    SLOTS,
    CORE_SLOTS,
    POSITION_SLOTS,
    MODE_SLOTS,
    AttachResult,
    CustomSlot,
    CustomSlotTemplate,
    MemEngine,
)
from .teleport_points import BOSS_TELEPORT_POINTS, BossTeleportPoint
from .reference_parity import (
    REFERENCE_ADD_PAL_DETAIL_TABS,
    REFERENCE_ADD_PAL_TABS,
    REFERENCE_ITEM_TABS,
    REFERENCE_ONLINE_TABS,
    REFERENCE_PAL_EDIT_TABS,
    ReferenceCoordEntry,
    build_reference_item_groups,
    build_reference_spawn_groups,
)


APP_TITLE = "幻兽帕鲁修改器"
WINDOW_WIDTH = 1040
WINDOW_HEIGHT = 760

RESULT_CLEAR_MS = 6000
BRIDGE_HIDDEN_COMMANDS_MIN_VERSION = (1, 2, 0)

TAB_NAMES = (
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
)


def _parse_version_tuple(text: str) -> tuple[int, ...]:
    parts: list[int] = []
    for chunk in text.split("."):
        chunk = chunk.strip()
        if not chunk:
            continue
        if not chunk.isdigit():
            break
        parts.append(int(chunk))
    return tuple(parts)


class TrainerApp:
    """The top-level tkinter application."""

    def __init__(self, root: tk.Tk, version: str) -> None:
        self.root = root
        self.version = version
        self.settings: TrainerSettings = load_settings()
        self.report: EnvironmentReport = scan_environment(self.settings.game_root)
        self.cheat_state: CheatState = self._load_cheat_state()

        enum_dir = pick_enum_dir(self.report.client_cheat_commands_enum_dir)
        self.catalogs = load_all_catalogs(enum_dir)
        self.coord_file_path, self.coord_groups = load_coord_groups(self.report.game_root)

        self.item_entries = self.catalogs.get("item", [])
        self.pal_entries = self.catalogs.get("pal", [])
        self.npc_entries = self.catalogs.get("npc", [])
        self.tech_entries = self.catalogs.get("technology", [])
        self._item_entry_by_key = {entry.key: entry for entry in self.item_entries}
        self._pal_entry_by_key = {entry.key: entry for entry in self.pal_entries}
        self._npc_entry_by_key = {entry.key: entry for entry in self.npc_entries}
        self._tech_entry_by_key = {entry.key: entry for entry in self.tech_entries}
        self._item_guide_groups = self._resolve_choice_groups(
            cmd.ITEM_GUIDE_GROUPS,
            self._item_entry_by_key,
        )
        self._pal_guide_groups = self._resolve_choice_groups(
            cmd.PAL_GUIDE_GROUPS,
            self._pal_entry_by_key,
        )
        self._tech_guide_groups = self._resolve_choice_groups(
            cmd.TECH_GUIDE_GROUPS,
            self._tech_entry_by_key,
        )
        self.boss_points: tuple[BossTeleportPoint, ...] = BOSS_TELEPORT_POINTS
        self._boss_point_by_label: dict[str, BossTeleportPoint] = {
            point.label: point for point in self.boss_points
        }
        self._item_reference_groups = build_reference_item_groups(self.item_entries)
        self._pal_reference_groups = build_reference_spawn_groups(
            self.pal_entries,
            self.npc_entries,
        )
        self._coord_seed_entries = self._build_reference_coord_seed_entries()
        self.coord_workspace_groups = load_coord_workspace(self._coord_seed_entries)
        self._coord_workspace_group_map: dict[str, CoordWorkspaceGroup] = {
            group.name: group for group in self.coord_workspace_groups
        }

        self._current_item_results: list[CatalogEntry] = []
        self._current_pal_results: list[CatalogEntry] = []
        self._current_tech_results: list[CatalogEntry] = []
        self._current_coord_workspace_results: list[ReferenceCoordEntry] = []
        self._item_quick_choice_map: dict[str, CatalogEntry] = {}
        self._item_full_choice_map: dict[str, CatalogEntry] = {}
        self._pal_quick_choice_map: dict[str, CatalogEntry] = {}
        self._pal_full_choice_map: dict[str, CatalogEntry] = {}
        self._tech_quick_choice_map: dict[str, CatalogEntry] = {}
        self._tech_full_choice_map: dict[str, CatalogEntry] = {}
        self._coord_group_names: list[str] = [
            group.name for group in self.coord_groups if group.items
        ]
        self._coord_groups_by_name = {
            group.name: group for group in self.coord_groups if group.items
        }
        self._coord_entries = flatten_coord_groups(self.coord_groups)
        self._coord_entry_by_label = {entry.label: entry for entry in self._coord_entries}
        self._current_coord_results: list[CoordPreset] = []
        self._result_clear_job: str | None = None

        # Direct memory-attach engine — no UE4SS, no in-game mod needed.
        # The engine owns a ticker thread that freezes enabled slots every
        # ~50 ms once the user has calibrated their HP / SP / speed / jump
        # addresses via value scanning.
        self.mem = MemEngine(calibration_dir=config_dir())
        self._mem_slot_vars: dict[str, tk.BooleanVar] = {}
        self._mem_slot_labels: dict[str, ttk.Label] = {}
        self._mem_scan_entries: dict[str, tk.StringVar] = {}
        self._mem_target_entries: dict[str, tk.StringVar] = {}
        # Dynamic custom-slot rows: each key maps to its row frame so we can
        # drop it when the user removes the slot.
        self._mem_custom_row_frames: dict[str, ttk.Frame] = {}
        self._mem_busy: bool = False
        self._mem_refresh_job: str | None = None
        self._route_stop_event = threading.Event()
        self._ui_call_queue: SimpleQueue[Callable[[], None]] = SimpleQueue()
        self._ui_call_job: str | None = None
        self._bridge_request_counter: int = int(time.time() * 1000)

        self._configure_root()
        self._build_style()
        self._build_layout()
        self._schedule_ui_call_drain()
        self._refresh_status()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------
    # Window setup
    # ------------------------------------------------------------------

    def _configure_root(self) -> None:
        self.root.title(f"{APP_TITLE}  v{self.version}")
        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.root.minsize(820, 580)

    def _queue_ui_call(self, callback: Callable[[], None]) -> None:
        self._ui_call_queue.put(callback)

    def _schedule_ui_call_drain(self) -> None:
        self._ui_call_job = self.root.after(40, self._drain_ui_call_queue)

    def _drain_ui_call_queue(self) -> None:
        self._ui_call_job = None
        while True:
            try:
                callback = self._ui_call_queue.get_nowait()
            except Empty:
                break
            try:
                callback()
            except Exception:
                continue
        if self.root.winfo_exists():
            self._schedule_ui_call_drain()
        try:
            self.root.tk.call("tk", "scaling", 1.25)
        except tk.TclError:
            pass

    def _build_style(self) -> None:
        style = ttk.Style()
        for theme in ("vista", "clam", "default"):
            try:
                style.theme_use(theme)
                break
            except tk.TclError:
                continue

        style.configure("Header.TLabel", font=("Microsoft YaHei UI", 18, "bold"))
        style.configure("SubHeader.TLabel", font=("Microsoft YaHei UI", 11, "bold"))
        style.configure("Status.TLabel", font=("Microsoft YaHei UI", 10))
        style.configure("Good.TLabel", foreground="#16a34a", font=("Microsoft YaHei UI", 10, "bold"))
        style.configure("Bad.TLabel", foreground="#dc2626", font=("Microsoft YaHei UI", 10, "bold"))
        style.configure("Warn.TLabel", foreground="#d97706", font=("Microsoft YaHei UI", 10, "bold"))
        style.configure("Result.TLabel", foreground="#2b6cb0", font=("Microsoft YaHei UI", 10, "bold"))
        style.configure("Card.TFrame", relief="solid", borderwidth=1)
        style.configure("Big.TButton", font=("Microsoft YaHei UI", 11, "bold"), padding=(10, 8))
        style.configure("Quiet.TButton", padding=(8, 4))

    def _build_layout(self) -> None:
        outer = ttk.Frame(self.root, padding=(16, 12, 16, 12))
        outer.pack(fill="both", expand=True)

        self._build_header(outer)
        self._build_status_bar(outer)
        self._build_notebook(outer)
        self._build_result_bar(outer)

    def _build_header(self, parent: ttk.Frame) -> None:
        header = ttk.Frame(parent)
        header.pack(fill="x", pady=(0, 10))

        ttk.Label(header, text=APP_TITLE, style="Header.TLabel").pack(side="left")
        ttk.Label(header, text=f"v{self.version}", style="Status.TLabel").pack(
            side="left", padx=(10, 0)
        )

    def _build_status_bar(self, parent: ttk.Frame) -> None:
        bar = ttk.Frame(parent, style="Card.TFrame", padding=(12, 10))
        bar.pack(fill="x")

        self.status_game = ttk.Label(bar, text="游戏：检测中", style="Status.TLabel")
        self.status_game.pack(side="left", padx=(0, 18))

        self.status_cheats = ttk.Label(bar, text="聊天命令：检测中", style="Status.TLabel")
        self.status_cheats.pack(side="left", padx=(0, 18))

        self.status_mem = ttk.Label(bar, text="增强模块：检测中", style="Status.TLabel")
        self.status_mem.pack(side="left")

        ttk.Button(bar, text="刷新状态", style="Quiet.TButton", command=self._refresh_status).pack(
            side="right"
        )

    def _build_notebook(self, parent: ttk.Frame) -> None:
        self.notebook = ttk.Notebook(parent)
        self.notebook.pack(fill="both", expand=True, pady=(10, 8))

        self._build_settings_tab()
        self._build_common_tab()
        self._build_tech_tab()
        self._build_player_tab()
        self._build_pal_edit_tab()
        self._build_online_pal_tab()
        self._build_items_tab()
        self._build_pals_tab()
        self._build_coords_tab()
        self._build_online_tab()
        self._build_changelog_tab()

        try:
            self.notebook.select(TAB_NAMES.index(self.settings.last_tab))
        except (ValueError, tk.TclError):
            self.notebook.select(0)

        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

    def _build_result_bar(self, parent: ttk.Frame) -> None:
        self.result_label = ttk.Label(
            parent,
            text="就绪。先启动游戏并进入世界，再点击上方按钮。",
            style="Status.TLabel",
        )
        self.result_label.pack(fill="x")

    # ------------------------------------------------------------------
    # Tabs
    # ------------------------------------------------------------------

    def _build_common_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=16)
        self.notebook.add(tab, text="常用功能")

        ttk.Label(tab, text="常用功能", style="SubHeader.TLabel").pack(anchor="w")

        ttk.Label(tab, text="启动与修复", style="SubHeader.TLabel").pack(anchor="w")

        grid = ttk.Frame(tab)
        grid.pack(fill="x", pady=(8, 0))

        buttons: list[tuple[str, Callable[[], None]]] = [
            ("🚀 启动游戏", self._launch_game),
            ("🧩 部署/更新增强模块", self._on_deploy_bridge),
            ("📂 打开游戏目录", self._open_game_dir),
            ("🔄 刷新状态", self._refresh_status),
        ]
        for index, (label, callback) in enumerate(buttons):
            ttk.Button(grid, text=label, style="Big.TButton", command=callback).grid(
                row=index // 2, column=index % 2, padx=6, pady=6, sticky="ew"
            )
        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, weight=1)

        ttk.Separator(tab).pack(fill="x", pady=(14, 10))

        ttk.Label(tab, text="角色快捷操作", style="SubHeader.TLabel").pack(anchor="w")
        common_row = ttk.Frame(tab)
        common_row.pack(fill="x", pady=(8, 14))
        common_buttons: list[tuple[str, Callable[[], None]]] = [
            ("🦅 开启飞行", lambda: self._on_mem_fly(True)),
            ("🛬 关闭飞行", lambda: self._on_mem_fly(False)),
            ("🛠 脱困", lambda: self._send_with_label(cmd.unstuck(), "脱困")),
            ("📍 读取坐标", self._on_mem_read_pos),
        ]
        for index, (label, callback) in enumerate(common_buttons):
            ttk.Button(common_row, text=label, style="Big.TButton", command=callback).grid(
                row=0, column=index, padx=6, pady=4, sticky="ew"
            )
            common_row.columnconfigure(index, weight=1)

        ttk.Label(tab, text="世界解锁", style="SubHeader.TLabel").pack(anchor="w")
        unlock_row = ttk.Frame(tab)
        unlock_row.pack(fill="x", pady=(8, 14))
        unlock_buttons: list[tuple[str, Callable[[], None]]] = [
            ("📍 解锁传送点", lambda: self._send(cmd.unlock_fast_travel())),
            ("🔓 解锁全部科技", lambda: self._send(cmd.unlock_all_tech())),
            ("🎁 打开物品页", lambda: self.notebook.select(TAB_NAMES.index("items"))),
            ("🧭 打开坐标页", lambda: self.notebook.select(TAB_NAMES.index("coords"))),
        ]
        for index, (label, callback) in enumerate(unlock_buttons):
            ttk.Button(unlock_row, text=label, style="Big.TButton", command=callback).grid(
                row=0, column=index, padx=6, pady=4, sticky="ew"
            )
            unlock_row.columnconfigure(index, weight=1)

        ttk.Label(tab, text="世界时间", style="SubHeader.TLabel").pack(anchor="w")
        ttk.Label(
            tab,
            text="拖动小时数后点「设置时间」，或直接使用下方的清晨/正午/黄昏/午夜快捷按钮。",
            style="Status.TLabel",
        ).pack(anchor="w", pady=(2, 8))

        slider_row = ttk.Frame(tab)
        slider_row.pack(fill="x", pady=(4, 10))
        self.common_time_var = tk.IntVar(value=12)
        ttk.Scale(
            slider_row,
            from_=0,
            to=23,
            orient="horizontal",
            variable=self.common_time_var,
            command=lambda _value: self._refresh_time_label(
                self.common_time_var, self.common_time_label
            ),
        ).pack(side="left", fill="x", expand=True)
        self.common_time_label = ttk.Label(slider_row, text="12 时", width=8, anchor="e")
        self.common_time_label.pack(side="left", padx=(10, 0))
        ttk.Button(
            slider_row,
            text="设置时间",
            style="Big.TButton",
            command=lambda: self._send(cmd.set_time(self.common_time_var.get())),
        ).pack(side="left", padx=(10, 0))

        quick = ttk.Frame(tab)
        quick.pack(fill="x", pady=(0, 4))
        for label, hour in (
            ("🌅 清晨 6:00", 6),
            ("☀️ 正午 12:00", 12),
            ("🌆 黄昏 18:00", 18),
            ("🌙 午夜 0:00", 0),
        ):
            ttk.Button(
                quick,
                text=label,
                style="Big.TButton",
                command=lambda h=hour: self._send(cmd.set_time(h)),
            ).pack(side="left", padx=4)

    def _build_player_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=16)
        self.notebook.add(tab, text="角色属性")
        self._build_simple_player_tab(tab)
        return

    def _build_simple_player_tab(self, tab: ttk.Frame) -> None:
        ttk.Label(tab, text="角色属性", style="SubHeader.TLabel").pack(anchor="w")

        quick_frame = ttk.LabelFrame(tab, text="角色快捷操作", padding=(12, 8))
        quick_frame.pack(fill="x", pady=(0, 10))

        quick_row = ttk.Frame(quick_frame)
        quick_row.pack(fill="x", pady=(0, 6))
        quick_buttons: list[tuple[str, Callable[[], None]]] = [
            ("🦅 开启飞行", lambda: self._on_mem_fly(True)),
            ("🛬 关闭飞行", lambda: self._on_mem_fly(False)),
            ("🛠 脱困", lambda: self._send_with_label(cmd.unstuck(), "脱困")),
            ("📍 读取当前位置", self._on_mem_read_pos),
            ("🧭 打开坐标页", lambda: self.notebook.select(TAB_NAMES.index("coords"))),
            ("🧩 部署增强模块", self._on_deploy_bridge),
        ]
        for index, (label, callback) in enumerate(quick_buttons):
            ttk.Button(
                quick_row,
                text=label,
                style="Big.TButton",
                command=callback,
            ).grid(row=index // 3, column=index % 3, padx=6, pady=4, sticky="ew")
        for col in range(3):
            quick_row.columnconfigure(col, weight=1)

        cheats_frame = ttk.LabelFrame(tab, text="角色增强（需增强模块）", padding=(12, 8))
        cheats_frame.pack(fill="x")

        cheats_head = ttk.Frame(cheats_frame)
        cheats_head.pack(fill="x", pady=(0, 6))
        self.player_bridge_status_label = ttk.Label(
            cheats_head, text="", style="Status.TLabel"
        )
        self.player_bridge_status_label.pack(side="left", fill="x", expand=True)
        ttk.Button(
            cheats_head,
            text="部署/更新增强模块",
            style="Quiet.TButton",
            command=self._on_deploy_bridge,
        ).pack(side="right")

        toggles_row = ttk.Frame(cheats_frame)
        toggles_row.pack(fill="x", pady=(0, 6))
        self.bridge_godmode_var = tk.BooleanVar(value=self.cheat_state.godmode)
        self.bridge_stamina_var = tk.BooleanVar(value=self.cheat_state.inf_stamina)
        self.bridge_weight_var = tk.BooleanVar(value=self.cheat_state.weight_zero)
        ttk.Checkbutton(
            toggles_row, text="无敌", variable=self.bridge_godmode_var
        ).pack(side="left", padx=(0, 12))
        ttk.Checkbutton(
            toggles_row, text="无限体力", variable=self.bridge_stamina_var
        ).pack(side="left", padx=(0, 12))
        ttk.Checkbutton(
            toggles_row, text="无限负重", variable=self.bridge_weight_var
        ).pack(side="left")

        multiplier_row = ttk.Frame(cheats_frame)
        multiplier_row.pack(fill="x", pady=(0, 6))
        ttk.Label(multiplier_row, text="移速倍率:").pack(side="left")
        self.bridge_speed_var = tk.StringVar(
            value=f"{self.cheat_state.speed_multiplier:g}"
        )
        ttk.Entry(multiplier_row, textvariable=self.bridge_speed_var, width=8).pack(
            side="left", padx=(4, 12)
        )
        ttk.Label(multiplier_row, text="跳跃倍率:").pack(side="left")
        self.bridge_jump_var = tk.StringVar(
            value=f"{self.cheat_state.jump_multiplier:g}"
        )
        ttk.Entry(multiplier_row, textvariable=self.bridge_jump_var, width=8).pack(
            side="left", padx=(4, 12)
        )
        ttk.Button(
            multiplier_row,
            text="应用增强状态",
            style="Big.TButton",
            command=self._apply_player_cheats,
        ).pack(side="left", padx=(6, 4))
        ttk.Button(
            multiplier_row,
            text="恢复默认倍率",
            style="Quiet.TButton",
            command=self._reset_player_multipliers,
        ).pack(side="left")

        ttk.Label(
            tab,
            text="主界面已经按傻瓜模式重构，不再引导你做手动搜索地址。",
            style="Status.TLabel",
        ).pack(anchor="w", pady=(10, 0))

        self._refresh_player_bridge_status()

    def _build_pal_edit_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=16)
        self.notebook.add(tab, text="帕鲁修改")

        ttk.Label(tab, text="帕鲁修改", style="SubHeader.TLabel").pack(anchor="w")
        ttk.Label(
            tab,
            text=(
                "参考修改器这里是单机帕鲁编辑入口。当前仓库这一轮先按参考版把入口和信息架构对齐，"
                "并把新增/传送/常用流程移出可见命令输入；帕鲁精修会继续往这个页里补。"
            ),
            style="Status.TLabel",
            wraplength=860,
            justify="left",
        ).pack(anchor="w", pady=(4, 10))

        actions = ttk.Frame(tab)
        actions.pack(fill="x", pady=(0, 10))
        ttk.Button(
            actions,
            text="打开 *添加帕鲁",
            style="Big.TButton",
            command=lambda: self.notebook.select(TAB_NAMES.index("pals")),
        ).pack(side="left", padx=(0, 6))
        ttk.Button(
            actions,
            text="部署/更新增强模块",
            style="Quiet.TButton",
            command=self._on_deploy_bridge,
        ).pack(side="left", padx=(0, 6))
        ttk.Button(
            actions,
            text="刷新状态",
            style="Quiet.TButton",
            command=self._refresh_status,
        ).pack(side="left")

        inner = ttk.Notebook(tab)
        inner.pack(fill="both", expand=True)

        base = ttk.Frame(inner, padding=12)
        inner.add(base, text="基础")
        ttk.Label(
            base,
            text="基础属性、等级、星级、个体值、词条入口会按参考页继续往这里收敛。",
            style="Status.TLabel",
            wraplength=820,
            justify="left",
        ).pack(anchor="w")

        learned = ttk.Frame(inner, padding=12)
        inner.add(learned, text="习得技能")
        ttk.Label(
            learned,
            text="技能编辑入口已保留页位，后续补齐到和参考版一致的批量技能流。",
            style="Status.TLabel",
            wraplength=820,
            justify="left",
        ).pack(anchor="w")

        more = ttk.Frame(inner, padding=12)
        inner.add(more, text="更多数据")
        ttk.Label(
            more,
            text="更多数据页位已预留，后续用于对齐工作速度、SAN、体力等扩展字段。",
            style="Status.TLabel",
            wraplength=820,
            justify="left",
        ).pack(anchor="w")

    def _build_online_pal_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=16)
        self.notebook.add(tab, text="*联机帕鲁修改")

        ttk.Label(tab, text="*联机帕鲁修改", style="SubHeader.TLabel").pack(anchor="w")
        ttk.Label(
            tab,
            text=(
                "参考修改器把它作为高级入口。当前版本先保留同名入口，"
                "并把可稳定的桥接与无可见命令能力继续向这里迁移。"
            ),
            style="Status.TLabel",
            wraplength=860,
            justify="left",
        ).pack(anchor="w", pady=(4, 10))

        row = ttk.Frame(tab)
        row.pack(fill="x", pady=(0, 8))
        ttk.Button(
            row,
            text="打开联机功能",
            style="Big.TButton",
            command=lambda: self.notebook.select(TAB_NAMES.index("online")),
        ).pack(side="left", padx=(0, 6))
        ttk.Button(
            row,
            text="打开传送和移速",
            style="Quiet.TButton",
            command=lambda: self.notebook.select(TAB_NAMES.index("coords")),
        ).pack(side="left", padx=(0, 6))
        ttk.Button(
            row,
            text="刷新状态",
            style="Quiet.TButton",
            command=self._refresh_status,
        ).pack(side="left")

    def _build_online_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=16)
        self.notebook.add(tab, text="联机功能")

        ttk.Label(tab, text="联机功能", style="SubHeader.TLabel").pack(anchor="w")
        ttk.Label(
            tab,
            text=(
                "这里收纳参考版里偏联机/联机房主向的一键操作。当前已切掉可见聊天命令输入，"
                "优先走桥接请求或隐藏命令执行。"
            ),
            style="Status.TLabel",
            wraplength=860,
            justify="left",
        ).pack(anchor="w", pady=(4, 10))

        quick = ttk.LabelFrame(tab, text="联机常用", padding=(12, 8))
        quick.pack(fill="x", pady=(0, 10))
        quick_row = ttk.Frame(quick)
        quick_row.pack(fill="x")
        buttons: list[tuple[str, Callable[[], None]]] = [
            ("切换飞行", lambda: self._on_mem_fly(True)),
            ("关闭飞行", lambda: self._on_mem_fly(False)),
            ("脱困", lambda: self._send_with_label(cmd.unstuck(), "脱困")),
            ("读取坐标", self._on_mem_read_pos),
            ("打开传送和移速", lambda: self.notebook.select(TAB_NAMES.index("coords"))),
        ]
        for index, (label, callback) in enumerate(buttons):
            ttk.Button(
                quick_row,
                text=label,
                style="Big.TButton",
                command=callback,
            ).grid(row=0, column=index, padx=4, pady=4, sticky="ew")
            quick_row.columnconfigure(index, weight=1)

        ttk.Label(
            tab,
            text="更细的联机高级功能还会继续往这个页里收，不再单独暴露自由命令页。",
            style="Status.TLabel",
            wraplength=860,
            justify="left",
        ).pack(anchor="w")

    def _build_changelog_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=16)
        self.notebook.add(tab, text="更新记录")

        ttk.Label(tab, text="更新记录", style="SubHeader.TLabel").pack(anchor="w")
        self.changelog_text = tk.Text(tab, height=18, wrap="word")
        self.changelog_text.pack(fill="both", expand=True, pady=(8, 0))
        self.changelog_text.insert(
            "1.0",
            "\n".join(
                (
                    "参考修改器对齐进行中",
                    "",
                    "本轮已完成：",
                    "1. 顶层页签顺序和命名开始按 chenstack 参考修改器对齐。",
                    "2. 主流程不再依赖可见聊天命令输入。",
                    "3. *添加物品 / *添加帕鲁 / 传送和移速 保留为主操作页。",
                    "",
                    "下一步会继续补齐：",
                    "1. 帕鲁修改页的细分字段。",
                    "2. 联机帕鲁修改页的高级入口。",
                    "3. 制作和建造页的更多参考功能。",
                )
            ),
        )
        self.changelog_text.configure(state="disabled")

    def _build_coords_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=16)
        self.notebook.add(tab, text="传送和移速")

        ttk.Label(tab, text="传送和移速", style="SubHeader.TLabel").pack(anchor="w")
        ttk.Label(
            tab,
            text="参考版这里负责坐标读写、收藏夹、预设坐标和传送；当前页默认走无可见命令的桥接执行。",
            style="Status.TLabel",
        ).pack(anchor="w", pady=(4, 10))

        speed_frame = ttk.LabelFrame(tab, text="移速与飞行", padding=(12, 8))
        speed_frame.pack(fill="x", pady=(0, 10))

        speed_row = ttk.Frame(speed_frame)
        speed_row.pack(fill="x", pady=(0, 6))
        ttk.Button(
            speed_row,
            text="开启飞行",
            style="Big.TButton",
            command=lambda: self._on_mem_fly(True),
        ).pack(side="left", padx=(0, 6))
        ttk.Button(
            speed_row,
            text="关闭飞行",
            style="Quiet.TButton",
            command=lambda: self._on_mem_fly(False),
        ).pack(side="left", padx=(0, 6))
        ttk.Button(
            speed_row,
            text="读取当前坐标",
            style="Quiet.TButton",
            command=self._on_mem_read_pos,
        ).pack(side="left")

        ttk.Label(
            speed_frame,
            text="移速/跳跃倍率和持续增强统一放在「角色属性」页应用，这里保留传送与位移主流程。",
            style="Status.TLabel",
            wraplength=840,
            justify="left",
        ).pack(anchor="w")

        favorite_frame = ttk.LabelFrame(tab, text="收藏夹", padding=(12, 8))
        favorite_frame.pack(fill="x", pady=(0, 10))
        ttk.Label(
            favorite_frame,
            text="把常用首领、商人、洞窟、传送点或基地点位收进这里，下次直接传，不用重新翻分类。",
            style="Status.TLabel",
            wraplength=840,
            justify="left",
        ).pack(anchor="w", pady=(0, 6))

        favorite_row = ttk.Frame(favorite_frame)
        favorite_row.pack(fill="x", pady=(0, 6))
        ttk.Label(favorite_row, text="收藏点位:").pack(side="left")
        self.coord_favorite_var = tk.StringVar()
        self.coord_favorite_box = ttk.Combobox(
            favorite_row,
            textvariable=self.coord_favorite_var,
            values=[],
            state="readonly",
            width=56,
        )
        self.coord_favorite_box.pack(side="left", padx=(6, 10), fill="x", expand=True)
        self.coord_favorite_box.bind(
            "<<ComboboxSelected>>",
            lambda _event: self._update_coord_favorite_hint(),
        )
        ttk.Button(
            favorite_row,
            text="载入坐标",
            style="Quiet.TButton",
            command=self._load_selected_coord_favorite,
        ).pack(side="left", padx=(0, 6))
        ttk.Button(
            favorite_row,
            text="直接传过去",
            style="Big.TButton",
            command=self._teleport_selected_coord_favorite,
        ).pack(side="left", padx=(0, 6))
        ttk.Button(
            favorite_row,
            text="追加到路径",
            style="Quiet.TButton",
            command=self._append_selected_coord_favorite_to_route,
        ).pack(side="left", padx=(0, 6))
        ttk.Button(
            favorite_row,
            text="移除收藏",
            style="Quiet.TButton",
            command=self._remove_selected_coord_favorite,
        ).pack(side="left")

        self.coord_favorite_hint_label = ttk.Label(
            favorite_frame,
            text="",
            style="Status.TLabel",
            wraplength=840,
            justify="left",
        )
        self.coord_favorite_hint_label.pack(anchor="w")

        preset_frame = ttk.LabelFrame(tab, text="通用坐标库", padding=(12, 8))
        preset_frame.pack(fill="x", pady=(0, 10))

        preset_note = (
            "支持基地、采集点、首领、悬赏、洞窟、传送点、商人和各等级区域。"
            " 输入关键词时会自动跨分类搜索。"
        )
        if self.coord_file_path is not None:
            preset_note += f" 当前坐标库：{self.coord_file_path.name}"
        else:
            preset_note += " 当前还没找到坐标库文件。"
        ttk.Label(
            preset_frame,
            text=preset_note,
            style="Status.TLabel",
            wraplength=840,
            justify="left",
        ).pack(anchor="w", pady=(0, 6))

        preset_filter_row = ttk.Frame(preset_frame)
        preset_filter_row.pack(fill="x", pady=(0, 6))
        ttk.Label(preset_filter_row, text="分类:").pack(side="left")
        self.coord_group_var = tk.StringVar()
        group_values = [ALL_GROUPS_LABEL, *self._coord_group_names]
        default_group = next(
            (name for name in self._coord_group_names if "Boss" in name),
            self._coord_group_names[0] if self._coord_group_names else ALL_GROUPS_LABEL,
        )
        self.coord_group_var.set(default_group)
        self.coord_group_box = ttk.Combobox(
            preset_filter_row,
            textvariable=self.coord_group_var,
            values=group_values,
            state="readonly",
            width=28,
        )
        self.coord_group_box.pack(side="left", padx=(6, 10))
        self.coord_group_box.bind(
            "<<ComboboxSelected>>",
            lambda _event: self._refresh_coord_presets(),
        )

        ttk.Label(preset_filter_row, text="搜索:").pack(side="left")
        self.coord_search_var = tk.StringVar()
        self.coord_search_var.trace_add("write", lambda *_args: self._refresh_coord_presets())
        ttk.Entry(
            preset_filter_row, textvariable=self.coord_search_var, width=26
        ).pack(side="left", padx=(6, 0), fill="x", expand=True)

        preset_pick_row = ttk.Frame(preset_frame)
        preset_pick_row.pack(fill="x", pady=(0, 6))
        ttk.Label(preset_pick_row, text="点位:").pack(side="left")
        self.coord_preset_var = tk.StringVar()
        self.coord_preset_box = ttk.Combobox(
            preset_pick_row,
            textvariable=self.coord_preset_var,
            values=[],
            state="readonly",
            width=56,
        )
        self.coord_preset_box.pack(side="left", padx=(6, 10), fill="x", expand=True)
        self.coord_preset_box.bind(
            "<<ComboboxSelected>>",
            lambda _event: self._update_coord_preset_hint(),
        )
        ttk.Button(
            preset_pick_row,
            text="载入坐标",
            style="Quiet.TButton",
            command=self._load_selected_coord_preset,
        ).pack(side="left", padx=(0, 6))
        ttk.Button(
            preset_pick_row,
            text="直接传过去",
            style="Big.TButton",
            command=self._teleport_selected_coord_preset,
        ).pack(side="left", padx=(0, 6))
        ttk.Button(
            preset_pick_row,
            text="追加到路径",
            style="Quiet.TButton",
            command=self._append_selected_coord_preset_to_route,
        ).pack(side="left", padx=(0, 6))
        ttk.Button(
            preset_pick_row,
            text="加入收藏",
            style="Quiet.TButton",
            command=self._add_selected_coord_preset_to_favorites,
        ).pack(side="left")

        self.coord_preset_hint_label = ttk.Label(
            preset_frame,
            text="",
            style="Status.TLabel",
            wraplength=840,
            justify="left",
        )
        self.coord_preset_hint_label.pack(anchor="w")

        boss_frame = ttk.LabelFrame(tab, text="首领直达", padding=(12, 8))
        boss_frame.pack(fill="x", pady=(0, 10))

        boss_row = ttk.Frame(boss_frame)
        boss_row.pack(fill="x", pady=(0, 6))
        ttk.Label(boss_row, text="目标首领:").pack(side="left")
        self.boss_preset_var = tk.StringVar()
        boss_labels = [point.label for point in self.boss_points]
        if boss_labels:
            self.boss_preset_var.set(boss_labels[0])
        self.boss_preset_box = ttk.Combobox(
            boss_row,
            textvariable=self.boss_preset_var,
            values=boss_labels,
            state="readonly",
            width=42,
        )
        self.boss_preset_box.pack(side="left", padx=(6, 10), fill="x", expand=True)
        self.boss_preset_box.bind(
            "<<ComboboxSelected>>",
            lambda _event: self._update_boss_preset_hint(),
        )
        ttk.Button(
            boss_row,
            text="载入坐标",
            style="Quiet.TButton",
            command=self._load_selected_boss_preset,
        ).pack(side="left", padx=(0, 6))
        ttk.Button(
            boss_row,
            text="直接传过去",
            style="Big.TButton",
            command=self._teleport_selected_boss_preset,
        ).pack(side="left", padx=(0, 6))
        ttk.Button(
            boss_row,
            text="加入收藏",
            style="Quiet.TButton",
            command=self._add_selected_boss_preset_to_favorites,
        ).pack(side="left")

        self.boss_preset_hint_label = ttk.Label(
            boss_frame,
            text="",
            style="Status.TLabel",
            wraplength=840,
            justify="left",
        )
        self.boss_preset_hint_label.pack(anchor="w")

        tp_frame = ttk.LabelFrame(tab, text="手动坐标传送", padding=(12, 8))
        tp_frame.pack(fill="x", pady=(0, 10))

        tp_row = ttk.Frame(tp_frame)
        tp_row.pack(fill="x")
        ttk.Label(tp_row, text="X:").pack(side="left")
        self.tp_x_var = tk.StringVar(value="0")
        ttk.Entry(tp_row, textvariable=self.tp_x_var, width=12).pack(
            side="left", padx=(4, 10)
        )
        ttk.Label(tp_row, text="Y:").pack(side="left")
        self.tp_y_var = tk.StringVar(value="0")
        ttk.Entry(tp_row, textvariable=self.tp_y_var, width=12).pack(
            side="left", padx=(4, 10)
        )
        ttk.Label(tp_row, text="Z:").pack(side="left")
        self.tp_z_var = tk.StringVar(value="0")
        ttk.Entry(tp_row, textvariable=self.tp_z_var, width=12).pack(
            side="left", padx=(4, 10)
        )
        ttk.Button(
            tp_row,
            text="读取当前位置",
            style="Quiet.TButton",
            command=self._on_mem_read_pos,
        ).pack(side="left", padx=(0, 6))
        ttk.Button(
            tp_row,
            text="传送到坐标",
            style="Big.TButton",
            command=self._on_mem_teleport,
        ).pack(side="left", padx=(6, 0))

        ttk.Label(
            tp_frame,
            text="支持直接手填 X/Y/Z；如果增强模块已在线，读取当前位置会直接回填这里。",
            style="Status.TLabel",
        ).pack(anchor="w", pady=(6, 0))

        route_frame = ttk.LabelFrame(tab, text="路径传送", padding=(12, 8))
        route_frame.pack(fill="both", expand=True, pady=(0, 10))

        ttk.Label(
            route_frame,
            text=(
                "每行一个 X Y Z，支持空格或逗号分隔。修改器会按顺序逐点写入桥接传送请求，"
                " 适合扫洞窟、商人、宝箱和多点采集路线。"
            ),
            justify="left",
            style="Status.TLabel",
            wraplength=840,
        ).pack(anchor="w", pady=(0, 6))

        route_ctrl = ttk.Frame(route_frame)
        route_ctrl.pack(fill="x", pady=(0, 6))
        ttk.Label(route_ctrl, text="每点停留（秒）:").pack(side="left")
        self.route_delay_var = tk.StringVar(value="3")
        ttk.Entry(route_ctrl, textvariable=self.route_delay_var, width=6).pack(
            side="left", padx=(4, 10)
        )
        self.route_start_btn = ttk.Button(
            route_ctrl,
            text="开始路径传送",
            style="Big.TButton",
            command=self._on_route_start,
        )
        self.route_start_btn.pack(side="left", padx=(0, 4))
        self.route_stop_btn = ttk.Button(
            route_ctrl,
            text="停止",
            style="Big.TButton",
            command=self._on_route_stop,
            state="disabled",
        )
        self.route_stop_btn.pack(side="left")
        self.route_progress_label = ttk.Label(route_ctrl, text="", style="Status.TLabel")
        self.route_progress_label.pack(side="left", padx=(10, 0))

        route_text_frame = ttk.Frame(route_frame)
        route_text_frame.pack(fill="both", expand=True)
        self.route_text = tk.Text(route_text_frame, height=8, wrap="none")
        self.route_text.pack(side="left", fill="both", expand=True)
        route_scroll = ttk.Scrollbar(
            route_text_frame, orient="vertical", command=self.route_text.yview
        )
        self.route_text.configure(yscrollcommand=route_scroll.set)
        route_scroll.pack(side="right", fill="y")
        self.route_text.insert(
            "1.0",
            "# 每行一个坐标：X Y Z（空格或逗号分隔）\n"
            "# 示例：\n"
            "# -350000 120000 15000\n"
            "# -280000, 85000, 12000\n",
        )

        self._refresh_coord_favorites()
        self._refresh_coord_presets()
        self._update_boss_preset_hint()

    def _bridge_toggles_path(self) -> Path | None:
        return toggles_path_for(self.report)

    def _bridge_status_path(self) -> Path | None:
        return status_path_for(self.report)

    def _bridge_request_path(self) -> Path | None:
        return request_path_for(self.report)

    def _bridge_session_log_path(self) -> Path | None:
        target = self.report.trainer_bridge_runtime_target or self.report.trainer_bridge_target
        if target is None:
            return None
        return target / "session.log"

    def _read_bridge_status(self) -> BridgeStatus:
        path = self._bridge_status_path()
        if path is None:
            return BridgeStatus()
        return read_status(path)

    def _bridge_runtime_ready(self) -> bool:
        path = self._bridge_status_path()
        return path is not None and path.exists()

    def _next_bridge_request_id(self) -> int:
        self._bridge_request_counter += 1
        return self._bridge_request_counter

    def _load_cheat_state(self) -> CheatState:
        path = self._bridge_toggles_path()
        if path is None:
            return CheatState()
        return read_toggles(path)

    def _sync_player_cheat_controls(self) -> None:
        if hasattr(self, "bridge_godmode_var"):
            self.bridge_godmode_var.set(self.cheat_state.godmode)
        if hasattr(self, "bridge_stamina_var"):
            self.bridge_stamina_var.set(self.cheat_state.inf_stamina)
        if hasattr(self, "bridge_weight_var"):
            self.bridge_weight_var.set(self.cheat_state.weight_zero)
        if hasattr(self, "bridge_speed_var"):
            self.bridge_speed_var.set(f"{self.cheat_state.speed_multiplier:g}")
        if hasattr(self, "bridge_jump_var"):
            self.bridge_jump_var.set(f"{self.cheat_state.jump_multiplier:g}")
        if hasattr(self, "coord_run_speed_var"):
            self.coord_run_speed_var.set(f"{self.cheat_state.speed_multiplier:g}")
        if hasattr(self, "coord_walk_speed_var"):
            self.coord_walk_speed_var.set(f"{self.cheat_state.speed_multiplier:g}")
        if hasattr(self, "coord_jump_speed_var"):
            self.coord_jump_speed_var.set(f"{self.cheat_state.jump_multiplier:g}")
        if hasattr(self, "common_ref_godmode_var"):
            self.common_ref_godmode_var.set(self.cheat_state.godmode)
        if hasattr(self, "common_ref_stamina_var"):
            self.common_ref_stamina_var.set(self.cheat_state.inf_stamina)
        if hasattr(self, "common_ref_weight_var"):
            self.common_ref_weight_var.set(self.cheat_state.weight_zero)
        if hasattr(self, "online_stamina_var"):
            self.online_stamina_var.set(self.cheat_state.inf_stamina)
        if hasattr(self, "online_speed_var"):
            self.online_speed_var.set(f"{self.cheat_state.speed_multiplier:g}")

    def _coord_search_entries(self) -> list[CoordPreset]:
        if hasattr(self, "coord_search_var") and self.coord_search_var.get().strip():
            return list(self._coord_entries)
        group_name = (
            self.coord_group_var.get().strip()
            if hasattr(self, "coord_group_var")
            else ALL_GROUPS_LABEL
        )
        if group_name and group_name != ALL_GROUPS_LABEL:
            group = self._coord_groups_by_name.get(group_name)
            if group is not None:
                return list(group.items)
        return list(self._coord_entries)

    def _refresh_coord_presets(self) -> None:
        if not hasattr(self, "coord_preset_box"):
            return

        source_entries = self._coord_search_entries()
        self._current_coord_results = search_coord_presets(
            source_entries,
            self.coord_search_var.get() if hasattr(self, "coord_search_var") else "",
        )
        values = [entry.label for entry in self._current_coord_results]
        self.coord_preset_box.configure(values=values)
        if values:
            current = self.coord_preset_var.get().strip()
            if current not in values:
                self.coord_preset_var.set(values[0])
        else:
            self.coord_preset_var.set("")
        self._update_coord_preset_hint()

    def _selected_coord_preset(self) -> CoordPreset | None:
        if not hasattr(self, "coord_preset_box"):
            return None
        current_index = self.coord_preset_box.current()
        if 0 <= current_index < len(self._current_coord_results):
            return self._current_coord_results[current_index]
        current_label = self.coord_preset_var.get().strip()
        for entry in self._current_coord_results:
            if entry.label == current_label:
                return entry
        return self._current_coord_results[0] if self._current_coord_results else None

    def _update_coord_preset_hint(self) -> None:
        if not hasattr(self, "coord_preset_hint_label"):
            return
        entry = self._selected_coord_preset()
        if entry is None:
            self.coord_preset_hint_label.configure(
                text="当前分类下没有匹配点位；可以切分类或输入关键词搜索。"
            )
            return
        self.coord_preset_hint_label.configure(
            text=(
                f"{entry.label} -> X={entry.x:g}  Y={entry.y:g}  Z={entry.z:g}。"
                " 可直接传送，也可把它塞进路径列表。"
            )
        )

    def _load_selected_coord_preset(self) -> None:
        entry = self._selected_coord_preset()
        if entry is None:
            self._show_result("先从坐标库里选一个点位。", ok=False)
            return
        self._set_coord_fields(entry.x, entry.y, entry.z)
        self._update_coord_preset_hint()
        self._show_result(f"已载入 {entry.label} 坐标。", ok=True)

    def _teleport_selected_coord_preset(self) -> None:
        entry = self._selected_coord_preset()
        if entry is None:
            self._show_result("先从坐标库里选一个点位。", ok=False)
            return
        self._teleport_to_coords(entry.x, entry.y, entry.z, entry.label)

    def _append_selected_coord_preset_to_route(self) -> None:
        entry = self._selected_coord_preset()
        if entry is None:
            self._show_result("先从坐标库里选一个点位。", ok=False)
            return
        self._append_coords_to_route(entry.x, entry.y, entry.z, entry.label)

    def _add_selected_coord_preset_to_favorites(self) -> None:
        entry = self._selected_coord_preset()
        if entry is None:
            self._show_result("先从坐标库里选一个点位。", ok=False)
            return
        self._remember_value(self.settings.favorite_coord_labels, entry.label, limit=80)
        save_settings(self.settings)
        self._refresh_coord_favorites()
        self._show_result(f"已把 {entry.label} 加入收藏夹。", ok=True)

    def _selected_boss_point(self) -> BossTeleportPoint | None:
        if not hasattr(self, "boss_preset_var"):
            return None
        label = self.boss_preset_var.get().strip()
        if not label:
            return None
        return self._boss_point_by_label.get(label)

    def _boss_point_safe_z(self, point: BossTeleportPoint) -> float:
        status = self._read_bridge_status()
        if status.player_valid:
            return max(point.safe_z, status.position_z + 1500.0)
        return point.safe_z

    def _update_boss_preset_hint(self) -> None:
        if not hasattr(self, "boss_preset_hint_label"):
            return
        point = self._selected_boss_point()
        if point is None:
            self.boss_preset_hint_label.configure(
                text="选择一个首领后，可直接把坐标填入下方传送栏，或一键传送到首领上空。"
            )
            return

        safe_z = self._boss_point_safe_z(point)
        self.boss_preset_hint_label.configure(
            text=(
                f"{point.label} 预计传送坐标：X={point.world_x}  Y={point.world_y}  Z={safe_z:.0f}。"
                " 默认会把你送到目标上空，减少卡进地形的概率。"
            )
        )

    def _load_selected_boss_preset(self) -> None:
        point = self._selected_boss_point()
        if point is None:
            self._show_result("先选一个首领。", ok=False)
            return

        safe_z = self._boss_point_safe_z(point)
        self._set_coord_fields(float(point.world_x), float(point.world_y), float(safe_z))
        self._update_boss_preset_hint()
        self._show_result(f"已载入 {point.label} 坐标。", ok=True)

    def _teleport_selected_boss_preset(self) -> None:
        point = self._selected_boss_point()
        if point is None:
            self._show_result("先选一个首领。", ok=False)
            return

        safe_z = self._boss_point_safe_z(point)
        self._teleport_to_coords(
            float(point.world_x),
            float(point.world_y),
            float(safe_z),
            point.label,
        )

    def _add_selected_boss_preset_to_favorites(self) -> None:
        point = self._selected_boss_point()
        if point is None:
            self._show_result("先选一个首领。", ok=False)
            return
        self._remember_value(self.settings.favorite_coord_labels, point.label, limit=80)
        save_settings(self.settings)
        self._refresh_coord_favorites()
        self._show_result(f"已把 {point.label} 加入收藏夹。", ok=True)

    def _load_selected_coord_favorite(self) -> None:
        entry = self._selected_coord_favorite()
        if entry is None:
            self._show_result("先选一个收藏点位。", ok=False)
            return
        label, x, y, z = entry
        self._set_coord_fields(x, y, z)
        self._update_coord_favorite_hint()
        self._show_result(f"已载入 {label} 坐标。", ok=True)

    def _teleport_selected_coord_favorite(self) -> None:
        entry = self._selected_coord_favorite()
        if entry is None:
            self._show_result("先选一个收藏点位。", ok=False)
            return
        label, x, y, z = entry
        self._teleport_to_coords(x, y, z, label)

    def _append_selected_coord_favorite_to_route(self) -> None:
        entry = self._selected_coord_favorite()
        if entry is None:
            self._show_result("先选一个收藏点位。", ok=False)
            return
        label, x, y, z = entry
        self._append_coords_to_route(x, y, z, label)

    def _remove_selected_coord_favorite(self) -> None:
        label = self.coord_favorite_var.get().strip() if hasattr(self, "coord_favorite_var") else ""
        if not label:
            self._show_result("先选一个收藏点位。", ok=False)
            return
        if label not in self.settings.favorite_coord_labels:
            self._show_result("这个点位不在收藏夹里。", ok=False)
            return
        self.settings.favorite_coord_labels.remove(label)
        save_settings(self.settings)
        self._refresh_coord_favorites()
        self._show_result(f"已移除收藏：{label}。", ok=True)

    def _refresh_player_bridge_status(self) -> None:
        if not hasattr(self, "player_bridge_status_label"):
            return

        status = self._read_bridge_status()
        bridge_version = status.bridge_version or "未知版本"
        hidden_mode = self._hidden_command_dispatch_mode()
        if self.report.trainer_bridge_target is None:
            text = "未找到 UE4SS Mods 目录，无法部署玩家增强模块。"
            style = "Bad.TLabel"
        elif not self.report.client_cheat_commands_present:
            text = "还没检测到聊天命令模组，先把 UE4SS / CCC 装好。"
            style = "Bad.TLabel"
        elif not self.report.trainer_bridge_deployed or not self.report.trainer_bridge_enabled:
            text = "玩家增强模块还没部署完成，点右侧按钮即可自动修复。"
            style = "Warn.TLabel"
        elif status.player_valid and hidden_mode == "bridge":
            text = (
                f"玩家增强模块已就绪（bridge {bridge_version}，原生隐藏指令可用）；"
                "飞行/坐标/物品/帕鲁等主流程都可直接使用。"
            )
            style = "Good.TLabel"
        elif status.player_valid and hidden_mode == "fallback":
            text = (
                f"玩家增强模块当前走兼容模式（bridge {bridge_version}）；"
                "飞行/坐标走 bridge，物品等指令按参考版静默发送。"
            )
            style = "Good.TLabel"
        elif status.player_valid:
            text = (
                f"玩家增强模块已连接（bridge {bridge_version}），"
                "但隐藏指令链路未就绪；当前可先用飞行/坐标。"
            )
            style = "Warn.TLabel"
        else:
            text = (
                f"玩家增强模块已写入（bridge {bridge_version}），"
                "但当前这局还没载入；请先进世界后再刷新状态。"
            )
            style = "Warn.TLabel"

        self.player_bridge_status_label.configure(text=text, style=style)

    def _ensure_player_bridge(self) -> tuple[bool, str]:
        if self.report.trainer_bridge_target is None:
            return False, "未找到 UE4SS Mods 目录。"
        if self._bridge_runtime_ready():
            return True, "玩家增强模块已经就绪。"

        ok, message = deploy_bridge(self.report)
        self._refresh_status()
        return ok, message

    def _collect_player_cheat_state(self) -> CheatState | None:
        return self._collect_player_cheat_state_impl()

    def _write_bridge_request(self, action: str, **payload: object) -> tuple[bool, str]:
        ok, message = self._ensure_player_bridge()
        if not ok:
            return False, message
        if not self._bridge_runtime_ready():
            return (
                False,
                "当前这局还没载入玩家增强模块；请完全退出并重开游戏后，再使用这一键玩家功能。",
            )

        path = self._bridge_request_path()
        if path is None:
            return False, "还没找到增强模块的 request.json 目录。"

        return write_request(
            path,
            action=action,
            request_id=self._next_bridge_request_id(),
            **payload,
        )

    def _write_bridge_teleport_request(
        self, x: float, y: float, z: float
    ) -> tuple[bool, str]:
        return self._write_bridge_request(
            "teleport",
            x=x,
            y=y,
            z=z,
        )

    def _write_bridge_fly_request(self, enabled: bool) -> tuple[bool, str]:
        return self._write_bridge_request("set_fly", enabled=enabled)

    def _bridge_supports_hidden_commands(self) -> bool:
        if not self._bridge_runtime_ready():
            return False
        status = self._read_bridge_status()
        version = _parse_version_tuple(status.bridge_version)
        return version >= BRIDGE_HIDDEN_COMMANDS_MIN_VERSION and status.hidden_registry_ready

    def _bridge_can_hide_chat_commands(self) -> bool:
        if not self._bridge_runtime_ready():
            return False
        return self._read_bridge_status().chat_suppression_ready

    def _hidden_command_dispatch_mode(self) -> str:
        if self._bridge_supports_hidden_commands():
            return "bridge"
        if self._bridge_can_hide_chat_commands():
            return "fallback"
        return "none"

    def _write_bridge_hidden_commands(self, commands: list[str]) -> tuple[bool, str]:
        normalized = [
            cmd.sanitize_command(command)
            for command in commands
            if command and command.strip()
        ]
        if not normalized:
            return False, "没有可发送的隐藏命令。"
        return self._write_bridge_request(
            "run_hidden_commands",
            commands_text="\n".join(normalized),
        )

    def _dispatch_hidden_commands(self, commands: list[str], *, label: str) -> None:
        normalized = [
            cmd.sanitize_command(command)
            for command in commands
            if command and command.strip()
        ]
        if not normalized:
            return

        dispatch_mode = self._hidden_command_dispatch_mode()
        if dispatch_mode == "bridge":
            ok, message = self._write_bridge_hidden_commands(normalized)
            if ok:
                self._show_result(f"已通过 bridge 原生模式执行：{label}", ok=True)
            else:
                self._show_result(f"{label} 发送失败：{message}", ok=False)
            return

        if dispatch_mode == "fallback":
            results = game_control.send_chat_commands(normalized)
            if results and all(result.ok for result in results):
                self._show_result(f"已按参考版兼容模式执行：{label}", ok=True)
            else:
                reason = results[-1].message if results else "没有发送任何命令。"
                self._show_result(f"{label} 兼容模式发送失败：{reason}", ok=False)
            return

        if self._bridge_runtime_ready():
            version = self._read_bridge_status().bridge_version or "未知版本"
            self._show_result(
                (
                    f"{label} 当前不能执行：桥接模块版本是 {version}，"
                    "原生隐藏指令不可用，参考版兼容模式也不可用。"
                ),
                ok=False,
            )
            return

        self._show_result(
            f"{label} 需要先让增强模块载入当前游戏会话后再使用；bridge 与兼容链路都未就绪。",
            ok=False,
        )

    def _collect_player_cheat_state_impl(self) -> CheatState | None:
        try:
            speed = float(self.bridge_speed_var.get().strip())
            jump = float(self.bridge_jump_var.get().strip())
        except ValueError:
            self._show_result("移速倍率和跳跃倍率必须是数字。", ok=False)
            return None

        speed = max(0.1, min(10.0, speed))
        jump = max(0.1, min(10.0, jump))
        self.bridge_speed_var.set(f"{speed:g}")
        self.bridge_jump_var.set(f"{jump:g}")

        return CheatState(
            godmode=bool(self.bridge_godmode_var.get()),
            inf_stamina=bool(self.bridge_stamina_var.get()),
            weight_zero=bool(self.bridge_weight_var.get()),
            speed_multiplier=speed,
            jump_multiplier=jump,
        )

    def _apply_player_cheats(self) -> None:
        state = self._collect_player_cheat_state()
        if state is None:
            return

        ok, message = self._ensure_player_bridge()
        if not ok:
            self._show_result(message, ok=False)
            return

        path = self._bridge_toggles_path()
        if path is None:
            self._show_result("还没找到增强模块的 toggles.json 目录。", ok=False)
            return

        ok, message = write_toggles(path, state)
        if not ok:
            self._show_result(message, ok=False)
            return

        self.cheat_state = state
        self._sync_player_cheat_controls()
        self._refresh_player_bridge_status()
        if self._bridge_runtime_ready():
            self._show_result("玩家增强状态已写入并等待桥接脚本持续应用。", ok=True)
        else:
            self._show_result(
                "玩家增强状态已写入；当前这局还没载入增强模块，重启游戏后会自动生效。",
                ok=True,
            )

    def _reset_player_multipliers(self) -> None:
        if hasattr(self, "bridge_speed_var"):
            self.bridge_speed_var.set("1")
        if hasattr(self, "bridge_jump_var"):
            self.bridge_jump_var.set("1")
        self._apply_player_cheats()

    def _on_deploy_bridge(self) -> None:
        ok, message = deploy_bridge(self.report)
        self._refresh_status()
        if ok:
            self._show_result(message, ok=True)
        else:
            self._show_result(message, ok=False)

    def _build_items_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=16)
        self.notebook.add(tab, text="*添加物品")

        ttk.Label(tab, text="*添加物品", style="SubHeader.TLabel").pack(anchor="w")
        preset_grid = ttk.Frame(tab)
        preset_grid.pack(fill="x", pady=(8, 16))
        for index, preset in enumerate(cmd.QUICK_PRESETS):
            ttk.Button(
                preset_grid,
                text=f"🎁 {preset.title}",
                style="Big.TButton",
                command=lambda p=preset: self._on_give_preset(p),
            ).grid(row=index // 3, column=index % 3, padx=6, pady=6, sticky="ew")
        for col in range(3):
            preset_grid.columnconfigure(col, weight=1)

        ttk.Separator(tab).pack(fill="x", pady=(4, 10))

        shortcuts = ttk.LabelFrame(tab, text="傻瓜式点选", padding=(12, 8))
        shortcuts.pack(fill="x", pady=(0, 10))

        count_row = ttk.Frame(shortcuts)
        count_row.pack(fill="x", pady=(0, 6))
        ttk.Label(count_row, text="数量快捷:").pack(side="left")
        self.item_count_var = tk.StringVar(value=str(self.settings.custom_item_count))
        for amount in (1, 10, 100, 999):
            ttk.Button(
                count_row,
                text=str(amount),
                style="Quiet.TButton",
                command=lambda value=amount: self._set_numeric_var(self.item_count_var, value),
            ).pack(side="left", padx=(6, 0))

        select_row = ttk.Frame(shortcuts)
        select_row.pack(fill="x", pady=(0, 6))
        ttk.Label(select_row, text="分类:").pack(side="left")
        self.item_quick_group_var = tk.StringVar(value=next(iter(self._item_guide_groups), ""))
        self.item_quick_group_box = ttk.Combobox(
            select_row,
            textvariable=self.item_quick_group_var,
            values=list(self._item_guide_groups),
            state="readonly",
            width=18,
        )
        self.item_quick_group_box.pack(side="left", padx=(6, 12))
        self.item_quick_group_box.bind(
            "<<ComboboxSelected>>",
            lambda _event: self._refresh_item_quick_choices(),
        )
        ttk.Label(select_row, text="常用项:").pack(side="left")
        self.item_quick_choice_var = tk.StringVar()
        self.item_quick_choice_box = ttk.Combobox(
            select_row,
            textvariable=self.item_quick_choice_var,
            values=[],
            state="readonly",
            width=34,
        )
        self.item_quick_choice_box.pack(side="left", padx=(6, 0), fill="x", expand=True)

        action_row = ttk.Frame(shortcuts)
        action_row.pack(fill="x", pady=(0, 8))
        ttk.Button(
            action_row,
            text="🎁 直接给我",
            style="Big.TButton",
            command=self._give_selected_item_quick,
        ).pack(side="left", padx=(0, 6))
        ttk.Button(
            action_row,
            text="⭐ 收藏当前",
            style="Quiet.TButton",
            command=self._add_selected_item_quick_favorite,
        ).pack(side="left")

        full_row = ttk.Frame(shortcuts)
        full_row.pack(fill="x", pady=(0, 6))
        ttk.Label(full_row, text="完整目录:").pack(side="left")
        self.item_full_var = tk.StringVar()
        self.item_full_box = ttk.Combobox(
            full_row,
            textvariable=self.item_full_var,
            values=[],
            state="readonly",
            width=42,
        )
        self.item_full_box.pack(side="left", padx=(6, 10), fill="x", expand=True)
        ttk.Button(
            full_row,
            text="直接给我",
            style="Quiet.TButton",
            command=self._give_selected_item_full,
        ).pack(side="left", padx=(0, 6))
        ttk.Button(
            full_row,
            text="收藏当前",
            style="Quiet.TButton",
            command=self._add_selected_item_full_favorite,
        ).pack(side="left")

        recent_row = ttk.Frame(shortcuts)
        recent_row.pack(fill="x", pady=(0, 6))
        ttk.Label(recent_row, text="最近给予:").pack(side="left")
        self.item_recent_var = tk.StringVar()
        self.item_recent_box = ttk.Combobox(
            recent_row,
            textvariable=self.item_recent_var,
            values=[],
            state="readonly",
            width=42,
        )
        self.item_recent_box.pack(side="left", padx=(6, 10), fill="x", expand=True)
        ttk.Button(
            recent_row,
            text="直接给予",
            style="Quiet.TButton",
            command=self._give_recent_item,
        ).pack(side="left")

        favorite_row = ttk.Frame(shortcuts)
        favorite_row.pack(fill="x")
        ttk.Label(favorite_row, text="收藏物品:").pack(side="left")
        self.item_favorite_var = tk.StringVar()
        self.item_favorite_box = ttk.Combobox(
            favorite_row,
            textvariable=self.item_favorite_var,
            values=[],
            state="readonly",
            width=42,
        )
        self.item_favorite_box.pack(side="left", padx=(6, 10), fill="x", expand=True)
        ttk.Button(
            favorite_row,
            text="直接给予",
            style="Quiet.TButton",
            command=self._give_favorite_item,
        ).pack(side="left", padx=(0, 6))
        ttk.Button(
            favorite_row,
            text="移除收藏",
            style="Quiet.TButton",
            command=self._remove_selected_item_favorite,
        ).pack(side="left")

        ttk.Separator(tab).pack(fill="x", pady=(4, 10))

        ttk.Label(tab, text="备用搜索", style="SubHeader.TLabel").pack(anchor="w")

        search_row = ttk.Frame(tab)
        search_row.pack(fill="x")
        ttk.Label(search_row, text="关键字：").pack(side="left")
        self.item_search_var = tk.StringVar()
        self.item_search_var.trace_add("write", lambda *_: self._refresh_item_list())
        ttk.Entry(search_row, textvariable=self.item_search_var).pack(
            side="left", padx=(4, 8), fill="x", expand=True
        )
        ttk.Label(search_row, text="数量：").pack(side="left", padx=(10, 0))
        ttk.Entry(search_row, textvariable=self.item_count_var, width=6).pack(
            side="left", padx=(4, 0)
        )

        list_frame = ttk.Frame(tab)
        list_frame.pack(fill="both", expand=True, pady=(8, 8))
        self.item_listbox = tk.Listbox(list_frame, height=10, activestyle="dotbox")
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.item_listbox.yview)
        self.item_listbox.configure(yscrollcommand=scrollbar.set)
        self.item_listbox.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.item_listbox.bind("<Double-Button-1>", lambda _event: self._on_give_selected_item())

        action_row = ttk.Frame(tab)
        action_row.pack(fill="x")
        ttk.Button(
            action_row,
            text="💾 给自己选中物品",
            style="Big.TButton",
            command=self._on_give_selected_item,
        ).pack(side="left", padx=(0, 6))
        ttk.Button(
            action_row,
            text="⭐ 收藏选中物品",
            style="Quiet.TButton",
            command=self._add_selected_item_favorite,
        ).pack(side="left")

        self._refresh_item_shortcuts()
        self._refresh_item_quick_choices()
        self._refresh_item_full_choices()
        self._refresh_item_list()

    def _build_pals_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=16)
        self.notebook.add(tab, text="*添加帕鲁")

        ttk.Label(tab, text="帕鲁生成（仅房主/单机有效）", style="SubHeader.TLabel").pack(anchor="w")

        shortcuts = ttk.LabelFrame(tab, text="傻瓜式点选", padding=(12, 8))
        shortcuts.pack(fill="x", pady=(0, 10))

        count_row = ttk.Frame(shortcuts)
        count_row.pack(fill="x", pady=(0, 6))
        ttk.Label(count_row, text="数量快捷:").pack(side="left")
        self.pal_count_var = tk.StringVar(value=str(self.settings.custom_pal_count))
        for amount in (1, 5, 10, 20):
            ttk.Button(
                count_row,
                text=str(amount),
                style="Quiet.TButton",
                command=lambda value=amount: self._set_numeric_var(self.pal_count_var, value),
            ).pack(side="left", padx=(6, 0))

        select_row = ttk.Frame(shortcuts)
        select_row.pack(fill="x", pady=(0, 6))
        ttk.Label(select_row, text="分类:").pack(side="left")
        self.pal_quick_group_var = tk.StringVar(value=next(iter(self._pal_guide_groups), ""))
        self.pal_quick_group_box = ttk.Combobox(
            select_row,
            textvariable=self.pal_quick_group_var,
            values=list(self._pal_guide_groups),
            state="readonly",
            width=18,
        )
        self.pal_quick_group_box.pack(side="left", padx=(6, 12))
        self.pal_quick_group_box.bind(
            "<<ComboboxSelected>>",
            lambda _event: self._refresh_pal_quick_choices(),
        )
        ttk.Label(select_row, text="推荐项:").pack(side="left")
        self.pal_quick_choice_var = tk.StringVar()
        self.pal_quick_choice_box = ttk.Combobox(
            select_row,
            textvariable=self.pal_quick_choice_var,
            values=[],
            state="readonly",
            width=34,
        )
        self.pal_quick_choice_box.pack(side="left", padx=(6, 0), fill="x", expand=True)

        action_row = ttk.Frame(shortcuts)
        action_row.pack(fill="x", pady=(0, 8))
        ttk.Button(
            action_row,
            text="🐉 直接生成",
            style="Big.TButton",
            command=self._spawn_selected_pal_quick,
        ).pack(side="left", padx=(0, 6))
        ttk.Button(
            action_row,
            text="⭐ 收藏当前",
            style="Quiet.TButton",
            command=self._add_selected_pal_quick_favorite,
        ).pack(side="left")

        full_row = ttk.Frame(shortcuts)
        full_row.pack(fill="x", pady=(0, 6))
        ttk.Label(full_row, text="完整目录:").pack(side="left")
        self.pal_full_var = tk.StringVar()
        self.pal_full_box = ttk.Combobox(
            full_row,
            textvariable=self.pal_full_var,
            values=[],
            state="readonly",
            width=42,
        )
        self.pal_full_box.pack(side="left", padx=(6, 10), fill="x", expand=True)
        ttk.Button(
            full_row,
            text="直接生成",
            style="Quiet.TButton",
            command=self._spawn_selected_pal_full,
        ).pack(side="left", padx=(0, 6))
        ttk.Button(
            full_row,
            text="收藏当前",
            style="Quiet.TButton",
            command=self._add_selected_pal_full_favorite,
        ).pack(side="left")

        recent_row = ttk.Frame(shortcuts)
        recent_row.pack(fill="x", pady=(0, 6))
        ttk.Label(recent_row, text="最近生成:").pack(side="left")
        self.pal_recent_var = tk.StringVar()
        self.pal_recent_box = ttk.Combobox(
            recent_row,
            textvariable=self.pal_recent_var,
            values=[],
            state="readonly",
            width=42,
        )
        self.pal_recent_box.pack(side="left", padx=(6, 10), fill="x", expand=True)
        ttk.Button(
            recent_row,
            text="直接生成",
            style="Quiet.TButton",
            command=self._spawn_recent_pal,
        ).pack(side="left")

        favorite_row = ttk.Frame(shortcuts)
        favorite_row.pack(fill="x")
        ttk.Label(favorite_row, text="收藏帕鲁:").pack(side="left")
        self.pal_favorite_var = tk.StringVar()
        self.pal_favorite_box = ttk.Combobox(
            favorite_row,
            textvariable=self.pal_favorite_var,
            values=[],
            state="readonly",
            width=42,
        )
        self.pal_favorite_box.pack(side="left", padx=(6, 10), fill="x", expand=True)
        ttk.Button(
            favorite_row,
            text="直接生成",
            style="Quiet.TButton",
            command=self._spawn_favorite_pal,
        ).pack(side="left", padx=(0, 6))
        ttk.Button(
            favorite_row,
            text="移除收藏",
            style="Quiet.TButton",
            command=self._remove_selected_pal_favorite,
        ).pack(side="left")

        ttk.Separator(tab).pack(fill="x", pady=(4, 10))
        ttk.Label(tab, text="备用搜索", style="SubHeader.TLabel").pack(anchor="w")

        search_row = ttk.Frame(tab)
        search_row.pack(fill="x")
        ttk.Label(search_row, text="关键字：").pack(side="left")
        self.pal_search_var = tk.StringVar()
        self.pal_search_var.trace_add("write", lambda *_: self._refresh_pal_list())
        ttk.Entry(search_row, textvariable=self.pal_search_var).pack(
            side="left", padx=(4, 8), fill="x", expand=True
        )
        ttk.Label(search_row, text="数量：").pack(side="left", padx=(10, 0))
        ttk.Entry(search_row, textvariable=self.pal_count_var, width=6).pack(
            side="left", padx=(4, 0)
        )

        list_frame = ttk.Frame(tab)
        list_frame.pack(fill="both", expand=True, pady=(8, 8))
        self.pal_listbox = tk.Listbox(list_frame, height=12, activestyle="dotbox")
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.pal_listbox.yview)
        self.pal_listbox.configure(yscrollcommand=scrollbar.set)
        self.pal_listbox.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.pal_listbox.bind("<Double-Button-1>", lambda _event: self._on_spawn_selected_pal())

        action_row = ttk.Frame(tab)
        action_row.pack(fill="x")
        ttk.Button(
            action_row,
            text="🐉 生成选中帕鲁",
            style="Big.TButton",
            command=self._on_spawn_selected_pal,
        ).pack(side="left", padx=(0, 6))
        ttk.Button(
            action_row,
            text="⭐ 收藏选中帕鲁",
            style="Quiet.TButton",
            command=self._add_selected_pal_favorite,
        ).pack(side="left")

        self._refresh_pal_shortcuts()
        self._refresh_pal_quick_choices()
        self._refresh_pal_full_choices()
        self._refresh_pal_list()

    def _build_tech_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=16)
        self.notebook.add(tab, text="制作和建造")

        ttk.Label(tab, text="制作和建造 / 科技解锁", style="SubHeader.TLabel").pack(anchor="w")

        big_row = ttk.Frame(tab)
        big_row.pack(fill="x", pady=(8, 14))
        ttk.Button(
            big_row,
            text="🔓 解锁全部科技",
            style="Big.TButton",
            command=self._on_unlock_all_tech,
        ).pack(side="left", padx=4)
        ttk.Button(
            big_row,
            text="🗺 解锁全部传送点",
            style="Big.TButton",
            command=self._on_unlock_fast_travel,
        ).pack(side="left", padx=4)

        ttk.Separator(tab).pack(fill="x", pady=(4, 10))
        guide = ttk.LabelFrame(tab, text="傻瓜式点选", padding=(12, 8))
        guide.pack(fill="x", pady=(0, 10))

        select_row = ttk.Frame(guide)
        select_row.pack(fill="x", pady=(0, 6))
        ttk.Label(select_row, text="分类:").pack(side="left")
        self.tech_quick_group_var = tk.StringVar(value=next(iter(self._tech_guide_groups), ""))
        self.tech_quick_group_box = ttk.Combobox(
            select_row,
            textvariable=self.tech_quick_group_var,
            values=list(self._tech_guide_groups),
            state="readonly",
            width=18,
        )
        self.tech_quick_group_box.pack(side="left", padx=(6, 12))
        self.tech_quick_group_box.bind(
            "<<ComboboxSelected>>",
            lambda _event: self._refresh_tech_quick_choices(),
        )
        ttk.Label(select_row, text="推荐项:").pack(side="left")
        self.tech_quick_choice_var = tk.StringVar()
        self.tech_quick_choice_box = ttk.Combobox(
            select_row,
            textvariable=self.tech_quick_choice_var,
            values=[],
            state="readonly",
            width=36,
        )
        self.tech_quick_choice_box.pack(side="left", padx=(6, 0), fill="x", expand=True)

        action_row = ttk.Frame(guide)
        action_row.pack(fill="x")
        ttk.Button(
            action_row,
            text="🔓 解锁当前",
            style="Big.TButton",
            command=self._unlock_selected_tech_quick,
        ).pack(side="left", padx=(0, 6))
        ttk.Button(
            action_row,
            text="📚 解锁整组",
            style="Quiet.TButton",
            command=self._unlock_selected_tech_group,
        ).pack(side="left")

        full_row = ttk.Frame(guide)
        full_row.pack(fill="x", pady=(8, 0))
        ttk.Label(full_row, text="完整目录:").pack(side="left")
        self.tech_full_var = tk.StringVar()
        self.tech_full_box = ttk.Combobox(
            full_row,
            textvariable=self.tech_full_var,
            values=[],
            state="readonly",
            width=42,
        )
        self.tech_full_box.pack(side="left", padx=(6, 10), fill="x", expand=True)
        ttk.Button(
            full_row,
            text="解锁当前",
            style="Quiet.TButton",
            command=self._unlock_selected_tech_full,
        ).pack(side="left")

        ttk.Separator(tab).pack(fill="x", pady=(4, 10))
        ttk.Label(tab, text="备用搜索", style="SubHeader.TLabel").pack(anchor="w")

        search_row = ttk.Frame(tab)
        search_row.pack(fill="x")
        ttk.Label(search_row, text="关键字：").pack(side="left")
        self.tech_search_var = tk.StringVar()
        self.tech_search_var.trace_add("write", lambda *_: self._refresh_tech_list())
        ttk.Entry(search_row, textvariable=self.tech_search_var).pack(
            side="left", padx=(4, 8), fill="x", expand=True
        )

        list_frame = ttk.Frame(tab)
        list_frame.pack(fill="both", expand=True, pady=(8, 8))
        self.tech_listbox = tk.Listbox(list_frame, height=12, activestyle="dotbox")
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.tech_listbox.yview)
        self.tech_listbox.configure(yscrollcommand=scrollbar.set)
        self.tech_listbox.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.tech_listbox.bind(
            "<Double-Button-1>", lambda _event: self._on_unlock_selected_tech()
        )

        action_row = ttk.Frame(tab)
        action_row.pack(fill="x")
        ttk.Button(
            action_row,
            text="🔓 解锁选中科技",
            style="Big.TButton",
            command=self._on_unlock_selected_tech,
        ).pack(side="left")

        self._refresh_tech_quick_choices()
        self._refresh_tech_full_choices()
        self._refresh_tech_list()

    def _build_world_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=16)
        self.notebook.add(tab, text="世界")

        ttk.Label(tab, text="世界时间", style="SubHeader.TLabel").pack(anchor="w")
        ttk.Label(
            tab,
            text="拖动滑块选小时数，再点「设置时间」。0=午夜，6=清晨，12=正午，18=黄昏。",
            style="Status.TLabel",
        ).pack(anchor="w", pady=(2, 8))

        slider_row = ttk.Frame(tab)
        slider_row.pack(fill="x", pady=(4, 14))
        self.world_time_var = tk.IntVar(value=12)
        ttk.Scale(
            slider_row,
            from_=0,
            to=23,
            orient="horizontal",
            variable=self.world_time_var,
            command=lambda _value: self._refresh_time_label(
                self.world_time_var, self.world_time_label
            ),
        ).pack(side="left", fill="x", expand=True)
        self.world_time_label = ttk.Label(slider_row, text="12 时", width=8, anchor="e")
        self.world_time_label.pack(side="left", padx=(10, 0))
        ttk.Button(
            slider_row,
            text="设置时间",
            style="Big.TButton",
            command=lambda: self._on_set_time(self.world_time_var.get()),
        ).pack(side="left", padx=(10, 0))

        quick = ttk.Frame(tab)
        quick.pack(fill="x", pady=(4, 0))
        for label, hour in (("🌅 清晨 6:00", 6), ("☀️ 正午 12:00", 12), ("🌆 黄昏 18:00", 18), ("🌙 午夜 0:00", 0)):
            ttk.Button(
                quick,
                text=label,
                style="Big.TButton",
                command=lambda h=hour: self._on_set_time(h),
            ).pack(side="left", padx=4)

    def _build_enhance_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=16)
        self.notebook.add(tab, text="高级")

        ttk.Label(
            tab,
            text="高级/调试（直接内存方式，无需安装任何 mod）",
            style="SubHeader.TLabel",
        ).pack(anchor="w")
        ttk.Label(
            tab,
            text=(
                "原理：进程连接到正在运行的 Palworld-Win64-Shipping.exe，"
                "先用「数值搜索」定位你当前的 HP / 体力 / 移动速度 / 跳跃速度，"
                "锁定后勾选开关，后台每 50 ms 把该内存字段写回你设定的值。"
                "不注入任何 DLL，不改动游戏文件，关掉修改器游戏就恢复正常。"
            ),
            justify="left",
            style="Status.TLabel",
            wraplength=860,
        ).pack(anchor="w", pady=(2, 10))

        # ---- Attach row ----
        attach_frame = ttk.LabelFrame(tab, text="游戏连接", padding=(12, 8))
        attach_frame.pack(fill="x", pady=(2, 10))

        self.mem_attach_label = ttk.Label(
            attach_frame, text="未连接。", style="Warn.TLabel"
        )
        self.mem_attach_label.pack(side="left")

        ttk.Button(
            attach_frame,
            text="🔌 断开",
            style="Quiet.TButton",
            command=self._on_mem_detach,
        ).pack(side="right", padx=(4, 0))
        ttk.Button(
            attach_frame,
            text="🎮 连接游戏",
            style="Big.TButton",
            command=self._on_mem_attach,
        ).pack(side="right", padx=(4, 0))

        # ---- Slots ----
        slots_frame = ttk.LabelFrame(tab, text="字段校准与锁定", padding=(12, 10))
        slots_frame.pack(fill="both", expand=True, pady=(0, 8))

        ttk.Label(
            slots_frame,
            text=(
                "流程：① 进游戏 → ② 在下方填入当前真实数值 → ③ 点「首次搜索」"
                "（约 40 秒）→ ④ 在游戏里把该数值变一下（受伤、跑动、跳跃）→ "
                "⑤ 填新值点「缩小范围」→ ⑥ 剩 1 个地址后点「锁定」。"
                "已锁定后勾选右侧开关即可把值冻结成目标值。"
            ),
            justify="left",
            style="Status.TLabel",
            wraplength=840,
        ).grid(row=0, column=0, columnspan=6, sticky="w", pady=(0, 8))

        headers = ("字段", "当前扫描值", "操作", "候选数", "冻结目标", "开关")
        for col, text in enumerate(headers):
            ttk.Label(slots_frame, text=text, style="SubHeader.TLabel").grid(
                row=1, column=col, padx=4, pady=(0, 4), sticky="w"
            )

        for row, slot in enumerate(CORE_SLOTS, start=2):
            self._build_mem_slot_row(slots_frame, row, slot)

        slots_frame.columnconfigure(1, weight=1)

        # ---- One-click presets ----
        presets_frame = ttk.LabelFrame(
            tab, text="一键开挂（需要先完成上方四个字段的锁定）", padding=(12, 8)
        )
        presets_frame.pack(fill="x", pady=(0, 8))
        preset_row = ttk.Frame(presets_frame)
        preset_row.pack(fill="x")
        preset_buttons: list[tuple[str, Callable[[], None]]] = [
            ("🛡 无敌", lambda: self._apply_mem_preset({"hp": 999_999.0}, "无敌")),
            ("⚡ 无限体力", lambda: self._apply_mem_preset({"sp": 999_999.0}, "无限体力")),
            (
                "🏃 超级移速",
                lambda: self._apply_mem_preset({"walk_speed": 3000.0}, "超级移速"),
            ),
            (
                "🦘 超级跳跃",
                lambda: self._apply_mem_preset({"jump_z": 3000.0}, "超级跳跃"),
            ),
            (
                "👼 神之模式 (HP+SP+移速+跳跃)",
                lambda: self._apply_mem_preset(
                    {
                        "hp": 999_999.0,
                        "sp": 999_999.0,
                        "walk_speed": 3000.0,
                        "jump_z": 3000.0,
                    },
                    "神之模式",
                ),
            ),
            ("🛑 全部关闭", self._mem_preset_stop_all),
        ]
        for index, (label, callback) in enumerate(preset_buttons):
            ttk.Button(
                preset_row, text=label, style="Big.TButton", command=callback
            ).grid(row=index // 3, column=index % 3, padx=4, pady=4, sticky="ew")
        for col in range(3):
            preset_row.columnconfigure(col, weight=1)

        # ---- Custom slots (user-defined fields) ----
        custom_outer = ttk.LabelFrame(
            tab,
            text="自定义字段（负重 / 饥饿 / 耐久 / 弹药 / …）",
            padding=(12, 8),
        )
        custom_outer.pack(fill="both", expand=True, pady=(0, 8))

        header_row = ttk.Frame(custom_outer)
        header_row.pack(fill="x", pady=(0, 6))
        ttk.Label(
            header_row,
            text=(
                "任何游戏里看得到的数字（负重、饥饿度、耐久、弹药数、氧气、心情…）"
                "都可以用这里添加一行，流程和上面四个字段完全一样。"
            ),
            justify="left",
            style="Status.TLabel",
            wraplength=720,
        ).pack(side="left", fill="x", expand=True)
        ttk.Button(
            header_row,
            text="➕ 添加字段",
            style="Big.TButton",
            command=self._on_add_custom_slot,
        ).pack(side="right")

        # Template quick-add row — click any preset to create the slot
        # with the label pre-filled. User still has to scan/lock manually.
        template_row = ttk.Frame(custom_outer)
        template_row.pack(fill="x", pady=(0, 6))
        ttk.Label(
            template_row,
            text="常用字段模板（点一下创建对应槽位）：",
            style="Status.TLabel",
        ).pack(anchor="w")
        template_buttons = ttk.Frame(template_row)
        template_buttons.pack(fill="x", pady=(2, 0))
        columns = 5
        for idx, tpl in enumerate(CUSTOM_SLOT_TEMPLATES):
            ttk.Button(
                template_buttons,
                text=f"➕ {tpl.label}",
                style="Quiet.TButton",
                command=lambda t=tpl: self._on_add_custom_slot_from_template(t),
            ).grid(row=idx // columns, column=idx % columns, padx=3, pady=2, sticky="ew")
        for col in range(columns):
            template_buttons.columnconfigure(col, weight=1)

        self._custom_slots_container = ttk.Frame(custom_outer)
        self._custom_slots_container.pack(fill="both", expand=True)
        self._custom_empty_hint = ttk.Label(
            self._custom_slots_container,
            text="（还没添加任何自定义字段。点右上「➕ 添加字段」开始。）",
            style="Status.TLabel",
        )
        self._custom_empty_hint.pack(anchor="w", pady=(4, 0))

        # ---- Status row ----
        self.mem_status_label = ttk.Label(tab, text="", style="Status.TLabel")
        self.mem_status_label.pack(anchor="w", pady=(4, 0))

    def _build_mem_slot_row(self, parent: ttk.Frame, row: int, slot: str) -> None:
        ttk.Label(parent, text=SLOT_LABELS_CN[slot]).grid(
            row=row, column=0, sticky="w", padx=4, pady=4
        )

        scan_var = tk.StringVar(value="")
        self._mem_scan_entries[slot] = scan_var
        ttk.Entry(parent, textvariable=scan_var, width=14).grid(
            row=row, column=1, sticky="w", padx=4, pady=4
        )

        btns = ttk.Frame(parent)
        btns.grid(row=row, column=2, sticky="w", padx=4, pady=4)
        ttk.Button(
            btns,
            text="首次搜索",
            style="Quiet.TButton",
            command=lambda s=slot: self._on_mem_scan(s, first=True),
        ).pack(side="left", padx=(0, 2))
        ttk.Button(
            btns,
            text="缩小范围",
            style="Quiet.TButton",
            command=lambda s=slot: self._on_mem_scan(s, first=False),
        ).pack(side="left", padx=(0, 2))
        ttk.Button(
            btns,
            text="锁定",
            style="Quiet.TButton",
            command=lambda s=slot: self._on_mem_lock(s),
        ).pack(side="left", padx=(0, 2))
        ttk.Button(
            btns,
            text="清除",
            style="Quiet.TButton",
            command=lambda s=slot: self._on_mem_clear(s),
        ).pack(side="left")

        count_label = ttk.Label(parent, text="—", style="Status.TLabel", width=14)
        count_label.grid(row=row, column=3, sticky="w", padx=4, pady=4)
        self._mem_slot_labels[slot] = count_label

        target_var = tk.StringVar(value=str(DEFAULT_FREEZE[slot]))
        self._mem_target_entries[slot] = target_var
        target_entry = ttk.Entry(parent, textvariable=target_var, width=10)
        target_entry.grid(row=row, column=4, sticky="w", padx=4, pady=4)
        target_entry.bind("<FocusOut>", lambda _event, s=slot: self._on_mem_target_changed(s))
        target_entry.bind("<Return>", lambda _event, s=slot: self._on_mem_target_changed(s))

        freeze_var = tk.BooleanVar(value=False)
        self._mem_slot_vars[slot] = freeze_var
        ttk.Checkbutton(
            parent,
            text="冻结",
            variable=freeze_var,
            command=lambda s=slot: self._on_mem_freeze_toggled(s),
        ).grid(row=row, column=5, sticky="w", padx=4, pady=4)

    def _build_chat_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=16)
        self.notebook.add(tab, text="命令")

        ttk.Label(
            tab,
            text="实验按钮（是否生效取决于当前模组版本）",
            style="SubHeader.TLabel",
        ).pack(anchor="w")
        ttk.Label(
            tab,
            text=(
                "点了没反应就说明当前版本不支持。"
                "或者直接用下方「自由命令」输入框。"
            ),
            justify="left",
            style="Status.TLabel",
            wraplength=860,
        ).pack(anchor="w", pady=(2, 8))

        grid = ttk.Frame(tab)
        grid.pack(fill="x", pady=(0, 14))
        columns = 3
        for idx, ec in enumerate(cmd.EXPERIMENTAL_COMMANDS):
            btn = ttk.Button(
                grid,
                text=ec.title,
                style="Big.TButton",
                command=lambda c=ec.command, t=ec.title: self._send_with_label(c, t),
            )
            btn.grid(row=idx // columns, column=idx % columns, padx=4, pady=4, sticky="ew")
            # Tooltip via hover text in the result bar
            btn.bind(
                "<Enter>",
                lambda _e, ec=ec: self._show_result(
                    f"{ec.title}：{ec.description}（命令：{ec.command}）",
                    ok=True,
                    pending=True,
                ),
            )
        for col in range(columns):
            grid.columnconfigure(col, weight=1)

        ttk.Separator(tab).pack(fill="x", pady=(4, 10))
        ttk.Label(tab, text="手动命令（可选）", style="SubHeader.TLabel").pack(anchor="w")
        ttk.Label(
            tab,
            text=(
                "这里给懂命令的人备用，不想碰可以不管。"
                "程序会自动补。按 Enter 或点「发送」即可。"
            ),
            justify="left",
            style="Status.TLabel",
            wraplength=860,
        ).pack(anchor="w", pady=(2, 8))

        entry_row = ttk.Frame(tab)
        entry_row.pack(fill="x", pady=(4, 4))
        ttk.Label(entry_row, text="命令：").pack(side="left")
        self.chat_freeform_var = tk.StringVar()
        entry = ttk.Entry(entry_row, textvariable=self.chat_freeform_var)
        entry.pack(side="left", fill="x", expand=True, padx=(4, 8))
        entry.bind("<Return>", lambda _e: self._on_chat_freeform_send())
        ttk.Button(
            entry_row,
            text="发送",
            style="Big.TButton",
            command=self._on_chat_freeform_send,
        ).pack(side="left")

        ttk.Label(
            tab,
            text="历史（最近 20 条）：",
            style="Status.TLabel",
        ).pack(anchor="w", pady=(12, 2))
        history_frame = ttk.Frame(tab)
        history_frame.pack(fill="both", expand=True)
        self.chat_history_listbox = tk.Listbox(history_frame, height=10, activestyle="dotbox")
        scrollbar = ttk.Scrollbar(
            history_frame, orient="vertical", command=self.chat_history_listbox.yview
        )
        self.chat_history_listbox.configure(yscrollcommand=scrollbar.set)
        self.chat_history_listbox.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.chat_history_listbox.bind(
            "<Double-Button-1>", lambda _e: self._on_chat_history_resend()
        )
        self._chat_history: list[str] = []

    def _build_settings_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=16)
        self.notebook.add(tab, text="关于")

        ttk.Label(tab, text="关于 / 环境", style="SubHeader.TLabel").pack(anchor="w")
        ttk.Label(
            tab,
            text=(
                "当前版本按 chenstack 参考修改器重排主流程。"
                " 游戏目录、增强模块状态和环境诊断统一放在这里。"
            ),
            style="Status.TLabel",
            wraplength=860,
            justify="left",
        ).pack(anchor="w", pady=(2, 8))

        ttk.Label(tab, text="游戏目录", style="SubHeader.TLabel").pack(anchor="w")
        path_row = ttk.Frame(tab)
        path_row.pack(fill="x", pady=(6, 14))
        self.game_root_var = tk.StringVar(
            value=str(self.report.game_root) if self.report.game_root else ""
        )
        ttk.Entry(path_row, textvariable=self.game_root_var).pack(
            side="left", fill="x", expand=True
        )
        ttk.Button(
            path_row, text="浏览…", style="Quiet.TButton", command=self._browse_game_root
        ).pack(side="left", padx=(6, 0))
        ttk.Button(
            path_row, text="保存并刷新", style="Big.TButton", command=self._apply_game_root
        ).pack(side="left", padx=(6, 0))

        ttk.Separator(tab).pack(fill="x", pady=(0, 10))
        ttk.Label(tab, text="环境报告", style="SubHeader.TLabel").pack(anchor="w")

        self.env_text = tk.Text(tab, height=14, wrap="word", state="disabled")
        self.env_text.pack(fill="both", expand=True, pady=(6, 10))

        bottom = ttk.Frame(tab)
        bottom.pack(fill="x")
        ttk.Button(
            bottom, text="重新扫描", style="Quiet.TButton", command=self._refresh_status
        ).pack(side="left")

    # ------------------------------------------------------------------
    # List refreshers
    # ------------------------------------------------------------------

    def _set_numeric_var(self, variable: tk.StringVar, value: int) -> None:
        variable.set(str(value))

    def _selected_notebook_tab_text(
        self,
        notebook: ttk.Notebook,
        fallback: str,
    ) -> str:
        try:
            current = notebook.select()
        except tk.TclError:
            return fallback
        if not current:
            return fallback
        try:
            return str(notebook.tab(current, "text")) or fallback
        except tk.TclError:
            return fallback

    def _build_reference_coord_seed_entries(self) -> list[ReferenceCoordEntry]:
        entries: list[ReferenceCoordEntry] = []
        for group in self.coord_groups:
            for item in group.items:
                entries.append(
                    ReferenceCoordEntry(
                        group=group.name,
                        label=item.label,
                        x=item.x,
                        y=item.y,
                        z=item.z,
                    )
                )
        for point in self.boss_points:
            entries.append(
                ReferenceCoordEntry(
                    group="Boss 直达",
                    label=point.label,
                    x=float(point.world_x),
                    y=float(point.world_y),
                    z=float(point.safe_z),
                )
            )
        return entries

    def _selected_item_reference_tab(self) -> str:
        if hasattr(self, "item_category_notebook"):
            return self._selected_notebook_tab_text(
                self.item_category_notebook,
                REFERENCE_ITEM_TABS[0],
            )
        return REFERENCE_ITEM_TABS[0]

    def _selected_pal_reference_tab(self) -> str:
        if hasattr(self, "pal_category_notebook"):
            return self._selected_notebook_tab_text(
                self.pal_category_notebook,
                REFERENCE_ADD_PAL_TABS[0],
            )
        return REFERENCE_ADD_PAL_TABS[0]

    def _catalog_display(self, entry: CatalogEntry) -> str:
        label = cmd.display_name(entry.kind, entry.key, entry.label)
        if label != entry.label:
            return label
        return f"{label} [{entry.key}]"

    def _catalog_entry_from_display(
        self,
        display: str,
        mapping: dict[str, CatalogEntry],
    ) -> CatalogEntry | None:
        text = display.strip()
        if not text:
            return None
        if text.endswith("]") and "[" in text:
            key = text.rsplit("[", 1)[1].removesuffix("]").strip()
            entry = mapping.get(key)
            if entry is not None:
                return entry
        for entry in mapping.values():
            if self._catalog_display(entry) == text:
                return entry
        return None

    def _resolve_choice_groups(
        self,
        groups: tuple[cmd.QuickChoiceGroup, ...],
        mapping: dict[str, CatalogEntry],
    ) -> dict[str, list[tuple[str, CatalogEntry]]]:
        resolved: dict[str, list[tuple[str, CatalogEntry]]] = {}
        for group in groups:
            entries: list[tuple[str, CatalogEntry]] = []
            for choice in group.choices:
                entry = mapping.get(choice.key)
                if entry is not None:
                    entries.append((choice.title, entry))
            if entries:
                resolved[group.title] = entries
        return resolved

    def _preferred_group_entries(
        self,
        groups: dict[str, list[tuple[str, CatalogEntry]]],
        selected_group: str,
    ) -> list[CatalogEntry]:
        if selected_group in groups:
            return [entry for _, entry in groups[selected_group]]
        if groups:
            return [entry for _, entry in next(iter(groups.values()))]
        return []

    def _refresh_choice_box(
        self,
        groups: dict[str, list[tuple[str, CatalogEntry]]],
        group_var: tk.StringVar,
        choice_var: tk.StringVar,
        choice_box: ttk.Combobox,
        *,
        choice_map_attr: str,
    ) -> None:
        selected_group = group_var.get().strip()
        if selected_group not in groups and groups:
            selected_group = next(iter(groups))
            group_var.set(selected_group)

        choice_map = {title: entry for title, entry in groups.get(selected_group, [])}
        setattr(self, choice_map_attr, choice_map)
        values = list(choice_map)
        choice_box.configure(values=values)
        if choice_var.get().strip() not in values:
            choice_var.set(values[0] if values else "")

    def _refresh_combo_values(
        self,
        box: ttk.Combobox,
        variable: tk.StringVar,
        values: list[str],
    ) -> None:
        box.configure(values=values)
        current = variable.get().strip()
        if current not in values:
            variable.set(values[0] if values else "")

    def _refresh_catalog_choice_box(
        self,
        entries: list[CatalogEntry],
        choice_var: tk.StringVar,
        choice_box: ttk.Combobox,
        *,
        choice_map_attr: str,
    ) -> None:
        choice_map: dict[str, CatalogEntry] = {}
        values: list[str] = []
        for entry in entries:
            display = self._catalog_display(entry)
            if display in choice_map:
                display = f"{display} [{entry.key}]"
            choice_map[display] = entry
            values.append(display)

        setattr(self, choice_map_attr, choice_map)
        self._refresh_combo_values(choice_box, choice_var, values)

    def _remember_value(self, bucket: list[str], value: str, limit: int = 10) -> None:
        if value in bucket:
            bucket.remove(value)
        bucket.insert(0, value)
        del bucket[limit:]

    def _catalog_values_for_keys(
        self,
        keys: list[str],
        mapping: dict[str, CatalogEntry],
    ) -> list[str]:
        return [
            self._catalog_display(entry)
            for key in keys
            if (entry := mapping.get(key)) is not None
        ]

    def _refresh_item_shortcuts(self) -> None:
        if hasattr(self, "item_recent_box"):
            self._refresh_combo_values(
                self.item_recent_box,
                self.item_recent_var,
                self._catalog_values_for_keys(
                    self.settings.recent_item_ids,
                    self._item_entry_by_key,
                ),
            )
        if hasattr(self, "item_favorite_box"):
            self._refresh_combo_values(
                self.item_favorite_box,
                self.item_favorite_var,
                self._catalog_values_for_keys(
                    self.settings.favorite_item_ids,
                    self._item_entry_by_key,
                ),
            )

    def _refresh_pal_shortcuts(self) -> None:
        if hasattr(self, "pal_recent_box"):
            self._refresh_combo_values(
                self.pal_recent_box,
                self.pal_recent_var,
                self._catalog_values_for_keys(
                    self.settings.recent_pal_ids,
                    self._pal_entry_by_key,
                ),
            )
        if hasattr(self, "pal_favorite_box"):
            self._refresh_combo_values(
                self.pal_favorite_box,
                self.pal_favorite_var,
                self._catalog_values_for_keys(
                    self.settings.favorite_pal_ids,
                    self._pal_entry_by_key,
                ),
            )

    def _refresh_item_quick_choices(self) -> None:
        if not hasattr(self, "item_quick_choice_box"):
            return
        self._refresh_choice_box(
            self._item_guide_groups,
            self.item_quick_group_var,
            self.item_quick_choice_var,
            self.item_quick_choice_box,
            choice_map_attr="_item_quick_choice_map",
        )
        if hasattr(self, "item_search_var") and not self.item_search_var.get().strip():
            self._refresh_item_list()

    def _selected_item_quick_entry(self) -> CatalogEntry | None:
        if not hasattr(self, "item_quick_choice_var"):
            return None
        return self._item_quick_choice_map.get(self.item_quick_choice_var.get().strip())

    def _give_selected_item_quick(self) -> None:
        entry = self._selected_item_quick_entry()
        if entry is None:
            self._show_result("当前分类没有可直接发放的物品。", ok=False)
            return
        self._give_item_entry(entry)

    def _add_selected_item_quick_favorite(self) -> None:
        entry = self._selected_item_quick_entry()
        if entry is None:
            self._show_result("当前分类没有可收藏的物品。", ok=False)
            return
        self._remember_value(self.settings.favorite_item_ids, entry.key, limit=40)
        save_settings(self.settings)
        self._refresh_item_shortcuts()
        self._show_result(f"已收藏物品：{self._catalog_display(entry)}。", ok=True)

    def _refresh_item_full_choices(self) -> None:
        if not hasattr(self, "item_full_box"):
            return
        self._refresh_catalog_choice_box(
            self.item_entries,
            self.item_full_var,
            self.item_full_box,
            choice_map_attr="_item_full_choice_map",
        )

    def _selected_item_full_entry(self) -> CatalogEntry | None:
        if not hasattr(self, "item_full_var"):
            return None
        return self._item_full_choice_map.get(self.item_full_var.get().strip())

    def _give_selected_item_full(self) -> None:
        entry = self._selected_item_full_entry()
        if entry is None:
            self._show_result("完整目录里还没有可直接发放的物品。", ok=False)
            return
        self._give_item_entry(entry)

    def _add_selected_item_full_favorite(self) -> None:
        entry = self._selected_item_full_entry()
        if entry is None:
            self._show_result("先在完整目录里选一个物品。", ok=False)
            return
        self._remember_value(self.settings.favorite_item_ids, entry.key, limit=40)
        save_settings(self.settings)
        self._refresh_item_shortcuts()
        self._show_result(f"已收藏物品：{self._catalog_display(entry)}。", ok=True)

    def _refresh_pal_quick_choices(self) -> None:
        if not hasattr(self, "pal_quick_choice_box"):
            return
        self._refresh_choice_box(
            self._pal_guide_groups,
            self.pal_quick_group_var,
            self.pal_quick_choice_var,
            self.pal_quick_choice_box,
            choice_map_attr="_pal_quick_choice_map",
        )
        if hasattr(self, "pal_search_var") and not self.pal_search_var.get().strip():
            self._refresh_pal_list()

    def _selected_pal_quick_entry(self) -> CatalogEntry | None:
        if not hasattr(self, "pal_quick_choice_var"):
            return None
        return self._pal_quick_choice_map.get(self.pal_quick_choice_var.get().strip())

    def _spawn_selected_pal_quick(self) -> None:
        entry = self._selected_pal_quick_entry()
        if entry is None:
            self._show_result("当前分类没有可直接生成的帕鲁。", ok=False)
            return
        self._spawn_pal_entry(entry)

    def _add_selected_pal_quick_favorite(self) -> None:
        entry = self._selected_pal_quick_entry()
        if entry is None:
            self._show_result("当前分类没有可收藏的帕鲁。", ok=False)
            return
        self._remember_value(self.settings.favorite_pal_ids, entry.key, limit=40)
        save_settings(self.settings)
        self._refresh_pal_shortcuts()
        self._show_result(f"已收藏帕鲁：{self._catalog_display(entry)}。", ok=True)

    def _refresh_pal_full_choices(self) -> None:
        if not hasattr(self, "pal_full_box"):
            return
        self._refresh_catalog_choice_box(
            self.pal_entries,
            self.pal_full_var,
            self.pal_full_box,
            choice_map_attr="_pal_full_choice_map",
        )

    def _selected_pal_full_entry(self) -> CatalogEntry | None:
        if not hasattr(self, "pal_full_var"):
            return None
        return self._pal_full_choice_map.get(self.pal_full_var.get().strip())

    def _spawn_selected_pal_full(self) -> None:
        entry = self._selected_pal_full_entry()
        if entry is None:
            self._show_result("完整目录里还没有可直接生成的帕鲁。", ok=False)
            return
        self._spawn_pal_entry(entry)

    def _add_selected_pal_full_favorite(self) -> None:
        entry = self._selected_pal_full_entry()
        if entry is None:
            self._show_result("先在完整目录里选一只帕鲁。", ok=False)
            return
        self._remember_value(self.settings.favorite_pal_ids, entry.key, limit=40)
        save_settings(self.settings)
        self._refresh_pal_shortcuts()
        self._show_result(f"已收藏帕鲁：{self._catalog_display(entry)}。", ok=True)

    def _refresh_tech_quick_choices(self) -> None:
        if not hasattr(self, "tech_quick_choice_box"):
            return
        self._refresh_choice_box(
            self._tech_guide_groups,
            self.tech_quick_group_var,
            self.tech_quick_choice_var,
            self.tech_quick_choice_box,
            choice_map_attr="_tech_quick_choice_map",
        )
        if hasattr(self, "tech_search_var") and not self.tech_search_var.get().strip():
            self._refresh_tech_list()

    def _selected_tech_quick_entry(self) -> CatalogEntry | None:
        if not hasattr(self, "tech_quick_choice_var"):
            return None
        return self._tech_quick_choice_map.get(self.tech_quick_choice_var.get().strip())

    def _unlock_selected_tech_quick(self) -> None:
        entry = self._selected_tech_quick_entry()
        if entry is None:
            self._show_result("当前分类没有可直接解锁的科技。", ok=False)
            return
        self._dispatch_hidden_commands(
            [cmd.unlock_tech(entry.key)],
            label=f"解锁科技：{self._catalog_display(entry)}",
        )

    def _refresh_tech_full_choices(self) -> None:
        if not hasattr(self, "tech_full_box"):
            return
        self._refresh_catalog_choice_box(
            self.tech_entries,
            self.tech_full_var,
            self.tech_full_box,
            choice_map_attr="_tech_full_choice_map",
        )

    def _selected_tech_full_entry(self) -> CatalogEntry | None:
        if not hasattr(self, "tech_full_var"):
            return None
        return self._tech_full_choice_map.get(self.tech_full_var.get().strip())

    def _unlock_selected_tech_full(self) -> None:
        entry = self._selected_tech_full_entry()
        if entry is None:
            self._show_result("先在完整目录里选一项科技。", ok=False)
            return
        self._dispatch_hidden_commands(
            [cmd.unlock_tech(entry.key)],
            label=f"解锁科技：{self._catalog_display(entry)}",
        )

    def _unlock_selected_tech_group(self) -> None:
        if not hasattr(self, "tech_quick_group_var"):
            self._show_result("当前还没有可整组解锁的科技分类。", ok=False)
            return
        group_name = self.tech_quick_group_var.get().strip()
        entries = self._preferred_group_entries(self._tech_guide_groups, group_name)
        if not entries:
            self._show_result("当前分类没有可整组解锁的科技。", ok=False)
            return
        commands = [cmd.unlock_tech(entry.key) for entry in entries]
        self._dispatch_hidden_commands(
            commands,
            label=f"{group_name}（共 {len(commands)} 项）",
        )

    def _saved_coord_labels(self) -> list[str]:
        labels: list[str] = []
        for label in self.settings.favorite_coord_labels:
            if label in self._coord_entry_by_label or label in self._boss_point_by_label:
                labels.append(label)
        return labels

    def _refresh_coord_favorites(self) -> None:
        if not hasattr(self, "coord_favorite_box"):
            return
        self._refresh_combo_values(
            self.coord_favorite_box,
            self.coord_favorite_var,
            self._saved_coord_labels(),
        )
        self._update_coord_favorite_hint()

    def _resolve_saved_coord_label(
        self,
        label: str,
    ) -> tuple[str, float, float, float] | None:
        coord = self._coord_entry_by_label.get(label)
        if coord is not None:
            return coord.label, coord.x, coord.y, coord.z

        boss = self._boss_point_by_label.get(label)
        if boss is None:
            return None
        safe_z = self._boss_point_safe_z(boss)
        return boss.label, float(boss.world_x), float(boss.world_y), float(safe_z)

    def _selected_coord_favorite(self) -> tuple[str, float, float, float] | None:
        if not hasattr(self, "coord_favorite_var"):
            return None
        return self._resolve_saved_coord_label(self.coord_favorite_var.get().strip())

    def _update_coord_favorite_hint(self) -> None:
        if not hasattr(self, "coord_favorite_hint_label"):
            return
        entry = self._selected_coord_favorite()
        if entry is None:
            self.coord_favorite_hint_label.configure(
                text="还没有收藏点位；在下方通用坐标库或 Boss 直达里选中后点「加入收藏」。"
            )
            return
        label, x, y, z = entry
        self.coord_favorite_hint_label.configure(
            text=f"{label} -> X={x:g}  Y={y:g}  Z={z:g}。可直接传送，也可塞进路径传送。"
        )

    def _set_coord_fields(self, x: float, y: float, z: float) -> None:
        self.tp_x_var.set(f"{x:g}")
        self.tp_y_var.set(f"{y:g}")
        self.tp_z_var.set(f"{z:g}")

    def _teleport_to_coords(self, x: float, y: float, z: float, label: str) -> None:
        self._set_coord_fields(x, y, z)
        ok, message = self._write_bridge_teleport_request(x, y, z)
        if ok:
            self._show_result(f"已发送 {label} 传送请求。", ok=True)
        else:
            self._show_result(message, ok=False)

    def _append_coords_to_route(self, x: float, y: float, z: float, label: str) -> None:
        if not hasattr(self, "route_text"):
            self._show_result("路径传送框还没初始化完成。", ok=False)
            return
        self.route_text.insert("end", f"{x:g} {y:g} {z:g}\n")
        self.route_text.see("end")
        self._show_result(f"已把 {label} 追加到路径列表。", ok=True)

    def _refresh_item_list(self) -> None:
        query = self.item_search_var.get().strip() if hasattr(self, "item_search_var") else ""
        if query:
            results = search_catalog(self.item_entries, query, limit=400)
            current_tab = self._selected_item_reference_tab()
            if current_tab != "全部":
                allowed_keys = {
                    entry.key for entry in self._item_reference_groups.get(current_tab, [])
                }
                results = [entry for entry in results if entry.key in allowed_keys]
        elif hasattr(self, "item_category_notebook"):
            current_tab = self._selected_item_reference_tab()
            results = list(self._item_reference_groups.get(current_tab, []))
        else:
            selected_group = (
                self.item_quick_group_var.get().strip()
                if hasattr(self, "item_quick_group_var")
                else ""
            )
            results = self._preferred_group_entries(self._item_guide_groups, selected_group)
        self.item_listbox.delete(0, "end")
        for entry in results:
            self.item_listbox.insert("end", self._catalog_display(entry))
        self._current_item_results = results
        self.item_listbox.selection_clear(0, "end")
        if results:
            self.item_listbox.selection_set(0)
            self.item_listbox.activate(0)
            self.item_listbox.see(0)

    def _refresh_pal_list(self) -> None:
        query = self.pal_search_var.get().strip() if hasattr(self, "pal_search_var") else ""
        if hasattr(self, "pal_spawn_listbox"):
            source_entries = list(self._pal_reference_groups.get(self._selected_pal_reference_tab(), []))
            if query:
                results = search_catalog(source_entries, query, limit=400)
            else:
                results = source_entries
            target_listbox = self.pal_spawn_listbox
        elif query:
            results = search_catalog(self.pal_entries, query, limit=400)
            target_listbox = self.pal_listbox
        else:
            selected_group = (
                self.pal_quick_group_var.get().strip()
                if hasattr(self, "pal_quick_group_var")
                else ""
            )
            results = self._preferred_group_entries(self._pal_guide_groups, selected_group)
            target_listbox = self.pal_listbox
        target_listbox.delete(0, "end")
        for entry in results:
            target_listbox.insert("end", self._catalog_display(entry))
        self._current_pal_results = results
        target_listbox.selection_clear(0, "end")
        if results:
            target_listbox.selection_set(0)
            target_listbox.activate(0)
            target_listbox.see(0)

    def _refresh_tech_list(self) -> None:
        query = self.tech_search_var.get().strip() if hasattr(self, "tech_search_var") else ""
        if query:
            results = search_catalog(self.tech_entries, query, limit=400)
        else:
            selected_group = (
                self.tech_quick_group_var.get().strip()
                if hasattr(self, "tech_quick_group_var")
                else ""
            )
            results = self._preferred_group_entries(self._tech_guide_groups, selected_group)
        self.tech_listbox.delete(0, "end")
        for entry in results:
            self.tech_listbox.insert("end", self._catalog_display(entry))
        self._current_tech_results = results
        self.tech_listbox.selection_clear(0, "end")
        if results:
            self.tech_listbox.selection_set(0)
            self.tech_listbox.activate(0)
            self.tech_listbox.see(0)

    def _refresh_time_label(self, time_var: tk.IntVar, time_label: ttk.Label) -> None:
        time_label.configure(text=f"{time_var.get()} 时")

    # ------------------------------------------------------------------
    # Button handlers
    # ------------------------------------------------------------------

    def _on_unlock_fast_travel(self) -> None:
        self._dispatch_hidden_commands(
            [cmd.unlock_fast_travel()],
            label="解锁全部传送点",
        )

    def _on_unlock_all_tech(self) -> None:
        self._dispatch_hidden_commands(
            [cmd.unlock_all_tech()],
            label="解锁全部科技",
        )

    def _on_set_time(self, hour: int) -> None:
        safe_hour = max(0, min(23, int(hour)))
        self._dispatch_hidden_commands(
            [cmd.set_time(safe_hour)],
            label=f"设置世界时间为 {safe_hour}:00",
        )

    def _on_give_custom_exp(self) -> None:
        try:
            amount = int(self.exp_var.get())
        except ValueError:
            self._show_result("经验值必须是整数。", ok=False)
            return
        if amount <= 0:
            self._show_result("经验值要大于 0。", ok=False)
            return
        self.settings.custom_exp_amount = amount
        save_settings(self.settings)
        self._dispatch_hidden_commands(
            [cmd.give_exp(amount)],
            label=f"发放经验值 {amount}",
        )

    def _on_mem_teleport(self) -> None:
        try:
            x = float(self.tp_x_var.get())
            y = float(self.tp_y_var.get())
            z = float(self.tp_z_var.get())
        except ValueError:
            self._show_result("坐标必须是数字。", ok=False)
            return
        self._teleport_to_coords(x, y, z, f"坐标 ({x:g}, {y:g}, {z:g})")

    def _on_mem_fly(self, enabled: bool) -> None:
        label = "开启飞行" if enabled else "关闭飞行"
        if self._bridge_runtime_ready():
            bridge_ok, message = self._write_bridge_fly_request(enabled)
            if bridge_ok:
                self._show_result(f"已无聊天回显执行：{label}", ok=True)
            else:
                self._show_result(f"{label} 发送失败：{message}", ok=False)
            return
        self._show_result(
            f"{label} 需要桥接模块已载入当前会话；不会再自动往游戏聊天框输入命令。",
            ok=False,
        )

    def _on_mem_read_pos(self) -> None:
        status = self._read_bridge_status()
        if status.player_valid:
            self._set_coord_fields(status.position_x, status.position_y, status.position_z)
            self._show_result("已从增强模块读取当前位置。", ok=True)
            return

        self._show_result(
            "读取当前位置需要增强模块已载入当前会话；不会再走聊天框回显读取。",
            ok=False,
        )

    # ------------------------------------------------------------------
    # Route teleport
    # ------------------------------------------------------------------

    def _parse_route_coords(self) -> list[tuple[float, float, float]]:
        """Parse multi-line coordinate text into a list of (x, y, z) tuples."""

        raw = self.route_text.get("1.0", "end").strip()
        coords: list[tuple[float, float, float]] = []
        for line in raw.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            # Accept space or comma separated
            parts = line.replace(",", " ").split()
            if len(parts) < 3:
                continue
            try:
                coords.append((float(parts[0]), float(parts[1]), float(parts[2])))
            except ValueError:
                continue
        return coords

    def _on_route_start(self) -> None:
        coords = self._parse_route_coords()
        if not coords:
            self._show_result("请至少填写一行 X Y Z 坐标。", ok=False)
            return
        try:
            delay = max(0.5, float(self.route_delay_var.get()))
        except ValueError:
            delay = 3.0

        self._route_stop_event.clear()
        self.route_start_btn.configure(state="disabled")
        self.route_stop_btn.configure(state="normal")
        self._show_result(
            f"开始路径传送，共 {len(coords)} 个点，每点停留 {delay:.1f}s。",
            ok=True,
            pending=True,
        )

        def worker() -> None:
            for idx, (x, y, z) in enumerate(coords, 1):
                if self._route_stop_event.is_set():
                    self._queue_ui_call(
                        lambda done=idx - 1, total=len(coords): self._route_done(
                            f"路径传送已停止（已发送 {done}/{total} 个点）。"
                        )
                    )
                    return

                self._queue_ui_call(
                    lambda i=idx, total=len(coords): self.route_progress_label.configure(
                        text=f"[{i}/{total}]"
                    )
                )
                ok, message = self._write_bridge_teleport_request(x, y, z)
                if not ok:
                    self._queue_ui_call(
                        lambda m=message: self._route_done(m, ok=False)
                    )
                    return
                self._route_stop_event.wait(delay)

            self._queue_ui_call(
                lambda total=len(coords): self._route_done(
                    f"路径传送完成，共发送 {total} 个点。"
                )
            )

        threading.Thread(target=worker, daemon=True).start()

    def _on_route_stop(self) -> None:
        self._route_stop_event.set()

    def _route_done(self, message: str, *, ok: bool = True) -> None:
        self.route_start_btn.configure(state="normal")
        self.route_stop_btn.configure(state="disabled")
        self.route_progress_label.configure(text="")
        self._show_result(message, ok=ok)

    def _on_give_preset(self, preset: cmd.QuickPreset) -> None:
        valid_items = [
            (item_id, count)
            for item_id, count in preset.items
            if item_id in self._item_entry_by_key
        ]
        missing_count = len(preset.items) - len(valid_items)
        commands = [cmd.giveme(item_id, count) for item_id, count in valid_items]
        if not commands:
            self._show_result(f"{preset.title} 里没有当前版本可用的物品。", ok=False)
            return
        label = preset.title
        if missing_count > 0:
            label = f"{preset.title}（已跳过 {missing_count} 个过期物品）"
        self._dispatch_hidden_commands(
            commands,
            label=f"{label}（共 {len(commands)} 条）",
        )

    def _parse_count(self, raw: str, default: int = 1) -> int:
        try:
            value = int(raw)
            return max(1, value)
        except ValueError:
            return default

    def _give_item_entry(self, entry: CatalogEntry) -> None:
        count = self._parse_count(self.item_count_var.get())
        self.settings.custom_item_count = count
        self._remember_recent(self.settings.recent_item_ids, entry.key)
        save_settings(self.settings)
        self._refresh_item_shortcuts()
        self._dispatch_hidden_commands(
            [cmd.giveme(entry.key, count)],
            label=f"发放物品：{entry.label} x{count}",
        )

    def _spawn_pal_entry(self, entry: CatalogEntry) -> None:
        count = self._parse_count(self.pal_count_var.get())
        self.settings.custom_pal_count = count
        self._remember_recent(self.settings.recent_pal_ids, entry.key)
        save_settings(self.settings)
        self._refresh_pal_shortcuts()
        self._dispatch_hidden_commands(
            [cmd.spawn_pal(entry.key, count)],
            label=f"生成帕鲁：{entry.label} x{count}",
        )

    def _load_recent_item_into_search(self) -> None:
        entry = self._catalog_entry_from_display(self.item_recent_var.get(), self._item_entry_by_key)
        if entry is None:
            self._show_result("最近列表里还没有可用物品。", ok=False)
            return
        self.item_search_var.set(entry.key)
        self._show_result(f"已把 {entry.label} 填入搜索框。", ok=True)

    def _give_recent_item(self) -> None:
        entry = self._catalog_entry_from_display(self.item_recent_var.get(), self._item_entry_by_key)
        if entry is None:
            self._show_result("最近列表里还没有可用物品。", ok=False)
            return
        self._give_item_entry(entry)

    def _give_favorite_item(self) -> None:
        entry = self._catalog_entry_from_display(
            self.item_favorite_var.get(),
            self._item_entry_by_key,
        )
        if entry is None:
            self._show_result("先选一个收藏物品。", ok=False)
            return
        self._give_item_entry(entry)

    def _add_selected_item_favorite(self) -> None:
        selection = self.item_listbox.curselection()
        if not selection:
            self._show_result("先在列表里选一项物品。", ok=False)
            return
        entry = self._current_item_results[selection[0]]
        self._remember_value(self.settings.favorite_item_ids, entry.key, limit=40)
        save_settings(self.settings)
        self._refresh_item_shortcuts()
        self._show_result(f"已收藏物品：{entry.label}。", ok=True)

    def _remove_selected_item_favorite(self) -> None:
        entry = self._catalog_entry_from_display(
            self.item_favorite_var.get(),
            self._item_entry_by_key,
        )
        if entry is None:
            self._show_result("先选一个收藏物品。", ok=False)
            return
        if entry.key not in self.settings.favorite_item_ids:
            self._show_result("这个物品不在收藏里。", ok=False)
            return
        self.settings.favorite_item_ids.remove(entry.key)
        save_settings(self.settings)
        self._refresh_item_shortcuts()
        self._show_result(f"已移除收藏：{entry.label}。", ok=True)

    def _load_recent_pal_into_search(self) -> None:
        entry = self._catalog_entry_from_display(self.pal_recent_var.get(), self._pal_entry_by_key)
        if entry is None:
            self._show_result("最近列表里还没有可用帕鲁。", ok=False)
            return
        self.pal_search_var.set(entry.key)
        self._show_result(f"已把 {entry.label} 填入搜索框。", ok=True)

    def _spawn_recent_pal(self) -> None:
        entry = self._catalog_entry_from_display(self.pal_recent_var.get(), self._pal_entry_by_key)
        if entry is None:
            self._show_result("最近列表里还没有可用帕鲁。", ok=False)
            return
        self._spawn_pal_entry(entry)

    def _spawn_favorite_pal(self) -> None:
        entry = self._catalog_entry_from_display(self.pal_favorite_var.get(), self._pal_entry_by_key)
        if entry is None:
            self._show_result("先选一个收藏帕鲁。", ok=False)
            return
        self._spawn_pal_entry(entry)

    def _add_selected_pal_favorite(self) -> None:
        selection = self.pal_listbox.curselection()
        if not selection:
            self._show_result("先在列表里选一只帕鲁。", ok=False)
            return
        entry = self._current_pal_results[selection[0]]
        self._remember_value(self.settings.favorite_pal_ids, entry.key, limit=40)
        save_settings(self.settings)
        self._refresh_pal_shortcuts()
        self._show_result(f"已收藏帕鲁：{entry.label}。", ok=True)

    def _remove_selected_pal_favorite(self) -> None:
        entry = self._catalog_entry_from_display(self.pal_favorite_var.get(), self._pal_entry_by_key)
        if entry is None:
            self._show_result("先选一个收藏帕鲁。", ok=False)
            return
        if entry.key not in self.settings.favorite_pal_ids:
            self._show_result("这只帕鲁不在收藏里。", ok=False)
            return
        self.settings.favorite_pal_ids.remove(entry.key)
        save_settings(self.settings)
        self._refresh_pal_shortcuts()
        self._show_result(f"已移除收藏：{entry.label}。", ok=True)

    def _on_give_selected_item(self) -> None:
        selection = self.item_listbox.curselection()
        if not selection:
            self._show_result("先在列表里选一项物品。", ok=False)
            return
        entry = self._current_item_results[selection[0]]
        self._give_item_entry(entry)

    def _on_spawn_selected_pal(self) -> None:
        selection = self.pal_listbox.curselection()
        if not selection:
            self._show_result("先在列表里选一只帕鲁。", ok=False)
            return
        entry = self._current_pal_results[selection[0]]
        self._spawn_pal_entry(entry)

    def _on_unlock_selected_tech(self) -> None:
        selection = self.tech_listbox.curselection()
        if not selection:
            self._show_result("先在列表里选一项科技。", ok=False)
            return
        entry = self._current_tech_results[selection[0]]
        self._dispatch_hidden_commands(
            [cmd.unlock_tech(entry.key)],
            label=f"解锁科技：{entry.label}",
        )

    def _remember_recent(self, bucket: list[str], key: str, limit: int = 10) -> None:
        self._remember_value(bucket, key, limit)

    # ------------------------------------------------------------------
    # Memory engine helpers
    # ------------------------------------------------------------------

    def _on_mem_attach(self) -> None:
        result = self.mem.attach()
        self._update_mem_status(result)
        if result.ok:
            self._refresh_mem_rows()

    def _on_mem_detach(self) -> None:
        self.mem.detach()
        self._update_mem_status(AttachResult(False, "已断开。"))
        self._refresh_mem_rows()

    def _update_mem_status(self, result: AttachResult) -> None:
        if not hasattr(self, "mem_attach_label"):
            return
        if result.ok and self.mem.is_attached():
            self.mem_attach_label.configure(
                text=f"✔ {result.message}", style="Good.TLabel"
            )
        else:
            self.mem_attach_label.configure(
                text=f"⚠ {result.message}", style="Warn.TLabel"
            )

    def _parse_float(self, raw: str) -> float | None:
        try:
            return float(raw.strip())
        except (TypeError, ValueError):
            return None

    def _on_mem_scan(self, slot: str, *, first: bool) -> None:
        if not self.mem.is_attached():
            self._show_result("还没连接游戏，先点「连接游戏」。", ok=False)
            return
        if self._mem_busy:
            self._show_result("上一次扫描还没跑完，稍等几秒。", ok=False)
            return
        value = self._parse_float(self._mem_scan_entries[slot].get())
        if value is None:
            self._show_result("数值要是个数字，例如 500 或 32.5。", ok=False)
            return

        label = self.mem.label_for(slot)
        self._mem_busy = True
        action = "首次搜索" if first else "缩小范围"
        self._show_result(f"{label} {action} 中（约 40 秒首次/秒级缩小）…", ok=True, pending=True)

        def worker() -> None:
            try:
                if first:
                    snap = self.mem.start_scan(slot, value)
                else:
                    snap = self.mem.refine_scan(slot, value)
            except Exception as error:  # noqa: BLE001 - report to UI
                self._queue_ui_call(lambda: self._mem_scan_done(slot, None, str(error)))
                return
            self._queue_ui_call(lambda: self._mem_scan_done(slot, len(snap), None))

        threading.Thread(target=worker, daemon=True).start()

    def _mem_scan_done(self, slot: str, count: int | None, error: str | None) -> None:
        self._mem_busy = False
        label = self.mem.label_for(slot)
        if error is not None:
            self._show_result(f"{label} 扫描失败：{error}", ok=False)
            return
        if count is None:
            return
        self._refresh_mem_rows()
        if count == 0:
            self._show_result(
                f"{label} 没找到候选。值是不是数错了？（试试整数/小数点切换）",
                ok=False,
            )
        elif count == 1:
            self._show_result(
                f"{label} 已缩到 1 个候选，可以点「锁定」了。", ok=True
            )
        else:
            self._show_result(
                f"{label} 当前 {count} 个候选。去游戏里把该数值变一下，再填新值点「缩小范围」。",
                ok=True,
            )

    def _on_mem_lock(self, slot: str) -> None:
        if not self.mem.is_attached():
            self._show_result("还没连接游戏。", ok=False)
            return
        ok = self.mem.lock_address(slot)
        if not ok:
            size = self.mem.snapshot_size(slot)
            if size == 0:
                self._show_result("先跑一次扫描。", ok=False)
            else:
                self._show_result(
                    f"还有 {size} 个候选，得缩到 1 个才能锁定。", ok=False
                )
            return
        self._refresh_mem_rows()
        self._show_result(f"{self.mem.label_for(slot)} 已锁定。可以勾选「冻结」了。", ok=True)

    def _on_mem_clear(self, slot: str) -> None:
        self.mem.unlock_address(slot)
        self._mem_slot_vars[slot].set(False)
        self.mem.set_slot_freeze(slot, False)
        self._refresh_mem_rows()
        self._show_result(f"{self.mem.label_for(slot)} 已清除。", ok=True)

    def _on_mem_target_changed(self, slot: str) -> None:
        value = self._parse_float(self._mem_target_entries[slot].get())
        if value is None:
            self._mem_target_entries[slot].set(f"{self.mem.slot_target(slot):.1f}")
            return
        self.mem.set_slot_target(slot, value)

    def _on_mem_freeze_toggled(self, slot: str) -> None:
        enabled = bool(self._mem_slot_vars[slot].get())
        if enabled and not self.mem.is_locked(slot):
            self._mem_slot_vars[slot].set(False)
            self._show_result(
                f"{self.mem.label_for(slot)} 还没锁定地址，先完成扫描。", ok=False
            )
            return
        # Commit current target first in case the user edited the box without
        # tabbing out.
        self._on_mem_target_changed(slot)
        self.mem.set_slot_freeze(slot, enabled)
        label = self.mem.label_for(slot)
        if enabled:
            self._show_result(
                f"{label} 已冻结到 {self.mem.slot_target(slot):g}。", ok=True
            )
        else:
            self._show_result(f"{label} 冻结已关闭。", ok=True)

    def _refresh_mem_rows(self) -> None:
        if not self._mem_slot_labels:
            return
        for slot in list(self._mem_slot_labels.keys()):
            label = self._mem_slot_labels.get(slot)
            if label is None:
                continue
            if self.mem.is_locked(slot):
                addr = self.mem.address_for(slot)
                current = self.mem.read_current_value(slot)
                cur_text = f"{current:g}" if current is not None else "?"
                label.configure(
                    text=f"已锁定 @ 0x{addr:x}\n当前 {cur_text}", style="Good.TLabel"
                )
            else:
                size = self.mem.snapshot_size(slot)
                if size == 0:
                    label.configure(text="—", style="Status.TLabel")
                else:
                    label.configure(text=f"候选 {size}", style="Warn.TLabel")

    # ------------------------------------------------------------------
    # Custom memory slots
    # ------------------------------------------------------------------

    def _on_add_custom_slot(self) -> None:
        dialog = _CustomSlotDialog(self.root)
        self.root.wait_window(dialog.top)
        if not dialog.result:
            return
        label, initial_value, default_target, dtype = dialog.result
        cs = self.mem.add_custom_slot(label, default_target=default_target, dtype=dtype)
        self._build_custom_slot_row(cs, initial_value=initial_value)
        self._hide_custom_empty_hint()
        dtype_label = DTYPE_LABELS_CN.get(dtype, dtype)
        self._show_result(
            f"已添加「{cs.label}」[{dtype_label}]。填入当前值后点「首次搜索」开始扫描。",
            ok=True,
        )

    def _on_add_custom_slot_from_template(self, template: CustomSlotTemplate) -> None:
        cs = self.mem.add_custom_slot(
            template.label, default_target=template.default_target, dtype=template.dtype
        )
        self._build_custom_slot_row(cs)
        self._hide_custom_empty_hint()
        dtype_label = DTYPE_LABELS_CN.get(cs.dtype, cs.dtype)
        self._show_result(
            f"已添加模板「{cs.label}」[{dtype_label}] —— {template.hint}。在本行填入当前值后点「首次搜索」。",
            ok=True,
        )

    def _build_custom_slot_row(self, cs: CustomSlot, *, initial_value: str = "") -> None:
        container = self._custom_slots_container
        frame = ttk.Frame(container, padding=(2, 2))
        frame.pack(fill="x", pady=2)
        self._mem_custom_row_frames[cs.key] = frame

        ttk.Label(frame, text=cs.label, width=18, anchor="w").grid(
            row=0, column=0, sticky="w", padx=4, pady=2
        )

        scan_var = tk.StringVar(value=initial_value)
        self._mem_scan_entries[cs.key] = scan_var
        ttk.Entry(frame, textvariable=scan_var, width=12).grid(
            row=0, column=1, sticky="w", padx=4, pady=2
        )

        btns = ttk.Frame(frame)
        btns.grid(row=0, column=2, sticky="w", padx=4, pady=2)
        for text, first in (("首次搜索", True), ("缩小范围", False)):
            ttk.Button(
                btns,
                text=text,
                style="Quiet.TButton",
                command=lambda s=cs.key, f=first: self._on_mem_scan(s, first=f),
            ).pack(side="left", padx=(0, 2))
        ttk.Button(
            btns,
            text="锁定",
            style="Quiet.TButton",
            command=lambda s=cs.key: self._on_mem_lock(s),
        ).pack(side="left", padx=(0, 2))
        ttk.Button(
            btns,
            text="清除",
            style="Quiet.TButton",
            command=lambda s=cs.key: self._on_mem_clear(s),
        ).pack(side="left", padx=(0, 2))

        count_label = ttk.Label(frame, text="—", style="Status.TLabel", width=14)
        count_label.grid(row=0, column=3, sticky="w", padx=4, pady=2)
        self._mem_slot_labels[cs.key] = count_label

        target_var = tk.StringVar(value=f"{cs.target:g}")
        self._mem_target_entries[cs.key] = target_var
        target_entry = ttk.Entry(frame, textvariable=target_var, width=10)
        target_entry.grid(row=0, column=4, sticky="w", padx=4, pady=2)
        target_entry.bind(
            "<FocusOut>", lambda _event, s=cs.key: self._on_mem_target_changed(s)
        )
        target_entry.bind(
            "<Return>", lambda _event, s=cs.key: self._on_mem_target_changed(s)
        )

        freeze_var = tk.BooleanVar(value=False)
        self._mem_slot_vars[cs.key] = freeze_var
        ttk.Checkbutton(
            frame,
            text="冻结",
            variable=freeze_var,
            command=lambda s=cs.key: self._on_mem_freeze_toggled(s),
        ).grid(row=0, column=5, sticky="w", padx=4, pady=2)

        ttk.Button(
            frame,
            text="✕ 移除",
            style="Quiet.TButton",
            command=lambda s=cs.key: self._on_remove_custom_slot(s),
        ).grid(row=0, column=6, sticky="w", padx=4, pady=2)

        frame.columnconfigure(1, weight=1)

    def _on_remove_custom_slot(self, key: str) -> None:
        self.mem.remove_custom_slot(key)
        frame = self._mem_custom_row_frames.pop(key, None)
        if frame is not None:
            frame.destroy()
        self._mem_slot_vars.pop(key, None)
        self._mem_slot_labels.pop(key, None)
        self._mem_scan_entries.pop(key, None)
        self._mem_target_entries.pop(key, None)
        if not self._mem_custom_row_frames:
            self._show_custom_empty_hint()
        self._show_result("已移除自定义字段。", ok=True)

    def _hide_custom_empty_hint(self) -> None:
        if self._custom_empty_hint is not None:
            self._custom_empty_hint.pack_forget()

    def _show_custom_empty_hint(self) -> None:
        if self._custom_empty_hint is not None:
            self._custom_empty_hint.pack(anchor="w", pady=(4, 0))

    # ------------------------------------------------------------------
    # One-click presets
    # ------------------------------------------------------------------

    def _apply_mem_preset(self, targets: dict[str, float], label: str) -> None:
        if not self.mem.is_attached():
            self._show_result("还没连接游戏，先点「连接游戏」。", ok=False)
            return
        missing = [SLOT_LABELS_CN[s] for s in targets if not self.mem.is_locked(s)]
        if missing:
            self._show_result(
                f"先锁定：{'、'.join(missing)}。再点「{label}」。",
                ok=False,
            )
            return
        for slot, value in targets.items():
            self.mem.set_slot_target(slot, value)
            self.mem.set_slot_freeze(slot, True)
            var = self._mem_slot_vars.get(slot)
            if var is not None:
                var.set(True)
            entry = self._mem_target_entries.get(slot)
            if entry is not None:
                entry.set(f"{value:g}")
        self._show_result(f"{label} 已启动。", ok=True)

    def _mem_preset_stop_all(self) -> None:
        for slot in SLOTS:
            self.mem.set_slot_freeze(slot, False)
            var = self._mem_slot_vars.get(slot)
            if var is not None:
                var.set(False)
        for cs in self.mem.custom_slots():
            self.mem.set_slot_freeze(cs.key, False)
            var = self._mem_slot_vars.get(cs.key)
            if var is not None:
                var.set(False)
        self._show_result("全部冻结已关闭。", ok=True)

    def _schedule_mem_refresh(self) -> None:
        # Poll the locked values a few times a second so the GUI shows the
        # currently-written HP/SP/speed without fighting the ticker thread.
        self._refresh_mem_rows()
        self._mem_refresh_job = self.root.after(500, self._schedule_mem_refresh)

    # ------------------------------------------------------------------
    # Reference-parity overrides
    # ------------------------------------------------------------------

    def _build_items_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=16)
        self.notebook.add(tab, text="*添加物品")

        ttk.Label(tab, text="*添加物品", style="SubHeader.TLabel").pack(anchor="w")
        ttk.Label(
            tab,
            text="参考版这一页以分类页签 + 搜索Id、名称 + 数量 + 一键添加为主，因此这里不再把本地快捷预设和收藏入口混在主流程里。",
            style="Status.TLabel",
            wraplength=860,
            justify="left",
        ).pack(anchor="w", pady=(4, 10))

        self.item_category_notebook = ttk.Notebook(tab)
        self.item_category_notebook.pack(fill="x", pady=(0, 8))
        for title in REFERENCE_ITEM_TABS:
            self.item_category_notebook.add(ttk.Frame(self.item_category_notebook), text=title)
        self.item_category_notebook.bind(
            "<<NotebookTabChanged>>",
            lambda _event: self._refresh_item_list(),
        )

        search_row = ttk.Frame(tab)
        search_row.pack(fill="x", pady=(0, 8))
        ttk.Label(search_row, text="搜索Id、名称").pack(side="left")
        self.item_search_var = tk.StringVar()
        self.item_search_var.trace_add("write", lambda *_: self._refresh_item_list())
        ttk.Entry(search_row, textvariable=self.item_search_var).pack(
            side="left", padx=(8, 10), fill="x", expand=True
        )
        self.item_search_desc_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            search_row,
            text="搜索描述",
            variable=self.item_search_desc_var,
            command=self._refresh_item_list,
        ).pack(side="left", padx=(0, 10))
        ttk.Label(search_row, text="数量").pack(side="left")
        self.item_count_var = tk.StringVar(value=str(self.settings.custom_item_count))
        ttk.Entry(search_row, textvariable=self.item_count_var, width=8).pack(
            side="left", padx=(6, 0)
        )

        list_frame = ttk.Frame(tab)
        list_frame.pack(fill="both", expand=True, pady=(0, 8))
        self.item_listbox = tk.Listbox(list_frame, height=14, activestyle="dotbox")
        item_scroll = ttk.Scrollbar(list_frame, orient="vertical", command=self.item_listbox.yview)
        self.item_listbox.configure(yscrollcommand=item_scroll.set)
        self.item_listbox.pack(side="left", fill="both", expand=True)
        item_scroll.pack(side="right", fill="y")
        self.item_listbox.bind("<Double-Button-1>", lambda _event: self._on_give_selected_item())

        action_row = ttk.Frame(tab)
        action_row.pack(fill="x")
        ttk.Button(
            action_row,
            text="添加物品",
            style="Big.TButton",
            command=self._on_give_selected_item,
        ).pack(side="left")

        self._refresh_item_list()

    def _build_pals_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=16)
        self.notebook.add(tab, text="*添加帕鲁")

        ttk.Label(tab, text="*添加帕鲁", style="SubHeader.TLabel").pack(anchor="w")
        ttk.Label(
            tab,
            text="参考版这一页的重点是分类页签、收藏夹、搜索Id/名称和直接生成。本版先把这些高频流程对齐，生成参数细项会继续并入后续 parity pass。",
            style="Status.TLabel",
            wraplength=860,
            justify="left",
        ).pack(anchor="w", pady=(4, 10))

        self.pal_category_notebook = ttk.Notebook(tab)
        self.pal_category_notebook.pack(fill="x", pady=(0, 8))
        for title in REFERENCE_ADD_PAL_TABS:
            self.pal_category_notebook.add(ttk.Frame(self.pal_category_notebook), text=title)
        self.pal_category_notebook.bind(
            "<<NotebookTabChanged>>",
            lambda _event: self._refresh_pal_list(),
        )

        content = ttk.Frame(tab)
        content.pack(fill="both", expand=True)
        content.columnconfigure(0, weight=0)
        content.columnconfigure(1, weight=1)
        content.rowconfigure(0, weight=1)

        favorites = ttk.LabelFrame(content, text="收藏夹", padding=(10, 8))
        favorites.grid(row=0, column=0, sticky="nsw", padx=(0, 10))
        self.pal_favorite_listbox = tk.Listbox(favorites, width=28, height=14, activestyle="dotbox")
        self.pal_favorite_listbox.pack(fill="both", expand=True)
        self.pal_favorite_listbox.bind(
            "<Double-Button-1>",
            lambda _event: self._spawn_selected_pal_favorite(),
        )
        fav_buttons = ttk.Frame(favorites)
        fav_buttons.pack(fill="x", pady=(8, 0))
        ttk.Button(
            fav_buttons,
            text="添加",
            style="Quiet.TButton",
            command=self._add_selected_pal_favorite,
        ).pack(side="left", padx=(0, 4))
        ttk.Button(
            fav_buttons,
            text="移除",
            style="Quiet.TButton",
            command=self._remove_selected_pal_favorite_listbox,
        ).pack(side="left")

        right = ttk.Frame(content)
        right.grid(row=0, column=1, sticky="nsew")
        right.rowconfigure(1, weight=1)

        search_row = ttk.Frame(right)
        search_row.pack(fill="x", pady=(0, 8))
        ttk.Label(search_row, text="搜索Id、名称").pack(side="left")
        self.pal_search_var = tk.StringVar()
        self.pal_search_var.trace_add("write", lambda *_: self._refresh_pal_list())
        ttk.Entry(search_row, textvariable=self.pal_search_var).pack(
            side="left", padx=(8, 10), fill="x", expand=True
        )
        self.pal_search_desc_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            search_row,
            text="搜索描述",
            variable=self.pal_search_desc_var,
            command=self._refresh_pal_list,
        ).pack(side="left", padx=(0, 10))
        ttk.Label(search_row, text="数量").pack(side="left")
        self.pal_count_var = tk.StringVar(value=str(self.settings.custom_pal_count))
        ttk.Entry(search_row, textvariable=self.pal_count_var, width=8).pack(
            side="left", padx=(6, 0)
        )

        list_frame = ttk.Frame(right)
        list_frame.pack(fill="both", expand=True)
        self.pal_spawn_listbox = tk.Listbox(list_frame, height=14, activestyle="dotbox")
        self.pal_listbox = self.pal_spawn_listbox
        pal_scroll = ttk.Scrollbar(list_frame, orient="vertical", command=self.pal_spawn_listbox.yview)
        self.pal_spawn_listbox.configure(yscrollcommand=pal_scroll.set)
        self.pal_spawn_listbox.pack(side="left", fill="both", expand=True)
        pal_scroll.pack(side="right", fill="y")
        self.pal_spawn_listbox.bind("<Double-Button-1>", lambda _event: self._on_spawn_selected_pal())

        detail_tabs = ttk.Notebook(right)
        detail_tabs.pack(fill="x", pady=(8, 0))
        for title in REFERENCE_ADD_PAL_DETAIL_TABS:
            frame = ttk.Frame(detail_tabs, padding=12)
            detail_tabs.add(frame, text=title)
            ttk.Label(
                frame,
                text="这一轮先对齐分类与生成主流程；生成参数细项会继续补齐到参考版。",
                style="Status.TLabel",
                wraplength=640,
                justify="left",
            ).pack(anchor="w")

        action_row = ttk.Frame(right)
        action_row.pack(fill="x", pady=(8, 0))
        ttk.Button(
            action_row,
            text="添加帕鲁",
            style="Big.TButton",
            command=self._on_spawn_selected_pal,
        ).pack(side="left")

        self._refresh_pal_reference_favorites()
        self._refresh_pal_list()

    def _refresh_pal_reference_favorites(self) -> None:
        if not hasattr(self, "pal_favorite_listbox"):
            return
        self.pal_favorite_listbox.delete(0, "end")
        for key in self.settings.favorite_pal_ids:
            entry = self._pal_entry_by_key.get(key) or self._npc_entry_by_key.get(key)
            if entry is None:
                continue
            self.pal_favorite_listbox.insert("end", self._catalog_display(entry))

    def _selected_pal_favorite_entry(self) -> CatalogEntry | None:
        if not hasattr(self, "pal_favorite_listbox"):
            return None
        selection = self.pal_favorite_listbox.curselection()
        if not selection:
            return None
        display = self.pal_favorite_listbox.get(selection[0])
        entry = self._catalog_entry_from_display(display, self._pal_entry_by_key)
        if entry is not None:
            return entry
        return self._catalog_entry_from_display(display, self._npc_entry_by_key)

    def _spawn_selected_pal_favorite(self) -> None:
        entry = self._selected_pal_favorite_entry()
        if entry is None:
            self._show_result("请先在收藏夹里选中一个帕鲁。", ok=False)
            return
        self._spawn_pal_entry(entry)

    def _remove_selected_pal_favorite_listbox(self) -> None:
        entry = self._selected_pal_favorite_entry()
        if entry is None:
            self._show_result("请先在收藏夹里选中一个帕鲁。", ok=False)
            return
        if entry.key not in self.settings.favorite_pal_ids:
            self._show_result("这个帕鲁不在收藏夹里。", ok=False)
            return
        self.settings.favorite_pal_ids.remove(entry.key)
        save_settings(self.settings)
        self._refresh_pal_reference_favorites()
        self._show_result(f"已移除收藏：{entry.label}", ok=True)

    def _add_selected_pal_favorite(self) -> None:
        selection = self.pal_listbox.curselection()
        if not selection:
            self._show_result("请先在列表里选中一个帕鲁。", ok=False)
            return
        entry = self._current_pal_results[selection[0]]
        self._remember_value(self.settings.favorite_pal_ids, entry.key, limit=60)
        save_settings(self.settings)
        self._refresh_pal_reference_favorites()
        self._show_result(f"已加入收藏：{entry.label}", ok=True)

    def _build_coords_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=16)
        self.notebook.add(tab, text="传送和移速")

        ttk.Label(tab, text="传送和移速", style="SubHeader.TLabel").pack(anchor="w")
        ttk.Label(
            tab,
            text="这一页按参考版改成移速倍率 + 分组/坐标列表 + 坐标读写 + 直接联机传送的流程。原来的 Boss 直达、收藏夹和路径传送已收敛进分组/坐标列表工作区。",
            style="Status.TLabel",
            wraplength=860,
            justify="left",
        ).pack(anchor="w", pady=(4, 10))

        speed_card = ttk.LabelFrame(tab, text="修改坐标 / 移速倍率", padding=(12, 8))
        speed_card.pack(fill="x", pady=(0, 10))

        top_toggle_row = ttk.Frame(speed_card)
        top_toggle_row.pack(fill="x", pady=(0, 6))
        self.coord_modify_enabled_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            top_toggle_row,
            text="修改坐标",
            variable=self.coord_modify_enabled_var,
        ).pack(side="left", padx=(0, 16))

        ttk.Label(top_toggle_row, text="奔跑速度倍率").pack(side="left")
        self.coord_run_speed_var = tk.StringVar(
            value=f"{self.cheat_state.speed_multiplier:g}"
        )
        ttk.Entry(top_toggle_row, textvariable=self.coord_run_speed_var, width=8).pack(
            side="left",
            padx=(6, 6),
        )
        ttk.Button(
            top_toggle_row,
            text="写入",
            style="Quiet.TButton",
            command=lambda: self._apply_coord_speed_multiplier(self.coord_run_speed_var.get()),
        ).pack(side="left", padx=(0, 10))

        ttk.Label(top_toggle_row, text="步行速度倍率").pack(side="left")
        self.coord_walk_speed_var = tk.StringVar(
            value=f"{self.cheat_state.speed_multiplier:g}"
        )
        ttk.Entry(top_toggle_row, textvariable=self.coord_walk_speed_var, width=8).pack(
            side="left",
            padx=(6, 6),
        )
        ttk.Button(
            top_toggle_row,
            text="写入",
            style="Quiet.TButton",
            command=lambda: self._apply_coord_speed_multiplier(self.coord_walk_speed_var.get()),
        ).pack(side="left", padx=(0, 10))

        ttk.Label(top_toggle_row, text="跳跃高度倍率").pack(side="left")
        self.coord_jump_speed_var = tk.StringVar(
            value=f"{self.cheat_state.jump_multiplier:g}"
        )
        ttk.Entry(top_toggle_row, textvariable=self.coord_jump_speed_var, width=8).pack(
            side="left",
            padx=(6, 6),
        )
        ttk.Button(
            top_toggle_row,
            text="写入",
            style="Quiet.TButton",
            command=lambda: self._apply_coord_jump_multiplier(self.coord_jump_speed_var.get()),
        ).pack(side="left", padx=(0, 10))
        ttk.Button(
            top_toggle_row,
            text="全部关闭",
            style="Quiet.TButton",
            command=self._reset_coord_movement_multipliers,
        ).pack(side="left")

        workspace = ttk.Frame(tab)
        workspace.pack(fill="both", expand=True)
        workspace.columnconfigure(0, weight=0)
        workspace.columnconfigure(1, weight=0)
        workspace.columnconfigure(2, weight=1)
        workspace.rowconfigure(0, weight=1)

        group_col = ttk.Frame(workspace)
        group_col.grid(row=0, column=0, sticky="ns", padx=(0, 8))
        group_toolbar = ttk.Frame(group_col)
        group_toolbar.pack(fill="x", pady=(0, 4))
        ttk.Label(group_toolbar, text="分组").pack(side="left")
        ttk.Button(group_toolbar, text="添加", style="Quiet.TButton", command=self._add_coord_group).pack(side="left", padx=(8, 4))
        ttk.Button(group_toolbar, text="重命名", style="Quiet.TButton", command=self._rename_coord_group).pack(side="left", padx=4)
        ttk.Button(group_toolbar, text="移除", style="Quiet.TButton", command=self._remove_coord_group).pack(side="left", padx=4)
        ttk.Button(group_toolbar, text="保存", style="Quiet.TButton", command=self._save_coord_workspace_action).pack(side="left", padx=4)
        ttk.Button(group_toolbar, text="导出", style="Quiet.TButton", command=self._export_coord_workspace).pack(side="left", padx=4)
        self.coord_group_listbox = tk.Listbox(group_col, width=24, height=16, activestyle="dotbox")
        self.coord_group_listbox.pack(fill="both", expand=True)
        self.coord_group_listbox.bind("<<ListboxSelect>>", self._on_select_coord_group)

        item_col = ttk.Frame(workspace)
        item_col.grid(row=0, column=1, sticky="ns", padx=(0, 8))
        item_toolbar = ttk.Frame(item_col)
        item_toolbar.pack(fill="x", pady=(0, 4))
        ttk.Label(item_toolbar, text="坐标列表").pack(side="left")
        ttk.Button(item_toolbar, text="添加", style="Quiet.TButton", command=self._add_coord_workspace_item).pack(side="left", padx=(8, 4))
        ttk.Button(item_toolbar, text="更新", style="Quiet.TButton", command=self._update_coord_workspace_item).pack(side="left", padx=4)
        ttk.Button(item_toolbar, text="移除", style="Quiet.TButton", command=self._remove_coord_workspace_item).pack(side="left", padx=4)
        ttk.Button(item_toolbar, text="清空", style="Quiet.TButton", command=self._clear_coord_workspace_group).pack(side="left", padx=4)
        self.coord_item_listbox = tk.Listbox(item_col, width=36, height=16, activestyle="dotbox")
        self.coord_item_listbox.pack(fill="both", expand=True)
        self.coord_item_listbox.bind("<<ListboxSelect>>", self._on_select_coord_item)

        editor_col = ttk.Frame(workspace)
        editor_col.grid(row=0, column=2, sticky="nsew")
        editor_toolbar = ttk.Frame(editor_col)
        editor_toolbar.pack(fill="x", pady=(0, 4))
        ttk.Label(editor_toolbar, text="坐标").pack(side="left")
        ttk.Button(editor_toolbar, text="读取", style="Quiet.TButton", command=self._read_coord_into_form).pack(side="left", padx=(8, 4))
        ttk.Button(editor_toolbar, text="写入", style="Quiet.TButton", command=self._update_coord_workspace_item).pack(side="left", padx=4)
        ttk.Button(editor_toolbar, text="复制", style="Quiet.TButton", command=self._copy_coord_fields).pack(side="left", padx=4)
        ttk.Button(editor_toolbar, text="粘贴", style="Quiet.TButton", command=self._paste_coord_fields).pack(side="left", padx=4)

        form = ttk.Frame(editor_col)
        form.pack(fill="x", pady=(6, 8))
        self.coord_name_var = tk.StringVar()
        self.tp_x_var = tk.StringVar()
        self.tp_y_var = tk.StringVar()
        self.tp_z_var = tk.StringVar()

        ttk.Label(form, text="名称").grid(row=0, column=0, sticky="w", pady=4)
        ttk.Entry(form, textvariable=self.coord_name_var).grid(row=0, column=1, sticky="ew", pady=4)
        ttk.Label(form, text="X坐标").grid(row=1, column=0, sticky="w", pady=4)
        ttk.Entry(form, textvariable=self.tp_x_var).grid(row=1, column=1, sticky="ew", pady=4)
        ttk.Label(form, text="Y坐标").grid(row=2, column=0, sticky="w", pady=4)
        ttk.Entry(form, textvariable=self.tp_y_var).grid(row=2, column=1, sticky="ew", pady=4)
        ttk.Label(form, text="Z坐标").grid(row=3, column=0, sticky="w", pady=4)
        ttk.Entry(form, textvariable=self.tp_z_var).grid(row=3, column=1, sticky="ew", pady=4)
        form.columnconfigure(1, weight=1)

        ttk.Button(
            editor_col,
            text="*联机传送(单机也支持)",
            style="Big.TButton",
            command=self._on_mem_teleport,
        ).pack(anchor="w")

        self._refresh_coord_workspace_groups()

    def _apply_coord_speed_multiplier(self, raw: str) -> None:
        try:
            value = max(0.1, min(10.0, float(raw.strip())))
        except ValueError:
            self._show_result("速度倍率必须是数字。", ok=False)
            return
        self.bridge_speed_var.set(f"{value:g}")
        self.coord_run_speed_var.set(f"{value:g}")
        self.coord_walk_speed_var.set(f"{value:g}")
        self._apply_player_cheats()

    def _apply_coord_jump_multiplier(self, raw: str) -> None:
        try:
            value = max(0.1, min(10.0, float(raw.strip())))
        except ValueError:
            self._show_result("跳跃倍率必须是数字。", ok=False)
            return
        self.bridge_jump_var.set(f"{value:g}")
        self.coord_jump_speed_var.set(f"{value:g}")
        self._apply_player_cheats()

    def _reset_coord_movement_multipliers(self) -> None:
        self.bridge_speed_var.set("1")
        self.bridge_jump_var.set("1")
        self.coord_run_speed_var.set("1")
        self.coord_walk_speed_var.set("1")
        self.coord_jump_speed_var.set("1")
        self._apply_player_cheats()

    def _reindex_coord_workspace_groups(self) -> None:
        self._coord_workspace_group_map = {
            group.name: group for group in self.coord_workspace_groups
        }

    def _save_coord_workspace_action(self) -> None:
        save_coord_workspace(self.coord_workspace_groups)
        self._show_result("坐标工作区已保存。", ok=True)

    def _coord_group_names_workspace(self) -> list[str]:
        return [group.name for group in self.coord_workspace_groups]

    def _selected_coord_workspace_group(self) -> CoordWorkspaceGroup | None:
        if not hasattr(self, "coord_group_listbox"):
            return None
        selection = self.coord_group_listbox.curselection()
        if not selection:
            return self.coord_workspace_groups[0] if self.coord_workspace_groups else None
        index = selection[0]
        if 0 <= index < len(self.coord_workspace_groups):
            return self.coord_workspace_groups[index]
        return None

    def _selected_coord_workspace_entry(self) -> ReferenceCoordEntry | None:
        if not hasattr(self, "coord_item_listbox"):
            return None
        selection = self.coord_item_listbox.curselection()
        if not selection:
            return None
        index = selection[0]
        if 0 <= index < len(self._current_coord_workspace_results):
            return self._current_coord_workspace_results[index]
        return None

    def _refresh_coord_workspace_groups(self) -> None:
        if not hasattr(self, "coord_group_listbox"):
            return
        self.coord_group_listbox.delete(0, "end")
        for name in self._coord_group_names_workspace():
            self.coord_group_listbox.insert("end", name)
        if self.coord_workspace_groups:
            self.coord_group_listbox.selection_set(0)
            self.coord_group_listbox.activate(0)
            self.coord_group_listbox.see(0)
        self._refresh_coord_workspace_items()

    def _refresh_coord_workspace_items(self) -> None:
        if not hasattr(self, "coord_item_listbox"):
            return
        group = self._selected_coord_workspace_group()
        items = list(group.items) if group is not None else []
        self._current_coord_workspace_results = items
        self.coord_item_listbox.delete(0, "end")
        for entry in items:
            self.coord_item_listbox.insert("end", entry.label)
        if items:
            self.coord_item_listbox.selection_set(0)
            self.coord_item_listbox.activate(0)
            self.coord_item_listbox.see(0)
            self._load_coord_workspace_entry(items[0])
        else:
            self.coord_name_var.set("")
            self.tp_x_var.set("")
            self.tp_y_var.set("")
            self.tp_z_var.set("")

    def _load_coord_workspace_entry(self, entry: ReferenceCoordEntry) -> None:
        self.coord_name_var.set(entry.label)
        self.tp_x_var.set(f"{entry.x:g}")
        self.tp_y_var.set(f"{entry.y:g}")
        self.tp_z_var.set(f"{entry.z:g}")

    def _on_select_coord_group(self, _event: tk.Event | None = None) -> None:
        self._refresh_coord_workspace_items()

    def _on_select_coord_item(self, _event: tk.Event | None = None) -> None:
        entry = self._selected_coord_workspace_entry()
        if entry is not None:
            self._load_coord_workspace_entry(entry)

    def _coord_entry_from_form(self, *, group_name: str) -> ReferenceCoordEntry | None:
        label = self.coord_name_var.get().strip()
        if not label:
            self._show_result("请先填写坐标名称。", ok=False)
            return None
        try:
            x = float(self.tp_x_var.get().strip())
            y = float(self.tp_y_var.get().strip())
            z = float(self.tp_z_var.get().strip())
        except ValueError:
            self._show_result("X/Y/Z 坐标必须都是数字。", ok=False)
            return None
        return ReferenceCoordEntry(group=group_name, label=label, x=x, y=y, z=z)

    def _add_coord_group(self) -> None:
        name = simpledialog.askstring("添加分组", "输入新分组名称：", parent=self.root)
        if not name:
            return
        name = name.strip()
        if not name:
            return
        if name in self._coord_workspace_group_map:
            self._show_result("这个分组已经存在。", ok=False)
            return
        self.coord_workspace_groups.append(CoordWorkspaceGroup(name=name))
        self.coord_workspace_groups.sort(
            key=lambda item: (item.name != DEFAULT_GROUP_NAME, item.name.casefold())
        )
        self._reindex_coord_workspace_groups()
        save_coord_workspace(self.coord_workspace_groups)
        self._refresh_coord_workspace_groups()
        self._show_result(f"已添加分组：{name}", ok=True)

    def _rename_coord_group(self) -> None:
        group = self._selected_coord_workspace_group()
        if group is None:
            self._show_result("请先选中一个分组。", ok=False)
            return
        new_name = simpledialog.askstring("重命名分组", "输入新的分组名称：", initialvalue=group.name, parent=self.root)
        if not new_name:
            return
        new_name = new_name.strip()
        if not new_name:
            return
        if new_name != group.name and new_name in self._coord_workspace_group_map:
            self._show_result("这个分组名称已经存在。", ok=False)
            return
        group.name = new_name
        group.items = [
            ReferenceCoordEntry(
                group=new_name,
                label=item.label,
                x=item.x,
                y=item.y,
                z=item.z,
                editable=item.editable,
            )
            for item in group.items
        ]
        self.coord_workspace_groups.sort(
            key=lambda item: (item.name != DEFAULT_GROUP_NAME, item.name.casefold())
        )
        self._reindex_coord_workspace_groups()
        save_coord_workspace(self.coord_workspace_groups)
        self._refresh_coord_workspace_groups()
        self._show_result(f"已重命名分组：{new_name}", ok=True)

    def _remove_coord_group(self) -> None:
        group = self._selected_coord_workspace_group()
        if group is None:
            self._show_result("请先选中一个分组。", ok=False)
            return
        self.coord_workspace_groups = [
            item for item in self.coord_workspace_groups if item.name != group.name
        ]
        if not self.coord_workspace_groups:
            self.coord_workspace_groups = [CoordWorkspaceGroup(name=DEFAULT_GROUP_NAME)]
        self._reindex_coord_workspace_groups()
        save_coord_workspace(self.coord_workspace_groups)
        self._refresh_coord_workspace_groups()
        self._show_result(f"已移除分组：{group.name}", ok=True)

    def _add_coord_workspace_item(self) -> None:
        group = self._selected_coord_workspace_group()
        if group is None:
            self._show_result("请先选中一个分组。", ok=False)
            return
        entry = self._coord_entry_from_form(group_name=group.name)
        if entry is None:
            return
        group.items.append(entry)
        group.items.sort(key=lambda item: item.label.casefold())
        save_coord_workspace(self.coord_workspace_groups)
        self._refresh_coord_workspace_items()
        self._show_result(f"已添加坐标：{entry.label}", ok=True)

    def _update_coord_workspace_item(self) -> None:
        group = self._selected_coord_workspace_group()
        current = self._selected_coord_workspace_entry()
        if group is None or current is None:
            self._show_result("请先在坐标列表里选中一个条目。", ok=False)
            return
        entry = self._coord_entry_from_form(group_name=group.name)
        if entry is None:
            return
        group.items = [
            entry if item.label == current.label and item.x == current.x and item.y == current.y and item.z == current.z else item
            for item in group.items
        ]
        group.items.sort(key=lambda item: item.label.casefold())
        save_coord_workspace(self.coord_workspace_groups)
        self._refresh_coord_workspace_items()
        self._show_result(f"已更新坐标：{entry.label}", ok=True)

    def _remove_coord_workspace_item(self) -> None:
        group = self._selected_coord_workspace_group()
        current = self._selected_coord_workspace_entry()
        if group is None or current is None:
            self._show_result("请先在坐标列表里选中一个条目。", ok=False)
            return
        group.items = [
            item for item in group.items
            if not (
                item.label == current.label
                and item.x == current.x
                and item.y == current.y
                and item.z == current.z
            )
        ]
        save_coord_workspace(self.coord_workspace_groups)
        self._refresh_coord_workspace_items()
        self._show_result(f"已移除坐标：{current.label}", ok=True)

    def _clear_coord_workspace_group(self) -> None:
        group = self._selected_coord_workspace_group()
        if group is None:
            self._show_result("请先选中一个分组。", ok=False)
            return
        group.items = []
        save_coord_workspace(self.coord_workspace_groups)
        self._refresh_coord_workspace_items()
        self._show_result(f"已清空分组：{group.name}", ok=True)

    def _read_coord_into_form(self) -> None:
        self._on_mem_read_pos()

    def _copy_coord_fields(self) -> None:
        raw = f"{self.coord_name_var.get().strip()}\n{self.tp_x_var.get().strip()},{self.tp_y_var.get().strip()},{self.tp_z_var.get().strip()}"
        self.root.clipboard_clear()
        self.root.clipboard_append(raw)
        self._show_result("已复制当前坐标。", ok=True)

    def _paste_coord_fields(self) -> None:
        try:
            text = self.root.clipboard_get()
        except tk.TclError:
            self._show_result("剪贴板里没有可用坐标。", ok=False)
            return
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if not lines:
            self._show_result("剪贴板里没有可用坐标。", ok=False)
            return
        if len(lines) >= 2:
            self.coord_name_var.set(lines[0])
            coord_text = lines[1]
        else:
            coord_text = lines[0]
        parts = coord_text.replace(",", " ").split()
        if len(parts) < 3:
            self._show_result("剪贴板坐标格式不正确。", ok=False)
            return
        self.tp_x_var.set(parts[0])
        self.tp_y_var.set(parts[1])
        self.tp_z_var.set(parts[2])
        self._show_result("已粘贴坐标。", ok=True)

    def _export_coord_workspace(self) -> None:
        path = filedialog.asksaveasfilename(
            title="导出坐标工作区",
            defaultextension=".json",
            filetypes=[("JSON", "*.json")],
        )
        if not path:
            return
        try:
            Path(path).write_text(
                json.dumps(
                    [
                        {
                            "name": group.name,
                            "items": [
                                {
                                    "label": item.label,
                                    "group": item.group,
                                    "x": item.x,
                                    "y": item.y,
                                    "z": item.z,
                                    "editable": item.editable,
                                }
                                for item in group.items
                            ],
                        }
                        for group in self.coord_workspace_groups
                    ],
                    indent=2,
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
        except OSError as error:
            self._show_result(f"导出失败：{error}", ok=False)
            return
        self._show_result("坐标工作区已导出。", ok=True)

    def _build_common_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=16)
        self.notebook.add(tab, text="常用功能")

        ttk.Label(tab, text="常用功能", style="SubHeader.TLabel").pack(anchor="w")
        ttk.Label(
            tab,
            text="绿色的项目支持联机。按参考版思路，这一页只保留高频常用功能，不再放启动器、打开目录这类工具入口。",
            style="Status.TLabel",
            wraplength=860,
            justify="left",
        ).pack(anchor="w", pady=(4, 10))

        supported = ttk.LabelFrame(tab, text="当前已接入的常用功能", padding=(12, 8))
        supported.pack(fill="x", pady=(0, 10))

        self.common_ref_godmode_var = tk.BooleanVar(value=self.cheat_state.godmode)
        self.common_ref_stamina_var = tk.BooleanVar(value=self.cheat_state.inf_stamina)
        self.common_ref_weight_var = tk.BooleanVar(value=self.cheat_state.weight_zero)
        toggle_row = ttk.Frame(supported)
        toggle_row.pack(fill="x", pady=(0, 6))
        ttk.Checkbutton(toggle_row, text="无敌/无视伤害判定", variable=self.common_ref_godmode_var).pack(side="left", padx=(0, 12))
        ttk.Checkbutton(toggle_row, text="无限体力", variable=self.common_ref_stamina_var).pack(side="left", padx=(0, 12))
        ttk.Checkbutton(toggle_row, text="负重清零（拖到物品后生效）", variable=self.common_ref_weight_var).pack(side="left")

        toggle_apply_row = ttk.Frame(supported)
        toggle_apply_row.pack(fill="x", pady=(0, 6))
        ttk.Button(
            toggle_apply_row,
            text="应用当前勾选",
            style="Big.TButton",
            command=self._apply_reference_common_cheats,
        ).pack(side="left", padx=(0, 6))
        ttk.Button(
            toggle_apply_row,
            text="全部关闭",
            style="Quiet.TButton",
            command=self._reset_reference_common_cheats,
        ).pack(side="left")

        command_row = ttk.Frame(supported)
        command_row.pack(fill="x", pady=(6, 6))
        ttk.Button(
            command_row,
            text="耐久度不减",
            style="Quiet.TButton",
            command=lambda: self._send_with_label("@!nodur", "耐久度不减"),
        ).pack(side="left", padx=(0, 6))
        ttk.Button(
            command_row,
            text="无限弹药",
            style="Quiet.TButton",
            command=lambda: self._send_with_label("@!infammo", "无限弹药"),
        ).pack(side="left", padx=(0, 6))
        ttk.Button(
            command_row,
            text="解锁全部配方",
            style="Quiet.TButton",
            command=lambda: self._send_with_label("@!unlockrecipes", "解锁全部配方"),
        ).pack(side="left", padx=(0, 6))
        ttk.Button(
            command_row,
            text="给满绿胖子像",
            style="Quiet.TButton",
            command=lambda: self._send_with_label("@!giveallstatues", "给满绿胖子像"),
        ).pack(side="left")

        shortcut_row = ttk.Frame(supported)
        shortcut_row.pack(fill="x")
        ttk.Button(
            shortcut_row,
            text="解锁传送点",
            style="Quiet.TButton",
            command=self._on_unlock_fast_travel,
        ).pack(side="left", padx=(0, 6))
        ttk.Button(
            shortcut_row,
            text="解锁全部科技",
            style="Quiet.TButton",
            command=self._on_unlock_all_tech,
        ).pack(side="left", padx=(0, 6))
        ttk.Button(
            shortcut_row,
            text="白天 6:00",
            style="Quiet.TButton",
            command=lambda: self._on_set_time(6),
        ).pack(side="left", padx=(0, 6))
        ttk.Button(
            shortcut_row,
            text="黑夜 0:00",
            style="Quiet.TButton",
            command=lambda: self._on_set_time(0),
        ).pack(side="left")

        ttk.Label(
            tab,
            text="参考版里还有食物腐烂、捕获概率、建造限制等更多常驻项；这轮先把当前仓库底层已经真正接上的常用链路摆正，并把额外工具入口从主流程移走。",
            style="Status.TLabel",
            wraplength=860,
            justify="left",
        ).pack(anchor="w")

    def _build_tech_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=16)
        self.notebook.add(tab, text="制作和建造")

        ttk.Label(tab, text="制作和建造", style="SubHeader.TLabel").pack(anchor="w")
        ttk.Label(
            tab,
            text="参考版这一页以建造限制和配方相关项为主。当前仓库里已经稳定可用的是“解锁配方/样式”链路，所以先把它放到最前面，不再继续显示旧版科技页那套不对位入口。",
            style="Status.TLabel",
            wraplength=860,
            justify="left",
        ).pack(anchor="w", pady=(4, 10))

        supported = ttk.LabelFrame(tab, text="当前已接入的制作/建造功能", padding=(12, 8))
        supported.pack(fill="x", pady=(0, 10))
        ttk.Button(
            supported,
            text="制作和建造无视需求（重启游戏还原）",
            style="Big.TButton",
            command=lambda: self._send_with_label("@!unlockrecipes", "制作和建造无视需求"),
        ).pack(anchor="w", fill="x", pady=(0, 6))
        ttk.Button(
            supported,
            text="*临时解锁全建造和制作样式",
            style="Big.TButton",
            command=lambda: self._send_with_label("@!unlockrecipes", "临时解锁全建造和制作样式"),
        ).pack(anchor="w", fill="x")

        ttk.Label(
            tab,
            text="无视重叠、无视地面、无视基地范围等深度建造限制项，当前桥接层还没有稳定接出对应底层，所以这一页先不伪装成全部可用。",
            style="Status.TLabel",
            wraplength=860,
            justify="left",
        ).pack(anchor="w")

    def _build_pal_edit_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=16)
        self.notebook.add(tab, text="帕鲁修改")

        ttk.Label(tab, text="帕鲁修改", style="SubHeader.TLabel").pack(anchor="w")
        ttk.Label(
            tab,
            text="参考版这一页会在背包帕鲁详情页里读写更多属性。当前开源版先把页内结构、命名和主流程对齐，避免继续保留旧版占位说明。",
            style="Status.TLabel",
            wraplength=860,
            justify="left",
        ).pack(anchor="w", pady=(4, 10))

        actions = ttk.Frame(tab)
        actions.pack(fill="x", pady=(0, 10))
        ttk.Button(
            actions,
            text="打开 *添加帕鲁",
            style="Big.TButton",
            command=lambda: self.notebook.select(TAB_NAMES.index("pals")),
        ).pack(side="left", padx=(0, 6))
        ttk.Button(
            actions,
            text="刷新状态",
            style="Quiet.TButton",
            command=self._refresh_status,
        ).pack(side="left")

        inner = ttk.Notebook(tab)
        inner.pack(fill="both", expand=True)
        for title in REFERENCE_PAL_EDIT_TABS:
            frame = ttk.Frame(inner, padding=12)
            inner.add(frame, text=title)
            ttk.Label(
                frame,
                text="这一页的深度读写功能需要继续并到参考版同等级的底层支持上；当前先完成页面结构和主流程去重，不再保留旧版误导性入口。",
                style="Status.TLabel",
                wraplength=820,
                justify="left",
            ).pack(anchor="w")

    def _build_online_pal_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=16)
        self.notebook.add(tab, text="*联机帕鲁修改")

        ttk.Label(tab, text="*联机帕鲁修改", style="SubHeader.TLabel").pack(anchor="w")
        ttk.Label(
            tab,
            text="参考版把联机帕鲁修改单独放成顶层页签。当前开源版先保留这个结构入口，并把常用生成/联机功能页串起来，避免继续显示旧占位说明。",
            style="Status.TLabel",
            wraplength=860,
            justify="left",
        ).pack(anchor="w", pady=(4, 10))

        row = ttk.Frame(tab)
        row.pack(fill="x")
        ttk.Button(
            row,
            text="打开 *添加帕鲁",
            style="Big.TButton",
            command=lambda: self.notebook.select(TAB_NAMES.index("pals")),
        ).pack(side="left", padx=(0, 6))
        ttk.Button(
            row,
            text="打开 联机功能",
            style="Quiet.TButton",
            command=lambda: self.notebook.select(TAB_NAMES.index("online")),
        ).pack(side="left", padx=(0, 6))
        ttk.Button(
            row,
            text="刷新状态",
            style="Quiet.TButton",
            command=self._refresh_status,
        ).pack(side="left")

    def _apply_reference_common_cheats(self) -> None:
        self.bridge_godmode_var.set(bool(self.common_ref_godmode_var.get()))
        self.bridge_stamina_var.set(bool(self.common_ref_stamina_var.get()))
        self.bridge_weight_var.set(bool(self.common_ref_weight_var.get()))
        self._apply_player_cheats()

    def _reset_reference_common_cheats(self) -> None:
        self.common_ref_godmode_var.set(False)
        self.common_ref_stamina_var.set(False)
        self.common_ref_weight_var.set(False)
        self.bridge_speed_var.set("1")
        self.bridge_jump_var.set("1")
        self._apply_reference_common_cheats()

    def _build_online_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=16)
        self.notebook.add(tab, text="联机功能")

        ttk.Label(tab, text="联机功能", style="SubHeader.TLabel").pack(anchor="w")
        ttk.Label(
            tab,
            text="下面带 * 的功能需要更深的联机链路。当前开源版先把玩家修改这一页里已经稳定的飞行、经验、移速和体力链路对齐出来。",
            style="Status.TLabel",
            wraplength=860,
            justify="left",
        ).pack(anchor="w", pady=(4, 10))

        inner = ttk.Notebook(tab)
        inner.pack(fill="both", expand=True)
        player_tab = ttk.Frame(inner, padding=12)
        other_tab = ttk.Frame(inner, padding=12)
        esp_tab = ttk.Frame(inner, padding=12)
        inner.add(player_tab, text=REFERENCE_ONLINE_TABS[0])
        inner.add(other_tab, text=REFERENCE_ONLINE_TABS[1])
        inner.add(esp_tab, text=REFERENCE_ONLINE_TABS[2])

        top_row = ttk.Frame(player_tab)
        top_row.pack(fill="x", pady=(0, 8))
        self.online_fly_var = tk.BooleanVar(value=False)
        ttk.Button(
            top_row,
            text="切换飞行 Alt+F",
            style="Big.TButton",
            command=self._toggle_online_fly,
        ).pack(side="left", padx=(0, 6))
        ttk.Button(
            top_row,
            text="灵魂出窍（脱困） Alt+G",
            style="Quiet.TButton",
            command=lambda: self._send_with_label(cmd.unstuck(), "灵魂出窍/脱困"),
        ).pack(side="left", padx=(0, 6))

        exp_row = ttk.Frame(player_tab)
        exp_row.pack(fill="x", pady=(0, 8))
        ttk.Label(exp_row, text="经验").pack(side="left")
        self.exp_var = tk.StringVar(value=str(self.settings.custom_exp_amount))
        ttk.Entry(exp_row, textvariable=self.exp_var, width=12).pack(side="left", padx=(6, 8))
        ttk.Button(
            exp_row,
            text="*增加经验",
            style="Big.TButton",
            command=self._on_give_custom_exp,
        ).pack(side="left")

        speed_row = ttk.Frame(player_tab)
        speed_row.pack(fill="x", pady=(0, 8))
        self.online_speed_enabled_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(speed_row, text="速度倍率", variable=self.online_speed_enabled_var).pack(side="left")
        self.online_speed_var = tk.StringVar(value=f"{self.cheat_state.speed_multiplier:g}")
        ttk.Entry(speed_row, textvariable=self.online_speed_var, width=10).pack(side="left", padx=(6, 8))
        ttk.Button(
            speed_row,
            text="设置",
            style="Quiet.TButton",
            command=lambda: self._apply_coord_speed_multiplier(self.online_speed_var.get()),
        ).pack(side="left", padx=(0, 16))

        self.online_stamina_var = tk.BooleanVar(value=self.cheat_state.inf_stamina)
        ttk.Checkbutton(
            speed_row,
            text="无限体力",
            variable=self.online_stamina_var,
            command=self._apply_online_stamina_toggle,
        ).pack(side="left")

        ttk.Label(
            player_tab,
            text="昵称、攻击增加、防御增加等参考版联机项在当前仓库里还没有稳定底层，这一轮不再伪装成可用按钮。",
            style="Status.TLabel",
            wraplength=820,
            justify="left",
        ).pack(anchor="w")

        ttk.Label(
            other_tab,
            text="其他：先保留常用联机辅助入口。",
            style="Status.TLabel",
        ).pack(anchor="w")
        other_row = ttk.Frame(other_tab)
        other_row.pack(fill="x", pady=(8, 0))
        ttk.Button(
            other_row,
            text="解锁传送点",
            style="Quiet.TButton",
            command=self._on_unlock_fast_travel,
        ).pack(side="left", padx=(0, 6))
        ttk.Button(
            other_row,
            text="读取坐标",
            style="Quiet.TButton",
            command=self._on_mem_read_pos,
        ).pack(side="left", padx=(0, 6))
        ttk.Button(
            other_row,
            text="打开传送页",
            style="Quiet.TButton",
            command=lambda: self.notebook.select(TAB_NAMES.index("coords")),
        ).pack(side="left")

        ttk.Label(
            esp_tab,
            text="*透视：当前开源版还没有稳定接出参考版的透视/ESP 链路，所以这一页先只保留结构，不误导成可用功能。",
            style="Status.TLabel",
            wraplength=820,
            justify="left",
        ).pack(anchor="w")

    def _toggle_online_fly(self) -> None:
        enabled = not bool(self.online_fly_var.get())
        self.online_fly_var.set(enabled)
        self._on_mem_fly(enabled)

    def _apply_online_stamina_toggle(self) -> None:
        self.bridge_stamina_var.set(bool(self.online_stamina_var.get()))
        self._apply_player_cheats()

    def _on_close(self) -> None:
        try:
            self.mem.detach()
        except Exception:  # noqa: BLE001 - best effort on shutdown
            pass
        self._route_stop_event.set()
        if self._ui_call_job is not None:
            try:
                self.root.after_cancel(self._ui_call_job)
            except tk.TclError:
                pass
        if self._mem_refresh_job is not None:
            try:
                self.root.after_cancel(self._mem_refresh_job)
            except tk.TclError:
                pass
        self.root.destroy()

    # ------------------------------------------------------------------
    # Home tab helpers
    # ------------------------------------------------------------------

    def _launch_game(self) -> None:
        if not self.report.game_root_exists or not self.report.game_root:
            self._show_result("还没定位游戏目录，先去 设置 填一下。", ok=False)
            return
        launcher = self.report.game_root / "Palworld.exe"
        if not launcher.exists():
            self._show_result("找不到 Palworld.exe。", ok=False)
            return
        try:
            subprocess.Popen([str(launcher)], cwd=str(self.report.game_root))
        except OSError as error:
            self._show_result(f"启动失败：{error}", ok=False)
            return
        self._show_result("游戏已启动。", ok=True)

    def _open_game_dir(self) -> None:
        if not self.report.game_root_exists or not self.report.game_root:
            self._show_result("还没定位游戏目录。", ok=False)
            return
        try:
            os.startfile(str(self.report.game_root))  # type: ignore[attr-defined]
        except OSError as error:
            self._show_result(f"打开失败：{error}", ok=False)

    def _browse_game_root(self) -> None:
        chosen = filedialog.askdirectory(title="选择游戏安装目录")
        if chosen:
            self.game_root_var.set(chosen)

    def _apply_game_root(self) -> None:
        path = self.game_root_var.get().strip() or None
        self.settings.game_root = path
        save_settings(self.settings)
        self._refresh_status()

    # ------------------------------------------------------------------
    # Command dispatch
    # ------------------------------------------------------------------

    def _send(self, command: str) -> None:
        if not command:
            return
        self._dispatch_hidden_commands([command], label="指令")

    def _send_with_label(self, command: str, label: str) -> None:
        """Dispatch a command and surface its human-readable name in the result bar."""

        if not command:
            return
        self._dispatch_hidden_commands([command], label=label)

    def _on_chat_freeform_send(self) -> None:
        raw = self.chat_freeform_var.get()
        command = cmd.sanitize_command(raw)
        if not command:
            self._show_result("命令不能为空。", ok=False)
            return
        self._remember_chat_history(command)
        self.chat_freeform_var.set("")
        self._send(command)

    def _remember_chat_history(self, command: str) -> None:
        if not hasattr(self, "chat_history_listbox"):
            return
        # Avoid obvious duplicates of the most recent entry.
        if self._chat_history and self._chat_history[0] == command:
            return
        self._chat_history.insert(0, command)
        del self._chat_history[20:]
        self.chat_history_listbox.delete(0, "end")
        for item in self._chat_history:
            self.chat_history_listbox.insert("end", item)

    def _on_chat_history_resend(self) -> None:
        selection = self.chat_history_listbox.curselection()
        if not selection:
            return
        command = self._chat_history[selection[0]]
        self._send(command)

    def _send_many(self, commands: list[str], *, label: str) -> None:
        self._dispatch_hidden_commands(commands, label=label)

    # ------------------------------------------------------------------
    # Status + feedback
    # ------------------------------------------------------------------

    def _refresh_status(self) -> None:
        self.report = scan_environment(self.settings.game_root)
        self.cheat_state = self._load_cheat_state()
        self._rebuild_env_text()
        self._sync_player_cheat_controls()
        self._refresh_player_bridge_status()
        status = self._read_bridge_status()
        hidden_mode = self._hidden_command_dispatch_mode()

        if game_control.is_game_running():
            self.status_game.configure(text="游戏：运行中 ✔", style="Good.TLabel")
        else:
            self.status_game.configure(text="游戏：未运行 ✘", style="Bad.TLabel")

        if not self.report.mods_globally_enabled and self.report.client_cheat_commands_present:
            self.status_cheats.configure(
                text="聊天命令：模组总开关关闭 ⚠",
                style="Warn.TLabel",
            )
        elif (
            self.report.client_cheat_commands_active
            and self.report.game_pid is not None
            and not self.report.ue4ss_live_loaded
        ):
            self.status_cheats.configure(
                text="聊天命令：当前进程未载入 UE4SS ⚠",
                style="Warn.TLabel",
            )
        elif self.report.client_cheat_commands_active and hidden_mode == "bridge":
            self.status_cheats.configure(text="聊天命令：隐藏执行 ✔", style="Good.TLabel")
        elif self.report.client_cheat_commands_active and hidden_mode == "fallback":
            self.status_cheats.configure(text="聊天命令：兼容静默 ✔", style="Good.TLabel")
        elif self.report.client_cheat_commands_active:
            self.status_cheats.configure(
                text="聊天命令：模组在线（等待兼容链路）",
                style="Warn.TLabel",
            )
        elif self.report.client_cheat_commands_present:
            self.status_cheats.configure(text="聊天命令：未启用 ⚠", style="Warn.TLabel")
        else:
            self.status_cheats.configure(text="聊天命令：未安装 ✘", style="Bad.TLabel")

        if status.player_valid and hidden_mode == "bridge":
            self.status_mem.configure(text="增强模块：原生模式 ✔", style="Good.TLabel")
        elif status.player_valid and hidden_mode == "fallback":
            self.status_mem.configure(text="增强模块：兼容模式 ✔", style="Good.TLabel")
        elif status.player_valid:
            self.status_mem.configure(
                text="增强模块：已连接（仅飞行/坐标）",
                style="Warn.TLabel",
            )
        elif self.report.trainer_bridge_deployed and self.report.trainer_bridge_enabled:
            self.status_mem.configure(text="增强模块：已部署，重开游戏后生效 ⚠", style="Warn.TLabel")
        elif self.report.trainer_bridge_target is not None:
            self.status_mem.configure(text="增强模块：未部署 ⚠", style="Warn.TLabel")
        else:
            self.status_mem.configure(text="增强模块：不可用 ✘", style="Bad.TLabel")

    def _rebuild_env_text(self) -> None:
        self.env_text.configure(state="normal")
        self.env_text.delete("1.0", "end")

        lines: list[str] = []
        lines.append(f"游戏根目录: {self.report.game_root or '<未检测到>'}")
        lines.append(f"  启动程序 Palworld.exe: {'是' if self.report.launcher_exists else '否'}")
        lines.append(f"  主程序 Shipping.exe: {'是' if self.report.shipping_exists else '否'}")
        lines.append("")
        lines.append(f"聊天命令模组安装: {'是' if self.report.client_cheat_commands_present else '否'}")
        lines.append(f"模组总开关: {'是' if self.report.mods_globally_enabled else '否'}")
        lines.append(f"聊天命令模组启用: {'是' if self.report.client_cheat_commands_active else '否'}")
        if self.report.game_pid is None:
            lines.append("当前游戏进程: 未运行，无法验证 UE4SS 是否真的载入")
        else:
            lines.append(f"当前游戏进程 PID: {self.report.game_pid}")
            lines.append(f"当前进程已载入 UE4SS: {'是' if self.report.ue4ss_live_loaded else '否'}")
            if self.report.ue4ss_loader_path is not None:
                lines.append(f"载入模块: {self.report.ue4ss_loader_path}")
        if self.report.notes:
            lines.append("")
            lines.append("检测提示：")
            for note in self.report.notes:
                lines.append(f"  • {note}")

        self.env_text.insert("1.0", "\n".join(lines))
        self.env_text.configure(state="disabled")

    def _show_result(self, message: str, *, ok: bool, pending: bool = False) -> None:
        if pending:
            style = "Result.TLabel"
            prefix = "⏳ "
        elif ok:
            style = "Good.TLabel"
            prefix = "✔ "
        else:
            style = "Bad.TLabel"
            prefix = "✘ "
        self.result_label.configure(text=f"{prefix}{message}", style=style)

        if self._result_clear_job is not None:
            try:
                self.root.after_cancel(self._result_clear_job)
            except tk.TclError:
                pass
            self._result_clear_job = None

        if not pending:
            self._result_clear_job = self.root.after(
                RESULT_CLEAR_MS,
                lambda: self.result_label.configure(text="就绪。", style="Status.TLabel"),
            )

    def _on_tab_changed(self, _event: tk.Event) -> None:
        try:
            index = self.notebook.index("current")
        except tk.TclError:
            return
        if 0 <= index < len(TAB_NAMES):
            self.settings.last_tab = TAB_NAMES[index]
            save_settings(self.settings)


class _CustomSlotDialog:
    """Tiny modal dialog that collects (label, current value, freeze target)
    from the user before adding a new custom memory slot.
    """

    def __init__(self, parent: tk.Tk) -> None:
        self.result: tuple[str, str, float, str] | None = None

        top = tk.Toplevel(parent)
        top.title("添加自定义字段")
        top.transient(parent)
        top.resizable(False, False)
        top.grab_set()
        self.top = top

        frame = ttk.Frame(top, padding=(16, 12))
        frame.pack(fill="both", expand=True)

        ttk.Label(
            frame,
            text=(
                "给字段起个中文名字（例如「负重」「饥饿度」「弹药」），"
                "再填入现在游戏里这个数值的**当前值**。添加后会出现一行，"
                "流程和上方固定字段完全一样：首次搜索 → 缩小 → 锁定 → 冻结。\n\n"
                "数据类型：HP/SP/移速等是浮点；帕鲁 IV (0-100) 用字节；"
                "等级/经验用整数。不确定就选浮点（默认）。"
            ),
            wraplength=380,
            justify="left",
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))

        ttk.Label(frame, text="字段名称：").grid(row=1, column=0, sticky="w", pady=4)
        self.label_var = tk.StringVar()
        label_entry = ttk.Entry(frame, textvariable=self.label_var, width=26)
        label_entry.grid(row=1, column=1, sticky="ew", pady=4)

        ttk.Label(frame, text="数据类型：").grid(row=2, column=0, sticky="w", pady=4)
        dtype_options = list(DTYPE_LABELS_CN.values())
        self.dtype_var = tk.StringVar(value=dtype_options[0])
        ttk.Combobox(
            frame,
            textvariable=self.dtype_var,
            values=dtype_options,
            state="readonly",
            width=24,
        ).grid(row=2, column=1, sticky="ew", pady=4)

        ttk.Label(frame, text="当前值（游戏里看到的数字）：").grid(
            row=3, column=0, sticky="w", pady=4
        )
        self.value_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.value_var, width=26).grid(
            row=3, column=1, sticky="ew", pady=4
        )

        ttk.Label(frame, text="冻结目标（默认等于当前值）：").grid(
            row=4, column=0, sticky="w", pady=4
        )
        self.target_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.target_var, width=26).grid(
            row=4, column=1, sticky="ew", pady=4
        )

        btn_row = ttk.Frame(frame)
        btn_row.grid(row=5, column=0, columnspan=2, sticky="e", pady=(10, 0))
        ttk.Button(btn_row, text="添加", command=self._on_ok).pack(side="right", padx=(4, 0))
        ttk.Button(btn_row, text="取消", command=self._on_cancel).pack(side="right")

        top.bind("<Return>", lambda _e: self._on_ok())
        top.bind("<Escape>", lambda _e: self._on_cancel())
        label_entry.focus_set()

        # Center on parent.
        top.update_idletasks()
        try:
            px = parent.winfo_rootx()
            py = parent.winfo_rooty()
            pw = parent.winfo_width()
            ph = parent.winfo_height()
            tw = top.winfo_width()
            th = top.winfo_height()
            top.geometry(f"+{px + (pw - tw) // 2}+{py + (ph - th) // 2}")
        except tk.TclError:
            pass

    def _selected_dtype(self) -> str:
        """Map the localized dropdown label back to a dtype key."""

        selected = self.dtype_var.get()
        for key, label in DTYPE_LABELS_CN.items():
            if label == selected:
                return key
        return "f32"

    def _on_ok(self) -> None:
        label = self.label_var.get().strip()
        value_raw = self.value_var.get().strip()
        target_raw = self.target_var.get().strip()
        dtype = self._selected_dtype()
        if not label:
            return
        try:
            float(value_raw)
        except ValueError:
            return
        if target_raw:
            try:
                target = float(target_raw)
            except ValueError:
                return
        else:
            target = float(value_raw)
        self.result = (label, value_raw, target, dtype)
        self.top.destroy()

    def _on_cancel(self) -> None:
        self.result = None
        self.top.destroy()


def run() -> int:
    from . import __version__

    root = tk.Tk()
    TrainerApp(root, __version__)
    root.mainloop()
    return 0
