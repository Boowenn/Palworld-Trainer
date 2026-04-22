"""Persistent cheat toggles mirrored into the UE4SS bridge via ``toggles.json``.

The bridge Lua mod polls this JSON file every ~2 seconds and applies the
requested effects from an in-game tick loop. The GUI side just needs to keep
this file in sync with the current :class:`CheatState` after each checkbox
flip.

Only flat primitives go into the file (bools and floats) because the Lua
side uses pattern matching instead of a real JSON parser — keep the schema
boring.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from .environment import BRIDGE_MOD_NAME, EnvironmentReport


TOGGLES_FILENAME = "toggles.json"
STATUS_FILENAME = "status.json"
REQUEST_FILENAME = "request.json"


@dataclass
class CheatState:
    """What the Lua bridge reads from ``toggles.json`` every tick.

    Keep field names in sync with the keys parsed in
    ``integrations/ue4ss/PalworldTrainerBridge/Scripts/main.lua``.
    """

    godmode: bool = False
    inf_stamina: bool = False
    weight_zero: bool = False
    inf_ammo: bool = False
    no_durability: bool = False
    speed_multiplier: float = 1.0
    jump_multiplier: float = 1.0

    def to_payload(self) -> dict[str, bool | float]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_payload(), indent=2, ensure_ascii=False)

    @classmethod
    def from_payload(cls, payload: dict[str, object]) -> "CheatState":
        state = cls()
        for key, value in payload.items():
            if not hasattr(state, key):
                continue
            default = getattr(state, key)
            if isinstance(default, bool):
                setattr(state, key, bool(value))
            elif isinstance(default, (int, float)):
                try:
                    setattr(state, key, float(value))
                except (TypeError, ValueError):
                    continue
        return state


@dataclass
class BridgeNearbyEntry:
    name: str = ""
    class_name: str = ""
    location: str = ""
    distance_meters: float = 0.0

    @classmethod
    def from_payload(cls, payload: dict[str, object]) -> "BridgeNearbyEntry":
        entry = cls()
        name = payload.get("name")
        if isinstance(name, str):
            entry.name = name
        class_name = payload.get("class_name")
        if isinstance(class_name, str):
            entry.class_name = class_name
        location = payload.get("location")
        if isinstance(location, str):
            entry.location = location
        distance = payload.get("distance_meters")
        try:
            entry.distance_meters = float(distance)
        except (TypeError, ValueError):
            entry.distance_meters = 0.0
        return entry


@dataclass
class BridgeStatus:
    player_valid: bool = False
    controller_valid: bool = False
    bridge_version: str = ""
    hidden_registry_ready: bool = False
    hidden_dispatch_ready: bool = False
    chat_suppression_ready: bool = False
    position_x: float = 0.0
    position_y: float = 0.0
    position_z: float = 0.0
    nearby_players: tuple[BridgeNearbyEntry, ...] = ()

    @classmethod
    def from_payload(cls, payload: dict[str, object]) -> "BridgeStatus":
        status = cls()
        player_valid = payload.get("player_valid")
        if isinstance(player_valid, bool):
            status.player_valid = player_valid
        controller_valid = payload.get("controller_valid")
        if isinstance(controller_valid, bool):
            status.controller_valid = controller_valid
        bridge_version = payload.get("bridge_version")
        if isinstance(bridge_version, str):
            status.bridge_version = bridge_version
        hidden_registry_ready = payload.get("hidden_registry_ready")
        if isinstance(hidden_registry_ready, bool):
            status.hidden_registry_ready = hidden_registry_ready
        hidden_dispatch_ready = payload.get("hidden_dispatch_ready")
        if isinstance(hidden_dispatch_ready, bool):
            status.hidden_dispatch_ready = hidden_dispatch_ready
        chat_suppression_ready = payload.get("chat_suppression_ready")
        if isinstance(chat_suppression_ready, bool):
            status.chat_suppression_ready = chat_suppression_ready
        for key in ("position_x", "position_y", "position_z"):
            value = payload.get(key)
            try:
                setattr(status, key, float(value))
            except (TypeError, ValueError):
                continue
        nearby_players = payload.get("nearby_players")
        if isinstance(nearby_players, list):
            rows: list[BridgeNearbyEntry] = []
            for raw_row in nearby_players:
                if not isinstance(raw_row, dict):
                    continue
                rows.append(BridgeNearbyEntry.from_payload(raw_row))
            status.nearby_players = tuple(rows)
        return status


def _bridge_io_target(report: EnvironmentReport) -> Path | None:
    if report.trainer_bridge_runtime_target is not None:
        return report.trainer_bridge_runtime_target
    return report.trainer_bridge_target


def toggles_path_for(report: EnvironmentReport) -> Path | None:
    """Return the absolute path ``toggles.json`` should live at for this game.

    ``None`` means we can't figure out the UE4SS Mods folder yet — the GUI
    should disable the cheat tab and surface the bridge deployment button.
    """

    target = _bridge_io_target(report)
    if target is None:
        return None
    return target / TOGGLES_FILENAME


def status_path_for(report: EnvironmentReport) -> Path | None:
    target = _bridge_io_target(report)
    if target is None:
        return None
    return target / STATUS_FILENAME


def request_path_for(report: EnvironmentReport) -> Path | None:
    target = _bridge_io_target(report)
    if target is None:
        return None
    return target / REQUEST_FILENAME


def write_toggles(path: Path, state: CheatState) -> tuple[bool, str]:
    """Atomically write ``state`` to ``path``. Creates parent dirs if needed."""

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        return False, f"无法创建目录 {path.parent}: {error}"

    tmp_path = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp_path.write_text(state.to_json(), encoding="utf-8")
        os.replace(tmp_path, path)
    except OSError as error:
        return False, f"写入 toggles 文件失败: {error}"

    return True, f"已同步到 {path}"


def read_toggles(path: Path) -> CheatState:
    """Load cheat state from ``toggles.json``, falling back to defaults."""

    if not path.exists():
        return CheatState()
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return CheatState()
    if not raw.strip():
        return CheatState()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return CheatState()
    if not isinstance(payload, dict):
        return CheatState()
    return CheatState.from_payload(payload)


def read_status(path: Path) -> BridgeStatus:
    if not path.exists():
        return BridgeStatus()

    for attempt in range(3):
        try:
            raw = path.read_text(encoding="utf-8")
        except OSError:
            raw = ""
        if raw.strip():
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                payload = None
            if isinstance(payload, dict):
                return BridgeStatus.from_payload(payload)
        if attempt < 2:
            time.sleep(0.02)
    return BridgeStatus()


def write_request(
    path: Path,
    *,
    action: str,
    request_id: int,
    x: float | None = None,
    y: float | None = None,
    z: float | None = None,
    **extra: object,
) -> tuple[bool, str]:
    payload: dict[str, object] = {
        "action": action,
        "request_id": int(request_id),
    }
    if x is not None:
        payload["x"] = float(x)
    if y is not None:
        payload["y"] = float(y)
    if z is not None:
        payload["z"] = float(z)
    for key, value in extra.items():
        if value is None:
            continue
        if isinstance(value, bool):
            payload[key] = value
        elif isinstance(value, int):
            payload[key] = int(value)
        elif isinstance(value, float):
            payload[key] = float(value)
        elif isinstance(value, str):
            payload[key] = value

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        return False, f"无法创建 bridge 请求目录 {path.parent}: {error}"

    tmp_path = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        os.replace(tmp_path, path)
    except OSError as error:
        return False, f"写入 bridge 请求失败: {error}"

    return True, f"已写入 {path}"


def describe_state(state: CheatState) -> str:
    """Short human-readable summary for the status bar / logs."""

    parts: list[str] = []
    if state.godmode:
        parts.append("无敌")
    if state.inf_stamina:
        parts.append("无限体力")
    if state.weight_zero:
        parts.append("负重解除")
    if state.inf_ammo:
        parts.append("无限弹药")
    if state.no_durability:
        parts.append("耐久不减")
    if state.speed_multiplier != 1.0:
        parts.append(f"移速×{state.speed_multiplier:.1f}")
    if state.jump_multiplier != 1.0:
        parts.append(f"跳跃×{state.jump_multiplier:.1f}")
    if not parts:
        return "未启用任何增强"
    return " / ".join(parts)


# Re-exported so callers don't need to import environment just for a constant.
BRIDGE_MOD = BRIDGE_MOD_NAME
