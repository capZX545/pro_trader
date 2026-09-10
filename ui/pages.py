"""All application pages."""
import os
import json
import html
import time
import numpy as np
import pandas as pd
from PyQt6 import QtCore, QtGui, QtWidgets

from core.data import UNIVERSE, TIMEFRAMES, get_ohlcv, generate_synthetic, CACHE_DIR
from core.backtest import run_backtest
from core import indicators as ta
from core import risk as rk
from core import validation as V
import strategies as S
from .theme import C, t, I18N
from .widgets import Card, StatTile, Badge, side_badge, hline, stars, make_table, cell, ncell, Worker, color_for, success_tip, row_tooltip
from .chart import ChartWidget, EquityChart
try:
    from .chart_advanced_toolbar import TradingViewToolbar, ChartStatusBar
    HAS_ADV_TB = True
except Exception as e:
    print(f"[ChartPage] Advanced toolbar not available: {e}")
    HAS_ADV_TB = False

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
from core.paths import data as _data
JOURNAL_PATH = _data("journal.json")
SETTINGS_PATH = _data("settings.json")


def all_symbols():
    out = []
    for cat, d in UNIVERSE.items():
        for s in d:
            out.append((cat, s))
    return out


def strat_name(cls):
    return cls.name_fa if I18N.lang == "fa" else cls.name_en


def load_data(symbol, tf):
    try:
        return get_ohlcv(symbol, tf), True
    except Exception:
        return generate_synthetic(seed=abs(hash(symbol + tf)) % 10_000), False


# ---------------------------------------------------------------- toolbar
class SymbolBar(QtWidgets.QWidget):
    changed = QtCore.pyqtSignal()

    def __init__(self, with_strategy=True, parent=None):
        super().__init__(parent)
        h = QtWidgets.QHBoxLayout(self)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(8)
        self.sym = QtWidgets.QComboBox()
        self.sym.setMinimumWidth(190)
        for cat, d in UNIVERSE.items():
            for s in d:
                self.sym.addItem(f"{s}", s)
        self.sym.setCurrentIndex(0)
        self.sym.setEditable(True)
        self.sym.setInsertPolicy(QtWidgets.QComboBox.InsertPolicy.NoInsert)
        self.tf = QtWidgets.QComboBox()
        self.tf.addItems(TIMEFRAMES)
        self.tf.setCurrentText("1h")
        h.addWidget(QtWidgets.QLabel(t("symbol")))
        h.addWidget(self.sym)
        h.addWidget(QtWidgets.QLabel(t("timeframe")))
        h.addWidget(self.tf)
        self.strat = None
        if with_strategy:
            self.cat = QtWidgets.QComboBox()
            self.cat.addItem(t("all"), None)
            for c in S.CATEGORIES:
                self.cat.addItem(c, c)
            self.strat = QtWidgets.QComboBox()
            self.strat.setMinimumWidth(280)
            self.proven_only = QtWidgets.QCheckBox(t("proven_only"))
            try:
                from core import playbook as PB
                self.proven_only.setChecked(bool(PB.proven_ids()))
            except Exception:
                self.proven_only.setChecked(False)
            self.proven_only.setToolTip(t("proven_only_tip"))
            self.proven_only.toggled.connect(self._fill_strats)
            self._fill_strats()
            self.cat.currentIndexChanged.connect(self._fill_strats)
            self.tf.currentTextChanged.connect(lambda *_: self._fill_strats())
            self.sym.currentIndexChanged.connect(lambda *_: self._fill_strats())
            h.addWidget(self.proven_only)
            h.addWidget(QtWidgets.QLabel(t("category")))
            h.addWidget(self.cat)
            h.addWidget(QtWidgets.QLabel(t("strategy")))
            h.addWidget(self.strat)
        self.btn = QtWidgets.QPushButton(t("run"))
        self.btn.setObjectName("primary")
        self.btn.clicked.connect(self.changed.emit)
        h.addWidget(self.btn)
        h.addStretch()

    def _fill_strats(self):
        cat = self.cat.currentData()
        cur = self.strat.currentData()
        self.strat.blockSignals(True)
        self.strat.clear()
        proven = set()
        if getattr(self, "proven_only", None) is not None and self.proven_only.isChecked():
            try:
                from core import playbook as PB
                proven = PB.proven_ids()
            except Exception:
                proven = set()
        for cls in S.ALL_STRATEGIES:
            if cat is None or cls.category == cat:
                if proven and cls.id not in proven:
                    continue
                tag = " ✓" if cls.id in proven else ""
                wr = ""
                try:
                    from core import success as SR
                    lab = SR.label(cls.id, self.symbol(), self.tf.currentText(), short=True)
                    if lab:
                        wr = f"  [{lab}]"
                except Exception:
                    pass
                self.strat.addItem(f"{strat_name(cls)}{tag}{wr}  ·  {cls.category}", cls.id)
                try:
                    full = SR.label(cls.id, self.symbol(), self.tf.currentText())
                    tip = (cls.description_fa if I18N.lang == "fa" else cls.description_en) or ""
                    self.strat.setItemData(self.strat.count() - 1, (f"📊 {t('success_rate')}: {full}\n" if full else f"📊 {t('success_unknown')}\n") + tip, QtCore.Qt.ItemDataRole.ToolTipRole)
                except Exception:
                    pass
        if self.strat.count() == 0:   # nothing proven in this category → show all so the user is never stuck
            for cls in S.ALL_STRATEGIES:
                if cat is None or cls.category == cat:
                    self.strat.addItem(f"{strat_name(cls)}  ·  {cls.category}", cls.id)
        if cur:
            i = self.strat.findData(cur)
            if i >= 0:
                self.strat.setCurrentIndex(i)
        self.strat.blockSignals(False)

    def symbol(self):
        d = self.sym.currentData()
        return d if d and self.sym.currentText() == self.sym.itemText(self.sym.currentIndex()) else self.sym.currentText().strip()

    def timeframe(self):
        return self.tf.currentText()

    def strategy_id(self):
        return self.strat.currentData() if self.strat else None

    def set_strategy(self, sid):
        if self.strat:
            self.cat.setCurrentIndex(0)
            i = self.strat.findData(sid)
            if i >= 0:
                self.strat.setCurrentIndex(i)


# ---------------------------------------------------------------- Dashboard
class _TickBridge(QtCore.QObject):
    """Thread → UI-thread bridge for stream callbacks."""
    tick = QtCore.pyqtSignal(object, float, float, float, float, float, bool)
    status = QtCore.pyqtSignal(str)


class DashboardPage(QtWidgets.QWidget):
    goto = QtCore.pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(24, 20, 24, 20)
        v.setSpacing(16)
        head = QtWidgets.QHBoxLayout()
        tl = QtWidgets.QVBoxLayout()
        self.title = QtWidgets.QLabel(t("welcome"))
        self.title.setObjectName("title")
        self.sub = QtWidgets.QLabel(t("welcome_sub").replace("{n}", str(len(S.ALL_STRATEGIES))))
        self.sub.setObjectName("subtitle")
        tl.addWidget(self.title)
        tl.addWidget(self.sub)
        head.addLayout(tl)
        head.addStretch()
        self.bar = SymbolBar(with_strategy=False)
        self.bar.btn.setText(t("load"))
        head.addWidget(self.bar)
        v.addLayout(head)

        tiles = QtWidgets.QHBoxLayout()
        self.t_price = StatTile(t("price"))
        self.t_chg = StatTile(t("change"))
        self.t_trend = StatTile(t("trend"))
        self.t_regime = StatTile(t("regime"))
        self.t_vol = StatTile(t("vol"))
        self.t_rsi = StatTile(t("rsi"))
        self.t_health = StatTile(t("dash_health"))
        self.t_fw = StatTile(t("dash_forward"))
        for x in (self.t_price, self.t_chg, self.t_trend, self.t_regime, self.t_vol, self.t_rsi, self.t_health, self.t_fw):
            tiles.addWidget(x)
        v.addLayout(tiles)
        # ---- self-training banner (Phase 12): what the bot is teaching itself right now
        self.train = QtWidgets.QFrame(); self.train.setObjectName("card2")
        th = QtWidgets.QHBoxLayout(self.train); th.setContentsMargins(14, 8, 14, 8)
        self.train_lbl = QtWidgets.QLabel(t("train_idle")); self.train_lbl.setWordWrap(True)
        self.train_bar = QtWidgets.QProgressBar(); self.train_bar.setFixedWidth(220); self.train_bar.setTextVisible(True)
        th.addWidget(QtWidgets.QLabel("🤖")); th.addWidget(self.train_lbl, 1); th.addWidget(self.train_bar)
        v.addWidget(self.train)
        self._train_timer = QtCore.QTimer(self); self._train_timer.timeout.connect(self._train_status); self._train_timer.start(5000)
        QtCore.QTimer.singleShot(2500, self._bot_status)
        QtCore.QTimer.singleShot(1000, self._train_status)


        body = QtWidgets.QHBoxLayout()
        body.setSpacing(16)
        left = QtWidgets.QVBoxLayout()
        self.chart_card = Card(t("market_pulse"))
        self.chart = ChartWidget()
        self.chart.setMinimumHeight(380)
        self.chart_card.add(self.chart)
        left.addWidget(self.chart_card, 3)
        self.top_card = Card(t("top_strats"))
        self.top_tbl = make_table([t("strategy"), t("trades"), t("winrate"), t("pf"), t("ret"), t("dd")])
        self.top_tbl.setMinimumHeight(200)
        self.top_tbl.itemDoubleClicked.connect(self._open_strat)
        self.top_card.add(self.top_tbl)
        left.addWidget(self.top_card, 2)
        body.addLayout(left, 3)

        right = QtWidgets.QVBoxLayout()
        q = Card(t("quick"))
        for label, idx in ((t("nav_advisor"), "nav_advisor"), (t("nav_forward"), "nav_forward"), (t("nav_live"), "nav_live"), (t("nav_chart"), "nav_chart"), (t("nav_health"), "nav_health"), (t("nav_academy"), "nav_academy")):
            b = QtWidgets.QPushButton("→  " + label)
            b.clicked.connect(lambda _, i=idx: self.goto.emit(i))
            q.add(b)
        right.addWidget(q)
        tips = Card(t("tip_title"))
        for tip in t("tips"):
            l = QtWidgets.QLabel("•  " + tip)
            l.setWordWrap(True)
            l.setStyleSheet(f"color:{C['text']}; padding:2px 0;")
            tips.add(l)
        right.addWidget(tips)
        self.lesson = Card(t("lesson"))
        self.lesson_lbl = QtWidgets.QLabel("")
        self.lesson_lbl.setWordWrap(True)
        self.lesson_btn = QtWidgets.QPushButton(t("nav_academy") + " →")
        self.lesson_btn.clicked.connect(lambda: self.goto.emit("nav_academy"))
        self.lesson.add(self.lesson_lbl)
        self.lesson.add(self.lesson_btn)
        right.addWidget(self.lesson)
        right.addStretch()
        body.addLayout(right, 1)
        v.addLayout(body)
        self.bar.changed.connect(self.refresh)
        self._set_lesson()
        self.status = None

    def _train_status(self):
        try:
            from core import maintenance as M
            s = M.training_status()
        except Exception:
            return
        st = s.get("stage"); pr = int(s.get("progress") or 0)
        if st and pr < 100 and st != "forward":
            name = {"audit": t("train_audit"), "playbook-quick": t("train_quick"), "playbook-full": t("train_full")}.get(st, st)
            self.train_lbl.setText(f"<b>{t('train_running')}:</b> {name} — {s.get('detail', '')}")
            self.train_bar.setValue(pr); self.train_bar.show()
        else:
            a = s.get("audit_summary") or {}
            self.train_lbl.setText(f"<b>{t('train_done')}</b> · {t('train_audit')}: {a.get('pass', 0)}/{a.get('n', 0)} ✓ · "
                                   f"{t('train_proven')}: {s.get('proven_combos', 0)} · {t('train_tfs')}: {', '.join(s.get('playbook_tfs') or []) or '—'}"
                                   + (f" · {s['playbook_age_days']} {t('days')}" if s.get("playbook_age_days") is not None else ""))
            self.train_bar.hide()

    def _bot_status(self):
        def work():
            from core import health as H, forward as FW
            fs = H.run_checks(quick=True)
            return H.summary(fs), FW.report()
        self.w_bot = Worker(work)

        def show(res):
            s, rep = res
            if s["errors"]:
                self.t_health.set(f"⛔ {s['errors']} " + t("hl_errors").lower(), C["red"])
            elif s["warns"]:
                self.t_health.set(f"⚠ {s['warns']} " + t("hl_warns").lower(), C["yellow"])
            else:
                self.t_health.set("✅ " + t("hl_good"), C["green"])
            o = rep["overall"]
            if rep["n_closed"]:
                self.t_fw.set(f"{rep['n_closed']} · WR {o['wr']:.0f}% · PF {o['pf']:.2f}", color_for(o["pf"] - 1))
            else:
                self.t_fw.set(f"{rep['n_open']} " + t("fw_open"), C["muted"])
        self.w_bot.done.connect(show)
        self.w_bot.error.connect(lambda e: None)
        self.w_bot.start()

    def _set_lesson(self):
        import datetime
        cls = S.ALL_STRATEGIES[datetime.date.today().toordinal() % len(S.ALL_STRATEGIES)]
        d = cls.description_fa if I18N.lang == "fa" else cls.description_en
        self.lesson_lbl.setText(f"<b>{strat_name(cls)}</b><br><span style='color:{C['muted']}'>{cls.author}</span><br><br>{d}")

    def refresh(self):
        """Two stages so the chart is on screen within ~1 s: (1) load data → draw chart + tiles + start live stream,
        (2) rank all strategies in the background and fill the table when done."""
        sym, tf = self.bar.symbol(), self.bar.timeframe()
        self.bar.btn.setEnabled(False)
        self.bar.btn.setText(t("loading"))

        def work1():
            return load_data(sym, tf)

        def stage2(res):
            df, ok = res
            self._show(sym, tf, df, ok, None)
            self._start_stream(sym, tf)

            def work2():
                rows = []
                for cls in S.ALL_STRATEGIES:
                    try:
                        r = cls().run(df)
                        st = run_backtest(df, r).stats
                        rows.append((cls, st))
                    except Exception:
                        pass
                rows.sort(key=lambda x: x[1]["return_pct"], reverse=True)
                return rows
            self.w2 = Worker(work2)
            self.w2.done.connect(lambda rows: self._fill_top(rows) if (sym, tf) == (self.bar.symbol(), self.bar.timeframe()) else None)
            self.w2.error.connect(lambda e: None)
            self.w2.start()

        for old in ("w", "w2"):
            if getattr(self, old, None) is not None:
                getattr(self, old).cancel()
        try:
            from core import maintenance; maintenance.ui_busy(60)
        except Exception:
            pass
        self.w = Worker(work1)
        self.w.done.connect(stage2)
        self.w.error.connect(lambda e: (self.bar.btn.setEnabled(True), self.bar.btn.setText(t("load")), QtWidgets.QMessageBox.warning(self, "Error", e)))
        self.w.start()

    # -- live stream for the Market-pulse chart (same engine as the Chart page)
    def _start_stream(self, sym, tf):
        self._stop_stream()
        try:
            from core.data import resolve
            from core.sources import CandleStream
            cat, (yt, bs) = resolve(sym)
        except Exception:
            bs = None
        if not bs:
            return
        if not hasattr(self, "_tick_sig"):
            self._tick_sig = _TickBridge(self)
            self._tick_sig.tick.connect(self._on_tick)
            self._tick_sig.status.connect(lambda st: self.chart.set_live_status(("● " if st.startswith("live") else "○ ") + st, st.startswith("live")))
        self._stream = CandleStream(bs[:-4], tf, on_candle=lambda *a: self._tick_sig.tick.emit(*a), on_status=lambda st: self._tick_sig.status.emit(st))
        self._stream.start()

    def _stop_stream(self):
        st = getattr(self, "_stream", None)
        if st is not None:
            try:
                st.stop()
            except Exception:
                pass
            self._stream = None

    def stop_stream(self):
        self._stop_stream()

    def _on_tick(self, ts, o, h, l, c, v, closed):
        try:
            if self.chart.df is None:
                return
            self.chart.update_last_bar(pd.Timestamp(int(ts), unit="ms"), o, h, l, c, v, closed)
            self.t_price.set(f"{c:,.6g}")
        except Exception:
            pass

    def _fill_top(self, rows):
        self.top_tbl.setSortingEnabled(False)
        self.top_tbl.setRowCount(0)
        for cls, st in rows[:10]:
            r = self.top_tbl.rowCount()
            self.top_tbl.insertRow(r)
            it = cell(strat_name(cls))
            it.setData(QtCore.Qt.ItemDataRole.UserRole + 1, cls.id)
            self.top_tbl.setItem(r, 0, it)
            self.top_tbl.setItem(r, 1, ncell(st["trades"], "{:.0f}"))
            self.top_tbl.setItem(r, 2, ncell(st["win_rate"], "{:.1f}%"))
            self.top_tbl.setItem(r, 3, ncell(st["profit_factor"], "{:.2f}", color_for(st["profit_factor"] - 1)))
            self.top_tbl.setItem(r, 4, ncell(st["return_pct"], "{:+.1f}%", color_for(st["return_pct"])))
            self.top_tbl.setItem(r, 5, ncell(st["max_dd_pct"], "{:.1f}%", C["red"]))
        self.top_tbl.setSortingEnabled(True)

    def _show(self, sym, tf, df, ok, rows):
        self.bar.btn.setEnabled(True)
        self.bar.btn.setText(t("load"))
        self.chart.set_data(df.tail(400).copy(), title=f"{sym} · {tf}" + ("" if ok else f"  [{t('offline')}]"))
        c = df.close
        px = c.iloc[-1]
        bars_24h = {"1m": 1440, "3m": 480, "5m": 288, "15m": 96, "30m": 48, "1h": 24, "2h": 12, "4h": 6, "6h": 4, "12h": 2, "1d": 1, "3d": 1, "1wk": 1, "1mo": 1}.get(tf, 24)
        chg = (px / c.iloc[-1 - bars_24h] - 1) * 100 if len(c) > bars_24h else 0
        e50, e200 = ta.ema(c, 50).iloc[-1], ta.ema(c, 200).iloc[-1]
        adx, _, _ = ta.adx(df)
        adxv = adx.iloc[-1]
        atrp = ta.atr(df).iloc[-1] / px * 100
        atr_med = (ta.atr(df) / c * 100).rolling(100).median().iloc[-1]
        rsi = ta.rsi(c).iloc[-1]
        self.t_price.set(f"{px:,.6g}")
        self.t_chg.set(f"{chg:+.2f}%", color_for(chg))
        trend = t("bull") if px > e50 > e200 else (t("bear") if px < e50 < e200 else t("range"))
        self.t_trend.set(trend, C["green"] if trend == t("bull") else (C["red"] if trend == t("bear") else C["yellow"]))
        self.t_regime.set(f"{t('trending') if adxv > 25 else t('range')} (ADX {adxv:.0f})", C["accent2"] if adxv > 25 else C["yellow"])
        vol_lbl = t("high") if atrp > atr_med * 1.3 else (t("low") if atrp < atr_med * 0.7 else t("normal"))
        self.t_vol.set(f"{atrp:.2f}% · {vol_lbl}")
        self.t_rsi.set(f"{rsi:.1f}", C["red"] if rsi > 70 else (C["green"] if rsi < 30 else None))
        if rows is not None:
            self._fill_top(rows)
        else:
            self.top_tbl.setRowCount(0)

    def _open_strat(self, item):
        sid = self.top_tbl.item(item.row(), 0).data(QtCore.Qt.ItemDataRole.UserRole + 1)
        self.window().open_chart(self.bar.symbol(), self.bar.timeframe(), sid)


