"""ML Lab page — train a market model, show what it learned (feature importance), how reliable it is (OOS AUC/lift/calibration),
and current probabilities. Also meta-labels strategy signals."""
import time
import numpy as np
from PyQt6 import QtCore, QtGui, QtWidgets

import strategies as S
from core import ml
from core.data import TIMEFRAMES
from .theme import C, t, I18N
from .widgets import Card, StatTile, make_table, cell, ncell, Worker, color_for
from .pages import SymbolBar, load_data, strat_name


class BarChart(QtWidgets.QWidget):
    """Tiny horizontal bar chart (no external deps)."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.items = []
        self.setMinimumHeight(220)

    def set(self, items):
        self.items = items[:14]
        self.update()

    def paintEvent(self, e):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        if not self.items:
            return
        w, h = self.width(), self.height()
        rowh = min(22, h / len(self.items))
        mx = max(v for _, v in self.items) or 1
        lw = 170
        f = p.font(); f.setPointSize(9); p.setFont(f)
        for i, (name, v) in enumerate(self.items):
            y = i * rowh
            p.setPen(QtGui.QColor(C["text"]))
            p.drawText(QtCore.QRectF(0, y, lw - 8, rowh), QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter, name)
            bw = (w - lw - 50) * v / mx
            grad = QtGui.QLinearGradient(lw, 0, lw + bw, 0)
            grad.setColorAt(0, QtGui.QColor(C["accent"])); grad.setColorAt(1, QtGui.QColor(C["accent2"]))
            p.fillRect(QtCore.QRectF(lw, y + 4, bw, rowh - 8), grad)
            p.setPen(QtGui.QColor(C["muted"]))
            p.drawText(QtCore.QRectF(lw + bw + 6, y, 60, rowh), QtCore.Qt.AlignmentFlag.AlignVCenter, f"{v:.3f}")


class MLPage(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.bundle = None
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(16, 12, 16, 12)
        v.setSpacing(10)
        title = QtWidgets.QLabel(t("ml_title"))
        title.setObjectName("h1")
        v.addWidget(title)
        sub = QtWidgets.QLabel(t("ml_sub"))
        sub.setObjectName("subtitle")
        sub.setWordWrap(True)
        v.addWidget(sub)

        self.bar = SymbolBar(with_strategy=False)
        self.bar.btn.setVisible(False)
        self.bar.sym.setMinimumWidth(230)
        self.bar.changed.connect(self.load_saved)
        top = QtWidgets.QHBoxLayout()
        top.addWidget(self.bar)
        self.horizon = QtWidgets.QSpinBox(); self.horizon.setRange(3, 200); self.horizon.setValue(24)
        self.ktp = QtWidgets.QDoubleSpinBox(); self.ktp.setRange(0.5, 10); self.ktp.setValue(2.0); self.ktp.setSingleStep(0.5)
        self.ksl = QtWidgets.QDoubleSpinBox(); self.ksl.setRange(0.5, 10); self.ksl.setValue(1.0); self.ksl.setSingleStep(0.5)
        for w_, lbl in ((self.horizon, t("ml_horizon")), (self.ktp, "TP ×ATR"), (self.ksl, "SL ×ATR")):
            top.addWidget(QtWidgets.QLabel(lbl)); top.addWidget(w_)
        self.btn = QtWidgets.QPushButton("🧠  " + t("ml_train"))
        self.btn.setObjectName("primary")
        self.btn.clicked.connect(self.train)
        top.addWidget(self.btn)
        self.load_btn = QtWidgets.QPushButton(t("ml_load"))
        self.load_btn.clicked.connect(self.load_saved)
        top.addWidget(self.load_btn)
        top.addStretch()
        v.addLayout(top)
        self.prog = QtWidgets.QProgressBar(); self.prog.setRange(0, 0); self.prog.setVisible(False)
        v.addWidget(self.prog)
        self.status = QtWidgets.QLabel(t("ml_hint")); self.status.setObjectName("subtitle"); self.status.setWordWrap(True)
        v.addWidget(self.status)

        tiles = QtWidgets.QHBoxLayout()
        self.t_pl = StatTile(t("ml_p_long"), color=C["green"])
        self.t_ps = StatTile(t("ml_p_short"), color=C["red"])
        self.t_auc = StatTile("AUC (OOS)")
        self.t_lift = StatTile(t("ml_lift"))
        self.t_base = StatTile(t("ml_base"))
        self.t_n = StatTile(t("ml_samples"))
        for x in (self.t_pl, self.t_ps, self.t_auc, self.t_lift, self.t_base, self.t_n):
            tiles.addWidget(x)
        v.addLayout(tiles)

        split = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        c1 = Card(t("ml_learned"))
        self.groups = QtWidgets.QLabel("—"); self.groups.setWordWrap(True)
        c1.v.addWidget(self.groups)
        self.chart = BarChart()
        c1.v.addWidget(self.chart, 1)
        split.addWidget(c1)
        c2 = Card(t("ml_calib"))
        self.cal = make_table([t("ml_pred"), t("ml_actual"), "n", t("ml_verdict")])
        c2.v.addWidget(self.cal)
        self.verdict = QtWidgets.QLabel(""); self.verdict.setWordWrap(True)
        c2.v.addWidget(self.verdict)
        split.addWidget(c2)
        c3 = Card(t("ml_meta"))
        self.meta = make_table([t("strategy"), t("side"), t("fresh"), "P(win) ML", t("ml_advice")])
        self.meta.itemDoubleClicked.connect(self._open)
        c3.v.addWidget(self.meta, 1)
        split.addWidget(c3)
        split.setSizes([520, 380, 480])
        v.addWidget(split, 1)
        self.saved_lbl = QtWidgets.QLabel(""); self.saved_lbl.setObjectName("subtitle")
        v.addWidget(self.saved_lbl)
        self._list_saved()

    # ------------------------------------------------------------ actions
    def _list_saved(self):
        idx = ml.list_models()
        if idx:
            self.saved_lbl.setText(t("ml_saved") + ": " + " · ".join(f"{k} (AUC {v['auc_long']:.2f}/{v['auc_short']:.2f})" for k, v in list(idx.items())[:8]))

    def train(self):
        sym, tf = self.bar.symbol(), self.bar.timeframe()
        H, ktp, ksl = self.horizon.value(), self.ktp.value(), self.ksl.value()
        self.btn.setEnabled(False); self.prog.setVisible(True)
        self.status.setText(t("ml_training"))

        def work(progress=None):
            df, ok = load_data(sym, tf)
            b = ml.train_market_model(df, horizon=H, k_tp=ktp, k_sl=ksl, progress=lambda s: progress(0, s) if progress else None)
            ml.save_bundle(sym, tf, b)
            return df, b

        self.w = Worker(work)
        self.w.progress.connect(lambda p, s: self.status.setText(f"{t('ml_training')} — {s}"))
        self.w.done.connect(self._done)
        self.w.error.connect(lambda e: (self._reset(), QtWidgets.QMessageBox.warning(self, "Error", e)))
        self.w.start()

    def load_saved(self):
        sym, tf = self.bar.symbol(), self.bar.timeframe()
        b = ml.load_bundle(sym, tf)
        if not b:
            self.status.setText(t("ml_none"))
            return
        df, ok = load_data(sym, tf)
        self._done((df, b))

    def _reset(self):
        self.btn.setEnabled(True); self.prog.setVisible(False)

    def _done(self, res):
        df, b = res
        self._reset()
        self.bundle = b
        self.df = df
        L, Sh = b["long"], b["short"]
        self.t_pl.set(f"{L['p_now'] * 100:.0f}%" if L["p_now"] == L["p_now"] else "—")
        self.t_ps.set(f"{Sh['p_now'] * 100:.0f}%" if Sh["p_now"] == Sh["p_now"] else "—")
        auc = np.nanmean([L["auc"], Sh["auc"]])
        self.t_auc.set(f"{auc:.3f}", C["green"] if auc > 0.56 else (C["yellow"] if auc > 0.52 else C["red"]))
        lift = np.nanmean([L["lift_top20"], Sh["lift_top20"]])
        self.t_lift.set(f"×{lift:.2f}", C["green"] if lift > 1.15 else (C["yellow"] if lift > 1.05 else C["red"]))
        self.t_base.set(f"{L['base_rate'] * 100:.0f}% / {Sh['base_rate'] * 100:.0f}%")
        self.t_n.set(f"{L['n_train']:,}")
        g = b["group_importance"]
        self.groups.setText("  ".join(f"<b style='color:{C['accent2']}'>{k}</b> {v * 100:.0f}%" for k, v in g.items()))
        imp = {}
        for side in ("long", "short"):
            for k, v in b[side]["importances"].items():
                imp[k] = imp.get(k, 0) + max(v, 0)
        self.chart.set(sorted(imp.items(), key=lambda x: -x[1]))
        # calibration
        self.cal.setSortingEnabled(False); self.cal.setRowCount(0)
        for side, lbl in (("long", t("long")), ("short", t("short"))):
            for pred, act, n in b[side]["calibration"]:
                r = self.cal.rowCount(); self.cal.insertRow(r)
                self.cal.setItem(r, 0, cell(f"{lbl} {pred * 100:.0f}%"))
                self.cal.setItem(r, 1, ncell(act * 100, "{:.0f}%", color_for(act - b[side]["base_rate"])))
                self.cal.setItem(r, 2, ncell(n, "{:.0f}"))
                ok = abs(pred - act) < 0.06
                self.cal.setItem(r, 3, cell("✔" if ok else "≈", C["green"] if ok else C["yellow"]))
        self.cal.resizeColumnsToContents()
        if auc < 0.52:
            vtxt, vc = t("ml_v_noise"), C["red"]
        elif auc < 0.56:
            vtxt, vc = t("ml_v_weak"), C["yellow"]
        else:
            vtxt, vc = t("ml_v_ok"), C["green"]
        self.verdict.setText(f"<b style='color:{vc}'>{vtxt}</b>")
        self.status.setText(f"{self.bar.symbol()} {self.bar.timeframe()} · H={b['horizon']} · TP {b['k_tp']}×ATR / SL {b['k_sl']}×ATR · "
                            f"{time.strftime('%H:%M', time.localtime(b['ts']))}")
        self._meta_label()
        self._list_saved()

    def _meta_label(self):
        """Run every strategy on the current data and attach ML P(win) to recent signals."""
        self.meta.setSortingEnabled(False); self.meta.setRowCount(0)
        df = self.df
        pl, ps = ml.predict(self.bundle, df)
        n = len(df)
        rows = []
        for cls in S.ALL_STRATEGIES:
            try:
                res = cls().run(df)
            except Exception:
                continue
            sig = res.signal.values
            idx = np.where(sig[-5:] != 0)[0]
            if len(idx) == 0:
                continue
            i = n - 5 + idx[-1]
            side = int(sig[i])
            p = float(pl.iloc[i] if side == 1 else ps.iloc[i])
            base = self.bundle["long" if side == 1 else "short"]["base_rate"]
            rows.append((cls, side, n - 1 - i, p, base))
        rows.sort(key=lambda r: -r[3])
        for cls, side, ago, p, base in rows:
            r = self.meta.rowCount(); self.meta.insertRow(r)
            it = cell(strat_name(cls)); it.setData(QtCore.Qt.ItemDataRole.UserRole, cls.id)
            self.meta.setItem(r, 0, it)
            self.meta.setItem(r, 1, cell(t("long") if side == 1 else t("short"), C["green"] if side == 1 else C["red"]))
            self.meta.setItem(r, 2, ncell(ago, "{:.0f} " + t("bars_ago")))
            self.meta.setItem(r, 3, ncell(p * 100, "{:.0f}%", color_for(p - base)))
            ratio = p / max(base, 1e-6)
            adv = t("ml_take") if ratio > 1.25 else (t("ml_skip") if ratio < 0.85 else t("ml_neutral"))
            self.meta.setItem(r, 4, cell(adv, C["green"] if ratio > 1.25 else (C["red"] if ratio < 0.85 else C["muted"])))
        self.meta.setSortingEnabled(True)

    def _open(self, item):
        sid = self.meta.item(item.row(), 0).data(QtCore.Qt.ItemDataRole.UserRole)
        self.window().open_chart(self.bar.symbol(), self.bar.timeframe(), sid)
