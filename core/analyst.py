"""
Offline financial "LLM" layer (Phase 11c) — what FinGPT / finance-tuned Llama, Mistral, DeepSeek, Qwen, Falcon are used
for in trading stacks, done WITHOUT any API:

  1. Structured analyst report   → `report(context, lang)`: an evidence-weighted narrative (bull/bear case, what would
                                   invalidate each, confluence score) built from the app's own numeric outputs
                                   (vision, patterns, forecast, sentiment, playbook). This is the part of FinGPT-style
                                   pipelines that actually adds value: turning many signals into one readable brief.
  2. Instruction-style Q&A       → `ask(question, context, lang)`: intent detection (trend? entry? risk? pattern? why?)
                                   answered from context; never invents numbers.
  3. Local LLM hook (optional)   → `local_llm()` uses llama-cpp-python with a GGUF placed in data/models/*.gguf
                                   (e.g. a finance-tuned Qwen/Mistral/DeepSeek). Fully offline. If absent, the rule
                                   engine above answers — same interface.

Design rule from studying FinGPT/FinBERT papers: LLM output must be *grounded* — every claim cites a number from the
context; the model is a writer, not the analyst. This module enforces that by constructing the evidence list first.
"""
import glob
import os
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_LLM = None


def _side(x):
    if isinstance(x, (int, float, np.integer, np.floating)):
        return int(np.sign(x))
    x = str(x).lower()
    return 1 if x in ("bull", "long", "bullish", "buy", "up") else (-1 if x in ("bear", "short", "bearish", "sell", "down") else 0)


