# -*- coding: utf-8 -*-
"""Portfolio page (Phase 12): proven-only, low-correlation, equal-risk strategy portfolio + alerts centre."""
import numpy as np
import pandas as pd
import pyqtgraph as pg
from PyQt6 import QtCore, QtGui, QtWidgets
from .theme import C, t, I18N
from .widgets import Card, StatTile, make_table, cell, ncell, Worker, color_for
from .chart import EquityChart, TimeAxis


class PortfolioPage(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(24, 20, 24, 20)
        v.setSpacing(12)
        title = QtWidgets.QLabel(t("pf_title")); title.setObjectName("title"); v.addWidget(title)
        sub = QtWidgets.QLabel(t("pf_sub")); sub.setObjectName("subtitle"); sub.setWordWrap(True); v.addWidget(sub)

        bar = QtWidgets.QHBoxLayout()
        self.tf = QtWidgets.QComboBox(); self.tf.addItems(["1h", "4h", "1d"]); self.tf.setCurrentText("4h")
        self.n = QtWidgets.QSpinBox(); self.n.setRange(2, 10); self.n.setValue(5)
        self.corr = QtWidgets.QDoubleSpinBox(); self.corr.setRange(0.2, 0.95); self.corr.setSingleStep(0.05); self.corr.setValue(0.6)
        self.risk = QtWidgets.QDoubleSpinBox(); self.risk.setRange(0.1, 3.0); self.risk.setSingleStep(0.1); self.risk.setValue(1.0); self.risk.setSuffix(" %")
        for lbl, w in ((t("timeframe"), self.tf), (t("pf_max_n"), self.n), (t("pf_max_corr"), self.corr), (t("pf_risk"), self.risk)):
            bar.addWidget(QtWidgets.QLabel(lbl)); bar.addWidget(w)
        self.btn = QtWidgets.QPushButton(t("pf_build")); self.btn.setObjectName("primary"); self.btn.clicked.connect(self._build)
        bar.addWidget(self.btn); bar.addStretch()
        self.prog = QtWidgets.QProgressBar(); self.prog.setFixedWidth(220); self.prog.setTextVisible(False); self.prog.hide(); bar.addWidget(self.prog)
        v.addLayout(bar)

        tiles = QtWidgets.QHBoxLayout()
        self.t_n = StatTile(t("pf_n_strats")); self.t_ret = StatTile(t("cagr")); self.t_dd = StatTile(t("max_dd"))
        self.t_sh = StatTile(t("sharpe")); self.t_each = StatTile(t("pf_risk_each"))
        for x in (self.t_n, self.t_ret, self.t_dd, self.t_sh, self.t_each):
            tiles.addWidget(x)
        v.addLayout(tiles)

        split = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        left = Card(t("pf_curve"))
        self.chart = pg.PlotWidget(axisItems={"bottom": TimeAxis(orientation="bottom")})
        self.chart.setLayoutDirection(QtCore.Qt.LayoutDirection.LeftToRight)
        self.chart.showGrid(x=True, y=True, alpha=0.15); self.chart.setMenuEnabled(False); self.chart.addLegend(offset=(10, 10))
        self.chart.setMinimumHeight(320)
        left.add(self.chart)
        right = Card(t("pf_members"))
        self.tbl = make_table([t("strategy"), t("lib_group"), "PF", "WR %", "n", t("pf_breadth"), t("pf_weight"), "ρ max"])
        right.add(self.tbl)
        self.corr_lbl = QtWidgets.QLabel(); self.corr_lbl.setWordWrap(True); self.corr_lbl.setStyleSheet(f"color:{C['muted']};font-size:12px")
        right.add(self.corr_lbl)
        split.addWidget(left); split.addWidget(right); split.setSizes([800, 600])
        v.addWidget(split, 1)
        self.note = QtWidgets.QLabel(t("pf_note")); self.note.setWordWrap(True); self.note.setStyleSheet(f"color:{C['muted']};font-size:12px")
        v.addWidget(self.note)

    def _build(self):
        from core.portfolio import build_proven_portfolio
        self.btn.setEnabled(False); self.prog.show(); self.prog.setValue(0)
        self.w = Worker(build_proven_portfolio, tf=self.tf.currentText(), max_n=self.n.value(), max_corr=self.corr.value(),
                        risk_per_trade=self.risk.value())
        self.w.progress.connect(lambda p, m: (self.prog.setValue(p), self.window().statusBar().showMessage(m)))
        self.w.done.connect(self._show); self.w.error.connect(self._err); self.w.start()

    def _err(self, msg):
        self.btn.setEnabled(True); self.prog.hide()
        QtWidgets.QMessageBox.warning(self, "Portfolio", msg[:800])

    def _show(self, r):
        self.btn.setEnabled(True); self.prog.hide()
        self.tbl.setRowCount(0); self.chart.clear()
        if not r["rows"]:
            self.note.setText(t("pf_none") + (f" ({r['note']})" if r.get("note") else ""))
            return
        st = r["stats"]
        self.t_n.set(st["n"]); self.t_ret.set(f"{st['cagr_pct']:+.1f}%", color_for(st["cagr_pct"]))
        self.t_dd.set(f"-{st['max_dd_pct']:.1f}%", C["red"]); self.t_sh.set(f"{st['sharpe']:.2f}", color_for(st["sharpe"] - 1))
        self.t_each.set(f"{st['risk_each_pct']:.2f}%")
        combo = r["combo"]; M = r["curves"]
        self.chart.getAxis("bottom").set_index(combo.index)
        x = np.arange(len(combo))
        palette = [C["accent"], C["green"], C["yellow"], C["purple"], C["red"], "#4dd0e1", "#ff8a65", "#a1887f", "#90a4ae", "#ba68c8"]
        for i, k in enumerate(M.columns):
            self.chart.plot(x, M[k].values * 100, pen=pg.mkPen(palette[i % len(palette)] + "88", width=1), name=k.split("@")[0])
        self.chart.plot(x, combo.values * 100, pen=pg.mkPen("#ffffff", width=2.5), name=t("pf_combined"))
        self.chart.plot(x, np.zeros(len(x)), pen=pg.mkPen(C["muted"], style=QtCore.Qt.PenStyle.DashLine))
        import strategies as S
        from .widgets import strat_name
        for row in r["rows"]:
            s = row["stats"]; br = s.get("breadth", {})
            i = self.tbl.rowCount(); self.tbl.insertRow(i)
            self.tbl.setItem(i, 0, cell(strat_name(S.REGISTRY[row["sid"]]) if row["sid"] in S.REGISTRY else row["sid"]))
            self.tbl.setItem(i, 1, cell(row["group"]))
            self.tbl.setItem(i, 2, ncell(s["pf"], f"{s['pf']:.2f}", color_for(s["pf"] - 1)))
            self.tbl.setItem(i, 3, ncell(s["wr"], f"{s['wr']:.0f}"))
            self.tbl.setItem(i, 4, ncell(s["n"], str(s["n"])))
            self.tbl.setItem(i, 5, cell(f"{br.get('symbols_pos', 0) * 100:.0f}% / {br.get('years_pos', 0) * 100:.0f}%"))
            self.tbl.setItem(i, 6, cell(f"{row['weight'] * 100:.0f}%"))
            self.tbl.setItem(i, 7, ncell(row["corr_max"], f"{row['corr_max']:.2f}", C["green"] if row["corr_max"] < 0.4 else C["yellow"]))
        self.tbl.resizeColumnsToContents()
        cm = r["corr"]
        self.corr_lbl.setText(t("pf_corr_avg") + f": {float(cm.values[np.triu_indices(len(cm), 1)].mean()) if len(cm) > 1 else 0:.2f}  ·  {t('pf_years')}: {st['years']}")
        self.note.setText(t("pf_note"))


class AlertsPanel(QtWidgets.QWidget):
    """embedded in Settings: Telegram credentials, toggles, test button, last alerts"""
    def __init__(self, parent=None):
        super().__init__(parent)
        from core import alerts as AL
        s = AL.settings()
        a = s.get("alerts", {})
        v = QtWidgets.QVBoxLayout(self); v.setContentsMargins(0, 0, 0, 0)
        f = QtWidgets.QFormLayout()
        self.tok = QtWidgets.QLineEdit(s.get("telegram_token", "")); self.tok.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)
        self.tok.setPlaceholderText("123456:ABC-DEF…  (@BotFather)")
        self.chat = QtWidgets.QLineEdit(s.get("telegram_chat_id", "")); self.chat.setPlaceholderText("chat id  (@userinfobot)")
        self.cb_tg = QtWidgets.QCheckBox(t("al_tg")); self.cb_tg.setChecked(a.get("telegram", True))
        self.cb_dt = QtWidgets.QCheckBox(t("al_desktop")); self.cb_dt.setChecked(a.get("desktop", True))
        self.minc = QtWidgets.QSpinBox(); self.minc.setRange(0, 100); self.minc.setValue(int(a.get("min_conf", 55)))
        self.tfs = QtWidgets.QLineEdit(",".join(a.get("tfs", ["1h", "4h", "1d"])))
        # Phase 23: quality gate + news filter for alerts
        self.cb_news = QtWidgets.QCheckBox(t("news_filter")); self.cb_news.setChecked(a.get("news_filter", True))
        self.qmode = QtWidgets.QComboBox()
        for k, lab in (("proven", t("q_proven_only")), ("candidate", t("q_candidate")), ("all", t("q_all"))):
            self.qmode.addItem(lab, k)
        self.qmode.setCurrentIndex({"proven": 0, "candidate": 1, "all": 2}.get(a.get("quality_mode", "candidate"), 1))
        f.addRow(t("tg_token"), self.tok); f.addRow(t("tg_chat"), self.chat)
        f.addRow(t("al_channels"), self._row(self.cb_tg, self.cb_dt)); f.addRow(t("al_min_conf"), self.minc); f.addRow(t("al_tfs"), self.tfs)
        f.addRow(t("quality_mode"), self.qmode); f.addRow("", self.cb_news)
        v.addLayout(f)
        h = QtWidgets.QHBoxLayout()
        self.save = QtWidgets.QPushButton(t("save")); self.save.setObjectName("primary"); self.save.clicked.connect(self._save)
        self.test = QtWidgets.QPushButton(t("al_test")); self.test.clicked.connect(self._test)
        self.scan = QtWidgets.QPushButton(t("al_scan_now")); self.scan.clicked.connect(self._scan)
        h.addWidget(self.save); h.addWidget(self.test); h.addWidget(self.scan); h.addStretch(); v.addLayout(h)
        self.log = QtWidgets.QPlainTextEdit(); self.log.setReadOnly(True); self.log.setMaximumHeight(160)
        v.addWidget(self.log)
        self._refresh_log()

    @staticmethod
    def _row(*ws):
        w = QtWidgets.QWidget(); h = QtWidgets.QHBoxLayout(w); h.setContentsMargins(0, 0, 0, 0)
        for x in ws:
            h.addWidget(x)
        h.addStretch(); return w

    def _save(self):
        from core import alerts as AL
        AL.save_settings(dict(telegram_token=self.tok.text().strip(), telegram_chat_id=self.chat.text().strip(),
                              alerts=dict(telegram=self.cb_tg.isChecked(), desktop=self.cb_dt.isChecked(), min_conf=self.minc.value(),
                                          tfs=[x.strip() for x in self.tfs.text().split(",") if x.strip()],
                                          quality_mode=self.qmode.currentData(), news_filter=self.cb_news.isChecked())))
        self.log.appendPlainText("✓ " + t("saved"))

    def _test(self):
        from core import alerts as AL
        self._save()
        ok, msg = AL.telegram_test()
        AL.desktop_send("ProTrader", t("al_test_body"))
        self.log.appendPlainText(("✓ Telegram ok" if ok else f"✗ Telegram: {msg}"))

    def _scan(self):
        from core import alerts as AL
        self._save(); self.scan.setEnabled(False)
        self.w = Worker(AL.scan, lang=I18N.lang)
        self.w.progress.connect(lambda p, m: self.window().statusBar().showMessage(f"{p}% {m}"))
        self.w.done.connect(self._scanned); self.w.error.connect(lambda e: (self.scan.setEnabled(True), self.log.appendPlainText("✗ " + e[:300]))); self.w.start()

    def _scanned(self, sent):
        self.scan.setEnabled(True)
        self.log.appendPlainText(f"{t('al_sent')}: {len(sent)}")
        for s in sent[:10]:
            self.log.appendPlainText("  " + s["body"].split("\n")[0])
        self._refresh_log()

    def _refresh_log(self):
        from core import alerts as AL
        import time
        for a in AL.history(8):
            self.log.appendPlainText(f"{time.strftime('%m-%d %H:%M', time.localtime(a['ts']))}  {a['title']}  {a.get('result', {})}")
