"""
Persistence & Background Service — برنامه حتی اگه ران نشده بود بتونه خودش تحلیل کنه

Features:
- Auto-start on system boot (Windows Registry, Task Scheduler, Startup folder, Linux systemd, macOS LaunchAgent)
- Single-instance lock so only one background service runs
- Background daemon that continues analysis even when UI is closed (minimize to tray)
- Keeps running until explicitly stopped from Task Manager / system tray
- Self-healing: if crashed, auto-restarts
- Provides API for UI to check if background service is running

Design:
- On first run, install auto-start (user can disable in Settings)
- Background threads:
  * analysis loop (playbook, forward test, ML retrain)
  * live market ticker (optional)
  * iran gold updater
  * resilient network monitor
- When UI closes, it minimizes to tray and keeps daemon alive, unless user explicitly chooses Exit
- Task Manager: process named "ProTrader" stays alive; killing it stops everything

Usage:
    from core.persistence import ensure_autostart, is_background_running, setup_tray_persistence
"""

import os
import sys
import time
import json
import threading
import subprocess
import platform
from pathlib import Path

from core.paths import DATA_DIR, data as data_path, SRC_ROOT

LOCK_FILE = data_path("protrader.lock")
PID_FILE = data_path("protrader.pid")
AUTOSTART_FLAG = data_path("autostart.json")
SERVICE_LOG = data_path("service.log")

def log(msg: str):
    try:
        os.makedirs(os.path.dirname(SERVICE_LOG), exist_ok=True)
        with open(SERVICE_LOG, "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')}  {msg}\n")
    except Exception:
        pass
    print(f"[persistence] {msg}")

# ------------------------------------------------------------------ Single instance lock
_lock_handle = None

