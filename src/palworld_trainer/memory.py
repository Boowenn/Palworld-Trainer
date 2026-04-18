"""Windows process memory access for the 傻瓜版 trainer.

This module talks to a running ``Palworld-Win64-Shipping.exe`` through the
standard Win32 APIs (``OpenProcess`` / ``ReadProcessMemory`` /
``WriteProcessMemory`` / ``VirtualQueryEx``). It's the bits that let the
trainer read and write the player's HP / SP / weight / speed fields
**without** depending on UE4SS or any in-game mod — the game runs vanilla,
and we attach from the outside.

Everything here is deliberately free of tkinter, so it can be unit-tested
headless and reused from a CLI or a future pytest rig.
"""

from __future__ import annotations

import ctypes
import re
import struct
from ctypes import wintypes
from dataclasses import dataclass
from typing import Iterable, Iterator

# ---------------------------------------------------------------------------
# Win32 constants
# ---------------------------------------------------------------------------

PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
PROCESS_VM_READ = 0x0010
PROCESS_VM_WRITE = 0x0020
PROCESS_VM_OPERATION = 0x0008

READ_ACCESS = PROCESS_QUERY_INFORMATION | PROCESS_VM_READ
READ_WRITE_ACCESS = (
    PROCESS_QUERY_INFORMATION | PROCESS_VM_READ | PROCESS_VM_WRITE | PROCESS_VM_OPERATION
)

MEM_COMMIT = 0x1000
MEM_IMAGE = 0x1000000
MEM_PRIVATE = 0x20000
MEM_MAPPED = 0x40000

PAGE_NOACCESS = 0x01
PAGE_READONLY = 0x02
PAGE_READWRITE = 0x04
PAGE_WRITECOPY = 0x08
PAGE_EXECUTE = 0x10
PAGE_EXECUTE_READ = 0x20
PAGE_EXECUTE_READWRITE = 0x40
PAGE_EXECUTE_WRITECOPY = 0x80
PAGE_GUARD = 0x100

READABLE_PROTECTS = (
    PAGE_READONLY
    | PAGE_READWRITE
    | PAGE_WRITECOPY
    | PAGE_EXECUTE_READ
    | PAGE_EXECUTE_READWRITE
    | PAGE_EXECUTE_WRITECOPY
)
WRITABLE_PROTECTS = PAGE_READWRITE | PAGE_WRITECOPY | PAGE_EXECUTE_READWRITE | PAGE_EXECUTE_WRITECOPY
EXEC_PROTECTS = PAGE_EXECUTE | PAGE_EXECUTE_READ | PAGE_EXECUTE_READWRITE | PAGE_EXECUTE_WRITECOPY

# Snapshot flags for CreateToolhelp32Snapshot
TH32CS_SNAPPROCESS = 0x00000002

# ---------------------------------------------------------------------------
# ctypes plumbing
# ---------------------------------------------------------------------------


class MODULEINFO(ctypes.Structure):
    _fields_ = [
        ("lpBaseOfDll", ctypes.c_void_p),
        ("SizeOfImage", wintypes.DWORD),
        ("EntryPoint", ctypes.c_void_p),
    ]


class MEMORY_BASIC_INFORMATION64(ctypes.Structure):
    _fields_ = [
        ("BaseAddress", ctypes.c_ulonglong),
        ("AllocationBase", ctypes.c_ulonglong),
        ("AllocationProtect", wintypes.DWORD),
        ("__alignment1", wintypes.DWORD),
        ("RegionSize", ctypes.c_ulonglong),
        ("State", wintypes.DWORD),
        ("Protect", wintypes.DWORD),
        ("Type", wintypes.DWORD),
        ("__alignment2", wintypes.DWORD),
    ]


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.c_void_p),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", wintypes.LONG),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", wintypes.WCHAR * 260),
    ]


