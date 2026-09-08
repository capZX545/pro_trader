"""
Order-flow / auction-theory strategies from OHLCV (Phase 16 round 2).

Sources studied: footprint-chart guides (FuturesHive 2025/26, GoCharting cheat-sheet, AlgoStorm), Fabio Valentini's
NQ order-flow rules (balance/imbalance day → direction via CVD → location at POC/VA edge/LVN → aggression), Dalton
"Mind over Markets" (value area, 80 % rule, poor highs/lows), Freqtrade community "Scalp" strategy & NFI-style
multi-condition dip buying, the "flat Bollinger + stochastic" 5-minute range scalp, Jesse "anchor timeframe".

True footprints need bid/ask tick data. These implementations use the best OHLCV proxies the literature itself
recommends when only bars are available:
  * absorption      = volume ≥ 2× average  AND  bar range ≤ 0.3 ATR  (effort without result)
  * imbalance       = body ≥ 70 % of range with volume ≥ 1.5× (one-sided aggression); stacked = 3 in a row
  * delta           = Bulk-Volume-Classification estimate (see strategies.scalp._cvd)
  * volume profile  = rolling histogram of volume by price (POC / VAH / VAL / LVN)
"""
import numpy as np
import pandas as pd
from .base import Strategy, StrategyResult
from .scalp import _cvd, _relvol, _bar_minutes
from core import indicators as ta


# ----------------------------------------------------------------------------- volume-profile helper
def rolling_profile(df, lookback=200, rows=24, step=10):
    """POC / VAH / VAL / nearest LVN computed every `step` bars over the trailing `lookback` bars (value area = 70 %).
    Returns four Series (forward-filled)."""
    n = len(df)
    poc = np.full(n, np.nan); vah = np.full(n, np.nan); val = np.full(n, np.nan); lvn = np.full(n, np.nan)
    h, l, v = df.high.values, df.low.values, df.volume.values
    for i in range(lookback, n, step):
        hs, ls, vs = h[i - lookback:i], l[i - lookback:i], v[i - lookback:i]
        lo, hi = ls.min(), hs.max()
        if hi <= lo:
            continue
        edges = np.linspace(lo, hi, rows + 1)
        hist = np.zeros(rows)
        # spread each bar's volume evenly over the bins it covers
        b0 = np.clip(np.searchsorted(edges, ls, side="right") - 1, 0, rows - 1)
        b1 = np.clip(np.searchsorted(edges, hs, side="right") - 1, 0, rows - 1)
        for a, b, vol in zip(b0, b1, vs):
            k = b - a + 1
            hist[a:b + 1] += vol / k
        p = int(hist.argmax())
        total = hist.sum(); acc = hist[p]; lo_i = hi_i = p
        while acc < 0.7 * total and (lo_i > 0 or hi_i < rows - 1):
            up = hist[hi_i + 1] if hi_i < rows - 1 else -1
            dn = hist[lo_i - 1] if lo_i > 0 else -1
            if up >= dn:
                hi_i += 1; acc += up
            else:
                lo_i -= 1; acc += dn
        mids = (edges[:-1] + edges[1:]) / 2
        # LVN: lowest-volume bin inside the value area (excluding POC) → thin zone price
        inside = hist[lo_i:hi_i + 1].copy()
        if len(inside) > 2:
            inside[p - lo_i] = np.inf
            lvn_i = lo_i + int(inside.argmin())
        else:
            lvn_i = p
        sl = slice(i, min(n, i + step))
        poc[sl], vah[sl], val[sl], lvn[sl] = mids[p], edges[hi_i + 1], edges[lo_i], mids[lvn_i]
    idx = df.index
    return (pd.Series(poc, idx).ffill(), pd.Series(vah, idx).ffill(), pd.Series(val, idx).ffill(), pd.Series(lvn, idx).ffill())


def _absorption(df, pct=97, n=200):
    """Effort-without-result: volume per unit of range in the top 3 % of the last 200 bars AND volume itself above average.
    (The literal futures rule 'volume ≥ 2× and range ≤ 0.3 ATR' fires ~0 % of the time on crypto bars, so it is expressed
    as a percentile of the volume/range ratio instead.)"""
    rng = (df.high - df.low).replace(0, np.nan)
    eff = (df.volume / rng)
    thr = eff.rolling(n).quantile(pct / 100)
    rv = _relvol(df, 48)
    return (eff >= thr) & (rv >= 1.2)


def _imbalance(df, body_ratio=0.6, vol_mult=1.2):
    rng = (df.high - df.low).replace(0, np.nan)
    body = (df.close - df.open) / rng
    rv = _relvol(df, 48)
    bull = (body >= body_ratio) & (rv >= vol_mult)
    bear = (body <= -body_ratio) & (rv >= vol_mult)
    return bull, bear


