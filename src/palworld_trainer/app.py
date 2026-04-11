from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from . import __version__
from .catalog import get_catalog_kinds, load_all_catalogs, search_catalog
from .config import save_settings
from .environment import build_module_statuses, scan_environment
from .host_tools import (
    compose_host_command,
    get_host_command_template,
    get_host_command_template_specs,
    get_primary_entry_command,
    render_host_commands_text,
    render_host_entry_text,
    render_host_search_text,
    render_host_templates_text,
)
from .models import CatalogEntry, EnvironmentReport, TrainerSettings
from .runtime import render_runtime_commands_text, render_runtime_presets_text
from .ue4ss import deploy_bridge


class TrainerApp:
    def __init__(self, settings: TrainerSettings) -> None:
        self.settings = settings
        self.report = scan_environment(settings)
        self.host_catalogs: dict[str, list[CatalogEntry]] = {}
        self.host_search_results: list[CatalogEntry] = []
        self.host_catalog_error: str | None = None
        self.host_template_specs = get_host_command_template_specs()
        self.host_template_title_to_key = {spec.title: spec.key for spec in self.host_template_specs}
        self.host_template_key_to_title = {spec.key: spec.title for spec in self.host_template_specs}
        self.tab_titles = ["Overview", "Modules", "Runtime", "Host Tools", "Notes"]

        self.root = tk.Tk()
        self.root.title("Palworld Trainer")
        self.root.geometry("980x720")
        self.root.minsize(920, 660)
        self.root.configure(bg="#11161f")

        self.status_var = tk.StringVar(value="Ready")
        self.game_root_var = tk.StringVar(value=str(self.report.game_root) if self.report.game_root else "")
        self.host_kind_var = tk.StringVar(value="item")
        self.host_query_var = tk.StringVar(value="")
        self.host_result_count_var = tk.StringVar(value="Catalog results will appear here.")
        self.host_template_var = tk.StringVar(value=self.host_template_key_to_title["self_item"])
        self.host_template_summary_var = tk.StringVar(value="")
        self.host_composer_vars = [tk.StringVar() for _ in range(4)]

        self._build_style()
        self._build_layout()
        self.refresh_environment(save_after=False)

    def _build_style(self) -> None:
        style = ttk.Style()
        style.theme_use("clam")

        style.configure(".", background="#11161f", foreground="#e8edf5", fieldbackground="#1a2330")
        style.configure("Card.TFrame", background="#16202b")
        style.configure("Header.TLabel", background="#11161f", foreground="#e8edf5", font=("Segoe UI Semibold", 22))
        style.configure("Muted.TLabel", background="#11161f", foreground="#9db0c7", font=("Segoe UI", 10))
        style.configure("CardTitle.TLabel", background="#16202b", foreground="#f4f7fb", font=("Segoe UI Semibold", 12))
        style.configure("CardBody.TLabel", background="#16202b", foreground="#b9c9dc", font=("Segoe UI", 10))
        style.configure("Accent.TButton", background="#2f8fef", foreground="#ffffff", padding=(12, 8))
        style.map("Accent.TButton", background=[("active", "#4aa0f5")])

    def _build_layout(self) -> None:
        root_frame = ttk.Frame(self.root, padding=18)
        root_frame.pack(fill=tk.BOTH, expand=True)

        top_frame = ttk.Frame(root_frame)
        top_frame.pack(fill=tk.X)

        ttk.Label(top_frame, text="Palworld Trainer", style="Header.TLabel").pack(anchor=tk.W)
        ttk.Label(
            top_frame,
            text=(
                "Modules 1-7 provide the desktop shell, UE4SS bridge deployment, runtime diagnostics, "
                "preset scans, packaging support, host command catalogs, and a command composer."
            ),
            style="Muted.TLabel",
        ).pack(anchor=tk.W, pady=(4, 12))

        controls = ttk.Frame(root_frame)
        controls.pack(fill=tk.X, pady=(0, 12))

        ttk.Label(controls, text="Game Root", style="Muted.TLabel").grid(row=0, column=0, sticky="w")
        entry = ttk.Entry(controls, textvariable=self.game_root_var, width=90)
        entry.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(4, 0), padx=(0, 8))

        ttk.Button(controls, text="Browse", command=self.select_game_root).grid(row=1, column=3, sticky="ew", padx=(0, 8))
        ttk.Button(controls, text="Rescan", command=self.refresh_environment).grid(row=1, column=4, sticky="ew")
        controls.columnconfigure(0, weight=1)

        notebook = ttk.Notebook(root_frame)
        notebook.pack(fill=tk.BOTH, expand=True)
        notebook.bind("<<NotebookTabChanged>>", self.on_tab_changed)
        self.notebook = notebook

        self.overview_tab = ttk.Frame(notebook, padding=12)
        self.modules_tab = ttk.Frame(notebook, padding=12)
        self.runtime_tab = ttk.Frame(notebook, padding=12)
        self.host_tab = ttk.Frame(notebook, padding=12)
        self.log_tab = ttk.Frame(notebook, padding=12)
        notebook.add(self.overview_tab, text="Overview")
        notebook.add(self.modules_tab, text="Modules")
        notebook.add(self.runtime_tab, text="Runtime")
        notebook.add(self.host_tab, text="Host Tools")
        notebook.add(self.log_tab, text="Notes")

        self._build_overview_tab()
        self._build_modules_tab()
        self._build_runtime_tab()
        self._build_host_tab()
        self._build_log_tab()
        self._restore_last_selected_tab()

        status_bar = ttk.Frame(root_frame)
        status_bar.pack(fill=tk.X, pady=(10, 0))
        ttk.Label(status_bar, textvariable=self.status_var, style="Muted.TLabel").pack(side=tk.LEFT)

    def _build_overview_tab(self) -> None:
        self.summary_text = tk.Text(
            self.overview_tab,
            height=18,
            bg="#16202b",
            fg="#e8edf5",
            relief=tk.FLAT,
            wrap=tk.WORD,
            font=("Consolas", 10),
            padx=12,
            pady=12,
        )
        self.summary_text.pack(fill=tk.BOTH, expand=True)

        actions = ttk.Frame(self.overview_tab)
        actions.pack(fill=tk.X, pady=(12, 0))

        ttk.Button(actions, text="Open Repo Root", command=self.open_repo_root).pack(side=tk.LEFT)
        ttk.Button(actions, text="Open Game Root", command=self.open_game_root).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(actions, text="Open UE4SS Mods", command=self.open_ue4ss_mods).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(actions, text="Deploy UE4SS Bridge", command=self.deploy_ue4ss_bridge).pack(side=tk.LEFT, padx=(8, 0))

    def _build_modules_tab(self) -> None:
        self.modules_container = ttk.Frame(self.modules_tab)
        self.modules_container.pack(fill=tk.BOTH, expand=True)

    def _build_runtime_tab(self) -> None:
        actions = ttk.Frame(self.runtime_tab)
        actions.pack(fill=tk.X, pady=(0, 12))

        ttk.Button(actions, text="Open Deployed Bridge", command=self.open_bridge_target).pack(side=tk.LEFT)
        ttk.Button(actions, text="Open Session Log", command=self.open_bridge_log).pack(side=tk.LEFT, padx=(8, 0))

        self.runtime_text = tk.Text(
            self.runtime_tab,
            height=18,
            bg="#16202b",
            fg="#d7e2ef",
            relief=tk.FLAT,
            wrap=tk.WORD,
            font=("Consolas", 10),
            padx=12,
            pady=12,
        )
        self.runtime_text.pack(fill=tk.BOTH, expand=True)

    def _build_host_tab(self) -> None:
        ttk.Label(
            self.host_tab,
            text=(
                "Search the ClientCheatCommands enum catalogs and copy starter commands for "
                "items, pals, and technology unlocks."
            ),
            style="Muted.TLabel",
            wraplength=860,
        ).pack(anchor=tk.W, pady=(0, 8))

        self.host_commands_text = tk.Text(
            self.host_tab,
            height=12,
            bg="#16202b",
            fg="#d7e2ef",
            relief=tk.FLAT,
            wrap=tk.WORD,
            font=("Consolas", 10),
            padx=12,
            pady=12,
        )
        self.host_commands_text.pack(fill=tk.X, expand=False)

        composer = ttk.Frame(self.host_tab)
        composer.pack(fill=tk.X, pady=(12, 10))

        ttk.Label(composer, text="Command Composer", style="CardTitle.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(composer, text="Preset", style="Muted.TLabel").grid(row=1, column=0, sticky="w", pady=(8, 0))

        template_combo = ttk.Combobox(
            composer,
            textvariable=self.host_template_var,
            values=list(self.host_template_title_to_key),
            state="readonly",
            width=28,
        )
        template_combo.grid(row=2, column=0, sticky="ew", padx=(0, 8))
        template_combo.bind("<<ComboboxSelected>>", self.on_host_template_changed)

        ttk.Button(composer, text="Use Selected Asset", command=self.apply_selected_asset_to_template).grid(
            row=2,
            column=1,
            sticky="ew",
            padx=(0, 8),
        )
        ttk.Button(composer, text="Copy Preview", command=self.copy_host_preview_command).grid(row=2, column=2, sticky="ew")

        ttk.Label(
            composer,
            textvariable=self.host_template_summary_var,
            style="Muted.TLabel",
            wraplength=820,
        ).grid(row=3, column=0, columnspan=4, sticky="w", pady=(8, 6))

        self.host_arg_labels: list[ttk.Label] = []
        self.host_arg_entries: list[ttk.Entry] = []
        for index, var in enumerate(self.host_composer_vars):
            label = ttk.Label(composer, text="", style="Muted.TLabel")
            label.grid(row=4, column=index, sticky="w", padx=(0, 8))
            entry = ttk.Entry(composer, textvariable=var, width=18)
            entry.grid(row=5, column=index, sticky="ew", padx=(0, 8))
            entry.bind("<KeyRelease>", self.on_host_composer_input_changed)
            entry.bind("<Return>", self.on_host_composer_input_changed)
            self.host_arg_labels.append(label)
            self.host_arg_entries.append(entry)
            composer.columnconfigure(index, weight=1)

        ttk.Label(composer, text="Preview", style="Muted.TLabel").grid(row=6, column=0, sticky="w", pady=(8, 0))

        self.host_preview_text = tk.Text(
            composer,
            height=3,
            bg="#16202b",
            fg="#e8edf5",
            relief=tk.FLAT,
            wrap=tk.WORD,
            font=("Consolas", 10),
            padx=12,
            pady=12,
        )
        self.host_preview_text.grid(row=7, column=0, columnspan=4, sticky="ew", pady=(4, 0))

        controls = ttk.Frame(self.host_tab)
        controls.pack(fill=tk.X, pady=(12, 8))

        ttk.Label(controls, text="Catalog", style="Muted.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(controls, text="Search", style="Muted.TLabel").grid(row=0, column=1, sticky="w", padx=(8, 0))

        kind_combo = ttk.Combobox(
            controls,
            textvariable=self.host_kind_var,
            values=get_catalog_kinds(),
            state="readonly",
            width=18,
        )
        kind_combo.grid(row=1, column=0, sticky="ew", padx=(0, 8))
        kind_combo.bind("<<ComboboxSelected>>", self.on_host_filters_changed)

        query_entry = ttk.Entry(controls, textvariable=self.host_query_var, width=40)
        query_entry.grid(row=1, column=1, sticky="ew", padx=(0, 8))
        query_entry.bind("<KeyRelease>", self.on_host_filters_changed)
        query_entry.bind("<Return>", self.on_host_filters_changed)

        ttk.Button(controls, text="Search", command=self.refresh_host_results).grid(row=1, column=2, sticky="ew", padx=(0, 8))
        ttk.Button(controls, text="Open Enum Folder", command=self.open_client_cheat_commands_enums).grid(
            row=1,
            column=3,
            sticky="ew",
            padx=(0, 8),
        )
        ttk.Button(controls, text="Copy Asset Key", command=self.copy_selected_asset_key).grid(row=1, column=4, sticky="ew", padx=(0, 8))
        ttk.Button(controls, text="Copy Suggested Command", command=self.copy_selected_host_command).grid(
            row=1,
            column=5,
            sticky="ew",
        )
        controls.columnconfigure(1, weight=1)

        results_frame = ttk.Frame(self.host_tab)
        results_frame.pack(fill=tk.BOTH, expand=True)

        left = ttk.Frame(results_frame)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=False, padx=(0, 10))

        ttk.Label(left, textvariable=self.host_result_count_var, style="Muted.TLabel").pack(anchor=tk.W, pady=(0, 6))

        list_container = ttk.Frame(left)
        list_container.pack(fill=tk.BOTH, expand=True)

        self.host_results_listbox = tk.Listbox(
            list_container,
            width=38,
            bg="#16202b",
            fg="#e8edf5",
            selectbackground="#2f8fef",
            selectforeground="#ffffff",
            relief=tk.FLAT,
            font=("Consolas", 10),
        )
        self.host_results_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.host_results_listbox.bind("<<ListboxSelect>>", self.on_host_selection_changed)

        scrollbar = ttk.Scrollbar(list_container, orient=tk.VERTICAL, command=self.host_results_listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.host_results_listbox.configure(yscrollcommand=scrollbar.set)

        right = ttk.Frame(results_frame)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.host_detail_text = tk.Text(
            right,
            bg="#16202b",
            fg="#d7e2ef",
            relief=tk.FLAT,
            wrap=tk.WORD,
            font=("Consolas", 10),
            padx=12,
            pady=12,
        )
        self.host_detail_text.pack(fill=tk.BOTH, expand=True)

    def _build_log_tab(self) -> None:
        self.notes_text = tk.Text(
            self.log_tab,
            height=18,
            bg="#16202b",
            fg="#d7e2ef",
            relief=tk.FLAT,
            wrap=tk.WORD,
            font=("Consolas", 10),
            padx=12,
            pady=12,
        )
        self.notes_text.pack(fill=tk.BOTH, expand=True)

    def _restore_last_selected_tab(self) -> None:
        if self.settings.last_selected_tab not in self.tab_titles:
            return

        target_index = self.tab_titles.index(self.settings.last_selected_tab)
        self.notebook.select(target_index)

    def on_tab_changed(self, _event: object | None = None) -> None:
        current = self.notebook.tab(self.notebook.select(), "text")
        self.settings.last_selected_tab = current
        save_settings(self.settings)

    def refresh_environment(self, save_after: bool = True) -> None:
        self.settings.game_root = self.game_root_var.get().strip() or None
        self.report = scan_environment(self.settings)
        self._load_host_catalogs()

        if save_after:
            save_settings(self.settings)

        self._render_summary(self.report)
        self._render_modules(self.report)
        self._render_runtime_commands()
        self._render_host_commands()
        self.refresh_host_results()
        self.refresh_host_template_form()
        self._render_notes(self.report)

        detected = str(self.report.game_root) if self.report.game_root else "Not detected"
        self.game_root_var.set(detected if detected != "Not detected" else self.game_root_var.get())
        self.status_var.set(f"Environment scan completed. Game root: {detected}")

    def _load_host_catalogs(self) -> None:
        self.host_catalogs = {}
        self.host_catalog_error = None

        if not self.report.client_cheat_commands_enum_dir_exists or not self.report.client_cheat_commands_enum_dir:
            return

        try:
            self.host_catalogs = load_all_catalogs(self.report.client_cheat_commands_enum_dir)
        except OSError as exc:
            self.host_catalog_error = str(exc)

    def _render_summary(self, report: EnvironmentReport) -> None:
        lines = [
            "Trainer shell status",
            "--------------------",
            f"Repository root        : {report.repo_root}",
            f"Game root              : {report.game_root or 'Not detected'}",
            f"Palworld.exe           : {'OK' if report.launcher_exists else 'Missing'}",
            f"Shipping executable    : {'OK' if report.shipping_exists else 'Missing'}",
            f"Mods folder            : {'OK' if report.mods_root_exists else 'Missing'}",
            f"UE4SS runtime          : {'OK' if report.ue4ss_root_exists else 'Missing'}",
            f"UE4SS mods folder      : {'OK' if report.ue4ss_mods_exists else 'Missing'}",
            f"ClientCheatCommands    : {'Enabled' if report.active_client_cheat_commands else 'Not enabled'}",
            f"CCC mod files          : {'OK' if report.client_cheat_commands_mod_exists else 'Missing'}",
            f"CCC enum catalogs      : {'OK' if report.client_cheat_commands_enum_dir_exists else 'Missing'}",
            f"CCC enum dir           : {report.client_cheat_commands_enum_dir or 'Not detected'}",
            f"UE4SSExperimentalPW    : {'Enabled' if report.active_ue4ss_experimental else 'Not enabled'}",
            f"Bridge source          : {'OK' if report.trainer_bridge_source_exists else 'Missing'}",
            f"Bridge deployed        : {'Yes' if report.trainer_bridge_deployed else 'No'}",
            f"Bridge session log     : {'Present' if report.trainer_bridge_log_exists else 'Not found yet'}",
        ]

        self.summary_text.configure(state=tk.NORMAL)
        self.summary_text.delete("1.0", tk.END)
        self.summary_text.insert("1.0", "\n".join(lines))
        self.summary_text.configure(state=tk.DISABLED)

    def _render_modules(self, report: EnvironmentReport) -> None:
        for child in self.modules_container.winfo_children():
            child.destroy()

        for module in build_module_statuses(report):
            card = ttk.Frame(self.modules_container, style="Card.TFrame", padding=12)
            card.pack(fill=tk.X, pady=(0, 10))

            ttk.Label(card, text=module.title, style="CardTitle.TLabel").pack(anchor=tk.W)
            ttk.Label(card, text=module.description, style="CardBody.TLabel", wraplength=780).pack(anchor=tk.W, pady=(6, 0))
            ttk.Label(card, text=f"Status: {module.status}", style="CardBody.TLabel").pack(anchor=tk.W, pady=(8, 0))

    def _render_notes(self, report: EnvironmentReport) -> None:
        payload = {
            "notes": report.notes,
            "next_steps": [
                "Layer in richer client-facing panels and bookmarkable scan workflows on top of the existing runtime bridge.",
                "Add more curated Palworld-specific helper views while keeping host and client-safe flows separate.",
                "Keep packaging and release automation ready for the next tagged build.",
            ],
        }

        self.notes_text.configure(state=tk.NORMAL)
        self.notes_text.delete("1.0", tk.END)
        self.notes_text.insert("1.0", json.dumps(payload, indent=2, ensure_ascii=False))
        self.notes_text.configure(state=tk.DISABLED)

    def _render_runtime_commands(self) -> None:
        self.runtime_text.configure(state=tk.NORMAL)
        self.runtime_text.delete("1.0", tk.END)
        self.runtime_text.insert("1.0", render_runtime_commands_text())
        self.runtime_text.configure(state=tk.DISABLED)

    def _render_host_commands(self) -> None:
        self.host_commands_text.configure(state=tk.NORMAL)
        self.host_commands_text.delete("1.0", tk.END)
        self.host_commands_text.insert("1.0", render_host_commands_text())
        self.host_commands_text.configure(state=tk.DISABLED)

    def _get_selected_host_template_key(self) -> str:
        return self.host_template_title_to_key[self.host_template_var.get()]

    def refresh_host_template_form(self) -> None:
        spec = get_host_command_template(self._get_selected_host_template_key())
        self.host_template_summary_var.set(f"{spec.category}: {spec.description}")

        for index, (label, entry, var) in enumerate(zip(self.host_arg_labels, self.host_arg_entries, self.host_composer_vars)):
            if index < len(spec.arguments):
                label.configure(text=spec.arguments[index])
                label.grid()
                entry.grid()
            else:
                var.set("")
                label.grid_remove()
                entry.grid_remove()

        self._render_host_command_preview()

    def on_host_filters_changed(self, _event: object | None = None) -> None:
        self.refresh_host_results()

    def on_host_template_changed(self, _event: object | None = None) -> None:
        self.refresh_host_template_form()

    def on_host_composer_input_changed(self, _event: object | None = None) -> None:
        self._render_host_command_preview()

    def refresh_host_results(self) -> None:
        kind = self.host_kind_var.get().strip() or "item"
        query = self.host_query_var.get().strip()
        all_entries = self.host_catalogs.get(kind, [])

        self.host_results_listbox.delete(0, tk.END)
        self.host_search_results = []

        if self.host_catalog_error:
            self.host_result_count_var.set("Catalog load failed.")
            self._render_host_detail_message(
                "Host catalog error\n------------------\n"
                f"{self.host_catalog_error}"
            )
            return

        if not self.report.client_cheat_commands_enum_dir_exists:
            self.host_result_count_var.set("ClientCheatCommands enum catalogs not detected.")
            self._render_host_detail_message(
                render_host_search_text(self.report.client_cheat_commands_enum_dir, kind, query, limit=20)
            )
            return

        self.host_search_results = search_catalog(all_entries, query, limit=120)
        self.host_result_count_var.set(
            f"{len(self.host_search_results)} shown / {len(all_entries)} available in {kind}."
        )

        for entry in self.host_search_results:
            self.host_results_listbox.insert(tk.END, f"{entry.label} [{entry.key}]")

        if not self.host_search_results:
            self._render_host_detail_message(
                render_host_search_text(self.report.client_cheat_commands_enum_dir, kind, query, limit=20)
            )
            return

        self.host_results_listbox.selection_set(0)
        self.host_results_listbox.activate(0)
        self.host_results_listbox.see(0)
        self._render_selected_host_entry(self.host_search_results[0])
        self._render_host_command_preview()

    def on_host_selection_changed(self, _event: object | None = None) -> None:
        entry = self.get_selected_host_entry()
        if not entry:
            return
        self._render_selected_host_entry(entry)
        self._render_host_command_preview()

    def _render_selected_host_entry(self, entry: CatalogEntry) -> None:
        self._render_host_detail_message(render_host_entry_text(entry))

    def _render_host_detail_message(self, text: str) -> None:
        self.host_detail_text.configure(state=tk.NORMAL)
        self.host_detail_text.delete("1.0", tk.END)
        self.host_detail_text.insert("1.0", text)
        self.host_detail_text.configure(state=tk.DISABLED)

    def _get_selected_asset_key_for_template(self) -> str | None:
        spec = get_host_command_template(self._get_selected_host_template_key())
        if not spec.asset_kind:
            return None

        entry = self.get_selected_host_entry()
        if not entry or entry.kind != spec.asset_kind:
            return None

        return entry.key

    def _render_host_command_preview(self) -> None:
        spec = get_host_command_template(self._get_selected_host_template_key())
        values = [var.get() for var in self.host_composer_vars]
        selected_asset_key = self._get_selected_asset_key_for_template()
        preview = compose_host_command(spec.key, values, selected_asset_key=selected_asset_key)

        lines = [preview]
        if selected_asset_key and spec.asset_argument_index is not None:
            asset_value = values[spec.asset_argument_index].strip() if spec.asset_argument_index < len(values) else ""
            if not asset_value:
                lines.extend(["", f"Using selected {spec.asset_kind} asset: {selected_asset_key}"])

        self.host_preview_text.configure(state=tk.NORMAL)
        self.host_preview_text.delete("1.0", tk.END)
        self.host_preview_text.insert("1.0", "\n".join(lines))
        self.host_preview_text.configure(state=tk.DISABLED)

    def get_selected_host_entry(self) -> CatalogEntry | None:
        selection = self.host_results_listbox.curselection()
        if not selection:
            return None

        index = selection[0]
        if index >= len(self.host_search_results):
            return None

        return self.host_search_results[index]

    def select_game_root(self) -> None:
        initial = self.game_root_var.get() or str(self.report.repo_root.parent)
        selected = filedialog.askdirectory(initialdir=initial, title="Select the Palworld game folder")
        if not selected:
            return
        self.game_root_var.set(selected)
        self.refresh_environment()

    def open_repo_root(self) -> None:
        self._open_path(self.report.repo_root)

    def open_game_root(self) -> None:
        if not self.report.game_root:
            messagebox.showwarning("Palworld Trainer", "The game root has not been configured yet.")
            return
        self._open_path(self.report.game_root)

    def open_ue4ss_mods(self) -> None:
        if not self.report.game_root:
            messagebox.showwarning("Palworld Trainer", "The game root has not been configured yet.")
            return

        mods_path = self.report.game_root / "Mods" / "NativeMods" / "UE4SS" / "Mods"
        if not mods_path.exists():
            messagebox.showwarning("Palworld Trainer", "UE4SS Mods folder was not found under the selected game root.")
            return
        self._open_path(mods_path)

    def open_client_cheat_commands_enums(self) -> None:
        if not self.report.client_cheat_commands_enum_dir:
            messagebox.showwarning("Palworld Trainer", "ClientCheatCommands enum directory is not available yet.")
            return

        if not self.report.client_cheat_commands_enum_dir.exists():
            messagebox.showwarning("Palworld Trainer", "ClientCheatCommands enum directory was not found.")
            return

        self._open_path(self.report.client_cheat_commands_enum_dir)

    def deploy_ue4ss_bridge(self) -> None:
        try:
            message = deploy_bridge(self.report)
        except Exception as exc:  # noqa: BLE001 - surface to the UI
            messagebox.showerror("Palworld Trainer", f"Failed to deploy the UE4SS bridge.\n\n{exc}")
            return

        self.refresh_environment()
        messagebox.showinfo("Palworld Trainer", message)

    def open_bridge_target(self) -> None:
        if not self.report.trainer_bridge_target:
            messagebox.showwarning("Palworld Trainer", "Bridge target path is not available yet.")
            return

        if not self.report.trainer_bridge_target.exists():
            messagebox.showwarning("Palworld Trainer", "The bridge has not been deployed yet.")
            return

        self._open_path(self.report.trainer_bridge_target)

    def open_bridge_log(self) -> None:
        if not self.report.trainer_bridge_log_path:
            messagebox.showwarning("Palworld Trainer", "Bridge session log path is not available yet.")
            return

        if not self.report.trainer_bridge_log_path.exists():
            messagebox.showwarning("Palworld Trainer", "The bridge session log has not been created yet.")
            return

        self._open_path(self.report.trainer_bridge_log_path)

    def copy_selected_asset_key(self) -> None:
        entry = self.get_selected_host_entry()
        if not entry:
            messagebox.showwarning("Palworld Trainer", "Select a catalog entry first.")
            return

        self._copy_to_clipboard(entry.key, f"Copied asset key: {entry.key}")

    def copy_selected_host_command(self) -> None:
        entry = self.get_selected_host_entry()
        if not entry:
            messagebox.showwarning("Palworld Trainer", "Select a catalog entry first.")
            return

        command = get_primary_entry_command(entry)
        if not command:
            messagebox.showwarning(
                "Palworld Trainer",
                "No ready-made command template is available for this catalog kind yet.",
            )
            return

        self._copy_to_clipboard(command, f"Copied command template: {command}")

    def apply_selected_asset_to_template(self) -> None:
        spec = get_host_command_template(self._get_selected_host_template_key())
        entry = self.get_selected_host_entry()

        if not entry:
            messagebox.showwarning("Palworld Trainer", "Select a catalog entry first.")
            return

        if spec.asset_kind is None or spec.asset_argument_index is None:
            messagebox.showwarning("Palworld Trainer", "The current template does not accept asset input.")
            return

        if entry.kind != spec.asset_kind:
            messagebox.showwarning(
                "Palworld Trainer",
                f"The current template expects a {spec.asset_kind} entry, but the selection is {entry.kind}.",
            )
            return

        self.host_composer_vars[spec.asset_argument_index].set(entry.key)
        self._render_host_command_preview()

    def copy_host_preview_command(self) -> None:
        spec = get_host_command_template(self._get_selected_host_template_key())
        values = [var.get() for var in self.host_composer_vars]
        selected_asset_key = self._get_selected_asset_key_for_template()
        command = compose_host_command(spec.key, values, selected_asset_key=selected_asset_key)
        self._copy_to_clipboard(command, f"Copied composed command: {command}")

    def _copy_to_clipboard(self, text: str, status: str) -> None:
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.root.update()
        self.status_var.set(status)

    def _open_path(self, path: Path) -> None:
        try:
            os.startfile(path)  # type: ignore[attr-defined]
        except OSError as exc:
            messagebox.showerror("Palworld Trainer", f"Failed to open path:\n{path}\n\n{exc}")

    def run(self) -> None:
        self.root.mainloop()


def build_self_check_payload(settings: TrainerSettings) -> dict[str, object]:
    report = scan_environment(settings)
    return {
        "repo_root": str(report.repo_root),
        "game_root": str(report.game_root) if report.game_root else None,
        "launcher_exists": report.launcher_exists,
        "shipping_exists": report.shipping_exists,
        "ue4ss_root_exists": report.ue4ss_root_exists,
        "active_client_cheat_commands": report.active_client_cheat_commands,
        "active_ue4ss_experimental": report.active_ue4ss_experimental,
        "client_cheat_commands_mod_exists": report.client_cheat_commands_mod_exists,
        "client_cheat_commands_enum_dir_exists": report.client_cheat_commands_enum_dir_exists,
        "client_cheat_commands_enum_dir": (
            str(report.client_cheat_commands_enum_dir) if report.client_cheat_commands_enum_dir else None
        ),
        "trainer_bridge_source_exists": report.trainer_bridge_source_exists,
        "trainer_bridge_deployed": report.trainer_bridge_deployed,
        "trainer_bridge_target": str(report.trainer_bridge_target) if report.trainer_bridge_target else None,
        "trainer_bridge_log_exists": report.trainer_bridge_log_exists,
        "trainer_bridge_log_path": str(report.trainer_bridge_log_path) if report.trainer_bridge_log_path else None,
        "notes": report.notes,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Palworld desktop trainer shell")
    parser.add_argument("--version", action="version", version=f"Palworld Trainer {__version__}")
    parser.add_argument("--self-check", action="store_true", help="Print the environment report as JSON and exit.")
    parser.add_argument("--build", action="store_true", help="Invoke the PowerShell build script and exit.")
    parser.add_argument(
        "--list-runtime-commands",
        action="store_true",
        help="Print the runtime command catalog and exit.",
    )
    parser.add_argument(
        "--list-runtime-presets",
        action="store_true",
        help="Print the runtime preset catalog and exit.",
    )
    parser.add_argument(
        "--list-host-commands",
        action="store_true",
        help="Print the host command catalog and exit.",
    )
    parser.add_argument(
        "--list-host-templates",
        action="store_true",
        help="Print the host command composer templates and exit.",
    )
    parser.add_argument(
        "--search-assets",
        nargs=2,
        metavar=("KIND", "QUERY"),
        help="Search a ClientCheatCommands asset catalog such as item, pal, technology, or npc.",
    )
    parser.add_argument(
        "--compose-host-command",
        nargs="+",
        metavar="PART",
        help="Compose a host command from a named template and optional argument values.",
    )
    parser.add_argument(
        "--search-limit",
        type=int,
        default=20,
        help="Maximum number of asset search results to print with --search-assets.",
    )
    parser.add_argument(
        "--deploy-ue4ss-bridge",
        action="store_true",
        help="Copy the repository UE4SS bridge mod into the configured game root.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    settings = TrainerSettings()

    if args.self_check:
        print(json.dumps(build_self_check_payload(settings), indent=2, ensure_ascii=False))
        return 0

    if args.build:
        repo_root = scan_environment(settings).repo_root
        build_script = repo_root / "scripts" / "build.ps1"
        subprocess.run(
            ["powershell", "-ExecutionPolicy", "Bypass", "-File", str(build_script), "-Clean"],
            check=True,
        )
        return 0

    if args.list_runtime_commands:
        print(render_runtime_commands_text())
        return 0

    if args.list_runtime_presets:
        print(render_runtime_presets_text())
        return 0

    if args.list_host_commands:
        print(render_host_commands_text())
        return 0

    if args.list_host_templates:
        print(render_host_templates_text())
        return 0

    if args.search_assets:
        kind, query = args.search_assets
        report = scan_environment(settings)
        try:
            print(render_host_search_text(report.client_cheat_commands_enum_dir, kind, query, limit=args.search_limit))
        except ValueError as exc:
            print(exc, file=sys.stderr)
            return 2
        return 0

    if args.compose_host_command:
        template, *values = args.compose_host_command
        try:
            print(compose_host_command(template, values))
        except ValueError as exc:
            print(exc, file=sys.stderr)
            return 2
        return 0

    if args.deploy_ue4ss_bridge:
        report = scan_environment(settings)
        print(deploy_bridge(report))
        return 0

    app = TrainerApp(settings)
    app.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
