"""
Compatibility chart renderer (Phase 14b).

Some Windows machines show an *empty* pyqtgraph canvas (QGraphicsView scene never paints) while every other
widget renders fine.  This widget draws the whole chart itself with QPainter into a QImage and blits it in
paintEvent — the same raster path that draws buttons and labels, so if the app is visible at all, this chart is
visible too.  It implements the subset of the ChartWidget API that the pages use:

    set_data(df, result=None, trades=None, title="")
    update_last_bar(ts, o, h, l, c, v, closed=False) -> appended: bool
    set_live_status(text, ok=True)
    view_range() -> (x0, x1)      set_x_range(x0, x1)
    barHovered signal, .info label text

Interaction: wheel = zoom (around cursor), drag = pan, double-click = reset to last 200 bars, crosshair + OHLC readout.
Rendering cost: ~2-4 ms for 300 visible candles + 3 panels, so live ticks are cheap.
"""
import math
import numpy as np
import pandas as pd
from PyQt6 import QtCore, QtGui, QtWidgets
from .theme import C

OVERLAY_COLORS = ["#ffb74d", "#4fc3f7", "#ba68c8", "#aed581", "#ff8a65", "#90a4ae", "#f06292", "#fff176"]


def _nice_step(span, target_ticks=6):
    if span <= 0 or not math.isfinite(span):
        return 1.0
    raw = span / max(target_ticks, 1)
    mag = 10 ** math.floor(math.log10(raw))
    for m in (1, 2, 2.5, 5, 10):
        if raw <= m * mag:
            return m * mag
    return 10 * mag


