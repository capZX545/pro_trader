#!/usr/bin/env python3
"""
ProTrader Academy — professional strategy library, scanner, backtester & trading academy.
Run:  python main.py
"""
import os
import sys
import json
import warnings

# Keep numeric libraries from spawning one busy thread per core for every tiny pandas/numpy op.
# With 20+ background jobs (strategies, playbook, scanner) that oversubscription is what makes the UI stutter.
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ.setdefault(_v, "1")
os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")

warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# --web : headless web/mobile server (same engine, no Qt needed — runs on a VPS too).  ProTrader --web [--port 8765]
if "--web" in sys.argv:
    from core import webapp  # noqa: E402
    webapp.main([a for a in sys.argv[1:] if a != "--web"]); sys.exit(0)

# --background : headless background service mode (analysis continues even when UI closed)
# این حالت باعث میشه برنامه حتی وقتی ران نیست تحلیل کنه و خودشو پیشرفت بده
# فقط کافیه یه بار ران بشه و تا وقتی از تسک منیجر متوقف نشده ادامه بده
if "--background" in sys.argv or os.environ.get("PROTRADER_BACKGROUND") == "1":
    # Background service mode - no UI, just continuous analysis
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from core.persistence import run_background_mode
    run_background_mode()
    sys.exit(0)

from PyQt6 import QtWidgets, QtGui, QtCore  # noqa: E402
from ui.theme import QSS, I18N  # noqa: E402


def _install_crash_handlers():
    """Crash forensics: native faults → data/crash.log (faulthandler); Python exceptions in slots → same log + no abort.
    Without this, any uncaught exception inside a Qt slot terminates the whole process on PyQt6."""
    import faulthandler, traceback, datetime
    from core.paths import data as _d
    path = _d("crash.log")
    try:
        f = open(path, "a", buffering=1)
        faulthandler.enable(file=f, all_threads=True)
    except Exception:
        f = None

    def hook(exc_type, exc, tb):
        try:
            msg = "".join(traceback.format_exception(exc_type, exc, tb))
            if f:
                f.write(f"\n[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}] uncaught exception\n{msg}")
            sys.__stderr__.write(msg)
        except Exception:
            pass
        # do NOT re-raise / abort: a failed slot should not kill the app
    sys.excepthook = hook
    try:
        import threading
        threading.excepthook = lambda a: hook(a.exc_type, a.exc_value, a.exc_traceback)
    except Exception:
        pass