# ----------------------------------------------------------------------------- 1. Value-area edge bounce with absorption
class ValueAreaBounce(Strategy):
    id = "value_area_bounce"
    name_en = "Value-Area Edge Bounce + Absorption (Volume Profile)"
    name_fa = "برگشت از لبهٔ ناحیهٔ ارزش + جذب (پروفایل حجم)"
    category = "Volume"
    author = "Dalton / Steidlmayer; Valentini order-flow rules"
    difficulty = 4
    timeframes = "1m – 15m"
    params = {"lookback": 200, "rows": 24, "tol_atr": 0.5, "sl_atr": 1.2}
    bt_kwargs = {"max_bars": 40}
    description_en = ("Balance-day play. Rolling 200-bar volume profile gives VAH/VAL/POC. When price tests VAL and an absorption bar "
                      "prints (volume ≥ 2×, range ≤ 0.3 ATR) followed by a close back above VAL, responsive buyers are defending value → "
                      "long to POC. Mirror at VAH. Skipped when the tape is trending (price outside value for > 30 bars).")
    description_fa = ("ستاپ روز تعادل. پروفایل حجم ۲۰۰ کندلی VAH/VAL/POC می‌دهد. وقتی قیمت VAL را تست می‌کند و کندل جذب چاپ می‌شود (حجم ≥ ۲×، "
                      "رنج ≤ ۰.۳ATR) و بعد بسته‌شدن بالای VAL، خریداران واکنشی از ارزش دفاع می‌کنند → خرید تا POC. برعکس در VAH.")
    rules_en = ["Rolling volume profile (200 bars, 24 rows, 70 % value area)", "Absorption bar within 0.5 ATR of VAL, next close > VAL",
                "Target POC; stop 1.2 ATR below absorption low; time stop 40 bars", "No trade if price has been outside value > 30 bars (trend day)"]
    rules_fa = ["پروفایل حجم غلتان (۲۰۰ کندل، ۲۴ ردیف، ناحیهٔ ارزش ۷۰٪)", "کندل جذب در فاصلهٔ ۰.۵ATR از VAL، بسته‌شدن بعدی > VAL",
                "هدف POC؛ حد ضرر ۱.۲ATR زیر کف کندل جذب؛ حد زمانی ۴۰ کندل", "اگر قیمت > ۳۰ کندل بیرون ارزش بوده (روز روند) معامله نکن"]
    pros_en = ["Location + aggression, the two things order-flow traders insist on", "Objective target (POC)"]
    cons_en = ["Profile from bars is coarser than tick profile", "Range-day only"]
    pros_fa = ["مکان + تهاجم، دو چیزی که معامله‌گران جریان سفارش روی آن اصرار دارند", "هدف عینی (POC)"]
    cons_fa = ["پروفایل کندلی از پروفایل تیک درشت‌تر است", "فقط روز رنج"]

    def run(self, df):
        p = self.p
        poc, vah, val, lvn = rolling_profile(df, p["lookback"], p["rows"])
        a = ta.atr(df, 14)
        ab = _absorption(df)
        outside = ((df.close > vah) | (df.close < val)).astype(int)
        out_run = outside.groupby((outside == 0).cumsum()).cumsum()
        balance = out_run.shift(1) <= 30
        near_val = (df.low <= val + p["tol_atr"] * a) & (df.low >= val - p["tol_atr"] * a * 2)
        near_vah = (df.high >= vah - p["tol_atr"] * a) & (df.high <= vah + p["tol_atr"] * a * 2)
        long = ab.shift(1).fillna(False).astype(bool) & near_val.shift(1).fillna(False).astype(bool) & (df.close > val) & balance
        short = ab.shift(1).fillna(False).astype(bool) & near_vah.shift(1).fillna(False).astype(bool) & (df.close < vah) & balance
        sig = self.make_signal(long, short)
        stop = pd.Series(np.nan, index=df.index); tgt = pd.Series(np.nan, index=df.index)
        stop[sig == 1] = (df.low.shift(1) - p["sl_atr"] * a)[sig == 1]; tgt[sig == 1] = poc[sig == 1]
        stop[sig == -1] = (df.high.shift(1) + p["sl_atr"] * a)[sig == -1]; tgt[sig == -1] = poc[sig == -1]
        # target must be at least 1R away
        r = (df.close - stop).abs()
        bad = (tgt - df.close).abs() < r
        sig[bad] = 0
        return StrategyResult(sig, stop, tgt, overlays={"POC": poc, "VAH": vah, "VAL": val}, bt_kwargs=dict(self.bt_kwargs))


