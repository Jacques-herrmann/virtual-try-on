# -*- mode: python ; coding: utf-8 -*-
# PyInstaller, mode dossier : `pyinstaller packaging/vto.spec --noconfirm` depuis la racine,
# après `npm run build` (le front compilé est embarqué depuis backend/src/vto/api/static).
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_submodules
from PyInstaller.utils.win32.versioninfo import (
    FixedFileInfo,
    StringFileInfo,
    StringStruct,
    StringTable,
    VarFileInfo,
    VarStruct,
    VSVersionInfo,
)

import vto

HERE = Path(SPECPATH)
VERSION = vto.__version__

if not (HERE.parent / "backend/src/vto/api/static/index.html").is_file():
    raise SystemExit("Front non compilé : lancer `npm run build` dans frontend/.")

# vto : front compilé, copie de vinted.json, pack de scènes ; modules importés dynamiquement.
datas = collect_data_files("vto")
hiddenimports = collect_submodules("vto")
binaries = []

# Playwright n'a pas de hook : son pilote (node.exe + package) doit suivre en entier.
pw_datas, pw_binaries, pw_hidden = collect_all("playwright")
datas += pw_datas
binaries += pw_binaries
hiddenimports += pw_hidden


def _version_tuple(version: str) -> tuple[int, int, int, int]:
    from packaging.version import Version

    parts = list(Version(version).release) + [0, 0, 0]
    return tuple(parts[:4])


numbers = _version_tuple(VERSION)
version_info = VSVersionInfo(
    ffi=FixedFileInfo(filevers=numbers, prodvers=numbers),
    kids=[
        StringFileInfo(
            [
                StringTable(
                    "040C04B0",
                    [
                        StringStruct("CompanyName", "Wearo"),
                        StringStruct("FileDescription", "Wearo"),
                        StringStruct("FileVersion", VERSION),
                        StringStruct("InternalName", "Wearo"),
                        StringStruct("OriginalFilename", "Wearo.exe"),
                        StringStruct("ProductName", "Wearo"),
                        StringStruct("ProductVersion", VERSION),
                    ],
                )
            ]
        ),
        VarFileInfo([VarStruct("Translation", [0x040C, 1200])]),
    ],
)

a = Analysis(
    [str(HERE / "launcher.py")],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "pytest", "ruff"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Wearo",
    icon=str(HERE / "icon.ico"),
    version=version_info,
    console=False,
    disable_windowed_traceback=False,
    upx=False,  # UPX augmente les faux positifs antivirus
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="Wearo",
)
