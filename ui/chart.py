"""Interactive candlestick chart widget with overlays, signals, zones, sub-panels & crosshair."""
import numpy as np
import pandas as pd
import pyqtgraph as pg
from PyQt6 import QtCore, QtGui, QtWidgets
from .theme import C

pg.setConfigOptions(antialias=True, background=C["panel"], foreground=C["text"])

OVERLAY_COLORS = ["#ffb74d", "#4fc3f7", "#ba68c8", "#aed581", "#ff8a65", "#90a4ae", "#f06292", "#fff176"]


class CandlestickItem(pg.GraphicsObject):
    def __init__(self, df: pd.DataFrame):
        super().__init__()
        self.df = df
        self.picture = None
        self._gen()

    def _gen(self):
        self.picture = QtGui.QPicture()
        p = QtGui.QPainter(self.picture)
        o, h, l, c = self.df.open.values, self.df.high.values, self.df.low.values, self.df.close.values
        w = 0.35
        up_pen = pg.mkPen(C["green"], width=1)
        dn_pen = pg.mkPen(C["red"], width=1)
        up_br = pg.mkBrush(C["green"])
        dn_br = pg.mkBrush(C["red"])
        for i in range(len(c)):
            up = c[i] >= o[i]
            p.setPen(up_pen if up else dn_pen)
            p.setBrush(up_br if up else dn_br)
            p.drawLine(QtCore.QPointF(i, l[i]), QtCore.QPointF(i, h[i]))
            top, bot = (c[i], o[i]) if up else (o[i], c[i])
            hgt = max(top - bot, (h[i] - l[i]) * 0.02 or 1e-9)
            p.drawRect(QtCore.QRectF(i - w, bot, 2 * w, hgt))
        p.end()

    def paint(self, p, *args):
        p.drawPicture(0, 0, self.picture)

    def boundingRect(self):
        return QtCore.QRectF(self.picture.boundingRect())


class VolumeItem(pg.GraphicsObject):
    def __init__(self, df):
        super().__init__()
        self.picture = QtGui.QPicture()
        p = QtGui.QPainter(self.picture)
        o, c, v = df.open.values, df.close.values, df.volume.values
        p.setPen(pg.mkPen(None))
        for i in range(len(v)):
            p.setBrush(pg.mkBrush(C["green"] + "88" if c[i] >= o[i] else C["red"] + "88"))
            p.drawRect(QtCore.QRectF(i - 0.35, 0, 0.7, v[i]))
        p.end()

    def paint(self, p, *args):
        p.drawPicture(0, 0, self.picture)

    def boundingRect(self):
        return QtCore.QRectF(self.picture.boundingRect())


class TimeAxis(pg.AxisItem):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.index = None

    def set_index(self, idx):
        self.index = idx

    def tickStrings(self, values, scale, spacing):
        if self.index is None or len(self.index) == 0:
            return [""] * len(values)
        out = []
        span = self.index[-1] - self.index[0] if len(self.index) > 1 else pd.Timedelta(days=1)
        fmt = "%H:%M" if spacing < 30 and span < pd.Timedelta(days=10) else ("%m-%d %H:%M" if span < pd.Timedelta(days=90) else "%Y-%m-%d")
        for v in values:
            i = int(round(v))
            if 0 <= i < len(self.index):
                out.append(pd.Timestamp(self.index[i]).strftime(fmt))
            else:
                out.append("")
        return out


