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

from core.paths import DATA_DIR as DATA, SRC_ROOT as APP_DIR
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


def check_audit():
    """Phase 12: look-ahead / random-data audit of every strategy (data/audit.json)"""
    from core import audit as A
    a = A.load()
    out = []
    if not a:
        def fix():
            import strategies as S
            A.run_all(S.ALL_STRATEGIES)
        out.append(Finding("audit", "warn", "Strategy audit has never run (look-ahead & random-data tests).",
                           "ممیزی استراتژی‌ها هرگز اجرا نشده (آزمون نگاه‌به‌آینده و دادهٔ تصادفی).", fix, ("Run audit", "اجرای ممیزی")))
        return out
    s = a.get("summary", {})
    for sid, v in a.get("results", {}).items():
        if v["status"] == "fail":
            out.append(Finding("audit", "error", f"{sid}: {'; '.join(v['findings'][:2])} → excluded from Playbook/Advisor",
                               f"{sid}: {'; '.join(v['findings'][:2])} ← از پلی‌بوک/مشاور حذف شد"))
        elif v["status"] == "warn":
            out.append(Finding("audit", "info", f"{sid}: {'; '.join(f for f in v['findings'] if not f.startswith('random-data PF'))[:160]}",
                               f"{sid}: {'; '.join(f for f in v['findings'] if not f.startswith('random-data PF'))[:160]}"))
    if _age(A.PATH) > 30:
        out.append(Finding("audit", "warn", f"Audit is {_age(A.PATH):.0f} days old.", f"ممیزی {_age(A.PATH):.0f} روز قدیمی است."))
    out.append(Finding("audit", "info", f"Audit: {s.get('pass', 0)} pass · {s.get('warn', 0)} warn · {s.get('fail', 0)} fail of {s.get('n', 0)} strategies.",
                       f"ممیزی: {s.get('pass', 0)} قبول · {s.get('warn', 0)} هشدار · {s.get('fail', 0)} رد از {s.get('n', 0)} استراتژی."))
    return out


def check_vision():
    """Phase 12: robustness of the chart-image extractor to compression/noise/scaling/phone photos"""
    import json
    p = os.path.join(DATA, "vision_robustness.json")
    if not os.path.exists(p):
        def fix():
            from core.vision import robustness_report
            robustness_report()
        return [Finding("vision", "info", "Vision robustness report not generated yet.", "گزارش مقاومت بینایی هنوز تولید نشده.", fix, ("Run", "اجرا"))]
    out = []
    pr = os.path.join(DATA, "vision_real.json")
    if os.path.exists(pr):
        rr = json.load(open(pr)); sc = [r for r in rr if r["ok"] is not None]
        out.append(Finding("vision", "info", f"real screenshots: {sum(r['ok'] for r in sc)}/{len(sc)} decoded within ±20 % (MetaTrader, TradingView, Binance app); {len(rr) - len(sc)} known-hard images tracked",
                           f"اسکرین‌شات واقعی: {sum(r['ok'] for r in sc)}/{len(sc)} با خطای ≤۲۰٪ (متاتریدر، تریدینگ‌ویو، اپ بایننس)؛ {len(rr) - len(sc)} تصویر سخت رصد می‌شود"))
    for r in json.load(open(p)):
        bad = r["dir_acc"] < 0.8 or r["count_err_pct"] > 15
        out.append(Finding("vision", "warn" if bad else "info",
                           f"chart images '{r['variant']}': candle count error {r['count_err_pct']:.0f}%, direction accuracy {r['dir_acc'] * 100:.0f}%" + (" → use a clean screenshot, not a photo" if bad else ""),
                           f"تصویر چارت «{r['variant']}»: خطای شمارش کندل {r['count_err_pct']:.0f}٪، دقت جهت {r['dir_acc'] * 100:.0f}٪" + (" ← اسکرین‌شات تمیز بدهید نه عکس" if bad else "")))
    return out


def run_checks(quick=False, progress=None):
    findings = []
    steps = [("env", check_env), ("playbook", check_playbook), ("validation", check_validation), ("forward", check_forward), ("audit", check_audit)]
    if not quick:
        steps += [("data", check_data), ("strategies", check_strategies), ("vision", check_vision)]
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
