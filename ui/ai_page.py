"""AI Desk — Phase 11: forecasting desk (Prophet/Darts/sktime-style models vs naive), news sentiment (VADER/FinBERT-style),
RL agent lab (TensorTrade/SB3-style env) and engine parity (Backtrader/Zipline/LEAN/FreqAI concepts). Every tab shows an
honest verdict against a baseline."""
import numpy as np
import pandas as pd
from PyQt6 import QtCore, QtGui, QtWidgets

import strategies as S
from core import forecast as F, sentiment as SE, rl as RL, engines as E
from core.data import UNIVERSE
from .theme import C, t, I18N
from .widgets import Card, StatTile, make_table, cell, ncell, Worker, color_for
from .pages import SymbolBar, load_data, strat_name


class MiniPlot(QtWidgets.QLabel):
    """tiny painter-based line chart: history tail + forecast paths + optional band"""

    def __init__(self, h=220):
        super().__init__()
        self.setMinimumHeight(h)
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Expanding)
        self.data = None

    def set(self, hist, paths, band=None, cps=(), overlay=False):
        self.overlay = overlay
        self.data = (np.asarray(hist, float), paths, band, cps)
        self.update()

    def paintEvent(self, ev):
        super().paintEvent(ev)
        if not self.data:
            return
        hist, paths, band, cps = self.data
        w, h = self.width(), self.height()
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        p.fillRect(0, 0, w, h, QtGui.QColor(C.get("bg2", "#0f131a")))
        nh = len(hist); nf = 0 if getattr(self, "overlay", False) else (max(len(v) for v in paths.values()) if paths else 0)
        off = 0 if getattr(self, "overlay", False) else nh
        allv = np.concatenate([hist] + [np.asarray(v, float) for v in paths.values()] + ([band[0], band[1]] if band else []))
        lo, hi = np.nanmin(allv), np.nanmax(allv); span = max(hi - lo, 1e-9)
        X = lambda i: 10 + i * (w - 20) / max(nh + nf - 1, 1)
        Y = lambda v: h - 10 - (v - lo) / span * (h - 20)
        if band is not None:
            poly = QtGui.QPolygonF([QtCore.QPointF(X(nh - 1 + i), Y(v)) for i, v in enumerate(band[1])] + [QtCore.QPointF(X(nh - 1 + i), Y(v)) for i, v in reversed(list(enumerate(band[0])))])
            p.setPen(QtCore.Qt.PenStyle.NoPen); col = QtGui.QColor(C["accent"]); col.setAlpha(50); p.setBrush(col); p.drawPolygon(poly)
        for i in cps:
            if 0 <= i < nh:
                p.setPen(QtGui.QPen(QtGui.QColor(C["yellow"] if "yellow" in C else "#e0b000"), 1, QtCore.Qt.PenStyle.DashLine)); p.drawLine(int(X(i)), 10, int(X(i)), h - 10)
        p.setPen(QtGui.QPen(QtGui.QColor(C["text"]), 2))
        for i in range(1, nh):
            p.drawLine(QtCore.QPointF(X(i - 1), Y(hist[i - 1])), QtCore.QPointF(X(i), Y(hist[i])))
        cols = [C["accent"], C["green"], C["red"], "#d08aff", "#ffa64d", "#4dd2ff", "#c0c0c0", "#ff66aa"]
        for k, (name, v) in enumerate(paths.items()):
            p.setPen(QtGui.QPen(QtGui.QColor(cols[k % len(cols)]), 1.5))
            prev = (X(0), Y(v[0])) if off == 0 else (X(nh - 1), Y(hist[-1]))
            for i, y in enumerate(v):
                cur = (X(off + i), Y(y)); p.drawLine(QtCore.QPointF(*prev), QtCore.QPointF(*cur)); prev = cur
            p.drawText(int(w - 130), 16 + 14 * k, name)
        p.end()


