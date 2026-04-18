"""Runtime engine that freezes memory values in the live Palworld process.

This is the core of the "no-mod" path added in v1.2 — the trainer attaches
to ``Palworld-Win64-Shipping.exe`` through the Win32 process-memory APIs
(see :mod:`.memory`) and writes game-state floats like HP / SP / walk
speed every ~50 ms from a background thread. Nothing is injected, nothing
is installed into the game directory; the game runs completely vanilla.

Usage from the GUI:

1. Build an :class:`MemEngine`.
2. Call :meth:`MemEngine.attach` once per session. It locates the process,
   opens a read/write handle, and starts the ticker thread.
3. For each cheat that needs calibration (HP, SP, walk speed, …) drive it
   through the two-step scan flow:

   - :meth:`start_scan(slot, value)` to record a first snapshot.
   - :meth:`refine_scan(slot, value)` after the user has changed the
     in-game value (took damage, ran a bit, etc.).

   Repeat ``refine_scan`` until ``len(snapshot) == 1`` and the address is
   locked.

4. Flip :attr:`CheatState` fields (``hp_freeze=True`` etc.). The ticker
   picks the change up automatically on the next tick.

The ticker never blocks the GUI; it only holds a local ``threading.Lock``
for the ~millisecond each write takes.
"""

from __future__ import annotations

import dataclasses
import json
import re
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from . import memory
from .memory import ProcessHandle, ScanSnapshot


# ---------------------------------------------------------------------------
# Cheat state + calibration
# ---------------------------------------------------------------------------


SLOTS = ("hp", "sp", "walk_speed", "jump_z", "pos_x", "pos_y", "pos_z", "move_mode")

# Reasonable default "freeze to" values for each slot — used when the user
# flips a toggle without having manually typed a freeze value.
DEFAULT_FREEZE: dict[str, float] = {
    "hp": 9999.0,
    "sp": 9999.0,
    "walk_speed": 1200.0,
    "jump_z": 1200.0,
    "pos_x": 0.0,
    "pos_y": 0.0,
    "pos_z": 0.0,
    "move_mode": 1.0,  # 1=Walking, 5=Flying
}

# Data type per fixed slot (default f32). Position & basic stats are f32,
# movement mode is u8.
SLOT_DTYPES: dict[str, str] = {
    "move_mode": "u8",
}

SLOT_LABELS_CN = {
    "hp": "HP（生命值）",
    "sp": "SP（体力值）",
    "walk_speed": "移动速度（MaxWalkSpeed）",
    "jump_z": "跳跃初速度（JumpZVelocity）",
    "pos_x": "玩家坐标 X",
    "pos_y": "玩家坐标 Y",
    "pos_z": "玩家坐标 Z",
    "move_mode": "移动模式（1=走 5=飞）",
}

# Slots that the GUI shows in the core "字段校准" grid. The other fixed
# slots (pos, move_mode) are surfaced in their own dedicated sections.
CORE_SLOTS = ("hp", "sp", "walk_speed", "jump_z")
POSITION_SLOTS = ("pos_x", "pos_y", "pos_z")
MODE_SLOTS = ("move_mode",)


@dataclass(frozen=True)
class CustomSlotTemplate:
    """A named preset for quickly adding a common custom-slot field.

    These map directly to the "fixed" rows on chenstack's reference
    trainer: anything numeric the user can see in-game. The trainer
    doesn't ship hard-coded offsets for any of them; each template just
    opens the scan flow with a pre-filled label so the user doesn't have
    to invent one.
    """

    label: str
    hint: str
    default_target: float = 0.0
    dtype: str = "f32"  # "f32" | "i32" | "u8"


# Supported data types for the scan engine.
DTYPE_LABELS_CN = {
    "f32": "浮点 (float32)",
    "i32": "整数 (int32)",
    "u8": "字节 (uint8)",
}

