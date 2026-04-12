# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

project_root = Path.cwd()
src_root = project_root / "src"
data_enums = src_root / "palworld_trainer" / "data" / "enums"
bridge_source = project_root / "integrations" / "ue4ss" / "PalworldTrainerBridge"

datas = []

if data_enums.exists():
    for lua_file in data_enums.glob("*.lua"):
        datas.append((str(lua_file), "palworld_trainer/data/enums"))

if bridge_source.exists():
    for entry in bridge_source.rglob("*"):
        if entry.is_file():
            relative = entry.relative_to(bridge_source.parent)
            datas.append((str(entry), str(Path("integrations/ue4ss") / relative.parent)))

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
