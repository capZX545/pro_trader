"""Chart indicator engine (Phase 17): every catalog indicator → overlays / panels the chart can draw.

`compute(df, key, **params)` returns dict(overlays={name: Series}, panels={panel_name: {series: Series}},
levels=[(price,label,color)], bands=[(upper, lower, color)], hlines={panel: [values]}).
`SPECS[key]` gives default params (editable in the chart's indicator dialog) and where it draws.
Used by ui.chart (indicator picker), core.analyst and the Academy encyclopedia ("show on chart").
"""
import numpy as np
import pandas as pd
from core import indicators as ta
from core import indicators2 as t2

# key -> (place: "overlay"|"panel", default params)
SPECS = {
    "sma": ("overlay", {"n": 50}), "ema": ("overlay", {"n": 20}), "wma": ("overlay", {"n": 20}), "hma": ("overlay", {"n": 20}),
    "dema": ("overlay", {"n": 20}), "tema": ("overlay", {"n": 20}), "zlema": ("overlay", {"n": 20}), "vwma": ("overlay", {"n": 20}),
    "kama": ("overlay", {"n": 10, "fast": 2, "slow": 30}), "alma": ("overlay", {"n": 9, "offset": 0.85, "sigma": 6}), "t3": ("overlay", {"n": 5, "vf": 0.7}),
    "mcginley": ("overlay", {"n": 14}), "supersmoother": ("overlay", {"n": 10}), "linreg": ("overlay", {"n": 100, "k": 2.0}),
    "ichimoku": ("overlay", {"tenkan": 9, "kijun": 26, "senkou": 52}), "supertrend": ("overlay", {"n": 10, "mult": 3.0}),
    "psar": ("overlay", {"af": 0.02, "af_max": 0.2}), "halftrend": ("overlay", {"amp": 2, "dev": 2.0}),
    "bollinger": ("overlay", {"n": 20, "k": 2.0}), "keltner": ("overlay", {"n": 20, "mult": 1.5}), "donchian": ("overlay", {"n": 20}),
    "vwap": ("overlay", {}), "pivots": ("overlay", {"kind": 0}), "fibonacci": ("overlay", {"lookback": 200}), "zigzag": ("overlay", {"pct": 3.0}),
    "volume_profile": ("overlay", {"bins": 24, "lookback": 300}), "heikin_ashi": ("overlay", {}),
    "adx": ("panel", {"n": 14}), "aroon": ("panel", {"n": 25}), "vortex": ("panel", {"n": 14}), "trix": ("panel", {"n": 15, "sig": 9}),
    "kst": ("panel", {}), "coppock": ("panel", {}), "dpo": ("panel", {"n": 20}), "schaff": ("panel", {}), "hurst": ("panel", {"n": 100}),
    "efficiency_ratio": ("panel", {"n": 10}), "choppiness": ("panel", {"n": 14}),
    "rsi": ("panel", {"n": 14}), "stoch": ("panel", {"k": 14, "d": 3, "smooth": 3}), "stoch_rsi": ("panel", {"n": 14, "k": 3, "d": 3}),
    "macd": ("panel", {"fast": 12, "slow": 26, "sig": 9}), "ppo": ("panel", {"fast": 12, "slow": 26, "sig": 9}), "cci": ("panel", {"n": 20}),
    "williams_r": ("panel", {"n": 14}), "roc": ("panel", {"n": 12}), "cmo": ("panel", {"n": 14}), "ultimate": ("panel", {}),
    "awesome": ("panel", {}), "accelerator": ("panel", {}), "fisher": ("panel", {"n": 9}), "rvi": ("panel", {"n": 10}),
    "connors_rsi": ("panel", {}), "qqe": ("panel", {"n": 14}), "squeeze": ("panel", {}), "elder_ray": ("panel", {"n": 13}),
    "atr": ("panel", {"n": 14}), "hist_vol": ("panel", {"n": 20}), "mass_index": ("panel", {}), "zscore": ("panel", {"n": 20}),
    "obv": ("panel", {}), "ad_line": ("panel", {}), "chaikin_osc": ("panel", {}), "cmf": ("panel", {"n": 20}), "mfi": ("panel", {"n": 14}),
    "force_index": ("panel", {"n": 13}), "eom": ("panel", {"n": 14}), "vpt": ("panel", {}), "nvi_pvi": ("panel", {}), "klinger": ("panel", {}),
    "relative_volume": ("panel", {"n": 20}), "cvd": ("panel", {}), "rs_vs": ("panel", {"n": 20}),
}