class ChartWidget(QtWidgets.QWidget):
    barHovered = QtCore.pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.df = None
        self.layout_ = QtWidgets.QVBoxLayout(self)
        self.layout_.setContentsMargins(0, 0, 0, 0)
        self.glw = pg.GraphicsLayoutWidget()
        self.glw.setLayoutDirection(QtCore.Qt.LayoutDirection.LeftToRight)
        self.layout_.addWidget(self.glw)
        self.info = QtWidgets.QLabel("")
        self.info.setStyleSheet(f"color:{C['muted']}; padding:4px 8px; font-family: Consolas, monospace; font-size:12px;")
        self.layout_.insertWidget(0, self.info)
        self.price_plot = None
        self.vol_plot = None
        self.panel_plots = []
        self.vline = None
        self.hline = None
        self._build()

    def _build(self):
        self.glw.clear()
        self.taxis = TimeAxis(orientation="bottom")
        self.price_plot = self.glw.addPlot(row=0, col=0, axisItems={"bottom": TimeAxis(orientation="bottom")})
        self.price_plot.showGrid(x=True, y=True, alpha=0.12)
        self.price_plot.setMenuEnabled(False)
        self.price_plot.getAxis("right").show()
        self.price_plot.getAxis("left").hide()
        self.price_plot.setDownsampling(mode="peak")
        self.price_plot.setClipToView(True)
        self.price_plot.getAxis("bottom").setStyle(showValues=False)
        self.legend = self.price_plot.addLegend(offset=(10, 10), labelTextColor=C["text"], brush=pg.mkBrush(C["panel"] + "cc"))
        self.vol_plot = self.glw.addPlot(row=1, col=0, axisItems={"bottom": self.taxis})
        self.vol_plot.setMaximumHeight(90)
        self.vol_plot.getAxis("right").show()
        self.vol_plot.getAxis("left").hide()
        self.vol_plot.setXLink(self.price_plot)
        self.vol_plot.setMenuEnabled(False)
        self.vol_plot.showGrid(x=True, alpha=0.1)
        self.glw.ci.layout.setRowStretchFactor(0, 5)
        self.glw.ci.layout.setRowStretchFactor(1, 1)
        self.panel_plots = []
        self.vline = pg.InfiniteLine(angle=90, pen=pg.mkPen(C["muted"], style=QtCore.Qt.PenStyle.DashLine))
        self.hline = pg.InfiniteLine(angle=0, pen=pg.mkPen(C["muted"], style=QtCore.Qt.PenStyle.DashLine))
        self.price_plot.addItem(self.vline, ignoreBounds=True)
        self.price_plot.addItem(self.hline, ignoreBounds=True)
        self.price_plot.scene().sigMouseMoved.connect(self._mouse)

    def _mouse(self, pos):
        if self.df is None:
            return
        vb = self.price_plot.vb
        if self.price_plot.sceneBoundingRect().contains(pos):
            mp = vb.mapSceneToView(pos)
            self.vline.setPos(mp.x())
            self.hline.setPos(mp.y())
            i = int(round(mp.x()))
            if 0 <= i < len(self.df):
                r = self.df.iloc[i]
                chg = (r.close / r.open - 1) * 100
                col = C["green"] if chg >= 0 else C["red"]
                self.info.setText(
                    f"<span style='color:{C['text']}'>{pd.Timestamp(self.df.index[i]).strftime('%Y-%m-%d %H:%M')}</span>"
                    f"&nbsp;&nbsp;O <b>{r.open:,.6g}</b>&nbsp; H <b>{r.high:,.6g}</b>&nbsp; L <b>{r.low:,.6g}</b>&nbsp; C <b>{r.close:,.6g}</b>"
                    f"&nbsp; <span style='color:{col}'>{chg:+.2f}%</span>&nbsp; Vol <b>{r.volume:,.0f}</b>")
                self.barHovered.emit(i)

    def set_data(self, df: pd.DataFrame, result=None, trades=None, title=""):
        self.df = df
        self._build()
        self.taxis.set_index(df.index)
        self.price_plot.setTitle(title, color=C["text"], size="12pt")
        self.price_plot.addItem(CandlestickItem(df))
        self.vol_plot.addItem(VolumeItem(df))
        n = len(df)
        x = np.arange(n)
        if result is not None:
            # zones
            for (s, e, lo, hi, col, lbl) in result.zones or []:
                e = min(e, n - 1)
                rect = QtWidgets.QGraphicsRectItem(s, lo, max(e - s, 1), hi - lo)
                rect.setPen(pg.mkPen(col, width=1))
                rect.setBrush(pg.mkBrush(col + "33"))
                self.price_plot.addItem(rect)
            # levels
            for (px, lbl, col) in result.levels or []:
                self.price_plot.addItem(pg.InfiniteLine(angle=0, pos=px, pen=pg.mkPen(col, width=1, style=QtCore.Qt.PenStyle.DotLine)))
            # overlays
            for k, (name, s) in enumerate(result.overlays.items()):
                col = OVERLAY_COLORS[k % len(OVERLAY_COLORS)]
                y = np.asarray(s.values, dtype=float)
                self.price_plot.plot(x, y, pen=pg.mkPen(col, width=1.3), name=name, connect="finite")
            # signals
            sig = result.signal.values
            li = np.where(sig == 1)[0]
            si = np.where(sig == -1)[0]
            atr_pad = (df.high - df.low).rolling(14).mean().bfill().values
            if len(li):
                sp = pg.ScatterPlotItem(x=li, y=df.low.values[li] - atr_pad[li] * 0.6, symbol="t1", size=13,
                                        brush=pg.mkBrush(C["green"]), pen=pg.mkPen("w", width=0.5), name="Long")
                self.price_plot.addItem(sp)
            if len(si):
                sp = pg.ScatterPlotItem(x=si, y=df.high.values[si] + atr_pad[si] * 0.6, symbol="t", size=13,
                                        brush=pg.mkBrush(C["red"]), pen=pg.mkPen("w", width=0.5), name="Short")
                self.price_plot.addItem(sp)
            # sub panels
            for k, (pname, series_dict) in enumerate(result.panels.items()):
                pl = self.glw.addPlot(row=2 + k, col=0, axisItems={"bottom": TimeAxis(orientation="bottom")})
                pl.setMaximumHeight(130)
                pl.setXLink(self.price_plot)
                pl.getAxis("right").show()
                pl.getAxis("left").hide()
                pl.getAxis("bottom").setStyle(showValues=False)
                pl.showGrid(x=True, y=True, alpha=0.1)
                pl.setMenuEnabled(False)
                pl.addLegend(offset=(10, 5), labelTextColor=C["text"], brush=pg.mkBrush(C["panel"] + "cc"))
                for j, (sname, s) in enumerate(series_dict.items()):
                    col = OVERLAY_COLORS[(j + 1) % len(OVERLAY_COLORS)]
                    y = np.asarray(s.values, dtype=float)
                    if sname.lower() in ("hist", "momentum", "squeeze"):
                        brushes = [pg.mkBrush(C["green"] + "99" if v >= 0 else C["red"] + "99") for v in np.nan_to_num(y)]
                        bg = pg.BarGraphItem(x=x, height=np.nan_to_num(y), width=0.7, brushes=brushes, pen=pg.mkPen(None))
                        pl.addItem(bg)
                    else:
                        pl.plot(x, y, pen=pg.mkPen(col, width=1.2), name=sname, connect="finite")
                if pname.upper().startswith("RSI") or pname in ("MFI", "StochRSI"):
                    for lvl in (30, 70) if pname != "StochRSI" else (20, 80):
                        pl.addItem(pg.InfiniteLine(angle=0, pos=lvl, pen=pg.mkPen(C["muted"], style=QtCore.Qt.PenStyle.DotLine)))
                if pname == "MACD":
                    pl.addItem(pg.InfiniteLine(angle=0, pos=0, pen=pg.mkPen(C["muted"])))
                self.panel_plots.append(pl)
        # trades (entry→exit lines)
        if trades:
            idx = {ts: i for i, ts in enumerate(df.index)}
            for tr in trades[-300:]:
                i0, i1 = idx.get(tr.entry_time), idx.get(tr.exit_time)
                if i0 is None or i1 is None:
                    continue
                col = C["green"] if tr.pnl > 0 else C["red"]
                self.price_plot.plot([i0, i1], [tr.entry, tr.exit], pen=pg.mkPen(col, width=1.5, style=QtCore.Qt.PenStyle.DashLine))
                # stop/target rails
                self.price_plot.plot([i0, i1], [tr.stop, tr.stop], pen=pg.mkPen(C["red"] + "66", width=0.8))
                self.price_plot.plot([i0, i1], [tr.target, tr.target], pen=pg.mkPen(C["green"] + "66", width=0.8))
        # default view: last 200 bars
        view_n = min(200, n)
        self.price_plot.setXRange(n - view_n, n + 3, padding=0)
        seg = df.iloc[n - view_n:]
        self.price_plot.setYRange(seg.low.min() * 0.995, seg.high.max() * 1.005, padding=0)
        self.price_plot.vb.setLimits(xMin=-5, xMax=n + 50)
        self.price_plot.sigXRangeChanged.connect(self._autoscale_y)

    def _autoscale_y(self):
        if self.df is None:
            return
        (x0, x1), _ = self.price_plot.viewRange()
        i0, i1 = max(int(x0), 0), min(int(x1) + 1, len(self.df))
        if i1 - i0 < 2:
            return
        seg = self.df.iloc[i0:i1]
        lo, hi = seg.low.min(), seg.high.max()
        pad = (hi - lo) * 0.05
        self.price_plot.blockSignals(True)
        self.price_plot.setYRange(lo - pad, hi + pad, padding=0)
        self.price_plot.blockSignals(False)
        vmax = seg.volume.max()
        if vmax > 0:
            self.vol_plot.setYRange(0, vmax * 1.1, padding=0)


