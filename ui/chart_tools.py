"""TradingView-style chart tooling for the pyqtgraph renderer (Phase 17):
  • DrawingLayer — trend line, ray, horizontal/vertical line, rectangle, Fibonacci retracement, text note, measure (ruler),
    all movable, persisted per symbol|timeframe as (UTC timestamp, price) so they survive new bars, refreshes and restarts.
  • IndicatorDialog — pick any of the 73 catalog indicators with editable parameters; multiple instances allowed.
"""
import numpy as np
import pandas as pd
import pyqtgraph as pg
from PyQt6 import QtCore, QtGui, QtWidgets
from .theme import C, t, I18N

TOOLS = [("cursor", "⊕", "tool_cursor"), ("trend", "╱", "tool_trend"), ("ray", "➚", "tool_ray"), ("hline", "─", "tool_hline"),
         ("vline", "│", "tool_vline"), ("rect", "▭", "tool_rect"), ("fib", "𝔽", "tool_fib"), ("text", "T", "tool_text"),
         ("measure", "📏", "tool_measure"), ("erase", "⌫", "tool_erase")]
FIB_LEVELS = [0, 0.236, 0.382, 0.5, 0.618, 0.705, 0.786, 1.0, 1.272, 1.618]
DRAW_COLOR = "#facc15"


