"""Chart Vision — give the app a chart IMAGE (screenshot / photo); it reconstructs the candles with OpenCV, runs the
numeric pattern library on them and explains what it sees (FA/EN). Optional YOLO hook and a self-test model card."""
import os
import numpy as np
import pandas as pd
from PyQt6 import QtCore, QtGui, QtWidgets

from core import vision as V
from .theme import C, t, I18N
from .widgets import Card, StatTile, make_table, cell, ncell, Worker, color_for


def _to_pixmap(bgr):
    rgb = np.ascontiguousarray(bgr[..., ::-1])
    h, w, _ = rgb.shape
    img = QtGui.QImage(rgb.data, w, h, 3 * w, QtGui.QImage.Format.Format_RGB888)
    return QtGui.QPixmap.fromImage(img.copy())


class DropLabel(QtWidgets.QLabel):
    dropped = QtCore.pyqtSignal(str)

    def __init__(self, text):
        super().__init__(text)
        self.setAcceptDrops(True)
        self.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.setMinimumHeight(320)
        self.setStyleSheet(f"border:2px dashed {C['border']}; border-radius:12px; color:{C['muted']}; font-size:14px;")

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls() or e.mimeData().hasImage():
            e.acceptProposedAction()

    def dropEvent(self, e):
        if e.mimeData().hasUrls():
            self.dropped.emit(e.mimeData().urls()[0].toLocalFile())
        elif e.mimeData().hasImage():
            img = QtGui.QImage(e.mimeData().imageData())
            p = os.path.join(os.path.expanduser("~"), ".protrader_clip.png"); img.save(p); self.dropped.emit(p)


