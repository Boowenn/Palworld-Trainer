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

import ctypes
import time
from ctypes import wintypes
from dataclasses import dataclass

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
VK_MENU = 0x12  # Alt key, used as the "unblock SetForegroundWindow" tap.
VK_BACK = 0x08
VK_ESCAPE = 0x1B


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


# ---------------------------------------------------------------------------
# Public data classes
# ---------------------------------------------------------------------------


@dataclass
class SendResult:
    """Outcome of :func:`send_chat_command`."""

    ok: bool
    message: str
    command: str


# ---------------------------------------------------------------------------
# Window discovery
# ---------------------------------------------------------------------------


DEFAULT_WINDOW_TITLES = ("Palworld", "Palworld  ")


def _get_window_title(hwnd: int) -> str:
    length = user32.GetWindowTextLengthW(hwnd)
    if length <= 0:
        return ""
    buffer = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buffer, length + 1)
    return buffer.value


def find_palworld_window(title_hints: tuple[str, ...] = DEFAULT_WINDOW_TITLES) -> int | None:
    """Return the HWND of the Palworld game window, or ``None`` if not found.

    First tries an exact ``FindWindowW`` for each hint, then falls back to an
    ``EnumWindows`` scan that looks for a visible top-level window whose title
    contains "Palworld" (case-insensitive).
    """

    for title in title_hints:
        hwnd = user32.FindWindowW(None, title)
        if hwnd:
            return int(hwnd)

    found: list[int] = []

    def _cb(hwnd: int, _lparam: int) -> bool:
        if not user32.IsWindowVisible(hwnd):
            return True
        title = _get_window_title(hwnd)
        if not title:
            return True
        if "palworld" in title.lower():
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

    _type_unicode(stripped, delay_ms=per_char_delay_ms)

    time.sleep(pre_send_delay_ms / 1000.0)
    _tap_vk(VK_RETURN)

    # Restore focus to the previous window (usually the trainer itself).
    if prev_hwnd and prev_hwnd != hwnd and user32.IsWindow(prev_hwnd):
        time.sleep(0.15)
        _focus_window(prev_hwnd)

    return SendResult(True, f"Sent: {stripped}", stripped)


def send_chat_commands(commands: list[str], *, between_ms: int = 250) -> list[SendResult]:
    """Send a batch of commands one after another, focusing once per command.

    A small pause between commands keeps Palworld's chat pipeline happy.
    """

    results: list[SendResult] = []
    for index, command in enumerate(commands):
        result = send_chat_command(command)
        results.append(result)
        if not result.ok:
            break
        if index < len(commands) - 1:
            time.sleep(between_ms / 1000.0)
    return results