class DrawingLayer(QtCore.QObject):
    """Owns all user drawings on one PlotItem. Coordinates: x = bar index (float), y = price."""
    changed = QtCore.pyqtSignal()

    def __init__(self, plot, parent=None):
        super().__init__(parent)
        self.plot = plot
        self.df = None
        self.items = []            # list of dict(type, pts(list of [x,y]), text, color, gfx=[...])
        self.tool = "cursor"
        self._pending = None       # first click of a 2-point tool
        self._preview = None
        self.color = DRAW_COLOR
        plot.scene().sigMouseClicked.connect(self._click)
        plot.scene().sigMouseMoved.connect(self._move)

    # ------------------------------------------------------------- index <-> timestamp
    def _bar_delta(self):
        idx = self.df.index
        return (idx[-1] - idx[-2]) if len(idx) > 1 else pd.Timedelta(hours=1)

    def x_to_ts(self, x):
        idx = self.df.index; n = len(idx)
        i = int(np.floor(x)); frac = x - i
        if 0 <= i < n - 1:
            return (idx[i] + (idx[i + 1] - idx[i]) * frac).isoformat()
        base = idx[min(max(i, 0), n - 1)]
        return (base + self._bar_delta() * (x - min(max(i, 0), n - 1))).isoformat()

    def ts_to_x(self, ts):
        idx = self.df.index; n = len(idx)
        ts = pd.Timestamp(ts)
        i = int(idx.searchsorted(ts, side="right")) - 1
        if 0 <= i < n - 1:
            span = (idx[i + 1] - idx[i]); return i + ((ts - idx[i]) / span if span else 0)
        base_i = min(max(i, 0), n - 1)
        return base_i + (ts - idx[base_i]) / self._bar_delta()

    # ------------------------------------------------------------- (de)serialisation
    def to_json(self):
        if self.df is None:
            return []
        out = []
        for d in self.items:
            self._sync_from_gfx(d)
            out.append({"type": d["type"], "pts": [[self.x_to_ts(x), float(y)] for x, y in d["pts"]], "text": d.get("text", ""), "color": d.get("color", self.color)})
        return out

    def load_json(self, items):
        self.clear(emit=False)
        for d in items or []:
            try:
                pts = [[float(self.ts_to_x(ts)), float(y)] for ts, y in d["pts"]]
                self._add(d["type"], pts, d.get("text", ""), d.get("color", self.color), emit=False)
            except Exception:
                pass

    def set_df(self, df):
        """Called on every set_data: rebuild graphics for the (possibly new) frame from stored timestamps."""
        js = self.to_json() if self.df is not None else None
        self.df = df
        if js is not None:
            self.load_json(js)

    # ------------------------------------------------------------- editing
    def set_tool(self, name):
        self.tool = name
        self._cancel_pending()

    def clear(self, emit=True):
        for d in self.items:
            self._remove_gfx(d)
        self.items = []
        if emit:
            self.changed.emit()

    def remove_last(self):
        if self.items:
            self._remove_gfx(self.items.pop())
            self.changed.emit()

    def _remove_gfx(self, d):
        for g in d.get("gfx", []):
            try:
                self.plot.removeItem(g)
            except Exception:
                pass
        d["gfx"] = []

    def _cancel_pending(self):
        self._pending = None
        if self._preview is not None:
            try:
                self.plot.removeItem(self._preview)
            except Exception:
                pass
            self._preview = None

    def _view_pos(self, scene_pos):
        vb = self.plot.vb
        if not self.plot.sceneBoundingRect().contains(scene_pos):
            return None
        p = vb.mapSceneToView(scene_pos)
        return float(p.x()), float(p.y())

    def _click(self, ev):
        if self.df is None or self.tool in ("cursor",):
            return
        if ev.button() == QtCore.Qt.MouseButton.RightButton:
            self._cancel_pending(); return
        pos = self._view_pos(ev.scenePos())
        if pos is None:
            return
        x, y = pos
        if self.tool == "erase":
            self._erase_near(x, y); ev.accept(); return
        if self.tool in ("hline", "vline", "text"):
            text = ""
            if self.tool == "text":
                text, ok = QtWidgets.QInputDialog.getText(None, t("tool_text"), t("tool_text_prompt"))
                if not ok or not text:
                    return
            self._add(self.tool, [[x, y]], text); ev.accept(); return
        if self._pending is None:
            self._pending = (x, y)
            self._preview = pg.PlotDataItem([x, x], [y, y], pen=pg.mkPen(self.color, width=1, style=QtCore.Qt.PenStyle.DashLine))
            self.plot.addItem(self._preview, ignoreBounds=True)
        else:
            x0, y0 = self._pending
            self._cancel_pending()
            if abs(x - x0) < 1e-9 and abs(y - y0) < 1e-12:
                return
            self._add(self.tool, [[x0, y0], [x, y]])
        ev.accept()

    def _move(self, scene_pos):
        if self._pending is None or self._preview is None:
            return
        pos = self._view_pos(scene_pos)
        if pos is None:
            return
        x0, y0 = self._pending
        self._preview.setData([x0, pos[0]], [y0, pos[1]])

    def _erase_near(self, x, y):
        vb = self.plot.vb
        (xr0, xr1), (yr0, yr1) = vb.viewRange()
        sx = (xr1 - xr0) / max(vb.width(), 1); sy = (yr1 - yr0) / max(vb.height(), 1)
        best, bd = None, 12.0     # pixels
        for d in self.items:
            self._sync_from_gfx(d)
            pts = d["pts"]
            if d["type"] == "hline":
                dist = abs(y - pts[0][1]) / sy
            elif d["type"] == "vline":
                dist = abs(x - pts[0][0]) / sx
            elif len(pts) == 1:
                dist = np.hypot((x - pts[0][0]) / sx, (y - pts[0][1]) / sy)
            else:
                (ax, ay), (bx, by) = pts[0], pts[1]
                if d["type"] == "rect":
                    inside = min(ax, bx) <= x <= max(ax, bx) and min(ay, by) <= y <= max(ay, by)
                    dist = 0 if inside else 99
                else:
                    ax, ay, bx, by, px, py = ax / sx, ay / sy, bx / sx, by / sy, x / sx, y / sy
                    if d["type"] == "ray" and (bx - ax) != 0:
                        far = px if (px - ax) * (bx - ax) > 0 and abs(px - ax) > abs(bx - ax) else bx
                        by = ay + (by - ay) * (far - ax) / (bx - ax); bx = far
                    seg = np.array([bx - ax, by - ay]); v = np.array([px - ax, py - ay])
                    L = seg @ seg
                    tt = 0 if L == 0 else float(np.clip((v @ seg) / L, 0, 1))
                    dist = float(np.hypot(*(v - tt * seg)))
            if dist < bd:
                best, bd = d, dist
        if best is not None:
            self._remove_gfx(best); self.items.remove(best); self.changed.emit()

    # ------------------------------------------------------------- graphics
    def _pen(self, color=None, w=1.4, style=None):
        return pg.mkPen(color or self.color, width=w, style=style or QtCore.Qt.PenStyle.SolidLine)

    def _add(self, typ, pts, text="", color=None, emit=True):
        d = {"type": typ, "pts": [list(map(float, p)) for p in pts], "text": text, "color": color or self.color, "gfx": []}
        self._build(d)
        self.items.append(d)
        if emit:
            self.changed.emit()
        return d

    def _build(self, d):
        typ, pts, col = d["type"], d["pts"], d["color"]
        P = self.plot
        if typ == "hline":
            ln = pg.InfiniteLine(angle=0, pos=pts[0][1], movable=True, pen=self._pen(col), label="{value:,.6g}",
                                 labelOpts={"position": 0.03, "color": col, "movable": True})
            ln.sigPositionChangeFinished.connect(lambda *_: self.changed.emit())
            P.addItem(ln, ignoreBounds=True); d["gfx"] = [ln]
        elif typ == "vline":
            ln = pg.InfiniteLine(angle=90, pos=pts[0][0], movable=True, pen=self._pen(col, style=QtCore.Qt.PenStyle.DashLine))
            ln.sigPositionChangeFinished.connect(lambda *_: self.changed.emit())
            P.addItem(ln, ignoreBounds=True); d["gfx"] = [ln]
        elif typ == "text":
            ti = pg.TextItem(d["text"], color=col, anchor=(0, 1), border=pg.mkPen(col), fill=pg.mkBrush(C["panel"] + "dd"))
            ti.setPos(pts[0][0], pts[0][1]); P.addItem(ti, ignoreBounds=True); d["gfx"] = [ti]
        elif typ == "rect":
            (ax, ay), (bx, by) = pts
            roi = pg.RectROI([min(ax, bx), min(ay, by)], [abs(bx - ax) or 1, abs(by - ay) or 1e-9], pen=self._pen(col), movable=True, resizable=True,
                             rotatable=False, removable=False)
            roi.setBrush(pg.mkBrush(QtGui.QColor(col).red(), QtGui.QColor(col).green(), QtGui.QColor(col).blue(), 40)) if hasattr(roi, "setBrush") else None
            roi.sigRegionChangeFinished.connect(lambda *_: self.changed.emit())
            P.addItem(roi); d["gfx"] = [roi]
        else:   # trend / ray / fib / measure: a LineSegmentROI + dependent decorations
            roi = pg.LineSegmentROI(pts, pen=self._pen(col), movable=True, rotatable=False, removable=False)
            roi.setZValue(30)
            P.addItem(roi)
            deco = []
            if typ == "ray":
                ext = pg.PlotDataItem(pen=self._pen(col)); P.addItem(ext, ignoreBounds=True); deco.append(ext)
            elif typ == "fib":
                lines = pg.PlotDataItem(pen=self._pen(col, 1.0), connect="pairs"); P.addItem(lines, ignoreBounds=True); deco.append(lines)
                for _ in FIB_LEVELS:
                    ti = pg.TextItem("", color=col, anchor=(1, 1)); P.addItem(ti, ignoreBounds=True); deco.append(ti)
            elif typ == "measure":
                ti = pg.TextItem("", color="#ffffff", anchor=(0.5, 1), fill=pg.mkBrush(col + "cc")); P.addItem(ti, ignoreBounds=True); deco.append(ti)
            d["gfx"] = [roi] + deco
            roi.sigRegionChanged.connect(lambda *_, d=d: self._update_deco(d))
            roi.sigRegionChangeFinished.connect(lambda *_: self.changed.emit())
            self._update_deco(d)

    def _roi_pts(self, roi):
        out = []
        for h in roi.getHandles():
            p = roi.mapToView(h.pos()) if hasattr(roi, "mapToView") else roi.mapSceneToParent(h.scenePos())
            out.append([float(p.x()), float(p.y())])
        return out

    def _sync_from_gfx(self, d):
        g = d.get("gfx") or []
        if not g:
            return
        typ = d["type"]
        try:
            if typ == "hline":
                d["pts"][0][1] = float(g[0].value())
            elif typ == "vline":
                d["pts"][0][0] = float(g[0].value())
            elif typ == "text":
                p = g[0].pos(); d["pts"][0] = [float(p.x()), float(p.y())]
            elif typ == "rect":
                p, s = g[0].pos(), g[0].size(); d["pts"] = [[float(p.x()), float(p.y())], [float(p.x() + s.x()), float(p.y() + s.y())]]
            else:
                pts = self._roi_pts(g[0])
                if len(pts) == 2:
                    d["pts"] = pts
        except Exception:
            pass

    def _update_deco(self, d):
        self._sync_from_gfx(d)
        typ, col = d["type"], d["color"]
        (ax, ay), (bx, by) = d["pts"]
        deco = d["gfx"][1:]
        if typ == "ray" and deco:
            n = len(self.df) if self.df is not None else 1000
            far = bx + (n + 500 - bx) if bx >= ax else bx - (bx + 500)
            if bx != ax:
                fy = ay + (by - ay) * (far - ax) / (bx - ax)
                deco[0].setData([bx, far], [by, fy])
        elif typ == "fib" and deco:
            xs, ys = [], []
            x0, x1 = min(ax, bx), max(ax, bx) + (max(ax, bx) - min(ax, bx)) * 0.5 + 5
            for j, lv in enumerate(FIB_LEVELS):
                y = by - (by - ay) * lv
                xs += [x0, x1]; ys += [y, y]
                ti = deco[1 + j]; ti.setPos(x1, y); ti.setText(f"{lv:g}  {y:,.6g}")
            deco[0].setData(np.asarray(xs, float), np.asarray(ys, float))
        elif typ == "measure" and deco:
            bars = abs(bx - ax); pct = (by / ay - 1) * 100 if ay else 0
            span = ""
            if self.df is not None and len(self.df) > 1:
                secs = bars * self._bar_delta().total_seconds()
                span = f"{secs / 3600:.1f}h" if secs < 86400 * 2 else f"{secs / 86400:.1f}d"
            deco[0].setText(f"{by - ay:+,.6g}  ({pct:+.2f}%)\n{bars:.0f} bars · {span}")
            deco[0].setPos((ax + bx) / 2, max(ay, by))
            deco[0].fill = pg.mkBrush((C["green"] if by >= ay else C["red"]) + "cc")