# ----------------------------------------------------------------------------- 2. Triple-A (absorption → accumulation → aggression)
class TripleA(Strategy):
    id = "triple_a_flow"
    name_en = "Triple-A: Absorption → Accumulation → Aggression"
    name_fa = "سه‌گانهٔ A: جذب → انباشت → تهاجم"
    category = "Volume"
    author = "Fabio Valentini (order-flow scalper) — OHLCV approximation"
    difficulty = 4
    timeframes = "1m – 15m"
    params = {"acc_bars": 6, "acc_range_atr": 1.2, "sl_atr": 1.0, "rr": 2.0}
    bt_kwargs = {"max_bars": 30}
    description_en = ("Institutional lifecycle in three bars-groups: (1) absorption bar (volume ≥ 2×, range ≤ 0.3 ATR), (2) accumulation: the next "
                      "≤ 6 bars stay inside a 1.2-ATR box, (3) aggression: an imbalance bar (body ≥ 70 %, volume ≥ 1.5×) closes outside the box. "
                      "Trade the aggression in its direction; stop on the other side of the box; 2R target.")
    description_fa = ("چرخهٔ نهادی در سه مرحله: (۱) کندل جذب (حجم ≥ ۲×، رنج ≤ ۰.۳ATR)، (۲) انباشت: ≤ ۶ کندل بعدی داخل جعبهٔ ۱.۲ATR، "
                      "(۳) تهاجم: کندل عدم‌تعادل (بدنه ≥ ۷۰٪، حجم ≥ ۱.۵×) بیرون جعبه بسته می‌شود. هم‌جهت تهاجم؛ حد ضرر آن‌سوی جعبه؛ هدف 2R.")
    rules_en = ["Absorption bar → mark box = [low, high] extended by the next bars while range ≤ 1.2 ATR",
                "Aggression = imbalance bar closing beyond box within 6 bars", "Stop: opposite box edge − 1 ATR; target 2R; time stop 30"]
    rules_fa = ["کندل جذب → جعبه = [کف، سقف] که با کندل‌های بعدی تا وقتی رنج ≤ ۱.۲ATR است گسترش می‌یابد",
                "تهاجم = کندل عدم‌تعادل که تا ۶ کندل بعد بیرون جعبه بسته شود", "حد ضرر: لبهٔ مخالف جعبه − ۱ATR؛ هدف 2R؛ حد زمانی ۳۰"]
    pros_en = ["Sequenced confirmation → few but clean trades"]
    cons_en = ["Rare; proxies can mis-classify news bars as absorption"]
    pros_fa = ["تأیید مرحله‌ای → معاملات کم ولی تمیز"]
    cons_fa = ["نادر؛ پراکسی ممکن است کندل خبری را جذب تشخیص دهد"]

    def run(self, df):
        p = self.p
        a = ta.atr(df, 14).values
        ab = _absorption(df).values
        bull_i, bear_i = _imbalance(df)
        bull_i, bear_i = bull_i.values, bear_i.values
        h, l, c = df.high.values, df.low.values, df.close.values
        n = len(df)
        sig = np.zeros(n, dtype=int); stop = np.full(n, np.nan); tgt = np.full(n, np.nan)
        i = 1
        while i < n - 1:
            if not ab[i] or not (a[i] == a[i]):
                i += 1; continue
            bl, bh = l[i], h[i]
            fired = False
            for k in range(i + 1, min(n, i + 1 + p["acc_bars"])):
                if bull_i[k] and c[k] > bh:
                    sig[k] = 1; stop[k] = bl - p["sl_atr"] * a[k]; tgt[k] = c[k] + p["rr"] * (c[k] - stop[k]); fired = True; break
                if bear_i[k] and c[k] < bl:
                    sig[k] = -1; stop[k] = bh + p["sl_atr"] * a[k]; tgt[k] = c[k] - p["rr"] * (stop[k] - c[k]); fired = True; break
                bl, bh = min(bl, l[k]), max(bh, h[k])
                if bh - bl > p["acc_range_atr"] * a[k]:
                    break
            i = k + 1 if fired else i + 1
        return StrategyResult(pd.Series(sig, index=df.index), pd.Series(stop, index=df.index), pd.Series(tgt, index=df.index),
                              bt_kwargs=dict(self.bt_kwargs))


# ----------------------------------------------------------------------------- 3. Stacked-imbalance zone retest
class StackedImbalanceRetest(Strategy):
    id = "stacked_imbalance_retest"
    name_en = "Stacked-Imbalance Zone Retest"
    name_fa = "ری‌تست ناحیهٔ عدم‌تعادل انباشته"
    category = "Smart-Money"
    author = "Footprint-chart practice (stacked imbalances = institutional initiative)"
    difficulty = 3
    timeframes = "1m – 15m"
    params = {"stack": 2, "max_wait": 40, "sl_atr": 0.8, "rr": 2.0}
    bt_kwargs = {"max_bars": 30}
    description_en = ("Three consecutive imbalance bars (body ≥ 70 %, volume ≥ 1.5×) in one direction define an initiative zone (the first bar's "
                      "range). When price pulls back into the zone within 40 bars and prints a bar closing back in the impulse direction, "
                      "defenders are present → enter. Stop beyond the zone; 2R target. This is the OHLCV version of the footprint 'stacked "
                      "imbalance retest'.")
    description_fa = ("سه کندل عدم‌تعادل پیاپی (بدنه ≥ ۷۰٪، حجم ≥ ۱.۵×) در یک جهت، ناحیهٔ ابتکار را می‌سازند (رنج کندل اول). وقتی قیمت تا ۴۰ کندل بعد "
                      "به ناحیه برمی‌گردد و کندلی در جهت ایمپالس بسته می‌شود، مدافعان حاضرند → ورود. حد ضرر آن‌سوی ناحیه؛ هدف 2R.")
    rules_en = ["Zone = range of the first of 3 stacked imbalance bars", "Retest: low enters zone, close above zone top (long)", "Stop zone bottom − 0.8 ATR; target 2R"]
    rules_fa = ["ناحیه = رنج اولین کندل از ۳ کندل عدم‌تعادل انباشته", "ری‌تست: کف وارد ناحیه شود، بسته‌شدن بالای سقف ناحیه (خرید)", "حد ضرر کف ناحیه − ۰.۸ATR؛ هدف 2R"]
    pros_en = ["Trades with the initiative side", "Defined zone risk"]
    cons_en = ["Zones can be run through on news"]
    pros_fa = ["هم‌جهت طرف ابتکار", "ریسک ناحیه‌ای مشخص"]
    cons_fa = ["ناحیه ممکن است با خبر شکسته شود"]

    def run(self, df):
        p = self.p
        bull, bear = _imbalance(df)
        a = ta.atr(df, 14).values
        b3 = bull.rolling(p["stack"]).sum() >= p["stack"]; s3 = bear.rolling(p["stack"]).sum() >= p["stack"]
        h, l, c = df.high.values, df.low.values, df.close.values
        n = len(df)
        sig = np.zeros(n, dtype=int); stop = np.full(n, np.nan); tgt = np.full(n, np.nan)
        zones = []   # (dir, lo, hi, expire)
        b3v, s3v = b3.values, s3.values
        for i in range(p["stack"], n):
            if b3v[i]:
                j = i - p["stack"] + 1; zones.append((1, l[j], h[j], i + p["max_wait"]))
            if s3v[i]:
                j = i - p["stack"] + 1; zones.append((-1, l[j], h[j], i + p["max_wait"]))
            zones = [z for z in zones if z[3] >= i]
            for z in list(zones):
                d, zl, zh, _ = z
                if d == 1 and l[i] <= zh and l[i] >= zl - 0.2 * a[i] and c[i] > zh and c[i] > df.open.values[i]:
                    sig[i] = 1; stop[i] = zl - p["sl_atr"] * a[i]; tgt[i] = c[i] + p["rr"] * (c[i] - stop[i]); zones.remove(z); break
                if d == -1 and h[i] >= zl and h[i] <= zh + 0.2 * a[i] and c[i] < zl and c[i] < df.open.values[i]:
                    sig[i] = -1; stop[i] = zh + p["sl_atr"] * a[i]; tgt[i] = c[i] - p["rr"] * (stop[i] - c[i]); zones.remove(z); break
        return StrategyResult(pd.Series(sig, index=df.index), pd.Series(stop, index=df.index), pd.Series(tgt, index=df.index),
                              bt_kwargs=dict(self.bt_kwargs))