# ---------------------------------------------------------------- Chart & signals
class ChartPage(QtWidgets.QWidget):
    tick = QtCore.pyqtSignal(object, float, float, float, float, float, bool)   # stream thread → UI thread (ts as object: ms > 2^31)
    stream_status = QtCore.pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(16, 12, 16, 12)
        v.setSpacing(10)
        self.bar = SymbolBar()
        # live indicator (● LIVE · venue · next bar in mm:ss)
        self.live_lbl = QtWidgets.QLabel("")
        self.live_lbl.setStyleSheet(f"color:{C['muted']}; font-weight:600; padding:0 8px;")
        self.bar.layout().insertWidget(self.bar.layout().count() - 1, self.live_lbl)
        # renderer toggle (visible fix for "chart area is empty" reports)
        self.render_btn = QtWidgets.QToolButton()
        self.render_btn.setText("🖼")
        self.render_btn.setToolTip(t("chart_renderer_tip"))
        self.render_btn.setCheckable(True)
        self.render_btn.toggled.connect(self._toggle_renderer)
        self.bar.layout().insertWidget(self.bar.layout().count() - 1, self.render_btn)
        # world / local clock (exact system timezone) — top-right corner
        self.clock_lbl = QtWidgets.QLabel("")
        self.clock_lbl.setObjectName("clock")
        self.clock_lbl.setStyleSheet(f"color:{C['text']}; font-family: Consolas, monospace; font-size:12px; padding:0 6px; border:1px solid {C['border']}; border-radius:6px;")
        self.clock_lbl.setToolTip(t("clock_tip"))
        self.bar.layout().addWidget(self.clock_lbl)
        v.addWidget(self.bar)
        # === Advanced TradingView toolbar (optional, safe) ===
        self.tv_toolbar = None
        self.chart_status = None
        if HAS_ADV_TB:
            try:
                self.tv_toolbar = TradingViewToolbar()
                self.tv_toolbar.timeframeChanged.connect(lambda tf: (self.bar.tf.setCurrentText(tf), self.run()))
                self.tv_toolbar.chartTypeChanged.connect(self._on_chart_type)
                self.tv_toolbar.screenshotRequested.connect(self._on_screenshot)
                v.addWidget(self.tv_toolbar)
            except Exception as e:
                print(f"[ChartPage] Failed to create advanced toolbar: {e}")
                self.tv_toolbar = None
        
        # TradingView-style tool strip
        tools = QtWidgets.QHBoxLayout(); tools.setSpacing(4)
        from .chart_tools import TOOLS
        self.tool_group = QtWidgets.QButtonGroup(self); self.tool_group.setExclusive(True)
        for name, icon, key in TOOLS:
            b = QtWidgets.QToolButton(); b.setText(icon); b.setToolTip(t(key)); b.setCheckable(True); b.setFixedSize(30, 26)
            b.setProperty("tool", name); self.tool_group.addButton(b); tools.addWidget(b)
            if name == "cursor":
                b.setChecked(True)
        self.tool_group.buttonClicked.connect(lambda b: self.chart.set_tool(b.property("tool")))
        undo = QtWidgets.QToolButton(); undo.setText("↶"); undo.setToolTip(t("tool_undo")); undo.clicked.connect(lambda: self.chart.undo_drawing()); tools.addWidget(undo)
        clr = QtWidgets.QToolButton(); clr.setText("🗑"); clr.setToolTip(t("tool_clear")); clr.clicked.connect(self._clear_drawings); tools.addWidget(clr)
        tools.addSpacing(12)
        self.ind_btn = QtWidgets.QPushButton("ƒx  " + t("ind_add")); self.ind_btn.clicked.connect(self._add_indicator); tools.addWidget(self.ind_btn)
        self.ind_list = QtWidgets.QComboBox(); self.ind_list.setMinimumWidth(180); self.ind_list.setToolTip(t("ind_list_tip")); tools.addWidget(self.ind_list)
        rm = QtWidgets.QToolButton(); rm.setText("✕"); rm.setToolTip(t("ind_remove")); rm.clicked.connect(self._remove_indicator); tools.addWidget(rm)
        self.tpl_btn = QtWidgets.QToolButton(); self.tpl_btn.setText("★"); self.tpl_btn.setToolTip(t("ind_templates")); tools.addWidget(self.tpl_btn)
        tm = QtWidgets.QMenu(self.tpl_btn)
        for label, keys in ((t("tpl_ichimoku"), [("ichimoku", {})]), (t("tpl_classic"), [("ema", {"n": 20}), ("ema", {"n": 50}), ("ema", {"n": 200}), ("rsi", {}), ("macd", {})]),
                            (t("tpl_scalp"), [("vwap", {}), ("bollinger", {}), ("stoch", {"k": 5, "d": 3, "smooth": 3}), ("cvd", {}), ("relative_volume", {})]),
                            (t("tpl_volume"), [("volume_profile", {}), ("obv", {}), ("cmf", {}), ("mfi", {})]),
                            (t("tpl_trend"), [("supertrend", {}), ("adx", {}), ("kama", {}), ("psar", {})])):
            tm.addAction(label, lambda keys=keys: self._apply_template(keys))
        self.tpl_btn.setMenu(tm); self.tpl_btn.setPopupMode(QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup)
        self.refresh_btn = QtWidgets.QPushButton("⟳ " + t("refresh_keep")); self.refresh_btn.setToolTip(t("refresh_keep_tip")); self.refresh_btn.clicked.connect(lambda: self.run(keep_view=True))
        tools.addWidget(self.refresh_btn)
        self.tz_btn = QtWidgets.QToolButton(); self.tz_btn.setCheckable(True); self.tz_btn.setToolTip(t("tz_toggle_tip")); tools.addWidget(self.tz_btn)
        self.tz_btn.toggled.connect(self._toggle_tz)
        tools.addStretch()
        v.addLayout(tools)
        split = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        self.chart = ChartWidget()
        self.chart.signalClicked.connect(self._on_chart_signal_click)
        self.chart.drawingsChanged.connect(self._save_drawings)
        split.addWidget(self.chart)
        right = QtWidgets.QWidget()
        rv = QtWidgets.QVBoxLayout(right)
        rv.setContentsMargins(0, 0, 0, 0)
        self.sig_card = Card(t("last_signal"))
        self.sig_lbl = QtWidgets.QLabel(t("no_signal"))
        self.sig_lbl.setWordWrap(True)
        self.sig_lbl.setTextFormat(QtCore.Qt.TextFormat.RichText)
        self.sig_card.add(self.sig_lbl)
        rv.addWidget(self.sig_card)
        self.param_card = Card(t("params"))
        self.param_form = QtWidgets.QFormLayout()
        self.param_card.v.addLayout(self.param_form)
        pb = QtWidgets.QHBoxLayout()
        self.apply_btn = QtWidgets.QPushButton(t("apply"))
        self.apply_btn.setObjectName("primary")
        self.reset_btn = QtWidgets.QPushButton(t("reset"))
        pb.addWidget(self.apply_btn)
        pb.addWidget(self.reset_btn)
        self.param_card.v.addLayout(pb)
        rv.addWidget(self.param_card)
        self.tbl_card = Card(t("signals"))
        self.tbl = make_table([t("time"), t("side"), t("price"), t("stop"), t("target"), t("rr"), t("outcome")])
        self.tbl.setToolTip(t("signals_click_tip"))
        self.tbl_card.add(self.tbl)
        self.wr_lbl = QtWidgets.QLabel(""); self.wr_lbl.setWordWrap(True); self.wr_lbl.setObjectName("subtitle")
        self.tbl_card.add(self.wr_lbl)
        rv.addWidget(self.tbl_card, 1)
        split.addWidget(right)
        split.setSizes([950, 470])
        right.setMinimumWidth(420)
        v.addWidget(split, 1)
        self.bar.changed.connect(self.run)
        self.bar.strat.currentIndexChanged.connect(self._build_params)
        self.apply_btn.clicked.connect(self.run)
        self.reset_btn.clicked.connect(lambda: (self._build_params(), self.run()))
        self.tbl.itemClicked.connect(self._jump)
        self.param_widgets = {}
        self._build_params()
        self.df = None
        self.res = None
        self.stream = None
        self._stream_key = None
        self._last_recompute = 0.0
        self.tick.connect(self._on_tick)
        self.stream_status.connect(self._on_stream_status)
        self.render_btn.blockSignals(True); self.render_btn.setChecked(self.chart.mode == "compat"); self.render_btn.setText("🖼✓" if self.chart.mode == "compat" else "🖼"); self.render_btn.blockSignals(False)
        self.chart.modeChanged.connect(lambda m: (self.render_btn.blockSignals(True), self.render_btn.setChecked(m == "compat"), self.render_btn.setText("🖼✓" if m == "compat" else "🖼"), self.render_btn.blockSignals(False)))
        self._clock = QtCore.QTimer(self)
        self._clock.timeout.connect(self._tick_clock)
        self._clock.start(1000)

    def _on_advanced_hover(self, i):
        try:
            if not hasattr(self, 'chart_status') or self.chart_status is None:
                return
            df = self.chart.df
            if df is None or not (0 <= i < len(df)):
                return
            r = df.iloc[i]
            prev = df.iloc[i-1] if i>0 else r
            chg = (r.close/prev.close-1)*100 if prev.close else 0
            self.chart_status.set_ohlc(r.open, r.high, r.low, r.close, r.volume, chg)
            if hasattr(self, 'tv_toolbar') and self.tv_toolbar:
                self.tv_toolbar.set_price_info(f"{r.close:,.6g} {chg:+.2f}%")
        except Exception:
            pass

    def _on_chart_type(self, ctype):
        try:
            if ctype == "heikin":
                self.chart.add_indicator("heikin_ashi", {})
            elif ctype == "renko":
                self.chart.add_indicator("renko", {})
        except Exception as e:
            print(f"chart type switch failed: {e}")

    def _on_screenshot(self):
        try:
            pixmap = self.chart.grab()
            import datetime
            fname = f"chart_{self.bar.symbol()}_{self.bar.timeframe()}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save Screenshot", fname, "PNG (*.png)")
            if path:
                pixmap.save(path)
        except Exception as e:
            print(f"screenshot failed: {e}")

    def _on_chart_settings(self):
        try:
            from PyQt6.QtWidgets import QDialog, QFormLayout, QCheckBox, QDialogButtonBox
            dlg = QDialog(self)
            dlg.setWindowTitle("Chart Settings")
            dlg.resize(400, 300)
            layout = QFormLayout(dlg)
            grid_cb = QCheckBox(); grid_cb.setChecked(True)
            layout.addRow("Show Grid", grid_cb)
            vol_cb = QCheckBox(); vol_cb.setChecked(True)
            layout.addRow("Show Volume", vol_cb)
            btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
            btns.accepted.connect(dlg.accept); btns.rejected.connect(dlg.reject)
            layout.addRow(btns)
            dlg.exec()
        except Exception as e:
            print(f"settings dialog failed: {e}")

    def _toggle_renderer(self, on):
        from .chart import ChartWidget
        mode = "compat" if on else "pyqtgraph"
        ChartWidget._forced = None
        try:
            cur = json.load(open(SETTINGS_PATH))
        except Exception:
            cur = {}
        cur["chart_renderer"] = mode
        try:
            json.dump(cur, open(SETTINGS_PATH, "w"), indent=1)
        except Exception:
            pass
        for w in self.window().findChildren(ChartWidget):
            w.switch(mode)
        self.render_btn.setText("🖼✓" if on else "🖼")

    # ------------------------------------------------------------------ live stream
    def hideEvent(self, e):
        # page hidden (user navigated elsewhere): keep the socket — cheap, and the chart stays in sync on return
        super().hideEvent(e)

    def closeEvent(self, e):
        self.stop_stream()
        super().closeEvent(e)

    def start_stream(self, sym, tf):
        from core.data import resolve
        from core.sources import CandleStream
        key = (sym, tf)
        if self._stream_key == key and self.stream is not None and self.stream.is_alive():
            return
        self.stop_stream()
        try:
            cat, (yt, bs) = resolve(sym)
        except Exception:
            bs = None
        if not bs:
            # non-crypto (Yahoo): no websocket → poll every 60 s via get_ohlcv (cache-busting) in a worker
            self._poll_timer = QtCore.QTimer(self)
            self._poll_timer.timeout.connect(lambda: self._poll_refresh(sym, tf))
            self._poll_timer.start(60_000)
            self._stream_key = key
            self._on_stream_status("polling 60s")
            return
        base = bs[:-4]
        self.stream = CandleStream(base, tf,
                                   on_candle=lambda ts, o, h, l, c, v, x: self.tick.emit(ts, o, h, l, c, v, x),
                                   on_status=lambda st: self.stream_status.emit(st))
        self.stream.start()
        self._stream_key = key

    def stop_stream(self):
        if getattr(self, "_poll_timer", None):
            self._poll_timer.stop(); self._poll_timer = None
        if self.stream is not None:
            try:
                self.stream.stop()
            except Exception:
                pass
            self.stream = None
        self._stream_key = None

    def _poll_refresh(self, sym, tf):
        if (sym, tf) != (self.bar.symbol(), self.bar.timeframe()):
            return
        def work():
            return get_ohlcv(sym, tf, max_age_sec=30)
        self._pw = Worker(work)
        def done(df):
            if self.df is None or df is None or not len(df):
                return
            r = df.iloc[-1]
            appended = self.chart.update_last_bar(df.index[-1], r.open, r.high, r.low, r.close, r.volume, False)
            if appended:
                self._recompute()
        self._pw.done.connect(done)
        self._pw.error.connect(lambda e: None)
        self._pw.start()

    def _on_stream_status(self, st):
        ok = st.startswith("live")
        self._live_text = st
        self.chart.set_live_status(("● " if ok else "○ ") + st, ok)
        self.live_lbl.setStyleSheet(f"color:{C['green'] if ok else C['muted']}; font-weight:600; padding:0 8px;")
        self._tick_clock()

    def _tick_clock(self):
        """Countdown to the close of the current bar (like TradingView) + local/UTC clocks."""
        try:
            from core import clock
            lt, ld, ut = clock.now_strings()
            self.clock_lbl.setText(f"🕒 {lt}  {ld}  ·  UTC {ut}")
            if not hasattr(self, "_tz_init"):
                self._tz_init = True
                self.tz_btn.blockSignals(True); self.tz_btn.setChecked(clock.display_mode() == "utc"); self.tz_btn.blockSignals(False)
                self.tz_btn.setText("UTC" if clock.display_mode() == "utc" else clock.tz_name().split(" ")[0])
        except Exception:
            pass
        if self.df is None or not len(self.df):
            self.live_lbl.setText(""); return
        from core.sources import TF_SECONDS
        sec = TF_SECONDS.get(self.bar.timeframe(), 3600)
        now = pd.Timestamp.utcnow().tz_localize(None)
        remain = int((self.df.index[-1] + pd.Timedelta(seconds=sec) - now).total_seconds())
        remain = max(remain, 0)
        h, m, s_ = remain // 3600, (remain % 3600) // 60, remain % 60
        cd = f"{h:02d}:{m:02d}:{s_:02d}" if h else f"{m:02d}:{s_:02d}"
        st = getattr(self, "_live_text", "")
        dot = "●" if st.startswith("live") else "○"
        self.live_lbl.setText(f"{dot} {st} · {t('next_bar')} {cd}" if st else "")

    def _on_tick(self, ts, o, h, l, c, v, closed):
        if self.df is None:
            return
        appended = self.chart.update_last_bar(pd.Timestamp(int(ts), unit="ms"), o, h, l, c, v, closed)
        # recompute strategy on bar close (or when a brand-new bar appears) — throttled to once per 3 s
        if (closed or appended) and time.time() - self._last_recompute > 3:
            self._last_recompute = time.time()
            self._recompute()

    def _recompute(self):
        """Re-run the strategy on the live frame in a worker and refresh overlays/signals without touching the view."""
        if self.df is None:
            return
        rw = getattr(self, "_rw", None)
        if rw is not None and rw.isRunning():
            return                                     # previous recompute still busy → skip this bar
        sym, tf, sid = self.bar.symbol(), self.bar.timeframe(), self.bar.strategy_id()
        params = self.params()
        df = self.df.copy()
        def work():
            strat = S.get(sid, **params)
            res = strat.run(df)
            bt = run_backtest(df, res)
            return df, res, bt
        self._rw = Worker(work)
        def done(r):
            if (sym, tf) != (self.bar.symbol(), self.bar.timeframe()):
                return
            df2, res, bt = r
            self._show(sym, tf, sid, df2, True, res, bt, keep_view=True)
        self._rw.done.connect(done)
        self._rw.error.connect(lambda e: None)
        self._rw.start()

    def _build_params(self):
        while self.param_form.rowCount():
            self.param_form.removeRow(0)
        self.param_widgets = {}
        cls = S.REGISTRY.get(self.bar.strategy_id())
        if not cls:
            return
        for k, val in cls.params.items():
            if isinstance(val, bool):
                w = QtWidgets.QCheckBox()
                w.setChecked(val)
            elif isinstance(val, int):
                w = QtWidgets.QSpinBox()
                w.setRange(1, 5000)
                w.setValue(val)
            else:
                w = QtWidgets.QDoubleSpinBox()
                w.setRange(0.0, 10000.0)
                w.setDecimals(3)
                w.setSingleStep(0.1)
                w.setValue(float(val))
            self.param_widgets[k] = w
            self.param_form.addRow(k, w)

    def params(self):
        out = {}
        for k, w in self.param_widgets.items():
            out[k] = w.isChecked() if isinstance(w, QtWidgets.QCheckBox) else w.value()
        return out

    def set_context(self, sym, tf, sid):
        i = self.bar.sym.findData(sym)
        if i >= 0:
            self.bar.sym.setCurrentIndex(i)
        else:
            self.bar.sym.setEditText(sym)
        self.bar.tf.setCurrentText(tf)
        if sid:
            self.bar.set_strategy(sid)
        self.run()

    def run(self, keep_view=None):
        sym, tf, sid = self.bar.symbol(), self.bar.timeframe(), self.bar.strategy_id()
        params = self.params()
        if keep_view is None:                      # same symbol/timeframe as what is on screen → keep the user's view
            keep_view = (getattr(self, "_shown_key", None) == (sym, tf))
        self.bar.btn.setEnabled(False)
        self.bar.btn.setText(t("loading"))

        def work():
            df, ok = load_data(sym, tf)
            if sid in ("funding_crowd_reversal",) or tf in ("1m", "3m", "5m", "15m"):
                try:                                   # perp positioning (funding/OI) for scalp strategies — best effort, cached
                    from core import derivs; derivs.attach(df, sym)
                except Exception:
                    pass
            strat = S.get(sid, **params)
            res = strat.run(df)
            bt = run_backtest(df, res)
            return df, ok, res, bt

        self.stop_stream()
        if getattr(self, "w", None) is not None:
            self.w.cancel()
        try:
            from core import maintenance; maintenance.ui_busy(20)
        except Exception:
            pass
        self.w = Worker(work)
        self.w.done.connect(lambda r: (self._show(sym, tf, sid, *r, keep_view=keep_view), self.start_stream(sym, tf)))
        self.w.error.connect(lambda e: (self.bar.btn.setEnabled(True), self.bar.btn.setText(t("run")), QtWidgets.QMessageBox.warning(self, "Error", e)))
        self.w.start()

    # ---- Phase 17 helpers
    def _add_indicator(self):
        from .chart_tools import IndicatorDialog
        d = IndicatorDialog(self)
        if d.exec() and d.result_value:
            key, params = d.result_value
            self.chart.add_indicator(key, params)
            self._refresh_ind_list(); self._save_layout()

    def _remove_indicator(self):
        i = self.ind_list.currentIndex()
        if i >= 0:
            self.chart.remove_indicator(i); self._refresh_ind_list(); self._save_layout()

    def _apply_template(self, keys):
        self.chart.indicators = [(k, dict(p)) for k, p in keys]
        self.chart.refresh_same(); self._refresh_ind_list(); self._save_layout()

    def _refresh_ind_list(self):
        self.ind_list.clear()
        for k, p in self.chart.indicators:
            self.ind_list.addItem(f"{k}({', '.join(f'{a}={b:g}' if isinstance(b, float) else f'{a}={b}' for a, b in p.items())})" if p else k)

    def _layout_key(self):
        return f"{self.bar.symbol()}|{self.bar.timeframe()}"

    def _save_layout(self):
        try:
            cur = json.load(open(SETTINGS_PATH))
        except Exception:
            cur = {}
        lay = cur.setdefault("chart_layouts", {})
        lay[self._layout_key()] = {"indicators": self.chart.indicators}
        lay["__last__"] = {"indicators": self.chart.indicators}
        try:
            json.dump(cur, open(SETTINGS_PATH, "w"), indent=1)
        except Exception:
            pass

    def _load_layout(self, sym, tf):
        try:
            lay = json.load(open(SETTINGS_PATH)).get("chart_layouts", {})
            d = lay.get(f"{sym}|{tf}") or lay.get("__last__") or {}
            self.chart.indicators = [(k, dict(p)) for k, p in d.get("indicators", [])]
        except Exception:
            pass
        self._refresh_ind_list()

    def _save_drawings(self):
        try:
            from core import drawings as D
            D.save(self.bar.symbol(), self.bar.timeframe(), self.chart.drawings_json())
        except Exception:
            pass

    def _clear_drawings(self):
        self.chart.clear_drawings(); self._save_drawings()

    def _toggle_tz(self, on):
        try:
            cur = json.load(open(SETTINGS_PATH))
        except Exception:
            cur = {}
        cur["chart_tz"] = "utc" if on else "local"
        try:
            json.dump(cur, open(SETTINGS_PATH, "w"), indent=1)
        except Exception:
            pass
        from core import clock
        self.tz_btn.setText("UTC" if on else clock.tz_name().split(" ")[0])
        if self.df is not None:
            self.chart.refresh_same(); self._fill_table()

    def _on_chart_signal_click(self, i):
        """Chart marker clicked → select the matching table row and show its details."""
        for r in range(self.tbl.rowCount()):
            it = self.tbl.item(r, 0)
            if it is not None and it.data(QtCore.Qt.ItemDataRole.UserRole) == i:
                self.tbl.selectRow(r); self.tbl.scrollToItem(it); break
        self._describe_signal(i)

    def _describe_signal(self, i):
        df, res = self.df, self.res
        if df is None or res is None or not (0 <= i < len(df)):
            return
        from core import clock
        side = int(res.signal.iloc[i]); px = float(df.close.iloc[i])
        sl = float(res.stop.iloc[i]) if res.stop is not None else float("nan")
        tp = float(res.target.iloc[i]) if res.target is not None else float("nan")
        col = C["green"] if side == 1 else C["red"]
        out = self._outcomes.get(i)
        oc = ""
        if out:
            oc = f"<br>{t('outcome')}: <b style='color:{C['green'] if out[0] > 0 else C['red']}'>{out[1]}</b> ({out[0]:+.2f}R · {out[2]} {t('bars')})"
        self.sig_lbl.setText(
            f"<div style='font-size:15px'>📍 <b style='color:{col}'>{t('long') if side == 1 else t('short')}</b> · {strat_name(S.REGISTRY[self.bar.strategy_id()])}</div>"
            f"<div style='color:{C['muted']}'>{clock.fmt(df.index[i])} ({t('local_time')}) · UTC {pd.Timestamp(df.index[i]).strftime('%H:%M')} · {len(df) - 1 - i} {t('bars_ago')}</div><br>"
            f"{t('entry')}: <b>{px:,.6g}</b><br>{t('stop')}: <b style='color:{C['red']}'>{sl:,.6g}</b><br>{t('target')}: <b style='color:{C['green']}'>{tp:,.6g}</b>"
            + (f"<br>{t('rr')}: <b>1:{abs(tp - px) / abs(px - sl):.1f}</b>" if sl == sl and tp == tp and px != sl else "") + oc)

    def _fill_table(self):
        df, res, bt = self.df, self.res, getattr(self, "_bt", None)
        if df is None or res is None:
            return
        from core import clock
        sig = res.signal
        idxs = np.where(sig.values != 0)[0][-200:][::-1]
        # outcome per signal bar from the backtest trades (entry bar = signal bar + 1 fill)
        self._outcomes = {}
        if bt is not None:
            pos = {ts: k for k, ts in enumerate(df.index)}
            for tr in bt.trades:
                k = pos.get(tr.entry_time)
                if k is None:
                    continue
                for j in (k - 1, k):
                    if 0 <= j < len(sig) and sig.iloc[j] != 0:
                        self._outcomes[j] = (tr.r_multiple, t("win") if tr.pnl > 0 else t("loss"), tr.bars); break
        self.tbl.setSortingEnabled(False)
        self.tbl.setRowCount(0)
        for i in idxs:
            r = self.tbl.rowCount()
            self.tbl.insertRow(r)
            side = int(sig.iloc[i])
            px = df.close.iloc[i]
            sl = res.stop.iloc[i] if res.stop is not None else np.nan
            tp = res.target.iloc[i] if res.target is not None else np.nan
            rr = abs(tp - px) / abs(px - sl) if sl == sl and tp == tp and px != sl else np.nan
            it = cell(clock.fmt(df.index[i]))
            it.setData(QtCore.Qt.ItemDataRole.UserRole, int(i))
            self.tbl.setItem(r, 0, it)
            self.tbl.setItem(r, 1, cell(t("long") if side == 1 else t("short"), C["green"] if side == 1 else C["red"]))
            self.tbl.setItem(r, 2, ncell(px, "{:,.6g}"))
            self.tbl.setItem(r, 3, ncell(sl, "{:,.6g}", C["red"]))
            self.tbl.setItem(r, 4, ncell(tp, "{:,.6g}", C["green"]))
            self.tbl.setItem(r, 5, ncell(rr, "1:{:.1f}"))
            out = self._outcomes.get(int(i))
            if out:
                self.tbl.setItem(r, 6, cell(f"{out[1]} {out[0]:+.1f}R", C["green"] if out[0] > 0 else C["red"]))
            else:
                self.tbl.setItem(r, 6, cell(t("open_or_na"), C["muted"]))
        # success-rate summary for this strategy on this symbol/timeframe (+ playbook OOS if available)
        if bt is not None:
            st = bt.stats
            txt = f"<b>{t('success_rate')}:</b> {st['win_rate']:.0f}% · PF {st['profit_factor']:.2f} · n={st['trades']} ({t('in_sample')})"
            try:
                from core import playbook as PB
                pbst = PB.stats_for(self.bar.strategy_id(), self.bar.timeframe(), self.bar.symbol())
                if pbst:
                    txt += f"<br><b>{t('oos_rate')}:</b> {pbst['wr']:.0f}% [{pbst['wr_lo']:.0f}–{pbst['wr_hi']:.0f}] · PF {pbst['pf']:.2f} · {pbst['grade']}"
            except Exception:
                pass
            self.wr_lbl.setText(txt)

    def _show(self, sym, tf, sid, df, ok, res, bt, keep_view=None):
        self.bar.btn.setEnabled(True)
        self.bar.btn.setText(t("run"))
        self.df = df
        self.res = res
        cls = S.REGISTRY[sid]
        st = bt.stats
        venue = df.attrs.get("venue") or ""
        title = f"{sym} · {tf} · {strat_name(cls)}   |   WR {st['win_rate']:.0f}%  PF {st['profit_factor']:.2f}  Ret {st['return_pct']:+.1f}%  DD {st['max_dd_pct']:.1f}%"
        if not ok:
            title += f"  [{t('offline')}]"
        elif df.attrs.get("stale"):
            title += f"  [{t('stale_cache')}]"
        self._bt = bt
        try:
            from core import success as SR
            SR.put(sid, sym, tf, bt.stats); SR.flush()
            self.bar._fill_strats()
            self.chart.impl.success_meta = (sid, sym, tf, strat_name(cls))
        except Exception:
            pass
        new_key = (sym, tf)
        if getattr(self, "_shown_key", None) != new_key:
            self._load_layout(sym, tf)
        keep = keep_view is not None and keep_view is not False
        self.chart.set_data(df, res, trades=bt.trades, title=title, keep_view=keep)
        if isinstance(keep_view, tuple):
            try:
                self.chart.set_x_range(*keep_view)
            except Exception:
                pass
        if getattr(self, "_shown_key", None) != new_key:
            try:
                from core import drawings as D
                self.chart.load_drawings(D.load(sym, tf))
            except Exception:
                pass
        self._shown_key = new_key
        if getattr(self, "_live_text", ""):
            self._on_stream_status(self._live_text)
        self._tick_clock()
        # table
        sig = res.signal
        idxs = np.where(sig.values != 0)[0][-200:][::-1]
        self._fill_table()
        # last signal card
        if len(idxs):
            i = idxs[0]
            ago = len(df) - 1 - i
            side = int(sig.iloc[i])
            px = df.close.iloc[i]
            sl = res.stop.iloc[i] if res.stop is not None else np.nan
            tp = res.target.iloc[i] if res.target is not None else np.nan
            col = C["green"] if side == 1 else C["red"]
            fresh = "🟢" if ago <= 2 else ("🟡" if ago <= 10 else "⚪")
            self.sig_lbl.setText(
                f"<div style='font-size:15px'>{fresh} <b style='color:{col}'>{t('long') if side == 1 else t('short')}</b> · {strat_name(cls)}</div>"
                f"<div style='color:{C['muted']}'>{__import__('core.clock', fromlist=['fmt']).fmt(df.index[i])} · {ago} {t('bars_ago')}</div><br>"
                f"{t('entry')}: <b>{px:,.6g}</b><br>{t('stop')}: <b style='color:{C['red']}'>{sl:,.6g}</b><br>"
                f"{t('target')}: <b style='color:{C['green']}'>{tp:,.6g}</b><br>"
                f"{t('rr')}: <b>1:{abs(tp - px) / abs(px - sl):.1f}</b>" if sl == sl and tp == tp and px != sl else
                f"<b style='color:{col}'>{t('long') if side == 1 else t('short')}</b> {ago} {t('bars_ago')}")
        else:
            self.sig_lbl.setText(t("no_signal"))

    def _jump(self, item):
        i = self.tbl.item(item.row(), 0).data(QtCore.Qt.ItemDataRole.UserRole)
        if i is None or self.df is None:
            return
        self.chart.highlight(int(i), pan=True)
        self._describe_signal(int(i))