# ------------------------------------------------------------------ evidence collection
def collect_evidence(ctx):
    """ctx keys (all optional): vision(understand() dict), forecast(res df), sentiment(agg), playbook(list), df(OHLCV)
    → list of dict(side=+1/-1/0, weight, text_en, text_fa, source)"""
    ev = []
    v = ctx.get("vision")
    if v:
        num = v["numeric"]
        tr = num["trend"]
        ev.append(dict(side=1 if tr == "up" else (-1 if tr == "down" else 0), weight=1.0, source="vision/trend",
                       en=f"Trend from reconstructed candles: {tr} (slope {num['slope_pct']:+.1f}% over the window)",
                       fa=f"روند از کندل‌های بازسازی‌شده: {({'up': 'صعودی', 'down': 'نزولی', 'range': 'رنج'})[tr]} (شیب {num['slope_pct']:+.1f}٪ در پنجره)"))
        for p in (num.get("chart_patterns") or [])[:4]:
            s = _side(p.get("side"))
            st = p.get("stats") or {}
            mv = st.get("move", st.get("avg_move", "?"))
            w = 0.8 if st.get("fail") is None else max(0.3, 1.0 - float(st.get("fail", 30)) / 100)
            if not p.get("confirmed", True):
                w *= 0.5
            sd = ("bullish" if s > 0 else ("bearish" if s < 0 else "neutral"), "صعودی" if s > 0 else ("نزولی" if s < 0 else "خنثی"))
            ev.append(dict(side=s, weight=w, source="pattern/numeric",
                           en=f"Chart pattern {p.get('name')} ({sd[0]}{'' if p.get('confirmed', True) else ', not yet confirmed'}); Bulkowski failure rate {st.get('fail', '?')}%, avg move {mv}%, rank {st.get('rank', '?')}",
                           fa=f"الگوی نموداری {p.get('name_fa', p.get('name'))} ({sd[1]}{'' if p.get('confirmed', True) else '، هنوز تأیید نشده'})؛ نرخ شکست بالکوفسکی {st.get('fail', '?')}٪، میانگین حرکت {mv}٪، رتبه {st.get('rank', '?')}"))
        for d in v.get("image_patterns", [])[:3]:
            s = 1 if d["side"] == "bull" else (-1 if d["side"] == "bear" else 0)
            ev.append(dict(side=s, weight=0.6 * d["conf"], source="pattern/image",
                           en=f"Learned image detector sees {d['name']} ({d['conf'] * 100:.0f}%) over bars {d['i0']}–{d['i1']}",
                           fa=f"آشکارساز تصویری {d['name_fa']} را با اطمینان {d['conf'] * 100:.0f}٪ روی کندل‌های {d['i0']}–{d['i1']} می‌بیند"))
        for ln in v.get("overlays", {}).get("lines", [])[:4]:
            if ln["kind"].startswith("trendline"):
                s = 1 if ln["kind"] == "trendline_up" else -1
                ev.append(dict(side=s, weight=0.5, source="vision/drawing",
                               en=f"A {'rising' if s > 0 else 'falling'} trend-line is drawn on the chart ({ln['angle']:+.1f}°)",
                               fa=f"خط روند {'صعودی' if s > 0 else 'نزولی'} روی نمودار کشیده شده ({ln['angle']:+.1f}°)"))
        rsi = num.get("rsi")
        if rsi == rsi and rsi is not None:
            s = -1 if rsi > 70 else (1 if rsi < 30 else 0)
            ev.append(dict(side=s, weight=0.5 if s else 0.1, source="vision/rsi", en=f"Short RSI {rsi:.0f}", fa=f"RSI کوتاه {rsi:.0f}"))
        lc = num.get("last_candle", {})
        if lc:
            if lc.get("lower_wick", 0) > 0.6:
                ev.append(dict(side=1, weight=0.4, source="candle", en="Last candle rejects lower prices (long lower wick)", fa="آخرین کندل قیمت‌های پایین را رد کرده (سایهٔ پایینی بلند)"))
            elif lc.get("upper_wick", 0) > 0.6:
                ev.append(dict(side=-1, weight=0.4, source="candle", en="Last candle rejects higher prices (long upper wick)", fa="آخرین کندل قیمت‌های بالا را رد کرده (سایهٔ بالایی بلند)"))
    fc = ctx.get("forecast")
    if fc is not None and len(fc):
        try:
            best = fc.sort_values("MASE").iloc[0]
            beat = float(best["vs_naive"]) < 0.97 and best["model"] != "naive"
            ev.append(dict(side=0, weight=0.3, source="forecast",
                           en=f"Forecast desk: best model {best['model']} MASE {best['MASE']:.2f} ({'beats' if beat else 'does NOT beat'} naive) — {'weak tilt only' if beat else 'no edge from forecasting here'}",
                           fa=f"میز پیش‌بینی: بهترین مدل {best['model']} با MASE {best['MASE']:.2f} ({'ساده را شکست می‌دهد' if beat else 'ساده را شکست نمی‌دهد'}) — {'فقط تمایل ضعیف' if beat else 'پیش‌بینی اینجا لبه‌ای ندارد'}"))
        except Exception:
            pass
    se = ctx.get("sentiment")
    if se:
        m = se.get("mean", 0.0)
        s = 1 if m > 0.1 else (-1 if m < -0.1 else 0)
        if se.get("crowded"):
            s = -s  # contrarian flag
        ev.append(dict(side=s, weight=0.5 if se.get("crowded") else 0.3, source="sentiment",
                       en=f"News sentiment {m:+.2f} ({se.get('regime')}){' — crowded/unanimous → contrarian risk' if se.get('crowded') else ''}",
                       fa=f"احساس اخبار {m:+.2f} ({se.get('regime')}){' — هم‌صدا/شلوغ → ریسک خلاف‌جهت' if se.get('crowded') else ''}"))
    pb = ctx.get("playbook")
    if pb:
        for row in pb[:3]:
            ev.append(dict(side=0, weight=0.2, source="playbook",
                           en=f"Playbook: {row.get('sid')} proven on this TF/asset (PF {row.get('pf', '?')}, {row.get('trades', '?')} trades)",
                           fa=f"پلی‌بوک: {row.get('sid')} روی این تایم‌فریم/دارایی اثبات‌شده (PF {row.get('pf', '?')}، {row.get('trades', '?')} معامله)"))
    return ev


def confluence(ev):
    if not ev:
        return 0.0, 0.0
    num = sum(e["side"] * e["weight"] for e in ev)
    den = sum(e["weight"] for e in ev if e["side"] != 0) or 1.0
    score = num / den                       # −1..+1
    agreement = abs(num) / den              # how one-sided the evidence is
    return float(score), float(agreement)


