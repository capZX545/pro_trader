"""
Self-diagnosis ("the bot fixes its own future problems").

run_checks() returns a list of findings, each with severity, a bilingual message and — when possible — an
auto-fix callable that the Health page can execute with one click:
  • data     : stale/empty parquet cache, symbols that stopped downloading, zero-volume series
  • playbook : older than 14 days, strategies missing from it (e.g. newly added), edge decay (last-year PF < 0.9)
  • validation: strategies never validated
  • forward  : open records not updated for > 1 day; backtest→reality gap worse than 0.6
  • strategies: any strategy raising an exception on a standard dataframe
  • environment: missing optional packages, no internet
"""
import os
import time
import json
import traceback
import numpy as np

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(APP_DIR, "data")
DAY = 86400


class Finding:
    def __init__(self, area, severity, en, fa, fix=None, fix_label=("Fix", "رفع")):
        self.area, self.severity, self.en, self.fa, self.fix, self.fix_label = area, severity, en, fa, fix, fix_label

    def __repr__(self):
        return f"[{self.severity}] {self.area}: {self.en}"


def _age(path):
    return (time.time() - os.path.getmtime(path)) / DAY if os.path.exists(path) else 1e9


def check_strategies(sample=None):
    import strategies as S
    from core.data import get_ohlcv, generate_synthetic
    out = []
    if sample is None:
        try:
            sample = get_ohlcv("BTC/USDT", "1d")
        except Exception:
            sample = generate_synthetic(1500)
    for cls in S.ALL_STRATEGIES:
        try:
            r = cls().run(sample)
            if r.signal is None or len(r.signal) != len(sample):
                raise ValueError("signal length mismatch")
            if r.signal.abs().sum() == 0:
                out.append(Finding("strategies", "info", f"{cls.id}: no signals on BTC 1d (may be market-specific)",
                                   f"{cls.id}: روی BTC روزانه سیگنالی ندارد (شاید مخصوص بازار دیگری است)"))
        except Exception as e:
            out.append(Finding("strategies", "error", f"{cls.id} crashed: {e}", f"{cls.id} خطا داد: {e}"))
    return out


def check_playbook():
    from core import playbook as PB
    import strategies as S
    out = []
    pb = PB.load()
    if not pb:
        out.append(Finding("playbook", "error", "Playbook missing — Advisor/Scanner are blind.",
                           "کتاب راهنما وجود ندارد — مشاور و اسکنر کور هستند.",
                           fix=lambda: PB.build_playbook(S.ALL_STRATEGIES), fix_label=("Build playbook", "ساخت کتاب راهنما")))
        return out
    age = (time.time() - pb.get("ts", 0)) / DAY
    if age > 14:
        out.append(Finding("playbook", "warn", f"Playbook is {age:.0f} days old — markets drift; rebuild.",
                           f"کتاب راهنما {age:.0f} روز قدیمی است — بازار تغییر می‌کند؛ بازسازی کنید.",
                           fix=lambda: PB.build_playbook(S.ALL_STRATEGIES), fix_label=("Rebuild", "بازسازی")))
    have = {sid for tf in pb["table"].values() for g in tf.values() for sid in g}
    missing = [c.id for c in S.ALL_STRATEGIES if c.id not in have]
    if missing:
        out.append(Finding("playbook", "warn", f"{len(missing)} strategies not in playbook: {', '.join(missing[:6])}…",
                           f"{len(missing)} استراتژی در کتاب راهنما نیستند: {', '.join(missing[:6])}…",
                           fix=lambda: PB.build_playbook(S.ALL_STRATEGIES), fix_label=("Rebuild", "بازسازی")))
    # edge decay: proven combos whose last-year PF collapsed
    decayed = []
    for tf, gd in pb.get("best", {}).items():
        for g, rows in gd.items():
            for sid, _ in rows:
                st = pb["table"][tf][g].get(sid, {})
                ly = st.get("last_year_pf")
                if ly is not None and ly == ly and ly < 0.9:
                    decayed.append(f"{sid}@{tf}/{g}")
    if decayed:
        out.append(Finding("playbook", "warn", f"Edge decay in last 12 months: {', '.join(decayed[:5])}",
                           f"افت لبه در ۱۲ ماه اخیر: {', '.join(decayed[:5])}"))
    return out


def check_validation():
    from core import validation as V
    import strategies as S
    out = []
    cache = V.load_cache()
    missing = [c for c in S.ALL_STRATEGIES if c.id not in cache]
    if missing:
        def fix(m=missing):
            c = V.load_cache()
            for cls in m:
                c[cls.id] = V.validate_strategy(cls)
            V.save_cache(c)
        out.append(Finding("validation", "warn", f"{len(missing)} strategies never validated.",
                           f"{len(missing)} استراتژی هرگز اعتبارسنجی نشده‌اند.", fix=fix, fix_label=("Validate", "اعتبارسنجی")))
    return out


