"""
Phase 25 — Trading Desk: the daily briefing a professional desk produces before the session.

One call → one bilingual document:
  1. Is it safe to trade now?     news window (core.calendar) + hard risk gates (core.psychology.gate) computed from the
                                  open forward-test positions (open risk, today's realised loss, losing streak)
  2. What is the market doing?    regime (trend/range/mixed × bull/bear) of one bellwether per asset class
  3. What do I already have on?   open forward-test positions with live unrealised R, MFE/MAE, bars held
  4. What is worth doing today?   fresh signals of playbook-proven strategies → Phase-24 trade plan → only GO/REDUCED
                                  survive, ranked; correlated same-direction plans halved; total risk capped (3%)
  5. What is quietly breaking?    proven strategies whose 12-month PF decayed vs history
  6. Reality check                forward-test vs backtest gap (core.forward.report)
Nothing here trades. All numbers come from the same engines as the Scanner / Signals / Forward pages.
"""
import time
import numpy as np
import pandas as pd

BELLWETHERS = {"crypto": "BTC/USDT", "stocks": "S&P 500", "commodities": "Gold (XAU/USD)", "forex": "EUR/USD"}
_CACHE = {}


def _px(sym, tf, max_age=300):
    from core.data import get_ohlcv
    df = get_ohlcv(sym, tf, max_age_sec=max_age)
    return float(df.close.iloc[-1]), df


def _naive(ts):
    t = pd.Timestamp(ts)
    return t.tz_localize(None) if t.tzinfo is not None else t


# ------------------------------------------------------------------------------------------ 1. safety
def open_positions(risk_pct_each=1.0):
    """→ (rows, open_risk_pct, today_loss_pct, consec_losses, last_loss_hours). Each forward record counts as risk_pct_each."""
    from core import forward as FW
    rows = []
    for r in FW.records("open"):
        try:
            px, _ = _px(r["symbol"], r["tf"])
        except Exception:
            continue
        rpu = abs(r["entry"] - r["stop"]) or 1e-9
        rows.append(dict(symbol=r["symbol"], tf=r["tf"], sid=r["sid"], side=r["side"], entry=r["entry"], stop=r["stop"], target=r["target"], price=px,
                         unreal_r=float((px - r["entry"]) * r["side"] / rpu), mfe_r=r.get("mfe_r", 0.0), mae_r=r.get("mae_r", 0.0), bars=r.get("bars", 0), bar=r["bar"]))
    closed = FW.records("closed")
    now = _naive(pd.Timestamp.utcnow()); today = now.normalize()
    today_loss = sum(-r["r"] * risk_pct_each for r in closed if r.get("exit_time") and (r.get("r") or 0) < 0 and _naive(r["exit_time"]) >= today)
    consec, last_h = 0, None
    for r in sorted(closed, key=lambda x: x.get("exit_time") or "", reverse=True):
        if (r.get("r") or 0) < 0:
            consec += 1
            if last_h is None and r.get("exit_time"):
                last_h = (now - _naive(r["exit_time"])).total_seconds() / 3600
        else:
            break
    open_risk = sum(risk_pct_each * max(0.0, 1.0 - max(0.0, x["unreal_r"])) for x in rows)   # ≥ +1R → risk "paid for"
    return rows, float(open_risk), float(today_loss), int(consec), last_h


# ------------------------------------------------------------------------------------------ 2. regimes
def market_regimes(tf="4h"):
    from core import edge as E
    out = {}
    for g, sym in BELLWETHERS.items():
        try:
            px, df = _px(sym, tf)
            r = E.current_regime(df)
            out[g] = dict(symbol=sym, price=px, kind=r["kind"], bias=r["bias"], chg_pct=float(df.close.iloc[-1] / df.close.iloc[-7] - 1) * 100 if len(df) > 7 else 0.0)
        except Exception:
            out[g] = dict(symbol=sym, price=None, kind="?", bias=0, chg_pct=0.0)
    return out