# ------------------------------------------------------------------ report writer (grounded)
def report(ctx, lang="en"):
    fa = lang == "fa"
    ev = collect_evidence(ctx)
    score, agree = confluence(ev)
    bulls = [e for e in ev if e["side"] > 0]; bears = [e for e in ev if e["side"] < 0]; neut = [e for e in ev if e["side"] == 0]
    bias = ("bullish" if score > 0.25 else ("bearish" if score < -0.25 else "neutral / no edge")) if not fa else ("صعودی" if score > 0.25 else ("نزولی" if score < -0.25 else "خنثی / بدون لبه"))
    L = []
    L.append(("### Analyst brief (offline, grounded in the app's own numbers)" if not fa else "### خلاصهٔ تحلیل‌گر (آفلاین، مبتنی بر اعداد خودِ برنامه)"))
    L.append((f"Bias: **{bias}** — confluence score {score:+.2f}, agreement {agree * 100:.0f}% across {len(ev)} pieces of evidence."
              if not fa else f"سوگیری: **{bias}** — امتیاز هم‌راستایی {score:+.2f}، توافق {agree * 100:.0f}٪ میان {len(ev)} شاهد."))
    if bulls:
        L.append(("**Bull case**" if not fa else "**سناریوی صعودی**")); L += [f"  • {e['fa' if fa else 'en']}  [{e['source']}]" for e in bulls]
    if bears:
        L.append(("**Bear case**" if not fa else "**سناریوی نزولی**")); L += [f"  • {e['fa' if fa else 'en']}  [{e['source']}]" for e in bears]
    if neut:
        L.append(("**Context**" if not fa else "**زمینه**")); L += [f"  • {e['fa' if fa else 'en']}  [{e['source']}]" for e in neut]
    # invalidation & plan (rule-based, from S/R if available)
    v = ctx.get("vision")
    if v:
        num = v["numeric"]; sup = num.get("support") or []; res = num.get("resistance") or []
        last = float(v["df"]["close"].iloc[-1]) if len(v["df"]) else None
        cal = v.get("calibration") is not None or ctx.get("calibrated")
        unit = "" if cal else (" (relative px units)" if not fa else " (واحد نسبی پیکسل)")
        if last is not None and (sup or res):
            L.append(("**Levels & invalidation**" if not fa else "**سطوح و ابطال**"))
            if res:
                L.append((f"  • Nearest resistance {res[0][0]:,.2f} (touched {res[0][1]}×){unit}; a bearish view is invalidated on a close above it."
                          if not fa else f"  • نزدیک‌ترین مقاومت {res[0][0]:,.2f} ({res[0][1]} برخورد){unit}؛ نگاه نزولی با بستهٔ بالای آن باطل می‌شود."))
            if sup:
                L.append((f"  • Nearest support {sup[0][0]:,.2f} (touched {sup[0][1]}×){unit}; a bullish view is invalidated on a close below it."
                          if not fa else f"  • نزدیک‌ترین حمایت {sup[0][0]:,.2f} ({sup[0][1]} برخورد){unit}؛ نگاه صعودی با بستهٔ زیر آن باطل می‌شود."))
            if sup and res and res[0][0] > last > sup[0][0]:
                rr_l = (res[0][0] - last) / max(last - sup[0][0], 1e-9)
                L.append((f"  • Long from here to resistance with stop under support → R:R ≈ {rr_l:.2f}; shorts mirror it at ≈ {1 / max(rr_l, 1e-9):.2f}. Below 1.5 the setup is not worth taking (Elder / Tharp)."
                          if not fa else f"  • خرید از اینجا تا مقاومت با استاپ زیر حمایت → R:R ≈ {rr_l:.2f}؛ فروش برعکس ≈ {1 / max(rr_l, 1e-9):.2f}. زیر ۱٫۵ ارزش گرفتن ندارد (الدر / تارپ)."))
            elif sup and res:
                where = ("above the resistance cluster (breakout — wait for a retest)" if last >= res[0][0] else "below the support cluster (breakdown — wait for a retest)")
                where_fa = ("بالای خوشهٔ مقاومت (شکست — منتظر پولبک بمانید)" if last >= res[0][0] else "زیر خوشهٔ حمایت (شکست نزولی — منتظر پولبک بمانید)")
                L.append((f"  • Price is currently {where}." if not fa else f"  • قیمت اکنون {where_fa} است."))
    L.append(("**Discipline**: this is analysis, not a signal. Size by the Risk page (≤1–2% per trade), wait for confirmation (close beyond level + volume), and log the trade in the Journal."
              if not fa else "**انضباط**: این تحلیل است نه سیگنال. اندازهٔ پوزیشن را از صفحهٔ ریسک بگیرید (≤۱–۲٪ هر معامله)، منتظر تأیید بمانید (بسته فراتر از سطح + حجم) و معامله را در ژورنال ثبت کنید."))
    return "\n".join(L), dict(score=score, agreement=agree, n=len(ev), bias=bias)


# ------------------------------------------------------------------ Q&A
INTENTS = {
    "trend": ["trend", "direction", "روند", "جهت", "صعودی", "نزولی"],
    "entry": ["entry", "buy", "sell", "enter", "ورود", "بخرم", "بفروشم", "خرید", "فروش"],
    "risk": ["stop", "risk", "size", "استاپ", "ریسک", "حجم معامله", "اندازه"],
    "pattern": ["pattern", "الگو", "head", "triangle", "wedge", "flag", "سر و شانه", "مثلث"],
    "level": ["support", "resistance", "level", "حمایت", "مقاومت", "سطح"],
    "why": ["why", "چرا", "دلیل"],
    "news": ["news", "sentiment", "خبر", "احساس"],
}


