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
from .config import TrainerSettings, load_settings, save_settings
from .environment import EnvironmentReport, deploy_bridge, scan_environment


APP_TITLE = "Palworld 修改器"
GITHUB_URL = "https://github.com/Boowenn/Palworld-Trainer"

WINDOW_WIDTH = 960
WINDOW_HEIGHT = 680

RESULT_CLEAR_MS = 6000

TAB_NAMES = ("home", "player", "items", "pals", "tech", "world", "settings")


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

        self._configure_root()
        self._build_style()
        self._build_layout()
        self._refresh_status()

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

        self.status_bridge = ttk.Label(bar, text="UE4SS：检测中", style="Status.TLabel")
        self.status_bridge.pack(side="left", padx=(0, 18))

        self.status_cheats = ttk.Label(bar, text="Cheat：检测中", style="Status.TLabel")
        self.status_cheats.pack(side="left")

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
            ("📦 部署 UE4SS Bridge", self._deploy_bridge),
            ("📂 打开游戏目录", self._open_game_dir),
            ("❓ 显示游戏内命令帮助", lambda: self._send(cmd.help_command())),
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

        ttk.Label(tab, text="玩家操作", style="SubHeader.TLabel").pack(anchor="w")

        quick = ttk.Frame(tab)
        quick.pack(fill="x", pady=(8, 18))

        quick_buttons: list[tuple[str, Callable[[], None]]] = [
            ("🦅 切换飞行 (开)", lambda: self._send(cmd.fly(True))),
            ("🛬 切换飞行 (关)", lambda: self._send(cmd.fly(False))),
            ("📍 打印坐标", lambda: self._send(cmd.get_position())),
            ("🚨 脱困", lambda: self._send(cmd.unstuck())),
            ("🗺 解锁所有传送点", lambda: self._send(cmd.unlock_fast_travel())),
            ("🔬 解锁全部科技", lambda: self._send(cmd.unlock_all_tech())),
        ]
        for index, (label, callback) in enumerate(quick_buttons):
            ttk.Button(quick, text=label, style="Big.TButton", command=callback).grid(
                row=index // 3, column=index % 3, padx=6, pady=6, sticky="ew"
            )
        for col in range(3):
            quick.columnconfigure(col, weight=1)

        ttk.Separator(tab).pack(fill="x", pady=(4, 12))
        ttk.Label(tab, text="经验值", style="SubHeader.TLabel").pack(anchor="w")

        exp_row = ttk.Frame(tab)
        exp_row.pack(fill="x", pady=(8, 6))
        ttk.Button(
            exp_row,
            text="+10,000 经验",
            style="Big.TButton",
            command=lambda: self._send(cmd.give_exp(10000)),
        ).pack(side="left", padx=4)
        ttk.Button(
            exp_row,
            text="+100,000 经验",
            style="Big.TButton",
            command=lambda: self._send(cmd.give_exp(100_000)),
        ).pack(side="left", padx=4)
        ttk.Button(
            exp_row,
            text="+1,000,000 经验",
            style="Big.TButton",
            command=lambda: self._send(cmd.give_exp(1_000_000)),
        ).pack(side="left", padx=4)

        custom_exp = ttk.Frame(tab)
        custom_exp.pack(fill="x", pady=(4, 14))
        ttk.Label(custom_exp, text="自定义经验：").pack(side="left")
        self.exp_var = tk.StringVar(value=str(self.settings.custom_exp_amount))
        ttk.Entry(custom_exp, textvariable=self.exp_var, width=12).pack(side="left", padx=(4, 8))
        ttk.Button(
            custom_exp,
            text="给予",
            style="Big.TButton",
            command=self._on_give_custom_exp,
        ).pack(side="left")

        ttk.Separator(tab).pack(fill="x", pady=(4, 12))
        ttk.Label(tab, text="传送", style="SubHeader.TLabel").pack(anchor="w")

        tp_row = ttk.Frame(tab)
        tp_row.pack(fill="x", pady=(8, 0))
        ttk.Label(tp_row, text="X：").pack(side="left")
        self.tp_x_var = tk.StringVar(value="0")
        ttk.Entry(tp_row, textvariable=self.tp_x_var, width=10).pack(side="left", padx=(2, 8))
        ttk.Label(tp_row, text="Y：").pack(side="left")
        self.tp_y_var = tk.StringVar(value="0")
        ttk.Entry(tp_row, textvariable=self.tp_y_var, width=10).pack(side="left", padx=(2, 8))
        ttk.Label(tp_row, text="Z：").pack(side="left")
        self.tp_z_var = tk.StringVar(value="0")
        ttk.Entry(tp_row, textvariable=self.tp_z_var, width=10).pack(side="left", padx=(2, 8))
        ttk.Button(
            tp_row, text="传送到坐标", style="Big.TButton", command=self._on_teleport
        ).pack(side="left", padx=(6, 0))

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

    def _on_teleport(self) -> None:
        try:
            x = float(self.tp_x_var.get())
            y = float(self.tp_y_var.get())
            z = float(self.tp_z_var.get())
        except ValueError:
            self._show_result("坐标必须是数字。", ok=False)
            return
        self._send(cmd.teleport(x, y, z))

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

    def _deploy_bridge(self) -> None:
        ok, message = deploy_bridge(self.report)
        self._show_result(message, ok=ok)
        self._refresh_status()

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

        if self.report.ue4ss_root_exists:
            self.status_bridge.configure(text="UE4SS：已安装 ✔", style="Good.TLabel")
        else:
            self.status_bridge.configure(text="UE4SS：未安装 ✘", style="Bad.TLabel")

        if self.report.client_cheat_commands_active:
            self.status_cheats.configure(text="Cheat 命令：已启用 ✔", style="Good.TLabel")
        elif self.report.client_cheat_commands_present:
            self.status_cheats.configure(text="Cheat 命令：未启用 ⚠", style="Warn.TLabel")
        else:
            self.status_cheats.configure(text="Cheat 命令：未安装 ✘", style="Bad.TLabel")

    def _rebuild_env_text(self) -> None:
        self.env_text.configure(state="normal")
        self.env_text.delete("1.0", "end")

        lines: list[str] = []
        lines.append(f"游戏根目录: {self.report.game_root or '<未检测到>'}")
        lines.append(f"  Palworld.exe 存在: {'是' if self.report.launcher_exists else '否'}")
        lines.append(f"  Shipping.exe 存在: {'是' if self.report.shipping_exists else '否'}")
        lines.append("")
        lines.append(f"UE4SS 根目录存在: {'是' if self.report.ue4ss_root_exists else '否'}")
        lines.append(
            f"ClientCheatCommands 安装: {'是' if self.report.client_cheat_commands_present else '否'}"
        )
        lines.append(
            f"ClientCheatCommands 启用: {'是' if self.report.client_cheat_commands_active else '否'}"
        )
        lines.append(f"Bridge 已部署: {'是' if self.report.trainer_bridge_deployed else '否'}")
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


def run() -> int:
    from . import __version__

    root = tk.Tk()
    TrainerApp(root, __version__)
    root.mainloop()
    return 0