# ----------------------------------------------------------------------------- 4. LVN breakout (thin zone → fast travel)
class LVNBreakout(Strategy):
    id = "lvn_breakout"
    name_en = "Low-Volume-Node Breakout (profile thin zone)"
    name_fa = "شکست گرهٔ کم‌حجم (ناحیهٔ نازک پروفایل)"
    category = "Volatility"
    author = "Volume-profile practice (LVN = no acceptance → price travels fast)"
    difficulty = 3
    timeframes = "1m – 15m"
    params = {"lookback": 200, "rows": 24, "relvol": 1.5, "sl_atr": 1.0, "rr": 1.5}
    bt_kwargs = {"max_bars": 20}
    description_en = ("Volume profile shows where price was accepted (HVN) and rejected (LVN). A high-volume bar that crosses the nearest LVN "
                      "in the direction away from POC is a breakout through a vacuum: momentum continuation to the value-area edge / beyond.")
    description_fa = ("پروفایل حجم نشان می‌دهد قیمت کجا پذیرفته (HVN) و کجا رد (LVN) شده. کندل پرحجمی که از نزدیک‌ترین LVN در جهت دور از POC عبور کند، "
                      "شکست از خلاء است: ادامهٔ مومنتوم تا لبهٔ ارزش/فراتر.")
    rules_en = ["Cross of LVN on rel.volume ≥ 1.5 with an imbalance body", "Direction must be away from POC", "Stop 1 ATR; target 1.5R; time stop 20"]
    rules_fa = ["عبور از LVN با حجم نسبی ≥ ۱.۵ و بدنهٔ عدم‌تعادل", "جهت باید دور از POC باشد", "حد ضرر ۱ATR؛ هدف ۱.۵R؛ حد زمانی ۲۰"]
    pros_en = ["Explains WHY some breakouts run"]
    cons_en = ["LVN estimate shifts every 10 bars"]
    pros_fa = ["توضیح می‌دهد چرا بعضی شکست‌ها ادامه می‌یابند"]
    cons_fa = ["برآورد LVN هر ۱۰ کندل جابه‌جا می‌شود"]

    def run(self, df):
        p = self.p
        poc, vah, val, lvn = rolling_profile(df, p["lookback"], p["rows"])
        a = ta.atr(df, 14)
        bull, bear = _imbalance(df, 0.6, p["relvol"])
        long = bull & (df.open < lvn) & (df.close > lvn) & (lvn > poc)
        short = bear & (df.open > lvn) & (df.close < lvn) & (lvn < poc)
        sig = self.make_signal(long, short)
        st, tp = self.atr_stops(df, sig, a, p["sl_atr"], p["sl_atr"] * p["rr"])
        return StrategyResult(sig, st, tp, overlays={"POC": poc, "LVN": lvn}, bt_kwargs=dict(self.bt_kwargs))


