from __future__ import annotations

import json
import sys
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import tkinter as tk
from tkinter import ttk


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from palworld_trainer import __version__  # noqa: E402
from palworld_trainer import commands as cmd  # noqa: E402
from palworld_trainer import game_control  # noqa: E402
from palworld_trainer.app import TrainerApp  # noqa: E402
from palworld_trainer.reference_parity import (  # noqa: E402
    REFERENCE_ADD_PAL_TABS,
    REFERENCE_ITEM_TABS,
)


BridgeJson = dict[str, object]


@dataclass
class TestResult:
    group: str
    name: str
    ok: bool
    details: str
    evidence: list[str] = field(default_factory=list)


class LiveSmokeHarness:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.withdraw()
        self.app = TrainerApp(self.root, __version__)
        self.pump(0.5)

        self.ue4ss_log = self._must_path(
            self.app.report.game_root / "Mods" / "NativeMods" / "UE4SS" / "UE4SS.log"
        )
        self.bridge_dir = self._must_path(
            self.app.report.game_root
            / "Mods"
            / "NativeMods"
            / "UE4SS"
            / "Mods"
            / "PalworldTrainerBridge"
        )
        self.request_json = self.bridge_dir / "request.json"
        self.toggles_json = self.bridge_dir / "toggles.json"
        self.status_json = self.bridge_dir / "status.json"
        self.session_log = self.bridge_dir / "session.log"
        self._case_context: dict[str, object] = {}

    def bridge_version(self) -> str:
        return str(self.app._read_bridge_status().bridge_version or "")

    def bridge_supports_hidden_commands(self) -> bool:
        return self.app._bridge_supports_hidden_commands()

    def hidden_dispatch_mode(self) -> str:
        return self.app._hidden_command_dispatch_mode()

    def _must_path(self, path: Path | None) -> Path:
        if path is None:
            raise RuntimeError("Required runtime path is missing.")
        return path

    def close(self) -> None:
        try:
            self.app._on_close()
        except Exception:
            try:
                self.root.destroy()
            except Exception:
                pass

    def pump(self, seconds: float = 0.2) -> None:
        deadline = time.time() + seconds
        while time.time() < deadline:
            self.root.update()
            time.sleep(0.02)
        self.root.update()

    def wait_for(
        self,
        predicate: Callable[[], bool],
        *,
        timeout: float = 8.0,
        step: float = 0.05,
    ) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            self.root.update()
            if predicate():
                return True
            time.sleep(step)
        self.root.update()
        return bool(predicate())

    def file_text(self, path: Path) -> str:
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8-sig", errors="replace")

    def file_size(self, path: Path) -> int:
        if not path.exists():
            return 0
        try:
            return path.stat().st_size
        except OSError:
            return 0

    def file_text_from(self, path: Path, start: int) -> str:
        if not path.exists():
            return ""
        try:
            with path.open("rb") as handle:
                handle.seek(max(0, start))
                return handle.read().decode("utf-8", errors="replace")
        except OSError:
            return ""

    def json_obj(self, path: Path) -> BridgeJson:
        if not path.exists():
            return {}
        return json.loads(self.file_text(path))

    def result_text(self) -> str:
        return str(self.app.result_label.cget("text"))

    def run_case(
        self,
        group: str,
        name: str,
        action: Callable[[], None],
        verify: Callable[[], tuple[bool, str, list[str]]],
        *,
        settle: float = 0.35,
    ) -> TestResult:
        before_result = self.result_text()
        self._case_context = {
            "result_text": before_result,
            "ue4ss_log_size": self.file_size(self.ue4ss_log),
            "session_log_size": self.file_size(self.session_log),
            "request_json": self.json_obj(self.request_json),
            "toggles_json": self.json_obj(self.toggles_json),
            "dispatch_mode": self.hidden_dispatch_mode(),
        }
        try:
            action()
            self.pump(settle)
            ok, details, evidence = verify()
            after_result = self.result_text()
            if after_result and after_result != before_result:
                evidence = [*evidence, f"result={ascii(after_result)}"]
            return TestResult(group, name, ok, details, evidence)
        except Exception as error:  # noqa: BLE001
            tb = traceback.format_exc()
            return TestResult(
                group,
                name,
                False,
                f"exception: {error}",
                [ascii(tb[-1200:]), f"result={ascii(self.result_text())}"],
            )

    def verify_log_contains(
        self,
        log_path: Path,
        needle: str,
        *,
        timeout: float = 10.0,
    ) -> tuple[bool, str, list[str]]:
        key = "ue4ss_log_size" if log_path == self.ue4ss_log else "session_log_size"
        before_size = int(self._case_context.get(key, 0))

        def predicate() -> bool:
            return needle in self.file_text_from(log_path, before_size)

        ok = self.wait_for(predicate, timeout=timeout)
        delta = self.file_text_from(log_path, before_size)
        evidence = [
            f"log={log_path.name}",
            f"needle={needle}",
            f"delta={ascii(delta[-400:])}",
        ]
        if ok:
            return True, f"log contains {needle}", evidence
        return False, f"log missing {needle}", evidence

    def verify_request_action(
        self,
        action_name: str,
        *,
        expected_pairs: dict[str, object] | None = None,
        timeout: float = 8.0,
    ) -> tuple[bool, str, list[str]]:
        before_obj = self._case_context.get("request_json", {})
        before = before_obj if isinstance(before_obj, dict) else {}

        def predicate() -> bool:
            data = self.json_obj(self.request_json)
            if data == before:
                return False
            if data.get("action") != action_name:
                return False
            if expected_pairs:
                for key, expected in expected_pairs.items():
                    if data.get(key) != expected:
                        return False
            return True

        ok = self.wait_for(predicate, timeout=timeout)
        data = self.json_obj(self.request_json)
        evidence = [f"request={ascii(data)}"]
        if ok:
            return True, f"request action {action_name}", evidence
        return False, f"request action mismatch for {action_name}", evidence

    def verify_log_not_contains(
        self,
        log_path: Path,
        needle: str,
    ) -> tuple[bool, str, list[str]]:
        key = "ue4ss_log_size" if log_path == self.ue4ss_log else "session_log_size"
        before_size = int(self._case_context.get(key, 0))
        delta = self.file_text_from(log_path, before_size)
        evidence = [
            f"log={log_path.name}",
            f"needle={needle}",
            f"delta={ascii(delta[-400:])}",
        ]
        if needle in delta:
            return False, f"log unexpectedly contains {needle}", evidence
        return True, f"log excludes {needle}", evidence

    def verify_hidden_request_and_no_visible_chat(
        self,
        *,
        commands_text: str | None = None,
        forbidden_needles: list[str],
        timeout: float = 8.0,
    ) -> tuple[bool, str, list[str]]:
        expected_pairs = {"commands_text": commands_text} if commands_text is not None else None
        ok, details, evidence = self.verify_request_action(
            "run_hidden_commands",
            expected_pairs=expected_pairs,
            timeout=timeout,
        )
        if not ok:
            return ok, details, evidence

        request_data = self.json_obj(self.request_json)
        request_id = request_data.get("request_id")
        all_evidence = [*evidence, f"request_id={request_id!r}"]
        for needle in forbidden_needles:
            visible_ok, visible_details, visible_evidence = self.verify_log_not_contains(
                self.ue4ss_log,
                needle,
            )
            all_evidence.extend(visible_evidence)
            if not visible_ok:
                return False, visible_details, all_evidence

        if isinstance(request_id, int):
            executed_ok, executed_details, executed_evidence = self.verify_log_contains(
                self.ue4ss_log,
                f"Hidden-command request #{request_id} executed",
                timeout=timeout,
            )
            all_evidence.extend(executed_evidence)
            if not executed_ok:
                return False, executed_details, all_evidence

        return True, "hidden request executed without visible chat injection", all_evidence

    def verify_log_contains_all(
        self,
        log_path: Path,
        needles: list[str],
        *,
        timeout: float = 8.0,
    ) -> tuple[bool, str, list[str]]:
        key = "ue4ss_log_size" if log_path == self.ue4ss_log else "session_log_size"
        before_size = int(self._case_context.get(key, 0))

        def predicate() -> bool:
            delta = self.file_text_from(log_path, before_size)
            return all(needle in delta for needle in needles)

        ok = self.wait_for(predicate, timeout=timeout)
        delta = self.file_text_from(log_path, before_size)
        evidence = [
            f"log={log_path.name}",
            f"needles={ascii(needles)}",
            f"delta={ascii(delta[-600:])}",
        ]
        if ok:
            return True, f"{log_path.name} contains all expected entries", evidence
        return False, f"{log_path.name} missing expected entries", evidence

    def verify_hidden_command_delivery(
        self,
        commands: list[str],
        *,
        timeout: float = 8.0,
    ) -> tuple[bool, str, list[str]]:
        normalized = [cmd.sanitize_command(command) for command in commands if command.strip()]
        game_running = game_control.is_game_running()
        window_handle = game_control.find_palworld_window()
        if not game_running or not window_handle:
            return (
                False,
                "game process/window missing during live verification",
                [f"game_running={game_running}", f"window_handle={window_handle!r}"],
            )
        mode = str(self._case_context.get("dispatch_mode", self.hidden_dispatch_mode()))
        bridge_ok, bridge_details, bridge_evidence = self.verify_hidden_request_and_no_visible_chat(
            commands_text="\n".join(normalized),
            forbidden_needles=normalized,
            timeout=timeout,
        )
        if bridge_ok:
            return True, bridge_details, [*bridge_evidence, f"dispatch_mode={mode}"]

        def fallback_predicate(log_path: Path) -> tuple[bool, str, list[str]]:
            key = "ue4ss_log_size" if log_path == self.ue4ss_log else "session_log_size"
            before_size = int(self._case_context.get(key, 0))

            def predicate() -> bool:
                delta = self.file_text_from(log_path, before_size)
                if "Suppressed visible chat command via" not in delta:
                    return False
                return all(command in delta for command in normalized)

            ok = self.wait_for(predicate, timeout=timeout)
            delta = self.file_text_from(log_path, before_size)
            evidence = [
                f"log={log_path.name}",
                f"commands={ascii(normalized)}",
                f"delta={ascii(delta[-800:])}",
            ]
            if "Command not registered:" in delta:
                return False, "hidden command was delivered but not registered", evidence
            if ok:
                return True, "fallback command delivery observed in log", evidence
            return False, "hidden command path unavailable", evidence

        for log_path in (self.ue4ss_log, self.session_log):
            ok, details, evidence = fallback_predicate(log_path)
            if ok:
                return ok, details, [*evidence, f"dispatch_mode={mode}"]
        return False, bridge_details, [*bridge_evidence, f"dispatch_mode={mode}"]

    def verify_toggles(
        self,
        expected: dict[str, object],
        *,
        timeout: float = 8.0,
    ) -> tuple[bool, str, list[str]]:
        def predicate() -> bool:
            data = self.json_obj(self.toggles_json)
            return all(data.get(key) == value for key, value in expected.items())

        ok = self.wait_for(predicate, timeout=timeout)
        data = self.json_obj(self.toggles_json)
        evidence = [f"toggles={ascii(data)}"]
        if ok:
            return True, "toggles updated", evidence
        return False, "toggles mismatch", evidence

    def verify_coord_fields_changed(self, before: tuple[str, str, str]) -> tuple[bool, str, list[str]]:
        current = (
            self.app.tp_x_var.get(),
            self.app.tp_y_var.get(),
            self.app.tp_z_var.get(),
        )
        ok = current != before and all(part.strip() for part in current)
        evidence = [f"coords={ascii(current)}"]
        if ok:
            return True, "coord fields updated", evidence
        return False, "coord fields did not change", evidence

    def verify_route_nonempty(self) -> tuple[bool, str, list[str]]:
        text = self.app.route_text.get("1.0", "end").strip()
        ok = bool(text)
        evidence = [f"route={ascii(text[-200:])}"]
        if ok:
            return True, "route text updated", evidence
        return False, "route text empty", evidence

    def verify_mem_attached(self, expected: bool) -> tuple[bool, str, list[str]]:
        attached = self.app.mem.is_attached()
        label = str(self.app.mem_attach_label.cget("text"))
        ok = attached is expected
        evidence = [f"attached={attached}", f"label={ascii(label)}"]
        if ok:
            return True, f"mem attached={expected}", evidence
        return False, f"mem attached expected {expected} got {attached}", evidence

    def select_first_item_search(self, query: str) -> None:
        self.app.item_search_var.set(query)
        self.pump(0.25)
        self.app.item_listbox.selection_clear(0, "end")
        if self.app.item_listbox.size() > 0:
            self.app.item_listbox.selection_set(0)
            self.app.item_listbox.activate(0)
            self.app.item_listbox.event_generate("<<ListboxSelect>>")

    def select_first_pal_search(self, query: str) -> None:
        self.app.pal_search_var.set(query)
        self.pump(0.25)
        self.app.pal_listbox.selection_clear(0, "end")
        if self.app.pal_listbox.size() > 0:
            self.app.pal_listbox.selection_set(0)
            self.app.pal_listbox.activate(0)
            self.app.pal_listbox.event_generate("<<ListboxSelect>>")

    def select_first_tech_search(self, query: str) -> None:
        self.app.tech_search_var.set(query)
        self.pump(0.25)
        self.app.tech_listbox.selection_clear(0, "end")
        if self.app.tech_listbox.size() > 0:
            self.app.tech_listbox.selection_set(0)

    def select_first_subset_search(
        self,
        search_var_name: str,
        listbox_attr: str,
        query: str,
    ) -> None:
        search_var = getattr(self.app, search_var_name)
        listbox = getattr(self.app, listbox_attr)
        search_var.set(query)
        self.pump(0.25)
        listbox.selection_clear(0, "end")
        if listbox.size() > 0:
            listbox.selection_set(0)
            listbox.activate(0)
            listbox.event_generate("<<ListboxSelect>>")

    def select_notebook_tab(self, notebook: ttk.Notebook, text: str) -> None:
        for tab_id in notebook.tabs():
            if notebook.tab(tab_id, "text") == text:
                notebook.select(tab_id)
                self.pump(0.2)
                return
        raise RuntimeError(f"Notebook tab not found: {text}")

    def select_notebook_tab_at(self, notebook: ttk.Notebook, index: int) -> None:
        tabs = notebook.tabs()
        if not tabs:
            raise RuntimeError("Notebook has no tabs.")
        notebook.select(tabs[index])
        self.pump(0.2)

    def select_listbox_index(self, listbox: tk.Listbox, index: int) -> None:
        if listbox.size() <= index:
            raise RuntimeError(f"Listbox index out of range: {index}")
        listbox.selection_clear(0, "end")
        listbox.selection_set(index)
        listbox.activate(index)
        listbox.see(index)
        listbox.event_generate("<<ListboxSelect>>")
        self.pump(0.2)


