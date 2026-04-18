"""Palworld Trainer — 傻瓜版主界面.

界面分七个 Tab：主页 / 玩家 / 物品 / 帕鲁 / 科技 / 世界 / 设置。
每个按钮背后对应一条 ClientCheatCommands 的 @! 聊天命令，trainer 通过
``game_control.send_chat_command`` 直接打到游戏聊天框里。
"""

from __future__ import annotations

import os
import subprocess
import threading
import tkinter as tk
import webbrowser
from tkinter import filedialog, ttk
from typing import Callable

from . import commands as cmd
from . import game_control
from .catalog import (
    CatalogEntry,
    load_all_catalogs,
    pick_enum_dir,
    search_catalog,
)
from .config import TrainerSettings, config_dir, load_settings, save_settings
from .environment import EnvironmentReport, scan_environment
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


APP_TITLE = "Palworld 修改器"
GITHUB_URL = "https://github.com/Boowenn/Palworld-Trainer"

WINDOW_WIDTH = 960
WINDOW_HEIGHT = 680

RESULT_CLEAR_MS = 6000

TAB_NAMES = (
    "home",
    "player",
    "items",
    "pals",
    "tech",
    "world",
    "enhance",
    "chat",
    "settings",
)


class TrainerApp:
    """The top-level tkinter application."""

    def __init__(self, root: tk.Tk, version: str) -> None:
        self.root = root
        self.version = version
        self.settings: TrainerSettings = load_settings()
        self.report: EnvironmentReport = scan_environment(self.settings.game_root)

        enum_dir = pick_enum_dir(self.report.client_cheat_commands_enum_dir)
        self.catalogs = load_all_catalogs(enum_dir)

        self.item_entries = self.catalogs.get("item", [])
        self.pal_entries = self.catalogs.get("pal", [])
        self.tech_entries = self.catalogs.get("technology", [])

        self._current_item_results: list[CatalogEntry] = []
        self._current_pal_results: list[CatalogEntry] = []
        self._current_tech_results: list[CatalogEntry] = []
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

        self._configure_root()
        self._build_style()
        self._build_layout()
        self._refresh_status()
        self._schedule_mem_refresh()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------
    # Window setup
    # ------------------------------------------------------------------

    def _configure_root(self) -> None:
        self.root.title(f"{APP_TITLE}  v{self.version}")
        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.root.minsize(820, 580)
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

        link = ttk.Label(header, text="GitHub", foreground="#2563eb", cursor="hand2")
        link.pack(side="right")
        link.bind("<Button-1>", lambda _event: webbrowser.open(GITHUB_URL))

    def _build_status_bar(self, parent: ttk.Frame) -> None:
        bar = ttk.Frame(parent, style="Card.TFrame", padding=(12, 10))
        bar.pack(fill="x")

        self.status_game = ttk.Label(bar, text="游戏：检测中", style="Status.TLabel")
        self.status_game.pack(side="left", padx=(0, 18))

        self.status_cheats = ttk.Label(bar, text="聊天命令：检测中", style="Status.TLabel")
        self.status_cheats.pack(side="left", padx=(0, 18))

        self.status_mem = ttk.Label(bar, text="外挂：未连接", style="Status.TLabel")
        self.status_mem.pack(side="left")

        ttk.Button(bar, text="刷新状态", style="Quiet.TButton", command=self._refresh_status).pack(
            side="right"
        )

    def _build_notebook(self, parent: ttk.Frame) -> None:
        self.notebook = ttk.Notebook(parent)
        self.notebook.pack(fill="both", expand=True, pady=(10, 8))

        self._build_home_tab()
        self._build_player_tab()
        self._build_items_tab()
        self._build_pals_tab()
        self._build_tech_tab()
        self._build_world_tab()
        self._build_enhance_tab()
        self._build_chat_tab()
        self._build_settings_tab()

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

    def _build_home_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=16)
        self.notebook.add(tab, text="主页")

        ttk.Label(tab, text="欢迎使用 Palworld 修改器", style="SubHeader.TLabel").pack(anchor="w")
        ttk.Label(
            tab,
            text=(
                "使用流程：\n"
                "  1) 先启动 Palworld 并进入世界。\n"
                "  2) 切换到本程序，点任意功能按钮。\n"
                "  3) 程序会自动把游戏窗口拉到前台，并把命令打进聊天框。\n\n"
                "前提条件：\n"
                "  • 已安装 UE4SS Experimental (Palworld)。\n"
                "  • 已安装 ClientCheatCommands 并在 PalModSettings.ini 中启用。\n"
                "  • 游戏内聊天默认打开键是回车。"
            ),
            justify="left",
            style="Status.TLabel",
        ).pack(anchor="w", pady=(6, 16))

        ttk.Label(tab, text="一键操作", style="SubHeader.TLabel").pack(anchor="w")

        grid = ttk.Frame(tab)
        grid.pack(fill="x", pady=(8, 0))

        buttons: list[tuple[str, Callable[[], None]]] = [
            ("🚀 启动 Palworld", self._launch_game),
            ("🎮 连接游戏（外挂）", self._on_mem_attach),
            ("📂 打开游戏目录", self._open_game_dir),
        ]
        for index, (label, callback) in enumerate(buttons):
            ttk.Button(grid, text=label, style="Big.TButton", command=callback).grid(
                row=index // 2, column=index % 2, padx=6, pady=6, sticky="ew"
            )
        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, weight=1)

    def _build_player_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=16)
        self.notebook.add(tab, text="玩家")

        ttk.Label(
            tab, text="玩家操作（纯内存注入，无需 mod）", style="SubHeader.TLabel"
        ).pack(anchor="w")

        # ---- Memory Fly ----
        fly_frame = ttk.LabelFrame(tab, text="飞行切换", padding=(12, 8))
        fly_frame.pack(fill="x", pady=(8, 10))

        ttk.Label(
            fly_frame,
            text=(
                "校准：站着不动 → 填 1 → 首次搜索 → 跳起来（空中=3）"
                " → 填 3 → 缩小 → 落地后填 1 → 缩小 → 锁定。"
            ),
            style="Status.TLabel",
            wraplength=840,
        ).pack(anchor="w", pady=(0, 4))

        mode_grid = ttk.Frame(fly_frame)
        mode_grid.pack(fill="x", pady=(0, 6))
        self._build_mem_slot_row(mode_grid, 0, "move_mode")
        mode_grid.columnconfigure(1, weight=1)

        fly_btns = ttk.Frame(fly_frame)
        fly_btns.pack(fill="x")
        ttk.Button(
            fly_btns, text="🦅 开启飞行", style="Big.TButton",
            command=lambda: self._on_mem_fly(True),
        ).pack(side="left", padx=4)
        ttk.Button(
            fly_btns, text="🛬 关闭飞行", style="Big.TButton",
            command=lambda: self._on_mem_fly(False),
        ).pack(side="left", padx=4)

        # ---- Memory Teleport ----
        tp_frame = ttk.LabelFrame(tab, text="传送", padding=(12, 8))
        tp_frame.pack(fill="x", pady=(0, 10))

        ttk.Label(
            tp_frame,
            text=(
                "校准：读取当前 X 坐标 → 填入 → 首次搜索 → 移动后读新值"
                " → 填入 → 缩小 → 锁定。Y、Z 同理。三轴锁定后可传送。"
            ),
            style="Status.TLabel",
            wraplength=840,
        ).pack(anchor="w", pady=(0, 4))

        pos_grid = ttk.Frame(tp_frame)
        pos_grid.pack(fill="x", pady=(0, 6))
        for row_idx, slot in enumerate(POSITION_SLOTS):
            self._build_mem_slot_row(pos_grid, row_idx, slot)
        pos_grid.columnconfigure(1, weight=1)

        tp_row = ttk.Frame(tp_frame)
        tp_row.pack(fill="x", pady=(6, 0))
        ttk.Label(tp_row, text="X：").pack(side="left")
        self.tp_x_var = tk.StringVar(value="0")
        ttk.Entry(tp_row, textvariable=self.tp_x_var, width=10).pack(
            side="left", padx=(2, 8)
        )
        ttk.Label(tp_row, text="Y：").pack(side="left")
        self.tp_y_var = tk.StringVar(value="0")
        ttk.Entry(tp_row, textvariable=self.tp_y_var, width=10).pack(
            side="left", padx=(2, 8)
        )
        ttk.Label(tp_row, text="Z：").pack(side="left")
        self.tp_z_var = tk.StringVar(value="0")
        ttk.Entry(tp_row, textvariable=self.tp_z_var, width=10).pack(
            side="left", padx=(2, 8)
        )
        ttk.Button(
            tp_row, text="📍 读取当前", style="Quiet.TButton",
            command=self._on_mem_read_pos,
        ).pack(side="left", padx=(6, 4))
        ttk.Button(
            tp_row, text="传送到坐标", style="Big.TButton",
            command=self._on_mem_teleport,
        ).pack(side="left", padx=(4, 0))

        # ---- Route teleport (内存注入) ----
        ttk.Separator(tab).pack(fill="x", pady=(4, 8))
        ttk.Label(
            tab, text="路径传送（吸宝箱/吸手记替代方案）", style="SubHeader.TLabel"
        ).pack(anchor="w")
        ttk.Label(
            tab,
            text=(
                "粘贴一组坐标（每行一个 X Y Z），修改器会按顺序自动传送过去，"
                "每个点停留几秒让游戏触发拾取。需要先锁定 pos_x/y/z。"
            ),
            justify="left",
            style="Status.TLabel",
            wraplength=860,
        ).pack(anchor="w", pady=(2, 6))

        route_ctrl = ttk.Frame(tab)
        route_ctrl.pack(fill="x", pady=(2, 4))
        ttk.Label(route_ctrl, text="每点停留（秒）：").pack(side="left")
        self.route_delay_var = tk.StringVar(value="3")
        ttk.Entry(route_ctrl, textvariable=self.route_delay_var, width=5).pack(
            side="left", padx=(2, 10)
        )
        self.route_start_btn = ttk.Button(
            route_ctrl,
            text="▶ 开始路径传送",
            style="Big.TButton",
            command=self._on_route_start,
        )
        self.route_start_btn.pack(side="left", padx=(0, 4))
        self.route_stop_btn = ttk.Button(
            route_ctrl,
            text="⏹ 停止",
            style="Big.TButton",
            command=self._on_route_stop,
            state="disabled",
        )
        self.route_stop_btn.pack(side="left")
        self.route_progress_label = ttk.Label(
            route_ctrl, text="", style="Status.TLabel"
        )
        self.route_progress_label.pack(side="left", padx=(10, 0))

        route_text_frame = ttk.Frame(tab)
        route_text_frame.pack(fill="both", expand=True, pady=(4, 0))
        self.route_text = tk.Text(route_text_frame, height=5, wrap="none")
        self.route_text.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(
            route_text_frame, orient="vertical", command=self.route_text.yview
        )
        self.route_text.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.route_text.insert(
            "1.0",
            "# 每行一个坐标：X Y Z （空格或逗号分隔）\n"
            "# 例如：\n"
            "# -350000 120000 15000\n"
            "# -280000, 85000, 12000\n",
        )
        self._route_stop_event = threading.Event()

    def _build_items_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=16)
        self.notebook.add(tab, text="物品")

        ttk.Label(tab, text="快捷礼包（点一下把整包物品发给自己）", style="SubHeader.TLabel").pack(
            anchor="w"
        )
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

        ttk.Label(tab, text="单件物品查找", style="SubHeader.TLabel").pack(anchor="w")
        ttk.Label(
            tab,
            text=f"当前物品目录共 {len(self.item_entries)} 条。支持模糊搜索。双击列表也会直接给予。",
            style="Status.TLabel",
        ).pack(anchor="w", pady=(2, 8))

        search_row = ttk.Frame(tab)
        search_row.pack(fill="x")
        ttk.Label(search_row, text="搜索：").pack(side="left")
        self.item_search_var = tk.StringVar()
        self.item_search_var.trace_add("write", lambda *_: self._refresh_item_list())
        ttk.Entry(search_row, textvariable=self.item_search_var).pack(
            side="left", padx=(4, 8), fill="x", expand=True
        )
        ttk.Label(search_row, text="数量：").pack(side="left", padx=(10, 0))
        self.item_count_var = tk.StringVar(value=str(self.settings.custom_item_count))
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
        ).pack(side="left")

        self._refresh_item_list()

    def _build_pals_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=16)
        self.notebook.add(tab, text="帕鲁")

        ttk.Label(tab, text="生成帕鲁（仅房主/单机有效）", style="SubHeader.TLabel").pack(anchor="w")
        ttk.Label(
            tab,
            text=f"当前帕鲁目录共 {len(self.pal_entries)} 条。双击列表也会直接生成。",
            style="Status.TLabel",
        ).pack(anchor="w", pady=(2, 8))

        search_row = ttk.Frame(tab)
        search_row.pack(fill="x")
        ttk.Label(search_row, text="搜索：").pack(side="left")
        self.pal_search_var = tk.StringVar()
        self.pal_search_var.trace_add("write", lambda *_: self._refresh_pal_list())
        ttk.Entry(search_row, textvariable=self.pal_search_var).pack(
            side="left", padx=(4, 8), fill="x", expand=True
        )
        ttk.Label(search_row, text="数量：").pack(side="left", padx=(10, 0))
        self.pal_count_var = tk.StringVar(value=str(self.settings.custom_pal_count))
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
        ).pack(side="left")

        self._refresh_pal_list()

    def _build_tech_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=16)
        self.notebook.add(tab, text="科技")

        ttk.Label(tab, text="科技解锁", style="SubHeader.TLabel").pack(anchor="w")

        big_row = ttk.Frame(tab)
        big_row.pack(fill="x", pady=(8, 14))
        ttk.Button(
            big_row,
            text="🔓 解锁全部科技",
            style="Big.TButton",
            command=lambda: self._send(cmd.unlock_all_tech()),
        ).pack(side="left", padx=4)
        ttk.Button(
            big_row,
            text="🗺 解锁全部传送点",
            style="Big.TButton",
            command=lambda: self._send(cmd.unlock_fast_travel()),
        ).pack(side="left", padx=4)

        ttk.Separator(tab).pack(fill="x", pady=(4, 10))
        ttk.Label(tab, text="单项科技解锁", style="SubHeader.TLabel").pack(anchor="w")
        ttk.Label(
            tab,
            text=f"当前科技目录共 {len(self.tech_entries)} 条。",
            style="Status.TLabel",
        ).pack(anchor="w", pady=(2, 8))

        search_row = ttk.Frame(tab)
        search_row.pack(fill="x")
        ttk.Label(search_row, text="搜索：").pack(side="left")
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
        self.time_var = tk.IntVar(value=12)
        ttk.Scale(
            slider_row,
            from_=0,
            to=23,
            orient="horizontal",
            variable=self.time_var,
            command=lambda _value: self._refresh_time_label(),
        ).pack(side="left", fill="x", expand=True)
        self.time_label = ttk.Label(slider_row, text="12 时", width=8, anchor="e")
        self.time_label.pack(side="left", padx=(10, 0))
        ttk.Button(
            slider_row,
            text="设置时间",
            style="Big.TButton",
            command=lambda: self._send(cmd.set_time(self.time_var.get())),
        ).pack(side="left", padx=(10, 0))

        quick = ttk.Frame(tab)
        quick.pack(fill="x", pady=(4, 0))
        for label, hour in (("🌅 清晨 6:00", 6), ("☀️ 正午 12:00", 12), ("🌆 黄昏 18:00", 18), ("🌙 午夜 0:00", 0)):
            ttk.Button(
                quick,
                text=label,
                style="Big.TButton",
                command=lambda h=hour: self._send(cmd.set_time(h)),
            ).pack(side="left", padx=4)

    def _build_enhance_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=16)
        self.notebook.add(tab, text="外挂")

        ttk.Label(
            tab,
            text="直接内存外挂（无需安装任何 mod）",
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
            text="实验性命令（需要 ClientCheatCommands mod 支持）",
            style="SubHeader.TLabel",
        ).pack(anchor="w")
        ttk.Label(
            tab,
            text=(
                "下面这些按钮对应社区公开文档里 CCC mod v2+ 支持的 @! 命令。"
                "不同版本的 mod 未必每条都实现——点了如果没反应，去游戏聊天框看报错，"
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
        ttk.Label(tab, text="自由命令", style="SubHeader.TLabel").pack(anchor="w")
        ttk.Label(
            tab,
            text=(
                "直接输入任意 @! 命令发送给游戏。不用自己加 @! 前缀，"
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
        self.notebook.add(tab, text="设置")

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
        ttk.Button(
            bottom,
            text="访问 GitHub",
            style="Quiet.TButton",
            command=lambda: webbrowser.open(GITHUB_URL),
        ).pack(side="right")

    # ------------------------------------------------------------------
    # List refreshers
    # ------------------------------------------------------------------

    def _refresh_item_list(self) -> None:
        query = self.item_search_var.get()
        results = search_catalog(self.item_entries, query, limit=400)
        self.item_listbox.delete(0, "end")
        for entry in results:
            self.item_listbox.insert("end", f"{entry.label}   [{entry.key}]")
        self._current_item_results = results

    def _refresh_pal_list(self) -> None:
        query = self.pal_search_var.get()
        results = search_catalog(self.pal_entries, query, limit=400)
        self.pal_listbox.delete(0, "end")
        for entry in results:
            self.pal_listbox.insert("end", f"{entry.label}   [{entry.key}]")
        self._current_pal_results = results

    def _refresh_tech_list(self) -> None:
        query = self.tech_search_var.get()
        results = search_catalog(self.tech_entries, query, limit=400)
        self.tech_listbox.delete(0, "end")
        for entry in results:
            self.tech_listbox.insert("end", f"{entry.label}   [{entry.key}]")
        self._current_tech_results = results

    def _refresh_time_label(self) -> None:
        self.time_label.configure(text=f"{self.time_var.get()} 时")

    # ------------------------------------------------------------------
    # Button handlers
    # ------------------------------------------------------------------

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
        self._send(cmd.give_exp(amount))

    def _on_mem_teleport(self) -> None:
        for slot in POSITION_SLOTS:
            if not self.mem.is_locked(slot):
                self._show_result("先锁定 pos_x/y/z 地址，才能传送。", ok=False)
                return
        try:
            x = float(self.tp_x_var.get())
            y = float(self.tp_y_var.get())
            z = float(self.tp_z_var.get())
        except ValueError:
            self._show_result("坐标必须是数字。", ok=False)
            return
        self.mem.write_slot_value("pos_x", x)
        self.mem.write_slot_value("pos_y", y)
        self.mem.write_slot_value("pos_z", z)
        self._show_result(f"已传送到 ({x:g}, {y:g}, {z:g})", ok=True)

    def _on_mem_fly(self, enabled: bool) -> None:
        if not self.mem.is_locked("move_mode"):
            self._show_result("先锁定 move_mode 地址。", ok=False)
            return
        value = 5 if enabled else 1
        self.mem.set_slot_target("move_mode", float(value))
        self.mem.set_slot_freeze("move_mode", True)
        var = self._mem_slot_vars.get("move_mode")
        if var:
            var.set(True)
        entry = self._mem_target_entries.get("move_mode")
        if entry:
            entry.set(str(value))
        label = "飞行" if enabled else "行走"
        self._show_result(f"已切换到{label}模式（move_mode={value}）。", ok=True)

    def _on_mem_read_pos(self) -> None:
        for slot, var in (
            ("pos_x", self.tp_x_var),
            ("pos_y", self.tp_y_var),
            ("pos_z", self.tp_z_var),
        ):
            v = self.mem.read_current_value(slot)
            if v is None:
                self._show_result(f"无法读取 {slot}，先锁定地址。", ok=False)
                return
            var.set(f"{v:g}")
        self._show_result("已读取当前坐标。", ok=True)

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
        for slot in POSITION_SLOTS:
            if not self.mem.is_locked(slot):
                self._show_result("先锁定 pos_x/y/z 地址，才能路径传送。", ok=False)
                return
        coords = self._parse_route_coords()
        if not coords:
            self._show_result("没有有效坐标。每行一组 X Y Z。", ok=False)
            return
        try:
            delay = max(0.5, float(self.route_delay_var.get()))
        except ValueError:
            delay = 3.0
        self._route_stop_event.clear()
        self.route_start_btn.configure(state="disabled")
        self.route_stop_btn.configure(state="normal")
        self._show_result(
            f"路径传送启动：共 {len(coords)} 个点，每点停 {delay:.1f}s。",
            ok=True,
            pending=True,
        )

        def worker() -> None:
            for idx, (x, y, z) in enumerate(coords, 1):
                if self._route_stop_event.is_set():
                    self.root.after(
                        0, lambda: self._route_done(f"路径传送已手动停止（{idx-1}/{len(coords)}）。")
                    )
                    return
                self.root.after(
                    0,
                    lambda i=idx, total=len(coords): self.route_progress_label.configure(
                        text=f"[{i}/{total}]"
                    ),
                )
                ok = (
                    self.mem.write_slot_value("pos_x", x)
                    and self.mem.write_slot_value("pos_y", y)
                    and self.mem.write_slot_value("pos_z", z)
                )
                if not ok:
                    self.root.after(
                        0,
                        lambda: self._route_done(
                            "传送失败：坐标地址未锁定或进程已断开。"
                        ),
                    )
                    return
                # Wait between teleports so the game can trigger pickups
                self._route_stop_event.wait(delay)
            self.root.after(
                0,
                lambda: self._route_done(f"路径传送完成！共 {len(coords)} 个点。"),
            )

        threading.Thread(target=worker, daemon=True).start()

    def _on_route_stop(self) -> None:
        self._route_stop_event.set()

    def _route_done(self, message: str) -> None:
        self.route_start_btn.configure(state="normal")
        self.route_stop_btn.configure(state="disabled")
        self.route_progress_label.configure(text="")
        self._show_result(message, ok=True)

    def _on_give_preset(self, preset: cmd.QuickPreset) -> None:
        commands = cmd.preset_commands(preset)
        if not commands:
            self._show_result(f"{preset.title} 是空包。", ok=False)
            return
        self._send_many(commands, label=f"{preset.title}（共 {len(commands)} 条）")

    def _parse_count(self, raw: str, default: int = 1) -> int:
        try:
            value = int(raw)
            return max(1, value)
        except ValueError:
            return default

    def _on_give_selected_item(self) -> None:
        selection = self.item_listbox.curselection()
        if not selection:
            self._show_result("先在列表里选一项物品。", ok=False)
            return
        entry = self._current_item_results[selection[0]]
        count = self._parse_count(self.item_count_var.get())
        self.settings.custom_item_count = count
        self._remember_recent(self.settings.recent_item_ids, entry.key)
        save_settings(self.settings)
        self._send(cmd.giveme(entry.key, count))

    def _on_spawn_selected_pal(self) -> None:
        selection = self.pal_listbox.curselection()
        if not selection:
            self._show_result("先在列表里选一只帕鲁。", ok=False)
            return
        entry = self._current_pal_results[selection[0]]
        count = self._parse_count(self.pal_count_var.get())
        self.settings.custom_pal_count = count
        self._remember_recent(self.settings.recent_pal_ids, entry.key)
        save_settings(self.settings)
        self._send(cmd.spawn_pal(entry.key, count))

    def _on_unlock_selected_tech(self) -> None:
        selection = self.tech_listbox.curselection()
        if not selection:
            self._show_result("先在列表里选一项科技。", ok=False)
            return
        entry = self._current_tech_results[selection[0]]
        self._send(cmd.unlock_tech(entry.key))

    def _remember_recent(self, bucket: list[str], key: str, limit: int = 10) -> None:
        if key in bucket:
            bucket.remove(key)
        bucket.insert(0, key)
        del bucket[limit:]

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
                self.root.after(0, lambda: self._mem_scan_done(slot, None, str(error)))
                return
            self.root.after(0, lambda: self._mem_scan_done(slot, len(snap), None))

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

    def _on_close(self) -> None:
        try:
            self.mem.detach()
        except Exception:  # noqa: BLE001 - best effort on shutdown
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
        self._show_result("已拉起 Palworld.exe。", ok=True)

    def _open_game_dir(self) -> None:
        if not self.report.game_root_exists or not self.report.game_root:
            self._show_result("还没定位游戏目录。", ok=False)
            return
        try:
            os.startfile(str(self.report.game_root))  # type: ignore[attr-defined]
        except OSError as error:
            self._show_result(f"打开失败：{error}", ok=False)

    def _browse_game_root(self) -> None:
        chosen = filedialog.askdirectory(title="选择 Palworld 安装目录")
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
        self._show_result(f"发送中：{command}", ok=True, pending=True)
        threading.Thread(target=self._send_worker, args=(command,), daemon=True).start()

    def _send_with_label(self, command: str, label: str) -> None:
        """Dispatch a command and surface its human-readable name in the result bar."""

        if not command:
            return
        self._show_result(f"发送 {label}：{command}", ok=True, pending=True)
        threading.Thread(target=self._send_worker, args=(command,), daemon=True).start()

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

    def _send_worker(self, command: str) -> None:
        result = game_control.send_chat_command(command)
        self.root.after(0, lambda: self._show_result(result.message, ok=result.ok))

    def _send_many(self, commands: list[str], *, label: str) -> None:
        self._show_result(f"正在发送 {label}…", ok=True, pending=True)

        def worker() -> None:
            results = game_control.send_chat_commands(commands)
            successes = sum(1 for item in results if item.ok)
            ok = successes == len(commands)
            message = (
                f"{label} 发送完成：{successes}/{len(commands)} 成功"
                if successes
                else (results[0].message if results else "未发送。")
            )
            self.root.after(0, lambda: self._show_result(message, ok=ok))

        threading.Thread(target=worker, daemon=True).start()

    # ------------------------------------------------------------------
    # Status + feedback
    # ------------------------------------------------------------------

    def _refresh_status(self) -> None:
        self.report = scan_environment(self.settings.game_root)
        self._rebuild_env_text()

        if game_control.is_game_running():
            self.status_game.configure(text="游戏：运行中 ✔", style="Good.TLabel")
        else:
            self.status_game.configure(text="游戏：未运行 ✘", style="Bad.TLabel")

        if self.report.client_cheat_commands_active:
            self.status_cheats.configure(text="聊天命令：已启用 ✔", style="Good.TLabel")
        elif self.report.client_cheat_commands_present:
            self.status_cheats.configure(text="聊天命令：未启用 ⚠", style="Warn.TLabel")
        else:
            self.status_cheats.configure(text="聊天命令：未安装 ✘", style="Bad.TLabel")

        if self.mem.is_attached():
            pid = self.mem.pid()
            self.status_mem.configure(text=f"外挂：已连接 PID={pid} ✔", style="Good.TLabel")
        else:
            self.status_mem.configure(text="外挂：未连接", style="Warn.TLabel")

    def _rebuild_env_text(self) -> None:
        self.env_text.configure(state="normal")
        self.env_text.delete("1.0", "end")

        lines: list[str] = []
        lines.append(f"游戏根目录: {self.report.game_root or '<未检测到>'}")
        lines.append(f"  Palworld.exe 存在: {'是' if self.report.launcher_exists else '否'}")
        lines.append(f"  Shipping.exe 存在: {'是' if self.report.shipping_exists else '否'}")
        lines.append("")
        lines.append(
            f"ClientCheatCommands 安装: {'是' if self.report.client_cheat_commands_present else '否'}"
        )
        lines.append(
            f"ClientCheatCommands 启用: {'是' if self.report.client_cheat_commands_active else '否'}"
        )
        lines.append("")
        lines.append("外挂（内存）模块不依赖 UE4SS / mod，只要游戏运行就能在「外挂」Tab 连接。")
        if self.report.notes:
            lines.append("")
            lines.append("说明：")
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