class EquityChart(pg.PlotWidget):
    def __init__(self, parent=None):
        super().__init__(parent, axisItems={"bottom": TimeAxis(orientation="bottom")})
        self.setLayoutDirection(QtCore.Qt.LayoutDirection.LeftToRight)
        self.showGrid(x=True, y=True, alpha=0.15)
        self.getAxis("right").show()
        self.getAxis("left").hide()
        self.setMenuEnabled(False)

    def set_equity(self, eq: pd.Series, initial: float):
        self.clear()
        self.getAxis("bottom").set_index(eq.index)
        x = np.arange(len(eq))
        y = eq.values.astype(float)
        base = np.full_like(y, initial)
        c1 = pg.PlotDataItem(x, y, pen=pg.mkPen(C["accent2"], width=2))
        c2 = pg.PlotDataItem(x, base, pen=pg.mkPen(C["muted"], style=QtCore.Qt.PenStyle.DashLine))
        fill = pg.FillBetweenItem(c1, c2, brush=pg.mkBrush(C["accent2"] + "22"))
        self.addItem(fill)
        self.addItem(c2)
        self.addItem(pg.PlotDataItem(x, eq.cummax().values, pen=pg.mkPen(C["red"] + "66", width=1)))
        self.addItem(c1)
        lo, hi = min(y.min(), initial), max(y.max(), initial)
        pad = (hi - lo) * 0.08 or 1
        self.setXRange(0, len(eq), padding=0.01)
        self.setYRange(lo - pad, hi + pad, padding=0)