def main() -> int:
    results: list[TestResult] = []
    harness = LiveSmokeHarness()
    try:
        status = harness.json_obj(harness.status_json)
        current_pos = (
            float(status.get("position_x", 0.0)),
            float(status.get("position_y", 0.0)),
            float(status.get("position_z", 0.0)),
        )
        def add(
            group: str,
            name: str,
            action: Callable[[], None],
            verify: Callable[[], tuple[bool, str, list[str]]],
            *,
            settle: float = 0.35,
        ) -> None:
            results.append(harness.run_case(group, name, action, verify, settle=settle))

        add(
            "about",
            "refresh_status",
            harness.app._refresh_status,
            lambda: (
                bool(harness.app.report.game_root_exists)
                and harness.app._read_bridge_status().player_valid
                and harness.hidden_dispatch_mode() != "none",
                "status refresh complete",
                [
                    f"game_root={ascii(str(harness.app.report.game_root))}",
                    f"player_valid={harness.app._read_bridge_status().player_valid}",
                    f"dispatch_mode={harness.hidden_dispatch_mode()}",
                    f"bridge_version={harness.bridge_version()}",
                ],
            ),
            settle=0.4,
        )
        add(
            "about",
            "environment_text_present",
            lambda: None,
            lambda: (
                bool(harness.app.env_text.get("1.0", "end").strip()),
                "environment text ready",
                [f"env_len={len(harness.app.env_text.get('1.0', 'end').strip())}"],
            ),
        )
        add(
            "changelog",
            "changelog_text_present",
            lambda: None,
            lambda: (
                bool(harness.app.changelog_text.get("1.0", "end").strip()),
                "changelog text ready",
                [f"changelog_len={len(harness.app.changelog_text.get('1.0', 'end').strip())}"],
            ),
        )
        add(
            "common",
            "deploy_bridge",
            harness.app._on_deploy_bridge,
            lambda: (
                harness.app._bridge_runtime_ready(),
                "bridge runtime ready" if harness.app._bridge_runtime_ready() else "bridge runtime not ready",
                [f"bridge_ready={harness.app._bridge_runtime_ready()}"],
            ),
        )

        harness.app.common_ref_godmode_var.set(True)
        harness.app.common_ref_stamina_var.set(True)
        harness.app.common_ref_weight_var.set(True)
        harness.app.bridge_speed_var.set("1.5")
        harness.app.bridge_jump_var.set("1.4")
        add(
            "common",
            "apply_reference_toggles",
            harness.app._apply_reference_common_cheats,
            lambda: harness.verify_toggles(
                {
                    "godmode": True,
                    "inf_stamina": True,
                    "weight_zero": True,
                    "speed_multiplier": 1.5,
                    "jump_multiplier": 1.4,
                }
            ),
            settle=0.5,
        )

        add(
            "common",
            "no_durability",
            harness.app._on_enable_no_durability_shortcut,
            lambda: harness.verify_toggles({"no_durability": True}),
            settle=0.6,
        )
        add(
            "common",
            "inf_ammo",
            harness.app._on_enable_inf_ammo_shortcut,
            lambda: harness.verify_toggles({"inf_ammo": True}),
            settle=0.6,
        )
        add(
            "common",
            "unlock_fast_travel",
            harness.app._on_unlock_fast_travel,
            lambda: harness.verify_hidden_command_delivery([cmd.unlock_fast_travel()]),
            settle=0.6,
        )
        add(
            "common",
            "unlock_all_tech",
            harness.app._on_unlock_all_tech,
            lambda: harness.verify_hidden_command_delivery([cmd.unlock_all_tech()]),
            settle=0.6,
        )
        add(
            "common",
            "set_time_day",
            lambda: harness.app._on_set_time(6),
            lambda: harness.verify_hidden_command_delivery([cmd.set_time(6)]),
            settle=0.6,
        )

        add(
            "build",
            "unlockrecipes_shortcut",
            harness.app._on_unlock_recipes_shortcut,
            lambda: harness.verify_hidden_command_delivery([cmd.unlock_all_tech()]),
            settle=0.6,
        )
        add(
            "build",
            "giveallstatues_shortcut",
            harness.app._on_give_all_statues_shortcut,
            lambda: harness.verify_hidden_command_delivery([cmd.giveme("Relic", 999)]),
            settle=0.6,
        )

        build_quick_commands: list[str] = []

        def action_build_quick_unlock() -> None:
            values = list(harness.app.tech_quick_group_box.cget("values"))
            if values:
                harness.app.tech_quick_group_var.set(values[0])
                harness.app._refresh_tech_quick_choices()
            entry = harness.app._selected_tech_quick_entry()
            if entry is None:
                raise RuntimeError("No quick tech entry is selected.")
            build_quick_commands[:] = [cmd.unlock_tech(entry.key)]
            harness.app._unlock_selected_tech_quick()

        add(
            "build",
            "quick_unlock_selected_tech",
            action_build_quick_unlock,
            lambda: harness.verify_hidden_command_delivery(build_quick_commands),
            settle=0.6,
        )

        build_search_commands: list[str] = []

        def action_build_search_unlock() -> None:
            harness.select_first_tech_search("Palbox")
            if not harness.app._current_tech_results:
                raise RuntimeError("No tech search result available.")
            entry = harness.app._current_tech_results[0]
            build_search_commands[:] = [cmd.unlock_tech(entry.key)]
            harness.app._on_unlock_selected_tech()

        add(
            "build",
            "search_unlock_tech",
            action_build_search_unlock,
            lambda: harness.verify_hidden_command_delivery(build_search_commands),
            settle=0.6,
        )

        add(
            "character",
            "fly_on",
            lambda: harness.app._on_mem_fly(True),
            lambda: harness.verify_request_action(
                "set_fly",
                expected_pairs={"enabled": True},
            ),
            settle=0.5,
        )
        add(
            "character",
            "fly_off",
            lambda: harness.app._on_mem_fly(False),
            lambda: harness.verify_request_action(
                "set_fly",
                expected_pairs={"enabled": False},
            ),
            settle=0.5,
        )
        add(
            "character",
            "unstuck",
            lambda: harness.app._send_with_label(cmd.unstuck(), "脱困"),
            lambda: harness.verify_hidden_command_delivery([cmd.unstuck()]),
            settle=0.6,
        )
        add(
            "character",
            "read_position",
            harness.app._on_mem_read_pos,
            lambda: (
                all(harness.app.tp_x_var.get().strip() for _ in [0])
                and all(harness.app.tp_y_var.get().strip() for _ in [0])
                and all(harness.app.tp_z_var.get().strip() for _ in [0]),
                "position read into fields",
                [f"coords={ascii((harness.app.tp_x_var.get(), harness.app.tp_y_var.get(), harness.app.tp_z_var.get()))}"],
            ),
            settle=0.4,
        )

        add(
            "items",
            "reference_tabs_present",
            lambda: None,
            lambda: (
                [harness.app.item_category_notebook.tab(tab_id, "text") for tab_id in harness.app.item_category_notebook.tabs()]
                == list(REFERENCE_ITEM_TABS),
                "item reference tabs ready",
                [
                    f"tabs={ascii([harness.app.item_category_notebook.tab(tab_id, 'text') for tab_id in harness.app.item_category_notebook.tabs()])}"
                ],
            ),
        )

        add(
            "items",
            "all_tab_search_results",
            lambda: (
                harness.select_notebook_tab_at(harness.app.item_category_notebook, -1),
                harness.app.item_search_var.set("PalSphere_Master"),
                harness.pump(0.25),
            ),
            lambda: (
                bool(harness.app._current_item_results),
                "item all-tab search returned results",
                [
                    f"tab={ascii(harness.app._selected_item_reference_tab())}",
                    f"results={len(harness.app._current_item_results)}",
                    f"first={ascii([harness.app.item_listbox.get(i) for i in range(min(3, harness.app.item_listbox.size()))])}",
                ],
            ),
        )

        item_search_commands: list[str] = []

        def action_item_search() -> None:
            harness.app.item_count_var.set("2")
            harness.select_notebook_tab_at(harness.app.item_category_notebook, -1)
            harness.select_first_item_search("PalSphere_Master")
            if not harness.app._current_item_results:
                raise RuntimeError("No item search result available.")
            entry = harness.app._current_item_results[0]
            item_search_commands[:] = [cmd.giveme(entry.key, 2)]
            harness.app._on_give_selected_item()

        add(
            "items",
            "search_give_item",
            action_item_search,
            lambda: harness.verify_hidden_command_delivery(item_search_commands),
            settle=0.6,
        )

        add(
            "pals",
            "reference_tabs_present",
            lambda: None,
            lambda: (
                [harness.app.pal_category_notebook.tab(tab_id, "text") for tab_id in harness.app.pal_category_notebook.tabs()]
                == list(REFERENCE_ADD_PAL_TABS),
                "pal reference tabs ready",
                [
                    f"tabs={ascii([harness.app.pal_category_notebook.tab(tab_id, 'text') for tab_id in harness.app.pal_category_notebook.tabs()])}"
                ],
            ),
        )

        pal_search_commands: list[str] = []

        def action_pal_search() -> None:
            harness.select_notebook_tab_at(harness.app.pal_category_notebook, 1)
            harness.app.pal_count_var.set("1")
            harness.select_first_pal_search("Lamball")
            if not harness.app._current_pal_results:
                raise RuntimeError("No pal search result available.")
            entry = harness.app._current_pal_results[0]
            pal_search_commands[:] = [cmd.spawn_pal(entry.key, 1)]
            harness.app._on_spawn_selected_pal()

        add(
            "pals",
            "search_spawn_pal",
            action_pal_search,
            lambda: harness.verify_hidden_command_delivery(pal_search_commands),
            settle=0.6,
        )
        add(
            "pals",
            "favorite_pal",
            harness.app._add_selected_pal_favorite,
            lambda: (
                bool(harness.app.settings.favorite_pal_ids),
                "pal favorite updated" if harness.app.settings.favorite_pal_ids else "pal favorite empty",
                [f"favorites={ascii(harness.app.settings.favorite_pal_ids[:5])}"],
            ),
        )

        favorite_pal_commands: list[str] = []

        def action_spawn_favorite_pal() -> None:
            harness.select_notebook_tab_at(harness.app.pal_category_notebook, 5)
            harness.app.pal_favorite_listbox.selection_clear(0, "end")
            if harness.app.pal_favorite_listbox.size() <= 0:
                raise RuntimeError("Favorite pal list is empty.")
            harness.app.pal_favorite_listbox.selection_set(0)
            entry = harness.app._selected_pal_favorite_entry()
            if entry is None:
                raise RuntimeError("No favorite pal is selected.")
            count = int(harness.app.pal_count_var.get())
            favorite_pal_commands[:] = [cmd.spawn_pal(entry.key, count)]
            harness.app._spawn_selected_pal_favorite()

        add(
            "pals",
            "spawn_favorite_pal",
            action_spawn_favorite_pal,
            lambda: harness.verify_hidden_command_delivery(favorite_pal_commands),
            settle=0.6,
        )

        add(
            "pal_edit",
            "mem_attach",
            harness.app._on_mem_attach,
            lambda: harness.verify_mem_attached(True),
            settle=0.6,
        )

        add(
            "pal_edit",
            "duplicate_last_pal",
            harness.app._on_duplicate_current_pal,
            lambda: harness.verify_hidden_command_delivery(
                [cmd.spawn_pal(harness.app.settings.recent_pal_ids[0], 1)]
            ),
            settle=0.6,
        )

        pal_skill_commands: list[str] = []

        def action_pal_skill_item() -> None:
            harness.select_first_subset_search("pal_skill_search_var", "pal_skill_listbox", "Apocalypse")
            if not harness.app._current_pal_skill_results:
                raise RuntimeError("No pal skill result available.")
            entry = harness.app._current_pal_skill_results[0]
            count = int(harness.app.pal_skill_count_var.get())
            pal_skill_commands[:] = [cmd.giveme(entry.key, count)]
            harness.app._give_selected_subset_item(
                listbox_attr="pal_skill_listbox",
                results_attr="_current_pal_skill_results",
                count_var_name="pal_skill_count_var",
                label_prefix="发放技能果实",
            )

        add(
            "pal_edit",
            "give_skill_fruit",
            action_pal_skill_item,
            lambda: harness.verify_hidden_command_delivery(pal_skill_commands),
            settle=0.6,
        )

        pal_passive_commands: list[str] = []

        def action_pal_passive_item() -> None:
            harness.select_first_subset_search("pal_passive_search_var", "pal_passive_listbox", "Swim")
            if not harness.app._current_pal_passive_results:
                raise RuntimeError("No pal passive result available.")
            entry = harness.app._current_pal_passive_results[0]
            count = int(harness.app.pal_passive_count_var.get())
            pal_passive_commands[:] = [cmd.giveme(entry.key, count)]
            harness.app._give_selected_subset_item(
                listbox_attr="pal_passive_listbox",
                results_attr="_current_pal_passive_results",
                count_var_name="pal_passive_count_var",
                label_prefix="发放被动植入体",
            )

        add(
            "pal_edit",
            "give_passive_implant",
            action_pal_passive_item,
            lambda: harness.verify_hidden_command_delivery(pal_passive_commands),
            settle=0.6,
        )

        pal_support_commands: list[str] = []

        def action_pal_support_item() -> None:
            harness.select_first_subset_search("pal_support_search_var", "pal_support_listbox", "Growth_Stone")
            if not harness.app._current_pal_support_results:
                raise RuntimeError("No pal support result available.")
            entry = harness.app._current_pal_support_results[0]
            count = int(harness.app.pal_support_count_var.get())
            pal_support_commands[:] = [cmd.giveme(entry.key, count)]
            harness.app._give_selected_subset_item(
                listbox_attr="pal_support_listbox",
                results_attr="_current_pal_support_results",
                count_var_name="pal_support_count_var",
                label_prefix="发放帕鲁补给",
            )

        add(
            "pal_edit",
            "give_support_item",
            action_pal_support_item,
            lambda: harness.verify_hidden_command_delivery(pal_support_commands),
            settle=0.6,
        )

        add(
            "online_pal",
            "duplicate_last_pal",
            lambda: harness.app._on_duplicate_current_pal(label="联机复制当前帕鲁"),
            lambda: harness.verify_hidden_command_delivery(
                [cmd.spawn_pal(harness.app.settings.recent_pal_ids[0], 1)]
            ),
            settle=0.6,
        )

        online_skill_commands: list[str] = []

        def action_online_skill_item() -> None:
            harness.select_first_subset_search("online_pal_skill_search_var", "online_pal_skill_listbox", "Apocalypse")
            if not harness.app._current_online_pal_skill_results:
                raise RuntimeError("No online pal skill result available.")
            entry = harness.app._current_online_pal_skill_results[0]
            count = int(harness.app.online_pal_skill_count_var.get())
            online_skill_commands[:] = [cmd.giveme(entry.key, count)]
            harness.app._give_selected_subset_item(
                listbox_attr="online_pal_skill_listbox",
                results_attr="_current_online_pal_skill_results",
                count_var_name="online_pal_skill_count_var",
                label_prefix="联机发放技能果实",
            )

        add(
            "online_pal",
            "give_skill_fruit",
            action_online_skill_item,
            lambda: harness.verify_hidden_command_delivery(online_skill_commands),
            settle=0.6,
        )

        online_passive_commands: list[str] = []

        def action_online_passive_item() -> None:
            harness.select_first_subset_search("online_pal_passive_search_var", "online_pal_passive_listbox", "Swim")
            if not harness.app._current_online_pal_passive_results:
                raise RuntimeError("No online pal passive result available.")
            entry = harness.app._current_online_pal_passive_results[0]
            count = int(harness.app.online_pal_passive_count_var.get())
            online_passive_commands[:] = [cmd.giveme(entry.key, count)]
            harness.app._give_selected_subset_item(
                listbox_attr="online_pal_passive_listbox",
                results_attr="_current_online_pal_passive_results",
                count_var_name="online_pal_passive_count_var",
                label_prefix="联机发放被动植入体",
            )

        add(
            "online_pal",
            "give_passive_implant",
            action_online_passive_item,
            lambda: harness.verify_hidden_command_delivery(online_passive_commands),
            settle=0.6,
        )

        online_support_commands: list[str] = []

        def action_online_support_item() -> None:
            harness.select_first_subset_search("online_pal_support_search_var", "online_pal_support_listbox", "Growth_Stone")
            if not harness.app._current_online_pal_support_results:
                raise RuntimeError("No online pal support result available.")
            entry = harness.app._current_online_pal_support_results[0]
            count = int(harness.app.online_pal_support_count_var.get())
            online_support_commands[:] = [cmd.giveme(entry.key, count)]
            harness.app._give_selected_subset_item(
                listbox_attr="online_pal_support_listbox",
                results_attr="_current_online_pal_support_results",
                count_var_name="online_pal_support_count_var",
                label_prefix="联机发放帕鲁补给",
            )

        add(
            "online_pal",
            "give_support_item",
            action_online_support_item,
            lambda: harness.verify_hidden_command_delivery(online_support_commands),
            settle=0.6,
        )

        add(
            "coords",
            "workspace_seed_loaded",
            lambda: harness.app._refresh_coord_workspace_items(),
            lambda: (
                harness.app.coord_group_listbox.size() > 0
                and harness.app.coord_item_listbox.size() > 0
                and all(
                    value.strip()
                    for value in (
                        harness.app.coord_name_var.get(),
                        harness.app.tp_x_var.get(),
                        harness.app.tp_y_var.get(),
                        harness.app.tp_z_var.get(),
                    )
                ),
                "coord workspace loaded",
                [
                    f"groups={harness.app.coord_group_listbox.size()}",
                    f"items={harness.app.coord_item_listbox.size()}",
                    f"name={ascii(harness.app.coord_name_var.get())}",
                    f"coords={ascii((harness.app.tp_x_var.get(), harness.app.tp_y_var.get(), harness.app.tp_z_var.get()))}",
                ],
            ),
        )
        before_coord_name = harness.app.coord_name_var.get()
        add(
            "coords",
            "workspace_item_switch",
            lambda: harness.select_listbox_index(
                harness.app.coord_item_listbox,
                max(1, harness.app.coord_item_listbox.size() - 1),
            ),
            lambda: (
                harness.app.coord_name_var.get() != before_coord_name,
                "coord workspace selection changed",
                [
                    f"before={ascii(before_coord_name)}",
                    f"after={ascii(harness.app.coord_name_var.get())}",
                    f"coords={ascii((harness.app.tp_x_var.get(), harness.app.tp_y_var.get(), harness.app.tp_z_var.get()))}",
                ],
            ),
        )

        add(
            "coords",
            "coord_speed_multiplier",
            lambda: harness.app._apply_coord_speed_multiplier("1.8"),
            lambda: harness.verify_toggles({"speed_multiplier": 1.8}),
            settle=0.5,
        )
        add(
            "coords",
            "coord_jump_multiplier",
            lambda: harness.app._apply_coord_jump_multiplier("1.3"),
            lambda: harness.verify_toggles({"jump_multiplier": 1.3}),
            settle=0.5,
        )
        add(
            "coords",
            "read_current_position",
            harness.app._read_coord_into_form,
            lambda: (
                bool(harness.app.coord_name_var.get() or harness.app.tp_x_var.get().strip()),
                "coord form populated",
                [
                    f"name={ascii(harness.app.coord_name_var.get())}",
                    f"coords={ascii((harness.app.tp_x_var.get(), harness.app.tp_y_var.get(), harness.app.tp_z_var.get()))}",
                ],
            ),
            settle=0.4,
        )

        add(
            "coords",
            "copy_and_paste_fields",
            lambda: (
                harness.app._copy_coord_fields(),
                harness.app.coord_name_var.set(""),
                harness.app.tp_x_var.set(""),
                harness.app.tp_y_var.set(""),
                harness.app.tp_z_var.set(""),
                harness.app._paste_coord_fields(),
            ),
            lambda: (
                all(
                    value.strip()
                    for value in (
                        harness.app.tp_x_var.get(),
                        harness.app.tp_y_var.get(),
                        harness.app.tp_z_var.get(),
                    )
                ),
                "coord fields restored from clipboard",
                [
                    f"name={ascii(harness.app.coord_name_var.get())}",
                    f"coords={ascii((harness.app.tp_x_var.get(), harness.app.tp_y_var.get(), harness.app.tp_z_var.get()))}",
                ],
            ),
        )

        def action_current_teleport() -> None:
            harness.app.tp_x_var.set(str(current_pos[0]))
            harness.app.tp_y_var.set(str(current_pos[1]))
            harness.app.tp_z_var.set(str(current_pos[2]))
            harness.app._on_mem_teleport()

        add(
            "coords",
            "teleport_current_position",
            action_current_teleport,
            lambda: harness.verify_request_action(
                "teleport",
                expected_pairs={"x": current_pos[0], "y": current_pos[1], "z": current_pos[2]},
            ),
            settle=0.4,
        )

        add(
            "pal_edit",
            "mem_detach",
            harness.app._on_mem_detach,
            lambda: harness.verify_mem_attached(False),
            settle=0.3,
        )

        add(
            "online",
            "give_exp",
            lambda: (harness.app.exp_var.set("12345"), harness.app._on_give_custom_exp()),
            lambda: harness.verify_hidden_command_delivery([cmd.give_exp(12345)]),
            settle=0.6,
        )
        add(
            "online",
            "fly_on",
            harness.app._toggle_online_fly,
            lambda: harness.verify_request_action("set_fly", expected_pairs={"enabled": True}),
            settle=0.5,
        )
        add(
            "online",
            "fly_off",
            harness.app._toggle_online_fly,
            lambda: harness.verify_request_action("set_fly", expected_pairs={"enabled": False}),
            settle=0.5,
        )
        add(
            "online",
            "speed_multiplier",
            lambda: (harness.app.online_speed_var.set("1.7"), harness.app._apply_coord_speed_multiplier(harness.app.online_speed_var.get())),
            lambda: harness.verify_toggles({"speed_multiplier": 1.7}),
            settle=0.5,
        )
        add(
            "online",
            "inf_stamina_toggle",
            lambda: (harness.app.online_stamina_var.set(True), harness.app._apply_online_stamina_toggle()),
            lambda: harness.verify_toggles({"inf_stamina": True}),
            settle=0.5,
        )

        existing_root = harness.app.game_root_var.get()
        add(
            "settings",
            "apply_game_root",
            lambda: (harness.app.game_root_var.set(existing_root), harness.app._apply_game_root()),
            lambda: (
                str(harness.app.report.game_root) == existing_root,
                "game root preserved" if str(harness.app.report.game_root) == existing_root else "game root changed unexpectedly",
                [f"game_root={ascii(str(harness.app.report.game_root))}"],
            ),
        )

    finally:
        harness.close()

    failed = [item for item in results if not item.ok]
    print("LIVE_SMOKETEST_RESULTS_BEGIN")
    for item in results:
        status = "PASS" if item.ok else "FAIL"
        print(f"[{status}] {item.group} :: {item.name} :: {item.details}")
        for evidence in item.evidence:
            print(f"  - {evidence}")
    print("LIVE_SMOKETEST_RESULTS_END")
    print(f"SUMMARY total={len(results)} pass={len(results) - len(failed)} fail={len(failed)}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
