# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec — build with:  pyinstaller protrader.spec
import os, sys
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

block_cipher = None
hidden = (collect_submodules("strategies") + collect_submodules("core") + collect_submodules("ui")
          + collect_submodules("sklearn") + collect_submodules("pyqtgraph") + ["yfinance", "websocket", "cv2", "matplotlib.backends.backend_agg"])
datas = [("assets", "assets"), ("tests/real_charts", "tests/real_charts")]
for f in ("data/playbook.json", "data/audit.json", "data/library.json", "data/vision_robustness.json", "data/vision_real.json"):
    if os.path.exists(f):
        datas.append((f, "data"))
if os.path.isdir("data/models"):
    datas.append(("data/models", "data/models"))
datas += collect_data_files("sklearn", include_py_files=False)
datas += collect_data_files("pyqtgraph", include_py_files=False)

a = Analysis(["main.py"], pathex=["."], binaries=[], datas=datas, hiddenimports=hidden, hookspath=[], runtime_hooks=[],
             excludes=["tkinter", "PyQt5", "PySide6", "torch", "tensorflow", "IPython", "notebook", "pytest"],
             win_no_prefer_redirects=False, win_private_assemblies=False, cipher=block_cipher, noarchive=False)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
icon = "assets/icon.ico" if sys.platform.startswith("win") else ("assets/icon.icns" if sys.platform == "darwin" else None)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="ProTrader", debug=False, bootloader_ignore_signals=False, strip=False,
          upx=False, console=False, icon=icon)
coll = COLLECT(exe, a.binaries, a.zipfiles, a.datas, strip=False, upx=False, name="ProTrader")
if sys.platform == "darwin":
    app = BUNDLE(coll, name="ProTrader.app", icon=icon, bundle_identifier="ir.protrader.academy",
                 info_plist={"NSHighResolutionCapable": True, "LSMinimumSystemVersion": "11.0"})