class IndicatorDialog(QtWidgets.QDialog):
    """Pick an indicator + edit its parameters. Returns (key, params) via .result_value."""

    def __init__(self, parent=None):
        super().__init__(parent)
        from core import chart_indicators as CI
        self.CI = CI
        self.setWindowTitle(t("ind_add"))
        self.resize(560, 520)
        v = QtWidgets.QVBoxLayout(self)
        self.search = QtWidgets.QLineEdit(); self.search.setPlaceholderText(t("search"))
        v.addWidget(self.search)
        split = QtWidgets.QHBoxLayout(); v.addLayout(split, 1)
        self.lst = QtWidgets.QListWidget(); split.addWidget(self.lst, 3)
        right = QtWidgets.QVBoxLayout(); split.addLayout(right, 2)
        self.desc = QtWidgets.QLabel(""); self.desc.setWordWrap(True); self.desc.setObjectName("subtitle"); right.addWidget(self.desc)
        self.form = QtWidgets.QFormLayout(); right.addLayout(self.form); right.addStretch()
        bb = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Ok | QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept); bb.rejected.connect(self.reject); v.addWidget(bb)
        self.names = CI.names()
        self.cat = {d["key"]: d for d in __import__("core.indicators2", fromlist=["INDICATOR_CATALOG"]).INDICATOR_CATALOG}
        self._fill()
        self.search.textChanged.connect(self._fill)
        self.lst.currentItemChanged.connect(self._pick)
        self.lst.itemDoubleClicked.connect(lambda *_: self.accept())
        self.widgets = {}
        self.result_value = None
        if self.lst.count():
            self.lst.setCurrentRow(0)

    def _fill(self):
        q = self.search.text().lower().strip()
        self.lst.clear()
        for key, en, fa, grp in self.names:
            label = f"{fa if I18N.lang == 'fa' else en}   ·  {grp}"
            if q and q not in (key + en + fa + grp).lower():
                continue
            it = QtWidgets.QListWidgetItem(label); it.setData(QtCore.Qt.ItemDataRole.UserRole, key); self.lst.addItem(it)

    def _pick(self, cur, prev=None):
        while self.form.rowCount():
            self.form.removeRow(0)
        self.widgets = {}
        if cur is None:
            return
        key = cur.data(QtCore.Qt.ItemDataRole.UserRole)
        d = self.cat.get(key)
        if d:
            self.desc.setText((d["how_fa"] + "\n" + d["read_fa"]) if I18N.lang == "fa" else (d["how_en"] + "\n" + d["read_en"]))
        else:
            self.desc.setText(key)
        _, params = self.CI.SPECS[key]
        for k, val in params.items():
            if isinstance(val, int):
                w = QtWidgets.QSpinBox(); w.setRange(0, 5000); w.setValue(val)
            else:
                w = QtWidgets.QDoubleSpinBox(); w.setRange(0, 10000); w.setDecimals(3); w.setSingleStep(0.1); w.setValue(float(val))
            self.widgets[k] = w; self.form.addRow(k, w)

    def accept(self):
        cur = self.lst.currentItem()
        if cur is None:
            return
        self.result_value = (cur.data(QtCore.Qt.ItemDataRole.UserRole), {k: w.value() for k, w in self.widgets.items()})
        super().accept()