def ask(question, ctx, lang="en"):
    fa = lang == "fa"
    q = question.lower()
    intent = next((k for k, ws in INTENTS.items() if any(w in q for w in ws)), "summary")
    ev = collect_evidence(ctx)
    score, agree = confluence(ev)
    v = ctx.get("vision"); num = v["numeric"] if v else {}
    llm = local_llm()
    if llm is not None:
        prompt = _ground_prompt(question, ev, num, lang)
        try:
            return llm(prompt), "local-llm"
        except Exception:
            pass
    if intent == "trend":
        tr = num.get("trend", "unknown")
        return ((f"Trend: {tr}; slope {num.get('slope_pct', 0):+.1f}%. Confluence {score:+.2f}." if not fa else
                 f"روند: {({'up': 'صعودی', 'down': 'نزولی', 'range': 'رنج'}).get(tr, tr)}؛ شیب {num.get('slope_pct', 0):+.1f}٪. هم‌راستایی {score:+.2f}."), "rules")
    if intent == "entry":
        txt, meta = report(ctx, lang)
        pre = ("I do not give buy/sell orders. Here is the grounded brief; decide with your plan:\n\n" if not fa else "من دستور خرید/فروش نمی‌دهم. این خلاصهٔ مستند است؛ با برنامهٔ خودتان تصمیم بگیرید:\n\n")
        return pre + txt, "rules"
    if intent == "risk":
        sup = num.get("support") or []; res = num.get("resistance") or []
        s = (f"Put stops beyond the nearest structure: support {sup[0][0]:,.2f} / resistance {res[0][0]:,.2f}. Risk ≤1–2% of equity; size = risk$ / |entry − stop|. Use the Risk page calculator."
             if (sup and res and not fa) else (f"استاپ را فراتر از نزدیک‌ترین ساختار بگذارید: حمایت {sup[0][0]:,.2f} / مقاومت {res[0][0]:,.2f}. ریسک ≤۱–۲٪ سرمایه؛ اندازه = ریسک$ ÷ |ورود − استاپ|. از ماشین‌حساب صفحهٔ ریسک استفاده کنید." if (sup and res) else
                   ("Not enough structure detected to place a stop objectively." if not fa else "ساختار کافی برای تعیین عینی استاپ پیدا نشد.")))
        return s, "rules"
    if intent == "pattern":
        lines = [e["fa" if fa else "en"] for e in ev if e["source"].startswith("pattern")]
        return ("\n".join("• " + x for x in lines) if lines else ("No pattern with enough quality detected." if not fa else "الگوی باکیفیتی شناسایی نشد.")), "rules"
    if intent == "level":
        sup = num.get("support") or []; res = num.get("resistance") or []
        return ((("Resistance: " if not fa else "مقاومت: ") + ", ".join(f"{a:,.2f}×{b}" for a, b in res) + "\n" + ("Support: " if not fa else "حمایت: ") + ", ".join(f"{a:,.2f}×{b}" for a, b in sup)), "rules")
    if intent == "news":
        se = ctx.get("sentiment")
        return ((f"Sentiment {se['mean']:+.2f}, regime {se['regime']}, crowded={se['crowded']}" if se else ("No headlines scored yet — use AI Desk ▸ Sentiment." if not fa else "هنوز تیتری امتیازدهی نشده — میز هوش مصنوعی ▸ احساسات.")), "rules")
    txt, meta = report(ctx, lang)
    return txt, "rules"


def _ground_prompt(question, ev, num, lang):
    facts = "\n".join(f"- {e['fa' if lang == 'fa' else 'en']}" for e in ev)
    return (f"You are a cautious financial analyst. Answer ONLY from the facts below; if a fact is missing say so. Never give buy/sell orders.\n"
            f"Language: {'Persian' if lang == 'fa' else 'English'}.\nFACTS:\n{facts}\n\nQUESTION: {question}\nANSWER:")


# ------------------------------------------------------------------ optional local LLM (GGUF via llama-cpp-python)
def local_llm(max_tokens=400):
    global _LLM
    if _LLM is not None:
        return _LLM or None
    try:
        from llama_cpp import Llama
    except Exception:
        _LLM = False; return None
    ggufs = sorted(glob.glob(os.path.join(ROOT, "data", "models", "*.gguf")))
    if not ggufs:
        _LLM = False; return None
    try:
        m = Llama(model_path=ggufs[0], n_ctx=4096, verbose=False)
        def run(prompt):
            out = m(prompt, max_tokens=max_tokens, temperature=0.2, stop=["QUESTION:", "FACTS:"])
            return out["choices"][0]["text"].strip()
        _LLM = run
        return run
    except Exception:
        _LLM = False; return None


def llm_status():
    ggufs = glob.glob(os.path.join(ROOT, "data", "models", "*.gguf"))
    try:
        import llama_cpp  # noqa
        has = True
    except Exception:
        has = False
    return dict(llama_cpp=has, gguf=[os.path.basename(g) for g in ggufs], active=local_llm() is not None)
