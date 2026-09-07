#!/usr/bin/env python3
"""
ProTrader Academy — professional strategy library, scanner, backtester & trading academy.
Run:  python main.py
"""
import os
import sys
import json
import warnings

warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6 import QtWidgets, QtGui, QtCore  # noqa: E402
from ui.theme import QSS, I18N  # noqa: E402


def main():
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