BAND_COLORS = {"bollinger": "#4f8ef7", "keltner": "#c084fc", "donchian": "#f59e0b", "linreg": "#22d3ee", "ichimoku": "#22c55e"}


def _cvd(df):
    rng = (df.high - df.low).replace(0, np.nan)
    delta = df.volume * (2 * (df.close - df.low) / rng - 1).fillna(0)
    return delta.cumsum()


def compute(df, key, **p):
    place, dflt = SPECS.get(key, ("panel", {}))
    q = dict(dflt); q.update({k: v for k, v in p.items() if k in dflt})
    c = df.close
    O, P, L, B, H = {}, {}, [], [], {}
    lab = f"{key.upper()}({','.join(str(v) for v in q.values())})" if q else key.upper()
    if key in ("sma", "ema", "wma", "hma"):
        O[lab] = getattr(ta, key)(c, q["n"])
    elif key in ("dema", "tema", "zlema", "mcginley", "supersmoother"):
        O[lab] = getattr(t2, key)(c, q["n"])
    elif key == "vwma":
        O[lab] = t2.vwma(df, q["n"])
    elif key == "kama":
        O[lab] = t2.kama(c, q["n"], q["fast"], q["slow"])
    elif key == "alma":
        O[lab] = t2.alma(c, q["n"], q["offset"], q["sigma"])
    elif key == "t3":
        O[lab] = t2.t3(c, q["n"], q["vf"])
    elif key == "linreg":
        v, u, l, _ = t2.lin_reg_channel(c, q["n"], q["k"]); O["LinReg"] = v; O["LR +σ"] = u; O["LR −σ"] = l; B.append(("LR +σ", "LR −σ", BAND_COLORS["linreg"]))
    elif key == "ichimoku":
        t, k, sa, sb, lag = ta.ichimoku(df, q["tenkan"], q["kijun"], q["senkou"])
        O["Tenkan"] = t; O["Kijun"] = k; O["Senkou A"] = sa; O["Senkou B"] = sb; O["Chikou"] = lag
        B.append(("Senkou A", "Senkou B", "kumo"))
    elif key == "supertrend":
        st = ta.supertrend(df, q["n"], q["mult"]); O[lab] = st[0] if isinstance(st, tuple) else st
    elif key == "psar":
        O["PSAR"] = ta.parabolic_sar(df, q["af"], q["af_max"])
    elif key == "halftrend":
        _, line = t2.halftrend(df, q["amp"], q["dev"]); O["HalfTrend"] = line
    elif key == "bollinger":
        u, m, l = ta.bollinger(c, q["n"], q["k"]); O["BB up"] = u; O["BB mid"] = m; O["BB low"] = l; B.append(("BB up", "BB low", BAND_COLORS[key]))
    elif key == "keltner":
        u, m, l = ta.keltner(df, q["n"], q["mult"]); O["KC up"] = u; O["KC mid"] = m; O["KC low"] = l; B.append(("KC up", "KC low", BAND_COLORS[key]))
    elif key == "donchian":
        u, l = ta.donchian(df, q["n"]); O["DC up"] = u; O["DC low"] = l; O["DC mid"] = (u + l) / 2; B.append(("DC up", "DC low", BAND_COLORS[key]))
    elif key == "vwap":
        O["VWAP"] = ta.vwap(df)
        sd = (c - O["VWAP"]).rolling(50).std()
        O["VWAP +1σ"] = O["VWAP"] + sd; O["VWAP −1σ"] = O["VWAP"] - sd
    elif key == "pivots":
        kind = int(q["kind"])
        if kind == 1:
            d = t2.pivots_fib(df)
        elif kind == 2:
            d = t2.pivots_camarilla(df)
        elif kind == 3:
            d = t2.pivots_woodie(df)
        else:
            pp, r1, s1, r2, s2 = ta.pivot_points(df); d = {"P": pp, "R1": r1, "S1": s1, "R2": r2, "S2": s2}
        for k_, s_ in d.items():
            O[f"Piv {k_}"] = s_
    elif key == "fibonacci":
        seg = df.tail(int(q["lookback"]))
        hi, lo = float(seg.high.max()), float(seg.low.min())
        up = seg.high.values.argmax() > seg.low.values.argmin()
        for r, v in ta.fibonacci_levels(hi, lo, up).items():
            L.append((float(v), f"Fib {r}", "#f5c542" if r in (0.618, 0.705) else "#94a3b8"))
    elif key == "zigzag":
        O["ZigZag"] = t2.zigzag(df, q["pct"]).interpolate(limit_area="inside")
    elif key == "volume_profile":
        poc, val, vah, _ = t2.volume_profile(df, int(q["bins"]), int(q["lookback"]))
        L += [(float(poc), "POC", "#f5c542"), (float(vah), "VAH", "#94a3b8"), (float(val), "VAL", "#94a3b8")]
    elif key == "heikin_ashi":
        ha = t2.heikin_ashi(df); O["HA open"] = ha.open; O["HA close"] = ha.close
    # ---------------- panels
    elif key == "adx":
        a, pdi, mdi = ta.adx(df, q["n"]); P["ADX"] = {"ADX": a, "+DI": pdi, "−DI": mdi}; H["ADX"] = [20, 25]
    elif key == "aroon":
        u, d, o = t2.aroon(df, q["n"]); P["Aroon"] = {"Up": u, "Down": d}; H["Aroon"] = [30, 70]
    elif key == "vortex":
        vp, vm = t2.vortex(df, q["n"]); P["Vortex"] = {"VI+": vp, "VI−": vm}; H["Vortex"] = [1]
    elif key == "trix":
        tr = t2.trix(c, q["n"]); P["TRIX"] = {"TRIX": tr, "Signal": ta.ema(tr, q["sig"])}; H["TRIX"] = [0]
    elif key == "kst":
        k, s = t2.kst(c); P["KST"] = {"KST": k, "Signal": s}; H["KST"] = [0]
    elif key == "coppock":
        P["Coppock"] = {"Coppock": t2.coppock(c)}; H["Coppock"] = [0]
    elif key == "dpo":
        P["DPO"] = {"DPO": t2.dpo(c, q["n"])}; H["DPO"] = [0]
    elif key == "schaff":
        P["Schaff"] = {"STC": t2.schaff(c)}; H["Schaff"] = [25, 75]
    elif key == "hurst":
        P["Hurst"] = {"H": t2.hurst(c, q["n"])}; H["Hurst"] = [0.5]
    elif key == "efficiency_ratio":
        P["ER"] = {"ER": t2.efficiency_ratio(c, q["n"])}; H["ER"] = [0.3]
    elif key == "choppiness":
        P["Chop"] = {"CHOP": t2.choppiness(df, q["n"])}; H["Chop"] = [38.2, 61.8]
    elif key == "rsi":
        P[f"RSI({q['n']})"] = {"RSI": ta.rsi(c, q["n"])}; H[f"RSI({q['n']})"] = [30, 50, 70]
    elif key == "stoch":
        k, d = ta.stochastic(df, q["k"], q["d"], q["smooth"]); P["Stoch"] = {"%K": k, "%D": d}; H["Stoch"] = [20, 80]
    elif key == "stoch_rsi":
        k, d = ta.stoch_rsi(c, q["n"], q["k"], q["d"]); P["StochRSI"] = {"%K": k, "%D": d}; H["StochRSI"] = [20, 80]
    elif key == "macd":
        m, s, h = ta.macd(c, q["fast"], q["slow"], q["sig"]); P["MACD"] = {"MACD": m, "Signal": s, "hist": h}; H["MACD"] = [0]
    elif key == "ppo":
        m, s = t2.ppo(c, q["fast"], q["slow"], q["sig"]); P["PPO"] = {"PPO": m, "Signal": s, "hist": m - s}; H["PPO"] = [0]
    elif key == "cci":
        P["CCI"] = {"CCI": ta.cci(df, q["n"])}; H["CCI"] = [-100, 100]
    elif key == "williams_r":
        P["Williams %R"] = {"%R": ta.williams_r(df, q["n"])}; H["Williams %R"] = [-80, -20]
    elif key == "roc":
        P["ROC"] = {"ROC": ta.roc(c, q["n"])}; H["ROC"] = [0]
    elif key == "cmo":
        P["CMO"] = {"CMO": t2.cmo(c, q["n"])}; H["CMO"] = [-50, 50]
    elif key == "ultimate":
        P["Ultimate"] = {"UO": t2.ultimate(df)}; H["Ultimate"] = [30, 70]
    elif key == "awesome":
        P["AO"] = {"hist": t2.awesome(df)}; H["AO"] = [0]
    elif key == "accelerator":
        P["AC"] = {"hist": t2.accelerator(df)}; H["AC"] = [0]
    elif key == "fisher":
        f = t2.fisher(df, q["n"]); f = f[0] if isinstance(f, tuple) else f; P["Fisher"] = {"Fisher": f, "Trigger": f.shift(1)}; H["Fisher"] = [-1.5, 1.5]
    elif key == "rvi":
        r, s = t2.rvi(df, q["n"]); P["RVI"] = {"RVI": r, "Signal": s}; H["RVI"] = [0]
    elif key == "connors_rsi":
        P["ConnorsRSI"] = {"CRSI": t2.connors_rsi(c)}; H["ConnorsRSI"] = [10, 90]
    elif key == "qqe":
        qq = t2.qqe(c, q["n"]); qq = qq if isinstance(qq, tuple) else (qq,); P["QQE"] = {"RSI-MA": qq[0], **({"Trail": qq[1]} if len(qq) > 1 else {})}; H["QQE"] = [50]
    elif key == "squeeze":
        on, val = t2.squeeze_momentum(df); P["Squeeze"] = {"momentum": val, "squeeze": on.astype(float) * val.abs().max() * 0.05}; H["Squeeze"] = [0]
    elif key == "elder_ray":
        bull, bear = t2.elder_ray(df, q["n"]); P["Elder Ray"] = {"Bull": bull, "Bear": bear}; H["Elder Ray"] = [0]
    elif key == "atr":
        P["ATR"] = {"ATR": ta.atr(df, q["n"]), "ATR %": ta.atr(df, q["n"]) / c * 100}
    elif key == "hist_vol":
        P["HV"] = {"HV %": t2.hist_vol(c, q["n"])}
    elif key == "mass_index":
        P["Mass"] = {"MI": t2.mass_index(df)}; H["Mass"] = [26.5, 27]
    elif key == "zscore":
        P["Z"] = {"z": t2.zscore(c, q["n"])}; H["Z"] = [-2, 0, 2]
    elif key == "obv":
        P["OBV"] = {"OBV": ta.obv(df), "EMA21": ta.ema(ta.obv(df), 21)}
    elif key == "ad_line":
        P["A/D"] = {"A/D": t2.ad_line(df)}
    elif key == "chaikin_osc":
        P["Chaikin"] = {"CO": t2.chaikin_osc(df)}; H["Chaikin"] = [0]
    elif key == "cmf":
        P["CMF"] = {"CMF": ta.cmf(df, q["n"])}; H["CMF"] = [0]
    elif key == "mfi":
        P["MFI"] = {"MFI": ta.mfi(df, q["n"])}; H["MFI"] = [20, 80]
    elif key == "force_index":
        P["Force"] = {"hist": t2.force_index(df, q["n"])}; H["Force"] = [0]
    elif key == "eom":
        P["EOM"] = {"EOM": t2.eom(df, q["n"])}; H["EOM"] = [0]
    elif key == "vpt":
        P["VPT"] = {"VPT": t2.vpt(df)}
    elif key == "nvi_pvi":
        P["NVI/PVI"] = {"NVI": t2.nvi(df), "PVI": t2.pvi(df)}
    elif key == "klinger":
        k = t2.klinger(df); k = k if isinstance(k, tuple) else (k, ta.ema(k, 13)); P["Klinger"] = {"KVO": k[0], "Signal": k[1]}; H["Klinger"] = [0]
    elif key == "relative_volume":
        P["RVOL"] = {"hist": t2.relative_volume(df, q["n"]) - 1}; H["RVOL"] = [0, 1]
    elif key == "cvd":
        P["CVD"] = {"CVD": _cvd(df)}
    elif key == "rs_vs":
        P["RS"] = {"RS": c.pct_change(q["n"]) * 100}; H["RS"] = [0]
    else:
        raise KeyError(key)
    return dict(overlays=O, panels=P, levels=L, bands=B, hlines=H)


def names():
    """[(key, name_en, name_fa, group)] for the picker, catalog order + extras."""
    out = []
    seen = set()
    for d in t2.INDICATOR_CATALOG:
        if d["key"] in SPECS:
            out.append((d["key"], d["name_en"], d["name_fa"], d["group"])); seen.add(d["key"])
    for k in SPECS:
        if k not in seen:
            out.append((k, k.upper(), k.upper(), "Volume" if k == "cvd" else "Other"))
    return out