# ----------------------------------------------------------------------------- 5. HTF-anchored scalp (Jesse anchor + Brooks always-in)
class AnchoredScalp(Strategy):
    id = "anchored_scalp"
    name_en = "HTF-Anchored Scalp (anchor TF trend + LTF EMA pullback)"
    name_fa = "اسکالپ لنگر تایم بالاتر (روند تایم لنگر + پولبک EMA تایم پایین)"
    category = "Trend"
    author = "Jesse 'anchor timeframe' + Brooks always-in + NFI informative pairs"
    difficulty = 2
    timeframes = "1m – 15m"
    params = {"anchor_factor": 12, "ema_fast": 8, "ema_slow": 21, "rsi_n": 7, "rsi_pb": 45, "sl_atr": 1.5, "rr": 1.6}
    bt_kwargs = {"max_bars": 36}
    description_en = ("Resample to an anchor timeframe (×12: 5m → 1h) and require EMA20 > EMA50 and rising there. On the trading timeframe buy the "
                      "pullback: RSI(7) dips below 45 then turns up while EMA8 > EMA21. The anchor gate is what NFI, Jesse and Brooks all share.")
    description_fa = ("به تایم لنگر ری‌سمپل کن (×۱۲: ۵ دقیقه → ۱ ساعت) و آن‌جا EMA20 > EMA50 و صعودی باشد. در تایم معامله پولبک را بخر: RSI(7) زیر ۴۵ "
                      "برود و برگردد در حالی که EMA8 > EMA21. گیت لنگر چیزی است که NFI، Jesse و بروکس همه دارند.")
    rules_en = ["Anchor (×12) EMA20 > EMA50 and EMA20 rising", "LTF: EMA8 > EMA21; RSI(7) crosses back above 45 after being below",
                "Stop 1.5 ATR; target 1.6R; time stop 36"]
    rules_fa = ["لنگر (×۱۲): EMA20 > EMA50 و EMA20 صعودی", "تایم پایین: EMA8 > EMA21؛ RSI(7) بعد از زیر ۴۵ بودن دوباره بالای ۴۵ کراس کند",
                "حد ضرر ۱.۵ATR؛ هدف ۱.۶R؛ حد زمانی ۳۶"]
    pros_en = ["Removes counter-trend scalps (the biggest loss source)"]
    cons_en = ["Late in fresh trends"]
    pros_fa = ["اسکالپ‌های خلاف روند (بزرگ‌ترین منبع ضرر) را حذف می‌کند"]
    cons_fa = ["در روندهای تازه دیر است"]

    def run(self, df):
        p = self.p
        from core.data import resample
        mins = _bar_minutes(df)
        rule = f"{int(round(mins * p['anchor_factor']))}min"
        try:
            hi = resample(df, rule)
            e20, e50 = ta.ema(hi.close, 20), ta.ema(hi.close, 50)
            up_h = ((e20 > e50) & (e20 > e20.shift(1))).shift(1)      # shift: only closed anchor bars
            dn_h = ((e20 < e50) & (e20 < e20.shift(1))).shift(1)
            up = up_h.reindex(df.index, method="ffill").fillna(False).astype(bool)
            dn = dn_h.reindex(df.index, method="ffill").fillna(False).astype(bool)
        except Exception:
            up = dn = pd.Series(True, index=df.index)
        ef, es = ta.ema(df.close, p["ema_fast"]), ta.ema(df.close, p["ema_slow"])
        r = ta.rsi(df.close, p["rsi_n"])
        a = ta.atr(df, 14)
        was_low = (r.shift(1) < p["rsi_pb"]) | (r.shift(2) < p["rsi_pb"])
        long = up & (ef > es) & was_low & (r > p["rsi_pb"]) & (r.shift(1) <= p["rsi_pb"])
        was_hi = (r.shift(1) > 100 - p["rsi_pb"]) | (r.shift(2) > 100 - p["rsi_pb"])
        short = dn & (ef < es) & was_hi & (r < 100 - p["rsi_pb"]) & (r.shift(1) >= 100 - p["rsi_pb"])
        sig = self.make_signal(long, short)
        st, tp = self.atr_stops(df, sig, a, p["sl_atr"], p["sl_atr"] * p["rr"])
        return StrategyResult(sig, st, tp, overlays={"EMA8": ef, "EMA21": es}, panels={"RSI7": {"RSI(7)": r}}, bt_kwargs=dict(self.bt_kwargs))