# ------------------------------------------------------------------------------------------ 4. candidates
def candidates(tfs=("4h", "1d"), recent=3, per_group=6, per_tf=3, equity=10_000.0, progress=None, mode="proven"):
    """Fresh signals of playbook-proven strategies → trade plan → keep GO / REDUCED. → (plans, n_rejected)"""
    import strategies as S
    from core import playbook as PB, quality as Q, edge as E
    from core.data import get_ohlcv
    pb = PB.load() or {}
    jobs = []
    for tf in tfs:
        for g, syms in PB.GROUPS.items():
            best = [sid for sid, _ in (pb.get("best", {}).get(tf, {}).get(g) or [])[:per_tf] if sid in S.REGISTRY]
            if best:
                jobs += [(tf, sym, best) for sym in syms[:per_group]]
    out, rejected = [], 0
    for j, (tf, sym, sids) in enumerate(jobs):
        if progress:
            progress(int(j / max(len(jobs), 1) * 100), f"{sym} {tf}")
        try:
            df = get_ohlcv(sym, tf, max_age_sec=300)
        except Exception:
            continue
        if len(df) < 300:
            continue
        n = len(df)
        for sid in sids:
            try:
                res = S.get(sid).run(df)
            except Exception:
                continue
            sig = res.signal.fillna(0).astype(int).values
            idx = np.where(sig[-recent:] != 0)[0]
            if len(idx) == 0:
                continue
            i = n - recent + idx[-1]
            try:
                if not Q.passes(Q.score(sid, sym, tf)["verdict"], mode):
                    continue
                p = E.trade_plan(sym, tf, sid, df=df, res=res, i=int(i), equity=equity)
            except Exception:
                continue
            if "error" in p:
                continue
            if p["verdict_en"] == "NO-TRADE":
                rejected += 1; continue
            out.append(p)
    out.sort(key=lambda p: (-(p["trust"]["score"] * max(p["size"]["risk_pct"], 0.05)), p["ago"]))
    return out, rejected


def allocate(plans, open_risk_pct, max_total=None):
    """Portfolio cap (psychology.HARD_GATES.max_total_risk) + correlated same-direction plans: leader keeps size, rest halved."""
    from core import psychology as PSY, edge as E
    cap = PSY.HARD_GATES["max_total_risk"] if max_total is None else max_total
    budget = max(0.0, cap - open_risk_pct)
    head = {}
    for c in E.cluster_risk([dict(sym=p["sym"], side=p["side"]) for p in plans], tf="1d"):
        for s in c["symbols"]:
            head[(s, c["side"])] = (c["symbols"][0], c["avg_corr"])
    seen = set()
    for p in plans:
        rp = p["size"]["risk_pct"]; p["cluster"] = None
        key = (p["sym"], p["side"])
        if key in head:
            lead, rho = head[key]; cid = (lead, p["side"])
            halved = cid in seen; seen.add(cid)
            if halved:
                rp *= 0.5
            p["cluster"] = dict(lead=lead, rho=rho, halved=halved)
        take = min(rp, budget)
        p["alloc_pct"] = round(take, 2)
        p["alloc_note"] = "ok" if take >= rp - 1e-9 else ("cap" if take <= 0 else "cut")
        budget -= take
    return plans


# ------------------------------------------------------------------------------------------ 5. decay
def decay_watch(tf="4h", top=8):
    from core import playbook as PB, edge as E
    from core.backtest import run_backtest
    from core.data import get_ohlcv
    import strategies as S
    pb = PB.load() or {}
    out = []
    for g, sym in BELLWETHERS.items():
        for sid, _ in (pb.get("best", {}).get(tf, {}).get(g) or [])[:3]:
            if sid not in S.REGISTRY:
                continue
            try:
                df = get_ohlcv(sym, tf, max_age_sec=900)
                d = E.edge_decay(run_backtest(df, S.get(sid).run(df), symbol=sym).trades)
            except Exception:
                continue
            if d["status"] in ("decayed", "improving"):
                out.append(dict(group=g, symbol=sym, tf=tf, sid=sid, **d))
    out.sort(key=lambda x: (x["status"] != "decayed", x.get("ratio") or 9))
    return out[:top]