def main():
    _install_crash_handlers()
    # Background threads (self-training, live analysis) hold the GIL in long numpy/pandas stretches; a shorter
    # switch interval (default 5 ms) lets the GUI thread get the interpreter back quickly → smoother UI.
    sys.setswitchinterval(0.001)
    # language
    from core.paths import data as _data
    settings = _data("settings.json")
    lang = "en"
    if os.path.exists(settings):
        try:
            lang = json.load(open(settings)).get("lang", "en")
        except Exception:
            pass
    if len(sys.argv) > 1 and sys.argv[1] in ("fa", "en"):
        lang = sys.argv[1]
    I18N.lang = lang

    QtCore.QCoreApplication.setAttribute(QtCore.Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName("ProTrader Academy")
    app.setStyle("Fusion")
    app.setStyleSheet(QSS)
    try:
        from core.paths import bundled
        app.setWindowIcon(QtGui.QIcon(bundled("assets", "icon.png")))
    except Exception:
        pass
    font = QtGui.QFont("Segoe UI" if sys.platform.startswith("win") else "Helvetica", 10)
    app.setFont(font)

    from ui.main_window import MainWindow
    w = MainWindow()
    w.show()
    # --diag: open Chart page, load default symbol, wait 20 s, save a screenshot + environment report into the data dir,
    # then exit. Lets a user with a blank chart send exactly what their machine renders:  ProTrader.exe --diag
    if "--diag" in sys.argv:
        from core.paths import data as _d

        def _diag():
            try:
                w.goto(1); page = w.pages[1][2]; page.run()
            except Exception as e:
                print("diag run error", e)

            def _snap():
                try:
                    out = _d("diag_chart.png"); w.grab().save(out)
                    import platform
                    rep = {"platform": platform.platform(), "python": sys.version, "qt": QtCore.qVersion(),
                           "renderer": getattr(getattr(page, "chart", None), "mode", None),
                           "df_rows": None if getattr(page, "df", None) is None else int(len(page.df)),
                           "live": page.live_lbl.text() if hasattr(page, "live_lbl") else None,
                           "qt_opengl": os.environ.get("QT_OPENGL"), "qpa": os.environ.get("QT_QPA_PLATFORM")}
                    json.dump(rep, open(_d("diag_report.json"), "w"), indent=1, ensure_ascii=False)
                    print("diag saved:", out)
                except Exception as e:
                    print("diag error", e)
                app.quit()
            QtCore.QTimer.singleShot(20000, _snap)
        QtCore.QTimer.singleShot(1500, _diag)
    # === ADVANCED PERSISTENCE & AUTO-EVOLUTION LAYER ===
    # حتی اگه فیلتر وصل نبود بتونه وصل بشه به چارتا + تحلیل پس‌زمینه + طلای ایران
    try:
        # 1) Resilient network layer (anti-filter)
        from core import resilient
        proxy = resilient.detect_system_proxy()
        if proxy:
            print(f"[ProTrader] Resilient proxy detected: {proxy}")
        # Quick health check in background
        import threading
        def _bg_health():
            try:
                h = resilient.health_check()
                print(f"[ProTrader] Network health: {h}")
            except Exception:
                pass
        threading.Thread(target=_bg_health, daemon=True).start()
    except Exception as e:
        print(f"[ProTrader] Resilient init failed: {e}")

    try:
        # 2) Iran Gold background updater + related services
        from core import iran_gold, bubble, jalali, correlation
        iran_gold.start_background_updater()
        print("[ProTrader] Iran Gold (طلای ایران) live updater started")
        
        # 2b) Gold alerts checker
        try:
            from core import gold_alerts
            gold_alerts.start_checker()
            print("[ProTrader] Gold alerts checker started")
        except Exception as e:
            print(f"[ProTrader] Gold alerts failed: {e}")
        
        # 2c) Jalali calendar - log seasonal pattern
        try:
            pattern = jalali.get_seasonal_pattern()
            print(f"[ProTrader] Jalali: {pattern['jalali_date']} - {pattern['season']} - Demand: {pattern['gold_demand']}")
        except Exception as e:
            print(f"[ProTrader] Jalali failed: {e}")
        
        # 2d) Monitoring
        try:
            from core import monitoring
            monitoring.start_monitoring()
            print("[ProTrader] Monitoring started")
        except Exception as e:
            print(f"[ProTrader] Monitoring failed: {e}")
            
    except Exception as e:
        print(f"[ProTrader] Iran Gold init failed: {e}")

    try:
        # 3) Persistence layer - auto-start + background service
        from core import persistence
        persistence.start_background_service()
        # Auto-start on boot (one-time setup, user can disable in settings)
        from core.paths import data as _pdata
        import json as _json
        settings_path = _pdata("settings.json")
        _settings = {}
        if os.path.exists(settings_path):
            try:
                _settings = _json.load(open(settings_path, encoding="utf-8"))
            except Exception:
                pass
        # If user hasn't explicitly disabled autostart, enable it on first run
        if _settings.get("autostart_enabled", None) is None:
            # First run - enable autostart
            try:
                persistence.ensure_autostart(True)
                _settings["autostart_enabled"] = True
                _settings["background_analysis"] = True
                _settings["minimize_to_tray"] = True
                _json.dump(_settings, open(settings_path, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
                print("[ProTrader] Auto-start enabled for background analysis")
            except Exception as e:
                print(f"[ProTrader] Auto-start setup failed: {e}")
        elif _settings.get("autostart_enabled"):
            # Ensure it's still installed (in case user moved exe)
            try:
                persistence.ensure_autostart(True)
            except Exception:
                pass
    except Exception as e:
        print(f"[ProTrader] Persistence init failed: {e}")

    # self-maintenance: forward-test outcomes, safe auto-fixes, playbook refresh when stale (daemon thread)
    if os.environ.get("PROTRADER_NO_MAINT") != "1":
        try:
            from core import maintenance
            maintenance.start()
        except Exception:
            pass
        # 4) Auto-evolution engine (self-improvement)
        try:
            from core import auto_evolution
            auto_evolution.start()
            print("[ProTrader] Auto-evolution engine started - خودشو پیشرفت میده")
        except Exception as e:
            print(f"[ProTrader] Auto-evolution failed: {e}")

    def _freeze():   # move ~200k start-up objects out of the cyclic GC → no more ~100 ms gen-2 pauses in the UI
        import gc
        gc.collect(); gc.freeze()
    QtCore.QTimer.singleShot(4000, _freeze)
    rc = app.exec()
    try:
        from core import maintenance, auto_evolution, iran_gold, persistence
        maintenance.stop()
        auto_evolution.stop()
        iran_gold.stop_background_updater()
        persistence.stop_background_service()
    except Exception:
        pass
    try:
        for fh in (sys.stdout, sys.stderr):
            if fh:
                fh.flush()
    except Exception:
        pass
    os._exit(rc)   # daemon threads still winding down during interpreter teardown = crash-on-exit on Windows


if __name__ == "__main__":
    main()
