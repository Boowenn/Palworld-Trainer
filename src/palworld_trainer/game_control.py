"""Win32 game window control and keystroke injection.

The trainer talks to Palworld by simulating keystrokes into the running game
window. The flow is:

1. Find the Palworld window by its title.
2. Focus it (restore if minimized, send a dummy key so Windows allows
   SetForegroundWindow, then SetForegroundWindow).
3. Tap Enter to open the chat box.
4. Type the command as Unicode keystrokes (KEYEVENTF_UNICODE so no keyboard
   layout issues).
5. Tap Enter to send it.

All cheat commands are registered by the third party ClientCheatCommands mod
and start with ``@!``. The trainer only types them, it does not interpret them.
"""

from __future__ import annotations

import base64
import ctypes
import json
import os
import subprocess
import sys
import tempfile
import time
from ctypes import wintypes
from dataclasses import dataclass
from pathlib import Path

# ---------------------------------------------------------------------------
# Win32 plumbing
# ---------------------------------------------------------------------------

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

SW_RESTORE = 9

INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004

VK_RETURN = 0x0D
VK_CONTROL = 0x11
VK_MENU = 0x12  # Alt key, used as the "unblock SetForegroundWindow" tap.
VK_A = 0x41
VK_BACK = 0x08
VK_ESCAPE = 0x1B

CHAT_HELPER_FLAG = "--chat-helper"
CHAT_HELPER_PAYLOAD_ENV = "PALWORLD_TRAINER_CHAT_HELPER_PAYLOAD"
CHAT_HELPER_RESULT_ENV = "PALWORLD_TRAINER_CHAT_HELPER_RESULT"


ULONG_PTR = ctypes.c_size_t


class KEYBDINPUT(ctypes.Structure):
    _fields_ = (
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    )


class MOUSEINPUT(ctypes.Structure):
    _fields_ = (
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    )


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = (
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    )


class _InputUnion(ctypes.Union):
    _fields_ = (
        ("ki", KEYBDINPUT),
        ("mi", MOUSEINPUT),
        ("hi", HARDWAREINPUT),
    )


class INPUT(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = (
        ("type", wintypes.DWORD),
        ("u", _InputUnion),
    )


user32.SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int)
user32.SendInput.restype = wintypes.UINT

user32.FindWindowW.argtypes = (wintypes.LPCWSTR, wintypes.LPCWSTR)
user32.FindWindowW.restype = wintypes.HWND

user32.IsWindow.argtypes = (wintypes.HWND,)
user32.IsWindow.restype = wintypes.BOOL

user32.IsIconic.argtypes = (wintypes.HWND,)
user32.IsIconic.restype = wintypes.BOOL

user32.ShowWindow.argtypes = (wintypes.HWND, ctypes.c_int)
user32.ShowWindow.restype = wintypes.BOOL

user32.SetForegroundWindow.argtypes = (wintypes.HWND,)
user32.SetForegroundWindow.restype = wintypes.BOOL

user32.GetForegroundWindow.restype = wintypes.HWND

user32.GetWindowTextW.argtypes = (wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
user32.GetWindowTextW.restype = ctypes.c_int

user32.GetWindowTextLengthW.argtypes = (wintypes.HWND,)
user32.GetWindowTextLengthW.restype = ctypes.c_int

EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
user32.EnumWindows.argtypes = (EnumWindowsProc, wintypes.LPARAM)
user32.EnumWindows.restype = wintypes.BOOL

user32.IsWindowVisible.argtypes = (wintypes.HWND,)
user32.IsWindowVisible.restype = wintypes.BOOL

user32.GetClassNameW.argtypes = (wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
user32.GetClassNameW.restype = ctypes.c_int

user32.GetWindowThreadProcessId.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.DWORD))
user32.GetWindowThreadProcessId.restype = wintypes.DWORD


# ---------------------------------------------------------------------------
# Public data classes
# ---------------------------------------------------------------------------


