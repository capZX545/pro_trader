"""Trading Desk page — Phase 25 daily briefing (core.desk)."""
import re, html
from PyQt6 import QtCore, QtWidgets, QtGui
from .theme import C, t, I18N
from .widgets import Worker


class DeskPage(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        v = QtWidgets.QVBoxLayout(self); v.setContentsMargins(16, 12, 16, 12); v.setSpacing(10)
        title = QtWidgets.QLabel("🗞 " + t("nav_desk")); title.setObjectName("h1"); v.addWidget(title)
        sub = QtWidgets.QLabel(t("desk_sub")); sub.setObjectName("subtitle"); sub.setWordWrap(True); v.addWidget(sub)
        bar = QtWidgets.QHBoxLayout()
        bar.addWidget(QtWidgets.QLabel(t("desk_mode")))
        self.mode = QtWidgets.QComboBox(); self.mode.addItem(t("q_proven_only"), "proven"); self.mode.addItem(t("q_candidate"), "candidate")
        bar.addWidget(self.mode)
        bar.addWidget(QtWidgets.QLabel(t("desk_equity")))
        self.eq = QtWidgets.QDoubleSpinBox(); self.eq.setRange(100, 1e9); self.eq.setValue(10000); self.eq.setDecimals(0); bar.addWidget(self.eq)
        self.btn = QtWidgets.QPushButton("🗞 " + t("desk_run")); self.btn.setObjectName("primary"); self.btn.clicked.connect(self.run); bar.addWidget(self.btn)
        self.copy = QtWidgets.QPushButton("📋 " + t("desk_copy")); self.copy.clicked.connect(self._copy); bar.addWidget(self.copy)
        bar.addStretch()
        self.status = QtWidgets.QLabel(""); self.status.setObjectName("subtitle"); bar.addWidget(self.status)
        v.addLayout(bar)
        self.prog = QtWidgets.QProgressBar(); self.prog.setRange(0, 100); self.prog.setVisible(False); v.addWidget(self.prog)
        self.out = QtWidgets.QTextBrowser(); self.out.setOpenExternalLinks(False)
        self.out.setStyleSheet(f"font-size:13px; line-height:1.6; color:{C['text']}")
        v.addWidget(self.out, 1)
        self._text = ""

    def run(self):
        self.btn.setEnabled(False); self.prog.setVisible(True); self.prog.setValue(0); self.status.setText(t("scanning"))
        mode, eq = self.mode.currentData(), float(self.eq.value())

        def job(progress=None):
            from core import desk as D
            return D.briefing(equity=eq, mode=mode, max_age=0, progress=progress)
        self.w = Worker(job)
        try:
            self.w.kw["progress"] = lambda p, s: self.w.progress.emit(p, s)
            self.w.progress.connect(lambda p, s: (self.prog.setValue(p), self.status.setText(s)))
        except Exception:
            pass
        self.w.done.connect(self._show)
        self.w.error.connect(lambda e: (self.out.setPlainText("⚠ " + str(e)), self._done()))
        self.w.start()

    def _done(self):
        self.btn.setEnabled(True); self.prog.setVisible(False)

    def _show(self, b):
        self._done()
        self._text = b["text_fa"] if I18N.lang == "fa" else b["text_en"]
        h = html.escape(self._text)
        h = re.sub(r"^# (.*)$", r"<h2>\1</h2>", h, flags=re.M)
        h = re.sub(r"^## (.*)$", rf"<h3 style='color:{C['accent2']}'>\1</h3>", h, flags=re.M)
        h = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", h)
        h = h.replace("⛔", f"<span style='color:{C['red']}'>⛔</span>").replace("⚠", f"<span style='color:{C['yellow']}'>⚠</span>").replace("✓", f"<span style='color:{C['green']}'>✓</span>")
        h = re.sub(r"^_(.*)_(.*)$", rf"<span style='color:{C['muted']}'>\1\2</span>", h, flags=re.M)
        self.out.setHtml(("<div dir='rtl'>" if I18N.lang == "fa" else "<div>") + h.replace("\n", "<br>") + "</div>")
        ok = b["gate"]["ok"] and not b["news"]
        self.status.setText(("✓ " if ok else "⛔ ") + f"{len(b['plans'])} · {b['total_alloc_pct']}% · {b['took']}s")

    def _copy(self):
        if self._text:
            QtWidgets.QApplication.clipboard().setText(self._text)