def check_data():
    from core.data import get_ohlcv
    out = []
    # internet / source reachability
    try:
        df = get_ohlcv("BTC/USDT", "1h", max_age_sec=0)
        lag_h = (time.time() - df.index[-1].timestamp()) / 3600
        if lag_h > 3:
            out.append(Finding("data", "warn", f"BTC 1h data lags {lag_h:.1f} h — source stale?", f"دادهٔ BTC ساعتی {lag_h:.1f} ساعت عقب است — منبع قدیمی؟"))
    except Exception as e:
        out.append(Finding("data", "error", f"Cannot download crypto data: {str(e)[:80]}", f"دانلود دادهٔ کریپتو ممکن نیست: {str(e)[:80]}"))
    try:
        df = get_ohlcv("S&P 500", "1d", max_age_sec=0)
        lag_d = (time.time() - df.index[-1].timestamp()) / DAY
        if lag_d > 5:
            out.append(Finding("data", "warn", f"S&P 500 daily data lags {lag_d:.0f} days", f"دادهٔ روزانهٔ S&P {lag_d:.0f} روز عقب است"))
    except Exception as e:
        out.append(Finding("data", "error", f"Cannot download stock data: {str(e)[:80]}", f"دانلود دادهٔ سهام ممکن نیست: {str(e)[:80]}"))
    # zero-volume caches (volume strategies meaningless there)
    zero = []
    if os.path.isdir(DATA):
        import pandas as pd
        for f in os.listdir(DATA):
            if f.endswith(".parquet"):
                try:
                    from core.data import _read_cache
                    d = _read_cache(os.path.join(DATA, f))
                    if (d.volume.fillna(0) == 0).mean() > 0.9:
                        zero.append(f.replace(".parquet", ""))
                except Exception:
                    pass
    if zero:
        out.append(Finding("data", "info", f"No volume data for: {', '.join(zero[:6])} — volume strategies are disabled there.",
                           f"حجم برای {', '.join(zero[:6])} موجود نیست — استراتژی‌های حجمی آنجا غیرفعال‌اند."))
    return out


def check_forward():
    from core import forward as FW
    out = []
    rep = FW.report()
    if rep["n_open"] and (rep["last_update"] is None or time.time() - rep["last_update"] > DAY):
        out.append(Finding("forward", "warn", f"{rep['n_open']} open forward-test records not updated in 24h.",
                           f"{rep['n_open']} رکورد باز تست پیش‌رو ۲۴ ساعت به‌روز نشده‌اند.", fix=lambda: FW.update(), fix_label=("Update", "به‌روزرسانی")))
    if rep.get("gap_pf") is not None and rep["gap_pf"] < 0.6:
        out.append(Finding("forward", "error", f"Reality is {100 * (1 - rep['gap_pf']):.0f}% worse than backtests (PF ratio {rep['gap_pf']:.2f}). "
                           "Discount all backtest numbers accordingly and rebuild the playbook.",
                           f"واقعیت {100 * (1 - rep['gap_pf']):.0f}٪ بدتر از بک‌تست است (نسبت PF {rep['gap_pf']:.2f}). همهٔ اعداد بک‌تست را با این ضریب تخفیف بدهید."))
    if rep["verdict"] == "no_edge" and rep["n_closed"] >= 50:
        out.append(Finding("forward", "error", "Forward test shows NO edge after 50+ trades. Do not trade real money.",
                           "تست پیش‌رو بعد از ۵۰+ معامله هیچ لبه‌ای نشان نمی‌دهد. با پول واقعی معامله نکنید."))
    return out


def _try_import(m):
    try:
        __import__(m)
        return True
    except Exception:
        return False


def check_env():
    out = []
    for mod, why in (("pyarrow|fastparquet", "parquet cache"), ("sklearn", "ML lab"), ("websocket", "live stream")):
        try:
            if mod.startswith("pyarrow"):
                continue   # data.py falls back to pickle cache automatically; not a problem
            if not any(_try_import(m) for m in mod.split("|")):
                raise ImportError
        except Exception:
            out.append(Finding("env", "warn", f"Package '{mod}' missing ({why}).", f"بستهٔ '{mod}' نصب نیست ({why})."))
    return out


def run_checks(quick=False, progress=None):
    findings = []
    steps = [("env", check_env), ("playbook", check_playbook), ("validation", check_validation), ("forward", check_forward)]
    if not quick:
        steps += [("data", check_data), ("strategies", check_strategies)]
    for k, (name, fn) in enumerate(steps):
        if progress:
            progress(int(k / len(steps) * 100), name)
        try:
            findings += fn()
        except Exception as e:
            findings.append(Finding(name, "error", f"check failed: {e}", f"بررسی شکست خورد: {e}"))
    order = {"error": 0, "warn": 1, "info": 2}
    findings.sort(key=lambda f: order.get(f.severity, 3))
    return findings


def summary(findings):
    return dict(errors=sum(f.severity == "error" for f in findings), warns=sum(f.severity == "warn" for f in findings),
                infos=sum(f.severity == "info" for f in findings))
