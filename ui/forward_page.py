"""Forward-Test page — every Advisor/Scanner signal is auto-recorded; here reality grades the backtests."""
import time
from PyQt6 import QtCore, QtGui, QtWidgets

from core import forward as FW
from .theme import C, t, I18N
from .widgets import Card, StatTile, make_table, cell, ncell, Worker, color_for

GRADE_COL = {"A": C["green"], "B": C["accent2"], "C": C["yellow"], "D": C["red"]}


def grade_cell(g):
    return cell(f"● {g}", GRADE_COL.get(g, C["muted"]))


class ForwardPage(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(16, 12, 16, 12)
        v.setSpacing(10)
        title = QtWidgets.QLabel(t("fw_title")); title.setObjectName("h1"); v.addWidget(title)
        sub = QtWidgets.QLabel(t("fw_sub")); sub.setObjectName("subtitle"); sub.setWordWrap(True); v.addWidget(sub)

        top = QtWidgets.QHBoxLayout()
        self.upd = QtWidgets.QPushButton("🔄 " + t("fw_update")); self.upd.setObjectName("primary"); self.upd.clicked.connect(self.update_now)
        self.clr = QtWidgets.QPushButton("🗑 " + t("fw_clear")); self.clr.clicked.connect(self.clear)
        self.exp = QtWidgets.QPushButton("📤 CSV"); self.exp.clicked.connect(self.export)
        self.auto = QtWidgets.QCheckBox(t("fw_auto")); self.auto.setChecked(True)
        top.addWidget(self.upd); top.addWidget(self.clr); top.addWidget(self.exp); top.addWidget(self.auto); top.addStretch()
        self.status = QtWidgets.QLabel(""); self.status.setObjectName("subtitle"); top.addWidget(self.status)
        v.addLayout(top)
        self.prog = QtWidgets.QProgressBar(); self.prog.setRange(0, 100); self.prog.setVisible(False); v.addWidget(self.prog)

        tiles = QtWidgets.QHBoxLayout()
        self.t_verdict = StatTile(t("fw_verdict"))
        self.t_n = StatTile(t("fw_closed_open"))
        self.t_wr = StatTile(t("winrate") + " (95% CI)")
        self.t_pf = StatTile(t("pf") + " (95% CI)")
        self.t_gap = StatTile(t("fw_gap"))
        self.t_r = StatTile(t("avg_r"))
        for x in (self.t_verdict, self.t_n, self.t_wr, self.t_pf, self.t_gap, self.t_r):
            tiles.addWidget(x)
        v.addLayout(tiles)

        split = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        left = Card(t("fw_by_strategy"))
        self.tbl_sid = make_table([t("strategy"), "n", t("winrate"), "CI", t("pf"), "CI", t("avg_r"), t("fw_expected"), t("fw_grade")])
        left.add(self.tbl_sid)
        right = Card(t("fw_by_tf"))
        self.tbl_tf = make_table([t("timeframe"), "n", t("winrate"), t("pf"), t("avg_r"), t("fw_grade")])
        right.add(self.tbl_tf)
        split.addWidget(left); split.addWidget(right); split.setSizes([700, 400])
        v.addWidget(split, 1)

        rec = Card(t("fw_records"))
        self.tbl = make_table([t("fw_status"), t("symbol"), t("timeframe"), t("strategy"), t("side"), t("fw_signal_bar"), t("price"), t("stop"), t("target"),
                               t("fw_exit"), t("fw_reason"), "PnL %", "R", "MFE R", "MAE R", t("conf"), t("fw_source")])
        self.tbl.itemDoubleClicked.connect(self._open)
        rec.add(self.tbl)
        v.addWidget(rec, 2)

        self.timer = QtCore.QTimer(self); self.timer.setInterval(15 * 60 * 1000); self.timer.timeout.connect(lambda: self.auto.isChecked() and self.update_now())
        self.timer.start()
        self.render()

    # ---------------------------------------------------------------- actions
    def update_now(self):
        self.upd.setEnabled(False); self.prog.setVisible(True)

        def work(progress=None):
            return FW.update(progress=progress)
        self.w = Worker(work)
        self.w.progress.connect(lambda p, s: (self.prog.setValue(p), self.status.setText(s)))
        self.w.done.connect(lambda r: (self.upd.setEnabled(True), self.prog.setVisible(False), self.status.setText(t("fw_updated").format(r[0], r[1])), self.render()))
        self.w.error.connect(lambda e: (self.upd.setEnabled(True), self.prog.setVisible(False), QtWidgets.QMessageBox.warning(self, "Error", e)))
        self.w.start()

    def clear(self):
        if QtWidgets.QMessageBox.question(self, t("fw_clear"), t("fw_clear_q")) == QtWidgets.QMessageBox.StandardButton.Yes:
            FW.clear(); self.render()

    def export(self):
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "CSV", "forward_test.csv", "CSV (*.csv)")
        if path:
            import pandas as pd
            pd.DataFrame(FW.records()).drop(columns=["expect"], errors="ignore").to_csv(path, index=False)

    def _open(self, item):
        r = self.tbl.item(item.row(), 0).data(QtCore.Qt.ItemDataRole.UserRole)
        if r:
            self.window().open_chart(r["symbol"], r["tf"], r["sid"])

    # ---------------------------------------------------------------- render
    def render(self):
        import strategies as S
        fa = I18N.lang == "fa"
        rep = FW.report()
        o = rep["overall"]
        vmap = {"collecting": (t("fw_v_collecting"), C["yellow"]), "edge_confirmed": (t("fw_v_confirmed"), C["green"]),
                "positive_unconfirmed": (t("fw_v_positive"), C["accent2"]), "no_edge": (t("fw_v_none"), C["red"])}
        txt, col = vmap[rep["verdict"]]
        self.t_verdict.set(txt, col)
        self.t_n.set(f"{rep['n_closed']} / {rep['n_open']}")
        if o["n"]:
            self.t_wr.set(f"{o['wr']:.0f}%  [{o['wr_lo']:.0f}–{o['wr_hi']:.0f}]", C["green"] if o["wr_lo"] > 50 else None)
            pf_ci = f"[{o['pf_lo']:.2f}–{o['pf_hi']:.2f}]" if o["pf_lo"] == o["pf_lo"] else ""
            self.t_pf.set(f"{o['pf']:.2f}  {pf_ci}", color_for(o["pf"] - 1))
            self.t_r.set(f"{o['avg_r']:+.2f} R", color_for(o["avg_r"]))
        else:
            self.t_wr.set("—"); self.t_pf.set("—"); self.t_r.set("—")
        if rep["gap_pf"] is not None:
            g = rep["gap_pf"]
            self.t_gap.set(f"×{g:.2f}  ({rep['gap_wr']:+.0f} pt)", C["green"] if g >= 0.8 else (C["yellow"] if g >= 0.6 else C["red"]))
        else:
            self.t_gap.set(t("fw_need10"), C["muted"])

        def name(sid):
            c = S.REGISTRY.get(sid)
            return (c.name_fa if fa else c.name_en).split(" (")[0] if c else sid

        self.tbl_sid.setSortingEnabled(False); self.tbl_sid.setRowCount(0)
        for sid, a in sorted(rep["by_sid"].items(), key=lambda kv: -kv[1]["n"]):
            r = self.tbl_sid.rowCount(); self.tbl_sid.insertRow(r)
            self.tbl_sid.setItem(r, 0, cell(name(sid))); self.tbl_sid.setItem(r, 1, ncell(a["n"], "{:.0f}"))
            self.tbl_sid.setItem(r, 2, ncell(a["wr"], "{:.0f}%")); self.tbl_sid.setItem(r, 3, cell(f"{a['wr_lo']:.0f}–{a['wr_hi']:.0f}", C["muted"]))
            self.tbl_sid.setItem(r, 4, ncell(a["pf"], "{:.2f}", color_for(a["pf"] - 1)))
            self.tbl_sid.setItem(r, 5, cell(f"{a['pf_lo']:.2f}–{a['pf_hi']:.2f}" if a["pf_lo"] == a["pf_lo"] else "—", C["muted"]))
            self.tbl_sid.setItem(r, 6, ncell(a["avg_r"], "{:+.2f}", color_for(a["avg_r"])))
            self.tbl_sid.setItem(r, 7, cell(f"WR {a['exp_wr']:.0f}% · PF {a['exp_pf']:.2f}" if a["exp_wr"] == a["exp_wr"] else "—", C["muted"]))
            self.tbl_sid.setItem(r, 8, grade_cell(a["grade"]))
        self.tbl_sid.setSortingEnabled(True); self.tbl_sid.resizeColumnsToContents()

        self.tbl_tf.setSortingEnabled(False); self.tbl_tf.setRowCount(0)
        for tf in ("5m", "15m", "30m", "1h", "4h", "1d", "1wk"):
            a = rep["by_tf"].get(tf)
            if not a:
                continue
            r = self.tbl_tf.rowCount(); self.tbl_tf.insertRow(r)
            self.tbl_tf.setItem(r, 0, cell(tf)); self.tbl_tf.setItem(r, 1, ncell(a["n"], "{:.0f}"))
            self.tbl_tf.setItem(r, 2, ncell(a["wr"], "{:.0f}%")); self.tbl_tf.setItem(r, 3, ncell(a["pf"], "{:.2f}", color_for(a["pf"] - 1)))
            self.tbl_tf.setItem(r, 4, ncell(a["avg_r"], "{:+.2f}", color_for(a["avg_r"]))); self.tbl_tf.setItem(r, 5, grade_cell(a["grade"]))
        self.tbl_tf.setSortingEnabled(True); self.tbl_tf.resizeColumnsToContents()

        self.tbl.setSortingEnabled(False); self.tbl.setRowCount(0)
        for rec in FW.records()[:500]:
            r = self.tbl.rowCount(); self.tbl.insertRow(r)
            st = rec["status"]
            it = cell("● " + (t("fw_open") if st == "open" else t("fw_closed_s")), C["yellow"] if st == "open" else C["muted"])
            it.setData(QtCore.Qt.ItemDataRole.UserRole, rec)
            self.tbl.setItem(r, 0, it)
            self.tbl.setItem(r, 1, cell(rec["symbol"])); self.tbl.setItem(r, 2, cell(rec["tf"])); self.tbl.setItem(r, 3, cell(name(rec["sid"])))
            self.tbl.setItem(r, 4, cell(t("long") if rec["side"] == 1 else t("short"), C["green"] if rec["side"] == 1 else C["red"]))
            self.tbl.setItem(r, 5, cell(rec["bar"].replace("T", " ")[:16]))
            self.tbl.setItem(r, 6, ncell(rec.get("fill") or rec["entry"], "{:,.6g}")); self.tbl.setItem(r, 7, ncell(rec["stop"], "{:,.6g}", C["red"]))
            self.tbl.setItem(r, 8, ncell(rec["target"], "{:,.6g}", C["green"]))
            self.tbl.setItem(r, 9, ncell(rec["exit"], "{:,.6g}") if rec["exit"] else cell("—", C["muted"]))
            rs = rec["reason"] or "—"
            self.tbl.setItem(r, 10, cell(rs, C["green"] if rs == "target" else (C["red"] if rs.startswith("stop") else C["muted"])))
            self.tbl.setItem(r, 11, ncell(rec["pnl_pct"], "{:+.2f}%", color_for(rec["pnl_pct"])) if rec["pnl_pct"] is not None else cell("—"))
            self.tbl.setItem(r, 12, ncell(rec["r"], "{:+.2f}", color_for(rec["r"])) if rec["r"] is not None else cell("—"))
            self.tbl.setItem(r, 13, ncell(rec.get("mfe_r", 0), "{:.2f}")); self.tbl.setItem(r, 14, ncell(rec.get("mae_r", 0), "{:.2f}"))
            self.tbl.setItem(r, 15, ncell(rec.get("conf") or 0, "{:.0f}")); self.tbl.setItem(r, 16, cell(rec.get("source", ""), C["muted"]))
        self.tbl.setSortingEnabled(True); self.tbl.resizeColumnsToContents()
        if rep["last_update"]:
            self.status.setText(t("fw_last") + " " + time.strftime("%Y-%m-%d %H:%M", time.localtime(rep["last_update"])))