CUSTOM_SLOT_TEMPLATES: tuple[CustomSlotTemplate, ...] = (
    CustomSlotTemplate("负重", "当前负重数值", 0.0),
    CustomSlotTemplate("饥饿度", "饱食度当前值", 100.0),
    CustomSlotTemplate("氧气", "潜水/溺水时的氧气值", 100.0),
    CustomSlotTemplate("心情", "帕鲁/玩家心情/神智数值", 100.0),
    CustomSlotTemplate("温度", "体温/环境温度", 36.0),
    CustomSlotTemplate("弹药（当前武器）", "当前武器弹药数", 999.0),
    CustomSlotTemplate("耐久（当前装备）", "选中装备耐久", 9999.0),
    CustomSlotTemplate("武器冷却", "武器/技能冷却秒数", 0.0),
    CustomSlotTemplate("帕鲁技能冷却", "出战帕鲁技能 CD", 0.0),
    CustomSlotTemplate("当前经验", "当前等级经验值", 9_999_999.0, "i32"),
    CustomSlotTemplate("帕鲁IV·近战", "帕鲁近战IV值 (0-100)", 100.0, "u8"),
    CustomSlotTemplate("帕鲁IV·射击", "帕鲁射击IV值 (0-100)", 100.0, "u8"),
    CustomSlotTemplate("帕鲁IV·防御", "帕鲁防御IV值 (0-100)", 100.0, "u8"),
    CustomSlotTemplate("帕鲁等级", "帕鲁当前等级", 50.0, "i32"),
)


@dataclass
class MemCheatState:
    """Which freezes are currently on, and what they should lock to."""

    hp_freeze: bool = False
    sp_freeze: bool = False
    walk_speed_freeze: bool = False
    jump_z_freeze: bool = False
    pos_x_freeze: bool = False
    pos_y_freeze: bool = False
    pos_z_freeze: bool = False
    move_mode_freeze: bool = False

    hp_target: float = DEFAULT_FREEZE["hp"]
    sp_target: float = DEFAULT_FREEZE["sp"]
    walk_speed_target: float = DEFAULT_FREEZE["walk_speed"]
    jump_z_target: float = DEFAULT_FREEZE["jump_z"]
    pos_x_target: float = DEFAULT_FREEZE["pos_x"]
    pos_y_target: float = DEFAULT_FREEZE["pos_y"]
    pos_z_target: float = DEFAULT_FREEZE["pos_z"]
    move_mode_target: float = DEFAULT_FREEZE["move_mode"]

    def is_slot_enabled(self, slot: str) -> bool:
        return bool(getattr(self, f"{slot}_freeze"))

    def target_for(self, slot: str) -> float:
        return float(getattr(self, f"{slot}_target"))

    def set_slot(self, slot: str, enabled: bool) -> None:
        setattr(self, f"{slot}_freeze", bool(enabled))

    def set_target(self, slot: str, value: float) -> None:
        setattr(self, f"{slot}_target", float(value))


@dataclass
class Calibration:
    """Addresses discovered for each slot, plus the last-seen snapshot size.

    An address of ``0`` means "not calibrated yet".
    """

    hp_addr: int = 0
    sp_addr: int = 0
    walk_speed_addr: int = 0
    jump_z_addr: int = 0
    pos_x_addr: int = 0
    pos_y_addr: int = 0
    pos_z_addr: int = 0
    move_mode_addr: int = 0

    def address_for(self, slot: str) -> int:
        return int(getattr(self, f"{slot}_addr"))

    def set_address(self, slot: str, addr: int) -> None:
        setattr(self, f"{slot}_addr", int(addr))

    def is_locked(self, slot: str) -> bool:
        return self.address_for(slot) != 0


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


def calibration_path(base_dir: Path) -> Path:
    return base_dir / "calibration.json"


def load_calibration(path: Path) -> Calibration:
    """Calibrations are only meaningful for a single game session — PIDs and
    heap addresses move on every launch — but we still persist them so the
    GUI can remember what the user last dialed in for a given session and
    let them re-verify instead of re-scanning from scratch.
    """

    if not path.exists():
        return Calibration()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return Calibration()
    if not isinstance(payload, dict):
        return Calibration()
    cal = Calibration()
    for slot in SLOTS:
        key = f"{slot}_addr"
        value = payload.get(key, 0)
        try:
            cal.set_address(slot, int(value))
        except (TypeError, ValueError):
            continue
    return cal


def save_calibration(path: Path, cal: Calibration) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = dataclasses.asdict(cal)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    tmp.replace(path)


# ---------------------------------------------------------------------------
# The engine
# ---------------------------------------------------------------------------