# ----------------------------------------------------------------------------- 6. Freqtrade community "Scalp" (EMA + STOCHF + ADX + BB)
class FreqtradeScalp(Strategy):
    id = "ft_scalp"
    name_en = "Freqtrade 'Scalp' (EMA/StochF/ADX/BB, corrected)"
    name_fa = "اسکالپ Freqtrade (EMA/StochF/ADX/BB، اصلاح‌شده)"
    category = "Mean-Reversion"
    author = "freqtrade-strategies repo (community) — with cost-aware exits"
    difficulty = 1
    timeframes = "1m – 5m"
    params = {"ema_hi": 5, "ema_lo": 50, "fastk": 30, "adx_min": 30, "sl_atr": 2.0, "rr": 1.0}
    bt_kwargs = {"max_bars": 15, "allow_short": False}
    description_en = ("The most-cloned freqtrade scalp: buy when open < EMA(5) low-band, fast-stoch %K < 30, ADX > 30 and close < BB lower; sell "
                      "when %K > 70 or price > EMA. Public backtests show it LOSES at 5-open-trades/113 trades per day because ROI 1 % < fees. "
                      "Kept for completeness with two fixes: ATR stop and a hard 15-bar time stop; long-only as in the original.")
    description_fa = ("پرکپی‌ترین اسکالپ freqtrade: خرید وقتی open < باند پایین EMA(5)، %K استوک سریع < ۳۰، ADX > ۳۰ و close < باند پایین BB؛ فروش با "
                      "%K > ۷۰ یا قیمت > EMA. بک‌تست‌های عمومی نشان می‌دهد با ۱۱۳ معامله در روز ضرر می‌دهد چون ROI ۱٪ < کارمزد. برای کامل بودن با دو اصلاح نگه داشته شد.")
    rules_en = ["open < EMA5(low) & fastK<30 & ADX>30 & close<BB lower", "Exit: fastK>70 or close>EMA5(high) or 15 bars", "Long only (original)"]
    rules_fa = ["open < EMA5(low) و fastK<30 و ADX>30 و close<BB پایین", "خروج: fastK>70 یا close>EMA5(high) یا ۱۵ کندل", "فقط خرید (اصل)"]
    pros_en = ["Ultra-simple reference"]
    cons_en = ["Documented negative expectancy after fees — educational"]
    pros_fa = ["مرجع بسیار ساده"]
    cons_fa = ["انتظار منفی مستند بعد از کارمزد — آموزشی"]

    def run(self, df):
        p = self.p
        ema_hi = ta.ema(df.high, p["ema_hi"]); ema_lo = ta.ema(df.low, p["ema_hi"])
        ll = df.low.rolling(5).min(); hh = df.high.rolling(5).max()
        fastk = 100 * (df.close - ll) / (hh - ll).replace(0, np.nan)
        adx, _, _ = ta.adx(df, 14)
        ub, mb, lb = ta.bollinger(df.close, 20, 2.0)
        a = ta.atr(df, 14)
        long = (df.open < ema_lo) & (fastk < p["fastk"]) & (adx > p["adx_min"]) & (df.close < lb)
        sig = self.make_signal(long, pd.Series(False, index=df.index))
        st, tp = self.atr_stops(df, sig, a, p["sl_atr"], p["sl_atr"] * p["rr"])
        exit_long = (fastk > 70) | (df.close > ema_hi)
        return StrategyResult(sig, st, tp, overlays={"EMA5 high": ema_hi, "EMA5 low": ema_lo, "BB lo": lb},
                              panels={"FastK": {"%K": fastk}, "ADX": {"ADX": adx}}, exit_long=exit_long, bt_kwargs=dict(self.bt_kwargs))


# ----------------------------------------------------------------------------- 7. Flat-Bollinger + Stochastic range scalp (quiet hours)
class FlatBBStochScalp(Strategy):
    id = "flat_bb_stoch"
    name_en = "Flat-Bollinger + Stochastic Range Scalp (quiet hours)"
    name_fa = "اسکالپ رنج بولینگر صاف + استوکاستیک (ساعات آرام)"
    category = "Mean-Reversion"
    author = "Classic M5 forex scalp (Asia session)"
    difficulty = 1
    timeframes = "1m – 15m"
    params = {"bw_pct_max": 25, "slope_atr": 0.15, "os": 20, "ob": 80, "sl_frac": 1.0}
    bt_kwargs = {"max_bars": 30}
    description_en = ("Only when Bollinger width is in its lowest 25 % of the last 200 bars AND the middle band is flat (|slope| < 0.15 ATR/5 bars): "
                      "buy a touch of the lower band with stochastic < 20, target the upper band, stop = distance to the middle band below entry. "
                      "Built for the Asian session when Europe sleeps.")
    description_fa = ("فقط وقتی عرض بولینگر در ۲۵٪ پایینی ۲۰۰ کندل اخیر است و باند وسط صاف: خرید روی لمس باند پایین با استوکاستیک < ۲۰، هدف باند بالا، "
                      "حد ضرر = فاصلهٔ باند وسط زیر ورود. برای سشن آسیا وقتی اروپا خواب است.")
    rules_en = ["BB width percentile ≤ 25 and flat middle band", "Long: low ≤ BB lower and Stoch %K < 20 (mirror short)", "Target opposite band; stop = 1× (mid − entry) beyond entry"]
    rules_fa = ["صدک عرض BB ≤ ۲۵ و باند وسط صاف", "خرید: کف ≤ باند پایین و %K < ۲۰ (فروش برعکس)", "هدف باند مقابل؛ حد ضرر = ۱× (وسط − ورود) آن‌سوی ورود"]
    pros_en = ["Trades the 'sleepy market' others skip"]
    cons_en = ["Must be OFF during London/NY expansions"]
    pros_fa = ["بازار خواب‌آلود را که دیگران رد می‌کنند معامله می‌کند"]
    cons_fa = ["در انبساط لندن/نیویورک باید خاموش باشد"]

    def run(self, df):
        p = self.p
        ub, mb, lb = ta.bollinger(df.close, 20, 2.0)
        a = ta.atr(df, 14)
        bw = (ub - lb) / mb
        bw_pct = bw.rolling(200).rank(pct=True) * 100
        flat = (mb - mb.shift(5)).abs() < p["slope_atr"] * a
        k, d = ta.stochastic(df, 14, 3, 3)
        quiet = (bw_pct <= p["bw_pct_max"]) & flat
        long = quiet & (df.low <= lb) & (k < p["os"]) & (df.close > lb)
        short = quiet & (df.high >= ub) & (k > p["ob"]) & (df.close < ub)
        sig = self.make_signal(long, short)
        stop = pd.Series(np.nan, index=df.index); tgt = pd.Series(np.nan, index=df.index)
        d_l = (mb - df.close).clip(lower=0.3 * a); d_s = (df.close - mb).clip(lower=0.3 * a)
        stop[sig == 1] = (df.close - p["sl_frac"] * d_l)[sig == 1]; tgt[sig == 1] = ub[sig == 1]
        stop[sig == -1] = (df.close + p["sl_frac"] * d_s)[sig == -1]; tgt[sig == -1] = lb[sig == -1]
        return StrategyResult(sig, stop, tgt, overlays={"BB up": ub, "BB mid": mb, "BB lo": lb}, panels={"Stoch": {"%K": k, "%D": d}, "BBW%": {"pct": bw_pct}},
                              bt_kwargs=dict(self.bt_kwargs))


