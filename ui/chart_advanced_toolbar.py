"""Advanced TradingView-style toolbar for chart (Phase 26)"""
from PyQt6 import QtCore, QtGui, QtWidgets
from .theme import C, t

class TradingViewToolbar(QtWidgets.QWidget):
    """TradingView-like top toolbar: timeframes, chart types, indicators, tools, settings"""
    timeframeChanged = QtCore.pyqtSignal(str)
    chartTypeChanged = QtCore.pyqtSignal(str)
    indicatorRequested = QtCore.pyqtSignal()
    screenshotRequested = QtCore.pyqtSignal()
    settingsRequested = QtCore.pyqtSignal()
    fullscreenToggled = QtCore.pyqtSignal(bool)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("tv_toolbar")
        self.setStyleSheet(f"""
            QWidget#tv_toolbar {{ background: {C['panel']}; border-bottom: 1px solid {C['border']}; }}
            QToolButton {{ background: transparent; border: 1px solid transparent; border-radius: 6px; padding: 4px 8px; color: {C['text']}; font-size: 12px; }}
            QToolButton:hover {{ background: {C['panel2']}; border-color: {C['border']}; }}
            QToolButton:checked {{ background: {C['accent']}; color: white; border-color: {C['accent']}; }}
            QPushButton {{ background: {C['panel2']}; border: 1px solid {C['border']}; border-radius: 6px; padding: 5px 10px; color: {C['text']}; font-size: 12px; }}
            QPushButton:hover {{ border-color: {C['accent']}; }}
            QComboBox {{ background: {C['panel2']}; border: 1px solid {C['border']}; border-radius: 6px; padding: 4px 8px; }}
        """)
        self._build()
    
    def _build(self):
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(4)
        
        # Timeframes group
        tf_group = QtWidgets.QButtonGroup(self)
        tf_group.setExclusive(True)
        tf_layout = QtWidgets.QHBoxLayout()
        tf_layout.setSpacing(2)
        
        timeframes = ["1m","3m","5m","15m","30m","1h","2h","4h","6h","12h","1d","1wk","1mo"]
        for tf in timeframes:
            btn = QtWidgets.QToolButton()
            btn.setText(tf)
            btn.setCheckable(True)
            btn.setProperty("tf", tf)
            if tf == "1h":
                btn.setChecked(True)
            btn.clicked.connect(lambda _, tf=tf: self.timeframeChanged.emit(tf))
            tf_group.addButton(btn)
            tf_layout.addWidget(btn)
        
        tf_container = QtWidgets.QWidget()
        tf_container.setLayout(tf_layout)
        layout.addWidget(tf_container)
        
        # Separator
        sep1 = QtWidgets.QFrame()
        sep1.setFrameShape(QtWidgets.QFrame.Shape.VLine)
        sep1.setStyleSheet(f"color: {C['border']};")
        layout.addWidget(sep1)
        
        # Chart types
        chart_group = QtWidgets.QButtonGroup(self)
        chart_group.setExclusive(True)
        chart_layout = QtWidgets.QHBoxLayout()
        chart_layout.setSpacing(2)
        
        chart_types = [
            ("candle", "🕯 Candle", "Candlestick"),
            ("line", "〰 Line", "Line"),
            ("area", "⛰ Area", "Area"),
            ("heikin", "HA Heikin Ashi", "Heikin Ashi"),
            ("renko", "▭ Renko", "Renko"),
        ]
        
        for ctype, label, tooltip in chart_types:
            btn = QtWidgets.QToolButton()
            btn.setText(label)
            btn.setToolTip(tooltip)
            btn.setCheckable(True)
            if ctype == "candle":
                btn.setChecked(True)
            btn.clicked.connect(lambda _, ct=ctype: self.chartTypeChanged.emit(ct))
            chart_group.addButton(btn)
            chart_layout.addWidget(btn)
        
        chart_container = QtWidgets.QWidget()
        chart_container.setLayout(chart_layout)
        layout.addWidget(chart_container)
        
        sep2 = QtWidgets.QFrame()
        sep2.setFrameShape(QtWidgets.QFrame.Shape.VLine)
        layout.addWidget(sep2)
        
        # Indicators
        ind_btn = QtWidgets.QPushButton("ƒx Indicators")
        ind_btn.setToolTip("Add indicators (73 available)")
        ind_btn.clicked.connect(self.indicatorRequested.emit)
        layout.addWidget(ind_btn)
        
        # Compare
        compare_btn = QtWidgets.QPushButton("⊕ Compare")
        compare_btn.setToolTip("Compare symbols")
        layout.addWidget(compare_btn)
        
        sep3 = QtWidgets.QFrame()
        sep3.setFrameShape(QtWidgets.QFrame.Shape.VLine)
        layout.addWidget(sep3)
        
        # Screenshot, Fullscreen, Settings
        shot_btn = QtWidgets.QToolButton()
        shot_btn.setText("📷")
        shot_btn.setToolTip("Take screenshot")
        shot_btn.clicked.connect(self.screenshotRequested.emit)
        layout.addWidget(shot_btn)
        
        self.fullscreen_btn = QtWidgets.QToolButton()
        self.fullscreen_btn.setText("⛶")
        self.fullscreen_btn.setToolTip("Fullscreen")
        self.fullscreen_btn.setCheckable(True)
        self.fullscreen_btn.toggled.connect(self.fullscreenToggled.emit)
        layout.addWidget(self.fullscreen_btn)
        
        settings_btn = QtWidgets.QToolButton()
        settings_btn.setText("⚙")
        settings_btn.setToolTip("Chart settings")
        settings_btn.clicked.connect(self.settingsRequested.emit)
        layout.addWidget(settings_btn)
        
        layout.addStretch()
        
        # Price info
        self.price_label = QtWidgets.QLabel("")
        self.price_label.setStyleSheet(f"color: {C['muted']}; font-family: monospace; font-size: 11px;")
        layout.addWidget(self.price_label)
    
    def set_price_info(self, text):
        self.price_label.setText(text)
    
    def set_timeframe(self, tf):
        for btn in self.findChildren(QtWidgets.QToolButton):
            if btn.property("tf") == tf:
                btn.setChecked(True)
                break

