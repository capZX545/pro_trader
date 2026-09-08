"""Quant Lab — Chan (stationarity, pairs), de Prado (FFD, DSR, PBO, CUSUM), Davey (incubation), Bulkowski/Nison
(pattern scanner with published stats), and the Psychology desk (Douglas/Steenbarger/Kahneman/Taleb checklist + journal audit)."""
import numpy as np
import pandas as pd
from PyQt6 import QtCore, QtWidgets

from core import quant as Q, quant2 as Q2, patterns as PT, psychology as PSY


def bt_allow_short(cls):
    return bool(getattr(cls, "bt_kwargs", {}).get("allow_short", True))
from .theme import C, t, I18N
from .widgets import Card, StatTile, make_table, cell, ncell, Worker, color_for
from .pages import SymbolBar, load_data, all_symbols


class QuantLabPage(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        v = QtWidgets.QVBoxLayout(self); v.setContentsMargins(16, 12, 16, 12); v.setSpacing(10)
        title = QtWidgets.QLabel(t("ql_title")); title.setObjectName("h1"); v.addWidget(title)
        sub = QtWidgets.QLabel(t("ql_sub")); sub.setObjectName("subtitle"); sub.setWordWrap(True); v.addWidget(sub)
        self.tabs = QtWidgets.QTabWidget(); v.addWidget(self.tabs, 1)
        self.tabs.addTab(self._series_tab(), "📐 " + t("ql_tab_series"))
        self.tabs.addTab(self._pairs_tab(), "🔗 " + t("ql_tab_pairs"))
        self.tabs.addTab(self._overfit_tab(), "🧪 " + t("ql_tab_overfit"))
        self.tabs.addTab(self._patterns_tab(), "🕯 " + t("ql_tab_patterns"))
        self.tabs.addTab(self._psy_tab(), "🧠 " + t("ql_tab_psy"))
        self.tabs.addTab(self._bots_tab(), "🤖 " + t("ql_tab_bots"))

    # ------------------------------------------------------------------ 1. series (Chan + de Prado FFD + CUSUM)
    def _series_tab(self):
        w = QtWidgets.QWidget(); v = QtWidgets.QVBoxLayout(w)
        self.bar1 = SymbolBar(with_strategy=False); self.bar1.btn.setText(t("ql_analyze")); self.bar1.changed.connect(self.run_series); v.addWidget(self.bar1)
        tiles = QtWidgets.QHBoxLayout()
        self.t_adf = StatTile("ADF (Chan)"); self.t_hurst = StatTile("Hurst H"); self.t_hl = StatTile(t("ql_half_life")); self.t_ffd = StatTile("min d (FFD, de Prado)"); self.t_cusum = StatTile("CUSUM events / 100 bars"); self.t_verdict = StatTile(t("ql_regime"))
        for x in (self.t_adf, self.t_hurst, self.t_hl, self.t_ffd, self.t_cusum, self.t_verdict):
            tiles.addWidget(x)
        v.addLayout(tiles)
        self.series_txt = QtWidgets.QLabel(""); self.series_txt.setWordWrap(True); self.series_txt.setTextFormat(QtCore.Qt.TextFormat.RichText); v.addWidget(self.series_txt)
        self.ffd_tbl = make_table(["d", "ADF stat", t("ql_stationary"), t("ql_corr_price")]); v.addWidget(self.ffd_tbl, 1)
        return w

    def run_series(self):
        sym, tf = self.bar1.symbol(), self.bar1.timeframe()
        self.bar1.btn.setEnabled(False)

        def work():
            df, ok = load_data(sym, tf)
            lp = np.log(df.close)
            a = Q.adf_test(lp.values); H = Q.hurst(lp.values); hl = Q.half_life(lp)
            rows, best = Q.min_ffd(df.close)
            ev = Q.cusum_filter(df.close, threshold=float(lp.diff().std() * 2))
            return df, a, H, hl, rows, best, len(ev) / len(df) * 100
        self.w = Worker(work); self.w.done.connect(self._show_series)
        self.w.error.connect(lambda e: (self.bar1.btn.setEnabled(True), QtWidgets.QMessageBox.warning(self, "Error", e))); self.w.start()

    def _show_series(self, r):
        df, a, H, hl, rows, best, cus = r
        self.bar1.btn.setEnabled(True)
        self.t_adf.set(f"{a['stat']:.2f} ({a['strength']})", C["green"] if a["stationary"] else C["red"])
        self.t_hurst.set(f"{H:.2f}", C["accent2"] if H < 0.45 else (C["yellow"] if H > 0.55 else C["muted"]))
        self.t_hl.set(f"{hl:.0f} bars" if np.isfinite(hl) else "∞", None)
        self.t_ffd.set(f"d = {best['d']}" if best else "—", None)
        self.t_cusum.set(f"{cus:.1f}")
        if H < 0.45 and a["stationary"]:
            self.t_verdict.set(t("ql_mr"), C["accent2"]); adv = t("ql_mr_adv")
        elif H > 0.55:
            self.t_verdict.set(t("ql_mom"), C["yellow"]); adv = t("ql_mom_adv")
        else:
            self.t_verdict.set(t("ql_rw"), C["muted"]); adv = t("ql_rw_adv")
        self.series_txt.setText(f"<b>{t('ql_meaning')}</b> {adv}")
        self.ffd_tbl.setSortingEnabled(False); self.ffd_tbl.setRowCount(0)
        for rw in rows:
            i = self.ffd_tbl.rowCount(); self.ffd_tbl.insertRow(i)
            self.ffd_tbl.setItem(i, 0, ncell(rw["d"], "{:.1f}")); self.ffd_tbl.setItem(i, 1, ncell(rw["adf"], "{:.2f}", C["green"] if rw["stationary"] else None))
            self.ffd_tbl.setItem(i, 2, cell("✔" if rw["stationary"] else "✖", C["green"] if rw["stationary"] else C["red"])); self.ffd_tbl.setItem(i, 3, ncell(rw["corr_with_price"], "{:.2f}"))

    # ------------------------------------------------------------------ 2. pairs (Chan ch.3, Blackbird/arbitrage spread)
    def _pairs_tab(self):
        w = QtWidgets.QWidget(); v = QtWidgets.QVBoxLayout(w)
        top = QtWidgets.QHBoxLayout()
        self.pair_cat = QtWidgets.QComboBox()
        from core.data import UNIVERSE
        self.pair_cat.addItems(list(UNIVERSE.keys()))
        self.pair_tf = QtWidgets.QComboBox(); self.pair_tf.addItems(["1h", "4h", "1d"]); self.pair_tf.setCurrentText("1d")
        b = QtWidgets.QPushButton("🔗 " + t("ql_scan_pairs")); b.setObjectName("primary"); b.clicked.connect(self.run_pairs)
        top.addWidget(QtWidgets.QLabel(t("category"))); top.addWidget(self.pair_cat); top.addWidget(QtWidgets.QLabel(t("timeframe"))); top.addWidget(self.pair_tf); top.addWidget(b); top.addStretch()
        self.pair_status = QtWidgets.QLabel(""); self.pair_status.setObjectName("subtitle"); top.addWidget(self.pair_status)
        v.addLayout(top)
        hint = QtWidgets.QLabel(t("ql_pairs_hint")); hint.setObjectName("subtitle"); hint.setWordWrap(True); v.addWidget(hint)
        self.pair_tbl = make_table(["A", "B", "β (hedge)", "ADF", t("ql_coint"), t("ql_half_life"), "Hurst", "z now", t("ql_signal"), "window", "n"]); v.addWidget(self.pair_tbl, 1)
        return w

    def run_pairs(self):
        cat, tf = self.pair_cat.currentText(), self.pair_tf.currentText()
        self.pair_status.setText(t("ql_running"))

        def work():
            from core.data import UNIVERSE
            prices = {}
            for s in list(UNIVERSE[cat].keys())[:10]:
                try:
                    df, ok = load_data(s, tf)
                    if ok:
                        idx = df.index.tz_localize(None) if df.index.tz is not None else df.index
                        prices[s] = pd.Series(df.close.values, index=idx)
                except Exception:
                    pass
            return Q.scan_pairs(prices)
        self.w2 = Worker(work); self.w2.done.connect(self._show_pairs)
        self.w2.error.connect(lambda e: QtWidgets.QMessageBox.warning(self, "Error", e)); self.w2.start()

    def _show_pairs(self, rows):
        self.pair_status.setText(f"{len(rows)} pairs · {sum(r['coint'] for r in rows)} {t('ql_coint').lower()}")
        self.pair_tbl.setSortingEnabled(False); self.pair_tbl.setRowCount(0)
        for r in rows:
            i = self.pair_tbl.rowCount(); self.pair_tbl.insertRow(i)
            self.pair_tbl.setItem(i, 0, cell(r["a"])); self.pair_tbl.setItem(i, 1, cell(r["b"])); self.pair_tbl.setItem(i, 2, ncell(r["beta"], "{:.3f}"))
            self.pair_tbl.setItem(i, 3, ncell(r["adf"], "{:.2f}", C["green"] if r["coint"] else None))
            self.pair_tbl.setItem(i, 4, cell(f"✔ {r['strength']}" if r["coint"] else "✖", C["green"] if r["coint"] else C["muted"]))
            self.pair_tbl.setItem(i, 5, ncell(r["half_life"], "{:.0f}") if np.isfinite(r["half_life"]) else cell("∞"))
            self.pair_tbl.setItem(i, 6, ncell(r["hurst"], "{:.2f}")); self.pair_tbl.setItem(i, 7, ncell(r["z"], "{:+.2f}", color_for(-abs(r["z"]) + 2)))
            sg = r["signal"]
            self.pair_tbl.setItem(i, 8, cell((f"{t('long')} {r['a']} / {t('short')} {r['b']}" if sg == 1 else (f"{t('short')} {r['a']} / {t('long')} {r['b']}" if sg == -1 else "—")) if r["coint"] else t("ql_not_tradeable"), C["green"] if sg == 1 and r["coint"] else (C["red"] if sg == -1 and r["coint"] else C["muted"])))
            self.pair_tbl.setItem(i, 9, ncell(r["window"], "{:.0f}")); self.pair_tbl.setItem(i, 10, ncell(r["n"], "{:.0f}"))
        self.pair_tbl.setSortingEnabled(True)

    # ------------------------------------------------------------------ 3. overfitting (de Prado DSR / PBO, Davey incubation)
    def _overfit_tab(self):
        w = QtWidgets.QWidget(); v = QtWidgets.QVBoxLayout(w)
        self.bar3 = SymbolBar(with_strategy=True); self.bar3.btn.setText(t("ql_test_overfit")); self.bar3.changed.connect(self.run_overfit); v.addWidget(self.bar3)
        hint = QtWidgets.QLabel(t("ql_overfit_hint")); hint.setObjectName("subtitle"); hint.setWordWrap(True); v.addWidget(hint)
        tiles = QtWidgets.QHBoxLayout()
        self.t_sr = StatTile("Sharpe"); self.t_dsr = StatTile("Deflated SR prob."); self.t_sr0 = StatTile("SR expected by luck"); self.t_pbo = StatTile("PBO (CSCV)"); self.t_wfe = StatTile("WFE (Davey)"); self.t_inc = StatTile(t("ql_incubation"))
        for x in (self.t_sr, self.t_dsr, self.t_sr0, self.t_pbo, self.t_wfe, self.t_inc):
            tiles.addWidget(x)
        v.addLayout(tiles)
        tiles2 = QtWidgets.QHBoxLayout()
        self.t_monkey = StatTile(t("ql_monkey")); self.t_mc_ret = StatTile(t("ql_mc_ret")); self.t_mc_dd = StatTile(t("ql_mc_dd")); self.t_prot = StatTile(t("ql_prot"))
        for x in (self.t_monkey, self.t_mc_ret, self.t_mc_dd, self.t_prot):
            tiles2.addWidget(x)
        v.addLayout(tiles2)
        self.inc_tbl = make_table([t("ql_check"), t("ql_pass")]); self.inc_tbl.setSortingEnabled(False); v.addWidget(self.inc_tbl, 1)
        self.of_txt = QtWidgets.QLabel(""); self.of_txt.setWordWrap(True); v.addWidget(self.of_txt)
        return w

    def run_overfit(self):
        import strategies as S
        from core.backtest import run_backtest
        from core.validation import monte_carlo_dd
        sym, tf, sid = self.bar3.symbol(), self.bar3.timeframe(), self.bar3.strategy_id()
        self.bar3.btn.setEnabled(False)

        def work():
            df, ok = load_data(sym, tf)
            cls = S.REGISTRY[sid]
            bt = run_backtest(df, cls().run(df))
            rets = bt.equity.pct_change().dropna().values
            delta = (df.index[1:] - df.index[:-1]).median(); periods = float(pd.Timedelta(days=365) / delta)
            sr = Q.sharpe(rets, periods)
            # variance of trial Sharpes estimated from the playbook's own distribution (not assumed)
            sr_var = Q.trial_sr_variance(periods)
            dsr = Q.deflated_sharpe(sr, n_trials=len(S.ALL_STRATEGIES) * 4, n_obs=len(rets), periods=periods, sr_var=sr_var)  # trials ≈ strategies × asset groups
            # PBO: parameter variants of this strategy (perturb numeric params ±20%) → returns matrix
            variants = []
            base = cls.params
            keys = [k for k, val in base.items() if isinstance(val, (int, float)) and not isinstance(val, bool)]
            rng = np.random.default_rng(1)
            for _ in range(min(16, 4 + 3 * len(keys))):
                kw = {k: (type(base[k])(base[k] * rng.uniform(0.8, 1.2)) if isinstance(base[k], float) else max(2, int(round(base[k] * rng.uniform(0.8, 1.2))))) for k in keys}
                try:
                    eq = run_backtest(df, cls(**kw).run(df)).equity.pct_change().fillna(0).values
                    variants.append(eq)
                except Exception:
                    continue
            pbo = Q.pbo_cscv(np.column_stack(variants), n_splits=8) if len(variants) >= 4 else float("nan")
            cut = int(len(df) * 0.7)
            ins = run_backtest(df.iloc[:cut], cls().run(df.iloc[:cut])).stats
            oos_df = df.iloc[cut - 300:]; r2 = cls().run(oos_df); r2.signal.iloc[:300] = 0
            oos = run_backtest(oos_df, r2).stats
            yrs_in = max((df.index[cut] - df.index[0]).days / 365.25, 0.1); yrs_out = max((df.index[-1] - df.index[cut]).days / 365.25, 0.1)
            wfe = Q.walk_forward_efficiency(ins["return_pct"] / yrs_in, oos["return_pct"] / yrs_out)
            dd95, _ = monte_carlo_dd(bt.trades, bt.initial_capital)
            big = max((abs(tr.pnl) for tr in bt.trades), default=0) / max(abs(bt.stats["net_profit"]), 1e-9)
            checks, ok_all = Q.davey_incubation(bt.stats, dd95, wfe, biggest_trade_share=big)
            pn = [tr.pnl_pct for tr in bt.trades]
            hold = int(np.mean([tr.bars for tr in bt.trades])) if bt.trades else 10
            monkey = Q2.monkey_test(df, pn, holding_bars=max(1, hold), n_sims=300, allow_short=bt_allow_short(cls)) if pn else {}
            mc = Q2.monte_carlo_trades([tr.r_multiple * 1.0 for tr in bt.trades], n_sims=1000)  # 1% risk per R → equity %
            btp = run_backtest(df, cls().run(df), protections=True)
            prot = dict(trades=btp.stats["trades"], pf=float(btp.stats["profit_factor"]), dd=float(btp.stats["max_dd_pct"]),
                        base_pf=float(bt.stats["profit_factor"]), base_dd=float(bt.stats["max_dd_pct"]), locks=btp.stats.get("protection_locks", {}))
            checks["Monkey test ≥ p95 (Davey)"] = bool(monkey.get("passed", False))
            checks["MC P(loss) < 10% (Davey)"] = bool(mc and mc["prob_loss"] < 10)
            return sr, dsr, pbo, wfe, checks, ok_all and checks["Monkey test ≥ p95 (Davey)"], len(variants), monkey, mc, prot
        self.w3 = Worker(work); self.w3.done.connect(self._show_overfit)
        self.w3.error.connect(lambda e: (self.bar3.btn.setEnabled(True), QtWidgets.QMessageBox.warning(self, "Error", e))); self.w3.start()

    def _show_overfit(self, r):
        sr, dsr, pbo, wfe, checks, ok_all, nv, monkey, mc, prot = r
        self.bar3.btn.setEnabled(True)
        if monkey:
            self.t_monkey.set(f"p{monkey['percentile']:.0f}  ({'✔' if monkey['passed'] else '✖'} ≥p95)", C["green"] if monkey["passed"] else C["red"])
            self.t_monkey.setToolTip(f"strategy {monkey['strategy_total_pct']:+.0f}% · random mean {monkey['random_mean']:+.0f}% · random p95 {monkey['random_p95']:+.0f}%")
        else:
            self.t_monkey.set("—")
        if mc:
            self.t_mc_ret.set(f"{mc['ret_p5']:+.0f}% / {mc['ret_med']:+.0f}% / {mc['ret_p95']:+.0f}%", C["green"] if mc["prob_loss"] < 10 else C["yellow"])
            self.t_mc_ret.setToolTip(f"P(loss) {mc['prob_loss']:.1f}% · 1% risk per R, trades resampled")
            self.t_mc_dd.set(f"p50 {mc['dd_med']:.0f}% · p95 {mc['dd_p95']:.0f}%", C["green"] if mc["dd_p95"] < 20 else C["red"])
            self.t_mc_dd.setToolTip(f"max {mc['dd_max']:.0f}%")
        locks = ", ".join(f"{k}×{v}" for k, v in prot["locks"].items() if k != "cooldown") or "—"
        self.t_prot.set(f"PF {prot['base_pf']:.2f}→{prot['pf']:.2f} · DD {prot['base_dd']:.0f}→{prot['dd']:.0f}%",
                        C["green"] if prot["dd"] < prot["base_dd"] - 0.5 else C["muted"])
        self.t_prot.setToolTip(f"locks: {locks} · trades {prot['trades']}")
        self.t_sr.set(f"{sr:.2f}", color_for(sr))
        self.t_dsr.set(f"{dsr['dsr'] * 100:.0f}%", C["green"] if dsr["dsr"] >= 0.95 else (C["yellow"] if dsr["dsr"] >= 0.5 else C["red"]))
        self.t_sr0.set(f"{dsr['sr0']:.2f}")
        self.t_pbo.set(f"{pbo * 100:.0f}%  ({nv} variants)" if pbo == pbo else "—", C["green"] if pbo == pbo and pbo < 0.3 else (C["yellow"] if pbo == pbo and pbo < 0.5 else C["red"]))
        self.t_wfe.set(f"{wfe * 100:.0f}%", C["green"] if wfe >= 0.5 else C["red"])
        self.t_inc.set("✔ " + t("ql_go") if ok_all else "✖ " + t("ql_nogo"), C["green"] if ok_all else C["red"])
        self.inc_tbl.setSortingEnabled(False); self.inc_tbl.setRowCount(0)
        for k, ok in checks.items():
            i = self.inc_tbl.rowCount(); self.inc_tbl.insertRow(i)
            self.inc_tbl.setItem(i, 0, cell(k)); self.inc_tbl.setItem(i, 1, cell("✔" if ok else "✖", C["green"] if ok else C["red"]))
        self.of_txt.setText(t("ql_overfit_read").format(dsr=dsr["dsr"] * 100, sr0=dsr["sr0"], pbo=(pbo * 100 if pbo == pbo else float("nan"))))

    # ------------------------------------------------------------------ 4. patterns (Bulkowski / Nison)
    def _patterns_tab(self):
        w = QtWidgets.QWidget(); v = QtWidgets.QVBoxLayout(w)
        self.bar4 = SymbolBar(with_strategy=False); self.bar4.btn.setText(t("ql_scan_patterns")); self.bar4.changed.connect(self.run_patterns); v.addWidget(self.bar4)
        hint = QtWidgets.QLabel(t("ql_patterns_hint")); hint.setObjectName("subtitle"); hint.setWordWrap(True); v.addWidget(hint)
        sp = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        c1 = Card(t("ql_chart_patterns")); self.cp_tbl = make_table([t("ql_pattern"), t("side"), t("ql_level"), t("target"), t("stop"), t("ql_confirmed"), t("ql_fail_rate"), t("ql_avg_move"), t("ql_rank")]); c1.add(self.cp_tbl)
        c2 = Card(t("ql_candles")); self.cd_tbl = make_table([t("ql_pattern"), t("side"), t("ql_bar"), t("ql_rev_rate")]); c2.add(self.cd_tbl)
        sp.addWidget(c1); sp.addWidget(c2); sp.setSizes([700, 400]); v.addWidget(sp, 1)
        return w

    def run_patterns(self):
        sym, tf = self.bar4.symbol(), self.bar4.timeframe()
        self.bar4.btn.setEnabled(False)

        def work():
            df, ok = load_data(sym, tf)
            cs = [p for p in PT.candlesticks(df) if p["i_end"] >= len(df) - 10]
            ch = PT.chart_patterns(df)
            return df, cs, ch
        self.w4 = Worker(work); self.w4.done.connect(self._show_patterns)
        self.w4.error.connect(lambda e: (self.bar4.btn.setEnabled(True), QtWidgets.QMessageBox.warning(self, "Error", e))); self.w4.start()

    def _show_patterns(self, r):
        df, cs, ch = r
        fa = I18N.lang == "fa"
        self.bar4.btn.setEnabled(True)
        self.cp_tbl.setSortingEnabled(False); self.cd_tbl.setSortingEnabled(False)
        self.cp_tbl.setRowCount(0)
        for p in ch:
            i = self.cp_tbl.rowCount(); self.cp_tbl.insertRow(i)
            self.cp_tbl.setItem(i, 0, cell(p["name_fa"] if fa else p["name"].replace("_", " ")))
            self.cp_tbl.setItem(i, 1, cell(t("long") if p["side"] == 1 else t("short"), C["green"] if p["side"] == 1 else C["red"]))
            self.cp_tbl.setItem(i, 2, ncell(p["level"], "{:,.6g}")); self.cp_tbl.setItem(i, 3, ncell(p["target"], "{:,.6g}", C["green"])); self.cp_tbl.setItem(i, 4, ncell(p["stop"], "{:,.6g}", C["red"]))
            self.cp_tbl.setItem(i, 5, cell("✔" if p["confirmed"] else t("ql_pending"), C["green"] if p["confirmed"] else C["yellow"]))
            self.cp_tbl.setItem(i, 6, ncell(p["stats"]["fail"], "{:.0f}%", C["green"] if p["stats"]["fail"] <= 10 else C["yellow"])); self.cp_tbl.setItem(i, 7, ncell(p["stats"]["avg_move"], "{:+.0f}%")); self.cp_tbl.setItem(i, 8, ncell(p["stats"]["rank"], "#{:.0f}"))
        self.cd_tbl.setRowCount(0)
        for p in sorted(cs, key=lambda x: -x["i_end"]):
            i = self.cd_tbl.rowCount(); self.cd_tbl.insertRow(i)
            self.cd_tbl.setItem(i, 0, cell(p["name_fa"] if fa else p["name"].replace("_", " ")))
            self.cd_tbl.setItem(i, 1, cell(t("long") if p["side"] == 1 else t("short"), C["green"] if p["side"] == 1 else C["red"]))
            self.cd_tbl.setItem(i, 2, cell(str(df.index[p["i_end"]])[:16])); self.cd_tbl.setItem(i, 3, ncell(p["stats"]["reversal_rate"], "{:.0f}%", C["green"] if p["stats"]["reversal_rate"] >= 65 else None))
        self.cp_tbl.resizeColumnsToContents(); self.cd_tbl.resizeColumnsToContents()
        self.cp_tbl.setSortingEnabled(True); self.cd_tbl.setSortingEnabled(True)

    # ------------------------------------------------------------------ 5. psychology desk
    def _psy_tab(self):
        w = QtWidgets.QWidget(); v = QtWidgets.QVBoxLayout(w)
        sp = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        left = Card(t("ql_checklist"))
        self.checks = []
        for cid, en, fa in PSY.CHECKLIST:
            cb = QtWidgets.QCheckBox(fa if I18N.lang == "fa" else en); cb.stateChanged.connect(self._update_checklist); left.add(cb); self.checks.append(cb)
        self.check_res = QtWidgets.QLabel(""); self.check_res.setObjectName("h2"); left.add(self.check_res)
        gates = QtWidgets.QLabel(t("ql_gates")); gates.setWordWrap(True); gates.setObjectName("subtitle"); left.add(gates)
        ror = QtWidgets.QHBoxLayout()
        self.ror_wr = QtWidgets.QDoubleSpinBox(); self.ror_wr.setRange(1, 99); self.ror_wr.setValue(45); self.ror_wr.setSuffix("% WR")
        self.ror_pay = QtWidgets.QDoubleSpinBox(); self.ror_pay.setRange(0.1, 10); self.ror_pay.setValue(1.5); self.ror_pay.setPrefix("payoff ")
        self.ror_risk = QtWidgets.QDoubleSpinBox(); self.ror_risk.setRange(0.1, 20); self.ror_risk.setValue(1.0); self.ror_risk.setSuffix("% risk")
        bt = QtWidgets.QPushButton(t("ql_ror")); bt.clicked.connect(self._ror)
        for x in (self.ror_wr, self.ror_pay, self.ror_risk, bt):
            ror.addWidget(x)
        left.v.addLayout(ror)
        self.ror_lbl = QtWidgets.QLabel(""); self.ror_lbl.setWordWrap(True); left.add(self.ror_lbl)
        right = Card(t("ql_audit"))
        b = QtWidgets.QPushButton("🧠 " + t("ql_audit_run")); b.setObjectName("primary"); b.clicked.connect(self.run_audit); right.add(b)
        self.audit_box = QtWidgets.QVBoxLayout(); right.v.addLayout(self.audit_box); right.v.addStretch()
        sp.addWidget(left); sp.addWidget(right); v.addWidget(sp, 1)
        self._update_checklist()
        return w

    def _update_checklist(self):
        n = sum(cb.isChecked() for cb in self.checks)
        ok = n == len(self.checks)
        self.check_res.setText(("✅ " + t("ql_cleared")) if ok else f"⛔ {n}/{len(self.checks)} — " + t("ql_not_cleared"))
        self.check_res.setStyleSheet(f"color:{C['green'] if ok else C['red']}")

    def _ror(self):
        p = PSY.risk_of_ruin(self.ror_wr.value() / 100, self.ror_pay.value(), self.ror_risk.value())
        p2 = PSY.risk_of_ruin(self.ror_wr.value() / 100, self.ror_pay.value(), self.ror_risk.value() * 2)
        self.ror_lbl.setText(t("ql_ror_res").format(p * 100, self.ror_risk.value() * 2, p2 * 100))
        self.ror_lbl.setStyleSheet(f"color:{C['green'] if p < 0.01 else (C['yellow'] if p < 0.1 else C['red'])}")

    def run_audit(self):
        import json, os
        from .pages import JOURNAL_PATH
        rows = []
        if os.path.exists(JOURNAL_PATH):
            try:
                rows = json.load(open(JOURNAL_PATH, encoding="utf-8"))
            except Exception:
                rows = []
        # also audit closed forward-test records as if they were the trader's trades
        try:
            from core import forward as FW
            for r in FW.records("closed"):
                rows.append(dict(entry=r.get("fill") or r["entry"], stop=r["stop"], exit=r["exit"], side=r["side"], ts=r["exit_time"]))
        except Exception:
            pass
        while self.audit_box.count():
            it = self.audit_box.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        fa = I18N.lang == "fa"
        for f in PSY.audit_journal(rows):
            col = {"error": C["red"], "warn": C["yellow"], "info": C["accent2"]}[f["severity"]]
            l = QtWidgets.QLabel(f"<span style='color:{col}'>●</span> <b>{f['bias']}</b> — {f['fa'] if fa else f['en']}"); l.setWordWrap(True); l.setTextFormat(QtCore.Qt.TextFormat.RichText)
            self.audit_box.addWidget(l)
        if not rows:
            self.audit_box.addWidget(QtWidgets.QLabel(t("ql_audit_empty")))


    # ------------------------------------------------------------------ 6. Bot desk (Freqtrade pairlist · Hummingbot A-S · Blackbird · OctoBot · Elder 6%)
    def _bots_tab(self):
        w = QtWidgets.QWidget(); v = QtWidgets.QVBoxLayout(w)
        hint = QtWidgets.QLabel(t("ql_bots_hint")); hint.setObjectName("subtitle"); hint.setWordWrap(True); v.addWidget(hint)
        top = QtWidgets.QHBoxLayout()
        self.bar6 = SymbolBar(with_strategy=False); self.bar6.btn.setText(t("ql_bots_run")); self.bar6.changed.connect(self.run_bots)
        top.addWidget(self.bar6, 1)
        v.addLayout(top)
        # A-S params
        prow = QtWidgets.QHBoxLayout()
        self.as_gamma = QtWidgets.QDoubleSpinBox(); self.as_gamma.setRange(0.001, 1000); self.as_gamma.setDecimals(3); self.as_gamma.setValue(0.1)
        self.as_inv = QtWidgets.QDoubleSpinBox(); self.as_inv.setRange(0, 100); self.as_inv.setValue(50); self.as_inv.setSuffix(" %")
        self.as_fee = QtWidgets.QDoubleSpinBox(); self.as_fee.setRange(0, 1); self.as_fee.setDecimals(3); self.as_fee.setValue(0.1); self.as_fee.setSuffix(" %")
        for lab, wd in ((t("ql_as_gamma"), self.as_gamma), (t("ql_as_inv"), self.as_inv), (t("ql_as_fee"), self.as_fee)):
            prow.addWidget(QtWidgets.QLabel(lab)); prow.addWidget(wd)
        prow.addStretch(1); v.addLayout(prow)
        tiles = QtWidgets.QHBoxLayout()
        self.t_as_res = StatTile(t("ql_as_res")); self.t_as_spread = StatTile(t("ql_as_spread")); self.t_as_quotes = StatTile("Bid / Ask"); self.t_as_edge = StatTile(t("ql_as_edge"))
        for x in (self.t_as_res, self.t_as_spread, self.t_as_quotes, self.t_as_edge):
            tiles.addWidget(x)
        v.addLayout(tiles)
        split = QtWidgets.QHBoxLayout()
        self.pl_tbl = make_table([t("symbol"), t("ql_pl_kept"), t("ql_pl_reason"), t("ql_vol_ann"), t("ql_range_pct"), t("ql_spread_proxy"), t("ql_quote_vol")])
        c1 = Card(t("ql_pl_title")); c1.add(self.pl_tbl); split.addWidget(c1, 3)
        right = QtWidgets.QVBoxLayout()
        self.octo_tbl = make_table([t("ql_octo_eval"), t("ql_octo_val"), t("ql_octo_w")]); c2 = Card(t("ql_octo_title")); c2.add(self.octo_tbl); right.addWidget(c2, 1)
        self.bots_txt = QtWidgets.QLabel(""); self.bots_txt.setWordWrap(True); self.bots_txt.setTextFormat(QtCore.Qt.TextFormat.RichText); right.addWidget(self.bots_txt)
        split.addLayout(right, 2)
        v.addLayout(split, 1)
        return w

    def run_bots(self):
        from core.pairlist import apply_pairlist
        from core.marketmaking import market_making_edge_report, blackbird_spread
        sym, tf = self.bar6.symbol(), self.bar6.timeframe()
        gamma, inv, fee = self.as_gamma.value(), self.as_inv.value() / 100, self.as_fee.value() / 100
        self.bar6.btn.setEnabled(False)

        def work():
            df, ok = load_data(sym, tf)
            mm = market_making_edge_report(df, gamma=gamma, target_inventory=0.5, current_inventory=inv, fee=fee)
            syms = [x[1] if isinstance(x, tuple) else x for x in all_symbols()]
            data = {}
            for s_ in syms[:40]:
                try:
                    d, _ = load_data(s_, tf); data[s_] = d
                except Exception:
                    continue
            delta = (df.index[1:] - df.index[:-1]).median(); ppy = float(pd.Timedelta(days=365) / delta)
            kept, rep = apply_pairlist(data, periods_per_year=ppy, top_n=20)
            # OctoBot evaluator matrix on this symbol
            from core import indicators as ta
            c = df.close
            rsi = float(ta.rsi(c, 14).iloc[-1]); r_eval = (rsi - 50) / 50  # OctoBot convention: RSI high → +1 (bearish)
            macd = ta.ema(c, 12) - ta.ema(c, 26); hist = macd - ta.ema(macd, 9)
            m_eval = float(-np.sign(hist.iloc[-1]) * min(1, abs(hist.iloc[-1]) / (c.iloc[-1] * 0.002)))
            mid = ta.sma(c, 20); sd = c.rolling(20).std(); bbpos = float((c.iloc[-1] - mid.iloc[-1]) / (2 * sd.iloc[-1])) if sd.iloc[-1] > 0 else 0
            b_eval = float(np.clip(bbpos, -1, 1))
            ema50 = ta.ema(c, 50); tr_eval = float(-np.clip((c.iloc[-1] / ema50.iloc[-1] - 1) / 0.05, -1, 1))
            evals = {"RSI": float(np.clip(r_eval, -1, 1)), "MACD hist": m_eval, "Bollinger": b_eval, "Trend (EMA50)": tr_eval}
            octo = Q2.octobot_matrix(evals, {"RSI": 1.0, "MACD hist": 1.0, "Bollinger": 1.0, "Trend (EMA50)": 1.5}, 0.4)
            # Blackbird demo with synthetic second venue (±5 bps)
            px = float(c.iloc[-1]); bb = blackbird_spread(px * 0.9997, px * 1.0003, px * 1.0005, px * 1.0011, fee, fee)
            return df, mm, kept, rep, octo, evals, bb
        self.w6 = Worker(work); self.w6.done.connect(self._show_bots)
        self.w6.error.connect(lambda e: (self.bar6.btn.setEnabled(True), QtWidgets.QMessageBox.warning(self, "Error", e))); self.w6.start()

    def _show_bots(self, r):
        df, mm, kept, rep, octo, evals, bb = r
        self.bar6.btn.setEnabled(True)
        self.t_as_res.set(f"{mm['reservation']:,.5g}  ({mm['skew_pct']:+.2f}%)", C["accent2"])
        self.t_as_spread.set(f"{mm['spread_pct']:.3f}%"); self.t_as_spread.setToolTip(f"κ={mm['kappa']:.0f} · σ={mm['sigma'] * 100:.3f}%/candle · γ={mm['gamma']}")
        self.t_as_quotes.set(f"{mm['bid']:,.5g} / {mm['ask']:,.5g}")
        self.t_as_edge.set(f"{mm['edge_pct']:+.3f}%", C["green"] if mm["viable"] else C["red"]); self.t_as_edge.setToolTip(t("ql_as_after_fees") + f" ({mm['fee_rt_pct']:.2f}%)")
        self.pl_tbl.setSortingEnabled(False); self.pl_tbl.setRowCount(0)
        for s_, m in sorted(rep.items(), key=lambda kv: (not kv[1].get("kept", False), -kv[1].get("quote_volume", 0))):
            i = self.pl_tbl.rowCount(); self.pl_tbl.insertRow(i)
            k = m.get("kept", False)
            self.pl_tbl.setItem(i, 0, cell(s_)); self.pl_tbl.setItem(i, 1, cell("✔" if k else "✖", C["green"] if k else C["red"]))
            self.pl_tbl.setItem(i, 2, cell(m.get("reason", "")))
            self.pl_tbl.setItem(i, 3, ncell(m.get("volatility", 0), "{:.2f}")); self.pl_tbl.setItem(i, 4, ncell(m.get("roc", 0) * 100, "{:.1f}"))
            self.pl_tbl.setItem(i, 5, ncell(m.get("spread", 0) * 100, "{:.2f}")); self.pl_tbl.setItem(i, 6, ncell(m.get("quote_volume", 0), "{:,.0f}"))
        self.pl_tbl.setSortingEnabled(True)
        self.octo_tbl.setSortingEnabled(False); self.octo_tbl.setRowCount(0)
        for k, v in evals.items():
            i = self.octo_tbl.rowCount(); self.octo_tbl.insertRow(i)
            self.octo_tbl.setItem(i, 0, cell(k)); self.octo_tbl.setItem(i, 1, ncell(v, "{:+.2f}")); self.octo_tbl.setItem(i, 2, ncell(octo["contributions"][k], "{:+.2f}"))
        i = self.octo_tbl.rowCount(); self.octo_tbl.insertRow(i)
        col = C["green"] if octo["state"] == "LONG" else (C["red"] if octo["state"] == "SHORT" else C["muted"])
        self.octo_tbl.setItem(i, 0, cell(t("ql_octo_avg"), col)); self.octo_tbl.setItem(i, 1, ncell(octo["average"], "{:+.2f}")); self.octo_tbl.setItem(i, 2, cell(octo["state"], col))
        best = max(bb, key=lambda x: x["net_pct"])
        self.bots_txt.setText(t("ql_bots_read").format(kept=len(kept), total=len(rep), bb_net=best["net_pct"], bb_long=best["long"], bb_short=best["short"]))