class CompatChart(QtWidgets.QWidget):
    barHovered = QtCore.pyqtSignal(int)

    RIGHT_AXIS = 74
    BOTTOM_AXIS = 22
    TITLE_H = 26

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setMinimumHeight(240)
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Expanding)
        self.setLayoutDirection(QtCore.Qt.LayoutDirection.LeftToRight)
        self.df = None
        self.result = None
        self.trades = None
        self.title = ""
        self.live_text = ""
        self.live_ok = False
        self.x0, self.x1 = 0.0, 1.0           # visible bar range (float, in bar index units)
        self._img = None
        self._dirty = True
        self._drag = None
        self._hover = None                    # (px, py) in widget coords
        self.info_text = ""
        self._panel_h = 110
        self._vol_h = 70

    # ------------------------------------------------------------------ public API (ChartWidget-compatible)
    def set_data(self, df, result=None, trades=None, title=""):
        self.df, self.result, self.trades, self.title = df, result, trades, title
        n = len(df)
        view = min(200, n)
        self.x0, self.x1 = float(n - view), float(n + 3)
        self._dirty = True
        self.update()

    def update_last_bar(self, ts, o, h, l, c, v, closed=False):
        if self.df is None or not len(self.df):
            return False
        ts = pd.Timestamp(ts)
        df = self.df
        appended = False
        if ts == df.index[-1]:
            df.iloc[-1, df.columns.get_indexer(["open", "high", "low", "close", "volume"])] = [o, h, l, c, v]
        elif ts > df.index[-1]:
            df.loc[ts, ["open", "high", "low", "close", "volume"]] = [o, h, l, c, v]
            appended = True
            if self.x1 >= len(df) - 1:          # following the right edge
                self.x0 += 1; self.x1 += 1
        else:
            return False
        self._dirty = True
        self.update()
        return appended

    def set_live_status(self, text, ok=True):
        self.live_text, self.live_ok = text, ok
        self._dirty = True
        self.update()

    def view_range(self):
        return (self.x0, self.x1)

    def set_x_range(self, x0, x1):
        if self.df is None:
            return
        n = len(self.df)
        w = max(x1 - x0, 5.0)
        self.x0 = max(-5.0, min(float(x0), n + 50 - w))
        self.x1 = self.x0 + w
        self._dirty = True
        self.update()

    # ------------------------------------------------------------------ geometry helpers
    def _layout(self):
        """Returns dict of rects: price, vol, panels(list of (name, rect)), right axis width."""
        W, H = self.width(), self.height()
        panels = list(self.result.panels.items()) if (self.result is not None and self.result.panels) else []
        top = self.TITLE_H
        bottom = H - self.BOTTOM_AXIS
        avail = bottom - top
        ph = min(self._panel_h, max(60, int(avail * 0.18))) if panels else 0
        vh = min(self._vol_h, max(40, int(avail * 0.12)))
        price_h = avail - vh - ph * len(panels)
        rects = {}
        y = top
        rects["price"] = QtCore.QRectF(0, y, W - self.RIGHT_AXIS, max(price_h, 80)); y += rects["price"].height()
        rects["vol"] = QtCore.QRectF(0, y, W - self.RIGHT_AXIS, vh); y += vh
        rects["panels"] = []
        for name, series in panels:
            rects["panels"].append((name, series, QtCore.QRectF(0, y, W - self.RIGHT_AXIS, ph))); y += ph
        return rects

    def _xpix(self, rect, i):
        return rect.left() + (i - self.x0) / (self.x1 - self.x0) * rect.width()

    def _ipix(self, rect, px):
        return self.x0 + (px - rect.left()) / rect.width() * (self.x1 - self.x0)

    # ------------------------------------------------------------------ painting
    def paintEvent(self, e):
        if self._dirty or self._img is None or self._img.size() != self.size() * self.devicePixelRatioF():
            self._render()
        p = QtGui.QPainter(self)
        p.drawImage(0, 0, self._img)
        # crosshair (cheap, drawn on top so it doesn't force a re-render)
        if self._hover is not None and self.df is not None:
            hx, hy = self._hover
            p.setPen(QtGui.QPen(QtGui.QColor(C["muted"]), 1, QtCore.Qt.PenStyle.DashLine))
            p.drawLine(int(hx), self.TITLE_H, int(hx), self.height() - self.BOTTOM_AXIS)
            p.drawLine(0, int(hy), self.width() - self.RIGHT_AXIS, int(hy))
        p.end()

    def _render(self):
        dpr = self.devicePixelRatioF()
        img = QtGui.QImage(int(self.width() * dpr), int(self.height() * dpr), QtGui.QImage.Format.Format_ARGB32_Premultiplied)
        img.setDevicePixelRatio(dpr)
        img.fill(QtGui.QColor(C["panel"]))
        p = QtGui.QPainter(img)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QtGui.QPainter.RenderHint.TextAntialiasing, True)
        try:
            self._draw(p)
        except Exception as ex:                     # never leave the user with a blank canvas
            p.setPen(QtGui.QColor(C["red"]))
            p.drawText(QtCore.QRectF(10, 10, self.width() - 20, 60), int(QtCore.Qt.AlignmentFlag.AlignLeft), f"chart render error: {ex}")
        p.end()
        self._img = img
        self._dirty = False

    def _draw(self, p: QtGui.QPainter):
        W, H = self.width(), self.height()
        font = p.font(); font.setPointSize(9); p.setFont(font)
        # title
        p.setPen(QtGui.QColor(C["text"]))
        tf = QtGui.QFont(font); tf.setPointSize(10); tf.setBold(False)
        p.setFont(tf)
        p.drawText(QtCore.QRectF(8, 0, W - 16, self.TITLE_H), int(QtCore.Qt.AlignmentFlag.AlignVCenter | QtCore.Qt.AlignmentFlag.AlignLeft), self.title)
        p.setFont(font)
        if self.df is None or len(self.df) == 0:
            p.setPen(QtGui.QColor(C["muted"]))
            p.drawText(self.rect(), int(QtCore.Qt.AlignmentFlag.AlignCenter), "—")
            return
        df = self.df
        n = len(df)
        R = self._layout()
        i0 = max(int(math.floor(self.x0)), 0)
        i1 = min(int(math.ceil(self.x1)) + 1, n)
        if i1 - i0 < 1:
            return
        seg = df.iloc[i0:i1]
        o, h, l, c, v = seg.open.values, seg.high.values, seg.low.values, seg.close.values, seg.volume.values
        lo, hi = float(np.nanmin(l)), float(np.nanmax(h))
        # include overlays in y-range
        if self.result is not None:
            for name, s in (self.result.overlays or {}).items():
                y = np.asarray(s.values[i0:i1], dtype=float)
                if np.isfinite(y).any():
                    lo = min(lo, float(np.nanmin(y))); hi = max(hi, float(np.nanmax(y)))
        pad = (hi - lo) * 0.06 or abs(hi) * 0.01 or 1.0
        lo -= pad; hi += pad
        pr = R["price"]
        bw = pr.width() / max(self.x1 - self.x0, 1)          # pixels per bar
        cw = max(1.0, min(bw * 0.7, 18.0))

        def ypix(val):
            return pr.bottom() - (val - lo) / (hi - lo) * pr.height()

        # grid + right price axis
        p.setClipping(False)
        step = _nice_step(hi - lo, max(4, int(pr.height() / 60)))
        yv = math.ceil(lo / step) * step
        grid_pen = QtGui.QPen(QtGui.QColor(255, 255, 255, 18), 1)
        axis_pen = QtGui.QPen(QtGui.QColor(C["muted"]))
        while yv <= hi:
            yy = ypix(yv)
            p.setPen(grid_pen); p.drawLine(QtCore.QPointF(pr.left(), yy), QtCore.QPointF(pr.right(), yy))
            p.setPen(axis_pen)
            p.drawText(QtCore.QRectF(pr.right() + 6, yy - 9, self.RIGHT_AXIS - 8, 18), int(QtCore.Qt.AlignmentFlag.AlignVCenter | QtCore.Qt.AlignmentFlag.AlignLeft), f"{yv:,.6g}")
            yv += step
        # time axis ticks (bottom)
        idx = df.index
        span_bars = self.x1 - self.x0
        tick_every = max(1, int(span_bars / max(3, int(pr.width() / 110))))
        span_t = idx[min(i1 - 1, n - 1)] - idx[i0] if i1 - 1 > i0 else pd.Timedelta(days=1)
        fmt = "%H:%M" if span_t < pd.Timedelta(days=2) else ("%m-%d %H:%M" if span_t < pd.Timedelta(days=60) else "%Y-%m-%d")
        for i in range(i0 - (i0 % tick_every), i1, tick_every):
            if i < 0 or i >= n:
                continue
            xx = self._xpix(pr, i)
            p.setPen(grid_pen); p.drawLine(QtCore.QPointF(xx, pr.top()), QtCore.QPointF(xx, H - self.BOTTOM_AXIS))
            p.setPen(axis_pen)
            p.drawText(QtCore.QRectF(xx - 55, H - self.BOTTOM_AXIS + 2, 110, self.BOTTOM_AXIS - 2), int(QtCore.Qt.AlignmentFlag.AlignHCenter | QtCore.Qt.AlignmentFlag.AlignTop), pd.Timestamp(idx[i]).strftime(fmt))
        # separators
        p.setPen(QtGui.QPen(QtGui.QColor(C["border"]), 1))
        p.drawLine(QtCore.QPointF(pr.right(), self.TITLE_H), QtCore.QPointF(pr.right(), H - self.BOTTOM_AXIS))
        p.drawLine(QtCore.QPointF(0, pr.bottom()), QtCore.QPointF(pr.right(), pr.bottom()))

        # zones / levels
        p.setClipRect(pr)
        if self.result is not None:
            for (s, e, zlo, zhi, col, lbl) in (self.result.zones or []):
                if e < i0 or s > i1:
                    continue
                qc = QtGui.QColor(col); qc.setAlpha(50)
                p.setPen(QtGui.QPen(QtGui.QColor(col), 1)); p.setBrush(qc)
                p.drawRect(QtCore.QRectF(self._xpix(pr, s), ypix(zhi), self._xpix(pr, e) - self._xpix(pr, s), ypix(zlo) - ypix(zhi)))
            for (px_, lbl, col) in (self.result.levels or []):
                if lo <= px_ <= hi:
                    p.setPen(QtGui.QPen(QtGui.QColor(col), 1, QtCore.Qt.PenStyle.DotLine))
                    p.drawLine(QtCore.QPointF(pr.left(), ypix(px_)), QtCore.QPointF(pr.right(), ypix(px_)))
        # trades
        if self.trades:
            pos = {ts: i for i, ts in enumerate(idx[i0:i1], start=i0)}
            for tr in self.trades[-300:]:
                a, b = pos.get(tr.entry_time), pos.get(tr.exit_time)
                if a is None and b is None:
                    continue
                a = a if a is not None else i0; b = b if b is not None else i1 - 1
                col = QtGui.QColor(C["green"] if tr.pnl > 0 else C["red"])
                p.setPen(QtGui.QPen(col, 1.5, QtCore.Qt.PenStyle.DashLine))
                p.drawLine(QtCore.QPointF(self._xpix(pr, a), ypix(tr.entry)), QtCore.QPointF(self._xpix(pr, b), ypix(tr.exit)))
        # candles
        up_pen = QtGui.QPen(QtGui.QColor(C["green"]), 1); dn_pen = QtGui.QPen(QtGui.QColor(C["red"]), 1)
        up_br = QtGui.QBrush(QtGui.QColor(C["green"])); dn_br = QtGui.QBrush(QtGui.QColor(C["red"]))
        for k in range(i1 - i0):
            i = i0 + k
            x = self._xpix(pr, i)
            up = c[k] >= o[k]
            p.setPen(up_pen if up else dn_pen); p.setBrush(up_br if up else dn_br)
            p.drawLine(QtCore.QPointF(x, ypix(h[k])), QtCore.QPointF(x, ypix(l[k])))
            top, bot = (c[k], o[k]) if up else (o[k], c[k])
            y_top, y_bot = ypix(top), ypix(bot)
            if y_bot - y_top < 1:
                y_bot = y_top + 1
            if cw >= 2:
                p.drawRect(QtCore.QRectF(x - cw / 2, y_top, cw, y_bot - y_top))
        # overlays + legend
        if self.result is not None:
            legend_y = pr.top() + 8
            xs = np.arange(i0, i1)
            for k, (name, s) in enumerate((self.result.overlays or {}).items()):
                col = QtGui.QColor(OVERLAY_COLORS[k % len(OVERLAY_COLORS)])
                y = np.asarray(s.values[i0:i1], dtype=float)
                path = QtGui.QPainterPath(); pen_down = False
                for j in range(len(xs)):
                    if not np.isfinite(y[j]):
                        pen_down = False; continue
                    pt = QtCore.QPointF(self._xpix(pr, xs[j]), ypix(y[j]))
                    if pen_down:
                        path.lineTo(pt)
                    else:
                        path.moveTo(pt); pen_down = True
                p.setPen(QtGui.QPen(col, 1.3)); p.setBrush(QtCore.Qt.BrushStyle.NoBrush); p.drawPath(path)
                p.setPen(col); p.drawText(QtCore.QPointF(pr.left() + 10, legend_y + 10), f"— {name}"); legend_y += 16
            # signals
            sig = self.result.signal.values[i0:i1]
            atr = (df.high - df.low).rolling(14).mean().bfill().values[i0:i1]
            for k in np.where(sig != 0)[0]:
                x = self._xpix(pr, i0 + k)
                if sig[k] == 1:
                    y = ypix(l[k] - atr[k] * 0.6); tri = QtGui.QPolygonF([QtCore.QPointF(x, y - 6), QtCore.QPointF(x - 5, y + 4), QtCore.QPointF(x + 5, y + 4)])
                    p.setPen(QtGui.QPen(QtGui.QColor("white"), 0.5)); p.setBrush(up_br)
                else:
                    y = ypix(h[k] + atr[k] * 0.6); tri = QtGui.QPolygonF([QtCore.QPointF(x, y + 6), QtCore.QPointF(x - 5, y - 4), QtCore.QPointF(x + 5, y - 4)])
                    p.setPen(QtGui.QPen(QtGui.QColor("white"), 0.5)); p.setBrush(dn_br)
                p.drawPolygon(tri)
        # last price line + tag
        last_c, last_o = float(df.close.iloc[-1]), float(df.open.iloc[-1])
        col = QtGui.QColor(C["green"] if last_c >= last_o else C["red"])
        yy = ypix(last_c)
        p.setPen(QtGui.QPen(col, 1, QtCore.Qt.PenStyle.DashLine)); p.drawLine(QtCore.QPointF(pr.left(), yy), QtCore.QPointF(pr.right(), yy))
        p.setClipping(False)
        tag = QtCore.QRectF(pr.right() + 2, yy - 10, self.RIGHT_AXIS - 4, 20)
        p.setPen(QtCore.Qt.PenStyle.NoPen); p.setBrush(col); p.drawRoundedRect(tag, 3, 3)
        p.setPen(QtGui.QColor("white")); p.drawText(tag, int(QtCore.Qt.AlignmentFlag.AlignCenter), f"{last_c:,.6g}")
        # live tag
        if self.live_text:
            p.setPen(QtGui.QColor(C["green"] if self.live_ok else C["muted"]))
            p.drawText(QtCore.QRectF(pr.right() - 260, pr.top() + 4, 252, 18), int(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter), self.live_text)

        # volume
        vr = R["vol"]
        vmax = float(np.nanmax(v)) if len(v) else 0.0
        p.setClipRect(vr)
        if vmax > 0:
            for k in range(i1 - i0):
                x = self._xpix(pr, i0 + k)
                hh = v[k] / vmax * (vr.height() - 6)
                qc = QtGui.QColor(C["green"] if c[k] >= o[k] else C["red"]); qc.setAlpha(140)
                p.setPen(QtCore.Qt.PenStyle.NoPen); p.setBrush(qc)
                p.drawRect(QtCore.QRectF(x - cw / 2, vr.bottom() - hh, max(cw, 1.0), hh))
        p.setClipping(False)
        p.setPen(axis_pen)
        p.drawText(QtCore.QRectF(vr.right() + 6, vr.top() + 4, self.RIGHT_AXIS - 8, 14), int(QtCore.Qt.AlignmentFlag.AlignLeft), f"{vmax:,.3g}")
        p.setPen(QtGui.QPen(QtGui.QColor(C["border"]), 1)); p.drawLine(QtCore.QPointF(0, vr.bottom()), QtCore.QPointF(vr.right(), vr.bottom()))

        # sub panels
        for (pname, series_dict, rr) in R["panels"]:
            vals = []
            for sname, s in series_dict.items():
                y = np.asarray(s.values[i0:i1], dtype=float)
                if np.isfinite(y).any():
                    vals.append(y)
            if not vals:
                continue
            plo = min(float(np.nanmin(y)) for y in vals); phi = max(float(np.nanmax(y)) for y in vals)
            if pname.upper().startswith("RSI") or pname in ("MFI", "StochRSI"):
                plo, phi = min(plo, 0.0), max(phi, 100.0)
            ppad = (phi - plo) * 0.08 or 1.0
            plo -= ppad; phi += ppad

            def pyp(val, rr=rr, plo=plo, phi=phi):
                return rr.bottom() - (val - plo) / (phi - plo) * rr.height()
            p.setClipRect(rr)
            if pname.upper().startswith("RSI") or pname in ("MFI", "StochRSI"):
                for lvl in ((30, 70) if pname != "StochRSI" else (20, 80)):
                    p.setPen(QtGui.QPen(QtGui.QColor(C["muted"]), 1, QtCore.Qt.PenStyle.DotLine)); p.drawLine(QtCore.QPointF(rr.left(), pyp(lvl)), QtCore.QPointF(rr.right(), pyp(lvl)))
            if pname == "MACD" or plo < 0 < phi:
                p.setPen(QtGui.QPen(QtGui.QColor(C["muted"]), 1)); p.drawLine(QtCore.QPointF(rr.left(), pyp(0)), QtCore.QPointF(rr.right(), pyp(0)))
            for j, (sname, s) in enumerate(series_dict.items()):
                y = np.asarray(s.values[i0:i1], dtype=float)
                col = QtGui.QColor(OVERLAY_COLORS[(j + 1) % len(OVERLAY_COLORS)])
                if sname.lower() in ("hist", "momentum", "squeeze"):
                    for k in range(len(y)):
                        if not np.isfinite(y[k]):
                            continue
                        qc = QtGui.QColor(C["green"] if y[k] >= 0 else C["red"]); qc.setAlpha(150)
                        p.setPen(QtCore.Qt.PenStyle.NoPen); p.setBrush(qc)
                        x = self._xpix(pr, i0 + k); y0 = pyp(0); y1 = pyp(y[k])
                        p.drawRect(QtCore.QRectF(x - cw / 2, min(y0, y1), max(cw, 1.0), abs(y1 - y0)))
                else:
                    path = QtGui.QPainterPath(); pen_down = False
                    for k in range(len(y)):
                        if not np.isfinite(y[k]):
                            pen_down = False; continue
                        pt = QtCore.QPointF(self._xpix(pr, i0 + k), pyp(y[k]))
                        if pen_down:
                            path.lineTo(pt)
                        else:
                            path.moveTo(pt); pen_down = True
                    p.setPen(QtGui.QPen(col, 1.2)); p.setBrush(QtCore.Qt.BrushStyle.NoBrush); p.drawPath(path)
            p.setClipping(False)
            p.setPen(QtGui.QColor(C["text"])); p.drawText(QtCore.QPointF(rr.left() + 10, rr.top() + 14), pname)
            p.setPen(axis_pen)
            if rr.height() >= 50:
                p.drawText(QtCore.QRectF(rr.right() + 6, rr.top() + 4, self.RIGHT_AXIS - 8, 14), int(QtCore.Qt.AlignmentFlag.AlignLeft), f"{phi - ppad:,.3g}")
                p.drawText(QtCore.QRectF(rr.right() + 6, rr.bottom() - 18, self.RIGHT_AXIS - 8, 14), int(QtCore.Qt.AlignmentFlag.AlignLeft), f"{plo + ppad:,.3g}")
            p.setPen(QtGui.QPen(QtGui.QColor(C["border"]), 1)); p.drawLine(QtCore.QPointF(0, rr.bottom()), QtCore.QPointF(rr.right(), rr.bottom()))

    # ------------------------------------------------------------------ interaction
    def resizeEvent(self, e):
        self._dirty = True
        super().resizeEvent(e)

    def wheelEvent(self, e):
        if self.df is None:
            return
        R = self._layout(); pr = R["price"]
        cx = self._ipix(pr, e.position().x())
        factor = 0.85 if e.angleDelta().y() > 0 else 1.18
        w = max(5.0, min((self.x1 - self.x0) * factor, len(self.df) + 60))
        frac = (cx - self.x0) / max(self.x1 - self.x0, 1e-9)
        self.set_x_range(cx - frac * w, cx - frac * w + w)

    def mousePressEvent(self, e):
        if e.button() == QtCore.Qt.MouseButton.LeftButton:
            self._drag = (e.position().x(), self.x0, self.x1)

    def mouseReleaseEvent(self, e):
        self._drag = None

    def mouseDoubleClickEvent(self, e):
        if self.df is not None:
            n = len(self.df); view = min(200, n)
            self.set_x_range(n - view, n + 3)

    def leaveEvent(self, e):
        self._hover = None; self.update()

    def mouseMoveEvent(self, e):
        if self.df is None:
            return
        R = self._layout(); pr = R["price"]
        if self._drag is not None:
            dx = e.position().x() - self._drag[0]
            bars = dx / pr.width() * (self._drag[2] - self._drag[1])
            self.set_x_range(self._drag[1] - bars, self._drag[2] - bars)
        self._hover = (e.position().x(), e.position().y())
        i = int(round(self._ipix(pr, e.position().x())))
        if 0 <= i < len(self.df):
            r = self.df.iloc[i]
            chg = (r.close / r.open - 1) * 100 if r.open else 0.0
            col = C["green"] if chg >= 0 else C["red"]
            self.info_text = (f"<span style='color:{C['text']}'>{pd.Timestamp(self.df.index[i]).strftime('%Y-%m-%d %H:%M')}</span>"
                              f"&nbsp;&nbsp;O <b>{r.open:,.6g}</b>&nbsp; H <b>{r.high:,.6g}</b>&nbsp; L <b>{r.low:,.6g}</b>&nbsp; C <b>{r.close:,.6g}</b>"
                              f"&nbsp; <span style='color:{col}'>{chg:+.2f}%</span>&nbsp; Vol <b>{r.volume:,.0f}</b>")
            self.barHovered.emit(i)
        self.update()