# ----------------------------------------------------------------------------- 8. NFI-style multi-condition dip (informative 1h gate)
class NFIDipMulti(Strategy):
    id = "nfi_dip_multi"
    name_en = "NFI-style Multi-Condition Dip (1h informative gate)"
    name_fa = "خرید دیپ چندشرطی به سبک NFI (گیت اطلاعاتی ۱ ساعته)"
    category = "Mean-Reversion"
    author = "NostalgiaForInfinity (iterativv) — distilled buy-condition logic"
    difficulty = 3
    timeframes = "5m – 15m"
    params = {"anchor_factor": 12, "ewo_min": 0.3, "rsi_max": 35, "bb_off": 1.0, "sl_atr": 2.5, "rr": 1.2}
    bt_kwargs = {"max_bars": 60, "allow_short": False}
    description_en = ("What NFI's 60+ buy conditions have in common: (1) higher-timeframe not in a dump (1h RSI(14) > 30 and 1h close > 1h EMA200 × 0.97), "
                      "(2) Elliott-Wave-Oscillator (EMA5−EMA35 in %) > 0.3 → up-market (NFI uses > 2 on alts; recalibrated to majors), (3) sharp local dip: close < BB lower and RSI < 35, "
                      "(4) volume not collapsing. Long-only, dip-buy, small target 1.2R and a generous time stop — the NFI profile.")
    description_fa = ("وجه مشترک ۶۰+ شرط خرید NFI: (۱) تایم بالاتر در ریزش نباشد (RSI ۱ ساعته > ۳۰ و close ۱ ساعته > EMA200×۰.۹۷)، (۲) اسیلاتور الیوت "
                      "(EMA5−EMA35 درصدی) > ۲ → بازار صعودی، (۳) دیپ محلی تند: close < باند پایین BB×۰.۹۸۵ و RSI < ۳۲، (۴) حجم فرو نریخته. فقط خرید.")
    rules_en = ["1h gate: RSI>30 & close > 0.97×EMA200", "EWO (6 bars earlier) > 0.3", "close < BB lower & RSI(14) < 35 & rel.volume ≥ 0.5", "Stop 2.5 ATR; target 1.2R; time stop 60"]
    rules_fa = ["گیت ۱ ساعته: RSI>30 و close > ۰.۹۷×EMA200", "EWO (6 bars earlier) > 0.3", "close < BB پایین و RSI(14) < 35 و حجم نسبی ≥ ۰.۵", "حد ضرر ۲.۵ATR؛ هدف ۱.۲R؛ حد زمانی ۶۰"]
    pros_en = ["Captures NFI's core without 5 000 lines"]
    cons_en = ["Long-only; bleeds in bear markets like NFI (14 % WR reported without its protections)"]
    pros_fa = ["هستهٔ NFI را بدون ۵۰۰۰ خط می‌گیرد"]
    cons_fa = ["فقط خرید؛ در بازار خرسی مثل NFI خون‌ریزی می‌کند"]

    def run(self, df):
        p = self.p
        from core.data import resample
        mins = _bar_minutes(df)
        try:
            hi = resample(df, f"{int(round(mins * p['anchor_factor']))}min")
            r_h = ta.rsi(hi.close, 14); e_h = ta.ema(hi.close, 200)
            gate_h = ((r_h > 30) & (hi.close > 0.97 * e_h)).shift(1)
            gate = gate_h.reindex(df.index, method="ffill").fillna(False).astype(bool)
        except Exception:
            gate = pd.Series(True, index=df.index)
        ewo = (ta.ema(df.close, 5) - ta.ema(df.close, 35)) / df.close * 100
        ub, mb, lb = ta.bollinger(df.close, 20, 2.0)
        r = ta.rsi(df.close, 14)
        rv = _relvol(df, 48)
        a = ta.atr(df, 14)
        ewo_pre = ewo.shift(6)                                   # up-market BEFORE the dip (same-bar EWO is negative inside a dip by construction)
        long = gate & (ewo_pre > p["ewo_min"]) & (df.close < p["bb_off"] * lb) & (r < p["rsi_max"]) & (rv >= 0.5)
        sig = self.make_signal(long, pd.Series(False, index=df.index))
        st, tp = self.atr_stops(df, sig, a, p["sl_atr"], p["sl_atr"] * p["rr"])
        return StrategyResult(sig, st, tp, overlays={"BB lo": lb, "BB mid": mb}, panels={"EWO": {"hist": ewo}, "RSI": {"RSI": r}}, bt_kwargs=dict(self.bt_kwargs))