def _load_apis() -> tuple:
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)

    k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    k32.OpenProcess.restype = wintypes.HANDLE

    k32.CloseHandle.argtypes = [wintypes.HANDLE]
    k32.CloseHandle.restype = wintypes.BOOL

    k32.ReadProcessMemory.argtypes = [
        wintypes.HANDLE,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_size_t,
        ctypes.POINTER(ctypes.c_size_t),
    ]
    k32.ReadProcessMemory.restype = wintypes.BOOL

    k32.WriteProcessMemory.argtypes = [
        wintypes.HANDLE,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_size_t,
        ctypes.POINTER(ctypes.c_size_t),
    ]
    k32.WriteProcessMemory.restype = wintypes.BOOL

    k32.VirtualQueryEx.argtypes = [
        wintypes.HANDLE,
        ctypes.c_void_p,
        ctypes.POINTER(MEMORY_BASIC_INFORMATION64),
        ctypes.c_size_t,
    ]
    k32.VirtualQueryEx.restype = ctypes.c_size_t

    k32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    k32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE

    k32.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
    k32.Process32FirstW.restype = wintypes.BOOL

    k32.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
    k32.Process32NextW.restype = wintypes.BOOL

    psapi.EnumProcessModules.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(wintypes.HMODULE),
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
    ]
    psapi.EnumProcessModules.restype = wintypes.BOOL

    psapi.GetModuleBaseNameW.argtypes = [
        wintypes.HANDLE,
        wintypes.HMODULE,
        wintypes.LPWSTR,
        wintypes.DWORD,
    ]
    psapi.GetModuleBaseNameW.restype = wintypes.DWORD

    psapi.GetModuleInformation.argtypes = [
        wintypes.HANDLE,
        wintypes.HMODULE,
        ctypes.POINTER(MODULEINFO),
        wintypes.DWORD,
    ]
    psapi.GetModuleInformation.restype = wintypes.BOOL

    return k32, psapi


try:
    _K32, _PSAPI = _load_apis()
except (OSError, AttributeError):  # non-Windows / headless test environments
    _K32 = None
    _PSAPI = None


# ---------------------------------------------------------------------------
# Process lookup
# ---------------------------------------------------------------------------


PALWORLD_PROCESS_NAME = "Palworld-Win64-Shipping.exe"


def find_process_id(name: str = PALWORLD_PROCESS_NAME) -> int | None:
    """Return the PID of the first process matching ``name`` (case-insensitive)."""

    if _K32 is None:
        return None
    snap = _K32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if not snap or snap == wintypes.HANDLE(-1).value:
        return None
    try:
        entry = PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
        target = name.lower()
        if not _K32.Process32FirstW(snap, ctypes.byref(entry)):
            return None
        while True:
            if entry.szExeFile.lower() == target:
                return int(entry.th32ProcessID)
            if not _K32.Process32NextW(snap, ctypes.byref(entry)):
                return None
    finally:
        _K32.CloseHandle(snap)


# ---------------------------------------------------------------------------
# Process handle
# ---------------------------------------------------------------------------


@dataclass
class ModuleInfo:
    name: str
    base: int
    size: int


