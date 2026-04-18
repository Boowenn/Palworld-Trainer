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
from dataclasses import asdict, dataclass
from pathlib import Path

from .environment import BRIDGE_MOD_NAME, EnvironmentReport


TOGGLES_FILENAME = "toggles.json"


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


def toggles_path_for(report: EnvironmentReport) -> Path | None:
    """Return the absolute path ``toggles.json`` should live at for this game.

    ``None`` means we can't figure out the UE4SS Mods folder yet — the GUI
    should disable the cheat tab and surface the bridge deployment button.
    """

    target = report.trainer_bridge_target
    if target is None:
        return None
    return target / TOGGLES_FILENAME


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
