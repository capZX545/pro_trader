"""
Behavioural risk layer — Douglas (Trading in the Zone / Disciplined Trader), Steenbarger (Psychology of Trading),
Kahneman (Thinking Fast & Slow), Taleb (Fooled by Randomness / Black Swan), Bernstein (Against the Gods),
Steve Day (Risk Management in Trading).

Two things a program CAN do about psychology:
  1. audit the trader's own journal for the classic biases (numbers, not sermons);
  2. put a pre-trade checklist + hard risk gates in front of every signal (Douglas' "5 fundamental truths" as rules).
"""
import numpy as np
import pandas as pd

CHECKLIST = [  # (id, en, fa) — Douglas + Elder's "Triple Screen discipline" + Steenbarger's "trade the plan"
    ("plan", "I know entry, stop and target BEFORE entering (no 'I'll see').", "ورود، استاپ و هدف را قبل از ورود می‌دانم (نه «بعداً می‌بینم»)."),
    ("risk", "Risk on this trade ≤ 1% of equity and total open risk ≤ 3%.", "ریسک این معامله ≤ ۱٪ سرمایه و ریسک باز کل ≤ ۳٪."),
    ("edge", "This setup has a proven edge (grade A/B in the Playbook) on THIS market & timeframe.", "این ستاپ روی همین بازار و تایم‌فریم لبهٔ اثبات‌شده دارد (نمرهٔ A/B)."),
    ("random", "I accept this single trade's outcome is random; only the series matters (Douglas truth #3).", "می‌پذیرم نتیجهٔ این یک معامله تصادفی است؛ فقط مجموعه مهم است."),
    ("revenge", "I am not trading to win back a loss or because I 'feel' it (Kahneman System-1 check).", "برای جبران ضرر یا از روی «حس» معامله نمی‌کنم."),
    ("chase", "Price is within 0.5R of the signal close — I am not chasing.", "قیمت بیش از ۰.۵R از سیگنال دور نشده — دنبال قیمت نمی‌دوم."),
    ("news", "No scheduled high-impact event in the next hold period, or I sized for it (Taleb).", "رویداد پرریسک در دورهٔ نگهداری نیست، یا برایش اندازه را کم کرده‌ام."),
    ("state", "Physically/emotionally OK: slept, not tilted, not after 3 consecutive losses (Steenbarger).", "وضعیت جسمی/روانی خوب است: خوابیده‌ام، عصبی نیستم، بعد از ۳ ضرر پیاپی نیست."),
]

HARD_GATES = dict(max_risk_per_trade=1.0, max_total_risk=3.0, max_daily_loss=3.0, max_consec_losses=3, cooldown_hours=24)


def gate(open_risk_pct, today_loss_pct, consec_losses, proposed_risk_pct, last_loss_hours_ago=None):
    """Hard rules (Steve Day / prop-firm style). Returns (allowed, reasons_en, reasons_fa)."""
    en, fa = [], []
    if proposed_risk_pct > HARD_GATES["max_risk_per_trade"]:
        en.append(f"risk {proposed_risk_pct:.2f}% > {HARD_GATES['max_risk_per_trade']}% per trade"); fa.append(f"ریسک {proposed_risk_pct:.2f}٪ > {HARD_GATES['max_risk_per_trade']}٪ در هر معامله")
    if open_risk_pct + proposed_risk_pct > HARD_GATES["max_total_risk"]:
        en.append("total open risk would exceed 3%"); fa.append("ریسک باز کل از ۳٪ بیشتر می‌شود")
    if today_loss_pct >= HARD_GATES["max_daily_loss"]:
        en.append("daily loss limit hit — stop for today"); fa.append("سقف ضرر روزانه پر شده — امروز تعطیل")
    if consec_losses >= HARD_GATES["max_consec_losses"] and (last_loss_hours_ago is None or last_loss_hours_ago < HARD_GATES["cooldown_hours"]):
        en.append(f"{consec_losses} consecutive losses — 24h cooldown (tilt protection)"); fa.append(f"{consec_losses} ضرر پیاپی — ۲۴ ساعت استراحت (محافظت از تیلت)")
    return (not en), en, fa