@dataclass
class SendResult:
    """Outcome of :func:`send_chat_command`."""

    ok: bool
    message: str
    command: str


def _result_to_dict(result: SendResult) -> dict[str, object]:
    return {
        "ok": bool(result.ok),
        "message": str(result.message),
        "command": str(result.command),
    }


def _result_from_dict(payload: object) -> SendResult:
    if not isinstance(payload, dict):
        return SendResult(False, "Invalid helper payload.", "")
    return SendResult(
        bool(payload.get("ok")),
        str(payload.get("message", "")),
        str(payload.get("command", "")),
    )


def _results_from_json_text(text: str) -> list[SendResult]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return [SendResult(False, "Invalid helper result JSON.", "")]

    if not isinstance(payload, list):
        return [SendResult(False, "Invalid helper result payload.", "")]
    return [_result_from_dict(item) for item in payload]


def _serialize_results(results: list[SendResult]) -> str:
    return json.dumps([_result_to_dict(result) for result in results], ensure_ascii=False)


def _helper_command() -> list[str]:
    if getattr(sys, "frozen", False):
        return [sys.executable, CHAT_HELPER_FLAG]
    return [sys.executable, "-m", "palworld_trainer", CHAT_HELPER_FLAG]


def _helper_env(payload_b64: str, result_path: Path) -> dict[str, str]:
    env = os.environ.copy()
    env[CHAT_HELPER_PAYLOAD_ENV] = payload_b64
    env[CHAT_HELPER_RESULT_ENV] = str(result_path)
    if not getattr(sys, "frozen", False):
        src_root = Path(__file__).resolve().parents[1]
        existing = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = (
            str(src_root) if not existing else str(src_root) + os.pathsep + existing
        )
    return env


# ---------------------------------------------------------------------------
# Window discovery
# ---------------------------------------------------------------------------


def _get_window_title(hwnd: int) -> str:
    length = user32.GetWindowTextLengthW(hwnd)
    if length <= 0:
        return ""
    buffer = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buffer, length + 1)
    return buffer.value


def _get_window_class(hwnd: int) -> str:
    buffer = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buffer, 256)
    return buffer.value


def _window_pid(hwnd: int) -> int:
    out = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(out))
    return int(out.value)


def find_palworld_window() -> int | None:
    """Return the HWND of the Palworld game window, or ``None``.

    Strategy: find the Palworld process by PID, then look for its visible
    top-level window with class ``UnrealWindow``.  This avoids false
    positives from the trainer's own window (whose title also contains
    "Palworld") and handles the game having unusual window titles like
    ``Pal  `` instead of ``Palworld``.
    """

    from . import memory

    pid = memory.find_process_id()
    if pid is None:
        return None

    found: list[int] = []

    def _cb(hwnd: int, _lparam: int) -> bool:
        if not user32.IsWindowVisible(hwnd):
            return True
        if _window_pid(hwnd) != pid:
            return True
        cls = _get_window_class(hwnd)
        if cls == "UnrealWindow":
            found.append(int(hwnd))
            return False
        return True

    user32.EnumWindows(EnumWindowsProc(_cb), 0)
    return found[0] if found else None


def is_game_running() -> bool:
    """Check whether Palworld is actually running by looking for its process.

    Using the process name (Palworld-Win64-Shipping.exe) instead of the
    window title avoids false positives from windows whose title happens
    to contain "Palworld" (like this trainer itself).
    """

    from . import memory

    return memory.find_process_id() is not None


# ---------------------------------------------------------------------------
# Focus + keystroke injection
# ---------------------------------------------------------------------------


def _make_key_input(vk: int, key_up: bool) -> INPUT:
    flags = KEYEVENTF_KEYUP if key_up else 0
    ki = KEYBDINPUT(wVk=vk, wScan=0, dwFlags=flags, time=0, dwExtraInfo=0)
    return INPUT(type=INPUT_KEYBOARD, u=_InputUnion(ki=ki))


