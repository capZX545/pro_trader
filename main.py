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
    # self-maintenance: forward-test outcomes, safe auto-fixes, playbook refresh when stale (daemon thread)
    if os.environ.get("PROTRADER_NO_MAINT") != "1":
        try:
            from core import maintenance
            maintenance.start()
        except Exception:
            pass
    rc = app.exec()
    try:
        from core import maintenance
        maintenance.stop()
    except Exception:
        pass
    sys.exit(rc)


if __name__ == "__main__":
    main()