@dataclass
class CustomSlot:
    """A user-defined freeze slot created at runtime via the 外挂 tab.

    Custom slots share the same value-scan pipeline as the four fixed
    slots — the only difference is that their label and default target are
    user-supplied, and they live in an in-memory registry instead of the
    ``Calibration`` dataclass. PIDs and heap addresses change every launch,
    so persisting custom slots across sessions wouldn't buy anything.
    """

    key: str
    label: str
    address: int = 0
    freeze: bool = False
    target: float = 0.0
    dtype: str = "f32"  # "f32" | "i32" | "u8"


_CUSTOM_KEY_RE = re.compile(r"[^a-z0-9]+")


def make_custom_key(label: str, existing: set[str]) -> str:
    """Derive a stable, unique ASCII key from a Chinese/English label."""

    base = _CUSTOM_KEY_RE.sub("_", label.strip().lower()).strip("_")
    if not base:
        base = "slot"
    # Custom keys live alongside the fixed slots, so make sure we never
    # collide with one of them.
    reserved = set(SLOTS) | existing
    candidate = base
    suffix = 2
    while candidate in reserved:
        candidate = f"{base}_{suffix}"
        suffix += 1
    return candidate


@dataclass
class AttachResult:
    ok: bool
    message: str
    pid: int | None = None