# ------------------------------------------------------------------------------------------ briefing
def briefing(tfs=("4h", "1d"), equity=10_000.0, progress=None, max_age=600, mode="proven", recent=3):
    key = (tuple(tfs), float(equity), mode, recent)
    hit = _CACHE.get(key)
    if hit and time.time() - hit[0] < max_age:
        return hit[1]
    from core import calendar as CAL, psychology as PSY, forward as FW
    t0 = time.time()
    news = CAL.risk_now(); upcoming = CAL.upcoming(24, n=5)
    pos, open_risk, today_loss, consec, last_h = open_positions()
    ok, gen, gfa = PSY.gate(open_risk, today_loss, consec, 0.5, last_h)
    regimes = market_regimes()
    plans, rejected = candidates(tfs, recent=recent, equity=equity, progress=progress, mode=mode)
    plans = allocate(plans, open_risk)
    decay = decay_watch()
    try:
        fwd = FW.report()
    except Exception:
        fwd = {}
    b = dict(ts=time.time(), took=round(time.time() - t0, 1), news=news, upcoming=upcoming, gate=dict(ok=ok, reasons_en=gen, reasons_fa=gfa),
             open_risk_pct=open_risk, today_loss_pct=today_loss, consec_losses=consec, positions=pos, regimes=regimes, plans=plans, rejected=rejected,
             decay=decay, forward=dict(n_closed=fwd.get("n_closed", 0), verdict=fwd.get("verdict"), gap_pf=fwd.get("gap_pf"), gap_wr=fwd.get("gap_wr"), pf=(fwd.get("overall") or {}).get("pf")),
             total_alloc_pct=round(sum(p.get("alloc_pct", 0) for p in plans), 2), equity=equity, tfs=list(tfs), mode=mode)
    b["text_fa"] = render(b, "fa"); b["text_en"] = render(b, "en")
    _CACHE[key] = (time.time(), b)
    return b


