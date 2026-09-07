"""
Single source of truth for where the app READS bundled files and WRITES user data.

  * Source checkout:            everything under the repo (data/ next to core/), as before.
  * Frozen build (PyInstaller): read-only bundle lives in sys._MEIPASS; writable data goes to the OS user-data dir
        Windows  %APPDATA%\\ProTrader        macOS  ~/Library/Application Support/ProTrader        Linux  ~/.local/share/protrader
    Bundled seed files (playbook.json, audit.json, models, library) are copied there on first run.
"""
import os
import sys
import shutil

FROZEN = getattr(sys, "frozen", False)
BUNDLE = getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) if not FROZEN else BUNDLE


def user_data_dir():
    if os.environ.get("PROTRADER_DATA"):
        return os.environ["PROTRADER_DATA"]
    if not FROZEN:
        return os.path.join(SRC_ROOT, "data")
    if sys.platform.startswith("win"):
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
        return os.path.join(base, "ProTrader")
    if sys.platform == "darwin":
        return os.path.expanduser("~/Library/Application Support/ProTrader")
    return os.path.expanduser("~/.local/share/protrader")


DATA_DIR = user_data_dir()
os.makedirs(DATA_DIR, exist_ok=True)

# first-run seed: copy bundled read-only data files into the writable dir
if FROZEN:
    seed = os.path.join(BUNDLE, "data")
    if os.path.isdir(seed):
        for name in os.listdir(seed):
            src = os.path.join(seed, name); dst = os.path.join(DATA_DIR, name)
            if os.path.exists(dst):
                continue
            try:
                (shutil.copytree if os.path.isdir(src) else shutil.copy2)(src, dst)
            except Exception:
                pass


def data(*parts):
    """writable data path, e.g. data('playbook.json')"""
    return os.path.join(DATA_DIR, *parts)


def bundled(*parts):
    """read-only path inside the source tree / bundle, e.g. bundled('assets', 'icon.png')"""
    return os.path.join(BUNDLE, *parts)