def audit_journal(rows):
    """rows: journal dicts with keys entry, stop, exit, side, date/time, pnl (or computed). Returns bias findings with numbers."""
    if not rows:
        return []
    df = pd.DataFrame(rows)
    out = []
    # normalise
    for k in ("entry", "stop", "exit"):
        if k in df:
            df[k] = pd.to_numeric(df[k], errors="coerce")
    side = df.get("side", pd.Series(1, index=df.index)).map(lambda s: -1 if str(s).lower() in ("short", "فروش", "-1") else 1)
    r = ((df["exit"] - df["entry"]) * side / (df["entry"] - df["stop"]).abs()).replace([np.inf, -np.inf], np.nan)
    r_valid = r.dropna()
    if len(r_valid) < 5:
        return [dict(bias="sample", en="Fewer than 5 complete trades — audit needs more data.", fa="کمتر از ۵ معاملهٔ کامل — ممیزی داده بیشتری می‌خواهد.", severity="info")]
    wins, losses = r_valid[r_valid > 0], r_valid[r_valid <= 0]
    # 1. Disposition effect (Kahneman/Shefrin): cut winners short, let losers run
    if len(wins) and len(losses) and wins.mean() < 1.0 and losses.mean() < -1.2:
        out.append(dict(bias="disposition", severity="error",
                        en=f"Disposition effect: avg win {wins.mean():.2f}R but avg loss {losses.mean():.2f}R — losers are held past the stop, winners cut early.",
                        fa=f"اثر تمایل: میانگین سود {wins.mean():.2f}R ولی میانگین ضرر {losses.mean():.2f}R — ضررها از استاپ رد می‌شوند، سودها زود بسته می‌شوند."))
    # 2. Stop violation: loss worse than −1.1R
    viol = (r_valid < -1.1).mean()
    if viol > 0.15:
        out.append(dict(bias="stop_violation", severity="error", en=f"{viol * 100:.0f}% of losses exceeded the planned stop (−1R). The stop is a decision, not a suggestion (Douglas).",
                        fa=f"{viol * 100:.0f}٪ ضررها از استاپ برنامه‌ریزی‌شده (−۱R) بیشتر شدند. استاپ تصمیم است نه پیشنهاد (داگلاس)."))
    # 3. Revenge / overtrading: trades within 1 hour after a loss
    if "date" in df or "time" in df or "ts" in df:
        tcol = next(c for c in ("ts", "date", "time") if c in df)
        try:
            ts = pd.to_datetime(df[tcol], errors="coerce")
            order = ts.sort_values().index
            rr = r.loc[order].values; tt = ts.loc[order].values
            quick_after_loss = sum(1 for i in range(1, len(rr)) if rr[i - 1] <= 0 and (tt[i] - tt[i - 1]) / np.timedelta64(1, "h") < 1)
            if quick_after_loss >= 3:
                out.append(dict(bias="revenge", severity="warn", en=f"{quick_after_loss} trades opened < 1h after a loss — revenge-trading pattern.",
                                fa=f"{quick_after_loss} معامله کمتر از ۱ ساعت بعد از ضرر باز شده — الگوی معاملهٔ انتقامی."))
        except Exception:
            pass
    # 4. Position-size drift after losses/wins (Kahneman: loss aversion → doubling)
    if "size" in df or "risk_pct" in df:
        sc = "risk_pct" if "risk_pct" in df else "size"
        sz = pd.to_numeric(df[sc], errors="coerce")
        after_loss = sz[(r.shift(1) <= 0)].mean(); after_win = sz[(r.shift(1) > 0)].mean()
        if after_loss == after_loss and after_win == after_win and after_loss > after_win * 1.3:
            out.append(dict(bias="martingale", severity="error", en=f"Size after a loss is {after_loss / after_win:.1f}× size after a win — martingale drift (ruin path).",
                            fa=f"اندازه بعد از ضرر {after_loss / after_win:.1f} برابر بعد از سود است — رانش مارتینگل (مسیر ورشکستگی)."))
    # 5. Randomness check (Taleb): is the track record distinguishable from luck?
    from core.stats import t_stat, wilson_ci
    t = t_stat(r_valid.values)
    lo, hi = wilson_ci(int((r_valid > 0).sum()), len(r_valid))
    out.append(dict(bias="luck", severity="info" if t >= 2 else "warn",
                    en=f"Edge significance t = {t:.2f} over {len(r_valid)} trades; WR 95% CI {lo * 100:.0f}–{hi * 100:.0f}%. " + ("Consistent with skill." if t >= 2 else "NOT yet distinguishable from luck (Taleb) — keep size small."),
                    fa=f"معناداری لبه t = {t:.2f} روی {len(r_valid)} معامله؛ بازهٔ WR {lo * 100:.0f}–{hi * 100:.0f}٪. " + ("با مهارت سازگار است." if t >= 2 else "هنوز از شانس قابل تفکیک نیست (طالب) — اندازه را کوچک نگه دارید.")))
    # 6. Fat tails: worst trade vs typical (Black Swan exposure)
    if len(r_valid) >= 10 and r_valid.min() < -3:
        out.append(dict(bias="tail", severity="error", en=f"Worst trade {r_valid.min():.1f}R — a tail event 3× the planned risk. Check gaps/leverage/news exposure.",
                        fa=f"بدترین معامله {r_valid.min():.1f}R — رویداد دنباله‌ای ۳ برابر ریسک برنامه. گپ/اهرم/اخبار را بررسی کنید."))
    return out


def risk_of_ruin(win_rate, payoff, risk_pct, ruin_pct=50.0, n_sims=2000, n_trades=500, seed=3):
    """Monte-Carlo ruin probability (Bernstein/Day): fixed-fractional risk, given WR & payoff."""
    rng = np.random.default_rng(seed)
    f = risk_pct / 100
    eq = np.ones(n_sims)
    ruined = np.zeros(n_sims, bool)
    for _ in range(n_trades):
        w = rng.random(n_sims) < win_rate
        eq = eq * np.where(w, 1 + f * payoff, 1 - f)
        ruined |= eq <= (1 - ruin_pct / 100)
    return float(ruined.mean())
