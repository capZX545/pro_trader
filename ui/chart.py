"""Interactive candlestick chart widget with overlays, signals, zones, sub-panels & crosshair."""
import time
import numpy as np
import pandas as pd
import pyqtgraph as pg
from PyQt6 import QtCore, QtGui, QtWidgets
from .theme import C

pg.setConfigOptions(antialias=True, background=C["panel"], foreground=C["text"])

def _fmt_ts(ts):
    try:
        from core import clock
        return clock.fmt(ts)
    except Exception:
        return pd.Timestamp(ts).strftime("%Y-%m-%d %H:%M")


OVERLAY_COLORS = ["#ffb74d", "#4fc3f7", "#ba68c8", "#aed581", "#ff8a65", "#90a4ae", "#f06292", "#fff176"]


class CandlestickItem(pg.GraphicsObject):
    def __init__(self, df: pd.DataFrame):
        super().__init__()
        self.df = df
        self.picture = None
        self._gen()

    CHUNK = 1000

    def _gen(self):
        """History is split into chunks of CHUNK bars, each its own QPicture, built LAZILY on first paint of that
        range (so a 50k-bar load costs ~nothing up front; scrolling back builds chunks on demand, ~5 ms each).
        paint() replays only chunks intersecting the visible x-range → repaint is O(visible), not O(n)."""
        self.picture = QtGui.QPicture()
        self.extra = []
        df = self.df
        n = len(df)
        self._o, self._h, self._l, self._c = (df.open.values.astype(float), df.high.values.astype(float),
                                              df.low.values.astype(float), df.close.values.astype(float))
        self._n = n
        self._cache = {}                            # chunk index → QPicture
        lo = float(np.nanmin(self._l)) if n else 0.0
        hi = float(np.nanmax(self._h)) if n else 1.0
        self._bounds = QtCore.QRectF(-1, lo, n + 2, max(hi - lo, 1e-9))

    def _chunk(self, ci):
        pic = self._cache.get(ci)
        if pic is not None:
            return pic
        s, e = ci * self.CHUNK, min((ci + 1) * self.CHUNK, self._n)
        o, h, l, c = self._o[s:e], self._h[s:e], self._l[s:e], self._c[s:e]
        up = c >= o
        top = np.where(up, c, o); bot = np.where(up, o, c)
        hgt = np.maximum(top - bot, np.maximum((h - l) * 0.02, 1e-9))
        w = 0.35
        pic = QtGui.QPicture(); p = QtGui.QPainter(pic)
        for mask, col in ((up, C["green"]), (~up, C["red"])):
            if not mask.any():
                continue
            xi = np.arange(s, e, dtype=float)[mask]; li = l[mask]; hi = h[mask]; bi = bot[mask]; gi = hgt[mask]
            p.setPen(pg.mkPen(col, width=1)); p.setBrush(pg.mkBrush(col))
            p.drawLines([QtCore.QLineF(xi[k], li[k], xi[k], hi[k]) for k in range(len(xi))])
            p.drawRects([QtCore.QRectF(xi[k] - w, bi[k], 2 * w, gi[k]) for k in range(len(xi))])
        p.end()
        self._cache[ci] = pic
        return pic

    def paint(self, p, opt, *args):
        vb = self.getViewBox()
        if vb is not None:
            (x0, x1), _ = vb.viewRange()
        else:
            x0, x1 = -1e18, 1e18
        n = getattr(self, "_n", 0)
        if n:
            c0 = max(int(x0 - 1) // self.CHUNK, 0)
            c1 = min(int(x1 + 1) // self.CHUNK, (n - 1) // self.CHUNK)
            for ci in range(c0, c1 + 1):
                p.drawPicture(0, 0, self._chunk(ci))
        for pic in self.extra:
            p.drawPicture(0, 0, pic)

    def boundingRect(self):
        r = QtCore.QRectF(self._bounds)
        for pic in self.extra:
            r = r.united(QtCore.QRectF(pic.boundingRect()))
        return r

    def update_df(self, df):
        """Called once per bar close. If exactly one bar was appended, draw only that bar on top of the existing
        display list (O(1)); otherwise regenerate."""
        n_old, n_new = len(self.df), len(df)
        if n_new == n_old + 1 and getattr(self, "_cache", None) is not None:
            self.df = df
            self._append_bar(n_new - 1)
        else:
            self.df = df
            self.prepareGeometryChange()
            self._gen()
        self.update()

    def _append_bar(self, i):
        r = self.df.iloc[i]
        o, h, l, cl = float(r.open), float(r.high), float(r.low), float(r.close)
        # QPicture cannot be appended in place → keep a list of chunk pictures; a new bar is a tiny extra chunk
        pic = QtGui.QPicture()
        p = QtGui.QPainter(pic)
        col = C["green"] if cl >= o else C["red"]
        p.setPen(pg.mkPen(col, width=1)); p.setBrush(pg.mkBrush(col))
        p.drawLine(QtCore.QPointF(i, l), QtCore.QPointF(i, h))
        top, bot = (cl, o) if cl >= o else (o, cl)
        p.drawRect(QtCore.QRectF(i - 0.35, bot, 0.7, max(top - bot, (h - l) * 0.02 or 1e-9)))
        p.end()
        self.prepareGeometryChange()
        self.extra.append(pic)
        if len(self.extra) > 500:                       # compact occasionally
            self._gen()


class LiveBarItem(pg.GraphicsObject):
    """The single forming candle + its volume bar, redrawn on every tick (O(1)) — the historical picture
    stays untouched, so streaming costs < 1 ms even with 50k bars loaded."""

    def __init__(self, volume=False):
        super().__init__()
        self.volume = volume
        self.i, self.o, self.h, self.l, self.c, self.v = 0, 0.0, 0.0, 0.0, 0.0, 0.0
        self._rect = QtCore.QRectF()

    def set_bar(self, i, o, h, l, c, v):
        self.i, self.o, self.h, self.l, self.c, self.v = i, o, h, l, c, v
        self.prepareGeometryChange()
        if self.volume:
            self._rect = QtCore.QRectF(i - 0.5, 0, 1.0, max(v, 1e-12))
        else:
            self._rect = QtCore.QRectF(i - 0.5, min(l, h), 1.0, max(abs(h - l), 1e-12))
        self.update()

    def paint(self, p, *args):
        up = self.c >= self.o
        col = C["green"] if up else C["red"]
        if self.volume:
            p.setPen(pg.mkPen(None)); p.setBrush(pg.mkBrush(col + "88"))
            p.drawRect(QtCore.QRectF(self.i - 0.35, 0, 0.7, self.v))
            return
        p.setPen(pg.mkPen(col, width=1)); p.setBrush(pg.mkBrush(col))
        p.drawLine(QtCore.QPointF(self.i, self.l), QtCore.QPointF(self.i, self.h))
        top, bot = (self.c, self.o) if up else (self.o, self.c)
        hgt = max(top - bot, (self.h - self.l) * 0.02 or 1e-9)
        p.drawRect(QtCore.QRectF(self.i - 0.35, bot, 0.7, hgt))

    def boundingRect(self):
        return self._rect


class VolumeItem(pg.GraphicsObject):
    """Volume bars in lazily-built 1000-bar QPicture chunks; only chunks intersecting the view are painted."""
    CHUNK = 1000

    def __init__(self, df):
        super().__init__()
        self.df = df
        self._gen()

    def update_df(self, df):
        n_old, n_new = len(self.df), len(df)
        self.df = df
        if n_new == n_old + 1 and self._cache is not None:
            i = n_new - 1; r = df.iloc[i]
            pic = QtGui.QPicture(); p = QtGui.QPainter(pic)
            p.setPen(pg.mkPen(None)); p.setBrush(pg.mkBrush((C["green"] if r.close >= r.open else C["red"]) + "88"))
            p.drawRect(QtCore.QRectF(i - 0.35, 0, 0.7, float(r.volume))); p.end()
            self.prepareGeometryChange(); self.extra.append(pic)
            self._vmax = max(self._vmax, float(r.volume))
            self._rect = QtCore.QRectF(-0.5, 0, n_new + 1, self._vmax * 1.02 or 1)
            if len(self.extra) > 500:
                self._gen()
        else:
            self.prepareGeometryChange()
            self._gen()
        self.update()

    def _gen(self):
        df = self.df
        self.o, self.c = df.open.values.astype(float), df.close.values.astype(float)
        self.v = np.nan_to_num(df.volume.values.astype(float))
        self._vmax = float(self.v.max()) if len(self.v) else 1.0
        self._cache = {}
        self.extra = []
        self._rect = QtCore.QRectF(-0.5, 0, len(self.v) + 1, self._vmax * 1.02 or 1)

    def _chunk(self, k):
        pic = self._cache.get(k)
        if pic is None:
            a, b = k * self.CHUNK, min((k + 1) * self.CHUNK, len(self.v))
            pic = QtGui.QPicture(); p = QtGui.QPainter(pic)
            x = np.arange(a, b, dtype=float); o, c, v = self.o[a:b], self.c[a:b], self.v[a:b]
            up = c >= o
            p.setPen(pg.mkPen(None))
            for mask, col in ((up, C["green"] + "88"), (~up, C["red"] + "88")):
                if mask.any():
                    p.setBrush(pg.mkBrush(col))
                    xi, vi = x[mask], v[mask]
                    p.drawRects([QtCore.QRectF(xi[j] - 0.35, 0, 0.7, vi[j]) for j in range(len(xi))])
            p.end()
            self._cache[k] = pic
        return pic

    def paint(self, p, opt, *args):
        n = len(self.v)
        if n == 0:
            return
        try:
            vr = self.getViewBox().viewRect(); x0, x1 = int(max(0, vr.left() - 1)), int(min(n - 1, vr.right() + 1))
        except Exception:
            x0, x1 = 0, n - 1
        if x1 < x0:
            return
        for k in range(x0 // self.CHUNK, x1 // self.CHUNK + 1):
            p.drawPicture(0, 0, self._chunk(k))
        for pic in self.extra:
            p.drawPicture(0, 0, pic)

    def boundingRect(self):
        return self._rect


class TimeAxis(pg.AxisItem):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.index = None

    def set_index(self, idx):
        try:
            from core import clock
            self.index = clock.to_local(idx)
        except Exception:
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


class PGChart(QtWidgets.QWidget):
    """pyqtgraph renderer (default). ChartWidget below wraps it and falls back to CompatChart when the
    QGraphicsView canvas does not paint on the user's machine."""
    barHovered = QtCore.pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.df = None
        self.layout_ = QtWidgets.QVBoxLayout(self)
        self.layout_.setContentsMargins(0, 0, 0, 0)
        self.glw = pg.GraphicsLayoutWidget()
        self.glw.setViewportUpdateMode(QtWidgets.QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
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
        self.drawings = None
        self._hl = []                       # highlight graphics for a clicked signal
        self.signal_clicked = None          # callback(i)
        self._build()

    def _build(self):
        # disconnect handlers bound to the previous plot BEFORE clearing (else they pile up on every Run and
        # fire against deleted C++ objects → "wrapped C/C++ object has been deleted" crash)
        try:
            if self.price_plot is not None:
                self.price_plot.sigXRangeChanged.disconnect(self._autoscale_y)
        except Exception:
            pass
        try:
            self.glw.scene().sigMouseMoved.disconnect(self._mouse)
        except Exception:
            pass
        # clipToView curves raise a harmless-but-noisy AttributeError inside pyqtgraph when the layout is cleared
        # while they are still parented (viewRangeChanged → parent is the GraphicsLayoutWidget). Detach them first.
        for pl in ([self.price_plot, self.vol_plot] + list(self.panel_plots)):
            if pl is None:
                continue
            try:
                for it in list(pl.listDataItems()):
                    pl.removeItem(it)
            except Exception:
                pass
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
        try:
            self.glw.scene().sigMouseClicked.disconnect(self._click)
        except Exception:
            pass
        self.glw.scene().sigMouseClicked.connect(self._click)
        from .chart_tools import DrawingLayer
        old = self.drawings
        self.drawings = DrawingLayer(self.price_plot, self)
        if old is not None:
            self.drawings.tool = old.tool
            self.drawings._json_cache = getattr(old, "_json_cache", None)
        self._hl = []

    def _click(self, ev):
        """Cursor tool: click on/near a signal marker → highlight it and report to the page."""
        if self.df is None or self.drawings is None or self.drawings.tool != "cursor" or ev.button() != QtCore.Qt.MouseButton.LeftButton:
            return
        if not self.price_plot.sceneBoundingRect().contains(ev.scenePos()):
            return
        mp = self.price_plot.vb.mapSceneToView(ev.scenePos())
        i = int(round(mp.x()))
        res = getattr(self, "_result", None)
        if res is None or not (0 <= i < len(self.df)):
            return
        sig = res.signal.values
        cand = [j for j in range(max(0, i - 2), min(len(sig), i + 3)) if sig[j] != 0]
        if cand:
            j = min(cand, key=lambda j: abs(j - i))
            self.highlight(j, pan=False)
            if callable(self.signal_clicked):
                self.signal_clicked(j)

    def highlight(self, i, pan=True):
        """Mark signal bar i: vertical line + ring + label with local time, entry/stop/target. Pans the view if asked."""
        for g in self._hl:
            try:
                self.price_plot.removeItem(g)
            except Exception:
                pass
        self._hl = []
        if self.df is None or not (0 <= i < len(self.df)):
            return
        res = getattr(self, "_result", None)
        r = self.df.iloc[i]
        side = int(res.signal.iloc[i]) if res is not None else 0
        col = C["green"] if side == 1 else (C["red"] if side == -1 else C["yellow"])
        vl = pg.InfiniteLine(angle=90, pos=i, pen=pg.mkPen(col, width=1.2, style=QtCore.Qt.PenStyle.DashLine))
        self.price_plot.addItem(vl, ignoreBounds=True)
        ring = pg.ScatterPlotItem(x=[i], y=[float(r.close)], symbol="o", size=22, brush=pg.mkBrush(None), pen=pg.mkPen(col, width=2))
        self.price_plot.addItem(ring, ignoreBounds=True)
        txt = f"{_fmt_ts(self.df.index[i])}\n{'LONG' if side == 1 else ('SHORT' if side == -1 else '')} @ {r.close:,.6g}"
        try:
            sl = float(res.stop.iloc[i]); tp = float(res.target.iloc[i])
            if sl == sl and tp == tp:
                txt += f"\nSL {sl:,.6g}  TP {tp:,.6g}"
                for y, cc in ((sl, C["red"]), (tp, C["green"])):
                    ln = pg.PlotDataItem([i, i + 30], [y, y], pen=pg.mkPen(cc, width=1, style=QtCore.Qt.PenStyle.DotLine))
                    self.price_plot.addItem(ln, ignoreBounds=True); self._hl.append(ln)
        except Exception:
            pass
        lab = pg.TextItem(txt, color="#ffffff", anchor=(0, 1) if side == 1 else (0, 0), fill=pg.mkBrush(col + "cc"))
        lab.setPos(i + 1, float(r.low if side == 1 else r.high)); lab.setZValue(60)
        self.price_plot.addItem(lab, ignoreBounds=True)
        self._hl += [vl, ring, lab]
        if pan:
            (x0, x1), _ = self.price_plot.viewRange()
            w = max(x1 - x0, 40)
            if not (x0 + w * 0.1 <= i <= x1 - w * 0.1):
                self.price_plot.setXRange(i - w * 0.6, i + w * 0.4, padding=0)

    def _mouse(self, pos):
        if self.df is None or self.price_plot is None:
            return
        now = time.monotonic()
        if now - getattr(self, "_mouse_t", 0.0) < 0.033:
            return
        self._mouse_t = now
        try:
            vb = self.price_plot.vb
        except RuntimeError:
            return
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
                    f"<span style='color:{C['text']}'>{_fmt_ts(self.df.index[i])}</span>"
                    f"&nbsp;&nbsp;O <b>{r.open:,.6g}</b>&nbsp; H <b>{r.high:,.6g}</b>&nbsp; L <b>{r.low:,.6g}</b>&nbsp; C <b>{r.close:,.6g}</b>"
                    f"&nbsp; <span style='color:{col}'>{chg:+.2f}%</span>&nbsp; Vol <b>{r.volume:,.0f}</b>")
                self.barHovered.emit(i)

    def set_data(self, df: pd.DataFrame, result=None, trades=None, title=""):
        self.glw.setUpdatesEnabled(False)          # one repaint at the end instead of one per item
        try:
            self._set_data(df, result, trades, title)
        finally:
            self.glw.setUpdatesEnabled(True)

    def _set_data(self, df, result, trades, title):
        self.df = df
        self._build()
        self.taxis.set_index(df.index)
        self.price_plot.setTitle(title, color=C["text"], size="12pt")
        # history (static picture, all bars but the last) + live forming bar (cheap per-tick redraw)
        self.candles = CandlestickItem(df.iloc[:-1] if len(df) > 1 else df)
        self.volumes = VolumeItem(df.iloc[:-1] if len(df) > 1 else df)
        self.price_plot.addItem(self.candles)
        self.vol_plot.addItem(self.volumes)
        self.live_candle = LiveBarItem(); self.live_vol = LiveBarItem(volume=True)
        r = df.iloc[-1]
        self.live_candle.set_bar(len(df) - 1, r.open, r.high, r.low, r.close, r.volume)
        self.live_vol.set_bar(len(df) - 1, r.open, r.high, r.low, r.close, r.volume)
        self.price_plot.addItem(self.live_candle); self.vol_plot.addItem(self.live_vol)
        # live last-price line + tag on the right axis (TradingView-style)
        last = float(df.close.iloc[-1])
        up = df.close.iloc[-1] >= df.open.iloc[-1]
        self.price_line = pg.InfiniteLine(angle=0, pos=last, pen=pg.mkPen(C["green"] if up else C["red"], width=1, style=QtCore.Qt.PenStyle.DashLine),
                                          label="{value:,.6g}", labelOpts={"position": 0.97, "color": "#ffffff", "fill": pg.mkBrush(C["green"] if up else C["red"]), "movable": False})
        self.price_plot.addItem(self.price_line, ignoreBounds=True)
        self.live_tag = pg.TextItem("", color=C["muted"], anchor=(1, 0))
        self.live_tag.setParentItem(self.price_plot.vb)
        self.live_tag.setPos(self.price_plot.vb.width() - 8, 6)
        self.live_tag.setZValue(50)
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
            curves = {}
            for k, (name, s) in enumerate(result.overlays.items()):
                col = OVERLAY_COLORS[k % len(OVERLAY_COLORS)]
                y = np.asarray(s.values, dtype=float)
                style = QtCore.Qt.PenStyle.DotLine if name.startswith("Chikou") else QtCore.Qt.PenStyle.SolidLine
                curves[name] = self.price_plot.plot(x, y, pen=pg.mkPen(col, width=1.3, style=style), name=name, connect="finite", skipFiniteCheck=True)
                curves[name].setClipToView(True); curves[name].setDownsampling(auto=True, method="peak")
            # Ichimoku Kumo fill (green when Span A ≥ Span B, red otherwise) + generic band fills
            if "Senkou A" in result.overlays and "Senkou B" in result.overlays:
                a = np.asarray(result.overlays["Senkou A"].values, float); b = np.asarray(result.overlays["Senkou B"].values, float)
                for mask, col in ((a >= b, C["green"]), (a < b, C["red"])):
                    ya = np.where(mask, a, np.nan); yb = np.where(mask, b, np.nan)
                    c1 = pg.PlotDataItem(x, ya, pen=None, connect="finite"); c2 = pg.PlotDataItem(x, yb, pen=None, connect="finite")
                    fill = pg.FillBetweenItem(c1, c2, brush=pg.mkBrush(col + "2e")); fill.setZValue(-5)
                    self.price_plot.addItem(fill)
            for (up, lo, col) in getattr(result, "bands", None) or []:
                if up in curves and lo in curves and col != "kumo":
                    fill = pg.FillBetweenItem(curves[up], curves[lo], brush=pg.mkBrush(col + "22")); fill.setZValue(-5)
                    self.price_plot.addItem(fill)
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
                if not isinstance(series_dict, dict):          # tolerate panels={"RSI": series}
                    series_dict = {pname: series_dict}
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
                        yy = np.nan_to_num(y); pos = yy >= 0   # two items instead of one brush per bar (40k mkBrush ≈ 0.3 s)
                        for mask, colr in ((pos, C["green"] + "99"), (~pos, C["red"] + "99")):
                            if mask.any():
                                pl.addItem(pg.BarGraphItem(x=x[mask], height=yy[mask], width=0.7, brush=pg.mkBrush(colr), pen=pg.mkPen(None)))
                    else:
                        ci = pl.plot(x, y, pen=pg.mkPen(col, width=1.2), name=sname, connect="finite", skipFiniteCheck=True)
                        ci.setClipToView(True); ci.setDownsampling(auto=True, method="peak")
                if pname.upper().startswith("RSI") or pname in ("MFI", "StochRSI"):
                    for lvl in (30, 70) if pname != "StochRSI" else (20, 80):
                        pl.addItem(pg.InfiniteLine(angle=0, pos=lvl, pen=pg.mkPen(C["muted"], style=QtCore.Qt.PenStyle.DotLine)))
                for lvl in (getattr(result, "hlines", None) or {}).get(pname, []):
                    pl.addItem(pg.InfiniteLine(angle=0, pos=lvl, pen=pg.mkPen(C["muted"], style=QtCore.Qt.PenStyle.DotLine)))
                if pname == "MACD":
                    pl.addItem(pg.InfiniteLine(angle=0, pos=0, pen=pg.mkPen(C["muted"])))
                self.panel_plots.append(pl)
        # trades (entry→exit lines)
        if trades:
            # ONE PlotDataItem per colour with connect="pairs" (was 3 items per trade → up to 900 items, ~5-20 s UI freeze)
            idx = {ts: i for i, ts in enumerate(df.index)}
            win_x, win_y, los_x, los_y, sl_x, sl_y, tp_x, tp_y = [], [], [], [], [], [], [], []
            for tr in trades[-400:]:
                i0, i1 = idx.get(tr.entry_time), idx.get(tr.exit_time)
                if i0 is None or i1 is None:
                    continue
                (win_x if tr.pnl > 0 else los_x).extend((i0, i1)); (win_y if tr.pnl > 0 else los_y).extend((tr.entry, tr.exit))
                sl_x.extend((i0, i1)); sl_y.extend((tr.stop, tr.stop)); tp_x.extend((i0, i1)); tp_y.extend((tr.target, tr.target))
            for xs, ys, pen in ((sl_x, sl_y, pg.mkPen(C["red"] + "66", width=0.8)), (tp_x, tp_y, pg.mkPen(C["green"] + "66", width=0.8)),
                                (win_x, win_y, pg.mkPen(C["green"], width=1.5, style=QtCore.Qt.PenStyle.DashLine)),
                                (los_x, los_y, pg.mkPen(C["red"], width=1.5, style=QtCore.Qt.PenStyle.DashLine))):
                if xs:
                    item = pg.PlotDataItem(np.asarray(xs, float), np.asarray(ys, float), pen=pen, connect="pairs", skipFiniteCheck=True)
                    self.price_plot.addItem(item, ignoreBounds=True)
        self._result = result
        # default view: last 200 bars
        view_n = min(200, n)
        self.price_plot.setXRange(n - view_n, n + 3, padding=0)
        seg = df.iloc[n - view_n:]
        self.price_plot.setYRange(seg.low.min() * 0.995, seg.high.max() * 1.005, padding=0)
        self.price_plot.vb.setLimits(xMin=-5, xMax=n + 50)
        self.price_plot.sigXRangeChanged.connect(self._autoscale_y)
        # user drawings: rebuild from stored timestamps on the new frame
        if self.drawings is not None:
            self.drawings.df = df
            js = getattr(self.drawings, "_json_cache", None)
            if js:
                self.drawings.load_json(js)

    # ------------------------------------------------------------ live streaming
    def update_last_bar(self, ts, o, h, l, c, v, closed=False):
        """Called from the UI thread on every stream tick. Updates/appends the last candle in place —
        no rebuild, so zoom/pan/crosshair state is preserved. Returns True if a NEW bar was appended
        (caller may want to recompute the strategy on bar close)."""
        if self.df is None or getattr(self, "candles", None) is None:
            return False
        ts = pd.Timestamp(ts)
        df = self.df
        appended = False
        if ts == df.index[-1]:
            df.iloc[-1, df.columns.get_indexer(["open", "high", "low", "close", "volume"])] = [o, h, l, c, v]
        elif ts > df.index[-1]:
            df.loc[ts, ["open", "high", "low", "close", "volume"]] = [o, h, l, c, v]
            appended = True
            n = len(df)
            self.price_plot.vb.setLimits(xMin=-5, xMax=n + 50)
            (x0, x1), _ = self.price_plot.viewRange()
            if x1 >= n - 1:                                # user is at the right edge → follow the market
                self.price_plot.blockSignals(True)
                self.price_plot.setXRange(x0 + 1, x1 + 1, padding=0)
                self.price_plot.blockSignals(False)
            self.taxis.set_index(df.index)
        else:
            return False                                   # stale/out-of-order tick
        if appended:                                       # previous live bar becomes history (once per period)
            self.candles.update_df(df.iloc[:-1])
            self.volumes.update_df(df.iloc[:-1])
        self._pending_tick = (len(df) - 1, o, h, l, c, v, appended)
        now = time.monotonic()
        if appended or now - getattr(self, "_last_paint", 0.0) >= 0.1:
            self._flush_tick()
        elif not getattr(self, "_flush_armed", False):
            self._flush_armed = True
            QtCore.QTimer.singleShot(100, self._flush_tick)
        return appended

    def _flush_tick(self):
        """Apply the latest tick to the graphics — coalesced to ≤10 repaints/s so a busy socket cannot stall the UI."""
        self._flush_armed = False
        pt = getattr(self, "_pending_tick", None)
        if pt is None or getattr(self, "candles", None) is None:
            return
        i, o, h, l, c, v, appended = pt
        self._pending_tick = None
        self._last_paint = time.monotonic()
        try:
            self.live_candle.set_bar(i, o, h, l, c, v)
            self.live_vol.set_bar(i, o, h, l, c, v)
            up = c >= o
            col = C["green"] if up else C["red"]
            self.price_line.setPos(c)
            self.price_line.setPen(pg.mkPen(col, width=1, style=QtCore.Qt.PenStyle.DashLine))
            try:
                self.price_line.label.fill = pg.mkBrush(col)
                self.price_line.label.setText(f"{c:,.6g}")
            except Exception:
                pass
            (x0, x1), (y0, y1) = self.price_plot.viewRange()
            if appended or not (y0 <= l and h <= y1):         # rescale only when the live bar leaves the visible price range
                self._autoscale_y()
        except RuntimeError:
            pass

    def set_live_status(self, text, ok=True):
        try:
            self.live_tag.setText(text, color=C["green"] if ok else C["muted"])
            self.live_tag.setPos(self.price_plot.vb.width() - 8, 6)
        except Exception:
            pass

    def _autoscale_y(self):
        if self.df is None or self.price_plot is None:
            return
        try:
            (x0, x1), _ = self.price_plot.viewRange()
        except RuntimeError:
            return
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


def _renderer_pref():
    """'auto' | 'pyqtgraph' | 'compat' from settings.json (Settings page) or PROTRADER_CHART env."""
    import os, json
    v = os.environ.get("PROTRADER_CHART")
    if v:
        return v
    try:
        from core.paths import data as _data
        return json.load(open(_data("settings.json"))).get("chart_renderer", "auto")
    except Exception:
        return "auto"


class ChartWidget(QtWidgets.QWidget):
    """Public chart widget used by all pages. Hosts PGChart (pyqtgraph) or CompatChart (pure QPainter).

    Blank-canvas guard: after the first set_data() the pyqtgraph viewport is grabbed and, if it is uniformly the
    background colour (nothing painted — seen on some Windows GPUs/drivers with QGraphicsView), the widget swaps
    itself to CompatChart transparently and remembers the choice for the session."""
    barHovered = QtCore.pyqtSignal(int)
    modeChanged = QtCore.pyqtSignal(str)
    signalClicked = QtCore.pyqtSignal(int)
    drawingsChanged = QtCore.pyqtSignal()
    _forced = None      # session-wide decision after a detected blank canvas

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setLayoutDirection(QtCore.Qt.LayoutDirection.LeftToRight)
        self._lay = QtWidgets.QVBoxLayout(self); self._lay.setContentsMargins(0, 0, 0, 0); self._lay.setSpacing(0)
        self.info = QtWidgets.QLabel("")
        self.info.setStyleSheet(f"color:{C['muted']}; padding:4px 8px; font-family: Consolas, monospace; font-size:12px;")
        self._lay.addWidget(self.info)
        pref = ChartWidget._forced or _renderer_pref()
        self.mode = "compat" if pref == "compat" else "pyqtgraph"
        self.impl = None
        self._checked = False
        self.indicators = []            # [(key, params)] user-added chart indicators (core.chart_indicators)
        self._tool = "cursor"
        self._drawings_json = []
        self._make_impl()

    # -- plumbing
    def _make_impl(self):
        if self.impl is not None:
            self._lay.removeWidget(self.impl); self.impl.setParent(None); self.impl.deleteLater()
        if self.mode == "compat":
            from .chart_compat import CompatChart
            self.impl = CompatChart()
            self.impl.barHovered.connect(lambda i: (self.info.setText(self.impl.info_text), self.barHovered.emit(i)))
        else:
            self.impl = PGChart()
            self.impl.info.hide()
            self.impl.barHovered.connect(self._pg_hover)
            self.impl.signal_clicked = self.signalClicked.emit
        self._lay.addWidget(self.impl, 1)

    def _pg_hover(self, i):
        self.info.setText(self.impl.info.text()); self.barHovered.emit(i)

    @property
    def price_plot(self):
        return getattr(self.impl, "price_plot", None)

    @property
    def df(self):
        return self.impl.df

    def switch(self, mode):
        """Runtime switch ('pyqtgraph' | 'compat'); re-renders current data."""
        if mode == self.mode:
            return
        df, res, tr, title = self.impl.df, getattr(self.impl, "result", None) or getattr(self.impl, "_result", None), getattr(self.impl, "trades", None) or getattr(self.impl, "_trades", None), getattr(self.impl, "title", "") or getattr(self.impl, "_title", "")
        self.mode = mode
        self._make_impl()
        if df is not None:
            self.impl.set_data(df, res, trades=tr, title=title)
        self.modeChanged.emit(mode)

    # -- API
    def set_data(self, df, result=None, trades=None, title="", keep_view=False):
        """keep_view=True: keep the user's zoom/scroll position across a refresh (anchored to TIMESTAMPS, so newly
        appended bars do not shift what he is looking at). Falls back to the default view when nothing was shown yet."""
        anchor = None
        try:
            old = self.impl.df
            if keep_view and old is not None and len(old) > 2:
                x0, x1 = self.view_range()
                n = len(old)
                at_right = x1 >= n - 1
                i0 = int(np.clip(round(x0), 0, n - 1)); i1 = int(np.clip(round(x1), 0, n - 1))
                anchor = (old.index[i0], old.index[i1], x0 - round(x0), x1 - round(x1), at_right, x1 - x0)
        except Exception:
            anchor = None
        base_result = result
        result = self._with_indicators(df, result)
        if self.mode == "pyqtgraph":
            self.impl.drawings._json_cache = self._drawings_json if getattr(self.impl, "drawings", None) is not None else None
        self.impl.set_data(df, result, trades=trades, title=title)
        if self.mode == "pyqtgraph":
            self.impl.drawings.tool = self._tool
            try:
                self.impl.drawings.changed.disconnect()
            except Exception:
                pass
            self.impl.drawings.changed.connect(self._on_drawings_changed)
        if anchor is not None:
            try:
                ts0, ts1, f0, f1, at_right, width = anchor
                n = len(df)
                if at_right:
                    self.set_x_range(n - width + 3, n + 3)
                else:
                    j0 = int(df.index.searchsorted(ts0)); j1 = int(df.index.searchsorted(ts1))
                    self.set_x_range(j0 + f0, max(j1 + f1, j0 + f0 + 5))
            except Exception:
                pass
        if self.mode == "pyqtgraph":
            self.impl._result, self.impl._trades, self.impl._title = result, trades, title
            self.impl._base_result = base_result
            if not self._checked and ChartWidget._forced is None and _renderer_pref() == "auto":
                self._checked = True
                QtCore.QTimer.singleShot(1200, self._blank_guard)

    def _blank_guard(self):
        """If the pyqtgraph viewport painted nothing, switch to the compat renderer for the whole session."""
        try:
            if self.mode != "pyqtgraph" or not self.isVisible() or self.impl.df is None:
                return
            vp = self.impl.glw.viewport()
            if vp.width() < 50 or vp.height() < 50:
                return
            img = vp.grab().toImage()
            w, h = img.width(), img.height()
            bg = QtGui.QColor(C["panel"]).rgb() & 0xFFFFFF
            # sample a coarse grid; count pixels that differ from the panel background
            diff = 0; total = 0
            for yy in range(4, h - 4, max(4, h // 40)):
                for xx in range(4, w - 4, max(4, w // 60)):
                    total += 1
                    if (img.pixel(xx, yy) & 0xFFFFFF) != bg:
                        diff += 1
            if total and diff / total < 0.01:          # < 1 % non-background → canvas is blank
                ChartWidget._forced = "compat"
                self.switch("compat")
        except Exception:
            pass

    def update_last_bar(self, ts, o, h, l, c, v, closed=False):
        return self.impl.update_last_bar(ts, o, h, l, c, v, closed)

    # -- Phase 17: indicators / drawings / highlight
    def _with_indicators(self, df, result):
        if not self.indicators or df is None:
            return result
        from strategies.base import StrategyResult
        from core import chart_indicators as CI
        import copy
        if result is None:
            result = StrategyResult(pd.Series(0, index=df.index, dtype=int))
        r = copy.copy(result)
        r.overlays = dict(result.overlays or {}); r.panels = dict(result.panels or {}); r.levels = list(result.levels or [])
        r.bands = list(getattr(result, "bands", []) or []); r.hlines = dict(getattr(result, "hlines", {}) or {})
        for key, params in self.indicators:
            try:
                out = CI.compute(df, key, **params)
            except Exception:
                continue
            for k, v in out["overlays"].items():
                r.overlays[k if k not in r.overlays else f"{k} ′"] = v
            for k, v in out["panels"].items():
                r.panels[k if k not in r.panels else f"{k} ′"] = v
            r.levels += out["levels"]; r.bands += out["bands"]; r.hlines.update(out["hlines"])
        return r

    def add_indicator(self, key, params=None):
        self.indicators.append((key, dict(params or {})))
        self.refresh_same()

    def remove_indicator(self, idx):
        if 0 <= idx < len(self.indicators):
            self.indicators.pop(idx); self.refresh_same()

    def clear_indicators(self):
        self.indicators = []; self.refresh_same()

    def refresh_same(self):
        """Re-render the current frame/result with the current indicator list, keeping the view."""
        df = self.impl.df
        if df is None:
            return
        res = getattr(self.impl, "_base_result", None) if self.mode == "pyqtgraph" else getattr(self.impl, "result", None)
        tr = getattr(self.impl, "_trades", None) if self.mode == "pyqtgraph" else getattr(self.impl, "trades", None)
        title = getattr(self.impl, "_title", "") if self.mode == "pyqtgraph" else getattr(self.impl, "title", "")
        self.set_data(df, res, trades=tr, title=title, keep_view=True)

    def set_tool(self, name):
        self._tool = name
        if self.mode == "pyqtgraph" and getattr(self.impl, "drawings", None) is not None:
            self.impl.drawings.set_tool(name)

    def _on_drawings_changed(self):
        try:
            self._drawings_json = self.impl.drawings.to_json()
        except Exception:
            pass
        self.drawingsChanged.emit()

    def drawings_json(self):
        return list(self._drawings_json)

    def load_drawings(self, items):
        self._drawings_json = list(items or [])
        if self.mode == "pyqtgraph" and getattr(self.impl, "drawings", None) is not None and self.impl.df is not None:
            self.impl.drawings.df = self.impl.df
            self.impl.drawings.load_json(self._drawings_json)

    def clear_drawings(self):
        self._drawings_json = []
        if self.mode == "pyqtgraph" and getattr(self.impl, "drawings", None) is not None:
            self.impl.drawings.clear()

    def undo_drawing(self):
        if self.mode == "pyqtgraph" and getattr(self.impl, "drawings", None) is not None:
            self.impl.drawings.remove_last()

    def highlight(self, i, pan=True):
        if self.mode == "pyqtgraph":
            self.impl.highlight(i, pan=pan)
        else:
            self.set_x_range(max(i - 80, 0), min(i + 40, len(self.impl.df or [])))

    def set_live_status(self, text, ok=True):
        self.impl.set_live_status(text, ok)

    def view_range(self):
        if self.mode == "compat":
            return self.impl.view_range()
        (x0, x1), _ = self.impl.price_plot.viewRange(); return (x0, x1)

    def set_x_range(self, x0, x1):
        if self.mode == "compat":
            self.impl.set_x_range(x0, x1)
        else:
            self.impl.price_plot.setXRange(x0, x1, padding=0)


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