def _make_unicode_input(char: str, key_up: bool) -> INPUT:
    flags = KEYEVENTF_UNICODE | (KEYEVENTF_KEYUP if key_up else 0)
    ki = KEYBDINPUT(wVk=0, wScan=ord(char), dwFlags=flags, time=0, dwExtraInfo=0)
    return INPUT(type=INPUT_KEYBOARD, u=_InputUnion(ki=ki))


def _send_inputs(inputs: list[INPUT]) -> bool:
    count = len(inputs)
    array = (INPUT * count)(*inputs)
    sent = user32.SendInput(count, array, ctypes.sizeof(INPUT))
    return sent == count


def _tap_vk(vk: int, delay_ms: int = 30) -> None:
    _send_inputs([_make_key_input(vk, False), _make_key_input(vk, True)])
    time.sleep(delay_ms / 1000.0)


def _tap_chord(modifiers: list[int], vk: int, delay_ms: int = 30) -> None:
    inputs = [_make_key_input(modifier, False) for modifier in modifiers]
    inputs.extend([_make_key_input(vk, False), _make_key_input(vk, True)])
    inputs.extend(_make_key_input(modifier, True) for modifier in reversed(modifiers))
    _send_inputs(inputs)
    time.sleep(delay_ms / 1000.0)


def _clear_chat_input() -> None:
    # Some sessions reopen chat with stale text still selected or partially present.
    # Clearing the input box first makes fallback command delivery much less flaky.
    _tap_chord([VK_CONTROL], VK_A, delay_ms=20)
    _tap_vk(VK_BACK, delay_ms=20)


def _type_unicode(text: str, delay_ms: int = 5) -> None:
    for char in text:
        if char == "\n":
            _tap_vk(VK_RETURN)
            continue
        _send_inputs(
            [
                _make_unicode_input(char, False),
                _make_unicode_input(char, True),
            ]
        )
        if delay_ms:
            time.sleep(delay_ms / 1000.0)


def _focus_window(hwnd: int) -> bool:
    if not user32.IsWindow(hwnd):
        return False
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, SW_RESTORE)
    # Windows refuses SetForegroundWindow unless the calling thread holds
    # foreground privilege. Tapping Alt briefly convinces Windows that we
    # are allowed. This is a well-known workaround.
    _tap_vk(VK_MENU, delay_ms=10)
    result = bool(user32.SetForegroundWindow(hwnd))
    time.sleep(0.1)
    return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def send_chat_command(
    command: str,
    *,
    chat_open_delay_ms: int = 180,
    post_open_delay_ms: int = 140,
    per_char_delay_ms: int = 8,
    pre_send_delay_ms: int = 80,
    restore_focus: bool = True,
) -> SendResult:
    """Focus Palworld and type ``command`` into the in-game chat box.

    The command is typed verbatim. Callers should already prefix it with
    ``@!`` or similar — this function does not validate command syntax.

    When *restore_focus* is True (default), the function records the
    currently active window before switching to Palworld and restores it
    after the command has been sent. This prevents the trainer UI from
    "jumping" back and forth on every button click.
    """

    stripped = command.strip()
    if not stripped:
        return SendResult(False, "Command is empty.", command)

    hwnd = find_palworld_window()
    if not hwnd:
        return SendResult(
            False,
            "Palworld window not found. Start the game and load into a world first.",
            command,
        )

    # Remember who had focus so we can give it back after typing.
    prev_hwnd = user32.GetForegroundWindow() if restore_focus else None

    if not _focus_window(hwnd):
        return SendResult(
            False,
            "Could not focus the Palworld window. Try alt-tabbing to the game once and retry.",
            command,
        )

    # Give the game a tick to settle after focus, then open chat.
    time.sleep(chat_open_delay_ms / 1000.0)
    _tap_vk(VK_RETURN)
    time.sleep(post_open_delay_ms / 1000.0)
    _clear_chat_input()
    time.sleep(0.04)

    _type_unicode(stripped, delay_ms=per_char_delay_ms)

    time.sleep(pre_send_delay_ms / 1000.0)
    _tap_vk(VK_RETURN)

    # Restore focus to the previous window (usually the trainer itself).
    if prev_hwnd and prev_hwnd != hwnd and user32.IsWindow(prev_hwnd):
        time.sleep(0.15)
        _focus_window(prev_hwnd)

    return SendResult(True, f"Sent: {stripped}", stripped)


