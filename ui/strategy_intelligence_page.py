"""Strategy Intelligence Page - هوش استراتژی - Auto-select best strategy per chart/timeframe"""

import time
from PyQt6 import QtCore, QtGui, QtWidgets
from .theme import C, t, I18N
from .widgets import Card, StatTile, make_table, cell, ncell, Worker, color_for, Badge
from .chart import ChartWidget
from core.data import UNIVERSE, TIMEFRAMES, get_ohlcv, generate_synthetic


class StrategyIntelligencePage(QtWidgets.QWidget):
    """🧠 هوش استراتژی - Automatically selects best strategy for chart/timeframe"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(16, 12, 16, 12)
        v.setSpacing(12)
        
        # Title
        title = QtWidgets.QLabel("🧠 " + t("nav_intelligence") if hasattr(t, '__call__') else "🧠 هوش استراتژی - Strategy Intelligence")
        title.setObjectName("title")
        v.addWidget(title)
        
        subtitle = QtWidgets.QLabel(t("intelligence_sub") if "intelligence_sub" in str(t("intelligence_sub")) or True else "هوش مصنوعی بهترین استراتژی را برای هر چارت و تایم‌فریم انتخاب می‌کند")
        subtitle.setObjectName("subtitle")
        subtitle.setWordWrap(True)
        v.addWidget(subtitle)
        
        # Top bar - symbol/timeframe
        top = QtWidgets.QHBoxLayout()
        top.setSpacing(10)
        
        self.sym_combo = QtWidgets.QComboBox()
        self.sym_combo.setMinimumWidth(180)
        self.sym_combo.setEditable(True)
        for cat, syms in UNIVERSE.items():
            for s in syms:
                self.sym_combo.addItem(f"{s} ({cat})", s)
        self.sym_combo.setCurrentText("BTC/USDT")
        
        self.tf_combo = QtWidgets.QComboBox()
        self.tf_combo.addItems(TIMEFRAMES)
        self.tf_combo.setCurrentText("1h")
        
        self.analyze_btn = QtWidgets.QPushButton("🧠 تحلیل هوشمند - Analyze")
        self.analyze_btn.setObjectName("primary")
        self.analyze_btn.setMinimumHeight(36)
        
        self.auto_btn = QtWidgets.QCheckBox("🔄 خودکار - Auto (هر بار چارت عوض شد)")
        self.auto_btn.setChecked(False)
        
        top.addWidget(QtWidgets.QLabel("نماد / Symbol:"))
        top.addWidget(self.sym_combo)
        top.addWidget(QtWidgets.QLabel("تایم‌فریم / Timeframe:"))
        top.addWidget(self.tf_combo)
        top.addWidget(self.analyze_btn)
        top.addWidget(self.auto_btn)
        top.addStretch()
        
        v.addLayout(top)
        
        # Market analysis tiles
        tiles_layout = QtWidgets.QHBoxLayout()
        tiles_layout.setSpacing(8)
        self.t_regime = StatTile("رژیم بازار / Regime")
        self.t_trend = StatTile("قدرت روند / Trend")
        self.t_vol = StatTile("نوسان / Volatility")
        self.t_adx = StatTile("ADX")
        self.t_rsi = StatTile("RSI")
        self.t_conf = StatTile("اطمینان / Confidence")
        for tile in (self.t_regime, self.t_trend, self.t_vol, self.t_adx, self.t_rsi, self.t_conf):
            tiles_layout.addWidget(tile)
        v.addLayout(tiles_layout)
        
        # Main split: left chart + right intelligence
        split = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        
        # Left: chart + best strategy card
        left = QtWidgets.QWidget()
        left_v = QtWidgets.QVBoxLayout(left)
        left_v.setContentsMargins(0, 0, 0, 0)
        left_v.setSpacing(10)
        
        # Best strategy card
        self.best_card = Card("✅ بهترین استراتژی / Best Strategy")
        self.best_label = QtWidgets.QLabel("روی تحلیل هوشمند کلیک کنید\nClick Analyze")
        self.best_label.setWordWrap(True)
        self.best_label.setTextFormat(QtCore.Qt.TextFormat.RichText)
        self.best_label.setStyleSheet(f"font-size: 14px; line-height: 1.5;")
        self.best_card.add(self.best_label)
        
        self.apply_btn = QtWidgets.QPushButton("📈 اعمال به چارت / Apply to Chart")
        self.apply_btn.setObjectName("primary")
        self.apply_btn.setEnabled(False)
        self.best_card.add(self.apply_btn)
        
        left_v.addWidget(self.best_card)
        
        # Chart
        self.chart = ChartWidget()
        self.chart.setMinimumHeight(400)
        left_v.addWidget(self.chart, 1)
        
        split.addWidget(left)
        
        # Right: Top 5 + details + reasoning
        right = QtWidgets.QWidget()
        right_v = QtWidgets.QVBoxLayout(right)
        right_v.setContentsMargins(0, 0, 0, 0)
        right_v.setSpacing(10)
        
        # Reasoning card
        self.reason_card = Card("🧩 دلیل انتخاب / Reasoning")
        self.reason_text = QtWidgets.QTextBrowser()
        self.reason_text.setMaximumHeight(180)
        self.reason_text.setStyleSheet(f"background: {C['bg']}; border: none;")
        self.reason_card.add(self.reason_text)
        right_v.addWidget(self.reason_card)
        
        # Top 5 table
        self.top_card = Card("🔝 5 استراتژی برتر / Top 5 Strategies")
        self.top_table = make_table(["#", "استراتژی / Strategy", "دسته", "امتیاز", "Grade", "WR", "PF", "اطمینان"])
        self.top_table.setMinimumHeight(250)
        self.top_table.itemDoubleClicked.connect(self._on_top_double_click)
        self.top_card.add(self.top_table)
        right_v.addWidget(self.top_card)
        
        # Stats card
        self.stats_card = Card("📊 آمار بک‌تست / Backtest Stats")
        self.stats_label = QtWidgets.QLabel("—")
        self.stats_label.setWordWrap(True)
        self.stats_label.setTextFormat(QtCore.Qt.TextFormat.RichText)
        self.stats_card.add(self.stats_label)
        right_v.addWidget(self.stats_card)
        
        # All strategies table (collapsible)
        self.all_card = Card("📚 همه 196 استراتژی / All 196 Strategies (sorted by score)")
        self.all_table = make_table(["امتیاز", "استراتژی", "دسته", "تایم‌فریم", "Grade", "WR", "دلیل"])
        self.all_table.setMinimumHeight(200)
        self.all_table.itemDoubleClicked.connect(self._on_all_double_click)
        self.all_card.add(self.all_table)
        right_v.addWidget(self.all_card, 1)
        
        split.addWidget(right)
        split.setSizes([700, 500])
        
        v.addWidget(split, 1)
        
        # Status
        self.status_label = QtWidgets.QLabel("")
        self.status_label.setObjectName("subtitle")
        v.addWidget(self.status_label)
        
        # Connections
        self.analyze_btn.clicked.connect(self.analyze)
        self.apply_btn.clicked.connect(self._apply_to_chart)
        self.sym_combo.currentTextChanged.connect(self._on_auto)
        self.tf_combo.currentTextChanged.connect(self._on_auto)
        
        # State
        self.current_result = None
        self.current_df = None
        self.current_bt = None
        
        # Initial analyze
        QtCore.QTimer.singleShot(1000, self.analyze)
    
    def _on_auto(self):
        if self.auto_btn.isChecked():
            self.analyze()
    
    def symbol(self):
        data = self.sym_combo.currentData()
        if data:
            return data
        txt = self.sym_combo.currentText().strip()
        # Extract symbol from "BTC/USDT (Crypto)" format
        if "(" in txt:
            txt = txt.split("(")[0].strip()
        return txt or "BTC/USDT"
    
    def timeframe(self):
        return self.tf_combo.currentText() or "1h"
    
    def analyze(self):
        sym = self.symbol()
        tf = self.timeframe()
        
        self.analyze_btn.setEnabled(False)
        self.analyze_btn.setText("⏳ در حال تحلیل... Analyzing...")
        self.status_label.setText(f"🧠 در حال تحلیل {sym} {tf} - {len(UNIVERSE)} categories, 196 strategies...")
        
        def work():
            from core.strategy_intelligence import select_best_strategy, auto_analyze
            # Get data
            try:
                df, ok = get_ohlcv(sym, tf), True
            except Exception:
                df = generate_synthetic(seed=abs(hash(sym+tf)) % 10000)
                ok = False
            
            # Intelligence
            from core.strategy_intelligence import select_best_strategy
            intel = select_best_strategy(sym, tf, df)
            
            # Auto backtest with best
            try:
                import strategies as S
                from core.backtest import run_backtest
                sid = intel.best.strategy_id
                strat = S.get(sid)
                res = strat.run(df)
                bt = run_backtest(df, res)
                return df, ok, intel, res, bt
            except Exception as e:
                return df, ok, intel, None, None
        
        self.worker = Worker(work)
        self.worker.done.connect(self._show_result)
        self.worker.error.connect(lambda e: (
            self.analyze_btn.setEnabled(True),
            self.analyze_btn.setText("🧠 تحلیل هوشمند - Analyze"),
            self.status_label.setText(f"❌ خطا: {e}"),
            QtWidgets.QMessageBox.warning(self, "Error", str(e))
        ))
        self.worker.start()
    
    def _show_result(self, data):
        df, ok, intel, res, bt = data
        self.current_df = df
        self.current_result = intel
        self.current_bt = bt
        
        self.analyze_btn.setEnabled(True)
        self.analyze_btn.setText("🧠 تحلیل هوشمند - Analyze")
        
        # Market tiles
        m = intel.market
        self.t_regime.set(f"{m.regime_fa}\n{m.regime_en}", C["accent2"] if m.confidence > 70 else C["yellow"])
        self.t_trend.set(f"{m.trend_strength:.0f}% - {m.ema_trend}", C["green"] if "bull" in m.ema_trend else (C["red"] if "bear" in m.ema_trend else C["yellow"]))
        self.t_vol.set(f"{m.volatility_level:.0f}% (x{m.volatility_vs_median:.1f})", C["red"] if m.volatility_level > 70 else C["green"])
        self.t_adx.set(f"{m.adx:.0f}", C["green"] if m.adx > 25 else C["yellow"])
        self.t_rsi.set(f"{m.rsi:.0f}", C["red"] if m.rsi > 70 else (C["green"] if m.rsi < 30 else C["muted"]))
        self.t_conf.set(f"{m.confidence:.0f}%", C["green"] if m.confidence > 70 else C["yellow"])
        
        # Best strategy card
        best = intel.best
        if best:
            # Color based on score
            score_color = C["green"] if best.total_score >= 75 else (C["yellow"] if best.total_score >= 60 else C["muted"])
            
            self.best_label.setText(
                f"<div style='font-size: 16px;'>"
                f"<b style='color: {score_color}; font-size: 18px;'>{best.strategy_name_fa}</b><br>"
                f"<span style='color: {C['muted']};'>{best.strategy_name}</span><br><br>"
                f"<b>شناسه:</b> <code>{best.strategy_id}</code> | "
                f"<b>دسته:</b> {best.category} | "
                f"<b>Grade:</b> <span style='color: {score_color};'>{best.grade}</span><br>"
                f"<b>امتیاز:</b> <span style='color: {score_color}; font-size: 18px;'>{best.total_score:.0f}/100</span> | "
                f"<b>اطمینان:</b> {best.confidence:.0f}%<br>"
                f"<b>WR:</b> {best.win_rate:.0f}% | <b>PF:</b> {best.profit_factor:.1f} | {best.success_label}<br><br>"
                f"<b>TF Match:</b> {best.breakdown['tf_match']:.0f} | "
                f"<b>Regime Match:</b> {best.breakdown['regime_match']:.0f} | "
                f"<b>Historical:</b> {best.breakdown['historical']:.0f}"
                f"</div>"
            )
            self.apply_btn.setEnabled(True)
            
            # Reasoning
            lang = "fa"  # Could use I18N
            reasoning = best.reasoning_fa if lang == "fa" else best.reasoning_en
            breakdown = best.breakdown
            self.reason_text.setHtml(
                f"<div style='line-height: 1.6; color: {C['text']};'>"
                f"<b>🧩 دلیل انتخاب:</b><br>{reasoning}<br><br>"
                f"<b>📊 جزئیات امتیاز:</b><br>"
                f"• تایم‌فریم: {breakdown['tf_match']:.0f}/100<br>"
                f"• تطابق رژیم بازار: {breakdown['regime_match']:.0f}/100<br>"
                f"• عملکرد تاریخی: {breakdown['historical']:.0f}/100<br>"
                f"• بونوس موفقیت: +{breakdown['success_bonus']:.0f}<br>"
                f"• بونوس PF: +{breakdown['pf_bonus']:.0f}<br>"
                f"• اثبات شده: +{breakdown['proven_bonus']:.0f}<br>"
                f"<br><b>بازار:</b> {m.regime_fa} - قدرت روند {m.trend_strength:.0f}% - ADX {m.adx:.0f} - RSI {m.rsi:.0f}"
                f"</div>"
            )
        else:
            self.best_label.setText("❌ استراتژی یافت نشد")
            self.reason_text.setPlainText("—")
            self.apply_btn.setEnabled(False)
        
        # Top 5 table
        self.top_table.setSortingEnabled(False)
        self.top_table.setRowCount(0)
        for idx, s in enumerate(intel.top_5, 1):
            r = self.top_table.rowCount()
            self.top_table.insertRow(r)
            self.top_table.setItem(r, 0, cell(str(idx)))
            self.top_table.setItem(r, 1, cell(f"{s.strategy_name_fa}\n{s.strategy_id}", C["text"] if idx==1 else C["muted"]))
            self.top_table.setItem(r, 2, cell(s.category, C["accent2"]))
            score_color = C["green"] if s.total_score >= 75 else (C["yellow"] if s.total_score >= 60 else C["muted"])
            self.top_table.setItem(r, 3, cell(f"{s.total_score:.0f}", score_color))
            grade_color = { "A": C["green"], "B": C["accent2"], "C": C["yellow"] }.get(s.grade, C["red"])
            self.top_table.setItem(r, 4, cell(s.grade, grade_color))
            self.top_table.setItem(r, 5, cell(f"{s.win_rate:.0f}%" if s.win_rate else "—", C["green"] if s.win_rate and s.win_rate>=65 else C["muted"]))
            self.top_table.setItem(r, 6, cell(f"{s.profit_factor:.1f}" if s.profit_factor else "—", C["green"] if s.profit_factor and s.profit_factor>=1.5 else C["muted"]))
            self.top_table.setItem(r, 7, cell(f"{s.confidence:.0f}%"))
        self.top_table.setSortingEnabled(True)
        
        # All strategies table
        self.all_table.setSortingEnabled(False)
        self.all_table.setRowCount(0)
        for s in intel.all_scored[:30]:  # Show top 30 for performance
            r = self.all_table.rowCount()
            self.all_table.insertRow(r)
            self.all_table.setItem(r, 0, cell(f"{s.total_score:.0f}", C["green"] if s.total_score>=70 else C["muted"]))
            self.all_table.setItem(r, 1, cell(f"{s.strategy_name_fa} ({s.strategy_id})"))
            self.all_table.setItem(r, 2, cell(s.category, C["accent2"]))
            # Find strategy timeframes
            try:
                import strategies as S
                tf_str = S.REGISTRY[s.strategy_id].timeframes
            except:
                tf_str = "any"
            self.all_table.setItem(r, 3, cell(tf_str, C["muted"]))
            self.all_table.setItem(r, 4, cell(s.grade))
            self.all_table.setItem(r, 5, cell(f"{s.win_rate:.0f}%" if s.win_rate else "—"))
            self.all_table.setItem(r, 6, cell(s.reasoning_fa[:80] + "..." if len(s.reasoning_fa) > 80 else s.reasoning_fa, C["muted"]))
        self.all_table.setSortingEnabled(True)
        self.all_table.sortItems(0, QtCore.Qt.SortOrder.DescendingOrder)
        
        # Chart
        if df is not None and res is not None and bt is not None:
            try:
                title = f"{intel.symbol} · {intel.timeframe} · {best.strategy_name_fa} (Score {best.total_score:.0f}) - {m.regime_fa}"
                self.chart.set_data(df, res, trades=bt.trades, title=title)
                
                # Stats
                st = bt.stats
                self.stats_label.setText(
                    f"<b>WR:</b> {st['win_rate']:.0f}% | "
                    f"<b>PF:</b> {st['profit_factor']:.2f} | "
                    f"<b>Trades:</b> {st['trades']} | "
                    f"<b>Return:</b> <span style='color: {C['green'] if st['return_pct']>0 else C['red']};'>{st['return_pct']:+.1f}%</span> | "
                    f"<b>DD:</b> {st['max_dd_pct']:.1f}% | "
                    f"<b>Sharpe:</b> {st['sharpe']:.2f}<br>"
                    f"<span style='color: {C['muted']};'>Grade {st.get('grade','?')} | "
                    f"WR [{st.get('wr_lo',0):.0f}-{st.get('wr_hi',100):.0f}%] | "
                    f"PF [{st.get('pf_lo',0):.1f}-{st.get('pf_hi',0):.1f}]</span>"
                )
            except Exception as e:
                self.stats_label.setText(f"Chart error: {e}")
        
        self.status_label.setText(f"✅ تحلیل {intel.symbol} {intel.timeframe} کامل شد - بهترین: {best.strategy_id} - {intel.analysis_time_ms}ms - {m.regime_fa}")
    
    def _on_top_double_click(self, item):
        row = item.row()
        if row < 0 or row >= len(self.current_result.top_5):
            return
        s = self.current_result.top_5[row]
        self._apply_strategy(s.strategy_id)
    
    def _on_all_double_click(self, item):
        row = item.row()
        # Get strategy id from second column text
        txt = self.all_table.item(row, 1).text()
        # Extract id from "Name (id)" format
        if "(" in txt and ")" in txt:
            sid = txt.split("(")[-1].split(")")[0].strip()
            self._apply_strategy(sid)
    
    def _apply_strategy(self, sid: str):
        """Apply strategy to chart page"""
        try:
            sym = self.symbol()
            tf = self.timeframe()
            self.window().open_chart(sym, tf, sid)
            self.status_label.setText(f"📈 {sid} اعمال شد به چارت {sym} {tf}")
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Error", str(e))
    
    def _apply_to_chart(self):
        if self.current_result and self.current_result.best:
            self._apply_strategy(self.current_result.best.strategy_id)