class MemEngine:
    """Attach to Palworld, scan for values, freeze toggles via a ticker."""

    TICK_SECONDS = 0.05

    def __init__(self, calibration_dir: Path | None = None) -> None:
        self._lock = threading.Lock()
        self._handle: ProcessHandle | None = None
        self._pid: int | None = None

        self.state = MemCheatState()
        self.calibration = Calibration()
        self._snapshots: dict[str, ScanSnapshot] = {}

        # User-defined freeze slots (negotiated at runtime via the GUI).
        # Keyed by their derived slot key; address discovery still flows
        # through the same scan/refine pipeline as the fixed slots.
        self._custom: dict[str, CustomSlot] = {}

        self._ticker_thread: threading.Thread | None = None
        self._ticker_stop = threading.Event()
        self._last_tick_error: str | None = None

        self._calibration_path: Path | None = (
            calibration_path(calibration_dir) if calibration_dir else None
        )
        if self._calibration_path is not None:
            self.calibration = load_calibration(self._calibration_path)

    # ------------------------------------------------------------------
    # Custom slot registry
    # ------------------------------------------------------------------

    def custom_slots(self) -> list[CustomSlot]:
        return list(self._custom.values())

    def has_slot(self, slot: str) -> bool:
        return slot in SLOTS or slot in self._custom

    def add_custom_slot(
        self, label: str, default_target: float = 0.0, dtype: str = "f32"
    ) -> CustomSlot:
        label = label.strip() or "自定义"
        key = make_custom_key(label, set(self._custom))
        cs = CustomSlot(
            key=key, label=label, target=float(default_target), dtype=dtype
        )
        self._custom[key] = cs
        return cs

    def remove_custom_slot(self, key: str) -> bool:
        if key not in self._custom:
            return False
        del self._custom[key]
        self._snapshots.pop(key, None)
        return True

    def get_custom_slot(self, key: str) -> CustomSlot | None:
        return self._custom.get(key)

    def label_for(self, slot: str) -> str:
        if slot in SLOTS:
            return SLOT_LABELS_CN[slot]
        cs = self._custom.get(slot)
        return cs.label if cs else slot

    # ------------------------------------------------------------------
    # Attach / detach
    # ------------------------------------------------------------------

    def is_attached(self) -> bool:
        return self._handle is not None

    def attach(self) -> AttachResult:
        with self._lock:
            if self._handle is not None:
                return AttachResult(True, f"已连接（PID {self._pid}）", self._pid)
            pid = memory.find_process_id()
            if pid is None:
                return AttachResult(False, "找不到 Palworld 进程，先把游戏打开。")
            try:
                handle = ProcessHandle(pid, writable=True)
            except OSError as error:
                return AttachResult(False, f"打开进程失败：{error}")
            self._handle = handle
            self._pid = pid
        self._start_ticker()
        return AttachResult(True, f"已连接（PID {pid}）", pid)

    def detach(self) -> None:
        self._stop_ticker()
        with self._lock:
            if self._handle is not None:
                self._handle.close()
            self._handle = None
            self._pid = None
            self._snapshots.clear()

    def pid(self) -> int | None:
        return self._pid

    # ------------------------------------------------------------------
    # Scan / refine flow
    # ------------------------------------------------------------------

    def dtype_for(self, slot: str) -> str:
        """Return the data type for a slot ("f32" for most fixed slots)."""

        if slot in SLOTS:
            return SLOT_DTYPES.get(slot, "f32")
        cs = self._custom.get(slot)
        return cs.dtype if cs else "f32"

    def start_scan(self, slot: str, value: float) -> ScanSnapshot:
        """First-pass value scan for ``slot``. Returns the snapshot (stored)."""

        if not self.has_slot(slot):
            raise ValueError(f"unknown slot: {slot}")
        handle = self._require_handle()
        dtype = self.dtype_for(slot)
        max_rs = 4 * 1024 * 1024
        if dtype == "i32":
            snap = memory.scan_i32(handle, int(value), max_region_size=max_rs)
        elif dtype == "u8":
            snap = memory.scan_u8(handle, int(value), max_region_size=max_rs)
        else:
            snap = memory.scan_f32(handle, float(value), max_region_size=max_rs)
        self._snapshots[slot] = snap
        return snap

    def refine_scan(self, slot: str, value: float) -> ScanSnapshot:
        """Second (or subsequent) pass — narrows to addresses now equal to value."""

        if not self.has_slot(slot):
            raise ValueError(f"unknown slot: {slot}")
        handle = self._require_handle()
        prev = self._snapshots.get(slot)
        if prev is None:
            return self.start_scan(slot, value)
        dtype = self.dtype_for(slot)
        if dtype == "i32":
            snap = memory.refine_i32(handle, prev, int(value))
        elif dtype == "u8":
            snap = memory.refine_u8(handle, prev, int(value))
        else:
            snap = memory.refine_f32(handle, prev, float(value))
        self._snapshots[slot] = snap
        return snap

    def clear_snapshot(self, slot: str) -> None:
        self._snapshots.pop(slot, None)

    def snapshot_size(self, slot: str) -> int:
        snap = self._snapshots.get(slot)
        return len(snap) if snap else 0

    def is_locked(self, slot: str) -> bool:
        if slot in SLOTS:
            return self.calibration.is_locked(slot)
        cs = self._custom.get(slot)
        return bool(cs and cs.address)

    def address_for(self, slot: str) -> int:
        if slot in SLOTS:
            return self.calibration.address_for(slot)
        cs = self._custom.get(slot)
        return cs.address if cs else 0

    def lock_address(self, slot: str, address: int | None = None) -> bool:
        """Finalize calibration for a slot.

        If ``address`` is ``None``, the slot's current snapshot must be
        down to exactly one candidate — that address gets locked. Otherwise
        the caller picks explicitly (useful when narrowing from the GUI).
        """

        if not self.has_slot(slot):
            raise ValueError(f"unknown slot: {slot}")
        if address is None:
            snap = self._snapshots.get(slot)
            if snap is None or len(snap) != 1:
                return False
            address = snap.addresses[0]
        if slot in SLOTS:
            self.calibration.set_address(slot, int(address))
            self._persist_calibration()
        else:
            self._custom[slot].address = int(address)
        return True

    def unlock_address(self, slot: str) -> None:
        if slot in SLOTS:
            self.calibration.set_address(slot, 0)
            self._persist_calibration()
        elif slot in self._custom:
            cs = self._custom[slot]
            cs.address = 0
            cs.freeze = False
        self._snapshots.pop(slot, None)

    def write_slot_value(self, slot: str, value: float) -> bool:
        """One-shot write to a calibrated slot (no freeze). Used for teleport."""

        addr = self.address_for(slot)
        if not addr:
            return False
        with self._lock:
            if self._handle is None:
                return False
            dtype = self.dtype_for(slot)
            if dtype == "i32":
                self._handle.write_i32(addr, int(value))
            elif dtype == "u8":
                self._handle.write_u8(addr, int(value))
            else:
                self._handle.write_f32(addr, value)
        return True

    def read_current_value(self, slot: str) -> float | None:
        """Peek the current value at the calibrated address (for the UI)."""

        addr = self.address_for(slot)
        if not addr:
            return None
        with self._lock:
            if self._handle is None:
                return None
            dtype = self.dtype_for(slot)
            if dtype == "i32":
                v = self._handle.read_i32(addr)
                return float(v) if v is not None else None
            elif dtype == "u8":
                v = self._handle.read_u8(addr)
                return float(v) if v is not None else None
            else:
                return self._handle.read_f32(addr)

    # ------------------------------------------------------------------
    # Unified slot state helpers (fixed + custom)
    # ------------------------------------------------------------------

    def slot_freeze_enabled(self, slot: str) -> bool:
        if slot in SLOTS:
            return self.state.is_slot_enabled(slot)
        cs = self._custom.get(slot)
        return bool(cs and cs.freeze)

    def slot_target(self, slot: str) -> float:
        if slot in SLOTS:
            return self.state.target_for(slot)
        cs = self._custom.get(slot)
        return cs.target if cs else 0.0

    def set_slot_freeze(self, slot: str, enabled: bool) -> None:
        if slot in SLOTS:
            self.state.set_slot(slot, enabled)
        elif slot in self._custom:
            self._custom[slot].freeze = bool(enabled)

    def set_slot_target(self, slot: str, value: float) -> None:
        if slot in SLOTS:
            self.state.set_target(slot, value)
        elif slot in self._custom:
            self._custom[slot].target = float(value)

    # ------------------------------------------------------------------
    # Ticker
    # ------------------------------------------------------------------

    def _start_ticker(self) -> None:
        if self._ticker_thread and self._ticker_thread.is_alive():
            return
        self._ticker_stop.clear()
        thread = threading.Thread(target=self._ticker_loop, name="pt-mem-ticker", daemon=True)
        self._ticker_thread = thread
        thread.start()

    def _stop_ticker(self) -> None:
        self._ticker_stop.set()
        thread = self._ticker_thread
        self._ticker_thread = None
        if thread and thread.is_alive():
            thread.join(timeout=1.0)

    def _ticker_loop(self) -> None:
        while not self._ticker_stop.is_set():
            try:
                self._tick_once()
            except Exception as error:  # noqa: BLE001 - defensive, report to GUI
                self._last_tick_error = str(error)
            self._ticker_stop.wait(self.TICK_SECONDS)

    def _tick_once(self) -> None:
        with self._lock:
            handle = self._handle
            if handle is None:
                return
            # Fixed slots (dtype-aware: most are f32, move_mode is u8)
            for slot in SLOTS:
                if not self.state.is_slot_enabled(slot):
                    continue
                addr = self.calibration.address_for(slot)
                if not addr:
                    continue
                target = self.state.target_for(slot)
                dtype = SLOT_DTYPES.get(slot, "f32")
                if dtype == "i32":
                    current = handle.read_i32(addr)
                    if current is not None and current == int(target):
                        continue
                    handle.write_i32(addr, int(target))
                elif dtype == "u8":
                    current = handle.read_u8(addr)
                    if current is not None and current == int(target) & 0xFF:
                        continue
                    handle.write_u8(addr, int(target))
                else:
                    current = handle.read_f32(addr)
                    if current is not None and abs(current - target) < 1e-3:
                        continue
                    handle.write_f32(addr, target)
            # Custom slots (snapshot values so a concurrent add/remove can't
            # mutate the dict mid-iteration).
            for cs in list(self._custom.values()):
                if not cs.freeze or not cs.address:
                    continue
                if cs.dtype == "i32":
                    current = handle.read_i32(cs.address)
                    if current is not None and current == int(cs.target):
                        continue
                    handle.write_i32(cs.address, int(cs.target))
                elif cs.dtype == "u8":
                    current = handle.read_u8(cs.address)
                    if current is not None and current == int(cs.target) & 0xFF:
                        continue
                    handle.write_u8(cs.address, int(cs.target))
                else:
                    current = handle.read_f32(cs.address)
                    if current is not None and abs(current - cs.target) < 1e-3:
                        continue
                    handle.write_f32(cs.address, cs.target)

    def last_error(self) -> str | None:
        return self._last_tick_error

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _require_handle(self) -> ProcessHandle:
        if self._handle is None:
            raise RuntimeError("未连接到 Palworld 进程，先点「连接游戏」。")
        return self._handle

    def _persist_calibration(self) -> None:
        if self._calibration_path is None:
            return
        try:
            save_calibration(self._calibration_path, self.calibration)
        except OSError:
            pass