def send_chat_commands(
    commands: list[str],
    *,
    between_ms: int = 250,
    restore_focus: bool = True,
) -> list[SendResult]:
    """Send a batch of commands one after another, focusing once per command.

    A small pause between commands keeps Palworld's chat pipeline happy.
    """

    results: list[SendResult] = []
    for index, command in enumerate(commands):
        result = send_chat_command(command, restore_focus=restore_focus)
        results.append(result)
        if not result.ok:
            break
        if index < len(commands) - 1:
            time.sleep(between_ms / 1000.0)
    return results


def send_chat_commands_isolated(
    commands: list[str],
    *,
    between_ms: int = 250,
    restore_focus: bool = True,
    timeout_ms: int = 20000,
) -> list[SendResult]:
    """Send commands from a helper process to avoid Tk/input contention."""

    normalized = [command.strip() for command in commands if command and command.strip()]
    if not normalized:
        return []

    payload = {
        "commands": normalized,
        "between_ms": int(between_ms),
        "restore_focus": bool(restore_focus),
    }
    payload_b64 = base64.b64encode(
        json.dumps(payload, ensure_ascii=False).encode("utf-8")
    ).decode("ascii")

    with tempfile.TemporaryDirectory(prefix="palworld-chat-helper-") as tmp:
        result_path = Path(tmp) / "result.json"
        env = _helper_env(payload_b64, result_path)
        kwargs: dict[str, object] = {
            "check": False,
            "env": env,
            "timeout": max(timeout_ms / 1000.0, 1.0),
        }
        if os.name == "nt":
            kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)

        try:
            completed = subprocess.run(_helper_command(), **kwargs)
        except (OSError, subprocess.TimeoutExpired) as error:
            fallback_results = send_chat_commands(
                normalized,
                between_ms=between_ms,
                restore_focus=restore_focus,
            )
            if fallback_results:
                return fallback_results
            return [SendResult(False, f"Chat helper failed to start: {error}", normalized[0])]

        if result_path.exists():
            return _results_from_json_text(result_path.read_text(encoding="utf-8"))

        message = f"Chat helper exited with code {completed.returncode}."
        return [SendResult(False, message, normalized[0])]


def run_chat_helper_from_env() -> int:
    """CLI helper entry point used by the GUI process for clean SendInput."""

    result_path_text = os.environ.get(CHAT_HELPER_RESULT_ENV, "").strip()
    payload_b64 = os.environ.get(CHAT_HELPER_PAYLOAD_ENV, "").strip()
    if not result_path_text or not payload_b64:
        return 2

    result_path = Path(result_path_text)
    try:
        payload = json.loads(base64.b64decode(payload_b64).decode("utf-8"))
    except (ValueError, json.JSONDecodeError):
        results = [SendResult(False, "Chat helper received invalid payload.", "")]
        result_path.write_text(_serialize_results(results), encoding="utf-8")
        return 1

    raw_commands = payload.get("commands", [])
    commands = [
        str(command).strip()
        for command in raw_commands
        if isinstance(command, str) and command.strip()
    ]
    between_ms = int(payload.get("between_ms", 250))
    restore_focus = bool(payload.get("restore_focus", True))

    try:
        results = send_chat_commands(
            commands,
            between_ms=between_ms,
            restore_focus=restore_focus,
        )
    except Exception as error:  # noqa: BLE001
        first_command = commands[0] if commands else ""
        results = [SendResult(False, f"Chat helper crashed: {error}", first_command)]

    result_path.write_text(_serialize_results(results), encoding="utf-8")
    return 0 if results and all(result.ok for result in results) else 1
