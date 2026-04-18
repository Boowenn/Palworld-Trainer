# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

project_root = Path.cwd()
src_root = project_root / "src"
data_enums = src_root / "palworld_trainer" / "data" / "enums"
data_coords = src_root / "palworld_trainer" / "data" / "coords"

datas = []

if data_enums.exists():
    for lua_file in data_enums.glob("*.lua"):
        datas.append((str(lua_file), "palworld_trainer/data/enums"))
if data_coords.exists():
    for json_file in data_coords.glob("*.json"):
        datas.append((str(json_file), "palworld_trainer/data/coords"))

hiddenimports = []

a = Analysis(
    [str(src_root / "palworld_trainer" / "__main__.py")],
    pathex=[str(src_root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="PalworldTrainer",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