# ---------------------------------------------------------------- Scanner
class ScannerPage(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(16, 12, 16, 12)
        v.setSpacing(10)
        top = QtWidgets.QHBoxLayout()
        self.tf = QtWidgets.QComboBox()
        self.tf.addItems(TIMEFRAMES)
        self.tf.setCurrentText("4h")
        self.recent = QtWidgets.QSpinBox()
        self.recent.setRange(1, 50)
        self.recent.setValue(3)
        self.minpf = QtWidgets.QDoubleSpinBox()
        self.minpf.setRange(0, 5)
        self.minpf.setValue(1.0)
        self.minpf.setSingleStep(0.1)
        self.cats = {}
        top.addWidget(QtWidgets.QLabel(t("timeframe")))
        top.addWidget(self.tf)
        top.addWidget(QtWidgets.QLabel(t("recent_bars")))
        top.addWidget(self.recent)
        top.addWidget(QtWidgets.QLabel(t("min_pf")))
        top.addWidget(self.minpf)
        for cat in UNIVERSE:
            cb = QtWidgets.QCheckBox(cat)
            cb.setChecked(cat in ("Crypto", "Forex", "Commodities"))
            self.cats[cat] = cb
            top.addWidget(cb)
        self.quality = QtWidgets.QComboBox()
        for k, lab in (("proven", t("q_proven_only")), ("candidate", t("q_candidate")), ("all", t("q_all"))):
            self.quality.addItem(lab, k)
        self.quality.setCurrentIndex(1)
        self.quality.setToolTip(t("q_tip"))
        top.addWidget(QtWidgets.QLabel(t("q_filter")))
        top.addWidget(self.quality)
        self.btn = QtWidgets.QPushButton(t("scan"))
        self.btn.setObjectName("primary")
        top.addWidget(self.btn)
        top.addStretch()
        v.addLayout(top)
        self.news = QtWidgets.QLabel("")
        self.news.setStyleSheet(f"color:{C['yellow']};font-weight:600")
        self.news.setWordWrap(True)
        v.addWidget(self.news)
        hint = QtWidgets.QLabel(t("scan_hint"))
        hint.setObjectName("subtitle")
        v.addWidget(hint)
        self.prog = QtWidgets.QProgressBar()
        self.prog.setRange(0, 100)
        self.prog.setValue(0)
        v.addWidget(self.prog)
        self.status = QtWidgets.QLabel("")
        self.status.setObjectName("subtitle")
        v.addWidget(self.status)
        self.tbl = make_table([t("symbol"), t("strategy"), t("category"), t("side"), t("fresh"), t("price"), t("stop"), t("target"), t("rr"), t("winrate"), t("pf"), t("conf"), t("robust"), t("grade"), t("score"), t("q_verdict")])
        self.tbl.itemDoubleClicked.connect(self._open)
        self.tbl.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self.tbl.customContextMenuRequested.connect(self._ctx)
        v.addWidget(self.tbl, 1)
        hb = QtWidgets.QHBoxLayout()
        self.plan_btn = QtWidgets.QPushButton("📋 " + t("plan"))
        self.plan_btn.clicked.connect(self._plan_selected)
        hb.addWidget(self.plan_btn)
        ph = QtWidgets.QLabel(t("plan_hint")); ph.setObjectName("subtitle"); ph.setWordWrap(True)
        hb.addWidget(ph, 1)
        v.addLayout(hb)
        self.plan_out = QtWidgets.QTextBrowser()
        self.plan_out.setMaximumHeight(210)
        self.plan_out.setVisible(False)
        v.addWidget(self.plan_out)
        self.btn.clicked.connect(self.scan)

    def _ctx(self, pos):
        it = self.tbl.itemAt(pos)
        if not it:
            return
        m = QtWidgets.QMenu(self)
        a = m.addAction("📋 " + t("plan"))
        if m.exec(self.tbl.viewport().mapToGlobal(pos)) == a:
            self.tbl.selectRow(it.row()); self._plan_selected()

    def _plan_selected(self):
        r = self.tbl.currentRow()
        if r < 0:
            return
        d = self.tbl.item(r, 0).data(QtCore.Qt.ItemDataRole.UserRole)
        if not d:
            return
        sym, sid = d[0], d[1]
        tf = self.tf.currentText()
        self.plan_out.setVisible(True)
        self.plan_out.setPlainText(t("scanning"))
        self.plan_btn.setEnabled(False)

        def job():
            from core import edge as E
            return E.trade_plan(sym, tf, sid)
        self._plan_w = Worker(job)
        self._plan_w.done.connect(self._plan_done)
        self._plan_w.error.connect(lambda e: (self.plan_out.setPlainText("⚠ " + str(e)), self.plan_btn.setEnabled(True)))
        self._plan_w.start()

    def _plan_done(self, p):
        self.plan_btn.setEnabled(True)
        if "error" in p:
            self.plan_out.setPlainText(str(p["error"])); return
        txt = p["text_fa"] if I18N.lang == "fa" else p["text_en"]
        col = C["green"] if p["verdict_en"] == "GO" else (C["yellow"] if p["verdict_en"] == "REDUCED" else C["red"])
        import html as _h
        body = _h.escape(txt).replace("\n", "<br>")
        import re as _re
        body = _re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", body)
        self.plan_out.setHtml(f'<div style="color:{col};line-height:1.6">{body}</div>')

    def scan(self):
        tf = self.tf.currentText()
        recent = self.recent.value()
        minpf = self.minpf.value()
        cats = [c for c, cb in self.cats.items() if cb.isChecked()]
        syms = [(c, s) for c, s in all_symbols() if c in cats]
        self.btn.setEnabled(False)
        self.btn.setText(t("scanning"))

        def work(progress=None):
            out = []
            total = len(syms)
            vcache = V.load_cache()
            for k, (cat, sym) in enumerate(syms):
                if progress:
                    progress(int(k / total * 100), f"{sym}")
                try:
                    df, ok = load_data(sym, tf)
                except Exception:
                    continue
                if not ok:
                    continue
                n = len(df)
                # confluence: count strategies agreeing on direction in recent bars
                per = []
                from core import playbook as PB
                proven = [sid for sid, _, _ in PB.best_for(tf, sym, k=8)]
                classes = [S.REGISTRY[i] for i in proven if i in S.REGISTRY] if proven else [c for c in S.ALL_STRATEGIES if V.score_of(c.id, 0) >= 45]
                for cls in classes:
                    try:
                        res = cls().run(df)
                    except Exception:
                        continue
                    sig = res.signal.values
                    idx = np.where(sig[-recent:] != 0)[0]
                    if len(idx) == 0:
                        continue
                    i = n - recent + idx[-1]
                    st = run_backtest(df, res).stats
                    try:
                        from core import success as SR; SR.put(cls.id, sym, tf, st)
                    except Exception:
                        pass
                    per.append((cls, res, i, st))
                longs = sum(1 for _, _, i, _ in per if _ is not None and per and True and _ is not None and True and per and True and True and (lambda r, ii: r.signal.values[ii] == 1)(_, i)) if False else sum(1 for _, r, i, _ in per if r.signal.values[i] == 1)
                shorts = sum(1 for _, r, i, _ in per if r.signal.values[i] == -1)
                for cls, res, i, st in per:
                    if st["profit_factor"] < minpf or st["trades"] < 10:
                        continue
                    if not V.allowed(cls.id, sym, tf):
                        continue  # domain lock: failed out-of-sample on this very market
                    side = int(res.signal.values[i])
                    px = df.close.values[i]
                    sl = res.stop.values[i] if res.stop is not None else np.nan
                    tp = res.target.values[i] if res.target is not None else np.nan
                    rr = abs(tp - px) / abs(px - sl) if sl == sl and tp == tp and px != sl else 0
                    conf = longs if side == 1 else shorts
                    ago = n - 1 - i
                    rob = vcache.get(cls.id, {}).get("score")
                    rob_w = (rob if rob is not None else 35) / 100
                    pbst = PB.stats_for(cls.id, tf, sym) or {}
                    grade = pbst.get("grade", "D")
                    gpen = {"A": 1.0, "B": 0.9, "C": 0.75, "D": 0.55}[grade]
                    pf_lo = st.get("pf_lo", st["profit_factor"])
                    pf_lo = pf_lo if pf_lo == pf_lo else st["profit_factor"] * 0.7
                    score = (min(pf_lo, 3) / 3 * 25 + st.get("wr_lo", st["win_rate"]) / 100 * 15 + min(rr, 4) / 4 * 10
                             + min(conf, 5) / 5 * 15 + (recent - ago) / recent * 10 + rob_w * 25) * gpen
                    out.append(dict(sym=sym, cls=cls, side=side, ago=ago, px=px, sl=sl, tp=tp, rr=rr, rob=rob, grade=grade, pb_n=pbst.get("n", 0),
                                    wr=st["win_rate"], pf=st["profit_factor"], conf=conf, score=score, last=df.close.values[-1],
                                    bar=df.index[i].isoformat(), tf=tf))
                    # auto forward-test record for fresh signals (never trades)
                    if ago <= 1 and sl == sl and tp == tp:
                        try:
                            from core import forward as FW
                            FW.record(sym, tf, cls.id, side, df.index[i], px, sl, tp, source="scanner",
                                      expect=dict(wr=pbst.get("wr", st["win_rate"]), pf=pbst.get("pf", st["profit_factor"]), n=pbst.get("n", st["trades"])), conf=score)
                        except Exception:
                            pass
            out.sort(key=lambda d: d["score"], reverse=True)
            return out

        if getattr(self, "w", None) is not None:
            self.w.cancel()
        try:
            from core import maintenance; maintenance.ui_busy(120)
        except Exception:
            pass
        self.w = Worker(work)
        self.w.progress.connect(lambda p, s: (self.prog.setValue(p), self.status.setText(s)))
        self.w.done.connect(self._show)
        self.w.error.connect(lambda e: (self.btn.setEnabled(True), self.btn.setText(t("scan")), QtWidgets.QMessageBox.warning(self, "Error", e)))
        self.w.start()

    def _show(self, rows):
        from core import quality as Q, calendar as CAL
        self.btn.setEnabled(True)
        self.btn.setText(t("scan"))
        self.prog.setValue(100)
        mode = self.quality.currentData()
        total = len(rows)
        for d in rows:
            try:
                qs = Q.score(d["cls"].id, d["sym"], d["tf"])
            except Exception:
                qs = dict(score=0, verdict="UNPROVEN", reasons_en=[], reasons_fa=[])
            d["q"] = qs
        rows = [d for d in rows if Q.passes(d["q"]["verdict"], mode)]
        hidden = total - len(rows)
        self.status.setText(f"{len(rows)} signals" + (f" · {hidden} {t('q_hidden')}" if hidden else "") + f" · {time.strftime('%H:%M:%S')}")
        try:
            ev = CAL.risk_now()
            self.news.setText(CAL.text(ev, I18N.lang) if ev else "")
        except Exception:
            self.news.setText("")
        self.tbl.setSortingEnabled(False)
        self.tbl.setRowCount(0)
        for d in rows:
            r = self.tbl.rowCount()
            self.tbl.insertRow(r)
            it = cell(d["sym"])
            it.setData(QtCore.Qt.ItemDataRole.UserRole, (d["sym"], d["cls"].id))
            self.tbl.setItem(r, 0, it)
            self.tbl.setItem(r, 1, cell(strat_name(d["cls"])))
            self.tbl.setItem(r, 2, cell(d["cls"].category, C["muted"]))
            self.tbl.setItem(r, 3, cell(t("long") if d["side"] == 1 else t("short"), C["green"] if d["side"] == 1 else C["red"]))
            self.tbl.setItem(r, 4, ncell(d["ago"], "{:.0f} " + t("bars_ago"), C["green"] if d["ago"] == 0 else None))
            self.tbl.setItem(r, 5, ncell(d["px"], "{:,.6g}"))
            self.tbl.setItem(r, 6, ncell(d["sl"], "{:,.6g}", C["red"]))
            self.tbl.setItem(r, 7, ncell(d["tp"], "{:,.6g}", C["green"]))
            self.tbl.setItem(r, 8, ncell(d["rr"], "1:{:.1f}"))
            self.tbl.setItem(r, 9, ncell(d["wr"], "{:.0f}%"))
            self.tbl.setItem(r, 10, ncell(d["pf"], "{:.2f}", color_for(d["pf"] - 1)))
            self.tbl.setItem(r, 11, ncell(d["conf"], "{:.0f}"))
            rob = d.get("rob")
            self.tbl.setItem(r, 12, ncell(rob if rob is not None else 0, "{:.0f}" if rob is not None else "—",
                                          C["green"] if (rob or 0) >= 55 else (C["yellow"] if (rob or 0) >= 40 else C["red"])))
            g = d.get("grade", "D")
            self.tbl.setItem(r, 13, cell(f"● {g} · n={d.get('pb_n', 0)}", {"A": C["green"], "B": C["accent2"], "C": C["yellow"]}.get(g, C["red"])))
            sc = d["score"]
            self.tbl.setItem(r, 14, ncell(sc, "{:.0f}", C["green"] if sc >= 60 else (C["yellow"] if sc >= 45 else C["muted"])))
            qv = d["q"]["verdict"]
            self.tbl.setItem(r, 15, cell(f"{Q.label(qv, I18N.lang)} · {d['q']['score']}", Q.VERDICT_COLOR.get(qv, C["muted"])))
            why = "\n".join("• " + x for x in (d["q"]["reasons_fa"] if I18N.lang == "fa" else d["q"]["reasons_en"]))
            row_tooltip(self.tbl, r, success_tip(d["cls"].id, d["sym"], d["tf"], strat_name(d["cls"])) + "\n\n" + t("q_why") + ":\n" + why)
        self.tbl.setSortingEnabled(True)
        self.tbl.sortItems(14, QtCore.Qt.SortOrder.DescendingOrder)
        fp = getattr(self.window(), "page", lambda k: None)("nav_forward")
        if fp is not None:
            fp.render()

    def _open(self, item):
        d = self.tbl.item(item.row(), 0).data(QtCore.Qt.ItemDataRole.UserRole)
        if d:
            self.window().open_chart(d[0], self.tf.currentText(), d[1])


# ---------------------------------------------------------------- Backtester
class BacktestPage(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(16, 12, 16, 12)
        v.setSpacing(10)
        self.bar = SymbolBar()
        self.bar.btn.setText(t("bt_run"))
        v.addWidget(self.bar)
        opts = QtWidgets.QHBoxLayout()
        self.cap = QtWidgets.QDoubleSpinBox()
        self.cap.setRange(100, 1e9)
        self.cap.setValue(10000)
        self.cap.setPrefix("$ ")
        self.risk = QtWidgets.QDoubleSpinBox()
        self.risk.setRange(0.1, 10)
        self.risk.setValue(1.0)
        self.risk.setSuffix(" %")
        self.comm = QtWidgets.QDoubleSpinBox()
        self.comm.setRange(0, 100)
        self.comm.setValue(5); self.comm.setSuffix(" bps")
        self.wf = QtWidgets.QSpinBox()
        self.wf.setRange(0, 90)
        self.wf.setValue(70)
        self.wf.setSuffix(" %")
        self.long_only = QtWidgets.QCheckBox(t("long_only"))
        self.be = QtWidgets.QCheckBox(t("breakeven"))
        for lbl, w in ((t("capital"), self.cap), (t("risk"), self.risk), (t("comm"), self.comm), (t("wf"), self.wf)):
            opts.addWidget(QtWidgets.QLabel(lbl))
            opts.addWidget(w)
        opts.addWidget(self.long_only)
        opts.addWidget(self.be)
        opts.addStretch()
        v.addLayout(opts)
        opts2 = QtWidgets.QHBoxLayout()
        self.cmp_btn = QtWidgets.QPushButton("⚖  " + t("compare"))
        opts2.addWidget(self.cmp_btn)
        self.exp_btn = QtWidgets.QPushButton("⬇  " + t("export_trades"))
        opts2.addWidget(self.exp_btn)
        opts2.addStretch()
        v.addLayout(opts2)
        tiles = QtWidgets.QHBoxLayout()
        self.tiles = {}
        for key, lbl in (("trades", t("trades")), ("win_rate", t("winrate")), ("profit_factor", t("pf")), ("return_pct", t("ret")),
                         ("max_dd_pct", t("dd")), ("sharpe", t("sharpe")), ("avg_r", t("avg_r")), ("expectancy", t("expect")), ("grade", t("grade"))):
            tl = StatTile(lbl)
            self.tiles[key] = tl
            tiles.addWidget(tl)
        v.addLayout(tiles)
        self.oos_lbl = QtWidgets.QLabel("")
        self.oos_lbl.setObjectName("subtitle")
        v.addWidget(self.oos_lbl)
        self.tabs = QtWidgets.QTabWidget()
        self.eq = EquityChart()
        self.tabs.addTab(self.eq, t("equity"))
        self.chart = ChartWidget()
        self.tabs.addTab(self.chart, t("nav_chart"))
        self.tbl = make_table([t("entry"), t("exit"), t("side"), t("entry_px"), t("exit"), t("pnl"), t("r_mult"), t("bars"), t("reason")])
        self.tabs.addTab(self.tbl, t("trade_list"))
        self.cmp_tbl = make_table([t("strategy"), t("category"), t("trades"), t("winrate"), t("pf"), t("ret"), t("dd"), t("sharpe"), t("avg_r"), t("out_sample") + " " + t("ret")])
        self.cmp_tbl.itemDoubleClicked.connect(self._pick_cmp)
        self.tabs.addTab(self.cmp_tbl, t("compare"))
        v.addWidget(self.tabs, 1)
        self.bar.changed.connect(self.run)
        self.cmp_btn.clicked.connect(self.compare)
        self.exp_btn.clicked.connect(self.export)
        self.bt = None

    def _kw(self):
        return dict(initial_capital=self.cap.value(), risk_pct=self.risk.value(), commission_bps=self.comm.value(),
                    allow_short=not self.long_only.isChecked(), breakeven_at_r=1.0 if self.be.isChecked() else None)

    def run(self):
        sym, tf, sid = self.bar.symbol(), self.bar.timeframe(), self.bar.strategy_id()
        kw = self._kw()
        wf = self.wf.value()
        self.bar.btn.setEnabled(False)

        def work():
            df, ok = load_data(sym, tf)
            res = S.get(sid).run(df)
            bt = run_backtest(df, res, **kw)
            oos = None
            if wf > 0:
                cut = int(len(df) * wf / 100)
                ins = run_backtest(df.iloc[:cut], S.get(sid).run(df.iloc[:cut]), **kw).stats
                oos_df = df.iloc[cut - 300:] if cut > 300 else df.iloc[cut:]
                r2 = S.get(sid).run(oos_df)
                r2.signal.iloc[:max(0, min(300, cut))] = 0
                out = run_backtest(oos_df, r2, **kw).stats
                oos = (ins, out)
            return df, ok, res, bt, oos

        if getattr(self, "w", None) is not None:
            self.w.cancel()
        try:
            from core import maintenance; maintenance.ui_busy(30)
        except Exception:
            pass
        self.w = Worker(work)
        self.w.done.connect(lambda r: self._show(sym, tf, sid, *r))
        self.w.error.connect(lambda e: (self.bar.btn.setEnabled(True), QtWidgets.QMessageBox.warning(self, "Error", e)))
        self.w.start()

    def _show(self, sym, tf, sid, df, ok, res, bt, oos):
        self.bar.btn.setEnabled(True)
        self.bt = bt
        st = bt.stats
        fmt = {"trades": "{:.0f}", "win_rate": "{:.1f}%", "profit_factor": "{:.2f}", "return_pct": "{:+.1f}%", "max_dd_pct": "{:.1f}%",
               "sharpe": "{:.2f}", "avg_r": "{:+.2f}R", "expectancy": "${:+,.2f}"}
        gcol = {"A": C["green"], "B": C["accent2"], "C": C["yellow"]}.get(st.get("grade", "D"), C["red"])
        for k, tl in self.tiles.items():
            if k == "grade":
                tl.set(f"● {st.get('grade', 'D')}  (t={st.get('t_stat', 0):.1f})", gcol)
                continue
            if k == "win_rate":
                tl.set(f"{st['win_rate']:.1f}%  [{st.get('wr_lo', 0):.0f}–{st.get('wr_hi', 100):.0f}]", None)
                continue
            if k == "profit_factor" and st.get("pf_lo", float("nan")) == st.get("pf_lo"):
                tl.set(f"{st['profit_factor']:.2f}  [{st['pf_lo']:.2f}–{st['pf_hi']:.2f}]", color_for(st["pf_lo"] - 1))
                continue
            v = st[k]
            col = None
            if k in ("return_pct", "avg_r", "expectancy", "sharpe"):
                col = color_for(v)
            elif k == "profit_factor":
                col = color_for(v - 1)
            elif k == "max_dd_pct":
                col = C["red"]
            tl.set(fmt[k].format(v) if v not in (float("inf"),) else "∞", col)
        if oos:
            ins, out = oos
            self.oos_lbl.setText(f"{t('in_sample')}: WR {ins['win_rate']:.0f}% · PF {ins['profit_factor']:.2f} · Ret {ins['return_pct']:+.1f}%      |      "
                                 f"{t('out_sample')}: WR {out['win_rate']:.0f}% · PF {out['profit_factor']:.2f} · Ret {out['return_pct']:+.1f}%"
                                 + f"      |      {t('need_n')}: {st.get('need_n', 0)}"
                                 + ("" if ok else f"      [{t('offline')}]"))
        self.eq.set_equity(bt.equity, bt.initial_capital)
        self.chart.set_data(df, res, trades=bt.trades, title=f"{sym} · {tf} · {strat_name(S.REGISTRY[sid])}")
        self.tbl.setSortingEnabled(False)
        self.tbl.setRowCount(0)
        for tr in bt.trades[::-1]:
            r = self.tbl.rowCount()
            self.tbl.insertRow(r)
            self.tbl.setItem(r, 0, cell(__import__("core.clock", fromlist=["fmt"]).fmt(tr.entry_time)))
            self.tbl.setItem(r, 1, cell(__import__("core.clock", fromlist=["fmt"]).fmt(tr.exit_time)))
            self.tbl.setItem(r, 2, cell(t("long") if tr.side == 1 else t("short"), C["green"] if tr.side == 1 else C["red"]))
            self.tbl.setItem(r, 3, ncell(tr.entry, "{:,.6g}"))
            self.tbl.setItem(r, 4, ncell(tr.exit, "{:,.6g}"))
            self.tbl.setItem(r, 5, ncell(tr.pnl, "${:+,.2f}", color_for(tr.pnl)))
            self.tbl.setItem(r, 6, ncell(tr.r_multiple, "{:+.2f}R", color_for(tr.r_multiple)))
            self.tbl.setItem(r, 7, ncell(tr.bars, "{:.0f}"))
            self.tbl.setItem(r, 8, cell(tr.reason, C["muted"]))
        self.tbl.setSortingEnabled(True)

    def compare(self):
        sym, tf = self.bar.symbol(), self.bar.timeframe()
        kw = self._kw()
        wf = self.wf.value()
        self.cmp_btn.setEnabled(False)
        self.cmp_btn.setText(t("comparing"))

        def work():
            df, ok = load_data(sym, tf)
            rows = []
            cut = int(len(df) * wf / 100) if wf > 0 else None
            for cls in S.ALL_STRATEGIES:
                try:
                    st = run_backtest(df, cls().run(df), **kw).stats
                    oos = None
                    if cut:
                        oos_df = df.iloc[max(cut - 300, 0):]
                        r2 = cls().run(oos_df)
                        r2.signal.iloc[:min(300, cut)] = 0
                        oos = run_backtest(oos_df, r2, **kw).stats["return_pct"]
                    rows.append((cls, st, oos))
                except Exception:
                    pass
            rows.sort(key=lambda x: x[1]["return_pct"], reverse=True)
            return rows

        self.w2 = Worker(work)
        self.w2.done.connect(self._show_cmp)
        self.w2.error.connect(lambda e: (self.cmp_btn.setEnabled(True), self.cmp_btn.setText(t("compare")), QtWidgets.QMessageBox.warning(self, "Error", e)))
        self.w2.start()

    def _show_cmp(self, rows):
        self.cmp_btn.setEnabled(True)
        self.cmp_btn.setText(t("compare"))
        self.cmp_tbl.setSortingEnabled(False)
        self.cmp_tbl.setRowCount(0)
        for cls, st, oos in rows:
            r = self.cmp_tbl.rowCount()
            self.cmp_tbl.insertRow(r)
            it = cell(strat_name(cls))
            it.setData(QtCore.Qt.ItemDataRole.UserRole, cls.id)
            self.cmp_tbl.setItem(r, 0, it)
            self.cmp_tbl.setItem(r, 1, cell(cls.category, C["muted"]))
            self.cmp_tbl.setItem(r, 2, ncell(st["trades"], "{:.0f}"))
            self.cmp_tbl.setItem(r, 3, ncell(st["win_rate"], "{:.1f}%"))
            self.cmp_tbl.setItem(r, 4, ncell(st["profit_factor"], "{:.2f}", color_for(st["profit_factor"] - 1)))
            self.cmp_tbl.setItem(r, 5, ncell(st["return_pct"], "{:+.1f}%", color_for(st["return_pct"])))
            self.cmp_tbl.setItem(r, 6, ncell(st["max_dd_pct"], "{:.1f}%", C["red"]))
            self.cmp_tbl.setItem(r, 7, ncell(st["sharpe"], "{:.2f}", color_for(st["sharpe"])))
            self.cmp_tbl.setItem(r, 8, ncell(st["avg_r"], "{:+.2f}", color_for(st["avg_r"])))
            self.cmp_tbl.setItem(r, 9, ncell(oos if oos is not None else 0, "{:+.1f}%", color_for(oos or 0)))
        self.cmp_tbl.setSortingEnabled(True)
        self.tabs.setCurrentWidget(self.cmp_tbl)

    def _pick_cmp(self, item):
        sid = self.cmp_tbl.item(item.row(), 0).data(QtCore.Qt.ItemDataRole.UserRole)
        self.bar.set_strategy(sid)
        self.run()
        self.tabs.setCurrentIndex(0)

    def export(self):
        if not self.bt or not self.bt.trades:
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, t("export_trades"), "trades.csv", "CSV (*.csv)")
        if path:
            pd.DataFrame([tr.__dict__ for tr in self.bt.trades]).to_csv(path, index=False)


# ---------------------------------------------------------------- Academy
class AcademyPage(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(16, 12, 16, 12)
        self.tabs = QtWidgets.QTabWidget()
        outer.addWidget(self.tabs)
        strat_tab = QtWidgets.QWidget()
        h = QtWidgets.QHBoxLayout(strat_tab)
        h.setContentsMargins(0, 8, 0, 0)
        self.tabs.addTab(strat_tab, "📚 " + t("acad_tab_strats"))
        self.tabs.addTab(IndicatorEncyclopedia(), "📐 " + t("acad_tab_inds"))
        self.tabs.addTab(LibraryTab(), "📖 " + t("acad_tab_lib"))
        left = QtWidgets.QVBoxLayout()
        self.search = QtWidgets.QLineEdit()
        self.search.setPlaceholderText("🔍 " + t("strategy"))
        left.addWidget(self.search)
        chips = QtWidgets.QGridLayout()
        chips.setSpacing(6)
        self.chip_group = QtWidgets.QButtonGroup(self)
        self.chip_group.setExclusive(True)
        for i, cat in enumerate([t("all")] + S.CATEGORIES):
            b = QtWidgets.QPushButton(cat)
            b.setObjectName("chip")
            b.setCheckable(True)
            b.setChecked(i == 0)
            self.chip_group.addButton(b, i)
            chips.addWidget(b, i // 4, i % 4)
        left.addLayout(chips)
        self.list = QtWidgets.QListWidget()
        self.list.setStyleSheet(f"QListWidget{{background:{C['panel']}; border:1px solid {C['border']}; border-radius:8px;}} "
                                f"QListWidget::item{{padding:10px; border-bottom:1px solid {C['border']};}} "
                                f"QListWidget::item:selected{{background:{C['accent']}33; color:white;}}")
        left.addWidget(self.list, 1)
        lw = QtWidgets.QWidget()
        lw.setLayout(left)
        lw.setMaximumWidth(420)
        h.addWidget(lw)
        self.detail = QtWidgets.QTextBrowser()
        self.detail.setOpenExternalLinks(True)
        self.detail.setStyleSheet(f"QTextBrowser{{background:{C['panel']}; border:1px solid {C['border']}; border-radius:10px; padding:18px; font-size:14px;}}")
        rv = QtWidgets.QVBoxLayout()
        rv.addWidget(self.detail, 1)
        self.try_btn = QtWidgets.QPushButton("📈  " + t("nav_chart"))
        self.try_btn.setObjectName("primary")
        self.try_btn.clicked.connect(self._try)
        rv.addWidget(self.try_btn)
        h.addLayout(rv, 1)
        self.search.textChanged.connect(self._fill)
        self.chip_group.idClicked.connect(lambda _: self._fill())
        self.list.currentItemChanged.connect(self._show)
        self._fill()
        self.list.setCurrentRow(0)

    def _fill(self):
        q = self.search.text().lower()
        cat_id = self.chip_group.checkedId()
        cat = None if cat_id <= 0 else S.CATEGORIES[cat_id - 1]
        self.list.clear()
        for cls in S.ALL_STRATEGIES:
            if cat and cls.category != cat:
                continue
            if q and q not in (cls.name_en + cls.name_fa + cls.author + cls.category).lower():
                continue
            it = QtWidgets.QListWidgetItem(f"{strat_name(cls)}\n{cls.category} · {stars(cls.difficulty)} · {cls.timeframes}")
            it.setData(QtCore.Qt.ItemDataRole.UserRole, cls.id)
            self.list.addItem(it)

    def _show(self, cur, prev=None):
        if not cur:
            return
        cls = S.REGISTRY[cur.data(QtCore.Qt.ItemDataRole.UserRole)]
        fa = I18N.lang == "fa"
        d = cls.description_fa if fa else cls.description_en
        rules = cls.rules_fa if fa else cls.rules_en
        pros = cls.pros_fa if fa else cls.pros_en
        cons = cls.cons_fa if fa else cls.cons_en
        other = cls.name_en if fa else cls.name_fa
        direction = "rtl" if fa else "ltr"
        li = lambda xs: "".join(f"<li style='margin:4px 0'>{x}</li>" for x in xs)
        params = "".join(f"<tr><td style='padding:3px 12px 3px 0;color:{C['muted']}'>{k}</td><td><b>{v}</b></td></tr>" for k, v in cls.params.items())
        vr = V.load_cache().get(cls.id)
        if vr:
            sc = vr["score"]
            vc = C["green"] if sc >= 55 else (C["yellow"] if sc >= 40 else C["red"])
            best = ", ".join(f"{a} {b}" for a, b in vr.get("best_markets", [])[:3])
            vbox = (f"<div style='background:{vc}22;border:1px solid {vc};border-radius:8px;padding:8px 12px;margin:6px 0'>"
                    f"<b style='color:{vc}'>🧬 {t('lab_score')}: {sc:.0f}/100</b> · {t('lab_oos_pf')} {vr.get('oos_pf_mean', 0):.2f} · "
                    f"{t('lab_oos_pos')} {vr.get('oos_pos_ratio', 0) * 100:.0f}% · {t('lab_mc_dd')} {vr.get('mc_dd95_median', 0):.1f}%"
                    f"<br><span style='color:{C['muted']}'>{t('lab_best')}: {best or '—'}</span></div>")
        else:
            vbox = ""
        try:
            from core import success as SR
            sm = SR.summary().get(cls.id)
            rows_ = [(k.split("|")[1], k.split("|")[2], d) for k, d in SR._load().items() if k.startswith(cls.id + "|") and d.get("n", 0) >= 10]
            rows_.sort(key=lambda x: -x[2]["pf"])
            cells = "".join(f"<tr><td style='padding:2px 10px 2px 0'>{a}</td><td style='padding:2px 10px 2px 0'>{b}</td>"
                            f"<td style='color:{C['green'] if d['pf'] >= 1 else C['red']}'><b>{d['wr']:.0f}%</b></td><td>PF {d['pf']:.2f}</td><td style='color:{C['muted']}'>n={d['n']}</td></tr>" for a, b, d in rows_[:12])
            if sm:
                sc_ = C["green"] if sm["pos_share"] >= 0.5 else (C["yellow"] if sm["pos_share"] >= 0.3 else C["red"])
                vbox += (f"<div style='background:{sc_}22;border:1px solid {sc_};border-radius:8px;padding:8px 12px;margin:6px 0'>"
                         f"<b style='color:{sc_}'>📊 {t('success_rate_all')}: {sm['wr']:.0f}%</b> · {t('median_pf')} {sm['pf']:.2f} · "
                         f"{t('pos_share')} {sm['pos_share'] * 100:.0f}% ({sm['cells']} {t('markets')}, n={sm['n']})<table style='margin-top:6px'>{cells}</table></div>")
            else:
                vbox += f"<div style='color:{C['muted']};margin:6px 0'>📊 {t('success_unknown')}</div>"
        except Exception:
            pass
        html = f"""
        <div dir='{direction}'>
        <h1 style='margin:0;color:white'>{strat_name(cls)}</h1>
        <div style='color:{C['muted']};font-size:13px'>{other}</div>
        <p style='margin-top:10px'>
          <span style='background:{C['accent']}33;color:{C['accent2']};padding:3px 10px;border-radius:10px'>{cls.category}</span>
          &nbsp;<span style='color:{C['yellow']}'>{stars(cls.difficulty)}</span>
          &nbsp;<span style='color:{C['muted']}'>⏱ {cls.timeframes}</span>
        </p>
        <p style='color:{C['muted']}'><b>{t('author')}:</b> {cls.author}</p>
        {vbox}
        <h3 style='color:{C['accent2']}'>{t('desc')}</h3><p style='line-height:1.6'>{d}</p>
        <h3 style='color:{C['accent2']}'>{t('rules')}</h3><ol style='line-height:1.6'>{li(rules)}</ol>
        <table width='100%'><tr>
          <td valign='top' width='50%'><h3 style='color:{C['green']}'>✔ {t('pros')}</h3><ul>{li(pros)}</ul></td>
          <td valign='top' width='50%'><h3 style='color:{C['red']}'>✘ {t('cons')}</h3><ul>{li(cons)}</ul></td>
        </tr></table>
        <h3 style='color:{C['accent2']}'>{t('params')}</h3><table>{params}</table>
        </div>"""
        self.detail.setHtml(html)

    def _try(self):
        cur = self.list.currentItem()
        if cur:
            self.window().open_chart(None, None, cur.data(QtCore.Qt.ItemDataRole.UserRole))


# ---------------------------------------------------------------- Risk
class RiskPage(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        h = QtWidgets.QHBoxLayout(self)
        h.setContentsMargins(24, 20, 24, 20)
        h.setSpacing(16)
        # position sizing
        c1 = Card(t("units"))
        f = QtWidgets.QFormLayout()
        self.eq = QtWidgets.QDoubleSpinBox(); self.eq.setRange(1, 1e9); self.eq.setValue(10000); self.eq.setPrefix("$ ")
        self.rp = QtWidgets.QDoubleSpinBox(); self.rp.setRange(0.05, 20); self.rp.setValue(1.0); self.rp.setSuffix(" %")
        self.en = QtWidgets.QDoubleSpinBox(); self.en.setRange(0, 1e9); self.en.setDecimals(5); self.en.setValue(100)
        self.sp = QtWidgets.QDoubleSpinBox(); self.sp.setRange(0, 1e9); self.sp.setDecimals(5); self.sp.setValue(98)
        self.lev = QtWidgets.QDoubleSpinBox(); self.lev.setRange(1, 125); self.lev.setValue(1)
        for lbl, w in ((t("equity_now"), self.eq), (t("risk_pct"), self.rp), (t("entry_px"), self.en), (t("stop_px"), self.sp), (t("leverage"), self.lev)):
            f.addRow(lbl, w)
        c1.v.addLayout(f)
        self.out = QtWidgets.QLabel("")
        self.out.setTextFormat(QtCore.Qt.TextFormat.RichText)
        self.out.setWordWrap(True)
        c1.add(self.out)
        c1.v.addStretch()
        h.addWidget(c1, 1)
        # expectancy / ruin
        c2 = Card(t("ror"))
        f2 = QtWidgets.QFormLayout()
        self.wr = QtWidgets.QDoubleSpinBox(); self.wr.setRange(1, 99); self.wr.setValue(40); self.wr.setSuffix(" %")
        self.rr = QtWidgets.QDoubleSpinBox(); self.rr.setRange(0.1, 20); self.rr.setValue(2.0)
        f2.addRow(t("wr_input"), self.wr)
        f2.addRow(t("rr_input"), self.rr)
        c2.v.addLayout(f2)
        self.out2 = QtWidgets.QLabel("")
        self.out2.setTextFormat(QtCore.Qt.TextFormat.RichText)
        self.out2.setWordWrap(True)
        c2.add(self.out2)
        # WR vs RR breakeven table
        self.tbl = make_table(["R:R", "Breakeven WR", "Exp @ your WR"])
        self.tbl.setSortingEnabled(False)
        c2.add(self.tbl)
        h.addWidget(c2, 1)
        for w in (self.eq, self.rp, self.en, self.sp, self.lev, self.wr, self.rr):
            w.valueChanged.connect(self.calc)
        self.calc()

    def calc(self):
        r = rk.position_size(self.eq.value(), self.rp.value(), self.en.value(), self.sp.value(), leverage=self.lev.value())
        if r:
            tg = rk.rr_targets(self.en.value(), self.sp.value())
            tg_html = " · ".join(f"{k}R: <b>{v:,.5g}</b>" for k, v in tg.items())
            self.out.setText(
                f"<table style='font-size:14px;line-height:1.9'>"
                f"<tr><td style='color:{C['muted']}'>{t('risk_amt')}</td><td><b style='color:{C['red']}'>${r['risk_amount']:,.2f}</b></td></tr>"
                f"<tr><td style='color:{C['muted']}'>{t('dist')}</td><td><b>{r['stop_distance']:,.5g} ({r['stop_distance_pct']:.2f}%)</b></td></tr>"
                f"<tr><td style='color:{C['muted']}'>{t('units')}</td><td><b style='color:{C['accent2']};font-size:18px'>{r['units']:,.4f}</b></td></tr>"
                f"<tr><td style='color:{C['muted']}'>{t('notional')}</td><td><b>${r['notional']:,.2f}</b> ({r['leverage_used']:.2f}x)</td></tr>"
                f"<tr><td style='color:{C['muted']}'>{t('margin')}</td><td><b>${r['margin_required']:,.2f}</b></td></tr>"
                f"</table><br><span style='color:{C['muted']}'>{t('targets')}:</span><br>{tg_html}")
        wr, rr, rp = self.wr.value(), self.rr.value(), self.rp.value()
        exp = rk.expectancy(wr, rr)
        ror = rk.risk_of_ruin(wr, rr, rp)
        k = rk.kelly_fraction(wr, rr, 1.0) * 100
        n_half = rk.max_trades_to_ruin(rp)
        col = color_for(exp)
        self.out2.setText(
            f"<table style='font-size:14px;line-height:1.9'>"
            f"<tr><td style='color:{C['muted']}'>{t('expect')}</td><td><b style='color:{col};font-size:18px'>{exp:+.2f}R</b> / trade</td></tr>"
            f"<tr><td style='color:{C['muted']}'>{t('ror')}</td><td><b style='color:{C['red'] if ror > 0.05 else C['green']}'>{ror * 100:.2f}%</b></td></tr>"
            f"<tr><td style='color:{C['muted']}'>{t('kelly')}</td><td><b>{k:.1f}%</b> (½ Kelly: {k / 2:.1f}%)</td></tr>"
            f"<tr><td style='color:{C['muted']}'>{t('losses_to_half')}</td><td><b>{n_half}</b></td></tr></table>")
        self.tbl.setRowCount(0)
        for r_ in (0.5, 1, 1.5, 2, 3, 4, 5):
            be = 100 / (1 + r_)
            e = rk.expectancy(wr, r_)
            row = self.tbl.rowCount()
            self.tbl.insertRow(row)
            self.tbl.setItem(row, 0, cell(f"1:{r_}"))
            self.tbl.setItem(row, 1, cell(f"{be:.1f}%"))
            self.tbl.setItem(row, 2, cell(f"{e:+.2f}R", color_for(e)))


# ---------------------------------------------------------------- Journal
class JournalPage(QtWidgets.QWidget):
    COLS = ["date", "symbol", "side", "strategy", "entry", "stop", "exit", "risk_pct", "r", "emotion", "notes"]

    def __init__(self, parent=None):
        super().__init__(parent)
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(16, 12, 16, 12)
        v.setSpacing(10)
        form = QtWidgets.QHBoxLayout()
        self.date = QtWidgets.QDateEdit(QtCore.QDate.currentDate()); self.date.setCalendarPopup(True)
        self.sym = QtWidgets.QComboBox(); self.sym.setEditable(True)
        for _, s in all_symbols():
            self.sym.addItem(s)
        self.side = QtWidgets.QComboBox(); self.side.addItems([t("long"), t("short")])
        self.strat = QtWidgets.QComboBox()
        for cls in S.ALL_STRATEGIES:
            self.strat.addItem(strat_name(cls), cls.id)
        self.strat.addItem("Discretionary", "manual")
        self.entry = QtWidgets.QDoubleSpinBox(); self.entry.setRange(0, 1e9); self.entry.setDecimals(5)
        self.stop = QtWidgets.QDoubleSpinBox(); self.stop.setRange(0, 1e9); self.stop.setDecimals(5)
        self.exit = QtWidgets.QDoubleSpinBox(); self.exit.setRange(0, 1e9); self.exit.setDecimals(5)
        self.riskp = QtWidgets.QDoubleSpinBox(); self.riskp.setRange(0, 20); self.riskp.setValue(1); self.riskp.setSuffix("%")
        self.emotion = QtWidgets.QComboBox(); self.emotion.addItems(["😐 Calm", "😤 FOMO", "😨 Fear", "😡 Revenge", "😎 Confident", "😴 Bored"])
        for lbl, w in ((t("date"), self.date), (t("symbol"), self.sym), (t("side"), self.side), (t("strategy"), self.strat),
                       (t("entry"), self.entry), (t("stop"), self.stop), (t("exit"), self.exit), (t("risk"), self.riskp), (t("emotion"), self.emotion)):
            col = QtWidgets.QVBoxLayout()
            l = QtWidgets.QLabel(lbl); l.setObjectName("statlbl")
            col.addWidget(l); col.addWidget(w)
            form.addLayout(col)
        v.addLayout(form)
        row2 = QtWidgets.QHBoxLayout()
        self.notes = QtWidgets.QLineEdit(); self.notes.setPlaceholderText(t("j_notes"))
        self.add_btn = QtWidgets.QPushButton(t("j_add")); self.add_btn.setObjectName("primary")
        self.del_btn = QtWidgets.QPushButton(t("j_del"))
        self.exp_btn = QtWidgets.QPushButton(t("j_export"))
        row2.addWidget(self.notes, 1); row2.addWidget(self.add_btn); row2.addWidget(self.del_btn); row2.addWidget(self.exp_btn)
        v.addLayout(row2)
        tiles = QtWidgets.QHBoxLayout()
        self.t_n = StatTile(t("trades")); self.t_wr = StatTile(t("winrate")); self.t_r = StatTile("Total R"); self.t_avg = StatTile(t("avg_r")); self.t_pf = StatTile(t("pf"))
        for x in (self.t_n, self.t_wr, self.t_r, self.t_avg, self.t_pf):
            tiles.addWidget(x)
        v.addLayout(tiles)
        self.tbl = make_table([t("date"), t("symbol"), t("side"), t("strategy"), t("entry"), t("stop"), t("exit"), t("risk"), "R", t("emotion"), t("j_notes")])
        split = QtWidgets.QHBoxLayout(); split.addWidget(self.tbl, 3)
        sb = Card(t("j_steen_title"))
        self.steen_tbl = make_table([t("j_steen_group"), t("trades"), t("winrate"), t("avg_r"), "Σ R"]); sb.add(self.steen_tbl)
        self.steen_txt = QtWidgets.QLabel(""); self.steen_txt.setWordWrap(True); self.steen_txt.setObjectName("subtitle"); sb.add(self.steen_txt)
        split.addWidget(sb, 2)
        v.addLayout(split, 1)
        self.add_btn.clicked.connect(self.add)
        self.del_btn.clicked.connect(self.delete)
        self.exp_btn.clicked.connect(self.export)
        self.rows = []
        self.load()

    def load(self):
        if os.path.exists(JOURNAL_PATH):
            try:
                self.rows = json.load(open(JOURNAL_PATH, encoding="utf-8"))
            except Exception:
                self.rows = []
        self.render()

    def save(self):
        os.makedirs(os.path.dirname(JOURNAL_PATH), exist_ok=True)
        json.dump(self.rows, open(JOURNAL_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    def add(self):
        e, s, x = self.entry.value(), self.stop.value(), self.exit.value()
        side = 1 if self.side.currentIndex() == 0 else -1
        r = ((x - e) * side / abs(e - s)) if e and s and x and e != s else 0.0
        self.rows.append(dict(date=self.date.date().toString("yyyy-MM-dd"), symbol=self.sym.currentText(), side=side,
                              strategy=self.strat.currentData(), entry=e, stop=s, exit=x, risk_pct=self.riskp.value(), r=r,
                              emotion=self.emotion.currentText(), notes=self.notes.text()))
        self.save(); self.render(); self.notes.clear()

    def delete(self):
        sel = sorted({i.row() for i in self.tbl.selectedItems()}, reverse=True)
        for r in sel:
            idx = self.tbl.item(r, 0).data(QtCore.Qt.ItemDataRole.UserRole)
            if idx is not None and 0 <= idx < len(self.rows):
                self.rows.pop(idx)
        self.save(); self.render()

    def export(self):
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, t("j_export"), "journal.csv", "CSV (*.csv)")
        if path:
            pd.DataFrame(self.rows).to_csv(path, index=False)

    def render(self):
        self.tbl.setSortingEnabled(False)
        self.tbl.setRowCount(0)
        for i, d in enumerate(self.rows):
            r = self.tbl.rowCount(); self.tbl.insertRow(r)
            it = cell(d["date"]); it.setData(QtCore.Qt.ItemDataRole.UserRole, i)
            self.tbl.setItem(r, 0, it)
            self.tbl.setItem(r, 1, cell(d["symbol"]))
            self.tbl.setItem(r, 2, cell(t("long") if d["side"] == 1 else t("short"), C["green"] if d["side"] == 1 else C["red"]))
            cls = S.REGISTRY.get(d["strategy"])
            self.tbl.setItem(r, 3, cell(strat_name(cls) if cls else d["strategy"]))
            self.tbl.setItem(r, 4, ncell(d["entry"], "{:,.5g}"))
            self.tbl.setItem(r, 5, ncell(d["stop"], "{:,.5g}"))
            self.tbl.setItem(r, 6, ncell(d["exit"], "{:,.5g}"))
            self.tbl.setItem(r, 7, ncell(d["risk_pct"], "{:.1f}%"))
            self.tbl.setItem(r, 8, ncell(d["r"], "{:+.2f}R", color_for(d["r"])))
            self.tbl.setItem(r, 9, cell(d["emotion"]))
            self.tbl.setItem(r, 10, cell(d["notes"]))
        self.tbl.setSortingEnabled(True)
        rs = np.array([d["r"] for d in self.rows]) if self.rows else np.array([])
        n = len(rs)
        wins = rs[rs > 0]; losses = rs[rs <= 0]
        self.t_n.set(n)
        self.t_wr.set(f"{len(wins) / n * 100:.0f}%" if n else "—")
        self.t_r.set(f"{rs.sum():+.2f}R" if n else "—", color_for(rs.sum()) if n else None)
        self.t_avg.set(f"{rs.mean():+.2f}R" if n else "—", color_for(rs.mean()) if n else None)
        pf = wins.sum() / -losses.sum() if len(losses) and losses.sum() < 0 else (float("inf") if len(wins) else 0)
        self.t_pf.set(f"{pf:.2f}" if pf != float("inf") else "∞", color_for(pf - 1) if n else None)
        self._steenbarger()

    def _steenbarger(self):
        """Steenbarger: performance metrics by setup / emotion / weekday → coach yourself with data."""
        from core.quant2 import steenbarger_metrics
        self.steen_tbl.setSortingEnabled(False); self.steen_tbl.setRowCount(0)
        if not self.rows:
            self.steen_txt.setText(t("j_steen_empty")); return
        df = pd.DataFrame(self.rows)
        df["pnl_r"] = df["r"]
        df["setup"] = df["strategy"]
        df["weekday"] = pd.to_datetime(df["date"], errors="coerce").dt.day_name().fillna("?")
        m = steenbarger_metrics(df)
        for grp, lab in (("setup", t("strategy")), ("emotion", t("emotion")), ("weekday", t("j_weekday"))):
            tb = m.get(grp)
            if tb is None:
                continue
            for k, row in tb.iterrows():
                cls = S.REGISTRY.get(k) if grp == "setup" else None
                i = self.steen_tbl.rowCount(); self.steen_tbl.insertRow(i)
                self.steen_tbl.setItem(i, 0, cell(f"{lab}: {strat_name(cls) if cls else k}"))
                self.steen_tbl.setItem(i, 1, ncell(int(row["n"]), "{}"))
                self.steen_tbl.setItem(i, 2, ncell(row["win_rate"], "{:.0f}%"))
                self.steen_tbl.setItem(i, 3, ncell(row["expectancy_r"], "{:+.2f}R", color_for(row["expectancy_r"])))
                self.steen_tbl.setItem(i, 4, ncell(row["total_r"], "{:+.1f}R", color_for(row["total_r"])))
        self.steen_tbl.setSortingEnabled(True)
        self.steen_txt.setText(t("j_steen_read").format(top=m.get("top10_share", 0), streak=m.get("worst_streak", 0)))


# ---------------------------------------------------------------- Settings
class SettingsPage(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(24, 20, 24, 20)
        c = Card(t("nav_settings"))
        f = QtWidgets.QFormLayout()
        self.lang = QtWidgets.QComboBox()
        self.lang.addItem("English", "en")
        self.lang.addItem("فارسی", "fa")
        self.lang.setCurrentIndex(0 if I18N.lang == "en" else 1)
        f.addRow(t("lang"), self.lang)
        self.clear = QtWidgets.QPushButton(t("cache_clear"))
        f.addRow(t("data_src"), self.clear)
        self.renderer = QtWidgets.QComboBox()
        self.renderer.addItem(t("chart_auto"), "auto"); self.renderer.addItem("pyqtgraph (GPU/QGraphicsView)", "pyqtgraph"); self.renderer.addItem(t("chart_compat"), "compat")
        try:
            cur_r = json.load(open(SETTINGS_PATH)).get("chart_renderer", "auto")
        except Exception:
            cur_r = "auto"
        self.renderer.setCurrentIndex(max(0, self.renderer.findData(cur_r)))
        self.renderer.setToolTip(t("chart_renderer_tip"))
        f.addRow(t("chart_renderer"), self.renderer)
        self.renderer.currentIndexChanged.connect(self._renderer)
        self.tz = QtWidgets.QComboBox(); self.tz.addItem(t("tz_local"), "local"); self.tz.addItem("UTC", "utc")
        try:
            self.tz.setCurrentIndex(max(0, self.tz.findData(json.load(open(SETTINGS_PATH)).get("chart_tz", "local"))))
        except Exception:
            pass
        self.tz.currentIndexChanged.connect(self._tz)
        f.addRow(t("time_display"), self.tz)
        self.succ_btn = QtWidgets.QPushButton("📊 " + t("succ_compute")); self.succ_btn.setToolTip(t("succ_compute_tip"))
        self.succ_btn.clicked.connect(self._precompute_success)
        self.succ_prog = QtWidgets.QProgressBar(); self.succ_prog.setRange(0, 100); self.succ_prog.setVisible(False)
        sb_ = QtWidgets.QHBoxLayout(); sb_.addWidget(self.succ_btn); sb_.addWidget(self.succ_prog, 1)
        f.addRow(t("success_rate"), sb_)
        # ---- Web & mobile (Phase 20): same engine served to phones/browsers on the LAN (or internet via tunnel)
        self.web_btn = QtWidgets.QPushButton("📱 " + t("web_start")); self.web_btn.setToolTip(t("web_tip"))
        self.web_btn.clicked.connect(self._toggle_web)
        self.web_url = QtWidgets.QLabel("—"); self.web_url.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)
        self.web_url.setOpenExternalLinks(True)
        self.web_qr = QtWidgets.QLabel(); self.web_qr.setFixedSize(132, 132); self.web_qr.setVisible(False)
        wb_ = QtWidgets.QHBoxLayout(); wb_.addWidget(self.web_btn); wb_.addWidget(self.web_url, 1); wb_.addWidget(self.web_qr)
        f.addRow(t("web_mobile"), wb_)
        try:
            from core import webapp as _W
            if _W.running():
                self._web_ui(_W.start()[0])
        except Exception:
            pass
        c.v.addLayout(f)
        v.addWidget(c)
        try:
            from .portfolio_page import AlertsPanel
            al = Card(t("alerts")); al.add(AlertsPanel()); v.addWidget(al)
        except Exception:
            pass
        about = Card(t("about"))
        lbl = QtWidgets.QLabel(f"<b>{t('app')}</b> {__import__('core.webapp', fromlist=['_version'])._version()}<br><br>{t('disclaimer')}")
        lbl.setWordWrap(True)
        about.add(lbl)
        v.addWidget(about)
        v.addStretch()
        self.clear.clicked.connect(self._clear)
        self.lang.currentIndexChanged.connect(self._lang)

    def _clear(self):
        n = 0
        for f in os.listdir(CACHE_DIR):
            if f.endswith(".parquet"):
                os.remove(os.path.join(CACHE_DIR, f)); n += 1
        QtWidgets.QMessageBox.information(self, "OK", f"{n} files removed")

    def _tz(self):
        try:
            cur = json.load(open(SETTINGS_PATH))
        except Exception:
            cur = {}
        cur["chart_tz"] = self.tz.currentData()
        try:
            json.dump(cur, open(SETTINGS_PATH, "w"), indent=1)
        except Exception:
            pass

    def _toggle_web(self):
        from core import webapp as W
        try:
            if W.running():
                W.stop(); self.web_btn.setText("📱 " + t("web_start")); self.web_url.setText("—"); self.web_qr.setVisible(False)
            else:
                url, port = W.start()
                self._web_ui(url)
        except Exception as e:
            self.web_url.setText(str(e)[:80])

    def _web_ui(self, url):
        self.web_btn.setText("⏹ " + t("web_stop"))
        self.web_url.setText(f"<a style='color:{C['accent2']}' href='{url}'>{url}</a><br><span style='color:{C['muted']}'>{t('web_hint')}</span>")
        try:
            from core.qr import qr_pixmap
            self.web_qr.setPixmap(qr_pixmap(url, 132)); self.web_qr.setVisible(True)
        except Exception:
            self.web_qr.setVisible(False)

    def _precompute_success(self):
        from core import success as SR
        self.succ_btn.setEnabled(False); self.succ_prog.setVisible(True); self.succ_prog.setValue(0)
        self._sw = Worker(lambda progress=None: SR.precompute(progress=progress))
        self._sw.progress.connect(lambda p, m: (self.succ_prog.setValue(p), self.succ_btn.setText(f"📊 {m}")))
        self._sw.done.connect(lambda *_: (self.succ_btn.setEnabled(True), self.succ_prog.setVisible(False), self.succ_btn.setText("📊 " + t("succ_compute") + " ✓")))
        self._sw.error.connect(lambda e: (self.succ_btn.setEnabled(True), self.succ_prog.setVisible(False), self.succ_btn.setText(e[:60])))
        self._sw.start()

    def _renderer(self):
        mode = self.renderer.currentData()
        try:
            cur = json.load(open(SETTINGS_PATH))
        except Exception:
            cur = {}
        cur["chart_renderer"] = mode
        json.dump(cur, open(SETTINGS_PATH, "w"), indent=1)
        # apply live to every chart in the app
        from .chart import ChartWidget
        ChartWidget._forced = None
        win = self.window()
        for w in win.findChildren(ChartWidget):
            try:
                w.switch("compat" if mode == "compat" else "pyqtgraph")
            except Exception:
                pass

    def _lang(self):
        lang = self.lang.currentData()
        try:
            cur = json.load(open(SETTINGS_PATH))
        except Exception:
            cur = {}
        cur["lang"] = lang
        json.dump(cur, open(SETTINGS_PATH, "w"), indent=1)
        QtWidgets.QMessageBox.information(self, "OK", "Restart the app to apply language.\nبرای اعمال زبان، برنامه را دوباره باز کنید.")


# ---------------------------------------------------------------- Indicator Encyclopedia
class IndicatorEncyclopedia(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        from core.indicators2 import catalog_groups
        from core.indicator_uses import full_catalog
        self.cat = full_catalog()
        h = QtWidgets.QHBoxLayout(self)
        h.setContentsMargins(0, 0, 0, 0)
        left = QtWidgets.QVBoxLayout()
        self.search = QtWidgets.QLineEdit()
        self.search.setPlaceholderText("🔍 RSI, MACD, …")
        left.addWidget(self.search)
        chips = QtWidgets.QGridLayout(); chips.setSpacing(6)
        self.group = QtWidgets.QButtonGroup(self); self.group.setExclusive(True)
        self.groups = [t("all")] + catalog_groups()
        for i, g in enumerate(self.groups):
            b = QtWidgets.QPushButton(g); b.setObjectName("chip"); b.setCheckable(True); b.setChecked(i == 0)
            self.group.addButton(b, i); chips.addWidget(b, i // 4, i % 4)
        left.addLayout(chips)
        self.list = QtWidgets.QListWidget()
        self.list.setStyleSheet(f"QListWidget{{background:{C['panel']}; border:1px solid {C['border']}; border-radius:8px;}} "
                                f"QListWidget::item{{padding:8px; border-bottom:1px solid {C['border']};}} "
                                f"QListWidget::item:selected{{background:{C['accent']}33; color:white;}}")
        left.addWidget(self.list, 1)
        lw = QtWidgets.QWidget(); lw.setLayout(left); lw.setMaximumWidth(400)
        h.addWidget(lw)
        self.detail = QtWidgets.QTextBrowser()
        self.detail.setStyleSheet(f"QTextBrowser{{background:{C['panel']}; border:1px solid {C['border']}; border-radius:10px; padding:18px; font-size:14px;}}")
        h.addWidget(self.detail, 1)
        self.search.textChanged.connect(self._fill)
        self.group.idClicked.connect(lambda _: self._fill())
        self.list.currentItemChanged.connect(self._show)
        self._fill()
        if self.list.count():
            self.list.setCurrentRow(0)

    def _fill(self):
        q = self.search.text().lower()
        g = self.groups[self.group.checkedId()] if self.group.checkedId() > 0 else None
        self.list.clear()
        fa = I18N.lang == "fa"
        for d in self.cat:
            if g and d["group"] != g:
                continue
            if q and q not in (d["name_en"] + d["name_fa"] + d["key"]).lower():
                continue
            it = QtWidgets.QListWidgetItem(f"{d['name_fa'] if fa else d['name_en']}\n{d['group']}")
            it.setData(QtCore.Qt.ItemDataRole.UserRole, d["key"])
            self.list.addItem(it)

    @staticmethod
    def _sheet(d, sfx):
        if "uses_" + sfx not in d:
            return ""
        from html import escape as esc
        def ul(items, color=None):
            st = f" style='color:{color}'" if color else ""
            return "<ul style='line-height:1.7'>" + "".join(f"<li{st}>{esc(x)}</li>" for x in items) + "</ul>"
        return (f"<p><b>{t('ind_params')}:</b> <code style='color:{C['accent2']}'>{esc(str(d.get('params', '—')))}</code></p>"
                f"<h3 style='color:{C['accent2']}'>{t('ind_uses')}</h3>{ul(d['uses_' + sfx])}"
                f"<h3 style='color:{C['accent2']}'>{t('ind_signals')}</h3>{ul(d['signals_' + sfx])}"
                f"<h3 style='color:{C['red']}'>{t('ind_pitfalls')}</h3>{ul(d['pitfalls_' + sfx], C['muted'])}"
                f"<h3 style='color:{C['accent2']}'>{t('ind_combos')}</h3><p style='color:{C['muted']}'>{esc(' · '.join(d['combos_' + sfx]))}</p>")

    def _show(self, cur, prev=None):
        if not cur:
            return
        key = cur.data(QtCore.Qt.ItemDataRole.UserRole)
        d = next(x for x in self.cat if x["key"] == key)
        fa = I18N.lang == "fa"
        sfx = "fa" if fa else "en"
        other = d["name_en"] if fa else d["name_fa"]
        # which strategies use it
        users = [strat_name(c) for c in S.ALL_STRATEGIES if key.split("_")[0] in (c.id + " ".join(c.rules_en)).lower()][:8]
        used = "، ".join(users) if fa else ", ".join(users)
        self.detail.setHtml(f"""
        <div dir='{'rtl' if fa else 'ltr'}'>
        <h1 style='margin:0;color:white'>{d['name_' + sfx]}</h1>
        <div style='color:{C['muted']};font-size:13px'>{other}</div>
        <p><span style='background:{C['accent']}33;color:{C['accent2']};padding:3px 10px;border-radius:10px'>{d['group']}</span></p>
        <h3 style='color:{C['accent2']}'>{t('ind_how')}</h3><p style='line-height:1.6'>{html.escape(d['how_' + sfx])}</p>
        <h3 style='color:{C['accent2']}'>{t('ind_read')}</h3><p style='line-height:1.7'>{html.escape(d['read_' + sfx])}</p>
        {self._sheet(d, sfx)}
        <h3 style='color:{C['accent2']}'>{t('ind_used')}</h3><p style='color:{C['muted']}'>{used or '—'}</p>
        <p style='color:{C['muted']};font-size:12px'>{t('ind_ml_note')}</p>
        </div>""")



# ---------------------------------------------------------------- Library (books & bots curriculum)
class LibraryTab(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        from core.library import BOOKS, BOTS
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(12, 12, 12, 12)
        fa = I18N.lang == "fa"
        sub = QtWidgets.QLabel(t("lib_sub")); sub.setObjectName("subtitle"); sub.setWordWrap(True); v.addWidget(sub)
        self.q = QtWidgets.QLineEdit(); self.q.setPlaceholderText(t("search")); self.q.textChanged.connect(self._filter); v.addWidget(self.q)
        self.tbl = make_table([t("lib_title_c"), t("lib_author"), t("lib_group"), t("lib_lesson"), t("lib_where")])
        self.tbl.setSortingEnabled(False)
        self.rows = []
        for title, author, grp, en, fa_, where in BOOKS:
            self.rows.append((title, author, grp, fa_ if fa else en, where))
        for name, grp, what, where in BOTS:
            self.rows.append((name, "🤖 bot", grp, what, where))
        self._fill(self.rows)
        self.tbl.setWordWrap(True)
        v.addWidget(self.tbl, 1)

    def _fill(self, rows):
        self.tbl.setRowCount(0)
        for title, author, grp, lesson, where in rows:
            r = self.tbl.rowCount(); self.tbl.insertRow(r)
            self.tbl.setItem(r, 0, cell(title)); self.tbl.setItem(r, 1, cell(author, C["muted"]))
            self.tbl.setItem(r, 2, cell(grp, C["accent2"])); self.tbl.setItem(r, 3, cell(lesson)); self.tbl.setItem(r, 4, cell(where, C["green"]))
        self.tbl.resizeColumnsToContents(); self.tbl.setColumnWidth(3, 520); self.tbl.resizeRowsToContents()

    def _filter(self, q):
        q = q.lower()
        self._fill([r for r in self.rows if q in " ".join(r).lower()])
