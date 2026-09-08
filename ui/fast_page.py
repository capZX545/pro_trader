"""⚡ Fast Signals — low-timeframe confluence radar (Phase 16)."""
import time
from PyQt6 import QtCore, QtWidgets

from .theme import C, t, I18N
from .widgets import Card, StatTile, make_table, cell, ncell, color_for, Worker


class FastSignalsPage(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.w = None
        self.results = []
        v = QtWidgets.QVBoxLayout(self); v.setContentsMargins(16, 12, 16, 12); v.setSpacing(10)
        title = QtWidgets.QLabel(t("fs_title")); title.setObjectName("h1"); v.addWidget(title)
        sub = QtWidgets.QLabel(t("fs_sub")); sub.setObjectName("subtitle"); sub.setWordWrap(True); v.addWidget(sub)

        bar = QtWidgets.QHBoxLayout()
        self.tf = QtWidgets.QComboBox(); self.tf.addItems(["1m", "3m", "5m", "15m"]); self.tf.setCurrentText("5m")
        self.topn = QtWidgets.QSpinBox(); self.topn.setRange(3, 200); self.topn.setValue(30)
        self.votes = QtWidgets.QSpinBox(); self.votes.setRange(1, 8); self.votes.setValue(3)
        self.fee = QtWidgets.QComboBox(); self.fee.addItems(["fut_maker", "fut_taker", "spot_taker"]); self.fee.setCurrentText("fut_taker")
        self.auto = QtWidgets.QCheckBox(t("fs_auto")); self.auto.setChecked(False)
        for w_, lbl in ((self.tf, t("timeframe")), (self.topn, t("live_topn")), (self.votes, t("fs_min_votes")), (self.fee, t("fs_fee_tier"))):
            bar.addWidget(QtWidgets.QLabel(lbl)); bar.addWidget(w_)
        self.btn = QtWidgets.QPushButton("⚡ " + t("fs_scan")); self.btn.setObjectName("primary"); self.btn.clicked.connect(self.run)
        bar.addWidget(self.btn); bar.addWidget(self.auto); bar.addStretch()
        self.status = QtWidgets.QLabel(""); self.status.setObjectName("subtitle"); bar.addWidget(self.status)
        v.addLayout(bar)
        self.prog = QtWidgets.QProgressBar(); self.prog.setRange(0, 100); self.prog.setVisible(False); v.addWidget(self.prog)

        tiles = QtWidgets.QHBoxLayout()
        self.t_scanned = StatTile(t("fs_scanned")); self.t_setups = StatTile(t("fs_setups")); self.t_best = StatTile(t("fs_best"))
        self.t_costok = StatTile(t("fs_cost_ok")); self.t_sess = StatTile(t("fs_session"))
        for x in (self.t_scanned, self.t_setups, self.t_best, self.t_costok, self.t_sess):
            tiles.addWidget(x)
        v.addLayout(tiles)

        split = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
        card = Card(t("fs_table"))
        self.tbl = make_table([t("symbol"), t("timeframe"), t("side"), t("fs_score"), t("fs_votes"), t("price"), t("stop"), t("target"),
                               t("fs_move"), t("fs_cost"), t("fs_session"), t("winrate"), t("pf"), "n", t("fs_agree")])
        self.tbl.itemSelectionChanged.connect(self._explain)
        self.tbl.itemDoubleClicked.connect(self._open)
        card.add(self.tbl)
        split.addWidget(card)
        exp = Card(t("fs_explain"))
        self.txt = QtWidgets.QTextEdit(); self.txt.setReadOnly(True); self.txt.setMinimumHeight(90)
        exp.add(self.txt)
        split.addWidget(exp); split.setSizes([600, 160])
        v.addWidget(split, 1)
        note = QtWidgets.QLabel(t("fs_note")); note.setObjectName("subtitle"); note.setWordWrap(True); v.addWidget(note)

        self.timer = QtCore.QTimer(self); self.timer.setInterval(5 * 60 * 1000)
        self.timer.timeout.connect(lambda: self.auto.isChecked() and self.isVisible() and self.run())
        self.timer.start()

    # ------------------------------------------------------------------ run
    def run(self):
        if self.w is not None and self.w.isRunning():
            return
        from core import fastsignals as F
        try:
            from core import maintenance; maintenance.ui_busy(120)
        except Exception:
            pass
        tf, n, mv, fee = self.tf.currentText(), self.topn.value(), self.votes.value(), self.fee.currentText()
        self.btn.setEnabled(False); self.prog.setVisible(True); self.prog.setValue(0)
        cancelled = {"v": False}

        def work(progress=None):
            return F.scan(tf, top_n=n, min_votes=mv, fee_tier=fee, progress=progress, stop=lambda: cancelled["v"])
        self.w = Worker(work)
        self.w.progress.connect(lambda p, m: (self.prog.setValue(p), self.status.setText(m)))
        self.w.done.connect(self._show)
        self.w.error.connect(lambda e: (self.btn.setEnabled(True), self.prog.setVisible(False), self.status.setText(e.splitlines()[0][:120])))
        self.w.start()

    def _show(self, res):
        self.btn.setEnabled(True); self.prog.setVisible(False)
        self.results = res
        setups = [r for r in res if r.get("setup")]
        self.t_scanned.set(str(len(res)))
        self.t_setups.set(str(len(setups)), C["green"] if setups else C["muted"])
        if setups:
            b = setups[0]; s = b["setup"]
            self.t_best.set(f"{b['sym']} {'▲' if s['side'] == 1 else '▼'} {s['score']}", C["green"] if s["side"] == 1 else C["red"])
            self.t_costok.set(f"{sum(1 for r in setups if r['setup']['cost_ok'])} / {len(setups)}")
        else:
            self.t_best.set("—"); self.t_costok.set("—")
        from core.fastsignals import session_factor
        _, sess = session_factor(time.time() * 1e9)
        self.t_sess.set(sess)
        self.tbl.setSortingEnabled(False); self.tbl.setRowCount(0)
        for r in res:
            s = r.get("setup"); st = r.get("stats") or {}
            row = self.tbl.rowCount(); self.tbl.insertRow(row)
            it = cell(r["sym"]); it.setData(QtCore.Qt.ItemDataRole.UserRole, r); self.tbl.setItem(row, 0, it)
            self.tbl.setItem(row, 1, cell(r.get("tf", "")))
            if s:
                self.tbl.setItem(row, 2, cell(t("long") if s["side"] == 1 else t("short"), C["green"] if s["side"] == 1 else C["red"]))
                self.tbl.setItem(row, 3, ncell(s["score"], "{:.0f}", C["green"] if s["score"] >= 60 else (C["yellow"] if s["score"] >= 40 else C["muted"])))
                self.tbl.setItem(row, 4, ncell(s["votes"], "{:.0f}"))
                self.tbl.setItem(row, 5, ncell(s["px"], "{:,.6g}")); self.tbl.setItem(row, 6, ncell(s["sl"], "{:,.6g}", C["red"]))
                self.tbl.setItem(row, 7, ncell(s["tp"], "{:,.6g}", C["green"]))
                self.tbl.setItem(row, 8, ncell(s["move_bps"], "{:.0f} bps")); self.tbl.setItem(row, 9, ncell(s["cost_bps"], "{:.0f} bps", C["green"] if s["cost_ok"] else C["red"]))
                self.tbl.setItem(row, 10, cell(s["session"]))
                self.tbl.setItem(row, 14, cell(", ".join(s["agree"][:5])))
            else:
                self.tbl.setItem(row, 2, cell("—", C["muted"])); self.tbl.setItem(row, 3, ncell(0, "{:.0f}", C["muted"]))
                if r.get("error"):
                    self.tbl.setItem(row, 14, cell(r["error"], C["muted"]))
            if st.get("trades"):
                self.tbl.setItem(row, 11, ncell(st["win_rate"], "{:.0f}%")); self.tbl.setItem(row, 12, ncell(st["profit_factor"], "{:.2f}", color_for(st["profit_factor"] - 1)))
                self.tbl.setItem(row, 13, ncell(st["trades"], "{:.0f}"))
        self.tbl.setSortingEnabled(True); self.tbl.sortItems(3, QtCore.Qt.SortOrder.DescendingOrder)
        self.status.setText(t("fs_done").format(n=len(setups)))
        if setups:
            try:
                from core import alerts as AL
                for r in setups[:3]:
                    if r["setup"]["score"] >= 60 and r["setup"]["ago"] == 0:
                        AL.push("⚡ Fast signal", f"{r['sym']} {r['tf']} {'LONG' if r['setup']['side'] == 1 else 'SHORT'} · score {r['setup']['score']} · "
                                f"entry {r['setup']['px']:,.6g} sl {r['setup']['sl']:,.6g} tp {r['setup']['tp']:,.6g}", meta=dict(kind="fast", sym=r["sym"]))
            except Exception:
                pass

    def _explain(self):
        from core.fastsignals import explain
        rows = self.tbl.selectedItems()
        if not rows:
            return
        r = self.tbl.item(rows[0].row(), 0).data(QtCore.Qt.ItemDataRole.UserRole)
        if r:
            self.txt.setPlainText(explain(r, I18N.lang))

    def _open(self, item):
        r = self.tbl.item(item.row(), 0).data(QtCore.Qt.ItemDataRole.UserRole)
        if r:
            sid = (r.get("setup") or {}).get("agree") or ["vwap_pullback_scalp"]
            self.window().open_chart(r["sym"], r.get("tf", "5m"), sid[0])