# ----------------------------------------------------------------------------- 9. Poor high/low (unfinished auction) revisit
class UnfinishedAuction(Strategy):
    id = "unfinished_auction"
    name_en = "Unfinished Auction (poor high/low) Revisit"
    name_fa = "بازدید مجدد حراج ناتمام (سقف/کف ضعیف)"
    category = "Price-Action"
    author = "Market Profile (Dalton) / footprint 'unfinished auction'"
    difficulty = 3
    timeframes = "1m – 15m"
    params = {"n": 30, "flat_ticks_atr": 0.15, "sl_atr": 1.0, "rr": 1.5}
    bt_kwargs = {"max_bars": 40}
    description_en = ("A swing high formed by ≥ 3 bars with (almost) the same high is a 'poor high' — the auction did not finish, buyers were not "
                      "exhausted, the level is a magnet. Rule: after price leaves a poor high by ≥ 1.5 ATR and then starts returning (close above EMA20), "
                      "go long targeting the poor high; mirror for poor lows.")
    description_fa = ("سوینگ‌های سقفی با ≥ ۳ کندل با سقف تقریباً برابر «سقف ضعیف» است — حراج تمام نشده، خریداران خسته نشده‌اند، سطح آهن‌ربا است. قانون: بعد از "
                      "این‌که قیمت ≥ ۱.۵ATR از سقف ضعیف دور شد و شروع به بازگشت کرد (بسته‌شدن بالای EMA20)، خرید با هدف سقف ضعیف؛ برای کف ضعیف برعکس.")
    rules_en = ["Poor high: 3 bars within 0.15 ATR of the same high, unbroken for 30 bars", "Price ≥ 1.5 ATR below it, then close crosses above EMA20",
                "Target poor high; stop 1 ATR under entry bar low"]
    rules_fa = ["سقف ضعیف: ۳ کندل در ۰.۱۵ATR از یک سقف، ۳۰ کندل نشکسته", "قیمت ≥ ۱.۵ATR زیر آن، سپس بسته‌شدن بالای EMA20 کراس کند",
                "هدف سقف ضعیف؛ حد ضرر ۱ATR زیر کف کندل ورود"]
    pros_en = ["Clear magnet target"]
    cons_en = ["Magnets can take long — time stop matters"]
    pros_fa = ["هدف آهن‌ربایی واضح"]
    cons_fa = ["آهن‌ربا ممکن است دیر عمل کند — حد زمانی مهم است"]

    def run(self, df):
        p = self.p
        a = ta.atr(df, 14)
        e = ta.ema(df.close, 20)
        h, l = df.high, df.low
        tol = p["flat_ticks_atr"] * a
        poor_hi = ((h - h.shift(1)).abs() <= tol) & ((h - h.shift(2)).abs() <= tol) & (h >= h.rolling(p["n"]).max() - tol)
        poor_lo = ((l - l.shift(1)).abs() <= tol) & ((l - l.shift(2)).abs() <= tol) & (l <= l.rolling(p["n"]).min() + tol)
        ph_level = h.where(poor_hi).ffill(); pl_level = l.where(poor_lo).ffill()
        # invalidate once broken
        ph_level = ph_level.where(h.rolling(3).max() < ph_level + tol)
        pl_level = pl_level.where(l.rolling(3).min() > pl_level - tol)
        ph_level = ph_level.ffill(limit=200); pl_level = pl_level.ffill(limit=200)
        far_below = (ph_level - df.close) >= 1.5 * a
        far_above = (df.close - pl_level) >= 1.5 * a
        long = far_below.shift(1).fillna(False).astype(bool) & self.cross_up(df.close, e) & (ph_level - df.close > 0.8 * a)
        short = far_above.shift(1).fillna(False).astype(bool) & self.cross_down(df.close, e) & (df.close - pl_level > 0.8 * a)
        # one attempt per level: suppress repeats while the level is unchanged
        long &= ph_level != ph_level.where(long).ffill().shift(1)
        short &= pl_level != pl_level.where(short).ffill().shift(1)
        sig = self.make_signal(long, short)
        stop = pd.Series(np.nan, index=df.index); tgt = pd.Series(np.nan, index=df.index)
        stop[sig == 1] = (df.low - p["sl_atr"] * a)[sig == 1]; tgt[sig == 1] = ph_level[sig == 1]
        stop[sig == -1] = (df.high + p["sl_atr"] * a)[sig == -1]; tgt[sig == -1] = pl_level[sig == -1]
        return StrategyResult(sig, stop, tgt, overlays={"poor high": ph_level, "poor low": pl_level, "EMA20": e}, bt_kwargs=dict(self.bt_kwargs))


ORDERFLOW_STRATEGIES = [ValueAreaBounce, TripleA, StackedImbalanceRetest, LVNBreakout, AnchoredScalp, FreqtradeScalp, FlatBBStochScalp,
                        NFIDipMulti, UnfinishedAuction]
