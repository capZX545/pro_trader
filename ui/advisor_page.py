"""Advisor page — one symbol, all timeframes 5m→1d: regime, best proven strategy, fresh signal, delivery time, verdict."""
import time
from PyQt6 import QtCore, QtGui, QtWidgets

from core import advisor as A
from core import playbook as PB
from .theme import C, t, I18N
from .widgets import Card, StatTile, make_table, cell, ncell, Worker, color_for
from .pages import SymbolBar


class AdvisorPage(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(16, 12, 16, 12)
        v.setSpacing(10)
        title = QtWidgets.QLabel(t("adv_title")); title.setObjectName("h1"); v.addWidget(title)
        sub = QtWidgets.QLabel(t("adv_sub")); sub.setObjectName("subtitle"); sub.setWordWrap(True); v.addWidget(sub)
        top = QtWidgets.QHBoxLayout()
        self.bar = SymbolBar(with_strategy=False)
        self.bar.tf.setVisible(False)
        self.bar.btn.setText("⚡ " + t("adv_run"))
        self.bar.changed.connect(self.run)
        top.addWidget(self.bar)
        self.pb_btn = QtWidgets.QPushButton("📖 " + t("adv_rebuild"))
        self.pb_btn.clicked.connect(self.rebuild)
        top.addWidget(self.pb_btn)
        top.addStretch()
        self.status = QtWidgets.QLabel(""); self.status.setObjectName("subtitle"); top.addWidget(self.status)
        v.addLayout(top)
        self.prog = QtWidgets.QProgressBar(); self.prog.setRange(0, 100); self.prog.setVisible(False); v.addWidget(self.prog)

        tiles = QtWidgets.QHBoxLayout()
        self.t_verdict = StatTile(t("adv_verdict"))
        self.t_conf = StatTile(t("conf"))
        self.t_htf = StatTile(t("adv_htf"))
        self.t_fast = StatTile(t("adv_fastest"))
        self.t_best = StatTile(t("adv_best_tf"))
        self.t_time = StatTile(t("adv_elapsed"))
        for x in (self.t_verdict, self.t_conf, self.t_htf, self.t_fast, self.t_best, self.t_time):
            tiles.addWidget(x)
        v.addLayout(tiles)

        self.tbl = make_table([t("timeframe"), t("adv_regime"), "ADX", "CHOP", t("strategy"), t("side"), t("fresh"), t("price"), t("stop"), t("target"),
                               t("rr"), t("adv_pb_wr"), t("adv_pb_pf"), t("grade"), t("adv_hold"), t("adv_next"), t("conf")])
        self.tbl.setSortingEnabled(False)
        self.tbl.itemDoubleClicked.connect(self._open)
        self.tbl.setMinimumHeight(240)
        v.addWidget(self.tbl, 3)
        hint = QtWidgets.QLabel("ⓘ " + t("adv_grade_hint")); hint.setObjectName("subtitle"); hint.setWordWrap(True); v.addWidget(hint)
        alloc = Card(t("adv_alloc"))
        self.alloc_tbl = make_table([t("timeframe"), t("strategy"), t("side"), t("adv_take"), t("adv_risk"), t("adv_units"), t("adv_reason")])
        self.alloc_tbl.setSortingEnabled(False); self.alloc_tbl.setMaximumHeight(120)
        alloc.add(self.alloc_tbl)
        v.addWidget(alloc)
        pbc = Card(t("adv_playbook"))
        pbc.setMaximumHeight(230)
        self.pb_lbl = QtWidgets.QLabel(""); self.pb_lbl.setWordWrap(True); self.pb_lbl.setTextFormat(QtCore.Qt.TextFormat.RichText)
        sa = QtWidgets.QScrollArea(); sa.setWidgetResizable(True); sa.setFrameShape(QtWidgets.QFrame.Shape.NoFrame); sa.setWidget(self.pb_lbl)
        pbc.v.addWidget(sa)
        v.addWidget(pbc)
        self._show_playbook()

    # ------------------------------------------------------------ playbook summary
    def _show_playbook(self):
        s = PB.tf_summary()
        if not s:
            self.pb_lbl.setText(t("adv_no_pb"))
            return
        fa = I18N.lang == "fa"
        import strategies as S
        rows = []
        for tf, d in s.items():
            col = C["green"] if d["proven"] >= 10 else (C["yellow"] if d["proven"] >= 3 else C["red"])
            cells = ""
            for g, sid, st in d["best"][:2]:
                if sid not in S.REGISTRY:
                    continue
                nm = (S.REGISTRY[sid].name_fa if fa else S.REGISTRY[sid].name_en).split(" (")[0].split(" —")[0]
                cells += f"<td style='padding:2px 10px'>{nm}<span style='color:{C['muted']}'> [{g}]</span></td><td style='padding:2px 10px;color:{C['green']}'>WR {st['wr']:.0f}% <span style='color:{C['muted']}'>[{st.get('wr_lo', 0):.0f}]</span></td><td style='padding:2px 10px'>PF {st['pf']:.2f} <span style='color:{C['muted']}'>[{st.get('pf_lo', float('nan')):.2f}]</span></td><td style='padding:2px 6px;color:{ {'A': C['green'], 'B': C['accent2'], 'C': C['yellow']}.get(st.get('grade', 'D'), C['red'])}'>● {st.get('grade', 'D')} · n={st['n']}</td>"
            if not cells:
                cells = f"<td colspan='8' style='padding:2px 10px;color:{C['muted']}'>{t('adv_flat')}</td>"
            rows.append(f"<tr><td style='padding:2px 10px'><b style='color:{col}'>{tf}</b></td><td style='padding:2px 10px'>{d['proven']}/{d['tested']}</td>{cells}</tr>")
        hdr = f"<tr style='color:{C['muted']}'><td style='padding:2px 10px'>TF</td><td style='padding:2px 10px'>{t('adv_proven')}</td><td colspan='8'></td></tr>"
        self.pb_lbl.setText(f"<table dir='{'rtl' if fa else 'ltr'}' cellspacing='0'>{hdr}{''.join(rows)}</table>")

    def rebuild(self):
        import strategies as S
        self.pb_btn.setEnabled(False); self.prog.setVisible(True)

        def work(progress=None):
            PB.build_playbook(S.ALL_STRATEGIES, progress=progress)
            return True
        self.w2 = Worker(work)
        self.w2.progress.connect(lambda p, s: (self.prog.setValue(p), self.status.setText(s)))
        self.w2.done.connect(lambda _: (self.pb_btn.setEnabled(True), self.prog.setVisible(False), self._show_playbook(), self.status.setText(t("adv_pb_done"))))
        self.w2.error.connect(lambda e: (self.pb_btn.setEnabled(True), self.prog.setVisible(False), QtWidgets.QMessageBox.warning(self, "Error", e)))
        self.w2.start()

    # ------------------------------------------------------------ advise
    def run(self):
        sym = self.bar.symbol()
        self.bar.btn.setEnabled(False)
        self.status.setText(t("adv_running"))
        t0 = time.time()

        def work(progress=None):
            a = A.advise(sym, progress=lambda tf: progress(0, tf) if progress else None)
            a["elapsed"] = time.time() - t0
            return a
        self.w = Worker(work)
        self.w.progress.connect(lambda p, s: self.status.setText(f"{t('adv_running')} {s}"))
        self.w.done.connect(self._show)
        self.w.error.connect(lambda e: (self.bar.btn.setEnabled(True), QtWidgets.QMessageBox.warning(self, "Error", e)))
        self.w.start()

    def _show(self, a):
        self.bar.btn.setEnabled(True)
        fa = I18N.lang == "fa"
        vd = a["verdict"]
        if vd["action"] == "wait":
            self.t_verdict.set("⏸ " + t("adv_wait"), C["yellow"]); self.t_conf.set("—"); self.t_fast.set("—"); self.t_best.set("—")
        else:
            self.t_verdict.set(("▲ " + t("long")) if vd["action"] == "long" else ("▼ " + t("short")), C["green"] if vd["action"] == "long" else C["red"])
            self.t_conf.set(f"{vd['conf']:.0f}/100", C["green"] if vd["conf"] >= 65 else (C["yellow"] if vd["conf"] >= 45 else C["red"]))
            self.t_fast.set(vd["fastest_tf"]); self.t_best.set(vd["best_tf"])
        hb = a["htf_bias"]
        self.t_htf.set(t("bull") if hb == 1 else (t("bear") if hb == -1 else t("range")), C["green"] if hb == 1 else (C["red"] if hb == -1 else C["yellow"]))
        self.t_time.set(f"{a['elapsed']:.1f}s")
        self.status.setText(f"{a['symbol']} · {time.strftime('%H:%M:%S')}")
        self.tbl.setRowCount(0)
        for tf, d in a["tfs"].items():
            r = self.tbl.rowCount(); self.tbl.insertRow(r)
            it = cell(tf); it.setData(QtCore.Qt.ItemDataRole.UserRole, (tf, d.get("signal", {}) or {}))
            self.tbl.setItem(r, 0, it)
            if "error" in d:
                self.tbl.setItem(r, 1, cell(d["error"], C["red"])); continue
            rg = d["regime"]
            self.tbl.setItem(r, 1, cell(t("adv_" + rg["kind"]), C["accent2"] if rg["kind"] == "trend" else (C["yellow"] if rg["kind"] == "range" else C["muted"])))
            self.tbl.setItem(r, 2, ncell(rg["adx"], "{:.0f}")); self.tbl.setItem(r, 3, ncell(rg["chop"], "{:.0f}"))
            s = d.get("signal")
            if not s:
                note = d.get("note")
                self.tbl.setItem(r, 4, cell(t("adv_flat") if note else t("adv_no_fresh"), C["muted"]))
                self.tbl.setItem(r, 15, ncell(d["next_close_min"], "{:.0f} min"))
                continue
            self.tbl.setItem(r, 4, cell(s["name_fa"] if fa else s["name"]))
            self.tbl.setItem(r, 5, cell(t("long") if s["side"] == 1 else t("short"), C["green"] if s["side"] == 1 else C["red"]))
            self.tbl.setItem(r, 6, ncell(s["ago"], "{:.0f} " + t("bars_ago"), C["green"] if s["ago"] == 0 else None))
            pxc = ncell(s["px"], "{:,.6g}")
            if not s.get("chase_ok", True):
                pxc.setText(f"{s['px']:,.6g}  ⚠ +{s['chase_r']:.1f}R"); pxc.setForeground(QtGui.QColor(C["yellow"])); pxc.setToolTip(t("adv_chase"))
            self.tbl.setItem(r, 7, pxc)
            self.tbl.setItem(r, 8, ncell(s["sl"], "{:,.6g}", C["red"]))
            self.tbl.setItem(r, 9, cell(t("adv_rule_exit") if s["rule_exit"] else f"{s['tp']:,.6g}", C["green"]))
            self.tbl.setItem(r, 10, ncell(s["rr"], "1:{:.1f}"))
            self.tbl.setItem(r, 11, cell(f"{s['pb_wr']:.0f}%  [{s.get('pb_wr_lo', 0):.0f}]", C["green"] if s.get("pb_wr_lo", 0) >= 50 else None))
            self.tbl.setItem(r, 12, cell(f"{s['pb_pf']:.2f}  [{s.get('pb_pf_lo', 0):.2f}]", color_for(s.get("pb_pf_lo", s["pb_pf"]) - 1)))
            g = s.get("grade", "D")
            self.tbl.setItem(r, 13, cell(f"● {g} · n={s['pb_n']}", {"A": C["green"], "B": C["accent2"], "C": C["yellow"]}.get(g, C["red"])))
            hm = s["hold_min"]
            self.tbl.setItem(r, 14, cell(f"{hm / 60:.1f} h" if hm < 2880 else f"{hm / 1440:.1f} d"))
            self.tbl.setItem(r, 15, ncell(d["next_close_min"], "{:.0f} min"))
            self.tbl.setItem(r, 16, ncell(s["conf"], "{:.0f}", C["green"] if s["conf"] >= 65 else (C["yellow"] if s["conf"] >= 45 else C["muted"])))
        self.tbl.resizeColumnsToContents()
        self._show_alloc(a)
        if a.get("recorded"):
            self.status.setText(self.status.text() + f"  ·  {a['recorded']} {t('adv_recorded')}")
            fp = getattr(self.window(), "page", lambda k: None)("nav_forward")
            if fp is not None:
                fp.render()

    def _show_alloc(self, a):
        from core import portfolio as P
        fa = I18N.lang == "fa"
        sigs = []
        for tf, d in a["tfs"].items():
            s = d.get("signal") if isinstance(d, dict) else None
            if s and s["sl"] == s["sl"]:
                sigs.append(dict(symbol=a["symbol"], side=s["side"], entry=s["px"], stop=s["sl"], conf=s["conf"], tf=tf,
                                 name=s["name_fa"] if fa else s["name"], wr=s["pb_wr"], payoff=None))
        self.alloc_tbl.setRowCount(0)
        if not sigs:
            return
        # same symbol on several TFs is perfectly correlated → the allocator halves the second/third
        rows = P.allocate(sigs, equity=10_000, risk_pct=0.5, max_total_risk=1.5, max_corr=0.7)
        for al in rows:
            s = al["signal"]
            r = self.alloc_tbl.rowCount(); self.alloc_tbl.insertRow(r)
            self.alloc_tbl.setItem(r, 0, cell(s["tf"])); self.alloc_tbl.setItem(r, 1, cell(s["name"]))
            self.alloc_tbl.setItem(r, 2, cell(t("long") if s["side"] == 1 else t("short"), C["green"] if s["side"] == 1 else C["red"]))
            self.alloc_tbl.setItem(r, 3, cell("✔ " + t("adv_take") if al["take"] else "✖ " + t("adv_skip"), C["green"] if al["take"] else C["muted"]))
            self.alloc_tbl.setItem(r, 4, ncell(al["risk_pct"], "{:.2f}%"))
            self.alloc_tbl.setItem(r, 5, ncell(al["size_units"], "{:,.4g}"))
            self.alloc_tbl.setItem(r, 6, cell(al["reason"], C["muted"]))
        self.alloc_tbl.resizeColumnsToContents()

    def _open(self, item):
        tf, s = self.tbl.item(item.row(), 0).data(QtCore.Qt.ItemDataRole.UserRole)
        self.window().open_chart(self.bar.symbol(), tf, s.get("sid") or "ensemble")
