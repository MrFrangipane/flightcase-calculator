# -*- mode: python ; coding: utf-8 -*-
# Empaquetado con PyInstaller para Windows y macOS.
#   pyinstaller packaging/flightcase.spec --noconfirm
import os
import sys
from PyInstaller.utils.hooks import collect_submodules

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
APP_NAME = "Flightcase Calculator"
VERSION = os.environ.get("APP_VERSION", "0.1.0")

a = Analysis(
    [os.path.join(ROOT, "main.py")],
    pathex=[ROOT],
    datas=[(os.path.join(ROOT, "flightcase", "resources"), os.path.join("flightcase", "resources"))],
    # PyOpenGL carga sus módulos de plataforma de forma dinámica
    hiddenimports=collect_submodules("OpenGL.platform") + collect_submodules("OpenGL.arrays"),
    excludes=["tkinter", "pytest"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    console=False,
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name=APP_NAME, upx=False)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name=f"{APP_NAME}.app",
        bundle_identifier="com.eldoctormail.flightcasecalculator",
        version=VERSION,
        info_plist={
            "CFBundleShortVersionString": VERSION,
            "CFBundleVersion": VERSION,
            "NSHighResolutionCapable": True,
            "LSMinimumSystemVersion": "12.0",
            "CFBundleDocumentTypes": [{
                "CFBundleTypeName": "Proyecto de flightcase",
                "CFBundleTypeExtensions": ["fcproj"],
                "CFBundleTypeRole": "Editor",
            }],
        },
    )