class VisionPage(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.path = None; self.ex = None
        v = QtWidgets.QVBoxLayout(self); v.setContentsMargins(16, 12, 16, 12); v.setSpacing(10)
        title = QtWidgets.QLabel(t("vis_title")); title.setObjectName("h1"); v.addWidget(title)
        sub = QtWidgets.QLabel(t("vis_sub")); sub.setObjectName("subtitle"); sub.setWordWrap(True); v.addWidget(sub)
        row = QtWidgets.QHBoxLayout()
        self.open_btn = QtWidgets.QPushButton("📂 " + t("vis_open")); self.open_btn.setObjectName("primary"); self.open_btn.clicked.connect(self.open_file)
        self.paste_btn = QtWidgets.QPushButton("📋 " + t("vis_paste")); self.paste_btn.clicked.connect(self.paste)
        self.demo_btn = QtWidgets.QPushButton("🎲 " + t("vis_demo")); self.demo_btn.clicked.connect(self.demo)
        self.test_btn = QtWidgets.QPushButton("🧪 " + t("vis_selftest")); self.test_btn.clicked.connect(self.selftest)
        row.addWidget(self.open_btn); row.addWidget(self.paste_btn); row.addWidget(self.demo_btn); row.addWidget(self.test_btn)
        row.addSpacing(20)
        row.addWidget(QtWidgets.QLabel(t("vis_cal")))
        self.cal_top = QtWidgets.QDoubleSpinBox(); self.cal_top.setRange(0, 1e9); self.cal_top.setDecimals(4); self.cal_top.setPrefix(t("vis_cal_top") + " ")
        self.cal_bot = QtWidgets.QDoubleSpinBox(); self.cal_bot.setRange(0, 1e9); self.cal_bot.setDecimals(4); self.cal_bot.setPrefix(t("vis_cal_bot") + " ")
        self.cal_btn = QtWidgets.QPushButton(t("vis_apply")); self.cal_btn.clicked.connect(self.analyse)
        row.addWidget(self.cal_top); row.addWidget(self.cal_bot); row.addWidget(self.cal_btn); row.addStretch(1)
        v.addLayout(row)
        tiles = QtWidgets.QHBoxLayout()
        self.t_n = StatTile(t("vis_candles")); self.t_theme = StatTile(t("vis_theme")); self.t_trend = StatTile(t("trend")); self.t_last = StatTile(t("vis_last")); self.t_rsi = StatTile("RSI"); self.t_conf = StatTile(t("vis_conf"))
        for x in (self.t_n, self.t_theme, self.t_trend, self.t_last, self.t_rsi, self.t_conf):
            tiles.addWidget(x)
        v.addLayout(tiles)
        split = QtWidgets.QHBoxLayout()
        left = QtWidgets.QVBoxLayout()
        self.img_lbl = DropLabel(t("vis_drop")); self.img_lbl.dropped.connect(self.load_path)
        self.scroll = QtWidgets.QScrollArea(); self.scroll.setWidgetResizable(True); self.scroll.setWidget(self.img_lbl)
        left.addWidget(self.scroll, 3)
        self.recon = QtWidgets.QLabel(); self.recon.setMinimumHeight(140); self.recon.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        rc = Card(t("vis_recon")); rc.add(self.recon); left.addWidget(rc, 1)
        split.addLayout(left, 3)
        right = QtWidgets.QVBoxLayout()
        self.txt = QtWidgets.QTextEdit(); self.txt.setReadOnly(True); self.txt.setMinimumWidth(380)
        ec = Card(t("vis_explain")); ec.add(self.txt)
        qrow = QtWidgets.QHBoxLayout()
        self.q_edit = QtWidgets.QLineEdit(); self.q_edit.setPlaceholderText(t("vis_ask_ph")); self.q_edit.returnPressed.connect(self.ask)
        self.q_btn = QtWidgets.QPushButton("💬 " + t("vis_ask")); self.q_btn.clicked.connect(self.ask)
        qrow.addWidget(self.q_edit, 1); qrow.addWidget(self.q_btn)
        qw = QtWidgets.QWidget(); qw.setLayout(qrow); ec.add(qw)
        right.addWidget(ec, 2)
        self._ctx = None
        self.tbl = make_table([t("vis_pattern"), t("vis_kind"), t("vis_where"), t("vis_stat")])
        pc = Card(t("vis_patterns")); pc.add(self.tbl); right.addWidget(pc, 2)
        self.card_tbl = make_table([t("vis_theme"), t("vis_found"), t("vis_diracc"), t("vis_corr")])
        mc = Card(t("vis_modelcard")); mc.add(self.card_tbl); right.addWidget(mc, 1)
        split.addLayout(right, 2)
        v.addLayout(split, 1)

    # ------------------------------------------------------------------ input
    def open_file(self):
        p, _ = QtWidgets.QFileDialog.getOpenFileName(self, t("vis_open"), "", "Images (*.png *.jpg *.jpeg *.bmp *.webp)")
        if p:
            self.load_path(p)

    def paste(self):
        cb = QtWidgets.QApplication.clipboard()
        img = cb.image()
        if img.isNull():
            QtWidgets.QMessageBox.information(self, "Clipboard", t("vis_noclip")); return
        p = os.path.join(os.path.expanduser("~"), ".protrader_clip.png"); img.save(p); self.load_path(p)

    def demo(self):
        import cv2
        th = list(V.THEMES)[np.random.randint(len(V.THEMES))]
        img, _ = V.synthetic_chart(70, th, seed=int(np.random.randint(1000)))
        p = os.path.join(os.path.expanduser("~"), ".protrader_demo.png"); cv2.imwrite(p, img); self.load_path(p)

    def load_path(self, p):
        self.path = p
        self.analyse()

    def ask(self):
        q = self.q_edit.text().strip()
        if not q or not self._ctx:
            return
        from core import analyst as AN
        ans, backend = AN.ask(q, self._ctx, I18N.lang)
        self.txt.append(f"\n\n❓ {q}\n💬 [{backend}] {ans}")
        self.txt.moveCursor(QtGui.QTextCursor.MoveOperation.End)

    # ------------------------------------------------------------------ analysis
    def analyse(self):
        if not self.path:
            return
        top, bot = self.cal_top.value(), self.cal_bot.value()
        lang = I18N.lang
        path = self.path
        self.open_btn.setEnabled(False)

        def work(progress=None):
            from core import vision2 as V2
            u = V2.understand(path, lang=lang, progress=progress)
            ex = u["ex"]; crop = ex["crop"]
            if top and bot and top != bot:            # manual calibration overrides OCR
                df = V.calibrate(ex["df"], px_top=crop[1], price_top=top, px_bot=crop[3], price_bot=bot)
                out = V.analyse_chart(df, lang)
            else:
                df = u["df"]; out = u["numeric"]
            text = V.describe(out, lang)
            fa = lang == "fa"
            extra = []
            if u["calibration"]:
                c = u["calibration"]
                extra.append((f"✓ Price axis read automatically ({c['n_ticks']} ticks, fit error {c['max_resid_pct']:.2f}%) → last close ≈ {df['close'].iloc[-1]:,.2f}"
                              if not fa else f"✓ محور قیمت خودکار خوانده شد ({c['n_ticks']} برچسب، خطای برازش {c['max_resid_pct']:.2f}٪) → آخرین بسته ≈ {df['close'].iloc[-1]:,.2f}"))
            if u["volume"]:
                extra.append("✓ Volume pane detected and attached to the candles." if not fa else "✓ پنل حجم شناسایی و به کندل‌ها متصل شد.")
            if u["overlay_text"]:
                extra.append(("Drawn objects / indicators on the chart:" if not fa else "اشیای کشیده‌شده / اندیکاتورهای روی نمودار:") + "\n  • " + "\n  • ".join(u["overlay_text"][:8]))
            wc = u["whole_chart"]
            if wc:
                nm = (lambda k: V2.CLASS_FA.get(k, k)) if fa else (lambda k: k)
                extra.append((f"Image classifier (HOG+SVM, trained on synthetic charts, hold-out acc {u['detector_meta'].get('holdout_acc', 0) * 100:.0f}%): whole chart looks like "
                              if not fa else f"طبقه‌بند تصویری (HOG+SVM آموزش‌دیده روی نمودارهای مصنوعی، دقت آزمون {u['detector_meta'].get('holdout_acc', 0) * 100:.0f}٪): کل نمودار شبیه ")
                             + ", ".join(f"{nm(k)} {p_ * 100:.0f}%" for k, p_ in wc))
            if u["image_patterns"]:
                extra.append(("Localised image patterns (sliding window + NMS): " if not fa else "الگوهای تصویری موضعی (پنجرهٔ لغزان + NMS): ")
                             + ", ".join(f"{(d['name_fa'] if fa else d['name'])} {d['conf'] * 100:.0f}% @bars {d['i0']}–{d['i1']}" for d in u["image_patterns"]))
            text = text + "\n\n" + "\n".join(extra)
            yolo = V.yolo_detect(path)
            ex = dict(ex); ex["annotated"] = u["annotated"]
            out = dict(out); out["image_patterns"] = u["image_patterns"]
            from core import analyst as AN
            u2 = dict(u); u2["numeric"] = out; u2["df"] = df
            brief, meta = AN.report(dict(vision=u2, calibrated=bool(top and bot)), lang)
            self._ctx = dict(vision=u2, calibrated=bool(top and bot))
            text = text + "\n\n" + brief
            return ex, df, out, text, yolo
        self.w = Worker(work); self.w.done.connect(self._show)
        self.w.error.connect(lambda e: (self.open_btn.setEnabled(True), self.txt.setPlainText(t("vis_fail") + "\n" + e))); self.w.start()

    def _show(self, r):
        ex, df, out, text, yolo = r
        self.open_btn.setEnabled(True)
        self.ex = ex
        pm = _to_pixmap(ex["annotated"])
        self.img_lbl.setPixmap(pm.scaledToWidth(min(pm.width(), max(600, self.scroll.width() - 30)), QtCore.Qt.TransformationMode.SmoothTransformation))
        self.img_lbl.setStyleSheet("")
        self.t_n.set(str(len(df)) + (f"  (⚠ {ex['dropped_clipped']} clipped)" if ex.get("dropped_clipped") else ""))
        self.t_theme.set(ex["theme"])
        tr = out["trend"]
        self.t_trend.set({"up": t("vis_up"), "down": t("vis_down"), "range": t("vis_range")}[tr], C["green"] if tr == "up" else (C["red"] if tr == "down" else C["muted"]))
        lc = out["last_candle"]
        self.t_last.set((t("long") if lc["bull"] else t("short")) + f" · body {lc['body_ratio'] * 100:.0f}%", C["green"] if lc["bull"] else C["red"])
        self.t_rsi.set(f"{out['rsi']:.0f}" if out["rsi"] == out["rsi"] else "—")
        conf = float(np.mean([b["conf"] for b in ex["boxes"]])) if ex["boxes"] else 0
        self.t_conf.set(f"{conf * 100:.0f}%", C["green"] if conf > 0.8 else C["yellow"])
        self.txt.setMarkdown(text.replace('\n', '  \n') + ("\n\nYOLO: " + ", ".join(f"{d['name']} {d['conf']:.2f}" for d in yolo) if yolo else ""))
        self.tbl.setSortingEnabled(False); self.tbl.setRowCount(0)
        for name, sgn, i in out.get("candles", []):
            r_ = self.tbl.rowCount(); self.tbl.insertRow(r_)
            self.tbl.setItem(r_, 0, cell(name)); self.tbl.setItem(r_, 1, cell(t("vis_candle_pat")))
            self.tbl.setItem(r_, 2, cell(f"bar {i}")); self.tbl.setItem(r_, 3, cell("bullish" if sgn > 0 else "bearish", C["green"] if sgn > 0 else C["red"]))
        for p in out.get("chart_patterns", []):
            r_ = self.tbl.rowCount(); self.tbl.insertRow(r_)
            if isinstance(p, dict):
                nm = p.get("name_fa") if I18N.lang == "fa" and p.get("name_fa") else p.get("name", "")
                self.tbl.setItem(r_, 0, cell(str(nm)))
                self.tbl.setItem(r_, 1, cell(t("vis_chart_pat")))
                self.tbl.setItem(r_, 2, cell(f"bar {p.get('i_start', '')}–{p.get('i_end', p.get('end', ''))}"))
                side = str(p.get("side", p.get("dir", "")))
                st = p.get("stats") or {}
                stat = f"fail {st.get('fail', '?')}% · move {st.get('move', '?')}% · rank {st.get('rank', '?')}" if isinstance(st, dict) and st else ""
                col = C["green"] if side in ("long", "bull", "bullish", "buy") else (C["red"] if side in ("short", "bear", "bearish", "sell") else None)
                self.tbl.setItem(r_, 3, cell(f"{side} {stat}".strip(), col))
            else:
                self.tbl.setItem(r_, 0, cell(str(p))); self.tbl.setItem(r_, 1, cell(t("vis_chart_pat")))
        for d in out.get("image_patterns", []):
            r_ = self.tbl.rowCount(); self.tbl.insertRow(r_)
            self.tbl.setItem(r_, 0, cell(d["name_fa"] if I18N.lang == "fa" else d["name"]))
            self.tbl.setItem(r_, 1, cell(t("vis_img_pat")))
            self.tbl.setItem(r_, 2, cell(f"bar {d['i0']}–{d['i1']}"))
            col = C["green"] if d["side"] == "bull" else (C["red"] if d["side"] == "bear" else None)
            self.tbl.setItem(r_, 3, cell(f"{d['side']} · conf {d['conf'] * 100:.0f}%", col))
        self.tbl.setSortingEnabled(True)
        self._draw_recon(df)

    def _draw_recon(self, df):
        w, h = max(300, self.recon.width() - 10), max(120, self.recon.height() - 10)
        pm = QtGui.QPixmap(w, h); pm.fill(QtGui.QColor(C["bg2"] if "bg2" in C else "#0f131a"))
        p = QtGui.QPainter(pm)
        n = len(df); lo, hi = df["low"].min(), df["high"].max(); span = max(hi - lo, 1e-9)
        cw = max(2, int(w / (n + 2)))
        for i in range(n):
            o, hh, ll, c = df.iloc[i][["open", "high", "low", "close"]]
            x = int((i + 1) * w / (n + 2))
            y = lambda v: int(h - (v - lo) / span * (h - 10) - 5)
            col = QtGui.QColor(C["green"]) if c >= o else QtGui.QColor(C["red"])
            p.setPen(col); p.drawLine(x, y(hh), x, y(ll))
            p.fillRect(x - cw // 2, min(y(o), y(c)), cw, max(1, abs(y(o) - y(c))), col)
        p.end()
        self.recon.setPixmap(pm)

    # ------------------------------------------------------------------ model card
    def selftest(self):
        self.test_btn.setEnabled(False)

        def work():
            return V.self_test(n_per=3)
        self.w2 = Worker(work); self.w2.done.connect(self._show_card)
        self.w2.error.connect(lambda e: (self.test_btn.setEnabled(True), QtWidgets.QMessageBox.warning(self, "Error", e))); self.w2.start()

    def _show_card(self, df):
        self.test_btn.setEnabled(True)
        self.card_tbl.setSortingEnabled(False); self.card_tbl.setRowCount(0)
        g = df.groupby("theme").agg(found=("found", "mean"), truth=("truth", "mean"), dir_acc=("dir_acc", "mean"), corr=("close_corr", "mean"))
        for th, r in g.iterrows():
            i = self.card_tbl.rowCount(); self.card_tbl.insertRow(i)
            self.card_tbl.setItem(i, 0, cell(th)); self.card_tbl.setItem(i, 1, cell(f"{r['found']:.0f}/{r['truth']:.0f}"))
            self.card_tbl.setItem(i, 2, ncell(r["dir_acc"] * 100, "{:.0f}%", C["green"] if r["dir_acc"] > 0.9 else C["yellow"]))
            self.card_tbl.setItem(i, 3, ncell(r["corr"], "{:.3f}", C["green"] if r["corr"] > 0.98 else C["yellow"]))
        self.card_tbl.setSortingEnabled(True)
