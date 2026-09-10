"""Advanced TradingView Chart Page - Desktop (Phase 26)"""
from PyQt6 import QtCore, QtGui, QtWidgets
from .theme import C, t
from .chart import ChartWidget
from .chart_advanced_toolbar import TradingViewToolbar, ChartStatusBar
import os, json, time, numpy as np, pandas as pd

from core.data import UNIVERSE, TIMEFRAMES, get_ohlcv, generate_synthetic
from core.backtest import run_backtest
import strategies as S

def all_symbols():
    out=[]
    for cat,d in UNIVERSE.items():
        for s in d:
            out.append((cat,s))
    return out

class TradingViewAdvancedPage(QtWidgets.QWidget):
    """Full TradingView-like advanced chart page"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(0,0,0,0)
        v.setSpacing(0)
        
        # Top bar: Symbol + TF + Strategy
        top = QtWidgets.QHBoxLayout()
        top.setContentsMargins(10,6,10,6)
        top.setSpacing(8)
        
        self.sym = QtWidgets.QComboBox()
        self.sym.setMinimumWidth(160)
        self.sym.setEditable(True)
        for cat,d in UNIVERSE.items():
            for s in d:
                self.sym.addItem(f"{s}", s)
        self.sym.setCurrentIndex(0)
        
        self.tf = QtWidgets.QComboBox()
        self.tf.addItems(TIMEFRAMES)
        self.tf.setCurrentText("1h")
        
        self.strat = QtWidgets.QComboBox()
        self.strat.setMinimumWidth(260)
        for cls in S.ALL_STRATEGIES:
            self.strat.addItem(f"{cls.name_en} · {cls.category}", cls.id)
        
        self.btn = QtWidgets.QPushButton("Run Analysis")
        self.btn.setObjectName("primary")
        
        self.price_lbl = QtWidgets.QLabel("")
        self.price_lbl.setStyleSheet(f"font-weight:700; font-size:13px;")
        
        self.change_lbl = QtWidgets.QLabel("")
        
        for lbl, w in (("Symbol", self.sym), ("TF", self.tf), ("Strategy", self.strat)):
            top.addWidget(QtWidgets.QLabel(lbl))
            top.addWidget(w)
        top.addWidget(self.btn)
        top.addWidget(self.price_lbl)
        top.addWidget(self.change_lbl)
        top.addStretch()
        
        v.addLayout(top)
        
        # TradingView toolbar
        self.tv_toolbar = TradingViewToolbar()
        self.tv_toolbar.timeframeChanged.connect(lambda tf: (self.tf.setCurrentText(tf), self.run()))
        self.tv_toolbar.chartTypeChanged.connect(self._on_chart_type)
        self.tv_toolbar.screenshotRequested.connect(self._on_screenshot)
        v.addWidget(self.tv_toolbar)
        
        # Main split: chart + right panel
        split = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        
        # Chart
        self.chart = ChartWidget()
        self.chart.barHovered.connect(self._on_hover)
        split.addWidget(self.chart)
        
        # Right panel: signals, trades, stats
        right = QtWidgets.QWidget()
        right.setMinimumWidth(380)
        right.setMaximumWidth(480)
        rv = QtWidgets.QVBoxLayout(right)
        rv.setContentsMargins(0,0,0,0)
        rv.setSpacing(0)
        
        # Stats tiles
        self.stats_card = QtWidgets.QFrame()
        self.stats_card.setObjectName("card")
        sv = QtWidgets.QVBoxLayout(self.stats_card)
        sv.setContentsMargins(10,8,10,8)
        self.stats_layout = QtWidgets.QGridLayout()
        sv.addLayout(self.stats_layout)
        rv.addWidget(self.stats_card)
        
        # Signals table
        from .widgets import make_table
        self.sig_tbl = make_table(["Time","Side","Price","SL","TP","R:R"])
        self.sig_tbl.setMaximumHeight(200)
        rv.addWidget(QtWidgets.QLabel("Signals"))
        rv.addWidget(self.sig_tbl)
        
        # Trades
        self.trade_tbl = make_table(["Entry","Side","R","PnL"])
        rv.addWidget(QtWidgets.QLabel("Last Trades"))
        rv.addWidget(self.trade_tbl,1)
        
        split.addWidget(right)
        split.setSizes([1000, 400])
        
        v.addWidget(split,1)
        
        # Status bar
        self.statusbar = ChartStatusBar()
        v.addWidget(self.statusbar)
        
        # Connections
        self.btn.clicked.connect(self.run)
        self.sig_tbl.itemClicked.connect(self._jump)
        
        # Init
        self.df=None
        self.res=None
        self._chart_type="candle"
        
        # Auto run first
        QtCore.QTimer.singleShot(500, self.run)
    
    def _on_hover(self, i):
        df=self.chart.df
        if df is None or not (0<=i<len(df)):
            return
        r=df.iloc[i]
        prev=df.iloc[i-1] if i>0 else r
        chg=(r.close/prev.close-1)*100 if prev.close else 0
        self.statusbar.set_ohlc(r.open, r.high, r.low, r.close, r.volume, chg)
        self.tv_toolbar.set_price_info(f"{r.close:,.6g} {chg:+.2f}%")
    
    def _on_chart_type(self, ctype):
        self._chart_type=ctype
        if ctype=="heikin":
            self.chart.add_indicator("heikin_ashi", {})
        elif ctype=="renko":
            self.chart.add_indicator("renko", {})
        else:
            # For line/area, we can set via chart refresh
            self.chart.refresh_same()
    
    def _on_screenshot(self):
        try:
            pixmap=self.chart.grab()
            import datetime
            fname=f"chart_{self.sym.currentData()}_{self.tf.currentText()}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            path,_=QtWidgets.QFileDialog.getSaveFileName(self, "Save Screenshot", fname, "PNG (*.png)")
            if path:
                pixmap.save(path)
        except Exception as e:
            print(f"screenshot failed: {e}")
    
    def _jump(self, item):
        # Jump to signal bar
        try:
            i=item.data(QtCore.Qt.ItemDataRole.UserRole)
            if i is not None:
                self.chart.highlight(int(i), pan=True)
        except Exception:
            pass
    
    def run(self):
        sym=self.sym.currentData() or self.sym.currentText().strip()
        tf=self.tf.currentText()
        sid=self.strat.currentData()
        
        self.btn.setEnabled(False)
        self.btn.setText("Loading...")
        
        def work():
            try:
                df=get_ohlcv(sym, tf)
                ok=True
            except Exception:
                df=generate_synthetic(seed=abs(hash(sym+tf))%10000)
                ok=False
            strat=S.REGISTRY[sid]()
            res=strat.run(df)
            bt=run_backtest(df, res, symbol=sym)
            return df, ok, res, bt
        
        from .widgets import Worker
        self.w=Worker(work)
        self.w.done.connect(lambda r: self._show(sym, tf, sid, *r))
        self.w.error.connect(lambda e: (self.btn.setEnabled(True), self.btn.setText("Run Analysis")))
        self.w.start()
    
    def _show(self, sym, tf, sid, df, ok, res, bt):
        self.btn.setEnabled(True)
        self.btn.setText("Run Analysis")
        self.df=df
        self.res=res
        
        # Title with stats
        st=bt.stats
        title=f"{sym} · {tf} · {S.REGISTRY[sid].name_en} | WR {st['win_rate']:.0f}% PF {st['profit_factor']:.2f} Ret {st['return_pct']:+.1f}%"
        
        self.chart.set_data(df, res, trades=bt.trades, title=title)
        
        # Update price labels
        last=df.close.iloc[-1]
        prev=df.close.iloc[-2] if len(df)>1 else last
        chg=(last/prev-1)*100 if prev else 0
        self.price_lbl.setText(f"{last:,.6g}")
        self.change_lbl.setText(f"{chg:+.2f}%")
        self.change_lbl.setStyleSheet(f"color: {C['green'] if chg>=0 else C['red']};")
        self.tv_toolbar.set_price_info(f"{last:,.6g} {chg:+.2f}%")
        
        # Stats tiles
        # Clear
        while self.stats_layout.count():
            child=self.stats_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        from .widgets import StatTile
        stats=[
            ("Win Rate", f"{st['win_rate']:.1f}%"),
            ("PF", f"{st['profit_factor']:.2f}"),
            ("Trades", f"{st['trades']:.0f}"),
            ("Return", f"{st['return_pct']:+.1f}%"),
            ("DD", f"{st['max_dd_pct']:.1f}%"),
            ("Avg R", f"{st['avg_r']:+.2f}R"),
        ]
        for idx,(k,v) in enumerate(stats):
            lbl=QtWidgets.QLabel(f"<b>{k}</b><br>{v}")
            lbl.setStyleSheet(f"background:{C['panel2']}; border:1px solid {C['border']}; border-radius:6px; padding:6px;")
            self.stats_layout.addWidget(lbl, idx//3, idx%3)
        
        # Signals
        self.sig_tbl.setRowCount(0)
        sig=res.signal
        idxs=np.where(sig.values!=0)[0][-30:][::-1]
        for i in idxs:
            r=self.sig_tbl.rowCount()
            self.sig_tbl.insertRow(r)
            from .widgets import cell, ncell
            from core import clock
            it=cell(clock.fmt(df.index[i]))
            it.setData(QtCore.Qt.ItemDataRole.UserRole, int(i))
            self.sig_tbl.setItem(r,0,it)
            side=int(sig.iloc[i])
            self.sig_tbl.setItem(r,1,cell("LONG" if side==1 else "SHORT", C['green'] if side==1 else C['red']))
            self.sig_tbl.setItem(r,2,ncell(df.close.iloc[i], "{:,.6g}"))
            self.sig_tbl.setItem(r,3,ncell(res.stop.iloc[i] if res.stop is not None else np.nan, "{:,.6g}", C['red']))
            self.sig_tbl.setItem(r,4,ncell(res.target.iloc[i] if res.target is not None else np.nan, "{:,.6g}", C['green']))
            px=df.close.iloc[i]
            sl=res.stop.iloc[i] if res.stop is not None else np.nan
            tp=res.target.iloc[i] if res.target is not None else np.nan
            rr=abs(tp-px)/abs(px-sl) if sl==sl and tp==tp and px!=sl else np.nan
            self.sig_tbl.setItem(r,5,ncell(rr, "1:{:.1f}"))
        
        # Trades
        self.trade_tbl.setRowCount(0)
        for tr in bt.trades[-20:][::-1]:
            r=self.trade_tbl.rowCount()
            self.trade_tbl.insertRow(r)
            from .widgets import cell, ncell
            from core import clock
            self.trade_tbl.setItem(r,0,cell(clock.fmt(tr.entry_time)))
            self.trade_tbl.setItem(r,1,cell("LONG" if tr.side==1 else "SHORT", C['green'] if tr.side==1 else C['red']))
            self.trade_tbl.setItem(r,2,ncell(tr.r_multiple, "{:+.2f}R", C['green'] if tr.r_multiple>0 else C['red']))
            self.trade_tbl.setItem(r,3,ncell(tr.pnl, "${:+,.2f}", C['green'] if tr.pnl>0 else C['red']))