def acquire_lock() -> bool:
    """Try to acquire single-instance lock. Returns True if we are the main instance."""
    global _lock_handle
    try:
        # Write PID file
        pid = os.getpid()
        # Check if existing PID is alive
        if os.path.exists(PID_FILE):
            try:
                old_pid = int(open(PID_FILE).read().strip())
                # check if process alive
                if sys.platform.startswith("win"):
                    # Windows: tasklist
                    try:
                        out = subprocess.check_output(f'tasklist /FI "PID eq {old_pid}"', shell=True, text=True)
                        if str(old_pid) in out:
                            # already running, but we still allow UI to run alongside service?
                            # For background service, we want to know
                            pass
                    except Exception:
                        pass
                else:
                    try:
                        os.kill(old_pid, 0)
                        # process exists
                        # if it's same program, we are second instance
                        # we will not block UI, just note
                    except OSError:
                        pass
            except Exception:
                pass
        
        # Write our PID
        with open(PID_FILE, "w") as f:
            f.write(str(pid))
        
        # Lock file with exclusive open (Windows)
        try:
            if sys.platform.startswith("win"):
                import msvcrt
                _lock_handle = open(LOCK_FILE, "w")
                msvcrt.locking(_lock_handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                _lock_handle = open(LOCK_FILE, "w")
                fcntl.flock(_lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            _lock_handle.write(str(pid))
            _lock_handle.flush()
        except Exception as e:
            # second instance, but allow
            log(f"Lock already held: {e}")
            return False
        
        return True
    except Exception as e:
        log(f"acquire_lock error: {e}")
        return True  # assume we are main if lock fails

def release_lock():
    global _lock_handle
    try:
        if _lock_handle:
            if sys.platform.startswith("win"):
                try:
                    import msvcrt
                    msvcrt.locking(_lock_handle.fileno(), msvcrt.LK_UNLCK, 1)
                except Exception:
                    pass
            else:
                try:
                    import fcntl
                    fcntl.flock(_lock_handle.fileno(), fcntl.LOCK_UN)
                except Exception:
                    pass
            _lock_handle.close()
            _lock_handle = None
        if os.path.exists(LOCK_FILE):
            os.remove(LOCK_FILE)
        if os.path.exists(PID_FILE):
            os.remove(PID_FILE)
    except Exception:
        pass

def is_background_running() -> bool:
    """Check if background service PID is alive."""
    try:
        if not os.path.exists(PID_FILE):
            return False
        pid = int(open(PID_FILE).read().strip())
        if sys.platform.startswith("win"):
            out = subprocess.check_output(f'tasklist /FI "PID eq {pid}"', shell=True, text=True, stderr=subprocess.DEVNULL)
            return str(pid) in out
        else:
            os.kill(pid, 0)
            return True
    except Exception:
        return False

def get_background_pid() -> int:
    try:
        return int(open(PID_FILE).read().strip())
    except Exception:
        return 0

# ------------------------------------------------------------------ Auto-start installation
def _get_executable() -> str:
    """Get executable path for autostart (frozen exe or python main.py)."""
    if getattr(sys, 'frozen', False):
        return sys.executable
    # source checkout: use python + main.py
    python = sys.executable
    main_py = os.path.join(SRC_ROOT, "main.py")
    # Wrap in quotes
    if sys.platform.startswith("win"):
        return f'"{python}" "{main_py}" --background'
    else:
        return f'{python} {main_py} --background'

def _get_autostart_settings() -> dict:
    try:
        if os.path.exists(AUTOSTART_FLAG):
            return json.load(open(AUTOSTART_FLAG, encoding="utf-8"))
    except Exception:
        pass
    return {"enabled": False, "installed": False, "method": None}

def _save_autostart_settings(d: dict):
    try:
        os.makedirs(os.path.dirname(AUTOSTART_FLAG), exist_ok=True)
        json.dump(d, open(AUTOSTART_FLAG, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    except Exception:
        pass

def install_autostart_windows_registry() -> bool:
    """Install via Windows Registry Run key."""
    try:
        import winreg
        exe = _get_executable()
        # For frozen exe, exe is already quoted? Ensure
        if not exe.startswith('"') and " " in exe:
            exe = f'"{exe}"'
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, "ProTrader", 0, winreg.REG_SZ, exe)
        winreg.CloseKey(key)
        log(f"Autostart installed via Registry: {exe}")
        return True
    except Exception as e:
        log(f"Registry autostart failed: {e}")
        return False

def install_autostart_windows_task_scheduler() -> bool:
    """Install via Task Scheduler (more reliable, runs at logon)."""
    try:
        exe = _get_executable()
        # Create task XML or use schtasks
        # schtasks /create /tn ProTrader /tr "..." /sc onlogon /rl limited /f
        task_name = "ProTraderBackground"
        if getattr(sys, 'frozen', False):
            tr = exe
        else:
            # need to escape
            tr = exe
        
        cmd = f'schtasks /create /tn "{task_name}" /tr "{tr}" /sc onlogon /rl limited /f'
        # Try
        subprocess.check_call(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        log(f"Autostart installed via Task Scheduler: {task_name}")
        return True
    except Exception as e:
        log(f"Task Scheduler autostart failed: {e}")
        return False

def install_autostart_windows_startup_folder() -> bool:
    """Install via Startup folder .lnk shortcut."""
    try:
        import winshell
        from win32com.client import Dispatch
        startup = winshell.startup()
        exe = _get_executable()
        # parse exe
        if getattr(sys, 'frozen', False):
            target = exe
            args = "--background"
        else:
            # exe is '"python" "main.py" --background'
            # split
            parts = exe.split('"')
            # parts: ['', python, ' ', main.py, ' --background']
            python = parts[1] if len(parts) > 1 else sys.executable
            main_py = parts[3] if len(parts) > 3 else os.path.join(SRC_ROOT, "main.py")
            target = python
            args = f'"{main_py}" --background'
        
        shortcut_path = os.path.join(startup, "ProTrader.lnk")
        shell = Dispatch('WScript.Shell')
        shortcut = shell.CreateShortCut(shortcut_path)
        shortcut.Targetpath = target
        shortcut.Arguments = args
        shortcut.WorkingDirectory = SRC_ROOT
        shortcut.IconLocation = target
        shortcut.save()
        log(f"Autostart installed via Startup folder: {shortcut_path}")
        return True
    except Exception:
        # Fallback without winshell: create .bat in startup
        try:
            startup = os.path.join(os.environ.get("APPDATA", ""), r"Microsoft\Windows\Start Menu\Programs\Startup")
            if not os.path.isdir(startup):
                return False
            bat_path = os.path.join(startup, "ProTrader.bat")
            exe = _get_executable()
            with open(bat_path, "w", encoding="utf-8") as f:
                f.write(f"@echo off\nstart \"\" {exe}\n")
            log(f"Autostart installed via Startup .bat: {bat_path}")
            return True
        except Exception as e:
            log(f"Startup folder autostart failed: {e}")
            return False

def install_autostart_linux() -> bool:
    """Install via systemd user service + autostart desktop entry."""
    try:
        # 1) .desktop file
        autostart_dir = os.path.expanduser("~/.config/autostart")
        os.makedirs(autostart_dir, exist_ok=True)
        desktop_path = os.path.join(autostart_dir, "protrader.desktop")
        exe = _get_executable()
        with open(desktop_path, "w", encoding="utf-8") as f:
            f.write(f"""[Desktop Entry]
Type=Application
Name=ProTrader
Comment=ProTrader background analysis service
Exec={exe}
Icon=applications-finance
Terminal=false
X-GNOME-Autostart-enabled=true
""")
        log(f"Autostart .desktop installed: {desktop_path}")
        
        # 2) systemd user service
        systemd_dir = os.path.expanduser("~/.config/systemd/user")
        os.makedirs(systemd_dir, exist_ok=True)
        service_path = os.path.join(systemd_dir, "protrader.service")
        with open(service_path, "w", encoding="utf-8") as f:
            f.write(f"""[Unit]
Description=ProTrader background analysis
After=network-online.target

[Service]
Type=simple
ExecStart={exe}
Restart=on-failure
RestartSec=30
Environment=PROTRADER_BACKGROUND=1

[Install]
WantedBy=default.target
""")
        try:
            subprocess.call(["systemctl", "--user", "daemon-reload"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.call(["systemctl", "--user", "enable", "protrader.service"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass
        
        return True
    except Exception as e:
        log(f"Linux autostart failed: {e}")
        return False

def install_autostart_macos() -> bool:
    try:
        launch_dir = os.path.expanduser("~/Library/LaunchAgents")
        os.makedirs(launch_dir, exist_ok=True)
        plist_path = os.path.join(launch_dir, "com.protrader.background.plist")
        exe = _get_executable()
        # exe may contain spaces, need to split for plist
        # For simplicity, use python + main.py
        python = sys.executable
        main_py = os.path.join(SRC_ROOT, "main.py")
        with open(plist_path, "w", encoding="utf-8") as f:
            f.write(f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>com.protrader.background</string>
    <key>ProgramArguments</key>
    <array>
        <string>{python}</string>
        <string>{main_py}</string>
        <string>--background</string>
    </array>
    <key>RunAtLoad</key><true/>
    <key>KeepAlive</key><true/>
    <key>StandardOutPath</key><string>{data_path("service.out.log")}</string>
    <key>StandardErrorPath</key><string>{data_path("service.err.log")}</string>
</dict>
</plist>
""")
        try:
            subprocess.call(["launchctl", "load", plist_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass
        log(f"Autostart LaunchAgent installed: {plist_path}")
        return True
    except Exception as e:
        log(f"macOS autostart failed: {e}")
        return False

def ensure_autostart(enable: bool = True) -> bool:
    """
    Ensure autostart is installed/uninstalled.
    Returns True if successful.
    """
    settings = _get_autostart_settings()
    
    if not enable:
        # Uninstall
        success = uninstall_autostart()
        settings.update(enabled=False, installed=False)
        _save_autostart_settings(settings)
        return success
    
    # Install
    success = False
    method = None
    
    if sys.platform.startswith("win"):
        # Try registry first, then task scheduler, then startup folder
        if install_autostart_windows_registry():
            success = True
            method = "registry"
        if install_autostart_windows_task_scheduler():
            success = True
            method = (method + "+taskscheduler") if method else "taskscheduler"
        if not success and install_autostart_windows_startup_folder():
            success = True
            method = "startup_folder"
    elif sys.platform.startswith("linux"):
        if install_autostart_linux():
            success = True
            method = "systemd+autostart"
    elif sys.platform == "darwin":
        if install_autostart_macos():
            success = True
            method = "launchagent"
    
    settings.update(enabled=success, installed=success, method=method, ts=time.time())
    _save_autostart_settings(settings)
    
    if success:
        log(f"Autostart enabled via {method}")
    else:
        log("Autostart installation failed")
    
    return success

def uninstall_autostart() -> bool:
    try:
        if sys.platform.startswith("win"):
            try:
                import winreg
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE)
                try:
                    winreg.DeleteValue(key, "ProTrader")
                except FileNotFoundError:
                    pass
                winreg.CloseKey(key)
            except Exception:
                pass
            try:
                subprocess.call('schtasks /delete /tn "ProTraderBackground" /f', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                pass
            try:
                startup = os.path.join(os.environ.get("APPDATA", ""), r"Microsoft\Windows\Start Menu\Programs\Startup")
                for name in ("ProTrader.lnk", "ProTrader.bat"):
                    p = os.path.join(startup, name)
                    if os.path.exists(p):
                        os.remove(p)
            except Exception:
                pass
        elif sys.platform.startswith("linux"):
            try:
                os.remove(os.path.expanduser("~/.config/autostart/protrader.desktop"))
            except Exception:
                pass
            try:
                subprocess.call(["systemctl", "--user", "disable", "protrader.service"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                os.remove(os.path.expanduser("~/.config/systemd/user/protrader.service"))
                subprocess.call(["systemctl", "--user", "daemon-reload"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                pass
        elif sys.platform == "darwin":
            try:
                plist = os.path.expanduser("~/Library/LaunchAgents/com.protrader.background.plist")
                subprocess.call(["launchctl", "unload", plist], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                os.remove(plist)
            except Exception:
                pass
        log("Autostart uninstalled")
        return True
    except Exception as e:
        log(f"Uninstall autostart failed: {e}")
        return False

def is_autostart_enabled() -> bool:
    s = _get_autostart_settings()
    return s.get("enabled", False)

# ------------------------------------------------------------------ Background service main loop
_background_threads = []
_background_stop = threading.Event()

def _background_analysis_loop():
    """Continuous analysis loop that runs even when UI closed."""
    log("Background analysis loop started")
    # Lower priority
    try:
        if sys.platform.startswith("win"):
            import ctypes
            ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x00004000)
        else:
            os.nice(10)
    except Exception:
        pass
    
    # Import here to avoid circular
    try:
        from core import maintenance, auto_evolution
        # Start maintenance
        maintenance.start()
        # Start auto-evolution
        auto_evolution.start()
        log("Maintenance + AutoEvolution started in background")
    except Exception as e:
        log(f"Failed to start maintenance/evolution: {e}")
    
    # Iran gold updater already auto-starts via its module
    try:
        from core import iran_gold
        iran_gold.start_background_updater()
    except Exception as e:
        log(f"Iran gold updater failed: {e}")
    
    # Resilient network monitor
    try:
        from core import resilient
        # Periodic health check
        while not _background_stop.is_set():
            try:
                health = resilient.health_check()
                # log if issues
                failed = [k for k, v in health.items() if not v]
                if failed:
                    log(f"Network health issues: {failed}")
            except Exception:
                pass
            _background_stop.wait(300)  # every 5 min
    except Exception as e:
        log(f"Network monitor loop error: {e}")

def start_background_service():
    """Start background service threads (call once at app start)."""
    global _background_threads
    if _background_threads:
        return  # already started
    
    _background_stop.clear()
    acquire_lock()
    
    th = threading.Thread(target=_background_analysis_loop, name="persistence-bg", daemon=True)
    th.start()
    _background_threads.append(th)
    log(f"Background service started, PID {os.getpid()}")

def stop_background_service():
    _background_stop.set()
    try:
        from core import maintenance, iran_gold, auto_evolution
        maintenance.stop()
        iran_gold.stop_background_updater()
        auto_evolution.stop()
    except Exception:
        pass
    release_lock()
    log("Background service stopped")

# ------------------------------------------------------------------ Tray persistence helper
def setup_tray_persistence(main_window):
    """
    Setup main window to minimize to tray instead of exit.
    Call from MainWindow.__init__ after tray init.
    """
    # This is handled in main_window.py closeEvent override
    # Here we just ensure flag
    try:
        settings_path = data_path("settings.json")
        s = {}
        if os.path.exists(settings_path):
            s = json.load(open(settings_path, encoding="utf-8"))
        # Default: minimize to tray enabled
        if "minimize_to_tray" not in s:
            s["minimize_to_tray"] = True
            s["background_analysis"] = True
            json.dump(s, open(settings_path, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    except Exception:
        pass

# ------------------------------------------------------------------ CLI for --background mode
def run_background_mode():
    """Entry point when launched with --background (no UI, just service)."""
    log("Running in --background mode (headless service)")
    start_background_service()
    try:
        # Keep alive until killed
        while True:
            time.sleep(60)
            # Self-healing: check maintenance thread alive?
            # If pid file removed, exit
            if not os.path.exists(PID_FILE):
                log("PID file removed, exiting background mode")
                break
    except KeyboardInterrupt:
        log("Background mode interrupted")
    finally:
        stop_background_service()

if __name__ == "__main__":
    if "--background" in sys.argv:
        run_background_mode()
    else:
        print(f"Autostart enabled: {is_autostart_enabled()}")
        print(f"Background running: {is_background_running()}")