class ProcessHandle:
    """A thin wrapper around an ``OpenProcess`` handle with read/write helpers."""

    def __init__(self, pid: int, *, writable: bool = True) -> None:
        if _K32 is None:
            raise RuntimeError("memory module only works on Windows")
        self.pid = pid
        access = READ_WRITE_ACCESS if writable else READ_ACCESS
        self._handle = _K32.OpenProcess(access, False, pid)
        if not self._handle:
            err = ctypes.get_last_error()
            raise OSError(err, f"OpenProcess failed for pid {pid}: WinError {err}")

    # -- lifecycle ------------------------------------------------------

    def close(self) -> None:
        if self._handle:
            _K32.CloseHandle(self._handle)
            self._handle = None

    def __enter__(self) -> "ProcessHandle":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    @property
    def handle(self) -> int:
        if not self._handle:
            raise RuntimeError("ProcessHandle is closed")
        return self._handle

    # -- module enumeration --------------------------------------------

    def iter_modules(self) -> Iterator[ModuleInfo]:
        arr_size = 1024
        arr = (wintypes.HMODULE * arr_size)()
        needed = wintypes.DWORD()
        if not _PSAPI.EnumProcessModules(
            self.handle, arr, ctypes.sizeof(arr), ctypes.byref(needed)
        ):
            return
        count = min(needed.value // ctypes.sizeof(wintypes.HMODULE), arr_size)
        for i in range(count):
            name_buf = ctypes.create_unicode_buffer(260)
            _PSAPI.GetModuleBaseNameW(self.handle, arr[i], name_buf, 260)
            info = MODULEINFO()
            if not _PSAPI.GetModuleInformation(
                self.handle, arr[i], ctypes.byref(info), ctypes.sizeof(info)
            ):
                continue
            yield ModuleInfo(
                name=name_buf.value,
                base=int(info.lpBaseOfDll or 0),
                size=int(info.SizeOfImage),
            )

    def main_module(self) -> ModuleInfo | None:
        for mod in self.iter_modules():
            low = mod.name.lower()
            if "palworld" in low and "shipping" in low:
                return mod
        return None

    # -- memory regions ------------------------------------------------

    def iter_regions(
        self,
        *,
        start: int = 0,
        end: int | None = None,
        protect_mask: int = READABLE_PROTECTS,
        only_private: bool = False,
        max_region_size: int | None = None,
    ) -> Iterator[tuple[int, int, int]]:
        """Yield ``(base, size, protect)`` for committed regions in [start, end).

        ``only_private`` — skip MEM_MAPPED / MEM_IMAGE (keeps heap-style regions only).
        ``max_region_size`` — skip any region larger than this (skips giant
        texture / mesh caches when you only care about gameplay data).
        """

        addr = start
        limit = end if end is not None else (1 << 47)  # user-mode ceiling on x64
        mbi = MEMORY_BASIC_INFORMATION64()
        mbi_size = ctypes.sizeof(mbi)
        while addr < limit:
            ret = _K32.VirtualQueryEx(
                self.handle,
                ctypes.c_void_p(addr),
                ctypes.byref(mbi),
                mbi_size,
            )
            if ret == 0:
                break
            base = int(mbi.BaseAddress)
            size = int(mbi.RegionSize)
            if size == 0:
                break
            protect = int(mbi.Protect)
            mem_type = int(mbi.Type)
            if (
                mbi.State == MEM_COMMIT
                and protect & protect_mask
                and not (protect & PAGE_GUARD)
                and not (protect & PAGE_NOACCESS)
                and (not only_private or mem_type == MEM_PRIVATE)
                and (max_region_size is None or size <= max_region_size)
            ):
                region_start = max(base, addr)
                region_end = base + size
                if region_end > region_start:
                    yield region_start, region_end - region_start, protect
            addr = base + size

    # -- read --------------------------------------------------------------

    def read(self, addr: int, size: int) -> bytes | None:
        buf = (ctypes.c_ubyte * size)()
        read = ctypes.c_size_t()
        ok = _K32.ReadProcessMemory(
            self.handle, ctypes.c_void_p(addr), buf, size, ctypes.byref(read)
        )
        if not ok or read.value == 0:
            return None
        return bytes(buf[: read.value])

    def read_f32(self, addr: int) -> float | None:
        data = self.read(addr, 4)
        if data is None or len(data) < 4:
            return None
        return struct.unpack("<f", data)[0]

    def read_i32(self, addr: int) -> int | None:
        data = self.read(addr, 4)
        if data is None or len(data) < 4:
            return None
        return struct.unpack("<i", data)[0]

    def read_u8(self, addr: int) -> int | None:
        data = self.read(addr, 1)
        if data is None or len(data) < 1:
            return None
        return data[0]

    def read_u64(self, addr: int) -> int | None:
        data = self.read(addr, 8)
        if data is None or len(data) < 8:
            return None
        return struct.unpack("<Q", data)[0]

    # -- write -------------------------------------------------------------

    def write(self, addr: int, data: bytes) -> bool:
        buf = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
        written = ctypes.c_size_t()
        ok = _K32.WriteProcessMemory(
            self.handle, ctypes.c_void_p(addr), buf, len(data), ctypes.byref(written)
        )
        return bool(ok and written.value == len(data))

    def write_f32(self, addr: int, value: float) -> bool:
        return self.write(addr, struct.pack("<f", value))

    def write_i32(self, addr: int, value: int) -> bool:
        return self.write(addr, struct.pack("<i", value))

    def write_u8(self, addr: int, value: int) -> bool:
        return self.write(addr, bytes([int(value) & 0xFF]))


# ---------------------------------------------------------------------------
# Value scanning
# ---------------------------------------------------------------------------


def pack_f32(value: float) -> bytes:
    return struct.pack("<f", value)


def pack_i32(value: int) -> bytes:
    return struct.pack("<i", value)


def pack_u8(value: int) -> bytes:
    return bytes([int(value) & 0xFF])


def _iter_exact_matches(chunk: bytes, needle: bytes, stride: int = 4) -> Iterator[int]:
    """Yield indices in ``chunk`` that match ``needle`` aligned on ``stride``."""

    nlen = len(needle)
    pos = 0
    find = chunk.find
    while True:
        idx = find(needle, pos)
        if idx < 0:
            return
        # Enforce alignment — floats / ints in UE classes are typically 4-byte
        # aligned, and filtering on alignment slashes the number of false
        # positives by ~4x.
        if idx % stride == 0:
            yield idx
        pos = idx + 1
        if pos + nlen > len(chunk):
            return


@dataclass
class ScanSnapshot:
    """Result of a value scan — list of absolute addresses and metadata."""

    addresses: list[int]
    value: float
    kind: str  # "f32", "i32"

    def __len__(self) -> int:  # pragma: no cover - trivial
        return len(self.addresses)


def scan_f32(
    process: ProcessHandle,
    value: float,
    *,
    max_hits: int = 2_000_000,
    protect_mask: int = WRITABLE_PROTECTS,
    max_region_size: int = 32 * 1024 * 1024,
    only_private: bool = True,
) -> ScanSnapshot:
    """Full scan for ``value`` as a little-endian float32 in writable memory.

    We only look in writable pages because read-only regions can't hold live
    player stats. By default we also skip anything larger than ``max_region_size``
    (texture / mesh caches) and anything that isn't MEM_PRIVATE (mapped files),
    which is where UE gameplay allocations always live. That keeps the scan
    bounded to a few hundred MB on a typical Palworld session.
    """

    needle = pack_f32(float(value))
    hits: list[int] = []
    for region_addr, region_size, protect in process.iter_regions(
        protect_mask=protect_mask,
        only_private=only_private,
        max_region_size=max_region_size,
    ):
        offset = 0
        while offset < region_size:
            chunk_size = min(8 * 1024 * 1024, region_size - offset)
            chunk = process.read(region_addr + offset, chunk_size)
            if chunk is None:
                offset += chunk_size
                continue
            for idx in _iter_exact_matches(chunk, needle):
                hits.append(region_addr + offset + idx)
                if len(hits) >= max_hits:
                    return ScanSnapshot(addresses=hits, value=value, kind="f32")
            # No overlap needed — 4-byte aligned needle, 4-aligned region start.
            offset += chunk_size
    return ScanSnapshot(addresses=hits, value=value, kind="f32")


def refine_f32(
    process: ProcessHandle,
    snapshot: ScanSnapshot,
    new_value: float,
    *,
    tolerance: float = 0.0,
) -> ScanSnapshot:
    """Keep only the addresses in ``snapshot`` that now hold ``new_value``."""

    target = float(new_value)
    kept: list[int] = []
    for addr in snapshot.addresses:
        current = process.read_f32(addr)
        if current is None:
            continue
        if tolerance <= 0.0:
            if current == target:
                kept.append(addr)
        else:
            if abs(current - target) <= tolerance:
                kept.append(addr)
    return ScanSnapshot(addresses=kept, value=new_value, kind="f32")


def refine_f32_between(
    process: ProcessHandle,
    snapshot: ScanSnapshot,
    low: float,
    high: float,
) -> ScanSnapshot:
    """Keep addresses whose current value is in [low, high]. Midpoint is recorded."""

    lo = float(low)
    hi = float(high)
    kept: list[int] = []
    for addr in snapshot.addresses:
        current = process.read_f32(addr)
        if current is None:
            continue
        if lo <= current <= hi:
            kept.append(addr)
    return ScanSnapshot(addresses=kept, value=(lo + hi) / 2, kind="f32")


# ---------------------------------------------------------------------------
# int32 scan / refine
# ---------------------------------------------------------------------------


def scan_i32(
    process: ProcessHandle,
    value: int,
    *,
    max_hits: int = 2_000_000,
    protect_mask: int = WRITABLE_PROTECTS,
    max_region_size: int = 32 * 1024 * 1024,
    only_private: bool = True,
) -> ScanSnapshot:
    """Full scan for ``value`` as a little-endian signed int32."""

    needle = pack_i32(int(value))
    hits: list[int] = []
    for region_addr, region_size, _protect in process.iter_regions(
        protect_mask=protect_mask,
        only_private=only_private,
        max_region_size=max_region_size,
    ):
        offset = 0
        while offset < region_size:
            chunk_size = min(8 * 1024 * 1024, region_size - offset)
            chunk = process.read(region_addr + offset, chunk_size)
            if chunk is None:
                offset += chunk_size
                continue
            for idx in _iter_exact_matches(chunk, needle, stride=4):
                hits.append(region_addr + offset + idx)
                if len(hits) >= max_hits:
                    return ScanSnapshot(addresses=hits, value=float(value), kind="i32")
            offset += chunk_size
    return ScanSnapshot(addresses=hits, value=float(value), kind="i32")


def refine_i32(
    process: ProcessHandle,
    snapshot: ScanSnapshot,
    new_value: int,
) -> ScanSnapshot:
    """Keep addresses in ``snapshot`` whose current int32 value matches."""

    target = int(new_value)
    kept: list[int] = []
    for addr in snapshot.addresses:
        current = process.read_i32(addr)
        if current is not None and current == target:
            kept.append(addr)
    return ScanSnapshot(addresses=kept, value=float(new_value), kind="i32")


# ---------------------------------------------------------------------------
# uint8 scan / refine
# ---------------------------------------------------------------------------


def scan_u8(
    process: ProcessHandle,
    value: int,
    *,
    max_hits: int = 2_000_000,
    protect_mask: int = WRITABLE_PROTECTS,
    max_region_size: int = 32 * 1024 * 1024,
    only_private: bool = True,
) -> ScanSnapshot:
    """Full scan for ``value`` as a single unsigned byte (stride=1, many hits expected)."""

    needle = pack_u8(int(value))
    hits: list[int] = []
    for region_addr, region_size, _protect in process.iter_regions(
        protect_mask=protect_mask,
        only_private=only_private,
        max_region_size=max_region_size,
    ):
        offset = 0
        while offset < region_size:
            chunk_size = min(8 * 1024 * 1024, region_size - offset)
            chunk = process.read(region_addr + offset, chunk_size)
            if chunk is None:
                offset += chunk_size
                continue
            # stride=1: uint8 fields are not necessarily aligned
            for idx in _iter_exact_matches(chunk, needle, stride=1):
                hits.append(region_addr + offset + idx)
                if len(hits) >= max_hits:
                    return ScanSnapshot(addresses=hits, value=float(value), kind="u8")
            offset += chunk_size
    return ScanSnapshot(addresses=hits, value=float(value), kind="u8")


def refine_u8(
    process: ProcessHandle,
    snapshot: ScanSnapshot,
    new_value: int,
) -> ScanSnapshot:
    """Keep addresses in ``snapshot`` whose current byte value matches."""

    target = int(new_value) & 0xFF
    kept: list[int] = []
    for addr in snapshot.addresses:
        current = process.read_u8(addr)
        if current is not None and current == target:
            kept.append(addr)
    return ScanSnapshot(addresses=kept, value=float(new_value), kind="u8")


# ---------------------------------------------------------------------------
# AOB scan (for static offsets inside the main module's code section)
# ---------------------------------------------------------------------------


def parse_aob(pattern: str) -> tuple[bytes, re.Pattern[bytes]]:
    """Compile a Cheat Engine-style 'AA BB ?? CC' pattern to a bytes regex."""

    parts = pattern.split()
    pieces: list[bytes] = []
    raw = bytearray()
    for p in parts:
        if p in ("?", "??"):
            pieces.append(b".")
            raw.append(0)
        else:
            byte = int(p, 16)
            pieces.append(re.escape(bytes([byte])))
            raw.append(byte)
    return bytes(raw), re.compile(b"".join(pieces), re.DOTALL)


def scan_aob_in_module(
    process: ProcessHandle,
    module: ModuleInfo,
    pattern: str,
    *,
    max_hits: int = 16,
) -> list[int]:
    """Scan executable regions inside ``module`` for the given AOB pattern."""

    _raw, regex = parse_aob(pattern)
    hits: list[int] = []
    mod_end = module.base + module.size
    for region_addr, region_size, _protect in process.iter_regions(
        start=module.base, end=mod_end, protect_mask=EXEC_PROTECTS
    ):
        data = process.read(region_addr, region_size)
        if data is None:
            continue
        for match in regex.finditer(data):
            hits.append(region_addr + match.start())
            if len(hits) >= max_hits:
                return hits
    return hits