def render(b, lang="en"):
    fa = lang == "fa"; ix = 0 if fa else 1
    K = {"trend": ("روند", "trend"), "range": ("رنج", "range"), "mixed": ("مختلط", "mixed"), "?": ("؟", "?")}
    B = {1: ("صعودی", "bull"), -1: ("نزولی", "bear"), 0: ("خنثی", "flat")}
    NOTE = {"ok": ("کامل", "ok"), "cap": ("سقف ریسک پرتفوی پر است", "portfolio cap reached"), "cut": ("کاهش برای سقف پرتفوی", "cut to fit cap")}
    L = [("# 🗞 بریفینگ میز معامله — " if fa else "# 🗞 Trading-desk briefing — ") + time.strftime("%Y-%m-%d %H:%M", time.localtime(b["ts"]))]
    L.append("## " + ("۱) آیا الان معامله امن است؟" if fa else "1) Is it safe to trade now?"))
    if b["news"]:
        from core import calendar as CAL
        L.append(("⛔ بازهٔ خبر پرریسک: " if fa else "⛔ High-impact news window: ") + CAL.text(b["news"], lang))
    else:
        L.append("✓ " + ("خبر پرریسکی در جریان نیست" if fa else "no high-impact news window open"))
    if b["upcoming"]:
        L.append(("رویدادهای ۲۴ ساعت آینده: " if fa else "next 24h: ") + " · ".join(f"{e.get('currency', '')} {e.get('title', '')} ({e['mins'] // 60}h{e['mins'] % 60:02d})" for e in b["upcoming"]))
    g = b["gate"]
    L.append(("✓ گیت‌های ریسک باز است" if g["ok"] else "⛔ گیت ریسک بسته: " + "؛ ".join(g["reasons_fa"])) if fa else ("✓ risk gates open" if g["ok"] else "⛔ risk gate CLOSED: " + "; ".join(g["reasons_en"])))
    L.append(f"ریسک باز {b['open_risk_pct']:.2f}٪ · ضرر امروز {b['today_loss_pct']:.2f}٪ · ضرر پیاپی {b['consec_losses']}" if fa else
             f"open risk {b['open_risk_pct']:.2f}% · today's loss {b['today_loss_pct']:.2f}% · losing streak {b['consec_losses']}")
    L.append("## " + ("۲) بازار چه می‌کند؟" if fa else "2) What is the market doing?"))
    for r in b["regimes"].values():
        L.append(f"- {r['symbol']}: {(f'{r['price']:,.6g}' if r.get('price') else '—')} ({r['chg_pct']:+.1f}%) — {K.get(r['kind'], K['?'])[ix]} / {B[r['bias']][ix]}")
    L.append("## " + (f"۳) پوزیشن‌های باز فوروارد‌تست ({len(b['positions'])})" if fa else f"3) Open forward-test positions ({len(b['positions'])})"))
    if not b["positions"]:
        L.append("- " + ("هیچ" if fa else "none"))
    for p in b["positions"][:12]:
        L.append(f"- {'▲' if p['side'] == 1 else '▼'} {p['symbol']} {p['tf']} · {p['sid']} · " + (f"شناور {p['unreal_r']:+.2f}R (بیشینه {p['mfe_r']:+.2f}R / کمینه {p['mae_r']:+.2f}R) · {p['bars']} کندل" if fa else
                                                                                                f"unrealised {p['unreal_r']:+.2f}R (MFE {p['mfe_r']:+.2f}R / MAE {p['mae_r']:+.2f}R) · {p['bars']} bars"))
    L.append("## " + (f"۴) چه چیزی ارزش انجام دارد؟ ({len(b['plans'])} برنامه، {b['rejected']} سیگنال رد شد)" if fa else f"4) What is worth doing? ({len(b['plans'])} plans, {b['rejected']} signals rejected)"))
    if not b["plans"]:
        L.append("- " + ("هیچ سیگنال اثبات‌شده‌ای از فیلترها عبور نکرد — معامله نکردن هم یک تصمیم حرفه‌ای است." if fa else "no proven signal passed the filters — not trading is also a professional decision."))
    for p in b["plans"][:10]:
        cl = ""
        if p.get("cluster"):
            c = p["cluster"]
            cl = (f" · هم‌بسته با {c['lead']} (ρ={c['rho']:.2f}{'، نصف شد' if c['halved'] else ''})" if fa else f" · correlated with {c['lead']} (ρ={c['rho']:.2f}{', halved' if c['halved'] else ''})")
        L.append(f"- **{p['verdict_fa'] if fa else p['verdict_en']}** {'▲' if p['side'] == 1 else '▼'} {p['sym']} {p['tf']} · {p['name_fa'] if fa else p['name_en']} · " +
                 (f"اعتماد {p['trust']['score']} · ورود {p['entry']:,.6g} / استاپ {p['stop']:,.6g} / هدف {p['tp2']:,.6g} (R:R {p['rr']:.1f}) · ریسک تخصیصی {p.get('alloc_pct', 0):.2f}٪ ({NOTE[p.get('alloc_note', 'ok')][0]})" if fa else
                  f"trust {p['trust']['score']} · entry {p['entry']:,.6g} / stop {p['stop']:,.6g} / target {p['tp2']:,.6g} (R:R {p['rr']:.1f}) · allocated risk {p.get('alloc_pct', 0):.2f}% ({NOTE[p.get('alloc_note', 'ok')][1]})") + cl)
        if p["avoid_en"]:
            L.append("    ⚠ " + " · ".join(p["avoid_fa"] if fa else p["avoid_en"]))
    L.append(f"جمع ریسک پیشنهادی امروز: {b['total_alloc_pct']:.2f}٪ سرمایه (سقف کل ۳٪ شامل پوزیشن‌های باز)" if fa else f"total suggested risk today: {b['total_alloc_pct']:.2f}% of equity (3% cap incl. open positions)")
    L.append("## " + ("۵) چه چیزی در سکوت خراب می‌شود؟ (فرسایش لبه)" if fa else "5) What is quietly breaking? (edge decay)"))
    if not b["decay"]:
        L.append("- " + ("فرسایش معناداری دیده نمی‌شود" if fa else "no meaningful decay"))
    for d in b["decay"]:
        L.append(f"- {d['sid']} @ {d['symbol']} {d['tf']}: " + (f"PF ۱۲ ماه {d['pf_recent']:.2f} در برابر کل {d['pf_all']:.2f} → {'فرسوده ⚠' if d['status'] == 'decayed' else 'رو به بهبود ↑'}" if fa else
                                                               f"PF 12m {d['pf_recent']:.2f} vs all {d['pf_all']:.2f} → {d['status']}{' ⚠' if d['status'] == 'decayed' else ' ↑'}"))
    f = b["forward"]
    V = {"collecting": ("در حال جمع‌آوری (کمتر از ۳۰ معاملهٔ بسته)", "collecting (<30 closed)"), "edge_confirmed": ("لبه تأیید شد ✓", "edge confirmed ✓"),
         "positive_unconfirmed": ("مثبت اما تأییدنشده", "positive, not yet confirmed"), "no_edge": ("بدون لبه ⛔", "no edge ⛔"), None: ("—", "—")}
    L.append("## " + ("۶) واقعیت در برابر بک‌تست" if fa else "6) Reality vs backtest"))
    gap = (f" · PF واقعی/انتظار {f['gap_pf']:.2f}" if fa else f" · realised/expected PF {f['gap_pf']:.2f}") if f.get("gap_pf") else ""
    L.append(f"- {f.get('n_closed', 0)} " + ("معاملهٔ بستهٔ فوروارد" if fa else "closed forward trades") + f" · {V.get(f.get('verdict'), V[None])[ix]}" + gap)
    L.append(("_تحلیل است نه دستور معامله؛ حداکثر ۱٪ ریسک در هر معامله._" if fa else "_analysis, not orders; ≤1% risk per trade._") + f"  ({b['took']}s)")
    return "\n".join(L)
