from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .config import save_settings
from .environment import build_module_statuses, scan_environment
from .models import EnvironmentReport, TrainerSettings


class TrainerApp:
    def __init__(self, settings: TrainerSettings) -> None:
        self.settings = settings
        self.report = scan_environment(settings)

        self.root = tk.Tk()
        self.root.title("Palworld Trainer")
        self.root.geometry("980x720")
        self.root.minsize(920, 660)
        self.root.configure(bg="#11161f")

        self.status_var = tk.StringVar(value="Ready")
        self.game_root_var = tk.StringVar(value=str(self.report.game_root) if self.report.game_root else "")

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
            text="Module 1 focuses on environment detection, trainer shell scaffolding, and packaging support.",
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
        self.notebook = notebook

        self.overview_tab = ttk.Frame(notebook, padding=12)
        self.modules_tab = ttk.Frame(notebook, padding=12)
        self.log_tab = ttk.Frame(notebook, padding=12)
        notebook.add(self.overview_tab, text="Overview")
        notebook.add(self.modules_tab, text="Modules")
        notebook.add(self.log_tab, text="Notes")

        self._build_overview_tab()
        self._build_modules_tab()
        self._build_log_tab()

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

    def _build_modules_tab(self) -> None:
        self.modules_container = ttk.Frame(self.modules_tab)
        self.modules_container.pack(fill=tk.BOTH, expand=True)

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

    def refresh_environment(self, save_after: bool = True) -> None:
        self.settings.game_root = self.game_root_var.get().strip() or None
        self.report = scan_environment(self.settings)

        if save_after:
            save_settings(self.settings)

        self._render_summary(self.report)
        self._render_modules(self.report)
        self._render_notes(self.report)

        detected = str(self.report.game_root) if self.report.game_root else "Not detected"
        self.game_root_var.set(detected if detected != "Not detected" else self.game_root_var.get())
        self.status_var.set(f"Environment scan completed. Game root: {detected}")

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
            f"UE4SSExperimentalPW    : {'Enabled' if report.active_ue4ss_experimental else 'Not enabled'}",
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
                "Implement the UE4SS trainer script pack in Module 2.",
                "Add runtime actions for player, world, and overlay controls.",
                "Package the desktop shell into a standalone exe with PyInstaller.",
            ],
        }

        self.notes_text.configure(state=tk.NORMAL)
        self.notes_text.delete("1.0", tk.END)
        self.notes_text.insert("1.0", json.dumps(payload, indent=2, ensure_ascii=False))
        self.notes_text.configure(state=tk.DISABLED)

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
        "notes": report.notes,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Palworld desktop trainer shell")
    parser.add_argument("--self-check", action="store_true", help="Print the environment report as JSON and exit.")
    parser.add_argument("--build", action="store_true", help="Invoke the PowerShell build script and exit.")
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

    app = TrainerApp(settings)
    app.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

