"""Live Market page — whole-market WebSocket stream, breadth, heat list and real-time validated signals."""
import time
from PyQt6 import QtCore, QtGui, QtWidgets

import strategies as S
from core.live import LiveEngine
from .theme import C, t, I18N
from .widgets import Card, StatTile, make_table, cell, ncell, color_for


def _name(sid):
    cls = S.REGISTRY.get(sid)
    if not cls:
        return sid
    return cls.name_fa if I18N.lang == "fa" else cls.name_en


class _Bridge(QtCore.QObject):
    tick = QtCore.pyqtSignal(object)
    signal = QtCore.pyqtSignal(object)
    status = QtCore.pyqtSignal(str)


class LiveMarketPage(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.engine = None
        self.bridge = _Bridge()
        self.bridge.tick.connect(self._on_tick)
        self.bridge.signal.connect(self._on_signal)
        self.bridge.status.connect(self._on_status)
        self._seen = set()
        self._dirty = False

        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(16, 12, 16, 12)
        v.setSpacing(10)
        title = QtWidgets.QLabel(t("live_title"))
        title.setObjectName("h1")
        v.addWidget(title)
        sub = QtWidgets.QLabel(t("live_sub"))
        sub.setObjectName("subtitle")
        sub.setWordWrap(True)
        v.addWidget(sub)

        top = QtWidgets.QHBoxLayout()
        self.tf = QtWidgets.QComboBox()
        self.tf.addItems(["1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "12h", "1d", "3d", "1wk", "1mo"])
        self.tf.setCurrentText("1h")
        self.topn = QtWidgets.QSpinBox()
        self.topn.setRange(10, 500)
        self.topn.setValue(150)
        self.topn.setSingleStep(10)
        self.minscore = QtWidgets.QSpinBox()
        self.minscore.setRange(0, 100)
        self.minscore.setValue(40)
        self.ml_cb = QtWidgets.QCheckBox(t("live_use_ml"))
        for w_, lbl in ((self.tf, t("timeframe")), (self.topn, t("live_topn")), (self.minscore, t("lab_score") + " ≥")):
            top.addWidget(QtWidgets.QLabel(lbl))
            top.addWidget(w_)
        top.addWidget(self.ml_cb)
        self.btn = QtWidgets.QPushButton("▶  " + t("live_start"))
        self.btn.setObjectName("primary")
        self.btn.clicked.connect(self.toggle)
        top.addWidget(self.btn)
        top.addStretch()
        self.led = QtWidgets.QLabel("●")
        self.led.setStyleSheet(f"color:{C['muted']}; font-size:18px")
        top.addWidget(self.led)
        self.status = QtWidgets.QLabel(t("live_idle"))
        self.status.setObjectName("subtitle")
        top.addWidget(self.status)
        v.addLayout(top)

        tiles = QtWidgets.QHBoxLayout()
        self.t_sym = StatTile(t("live_t_symbols"))
        self.t_ticks = StatTile(t("live_t_ticks"))
        self.t_breadth = StatTile(t("live_t_breadth"))
        self.t_adv = StatTile(t("live_t_adv"))
        self.t_btc = StatTile("BTC 24h")
        self.t_sig = StatTile(t("live_t_signals"), color=C["accent"])
        for x in (self.t_sym, self.t_ticks, self.t_breadth, self.t_adv, self.t_btc, self.t_sig):
            tiles.addWidget(x)
        v.addLayout(tiles)

        split = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        sig_card = Card(t("live_signals_card"))
        self.tbl = make_table([t("time"), t("symbol"), t("strategy"), t("side"), t("fresh"), t("price"), t("live_now"), t("stop"), t("target"),
                               t("rr"), t("winrate"), t("pf"), "ML P(win)"])
        self.tbl.itemDoubleClicked.connect(self._open)
        sig_card.v.addWidget(self.tbl, 1)
        split.addWidget(sig_card)
        mk_card = Card(t("live_market_card"))
        self.filter = QtWidgets.QLineEdit()
        self.filter.setPlaceholderText("🔍 BTC, ETH, …")
        self.filter.textChanged.connect(lambda _: self._refresh_market())
        mk_card.v.addWidget(self.filter)
        self.mtbl = make_table([t("symbol"), t("price"), "24h %", t("live_vol24")])
        self.mtbl.setSortingEnabled(False)
        self.mtbl.horizontalHeader().setSortIndicatorShown(False)
        # ResizeToContents re-measures every row on each setText (300 rows × 4 cols every refresh) → use
        # Stretch instead; also uniform row heights let Qt skip per-row layout work.
        self.mtbl.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.mtbl.verticalHeader().setDefaultSectionSize(24)
        self.mtbl.verticalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Fixed)
        self.mtbl.itemDoubleClicked.connect(self._open_market)
        mk_card.v.addWidget(self.mtbl, 1)
        split.addWidget(mk_card)
        split.setSizes([900, 420])
        v.addWidget(split, 1)

        self.timer = QtCore.QTimer(self)
        self.timer.setInterval(3000)
        self.timer.timeout.connect(self._periodic)

    # ------------------------------------------------------------ control
    def toggle(self):
        if self.engine:
            self.engine.stop()
            self.engine = None
            self.timer.stop()
            self.btn.setText("▶  " + t("live_start"))
            self.led.setStyleSheet(f"color:{C['muted']}; font-size:18px")
            self.status.setText(t("live_stopped"))
            return
        self.engine = LiveEngine(timeframe=self.tf.currentText(), min_score=self.minscore.value(), top_n=self.topn.value(),
                                 use_ml=self.ml_cb.isChecked(), on_tick=self.bridge.tick.emit, on_signal=self.bridge.signal.emit,
                                 on_status=self.bridge.status.emit)
        self.engine.start()
        self.timer.start()
        self.btn.setText("■  " + t("live_stop"))
        self.led.setStyleSheet(f"color:{C['green']}; font-size:18px")

    # ------------------------------------------------------------ slots
    def _on_status(self, s):
        self.status.setText(s)

    def _on_tick(self, batch):
        self._dirty = True

    def _on_signal(self, out):
        fresh = [d for d in out if d["ago"] == 0 and (d["bsym"], d["sid"], d["ts"] // 60) not in self._seen]
        for d in fresh:
            self._seen.add((d["bsym"], d["sid"], d["ts"] // 60))
        if fresh:
            self.window().statusBar().showMessage(
                "🔔 " + " · ".join(f"{d['sym']} {'▲' if d['side'] == 1 else '▼'} {_name(d['sid'])}" for d in fresh[:3]), 15000)
        self._refresh_signals()

    def _periodic(self):
        if not self.engine:
            return
        e = self.engine
        self.t_sym.set(f"{len(e.symbols)} / {len(e.prices)}")
        self.t_ticks.set(f"{e.stats['ticks']:,}")
        b = e.breadth()
        self.t_breadth.set(f"{b['pct_above50']:.0f}% / {b['pct_above200']:.0f}%",
                           C["green"] if b["pct_above50"] > 60 else (C["red"] if b["pct_above50"] < 40 else C["yellow"]))
        self.t_adv.set(f"{b['advancers']} ▲ / {b['decliners']} ▼", color_for(b["advancers"] - b["decliners"]))
        self.t_btc.set(f"{b['btc_chg']:+.2f}%", color_for(b["btc_chg"]))
        self.t_sig.set(str(e.stats["signals"]))
        if self._dirty:
            self._dirty = False
            # only touch the market table when this page is actually visible – hidden work is wasted UI time
            if self.isVisible():
                self._refresh_market()
                self._update_now_prices()

    # ------------------------------------------------------------ tables
    def _refresh_signals(self):
        if not self.engine:
            return
        rows = self.engine.snapshot_signals()
        self.tbl.setSortingEnabled(False)
        self.tbl.setRowCount(0)
        for d in rows:
            r = self.tbl.rowCount()
            self.tbl.insertRow(r)
            it = cell(time.strftime("%H:%M", time.localtime(d["ts"])))
            it.setData(QtCore.Qt.ItemDataRole.UserRole, (d["sym"], d["tf"], d["sid"], d["bsym"]))
            self.tbl.setItem(r, 0, it)
            self.tbl.setItem(r, 1, cell(d["sym"]))
            self.tbl.setItem(r, 2, cell(_name(d["sid"]), C["accent2"] if d["sid"] == "ensemble" else None))
            self.tbl.setItem(r, 3, cell(t("long") if d["side"] == 1 else t("short"), C["green"] if d["side"] == 1 else C["red"]))
            self.tbl.setItem(r, 4, ncell(d["ago"], "{:.0f} " + t("bars_ago"), C["green"] if d["ago"] == 0 else None))
            self.tbl.setItem(r, 5, ncell(d["px"], "{:,.6g}"))
            self.tbl.setItem(r, 6, ncell(d["last"], "{:,.6g}", color_for((d["last"] - d["px"]) * d["side"])))
            self.tbl.setItem(r, 7, ncell(d["sl"], "{:,.6g}", C["red"]))
            self.tbl.setItem(r, 8, ncell(d["tp"], "{:,.6g}", C["green"]))
            self.tbl.setItem(r, 9, ncell(d["rr"], "1:{:.1f}"))
            self.tbl.setItem(r, 10, ncell(d["wr"], "{:.0f}%"))
            self.tbl.setItem(r, 11, ncell(d["pf"], "{:.2f}", color_for(d["pf"] - 1)))
            p = d.get("p_ml")
            self.tbl.setItem(r, 12, ncell(p * 100 if p == p else 0, "{:.0f}%" if p == p else "—",
                                          C["green"] if p == p and p > 0.4 else (C["red"] if p == p and p < 0.25 else C["muted"])))
        self.tbl.setSortingEnabled(True)
        self.tbl.sortItems(4, QtCore.Qt.SortOrder.AscendingOrder)

    def _update_now_prices(self):
        if not self.engine:
            return
        for r in range(self.tbl.rowCount()):
            d = self.tbl.item(r, 0).data(QtCore.Qt.ItemDataRole.UserRole)
            p = self.engine.prices.get(d[3])
            if p:
                px_item = self.tbl.item(r, 5)
                side = 1 if self.tbl.item(r, 3).text() == t("long") else -1
                entry = px_item.data(QtCore.Qt.ItemDataRole.UserRole) or 0
                self.tbl.setItem(r, 6, ncell(p["price"], "{:,.6g}", color_for((p["price"] - entry) * side)))

    def _refresh_market(self):
        """Update the market table IN PLACE: only cells whose text changed are touched (was: 1 200 new
        QTableWidgetItems every 1.5 s → the UI got slower the longer Live Market ran)."""
        if not self.engine:
            return
        q = self.filter.text().upper().strip()
        rows = self.engine.snapshot_market()
        if q:
            rows = [r for r in rows if q in r[0]]
        # Keep row ORDER stable between refreshes (re-rank by volume only every 30 s): sorting by live
        # volume on every tick reshuffled ~all rows → every cell was recreated each refresh.
        now = time.time()
        order = getattr(self, "_mkt_order", None)
        if order is None or now - getattr(self, "_mkt_order_t", 0) > 30 or q != getattr(self, "_mkt_q", None) \
                or len(order) != min(300, len(rows)):
            order = self._mkt_order = [r[0] for r in rows[:300]]
            self._mkt_order_t, self._mkt_q = now, q
        pos = {s: i for i, s in enumerate(order)}
        rows = sorted((r for r in rows if r[0] in pos), key=lambda r: pos[r[0]])
        tbl = self.mtbl
        tbl.setUpdatesEnabled(False)
        try:
            if tbl.rowCount() != len(rows):
                tbl.setRowCount(len(rows))
            for i, (s, px, chg, vol) in enumerate(rows):
                it0 = tbl.item(i, 0)
                if it0 is None or it0.data(QtCore.Qt.ItemDataRole.UserRole) != s:
                    it = cell(s[:-4] + "/USDT"); it.setData(QtCore.Qt.ItemDataRole.UserRole, s); tbl.setItem(i, 0, it)
                    tbl.setItem(i, 1, ncell(px, "{:,.6g}")); tbl.setItem(i, 2, ncell(chg, "{:+.2f}%", color_for(chg))); tbl.setItem(i, 3, ncell(vol / 1e6, "{:,.1f}M"))
                    continue
                for col, txt, colr in ((1, f"{px:,.6g}", None), (2, f"{chg:+.2f}%", color_for(chg)), (3, f"{vol / 1e6:,.1f}M", None)):
                    it = tbl.item(i, col)
                    if it is None:
                        tbl.setItem(i, col, ncell(px if col == 1 else (chg if col == 2 else vol / 1e6), "{}", colr)); it = tbl.item(i, col); it.setText(txt)
                    elif it.text() != txt:
                        it.setText(txt)
                        if colr:
                            it.setForeground(QtGui.QColor(colr))
        finally:
            tbl.setUpdatesEnabled(True)

    # ------------------------------------------------------------ nav
    def _open(self, item):
        d = self.tbl.item(item.row(), 0).data(QtCore.Qt.ItemDataRole.UserRole)
        if d:
            self.window().open_chart(d[0], d[1], d[2])

    def _open_market(self, item):
        s = self.mtbl.item(item.row(), 0).data(QtCore.Qt.ItemDataRole.UserRole)
        if s:
            self.window().open_chart(s[:-4] + "/USDT", self.tf.currentText(), "ensemble")