class ChartStatusBar(QtWidgets.QWidget):
    """Bottom status bar like TradingView: OHLC, indicators values, etc."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(24)
        self.setStyleSheet(f"background: {C['panel']}; border-top: 1px solid {C['border']};")
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(8, 2, 8, 2)
        layout.setSpacing(12)
        
        self.ohlc_label = QtWidgets.QLabel("")
        self.ohlc_label.setStyleSheet(f"color: {C['text']}; font-family: monospace; font-size: 11px;")
        layout.addWidget(self.ohlc_label)
        
        layout.addStretch()
        
        self.info_label = QtWidgets.QLabel("")
        self.info_label.setStyleSheet(f"color: {C['muted']}; font-size: 11px;")
        layout.addWidget(self.info_label)
    
    def set_ohlc(self, o,h,l,c, vol=None, change=None):
        if o is None:
            self.ohlc_label.setText("")
            return
        
        chg_str = ""
        if change is not None:
            color = C['green'] if change>=0 else C['red']
            chg_str = f"<span style='color:{color}'>{change:+.2f}%</span>"
        
        vol_str = f" Vol {vol:,.0f}" if vol else ""
        
        text = f"<span style='color:{C['muted']}'>O</span> {o:,.6g} <span style='color:{C['muted']}'>H</span> {h:,.6g} <span style='color:{C['muted']}'>L</span> {l:,.6g} <span style='color:{C['muted']}'>C</span> {c:,.6g} {chg_str}<span style='color:{C['muted']}'>{vol_str}</span>"
        self.ohlc_label.setText(text)
    
    def set_info(self, text):
        self.info_label.setText(text)

class AdvancedChartWidget(QtWidgets.QWidget):
    """Wrapper combining ChartWidget + TradingView toolbar + status bar"""
    timeframeChanged = QtCore.pyqtSignal(str)
    chartTypeChanged = QtCore.pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        from .chart import ChartWidget
        
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)
        layout.setSpacing(0)
        
        # Toolbar
        self.toolbar = TradingViewToolbar()
        self.toolbar.timeframeChanged.connect(self.timeframeChanged.emit)
        self.toolbar.chartTypeChanged.connect(self.chartTypeChanged.emit)
        self.toolbar.indicatorRequested.connect(self._on_indicator)
        self.toolbar.screenshotRequested.connect(self._on_screenshot)
        self.toolbar.fullscreenToggled.connect(self._on_fullscreen)
        layout.addWidget(self.toolbar)
        
        # Chart
        self.chart = ChartWidget()
        self.chart.barHovered.connect(self._on_hover)
        layout.addWidget(self.chart, 1)
        
        # Status bar
        self.statusbar = ChartStatusBar()
        layout.addWidget(self.statusbar)
        
        self._chart_type = "candle"
    
    def _on_hover(self, i):
        df = self.chart.df
        if df is None or not (0 <= i < len(df)):
            return
        
        r = df.iloc[i]
        prev = df.iloc[i-1] if i>0 else r
        chg = (r.close/prev.close-1)*100 if prev.close else 0
        
        self.statusbar.set_ohlc(r.open, r.high, r.low, r.close, r.volume, chg)
        self.toolbar.set_price_info(f"{r.close:,.6g} {chg:+.2f}%")
    
    def _on_indicator(self):
        from .chart_tools import IndicatorDialog
        dlg = IndicatorDialog(self)
        if dlg.exec() and dlg.result_value:
            key, params = dlg.result_value
            self.chart.add_indicator(key, params)
    
    def _on_screenshot(self):
        # Grab chart pixmap
        pixmap = self.chart.grab()
        # Save dialog
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save Screenshot", f"chart_{QtCore.QDateTime.currentDateTime().toString('yyyyMMdd_hhmmss')}.png", "PNG (*.png)")
        if path:
            pixmap.save(path)
    
    def _on_fullscreen(self, on):
        if on:
            self.chart.setParent(None)
            self.chart.showFullScreen()
            # Add exit fullscreen button
            exit_btn = QtWidgets.QPushButton("Exit Fullscreen (Esc)", self.chart)
            exit_btn.setStyleSheet(f"background: {C['panel']}; color: white; padding: 6px 12px; border-radius: 6px;")
            exit_btn.move(10,10)
            exit_btn.show()
            exit_btn.clicked.connect(lambda: self._exit_fullscreen(exit_btn))
        else:
            self._exit_fullscreen(None)
    
    def _exit_fullscreen(self, btn):
        if btn:
            btn.deleteLater()
        self.chart.showNormal()
        # Re-add to layout
        lay = self.layout()
        lay.insertWidget(1, self.chart)
        self.toolbar.fullscreen_btn.setChecked(False)
    
    def set_data(self, df, result=None, trades=None, title="", keep_view=False):
        self.chart.set_data(df, result, trades, title, keep_view)
    
    def set_tool(self, name):
        self.chart.set_tool(name)
    
    @property
    def df(self):
        return self.chart.df
    
    def __getattr__(self, name):
        # Delegate to chart widget
        return getattr(self.chart, name)