class AIPage(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.workers = []
        v = QtWidgets.QVBoxLayout(self); v.setContentsMargins(16, 12, 16, 12); v.setSpacing(10)
        title = QtWidgets.QLabel(t("ai_title")); title.setObjectName("h1"); v.addWidget(title)
        sub = QtWidgets.QLabel(t("ai_sub")); sub.setObjectName("subtitle"); sub.setWordWrap(True); v.addWidget(sub)
        self.bar = SymbolBar(with_strategy=True); v.addWidget(self.bar)
        self.tabs = QtWidgets.QTabWidget(); v.addWidget(self.tabs, 1)
        self.tabs.addTab(self._fc_tab(), "📈 " + t("ai_tab_fc"))
        self.tabs.addTab(self._sent_tab(), "📰 " + t("ai_tab_sent"))
        self.tabs.addTab(self._rl_tab(), "🤖 " + t("ai_tab_rl"))
        self.tabs.addTab(self._eng_tab(), "⚙ " + t("ai_tab_eng"))
        self.tabs.addTab(self._an_tab(), "🧾 " + t("ai_tab_an"))
        self.status = QtWidgets.QLabel(""); self.status.setObjectName("subtitle"); v.addWidget(self.status)

    def _run(self, fn, done, *a, **kw):
        self.status.setText(t("ai_running"))
        w = Worker(fn, *a, **kw); self.workers.append(w)
        w.done.connect(lambda r, d=done: (d(r), self.status.setText(t("ai_done"))))
        w.error.connect(lambda e: self.status.setText("⚠ " + e))
        w.start()

    # ------------------------------------------------------------------ forecasting
    def _fc_tab(self):
        w = QtWidgets.QWidget(); v = QtWidgets.QVBoxLayout(w)
        row = QtWidgets.QHBoxLayout()
        self.fc_h = QtWidgets.QSpinBox(); self.fc_h.setRange(1, 60); self.fc_h.setValue(10); self.fc_h.setPrefix(t("ai_horizon") + " ")
        self.fc_btn = QtWidgets.QPushButton("▶ " + t("ai_run")); self.fc_btn.setObjectName("primary"); self.fc_btn.clicked.connect(self.run_fc)
        row.addWidget(self.fc_h); row.addWidget(self.fc_btn); row.addStretch(1); v.addLayout(row)
        tiles = QtWidgets.QHBoxLayout()
        self.fc_best = StatTile(t("ai_model")); self.fc_mase = StatTile(t("ai_mase")); self.fc_dir = StatTile(t("ai_diracc")); self.fc_cp = StatTile(t("ai_cp")); self.fc_verdict = StatTile(t("ai_verdict"))
        for x in (self.fc_best, self.fc_mase, self.fc_dir, self.fc_cp, self.fc_verdict):
            tiles.addWidget(x)
        v.addLayout(tiles)
        split = QtWidgets.QHBoxLayout()
        self.fc_plot = MiniPlot(260); c1 = Card(t("ai_fc_band")); c1.add(self.fc_plot); split.addWidget(c1, 3)
        self.fc_tbl = make_table([t("ai_model"), t("ai_mase"), t("ai_rmse"), t("ai_diracc"), t("ai_vsnaive"), t("ai_pval")])
        c2 = Card(t("ai_tab_fc")); c2.add(self.fc_tbl); split.addWidget(c2, 3)
        v.addLayout(split, 1)
        self.fc_q = make_table(["q05", "q25", "q50", "q75", "q95"]); c3 = Card(t("ai_q")); c3.add(self.fc_q); v.addWidget(c3)
        self.fc_note = QtWidgets.QLabel(""); self.fc_note.setWordWrap(True); self.fc_note.setObjectName("subtitle"); v.addWidget(self.fc_note)
        return w

    def run_fc(self):
        sym, tf, h = self.bar.symbol(), self.bar.timeframe(), self.fc_h.value()

        def job():
            df, _ = load_data(sym, tf)
            y = df["close"].values[-1500:]
            res = F.historical_forecasts(y, h=h, n_origins=25)
            panel = F.forecast_panel(y, h=h)
            return dict(y=y, res=res, panel=panel)
        self._run(job, self._fc_done)

    def _fc_done(self, r):
        res, panel, y = r["res"], r["panel"], r["y"]
        self.fc_tbl.setSortingEnabled(False); self.fc_tbl.setRowCount(0)
        for _, row in res.iterrows():
            i = self.fc_tbl.rowCount(); self.fc_tbl.insertRow(i)
            self.fc_tbl.setItem(i, 0, cell(row["model"]))
            self.fc_tbl.setItem(i, 1, ncell(row["MASE"], "{:.3f}", color_for(1 - row["MASE"])))
            self.fc_tbl.setItem(i, 2, ncell(row["RMSE"], "{:.4f}"))
            self.fc_tbl.setItem(i, 3, ncell(row["dir_acc"] * 100, "{:.1f}%", color_for(row["dir_acc"] - 0.5)))
            self.fc_tbl.setItem(i, 4, ncell(row["vs_naive"], "{:.3f}", color_for(1 - row["vs_naive"])))
            self.fc_tbl.setItem(i, 5, ncell(row.get("dir_pval", np.nan), "{:.3f}"))
        self.fc_tbl.setSortingEnabled(True)
        best = res.sort_values("MASE").iloc[0]
        self.fc_best.set(best["model"]); self.fc_mase.set(f"{best['MASE']:.3f}", color_for(1 - best["MASE"]))
        self.fc_dir.set(f"{best['dir_acc'] * 100:.1f}%", color_for(best["dir_acc"] - 0.5))
        self.fc_cp.set(str(len(panel["changepoints"])))
        good = bool((res[res.model != "naive"]["vs_naive"] < 0.97).any())
        self.fc_verdict.set("✓" if good else "✗", C["green"] if good else C["red"])
        self.fc_note.setText(t("ai_fc_note").format(n=int(best["n"])) + "\n" + (t("ai_fc_good") if good else t("ai_fc_bad")))
        tail = y[-80:]
        paths = {k: v for k, v in panel["forecasts"].items() if k in ("naive", "theta", "holt", "prophet_like", "nbeats_mlp")}
        pr = panel["prophet"]
        cps = [c[0] - (len(y) - 80) for c in panel["changepoints"] if c[0] >= len(y) - 80]
        self.fc_plot.set(tail, paths, (pr["lo"], pr["hi"]), cps)
        q = panel["quantiles"]; self.fc_q.setRowCount(0)
        keys = sorted(q.keys(), key=float)
        self.fc_q.setColumnCount(len(keys)); self.fc_q.setHorizontalHeaderLabels([f"q{int(round(float(k) * 100)):02d}" for k in keys])
        for step in range(len(q[keys[0]])):
            i = self.fc_q.rowCount(); self.fc_q.insertRow(i)
            for j, k in enumerate(keys):
                self.fc_q.setItem(i, j, ncell(q[k][step], "{:.4f}"))

    # ------------------------------------------------------------------ sentiment
    def _sent_tab(self):
        w = QtWidgets.QWidget(); v = QtWidgets.QVBoxLayout(w)
        row = QtWidgets.QHBoxLayout()
        self.se_fetch = QtWidgets.QPushButton("🌐 " + t("ai_fetch")); self.se_fetch.clicked.connect(self.fetch_news)
        self.se_btn = QtWidgets.QPushButton("▶ " + t("ai_score")); self.se_btn.setObjectName("primary"); self.se_btn.clicked.connect(self.run_sent)
        self.se_backend = QtWidgets.QLabel(t("ai_backend") + ": " + ("FinBERT" if SE.transformer_backend() else "lexicon (VADER+LM)"))
        row.addWidget(self.se_fetch); row.addWidget(self.se_btn); row.addSpacing(16); row.addWidget(self.se_backend); row.addStretch(1); v.addLayout(row)
        tiles = QtWidgets.QHBoxLayout()
        self.se_mean = StatTile(t("ai_sent_mean")); self.se_pos = StatTile(t("ai_pos")); self.se_neg = StatTile(t("ai_neg")); self.se_subj = StatTile(t("ai_subj")); self.se_regime = StatTile(t("ai_regime")); self.se_crowd = StatTile(t("ai_crowded"))
        for x in (self.se_mean, self.se_pos, self.se_neg, self.se_subj, self.se_regime, self.se_crowd):
            tiles.addWidget(x)
        v.addLayout(tiles)
        split = QtWidgets.QHBoxLayout()
        self.se_text = QtWidgets.QPlainTextEdit(); self.se_text.setPlaceholderText(t("ai_headlines"))
        self.se_text.setPlainText("Bitcoin surges to record high as ETF inflows accelerate\nFed signals rate cuts may be delayed; stocks slide\nTSLA misses estimates, shares plunge 12% after hours\nAAPL beats on revenue, raises dividend and buyback\nOil steady as OPEC+ keeps output unchanged")
        c1 = Card(t("ai_headlines")); c1.add(self.se_text); split.addWidget(c1, 2)
        self.se_tbl = make_table([t("ai_headline"), t("ai_compound"), t("ai_subj"), t("ai_tickers"), "FinBERT"])
        c2 = Card(t("ai_tab_sent")); c2.add(self.se_tbl); split.addWidget(c2, 3)
        v.addLayout(split, 1)
        n = QtWidgets.QLabel(t("ai_sent_note")); n.setWordWrap(True); n.setObjectName("subtitle"); v.addWidget(n)
        return w

    def fetch_news(self):
        sym = self.bar.symbol()

        def job():
            return SE.fetch_headlines(sym)

        def done(hl):
            if hl:
                self.se_text.setPlainText("\n".join(hl)); self.run_sent()
            else:
                self.status.setText(t("ai_offline"))
        self._run(job, done)

    def run_sent(self):
        lines = [x.strip() for x in self.se_text.toPlainText().splitlines() if x.strip()]
        be = SE.transformer_backend()
        self._run(lambda: SE.score_headlines(lines, backend=be), self._sent_done)

    def _sent_done(self, r):
        df, agg = r
        self.se_tbl.setSortingEnabled(False); self.se_tbl.setRowCount(0)
        for _, row in df.iterrows():
            i = self.se_tbl.rowCount(); self.se_tbl.insertRow(i)
            self.se_tbl.setItem(i, 0, cell(row["text"]))
            self.se_tbl.setItem(i, 1, ncell(row["compound"], "{:+.2f}", color_for(row["compound"])))
            self.se_tbl.setItem(i, 2, ncell(row["subjectivity"], "{:.2f}"))
            self.se_tbl.setItem(i, 3, cell(", ".join(row["tickers"]) if isinstance(row["tickers"], (list, tuple)) else str(row["tickers"])))
            self.se_tbl.setItem(i, 4, ncell(row["finbert"], "{:+.2f}") if row["finbert"] is not None and not pd.isna(row["finbert"]) else cell("—"))
        self.se_tbl.setSortingEnabled(True)
        if agg:
            self.se_mean.set(f"{agg['mean']:+.2f}", color_for(agg["mean"])); self.se_pos.set(f"{agg['share_pos'] * 100:.0f}%", C["green"])
            self.se_neg.set(f"{agg['share_neg'] * 100:.0f}%", C["red"]); self.se_subj.set(f"{agg['subjectivity']:.2f}")
            self.se_regime.set(agg["regime"], color_for(agg["mean"])); self.se_crowd.set("⚠ yes" if agg["crowded"] else "no", C["red"] if agg["crowded"] else C["green"])

    # ------------------------------------------------------------------ RL
    def _rl_tab(self):
        w = QtWidgets.QWidget(); v = QtWidgets.QVBoxLayout(w)
        row = QtWidgets.QHBoxLayout()
        self.rl_kind = QtWidgets.QComboBox(); self.rl_kind.addItem("Linear Q-learning (DQN-lite)", "q"); self.rl_kind.addItem("Policy gradient (REINFORCE)", "pg")
        self.rl_ep = QtWidgets.QSpinBox(); self.rl_ep.setRange(3, 300); self.rl_ep.setValue(30); self.rl_ep.setPrefix(t("ai_episodes") + " ")
        self.rl_seeds = QtWidgets.QSpinBox(); self.rl_seeds.setRange(1, 10); self.rl_seeds.setValue(3); self.rl_seeds.setPrefix(t("ai_seeds") + " ")
        self.rl_rew = QtWidgets.QComboBox(); self.rl_rew.addItem("log-return", "logret"); self.rl_rew.addItem("differential Sharpe", "dsr")
        self.rl_btn = QtWidgets.QPushButton("▶ " + t("ai_run")); self.rl_btn.setObjectName("primary"); self.rl_btn.clicked.connect(self.run_rl)
        for x in (QtWidgets.QLabel(t("ai_agent")), self.rl_kind, self.rl_ep, self.rl_seeds, QtWidgets.QLabel(t("ai_reward")), self.rl_rew, self.rl_btn):
            row.addWidget(x)
        row.addStretch(1); v.addLayout(row)
        tiles = QtWidgets.QHBoxLayout()
        self.rl_test = StatTile(t("ai_test")); self.rl_bh = StatTile(t("ai_bh")); self.rl_r95 = StatTile(t("ai_rand95")); self.rl_gap = StatTile(t("ai_gap")); self.rl_verdict = StatTile(t("ai_verdict"))
        for x in (self.rl_test, self.rl_bh, self.rl_r95, self.rl_gap, self.rl_verdict):
            tiles.addWidget(x)
        v.addLayout(tiles)
        split = QtWidgets.QHBoxLayout()
        self.rl_tbl = make_table([t("ai_seed"), t("ai_train"), t("ai_val"), t("ai_test"), t("ai_dd"), t("ai_sharpe"), t("ai_trades")])
        c1 = Card(t("ai_tab_rl")); c1.add(self.rl_tbl); split.addWidget(c1, 3)
        self.rl_plot = MiniPlot(240); c2 = Card("Equity (test) — agent vs buy&hold"); c2.add(self.rl_plot); split.addWidget(c2, 3)
        v.addLayout(split, 1)
        n = QtWidgets.QLabel(t("ai_rl_note")); n.setWordWrap(True); n.setObjectName("subtitle"); v.addWidget(n)
        return w

    def run_rl(self):
        sym, tf = self.bar.symbol(), self.bar.timeframe()
        kind, ep, ns, rew = self.rl_kind.currentData(), self.rl_ep.value(), self.rl_seeds.value(), self.rl_rew.currentData()

        def job(progress=None):
            df, _ = load_data(sym, tf)
            return RL.train_and_evaluate(df.tail(3000), agent_kind=kind, episodes=ep, reward=rew, seeds=tuple(range(ns)), progress=progress)
        self._run(job, self._rl_done)

    def _rl_done(self, r):
        res, summ, curves = r
        self.rl_tbl.setSortingEnabled(False); self.rl_tbl.setRowCount(0)
        for _, row in res.iterrows():
            i = self.rl_tbl.rowCount(); self.rl_tbl.insertRow(i)
            self.rl_tbl.setItem(i, 0, ncell(row["seed"], "{:.0f}"))
            for j, k in enumerate(["train", "val", "test"], 1):
                self.rl_tbl.setItem(i, j, ncell(row[k] * 100, "{:+.1f}%", color_for(row[k])))
            self.rl_tbl.setItem(i, 4, ncell(row["test_dd"] * 100, "{:.1f}%", C["red"]))
            self.rl_tbl.setItem(i, 5, ncell(row["test_sharpe"], "{:.2f}", color_for(row["test_sharpe"])))
            self.rl_tbl.setItem(i, 6, ncell(row["trades"], "{:.0f}"))
        self.rl_tbl.setSortingEnabled(True)
        self.rl_test.set(f"{summ['test_mean'] * 100:+.1f}% ± {summ['test_std'] * 100:.1f}", color_for(summ["test_mean"]))
        self.rl_bh.set(f"{summ['buy_hold'] * 100:+.1f}%", color_for(summ["buy_hold"]))
        self.rl_r95.set(f"{summ['random_p95'] * 100:+.1f}%")
        self.rl_gap.set(f"{summ['overfit_gap'] * 100:+.1f}%", color_for(-summ["overfit_gap"]))
        ok = summ["beats_bh"] and summ["beats_random95"] and summ["test_mean"] > 0
        self.rl_verdict.set("✓" if ok else "✗", C["green"] if ok else C["red"])
        self.status.setText(t("ai_rl_good") if ok else t("ai_rl_bad"))
        if curves and len(curves[0]) > 2:
            ag = np.asarray(curves[0], float); bh = np.asarray(summ.get("bh_curve", []), float)
            m = min(len(ag), len(bh)) if len(bh) else len(ag)
            self.rl_plot.set(ag[:m], {"buy&hold": bh[:m]} if len(bh) else {}, None, overlay=True)

    # ------------------------------------------------------------------ analyst (offline LLM layer)
    def _an_tab(self):
        from core import analyst as AN
        w = QtWidgets.QWidget(); v = QtWidgets.QVBoxLayout(w)
        st = AN.llm_status()
        row = QtWidgets.QHBoxLayout()
        self.an_btn = QtWidgets.QPushButton("▶ " + t("ai_run")); self.an_btn.setObjectName("primary"); self.an_btn.clicked.connect(self.run_an)
        lbl = QtWidgets.QLabel(t("ai_llm_status").format(llama="✓" if st["llama_cpp"] else "✗", gguf=", ".join(st["gguf"]) or "—", mode=("local GGUF" if st["active"] else t("ai_llm_rules"))))
        lbl.setWordWrap(True)
        row.addWidget(self.an_btn); row.addWidget(lbl, 1); v.addLayout(row)
        tiles = QtWidgets.QHBoxLayout()
        self.an_bias = StatTile(t("ai_bias")); self.an_score = StatTile(t("ai_confl")); self.an_agree = StatTile(t("ai_agree")); self.an_n = StatTile(t("ai_evidence"))
        for x in (self.an_bias, self.an_score, self.an_agree, self.an_n):
            tiles.addWidget(x)
        v.addLayout(tiles)
        self.an_txt = QtWidgets.QTextEdit(); self.an_txt.setReadOnly(True)
        c = Card(t("ai_brief")); c.add(self.an_txt); v.addWidget(c, 1)
        qrow = QtWidgets.QHBoxLayout()
        self.an_q = QtWidgets.QLineEdit(); self.an_q.setPlaceholderText(t("vis_ask_ph")); self.an_q.returnPressed.connect(self.ask_an)
        b = QtWidgets.QPushButton("💬 " + t("vis_ask")); b.clicked.connect(self.ask_an)
        qrow.addWidget(self.an_q, 1); qrow.addWidget(b); v.addLayout(qrow)
        n = QtWidgets.QLabel(t("ai_an_note")); n.setWordWrap(True); n.setObjectName("subtitle"); v.addWidget(n)
        self._an_ctx = None
        return w

    def run_an(self):
        sym, tf = self.bar.symbol(), self.bar.timeframe()
        lang = I18N.lang

        def job():
            from core import analyst as AN, vision2 as V2, playbook as PB
            import cv2, os
            df, _ = load_data(sym, tf)
            tail = df.tail(120).reset_index(drop=True)
            # run the SAME vision pipeline the user gets on a screenshot, on a rendered chart of live data
            img = V2.render_df(tail, size=(1100, 520))
            p = os.path.join(os.path.expanduser("~"), ".protrader_live_chart.png"); cv2.imwrite(p, img)
            try:
                u = V2.understand(p, lang=lang)
            except Exception:
                from core import vision as V
                u = dict(numeric=V.analyse_chart(tail, lang), df=tail, image_patterns=[], overlays=dict(lines=[], curves=[]), calibration=None)
            u["numeric"] = __import__("core.vision", fromlist=["analyse_chart"]).analyse_chart(tail, lang)  # exact data, not pixels
            u["df"] = tail; u["calibration"] = dict(n_ticks=0)
            fc = F.historical_forecasts(df["close"].values[-800:], h=5, n_origins=12)
            pb = []
            try:
                for sid, sc, st_ in PB.best_for(tf, sym, k=3) or []:
                    pb.append(dict(sid=sid, pf=round(float(st_.get("pf", 0)), 2) if isinstance(st_, dict) else "?", trades=st_.get("trades", "?") if isinstance(st_, dict) else "?"))
            except Exception:
                pass
            ctx = dict(vision=u, forecast=fc, playbook=pb, calibrated=True)
            txt, meta = AN.report(ctx, lang)
            return ctx, txt, meta
        self._run(job, self._an_done)

    def _an_done(self, r):
        ctx, txt, meta = r
        self._an_ctx = ctx
        self.an_txt.setMarkdown(txt.replace("\n", "  \n"))
        self.an_bias.set(meta["bias"], color_for(meta["score"]) if abs(meta["score"]) > 0.25 else C["muted"])
        self.an_score.set(f"{meta['score']:+.2f}", color_for(meta["score"])); self.an_agree.set(f"{meta['agreement'] * 100:.0f}%"); self.an_n.set(str(meta["n"]))

    def ask_an(self):
        q = self.an_q.text().strip()
        if not q or not self._an_ctx:
            return
        from core import analyst as AN
        ans, be = AN.ask(q, self._an_ctx, I18N.lang)
        self.an_txt.append(f"\n\n❓ {q}\n💬 [{be}] {ans}")

    # ------------------------------------------------------------------ engines
    def _eng_tab(self):
        w = QtWidgets.QWidget(); v = QtWidgets.QVBoxLayout(w)
        row = QtWidgets.QHBoxLayout()
        self.en_btn = QtWidgets.QPushButton("▶ " + t("ai_run")); self.en_btn.setObjectName("primary"); self.en_btn.clicked.connect(self.run_eng)
        row.addWidget(self.en_btn); row.addStretch(1); v.addLayout(row)
        self.en_tbl = make_table([t("ai_engine"), t("ai_trades"), t("ai_ret"), "Max DD %", t("ai_pf"), t("ai_sqn")])
        c1 = Card(t("ai_parity")); c1.add(self.en_tbl); v.addWidget(c1)
        split = QtWidgets.QHBoxLayout()
        self.en_pipe = make_table(["Symbol", "Momentum", "Vol", "Rank", "Long", "Short"]); c2 = Card(t("ai_pipeline")); c2.add(self.en_pipe); split.addWidget(c2, 1)
        self.en_fw = QtWidgets.QTextEdit(); self.en_fw.setReadOnly(True); c3 = Card(t("ai_framework")); c3.add(self.en_fw); split.addWidget(c3, 1)
        v.addLayout(split, 1)
        n = QtWidgets.QLabel(t("ai_eng_note")); n.setWordWrap(True); n.setObjectName("subtitle"); v.addWidget(n)
        return w

    def run_eng(self):
        sym, tf, sid = self.bar.symbol(), self.bar.timeframe(), self.bar.strategy_id()

        def job():
            df, _ = load_data(sym, tf)
            res = S.get(sid).run(df)
            par = E.parity_check(df, res)
            cat = next((c for c, d in UNIVERSE.items() if sym in d), None)
            peers = list(UNIVERSE.get(cat, {sym: None}).keys())[:8] if cat else [sym]
            prices = {}
            for s_ in peers:
                d, _ = load_data(s_, tf); prices[s_] = d
            pipe = E.pipeline_rank(prices, window=min(126, len(df) // 4))
            fw = E.AlgorithmFramework(lambda pd_: {s_: ((1 if pipe.loc[pipe.symbol == s_, "longs"].any() else (-1 if pipe.loc[pipe.symbol == s_, "shorts"].any() else 0)), 0.6) for s_ in pd_} if len(pipe) else {}, portfolio="weighted")
            fwr = fw.run(prices, [1.0, 1.0])
            sched = E.freqai_schedule(len(df), train_period=int(len(df) * 0.5), backtest_period=int(len(df) * 0.1))
            return dict(par=par, pipe=pipe, fw=fwr, sched=sched, sid=sid)
        self._run(job, self._eng_done)

    def _eng_done(self, r):
        par = r["par"]; self.en_tbl.setSortingEnabled(False); self.en_tbl.setRowCount(0)
        for name, d in (("vectorised (core/backtest)", par["vectorised"]), ("event-driven (Backtrader-style)", par["event"])):
            i = self.en_tbl.rowCount(); self.en_tbl.insertRow(i)
            self.en_tbl.setItem(i, 0, cell(name)); self.en_tbl.setItem(i, 1, ncell(d["trades"], "{:.0f}"))
            self.en_tbl.setItem(i, 2, ncell(d["return_pct"], "{:+.2f}", color_for(d["return_pct"]))); self.en_tbl.setItem(i, 3, ncell(d["max_dd_pct"], "{:.2f}", C["red"]))
            self.en_tbl.setItem(i, 4, ncell(d["pf"], "{:.2f}")); self.en_tbl.setItem(i, 5, ncell(d.get("sqn", np.nan), "{:.2f}") if "sqn" in d else cell("—"))
        i = self.en_tbl.rowCount(); self.en_tbl.insertRow(i)
        okc = C["green"] if par["trade_count_gap"] == 0 and par["return_gap_pct"] < 1 else C["red"]
        self.en_tbl.setItem(i, 0, cell("Δ gap", okc)); self.en_tbl.setItem(i, 1, ncell(par["trade_count_gap"], "{:.0f}", okc)); self.en_tbl.setItem(i, 2, ncell(par["return_gap_pct"], "{:.2f}", okc))
        if "sqn" in par["event"]:
            self.en_tbl.setItem(i, 5, cell(E.sqn_label(par["event"]["sqn"]), okc))
        self.en_tbl.setSortingEnabled(True)
        pipe = r["pipe"]; self.en_pipe.setSortingEnabled(False); self.en_pipe.setRowCount(0)
        for _, row in pipe.iterrows():
            j = self.en_pipe.rowCount(); self.en_pipe.insertRow(j)
            self.en_pipe.setItem(j, 0, cell(row["symbol"])); self.en_pipe.setItem(j, 1, ncell(row["momentum"] * 100, "{:+.1f}%", color_for(row["momentum"])))
            self.en_pipe.setItem(j, 2, ncell(row["volatility"] * 100, "{:.0f}%")); self.en_pipe.setItem(j, 3, ncell(row["mom_rank"], "{:.0f}"))
            self.en_pipe.setItem(j, 4, cell("✓" if row["longs"] else "", C["green"])); self.en_pipe.setItem(j, 5, cell("✓" if row["shorts"] else "", C["red"]))
        self.en_pipe.setSortingEnabled(True)
        fw = r["fw"]
        lines = [f"Strategy: {strat_name(S.REGISTRY[r['sid']])}", "", "Alpha insights:"] + [f"  {s}: {'▲' if v[0] > 0 else ('▼' if v[0] < 0 else '—')} conf {v[1]:.2f}" for s, v in fw["insights"].items()]
        lines += ["", "Portfolio weights (max 25%/asset):"] + [f"  {s}: {w_:+.2f}" for s, w_ in fw["weights"].items()]
        lines += ["", f"Risk: drawdown kill-switch {'ACTIVE' if fw['halted'] else 'ok'}", "", "Execution orders:"] + [f"  {o['action']} {o['symbol']} → {o['target_weight']:+.2f}" for o in fw["orders"]]
        lines += ["", t("ai_freqai") + f": {len(r['sched'])} windows"] + [f"  train [{a}, {b}) → test [{b}, {c})" for a, b, c in r["sched"][:6]]
        self.en_fw.setPlainText("\n".join(lines))
