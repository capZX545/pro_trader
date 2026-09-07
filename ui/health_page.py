"""Health page — the bot diagnoses itself (data, playbook, validation, forward-test, strategies) and offers one-click fixes."""
import time
from PyQt6 import QtCore, QtWidgets

from core import health as H
from .theme import C, t, I18N
from .widgets import Card, StatTile, Worker

SEV = {"error": ("⛔", C["red"]), "warn": ("⚠", C["yellow"]), "info": ("ℹ", C["accent2"])}


class HealthPage(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(16, 12, 16, 12)
        v.setSpacing(10)
        title = QtWidgets.QLabel(t("hl_title")); title.setObjectName("h1"); v.addWidget(title)
        sub = QtWidgets.QLabel(t("hl_sub")); sub.setObjectName("subtitle"); sub.setWordWrap(True); v.addWidget(sub)
        top = QtWidgets.QHBoxLayout()
        self.quick = QtWidgets.QPushButton("⚡ " + t("hl_quick")); self.quick.clicked.connect(lambda: self.run(True))
        self.full = QtWidgets.QPushButton("🩺 " + t("hl_full")); self.full.setObjectName("primary"); self.full.clicked.connect(lambda: self.run(False))
        self.fixall = QtWidgets.QPushButton("🛠 " + t("hl_fix_all")); self.fixall.clicked.connect(self.fix_all); self.fixall.setEnabled(False)
        top.addWidget(self.quick); top.addWidget(self.full); top.addWidget(self.fixall); top.addStretch()
        self.status = QtWidgets.QLabel(""); self.status.setObjectName("subtitle"); top.addWidget(self.status)
        v.addLayout(top)
        self.prog = QtWidgets.QProgressBar(); self.prog.setRange(0, 100); self.prog.setVisible(False); v.addWidget(self.prog)
        tiles = QtWidgets.QHBoxLayout()
        self.t_state = StatTile(t("hl_state")); self.t_err = StatTile(t("hl_errors")); self.t_warn = StatTile(t("hl_warns")); self.t_info = StatTile(t("hl_infos"))
        self.t_last = StatTile(t("hl_last"))
        for x in (self.t_state, self.t_err, self.t_warn, self.t_info, self.t_last):
            tiles.addWidget(x)
        v.addLayout(tiles)
        self.scroll = QtWidgets.QScrollArea(); self.scroll.setWidgetResizable(True); self.scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self.list_w = QtWidgets.QWidget(); self.lv = QtWidgets.QVBoxLayout(self.list_w); self.lv.setSpacing(8); self.lv.addStretch()
        self.scroll.setWidget(self.list_w)
        v.addWidget(self.scroll, 1)
        mc = Card(t("hl_maint"))
        self.maint = QtWidgets.QPlainTextEdit(); self.maint.setReadOnly(True); self.maint.setMaximumHeight(140)
        self.maint.setStyleSheet(f"font-family: Consolas, monospace; font-size: 11px; color:{C['muted']}")
        mc.add(self.maint)
        v.addWidget(mc)
        self.findings = []
        QtCore.QTimer.singleShot(1500, lambda: self.run(True))

    def run(self, quick):
        self.quick.setEnabled(False); self.full.setEnabled(False); self.prog.setVisible(True)
        self.status.setText(t("hl_running"))

        def work(progress=None):
            return H.run_checks(quick=quick, progress=progress)
        self.w = Worker(work)
        self.w.progress.connect(lambda p, s: (self.prog.setValue(p), self.status.setText(s)))
        self.w.done.connect(self._show)
        self.w.error.connect(lambda e: (self._reset(), QtWidgets.QMessageBox.warning(self, "Error", e)))
        self.w.start()

    def _reset(self):
        self.quick.setEnabled(True); self.full.setEnabled(True); self.prog.setVisible(False)

    def _show(self, findings):
        self._reset()
        self.findings = findings
        s = H.summary(findings)
        self.t_err.set(str(s["errors"]), C["red"] if s["errors"] else C["green"])
        self.t_warn.set(str(s["warns"]), C["yellow"] if s["warns"] else C["green"])
        self.t_info.set(str(s["infos"]), C["accent2"])
        self.t_last.set(time.strftime("%H:%M:%S"))
        if s["errors"]:
            self.t_state.set("⛔ " + t("hl_bad"), C["red"])
        elif s["warns"]:
            self.t_state.set("⚠ " + t("hl_ok_warn"), C["yellow"])
        else:
            self.t_state.set("✅ " + t("hl_good"), C["green"])
        self.fixall.setEnabled(any(f.fix for f in findings))
        self.status.setText(t("hl_done"))
        try:
            from core import maintenance as M
            self.maint.setPlainText("".join(M.tail(30)) or t("hl_maint_none"))
        except Exception:
            pass
        while self.lv.count() > 1:
            it = self.lv.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        fa = I18N.lang == "fa"
        if not findings:
            lbl = QtWidgets.QLabel("✅ " + t("hl_none")); lbl.setStyleSheet(f"color:{C['green']}; font-size:15px; padding:20px")
            self.lv.insertWidget(0, lbl)
        for f in findings:
            card = Card(obj="card2")
            h = QtWidgets.QHBoxLayout()
            icon, col = SEV.get(f.severity, ("•", C["muted"]))
            l1 = QtWidgets.QLabel(f"<span style='color:{col};font-size:16px'>{icon}</span> <b style='color:{col}'>{f.area}</b>  ·  {f.fa if fa else f.en}")
            l1.setWordWrap(True); l1.setTextFormat(QtCore.Qt.TextFormat.RichText)
            h.addWidget(l1, 1)
            if f.fix:
                b = QtWidgets.QPushButton("🛠 " + (f.fix_label[1] if fa else f.fix_label[0]))
                b.clicked.connect(lambda _, ff=f, bb=b: self._fix(ff, bb))
                h.addWidget(b)
            card.v.addLayout(h)
            self.lv.insertWidget(self.lv.count() - 1, card)

    def _fix(self, f, btn=None):
        if btn:
            btn.setEnabled(False); btn.setText("⏳")
        self.prog.setVisible(True); self.prog.setRange(0, 0)
        self.status.setText(t("hl_fixing") + f" {f.area}")
        self.wf = Worker(lambda: f.fix())
        self.wf.done.connect(lambda _: (self.prog.setRange(0, 100), self.run(True)))
        self.wf.error.connect(lambda e: (self.prog.setRange(0, 100), self._reset(), QtWidgets.QMessageBox.warning(self, "Error", e)))
        self.wf.start()

    def fix_all(self):
        fixes = [f for f in self.findings if f.fix]
        if not fixes:
            return
        self.fixall.setEnabled(False)
        self.prog.setVisible(True); self.prog.setRange(0, 0)

        def work():
            for f in fixes:
                try:
                    f.fix()
                except Exception:
                    pass
            return True
        self.wf = Worker(work)
        self.wf.done.connect(lambda _: (self.prog.setRange(0, 100), self.run(True)))
        self.wf.error.connect(lambda e: (self.prog.setRange(0, 100), self._reset()))
        self.wf.start()
