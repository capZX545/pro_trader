# -*- coding: utf-8 -*-
"""
Phase 12 — complete usage sheet for every indicator (all the ways traders actually use it), bilingual.
Merged into INDICATOR_CATALOG by `full_catalog()`; the Encyclopedia page renders:  params · uses · signals · pitfalls · combos.

Each entry:  params (defaults), uses (list), signals (list of concrete rules), pitfalls (list), combos (works best with)
Language keys end with _en/_fa.
"""

U = {}


def _e(key, params, uses_en, uses_fa, sig_en, sig_fa, pit_en, pit_fa, combo_en, combo_fa):
    U[key] = dict(params=params, uses_en=uses_en, uses_fa=uses_fa, signals_en=sig_en, signals_fa=sig_fa,
                  pitfalls_en=pit_en, pitfalls_fa=pit_fa, combos_en=combo_en, combos_fa=combo_fa)


# ------------------------------------------------------------------ moving averages (shared text, per-type notes)
_MA_USES_EN = ["Trend filter: trade only in the direction of the slope / price side", "Dynamic support & resistance (pullback entries)",
               "Crossovers of two lengths (fast/slow) for entries and exits", "Trailing stop (close below MA = exit)",
               "Envelope/band centre line (Bollinger, Keltner, ATR bands)", "Smoothing input for other indicators (MACD, RSI-MA, signal lines)"]
_MA_USES_FA = ["فیلتر روند: فقط در جهت شیب / سمت قیمت معامله کنید", "حمایت و مقاومت پویا (ورود در پولبک)",
               "کراس دو طول (تند/کند) برای ورود و خروج", "استاپ دنباله‌دار (بسته‌شدن زیر MA = خروج)",
               "خط مرکزی باندها (بولینگر، کلتنر، باند ATR)", "هموارسازی ورودی سایر اندیکاتورها (MACD، RSI-MA، خط سیگنال)"]
_MA_SIG_EN = ["Price closes above rising MA → bullish bias; below falling MA → bearish", "Fast MA crosses above slow MA → buy (golden cross 50/200 on daily)",
              "Pullback touches MA in a trend and prints a rejection candle → continuation entry", "Distance from MA > 2 ATR → stretched, avoid chasing (mean reversion risk)"]
_MA_SIG_FA = ["بسته‌شدن قیمت بالای MA صعودی → سوگیری خرید؛ زیر MA نزولی → فروش", "کراس MA تند بالای کند → خرید (تقاطع طلایی ۵۰/۲۰۰ روزانه)",
              "پولبک به MA در روند + کندل برگشتی → ورود ادامه‌دهنده", "فاصله از MA > ۲ ATR → کشیده‌شده؛ دنبال نکنید (ریسک بازگشت به میانگین)"]
_MA_PIT_EN = ["Lags the price — late entries/exits in fast reversals", "Whipsaws in ranges: many false crosses", "No MA works on all markets; length must fit the timeframe/volatility"]
_MA_PIT_FA = ["از قیمت عقب است — ورود/خروج دیرهنگام در برگشت‌های سریع", "در رنج اره می‌کند: کراس‌های کاذب زیاد", "هیچ MA برای همهٔ بازارها کار نمی‌کند؛ طول باید با تایم‌فریم/نوسان بخواند"]

for k, p, note_en, note_fa in [
    ("sma", "length=20/50/200", "Most widely watched (200-day = institutional trend line).", "پرمخاطب‌ترین (۲۰۰ روزه = خط روند نهادی)."),
    ("ema", "length=9/21/50/200", "Faster than SMA; standard for intraday and MACD.", "سریع‌تر از SMA؛ استاندارد اینترادی و MACD."),
    ("wma", "length=20", "Linear weights; middle ground between SMA and EMA.", "وزن خطی؛ بین SMA و EMA."),
    ("hma", "length=16/55", "Very low lag with little noise; slope colour flips are used as entries.", "تأخیر بسیار کم و نویز کم؛ تغییر رنگ شیب به‌عنوان ورود."),
    ("dema", "length=20", "Double smoothing minus lag.", "هموارسازی دوگانه منهای تأخیر."),
    ("tema", "length=20", "Triple smoothing; fastest of the classic family.", "هموارسازی سه‌گانه؛ سریع‌ترین خانوادهٔ کلاسیک."),
    ("zlema", "length=20", "Zero-lag error correction; overshoots on spikes.", "تصحیح خطای بدون تأخیر؛ روی اسپایک بیش‌ازحد می‌رود."),
    ("kama", "er=10, fast=2, slow=30", "Adapts: flat in noise, fast in trends — great trailing stop.", "تطبیقی: صاف در نویز، سریع در روند — استاپ دنباله‌دار عالی."),
    ("alma", "length=9, offset=0.85, sigma=6", "Gaussian weights; smooth and responsive.", "وزن گاوسی؛ نرم و واکنش‌گرا."),
    ("t3", "length=5, vfactor=0.7", "Tillson T3, very smooth; slope used as trend state.", "T3 تیلسون، بسیار نرم؛ شیب = وضعیت روند."),
    ("mcginley", "length=14", "Speed self-adjusts to price change; fewer whipsaws.", "سرعت خود را با تغییر قیمت تنظیم می‌کند؛ اره کمتر."),
    ("supersmoother", "length=10", "Ehlers 2-pole filter; removes aliasing noise.", "فیلتر دو‌قطبی الرز؛ نویز aliasing را حذف می‌کند."),
    ("linreg", "length=20", "Least-squares line end-point; slope = trend strength, channel = ±2σ.", "نقطهٔ پایان خط حداقل مربعات؛ شیب = قدرت روند، کانال = ±۲σ."),
    ("vwma", "length=20", "Volume-weighted: heavy-volume bars pull the line — confirms conviction.", "وزن حجمی: کندل‌های پرحجم خط را می‌کشند — تأیید قاطعیت."),
]:
    _e(k, p, _MA_USES_EN + [note_en], _MA_USES_FA + [note_fa], _MA_SIG_EN, _MA_SIG_FA, _MA_PIT_EN, _MA_PIT_FA,
       ["ADX (only trade crosses when ADX>20)", "Volume / RVOL for breakout confirmation", "RSI for pullback timing"],
       ["ADX (کراس فقط وقتی ADX>۲۰)", "حجم / RVOL برای تأیید شکست", "RSI برای زمان‌بندی پولبک"])

# ------------------------------------------------------------------ trend systems
_e("ichimoku", "tenkan=9, kijun=26, senkou_b=52, displacement=26",
   ["Complete system: trend (cloud), momentum (TK cross), confirmation (Chikou), S/R (Kijun, cloud edges)", "Cloud thickness = strength of support/resistance",
    "Future cloud colour = forward bias", "Kijun as trailing stop / mean-reversion magnet"],
   ["سیستم کامل: روند (ابر)، مومنتوم (کراس TK)، تأیید (چیکو)، حمایت/مقاومت (کیجون، لبهٔ ابر)", "ضخامت ابر = قدرت حمایت/مقاومت",
    "رنگ ابر آینده = سوگیری پیش‌رو", "کیجون به‌عنوان استاپ دنباله‌دار / آهنربای بازگشت به میانگین"],
   ["Price above cloud + Tenkan>Kijun + Chikou above price 26 bars ago → strong long", "TK cross above the cloud = strong; inside = neutral; below = weak",
    "Kumo twist (Senkou A crosses B) = potential trend change", "Price breaks out of a thin cloud → high-probability trend start"],
   ["قیمت بالای ابر + تنکان>کیجون + چیکو بالای قیمتِ ۲۶ کندل قبل → لانگ قوی", "کراس TK بالای ابر = قوی؛ داخل ابر = خنثی؛ زیر ابر = ضعیف",
    "کومو تویست (سنکو A از B عبور کند) = تغییر روند بالقوه", "شکست قیمت از ابر نازک → شروع روند با احتمال بالا"],
   ["Useless in ranges (price inside the cloud most of the time)", "Default 9/26/52 were designed for 6-day weeks; crypto often uses 10/30/60/30"],
   ["در رنج بی‌فایده (قیمت اغلب داخل ابر)", "پیش‌فرض ۹/۲۶/۵۲ برای هفتهٔ ۶ روزه طراحی شده؛ کریپتو اغلب ۱۰/۳۰/۶۰/۳۰"],
   ["RSI divergence at cloud edges", "ATR stops instead of Kijun in volatile assets"], ["واگرایی RSI در لبهٔ ابر", "استاپ ATR به‌جای کیجون در دارایی‌های پرنوسان"])
_e("supertrend", "atr=10, mult=3",
   ["Trend direction flag (colour)", "Trailing stop that ratchets only in trade direction", "Multi-timeframe filter (HTF supertrend = bias)", "Triple-supertrend confluence (mult 1/2/3)"],
   ["پرچم جهت روند (رنگ)", "استاپ دنباله‌دار که فقط در جهت معامله جلو می‌رود", "فیلتر چند تایم‌فریمی (سوپرترند HTF = سوگیری)", "هم‌راستایی سه سوپرترند (ضریب ۱/۲/۳)"],
   ["Flip to green (close above line) → long; flip to red → short/exit", "Pullback to the line in a trend without a flip → add/enter", "Line flat for many bars → range, stand aside"],
   ["تغییر به سبز (بسته بالای خط) → لانگ؛ به قرمز → شورت/خروج", "پولبک تا خط بدون فلیپ → افزودن/ورود", "خط چند کندل صاف → رنج، کنار بایستید"],
   ["Whipsaws violently in sideways markets", "Multiplier too small = noise, too large = late"], ["در بازار خنثی به‌شدت اره می‌کند", "ضریب کوچک = نویز، بزرگ = دیر"],
   ["ADX>20 filter", "EMA200 direction", "Volume on the flip bar"], ["فیلتر ADX>۲۰", "جهت EMA200", "حجم در کندل فلیپ"])
_e("psar", "step=0.02, max=0.2",
   ["Trailing stop for trend trades", "Stop-and-reverse entries in strong trends", "Time-based acceleration: the longer the trend, the tighter the stop"],
   ["استاپ دنباله‌دار برای معاملات روندی", "ورود توقف-و-برگشت در روندهای قوی", "شتاب زمانی: هرچه روند طولانی‌تر، استاپ تنگ‌تر"],
   ["Dots flip below price → long; above → short", "Dots accelerating toward price → trend maturing, tighten risk"],
   ["نقطه‌ها زیر قیمت → لانگ؛ بالا → شورت", "نقطه‌ها با شتاب به قیمت نزدیک می‌شوند → روند در حال بلوغ، ریسک را کم کنید"],
   ["Constantly flips in ranges — never use alone", "step 0.02 too fast for crypto daily; try 0.01"], ["در رنج مدام فلیپ می‌کند — هرگز تنها استفاده نکنید", "گام ۰٫۰۲ برای روزانهٔ کریپتو تند است؛ ۰٫۰۱ را امتحان کنید"],
   ["ADX (Wilder designed them together)", "MA200 direction filter"], ["ADX (وایلدر هر دو را با هم طراحی کرد)", "فیلتر جهت MA200"])
_e("halftrend", "amplitude=2, channel_dev=2", ["Trend flag with built-in ATR channel", "Entry arrows on flips", "Channel edges as pullback zones"],
   ["پرچم روند با کانال ATR داخلی", "فلش ورود در فلیپ", "لبهٔ کانال = ناحیهٔ پولبک"], ["Flip up + close above channel mid → long", "Flip against HTF trend → ignore"],
   ["فلیپ بالا + بسته بالای میانهٔ کانال → لانگ", "فلیپ خلاف روند HTF → نادیده بگیرید"], ["Repaints inside the current bar until close"], ["تا بسته‌شدن کندل جاری تغییر می‌کند"],
   ["HTF EMA", "RSI 50 line"], ["EMA تایم بالاتر", "خط ۵۰ RSI"])
_e("adx", "length=14",
   ["Trend STRENGTH (not direction): ADX>25 trending, <20 ranging", "Regime switch: trend systems when ADX rising, mean-reversion when falling below 20",
    "+DI/−DI crossover for direction", "ADX peak & turn-down = trend exhaustion, tighten stops"],
   ["قدرت روند (نه جهت): ADX>۲۵ روند، <۲۰ رنج", "سوئیچ رژیم: سیستم روندی وقتی ADX صعودی، بازگشت‌به‌میانگین وقتی زیر ۲۰",
    "کراس +DI/−DI برای جهت", "اوج ADX و برگشت = خستگی روند، استاپ را تنگ کنید"],
   ["ADX crosses above 20–25 with +DI>−DI → new uptrend", "ADX>40 then turning down → take partial profit", "+DI crosses −DI while ADX>20 → entry"],
   ["ADX از ۲۰–۲۵ بالا برود با +DI>−DI → روند صعودی جدید", "ADX>۴۰ سپس برگشت → سود بخشی را ببندید", "کراس +DI از −DI وقتی ADX>۲۰ → ورود"],
   ["Very laggy (double smoothing)", "High ADX in a downtrend confuses beginners — it is not bullish"], ["بسیار کند (دو بار هموار)", "ADX بالا در روند نزولی گیج‌کننده است — صعودی نیست"],
   ["Any MA cross / breakout system", "Bollinger squeeze"], ["هر سیستم کراس MA / شکست", "اسکوییز بولینگر"])
_e("aroon", "length=25", ["Time since highest high / lowest low → trend freshness", "Aroon oscillator (Up−Down) as trend gauge", "Range detection when both < 50"],
   ["زمان از آخرین سقف/کف → تازگی روند", "نوسانگر آرون (Up−Down) به‌عنوان سنجهٔ روند", "تشخیص رنج وقتی هر دو < ۵۰"],
   ["Aroon Up crosses above 70 while Down < 30 → uptrend start", "Both between 30–70 → consolidation"], ["آرون Up بالای ۷۰ و Down زیر ۳۰ → شروع روند صعودی", "هر دو بین ۳۰–۷۰ → تثبیت"],
   ["Ignores magnitude of moves"], ["اندازهٔ حرکت را نادیده می‌گیرد"], ["ADX", "Donchian breakout"], ["ADX", "شکست دونچیان"])
_e("vortex", "length=14", ["VI+ / VI− crossover for trend starts", "Spread between them = strength"], ["کراس VI+ / VI− برای شروع روند", "فاصلهٔ آن‌ها = قدرت"],
   ["VI+ crosses above VI− → long; confirm with close above prior swing"], ["VI+ از VI− بالا برود → لانگ؛ تأیید با بسته بالای سوئینگ قبلی"],
   ["Many crosses in chop"], ["کراس زیاد در بازار پرنوسان"], ["ADX", "Chandelier stop"], ["ADX", "استاپ چندلیر"])
_e("trix", "length=15, signal=9", ["Momentum of a triple-EMA; zero-line = trend", "Signal-line cross", "Divergence"], ["مومنتوم EMA سه‌گانه؛ خط صفر = روند", "کراس خط سیگنال", "واگرایی"],
   ["TRIX crosses above 0 → uptrend; above signal → entry"], ["TRIX بالای صفر → روند صعودی؛ بالای سیگنال → ورود"], ["Slow; misses first leg"], ["کند؛ موج اول را از دست می‌دهد"],
   ["RSI", "Volume"], ["RSI", "حجم"])
_e("kst", "roc 10/15/20/30, sma 10/10/10/15, signal 9", ["Multi-horizon momentum summary (Pring)", "Signal cross on weekly charts for major turns"],
   ["خلاصهٔ مومنتوم چند‌افقی (پرینگ)", "کراس سیگنال در نمودار هفتگی برای چرخش‌های بزرگ"], ["KST crosses signal from below near zero → cyclical buy"],
   ["KST از زیر نزدیک صفر سیگنال را قطع کند → خرید چرخه‌ای"], ["Designed for weekly/monthly — noisy intraday"], ["برای هفتگی/ماهانه طراحی شده — در اینترادی نویزی"],
   ["Coppock", "200-week MA"], ["کاپاک", "MA ۲۰۰ هفته"])
_e("coppock", "roc 14 & 11, wma 10", ["Long-term bottom finder for indices (monthly)"], ["یابندهٔ کف بلندمدت شاخص‌ها (ماهانه)"],
   ["Turns up from below zero → long-term buy"], ["از زیر صفر رو به بالا برگردد → خرید بلندمدت"], ["No sell signal by design"], ["طبق طراحی سیگنال فروش ندارد"],
   ["KST", "Breadth"], ["KST", "وسعت بازار"])
_e("dpo", "length=20", ["Removes trend to expose cycles", "Cycle length estimation (peak-to-peak)"], ["حذف روند برای آشکارسازی چرخه", "برآورد طول چرخه (اوج تا اوج)"],
   ["DPO trough below zero + turn up → cyclical low"], ["کف DPO زیر صفر + برگشت → کف چرخه‌ای"], ["Shifted back N/2+1 bars — last bars are missing (never use for live entries)"],
   ["N/2+1 کندل به عقب شیفت شده — کندل‌های آخر ندارد (برای ورود زنده استفاده نکنید)"], ["Hurst", "Stochastic"], ["هرست", "استوکاستیک"])
_e("schaff", "macd 23/50, cycle=10", ["Faster MACD via stochastic cycles", "Overbought/oversold 75/25 crosses"], ["MACD سریع‌تر با چرخهٔ استوکاستیک", "کراس ۷۵/۲۵ اشباع"],
   ["Crosses up through 25 → buy; down through 75 → sell"], ["از ۲۵ بالا برود → خرید؛ از ۷۵ پایین → فروش"], ["Stays pinned at 0/100 in strong trends"], ["در روند قوی به ۰/۱۰۰ می‌چسبد"],
   ["EMA200 trend filter"], ["فیلتر روند EMA200"])
_e("hurst", "window=100", ["Regime classifier: H>0.55 trending (momentum works), H<0.45 mean-reverting (fade extremes)", "Strategy selector"],
   ["طبقه‌بند رژیم: H>۰٫۵۵ روندی (مومنتوم کار می‌کند)، H<۰٫۴۵ بازگشت‌به‌میانگین (اکستریم‌ها را فید کنید)", "انتخاب‌گر استراتژی"],
   ["H rising through 0.55 → switch to trend systems"], ["H از ۰٫۵۵ بالا برود → به سیستم روندی سوئیچ کنید"], ["Needs long windows; noisy estimate"], ["پنجرهٔ بلند می‌خواهد؛ برآورد نویزی"],
   ["ADX", "Choppiness"], ["ADX", "چاپینس"])
_e("efficiency_ratio", "length=10", ["Kaufman ER: net move ÷ path length (0 noise … 1 straight line)", "Trend quality filter", "Adaptive MA speed"],
   ["ER کافمن: حرکت خالص ÷ طول مسیر (۰ نویز … ۱ خط مستقیم)", "فیلتر کیفیت روند", "سرعت MA تطبیقی"],
   ["ER>0.5 → follow breakouts; ER<0.3 → fade"], ["ER>۰٫۵ → شکست‌ها را دنبال کنید؛ ER<۰٫۳ → فید"], ["Direction-blind"], ["به جهت بی‌اعتنا"], ["KAMA", "ADX"], ["KAMA", "ADX"])
_e("choppiness", "length=14", ["Range vs trend gauge: >61.8 choppy, <38.2 trending", "Breakout anticipation after extended chop"],
   ["سنجهٔ رنج/روند: >۶۱٫۸ خنثی، <۳۸٫۲ روندی", "پیش‌بینی شکست پس از خنثی طولانی"],
   ["CHOP falls from >61.8 below 50 with volume → breakout underway"], ["CHOP از >۶۱٫۸ زیر ۵۰ بیاید با حجم → شکست در جریان"], ["No direction"], ["بدون جهت"],
   ["Donchian", "Bollinger width"], ["دونچیان", "پهنای بولینگر"])

# ------------------------------------------------------------------ momentum
_e("rsi", "length=14 (2 for Connors, 7 intraday)",
   ["Overbought/oversold 70/30 (in ranges only)", "Trend filter: bull range 40–90, bear range 10–60 (Cardwell)", "Classic & hidden divergence",
    "50-line cross as momentum shift", "RSI trendline breaks (lead price)", "RSI(2) extreme mean reversion (Connors)", "Failure swings"],
   ["اشباع خرید/فروش ۷۰/۳۰ (فقط در رنج)", "فیلتر روند: بازهٔ گاوی ۴۰–۹۰، خرسی ۱۰–۶۰ (کاردول)", "واگرایی کلاسیک و مخفی",
    "کراس خط ۵۰ = تغییر مومنتوم", "شکست خط روند روی RSI (جلوتر از قیمت)", "بازگشت‌به‌میانگین RSI(2) (کانرز)", "سوئینگ‌های ناکام"],
   ["Uptrend + RSI dips to 40–50 and turns up → buy pullback", "Price higher high & RSI lower high → bearish divergence, tighten stop",
    "RSI(2)<10 above SMA200 → buy, exit at close above SMA5", "RSI breaks its own trendline before price → early warning"],
   ["روند صعودی + RSI به ۴۰–۵۰ برسد و برگردد → خرید پولبک", "سقف بالاتر قیمت و سقف پایین‌تر RSI → واگرایی نزولی، استاپ را تنگ کنید",
    "RSI(2)<۱۰ بالای SMA200 → خرید، خروج در بسته بالای SMA5", "RSI خط روند خودش را قبل از قیمت بشکند → هشدار زودهنگام"],
   ["Stays overbought for weeks in strong trends — selling 70 in a bull market loses", "Divergences can persist a long time"],
   ["در روند قوی هفته‌ها اشباع می‌ماند — فروش در ۷۰ در بازار گاوی ضرر می‌دهد", "واگرایی می‌تواند مدت زیادی ادامه یابد"],
   ["SMA200 direction", "Support/resistance levels", "Candlestick reversal"], ["جهت SMA200", "سطوح حمایت/مقاومت", "کندل برگشتی"])
_e("stoch", "k=14, d=3, smooth=3 (5,3,3 fast)",
   ["Overbought/oversold 80/20", "%K/%D crosses for timing", "Divergence", "Trend-following: in uptrend only take crosses up from <50 (Lane)"],
   ["اشباع ۸۰/۲۰", "کراس %K/%D برای زمان‌بندی", "واگرایی", "روندی: در روند صعودی فقط کراس رو به بالا از زیر ۵۰ (لِین)"],
   ["%K crosses above %D below 20 → buy in a range", "Bull setup: %K hooks up from 20–40 in an uptrend"], ["%K از %D بالا برود زیر ۲۰ → خرید در رنج", "ستاپ گاوی: %K از ۲۰–۴۰ در روند صعودی قلاب می‌شود"],
   ["Pins to 100/0 in trends", "Fast stochastic is noisy — use slow"], ["در روند به ۱۰۰/۰ می‌چسبد", "استوکاستیک سریع نویزی است — از کند استفاده کنید"],
   ["Bollinger touch", "EMA slope"], ["لمس بولینگر", "شیب EMA"])
_e("stoch_rsi", "rsi=14, stoch=14, k=3, d=3", ["Faster overbought/oversold than RSI", "Crypto favourite for scalps"], ["اشباع سریع‌تر از RSI", "محبوب اسکالپ کریپتو"],
   ["K crosses D below 0.2 in an uptrend → buy"], ["K از D بالا برود زیر ۰٫۲ در روند صعودی → خرید"], ["Very noisy; over-signals"], ["بسیار نویزی؛ سیگنال زیاد"], ["HTF trend", "VWAP"], ["روند HTF", "VWAP"])
_e("macd", "fast=12, slow=26, signal=9",
   ["Trend + momentum in one", "Signal-line cross entries", "Zero-line cross = trend change", "Histogram divergence (Elder)", "Histogram slope as early momentum shift", "Impulse system colour (Elder)"],
   ["روند + مومنتوم در یک ابزار", "ورود با کراس خط سیگنال", "کراس خط صفر = تغییر روند", "واگرایی هیستوگرام (الدر)", "شیب هیستوگرام = تغییر زودهنگام مومنتوم", "رنگ سیستم ایمپالس (الدر)"],
   ["MACD crosses above signal while above zero → continuation buy", "Histogram lower low fails while price makes new low → bullish divergence", "Zero cross after a divergence = strongest"],
   ["MACD بالای سیگنال برود وقتی بالای صفر است → خرید ادامه‌دهنده", "هیستوگرام کف پایین‌تر نسازد ولی قیمت بسازد → واگرایی صعودی", "کراس صفر بعد از واگرایی = قوی‌ترین"],
   ["Late in fast markets", "Unbounded — 'overbought' is undefined"], ["در بازار سریع دیر است", "بی‌کران — «اشباع» تعریف ندارد"], ["EMA trend filter", "ADX"], ["فیلتر روند EMA", "ADX"])
_e("ppo", "fast=12, slow=26, signal=9", ["MACD in % — comparable across symbols/prices", "Screener ranking by momentum"], ["MACD درصدی — قابل مقایسه بین نمادها", "رتبه‌بندی اسکنر با مومنتوم"],
   ["Same as MACD"], ["مانند MACD"], ["Same as MACD"], ["مانند MACD"], ["Relative strength"], ["قدرت نسبی"])
_e("cci", "length=20", ["Deviation from typical price mean: ±100 trend start, extremes ±200", "Zero-line trend", "Divergence", "Woodie CCI patterns"],
   ["انحراف از میانگین قیمت تیپیکال: ±۱۰۰ شروع روند، اکستریم ±۲۰۰", "روند خط صفر", "واگرایی", "الگوهای CCI وودی"],
   ["Crosses above +100 → momentum long; back below +100 → exit", "Below −200 then turns up → mean-reversion long"], ["از +۱۰۰ بالا برود → لانگ مومنتومی؛ برگشت زیر +۱۰۰ → خروج", "زیر −۲۰۰ سپس برگشت → لانگ بازگشتی"],
   ["Unbounded; extremes vary per market"], ["بی‌کران؛ اکستریم‌ها در هر بازار فرق دارد"], ["ADX", "Keltner"], ["ADX", "کلتنر"])
_e("williams_r", "length=14", ["Overbought/oversold −20/−80", "Momentum failure: fails to reach −20 in uptrend = weakness", "Fast timing tool"],
   ["اشباع −۲۰/−۸۰", "ناکامی مومنتوم: در روند صعودی به −۲۰ نرسد = ضعف", "ابزار زمان‌بندی سریع"],
   ["Crosses up through −80 in an uptrend → buy"], ["از −۸۰ بالا برود در روند صعودی → خرید"], ["Very jumpy"], ["بسیار پرشی"], ["Trend MA"], ["MA روند"])
_e("roc", "length=12", ["Pure momentum %", "Zero cross", "Momentum ranking across assets (12-month ROC = classic factor)", "Divergence"],
   ["مومنتوم خالص درصدی", "کراس صفر", "رتبه‌بندی مومنتوم بین دارایی‌ها (ROC ۱۲ ماهه = فاکتور کلاسیک)", "واگرایی"],
   ["Top-decile 12m ROC, rebalanced monthly → momentum portfolio", "ROC turns up from extreme negative → bounce"], ["دهک بالای ROC ۱۲ ماهه، ماهانه بازتنظیم → پرتفوی مومنتوم", "ROC از منفی شدید برگردد → جهش"],
   ["Whipsaw at zero"], ["اره در صفر"], ["Volatility scaling", "MA200"], ["مقیاس‌بندی نوسان", "MA200"])
_e("cmo", "length=14", ["Chande momentum, bounded ±100; ±50 overbought/oversold", "VIDYA input"], ["مومنتوم چانده ±۱۰۰؛ ±۵۰ اشباع", "ورودی VIDYA"],
   ["Crosses above −50 → buy"], ["از −۵۰ بالا برود → خرید"], ["Similar failure modes to RSI"], ["مشکلات مشابه RSI"], ["Trend filter"], ["فیلتر روند"])
_e("ultimate", "7/14/28", ["Three-horizon buying pressure; fewer false divergences (Williams)", "Divergence 30/70 rule"], ["فشار خرید سه‌افقی؛ واگرایی کاذب کمتر (ویلیامز)", "قاعدهٔ واگرایی ۳۰/۷۰"],
   ["Bullish divergence + UO<30 + break of divergence high → buy"], ["واگرایی صعودی + UO<۳۰ + شکست سقف واگرایی → خرید"], ["Rare signals"], ["سیگنال کم"], ["S/R"], ["حمایت/مقاومت"])
_e("awesome", "5/34 median price", ["Bill Williams momentum: zero cross, twin peaks, saucer", "Momentum phase of Alligator system"], ["مومنتوم بیل ویلیامز: کراس صفر، دوقله، نعلبکی", "فاز مومنتوم سیستم الیگیتور"],
   ["Saucer: two red bars then green above zero → buy", "Twin peaks below zero (second higher) → buy"], ["نعلبکی: دو میلهٔ قرمز سپس سبز بالای صفر → خرید", "دوقله زیر صفر (دومی بالاتر) → خرید"],
   ["Noisy on low TFs"], ["در تایم پایین نویزی"], ["Alligator", "Fractals"], ["الیگیتور", "فراکتال"])
_e("accelerator", "AO − SMA5(AO)", ["Acceleration of momentum (leads AO)", "Colour-change entries"], ["شتاب مومنتوم (جلوتر از AO)", "ورود با تغییر رنگ"],
   ["Two consecutive green bars above zero → buy"], ["دو میلهٔ سبز متوالی بالای صفر → خرید"], ["Very early — many fakeouts"], ["خیلی زود — فیک زیاد"], ["Alligator"], ["الیگیتور"])
_e("fisher", "length=10", ["Gaussianised price → sharp turning points", "Extremes ±1.5"], ["قیمت گاوسی‌شده → نقاط چرخش تیز", "اکستریم ±۱٫۵"],
   ["Fisher crosses its 1-bar lag from below −1.5 → buy"], ["فیشر تأخیر یک‌کندلی خود را از زیر −۱٫۵ قطع کند → خرید"], ["Repeated extremes in trends"], ["اکستریم‌های پیاپی در روند"], ["Trend filter"], ["فیلتر روند"])
_e("rvi", "length=10", ["Close−open vs range: conviction of moves", "Signal cross"], ["بسته−باز نسبت به رنج: قاطعیت حرکت", "کراس سیگنال"],
   ["RVI crosses signal up below zero → buy"], ["RVI از سیگنال بالا برود زیر صفر → خرید"], ["Noise in doji-heavy markets"], ["نویز در بازار پر از دوجی"], ["RSI"], ["RSI"])
_e("connors_rsi", "rsi=3, streak=2, pct_rank=100", ["Short-term mean reversion composite", "Extremes <10 / >90"], ["ترکیب بازگشت‌به‌میانگین کوتاه‌مدت", "اکستریم <۱۰ / >۹۰"],
   ["CRSI<10 above SMA200 → buy; exit CRSI>70"], ["CRSI<۱۰ بالای SMA200 → خرید؛ خروج CRSI>۷۰"], ["Designed for stocks/ETFs daily; crypto needs wider thresholds"], ["برای سهام/ETF روزانه؛ کریپتو آستانهٔ گشادتر می‌خواهد"], ["SMA200"], ["SMA200"])
_e("qqe", "rsi=14, smooth=5, factor=4.236", ["Smoothed RSI with ATR-like trailing bands", "Trend flips on band cross"], ["RSI هموار با باند دنباله‌دار شبه‌ATR", "فلیپ روند در کراس باند"],
   ["RSI-MA crosses above trailing line & above 50 → buy"], ["RSI-MA از خط دنباله‌دار و ۵۰ بالا برود → خرید"], ["Lag from double smoothing"], ["تأخیر هموارسازی دوگانه"], ["HTF bias"], ["سوگیری HTF"])
_e("squeeze", "bb 20/2, kc 20/1.5, mom 20", ["Volatility compression detector (BB inside KC)", "Direction from momentum histogram at release", "Pre-breakout watchlist builder"],
   ["آشکارساز فشردگی نوسان (BB داخل KC)", "جهت از هیستوگرام مومنتوم هنگام رهاشدن", "ساخت واچ‌لیست پیش از شکست"],
   ["Squeeze fires (dots turn off) with momentum > 0 rising → long", "Count of squeeze bars ≥ 6 → bigger expected move"], ["اسکوییز رها شود با مومنتوم > ۰ صعودی → لانگ", "شمار کندل‌های اسکوییز ≥ ۶ → حرکت بزرگ‌تر"],
   ["First move after release can be a fake"], ["اولین حرکت بعد از رهاشدن می‌تواند فیک باشد"], ["Volume", "Donchian"], ["حجم", "دونچیان"])
_e("elder_ray", "ema=13", ["Bull/Bear power = highs/lows vs EMA13 (buyer/seller strength)", "Divergence on Bull Power", "Triple Screen timing"],
   ["قدرت گاو/خرس = سقف/کف نسبت به EMA13", "واگرایی روی Bull Power", "زمان‌بندی سه‌صفحه‌ای"],
   ["EMA rising + Bear Power negative but rising → buy", "Bull Power divergence at new highs → sell"], ["EMA صعودی + Bear Power منفی ولی صعودی → خرید", "واگرایی Bull Power در سقف جدید → فروش"],
   ["Needs the weekly trend filter (screen 1)"], ["به فیلتر روند هفتگی (صفحهٔ ۱) نیاز دارد"], ["Weekly MACD-H", "Force Index"], ["MACD-H هفتگی", "Force Index"])

# ------------------------------------------------------------------ volatility
_e("atr", "length=14",
   ["Stop distance (1.5–3 ATR)", "Position sizing (risk ÷ ATR → units) so every trade risks the same", "Volatility regime (ATR% of price)", "Target scaling (R multiples)",
    "Chandelier trailing stop", "Filter: skip entries when ATR > 2× median (news)", "Breakout validity: move > 1 ATR"],
   ["فاصلهٔ استاپ (۱٫۵–۳ ATR)", "اندازهٔ پوزیشن (ریسک ÷ ATR → تعداد) تا هر معامله ریسک برابر داشته باشد", "رژیم نوسان (ATR٪ قیمت)", "مقیاس هدف (مضرب R)",
    "استاپ دنباله‌دار چندلیر", "فیلتر: وقتی ATR > ۲ برابر میانه (خبر) ورود نکنید", "اعتبار شکست: حرکت > ۱ ATR"],
   ["Stop = entry − 2×ATR; size = 1% equity ÷ (2×ATR)", "ATR at 6-month low → expansion coming, prepare breakout plan"], ["استاپ = ورود − ۲×ATR؛ سایز = ۱٪ سرمایه ÷ (۲×ATR)", "ATR در کف ۶ ماهه → انبساط در راه، برنامهٔ شکست"],
   ["Not directional", "Spikes distort for 14 bars"], ["جهت‌دار نیست", "اسپایک ۱۴ کندل اثر می‌گذارد"], ["Everything — it is the risk unit"], ["همه‌چیز — واحد ریسک است"])
_e("bollinger", "length=20, std=2",
   ["Volatility bands: squeeze → breakout", "Mean reversion from bands in ranges", "Band walk = strong trend (do not fade)", "%B for normalised position", "Bandwidth for regime", "W-bottoms / M-tops (Bollinger)"],
   ["باند نوسان: اسکوییز → شکست", "بازگشت‌به‌میانگین از باندها در رنج", "راه‌رفتن روی باند = روند قوی (فید نکنید)", "%B برای موقعیت نرمال‌شده", "پهنای باند برای رژیم", "کف W / سقف M (بولینگر)"],
   ["Bandwidth at 6-month low then close outside band with volume → breakout", "Range + close below lower band + RSI<30 + reversal candle → long to the middle band",
    "W-bottom: second low holds inside the band while first was outside → buy"],
   ["پهنای باند در کف ۶ ماهه سپس بسته بیرون باند با حجم → شکست", "رنج + بسته زیر باند پایین + RSI<۳۰ + کندل برگشتی → لانگ تا باند میانی",
    "کف W: کف دوم داخل باند بماند درحالی‌که اول بیرون بود → خرید"],
   ["Touch of a band is NOT a signal by itself", "Head-fake at squeeze release"], ["لمس باند به‌تنهایی سیگنال نیست", "فیک در رهاشدن اسکوییز"], ["RSI", "Volume", "Keltner (squeeze)"], ["RSI", "حجم", "کلتنر (اسکوییز)"])
_e("keltner", "ema=20, atr=10, mult=1.5–2", ["ATR-based channel; trend pullback to the middle line", "Breakout above upper band (close) = momentum", "Squeeze partner of Bollinger"],
   ["کانال ATR؛ پولبک روند به خط میانی", "شکست بالای باند بالایی (بسته) = مومنتوم", "شریک اسکوییز بولینگر"],
   ["Close above upper KC in uptrend → momentum long, stop at midline"], ["بسته بالای KC بالایی در روند صعودی → لانگ مومنتومی، استاپ خط میانی"], ["Ranges: false breakouts"], ["رنج: شکست کاذب"], ["ADX", "Bollinger"], ["ADX", "بولینگر"])
_e("donchian", "length=20 (entry) / 10 (exit); 55/20 turtle", ["Breakout entry (Turtles)", "Trailing exit on opposite channel", "Range width = volatility", "Mid-line as trend filter"],
   ["ورود شکست (لاک‌پشت‌ها)", "خروج دنباله‌دار در کانال مخالف", "پهنای کانال = نوسان", "خط میانی = فیلتر روند"],
   ["Close above 20-bar high → long; exit close below 10-bar low; pyramid every ½ ATR"], ["بسته بالای سقف ۲۰ کندل → لانگ؛ خروج بسته زیر کف ۱۰ کندل؛ پله هر ½ ATR"],
   ["~60% losing trades by design — needs discipline"], ["طبق طراحی ~۶۰٪ معاملات بازنده — نظم می‌خواهد"], ["ATR sizing", "ADX"], ["سایز ATR", "ADX"])
_e("hist_vol", "length=20/30, annualised", ["Realised volatility % for regime & sizing", "Vol targeting (size ∝ 1/σ)", "Compare to implied vol (options)"],
   ["نوسان محقق‌شدهٔ درصدی برای رژیم و سایز", "هدف‌گذاری نوسان (سایز ∝ 1/σ)", "مقایسه با نوسان ضمنی (آپشن)"],
   ["σ in bottom decile → expect expansion; cut size when σ doubles"], ["σ در دهک پایین → انتظار انبساط؛ وقتی σ دو برابر شد سایز را نصف کنید"], ["Backward-looking"], ["گذشته‌نگر"], ["ATR", "Bollinger width"], ["ATR", "پهنای بولینگر"])
_e("mass_index", "ema=9, sum=25", ["Reversal bulge: range expansion then contraction", "Direction from EMA9 slope"], ["برآمدگی برگشت: انبساط سپس انقباض رنج", "جهت از شیب EMA9"],
   ["Rises above 27 then falls below 26.5 → reversal, trade against EMA9 direction"], ["از ۲۷ بالا برود سپس زیر ۲۶٫۵ → برگشت، خلاف جهت EMA9"], ["Rare"], ["نادر"], ["EMA9"], ["EMA9"])
_e("zscore", "length=20", ["Standardised distance from the mean — pairs & mean reversion", "Entry ±2, exit 0", "Regime sanity (|z|>3 = event)"],
   ["فاصلهٔ استانداردشده از میانگین — جفت‌ها و بازگشت‌به‌میانگین", "ورود ±۲، خروج ۰", "سلامت رژیم (|z|>۳ = رویداد)"],
   ["Spread z<−2 → long spread; z>+2 → short; exit near 0; stop |z|>3.5"], ["z اسپرد <−۲ → لانگ اسپرد؛ >+۲ → شورت؛ خروج نزدیک ۰؛ استاپ |z|>۳٫۵"],
   ["Trends break z-score logic (non-stationary)"], ["روند منطق z را می‌شکند (نامانا)"], ["Cointegration test", "Hurst"], ["آزمون هم‌انباشتگی", "هرست"])

# ------------------------------------------------------------------ volume
_e("obv", "—", ["Cumulative volume flow confirms trend", "OBV divergence leads price", "OBV breakout before price (accumulation)", "OBV trendline breaks"],
   ["جریان حجم تجمعی روند را تأیید می‌کند", "واگرایی OBV جلوتر از قیمت", "شکست OBV قبل از قیمت (انباشت)", "شکست خط روند OBV"],
   ["Price flat, OBV new high → accumulation, buy breakout", "Price new high, OBV lower high → distribution"], ["قیمت صاف، OBV سقف جدید → انباشت، خرید شکست", "قیمت سقف جدید، OBV سقف پایین‌تر → توزیع"],
   ["One huge-volume bar dominates for a long time", "Meaningless for FX (tick volume)"], ["یک کندل حجم عظیم مدت‌ها غالب می‌ماند", "برای فارکس (حجم تیک) بی‌معنا"], ["Price patterns", "VWAP"], ["الگوهای قیمت", "VWAP"])
_e("ad_line", "—", ["Accumulation/Distribution: where within the range the bar closed × volume", "Divergence", "Trend confirmation"],
   ["انباشت/توزیع: بسته‌شدن در کجای رنج × حجم", "واگرایی", "تأیید روند"], ["A/D rising while price ranges → breakout up likely"], ["A/D صعودی حین رنج قیمت → شکست رو به بالا محتمل"],
   ["Gaps ignored (uses only bar range)"], ["گپ‌ها نادیده (فقط رنج کندل)"], ["OBV", "CMF"], ["OBV", "CMF"])
_e("chaikin_osc", "3/10 EMA of A/D", ["Momentum of A/D line", "Zero cross & divergence"], ["مومنتوم خط A/D", "کراس صفر و واگرایی"],
   ["Crosses above zero while price above MA → buy"], ["از صفر بالا برود وقتی قیمت بالای MA است → خرید"], ["Noisy"], ["نویزی"], ["MA trend"], ["روند MA"])
_e("cmf", "length=20", ["Money flow −1..+1; >0.05 buying pressure, <−0.05 selling", "Breakout confirmation", "Divergence"],
   ["جریان پول −۱..+۱؛ >۰٫۰۵ فشار خرید، <−۰٫۰۵ فروش", "تأیید شکست", "واگرایی"], ["Breakout with CMF>0.1 → valid; with CMF<0 → suspect"], ["شکست با CMF>۰٫۱ → معتبر؛ با CMF<۰ → مشکوک"],
   ["Gaps ignored"], ["گپ نادیده"], ["Donchian", "Patterns"], ["دونچیان", "الگوها"])
_e("mfi", "length=14", ["Volume-weighted RSI: 80/20 extremes", "Divergence (stronger than RSI because volume included)", "Failure swings"],
   ["RSI وزن‌دار حجمی: اکستریم ۸۰/۲۰", "واگرایی (قوی‌تر از RSI چون حجم دارد)", "سوئینگ ناکام"], ["MFI<20 + bullish divergence + reversal candle → long"], ["MFI<۲۰ + واگرایی صعودی + کندل برگشتی → لانگ"],
   ["Useless without real volume"], ["بدون حجم واقعی بی‌فایده"], ["S/R", "Bollinger"], ["حمایت/مقاومت", "بولینگر"])
_e("force_index", "ema=2 (timing) / 13 (trend)", ["Elder: price change × volume", "FI(2) dips below zero in uptrend = pullback buy", "FI(13) sign = who controls", "Divergence"],
   ["الدر: تغییر قیمت × حجم", "FI(2) زیر صفر در روند صعودی = خرید پولبک", "علامت FI(13) = چه کسی کنترل دارد", "واگرایی"],
   ["EMA22 rising + FI(2)<0 → buy next bar above high"], ["EMA22 صعودی + FI(2)<۰ → خرید کندل بعد بالای سقف"], ["Spiky"], ["اسپایکی"], ["Elder Ray", "EMA22"], ["الدر ری", "EMA22"])
_e("eom", "length=14", ["Ease of Movement: how far price moves per unit volume", "Zero cross"], ["سهولت حرکت: قیمت به ازای واحد حجم چقدر می‌رود", "کراس صفر"],
   ["EOM>0 rising → easy advance, hold longs"], ["EOM>۰ صعودی → صعود آسان، لانگ را نگه دارید"], ["Erratic on thin volume"], ["در حجم کم بی‌ثبات"], ["Trend MA"], ["MA روند"])
_e("vpt", "—", ["Volume × % change cumulative; like OBV but scaled", "Divergence"], ["حجم × درصد تغییر تجمعی؛ مانند OBV ولی مقیاس‌شده", "واگرایی"],
   ["VPT confirms breakout with new high"], ["VPT با سقف جدید شکست را تأیید کند"], ["Same as OBV"], ["مانند OBV"], ["OBV"], ["OBV"])
_e("nvi_pvi", "ema=255", ["NVI: smart money (low-volume days); PVI: crowd", "NVI above its 1-year EMA = bull market odds ~95% (Fosback)"],
   ["NVI: پول هوشمند (روزهای کم‌حجم)؛ PVI: جمعیت", "NVI بالای EMA یک‌ساله = احتمال بازار گاوی ~۹۵٪ (فاسبک)"],
   ["NVI crosses above EMA255 → long-term long bias"], ["NVI از EMA255 بالا برود → سوگیری لانگ بلندمدت"], ["Slow; daily only"], ["کند؛ فقط روزانه"], ["Breadth", "SMA200"], ["وسعت", "SMA200"])
_e("klinger", "34/55, signal 13", ["Volume force oscillator; signal cross", "Divergence"], ["نوسانگر نیروی حجم؛ کراس سیگنال", "واگرایی"],
   ["KVO crosses above signal below zero in uptrend → buy"], ["KVO از سیگنال بالا برود زیر صفر در روند صعودی → خرید"], ["Many crosses"], ["کراس زیاد"], ["EMA trend"], ["روند EMA"])
_e("relative_volume", "length=20", ["RVOL = volume ÷ average → conviction", "Breakout filter (RVOL>1.5)", "Scanner ranking", "Low RVOL breakout = fade"],
   ["RVOL = حجم ÷ میانگین → قاطعیت", "فیلتر شکست (RVOL>۱٫۵)", "رتبه‌بندی اسکنر", "شکست با RVOL کم = فید"],
   ["Breakout bar RVOL>2 → follow; RVOL<0.8 → likely false"], ["کندل شکست RVOL>۲ → دنبال کنید؛ RVOL<۰٫۸ → احتمالاً کاذب"], ["Session effects intraday (open always high)"], ["اثر سشن در اینترادی (بازگشایی همیشه بالا)"],
   ["Donchian", "Patterns"], ["دونچیان", "الگوها"])
_e("vwap", "session / anchored", ["Institutional fair value of the session", "Above VWAP = buyers control (intraday bias)", "Pullback entries to VWAP", "Anchored VWAP from swing/earnings/IPO", "Execution benchmark", "VWAP bands (±1/2σ)"],
   ["ارزش منصفانهٔ نهادی سشن", "بالای VWAP = کنترل خریداران (سوگیری اینترادی)", "ورود پولبک به VWAP", "VWAP لنگرشده از سوئینگ/گزارش/IPO", "معیار اجرا", "باند VWAP (±۱/۲σ)"],
   ["Open above VWAP, first pullback holds VWAP → long", "Price rejects anchored VWAP from a major low → resistance flip"], ["بازگشایی بالای VWAP، اولین پولبک VWAP را نگه دارد → لانگ", "قیمت VWAP لنگرشده از کف بزرگ را پس بزند → تبدیل مقاومت"],
   ["Resets each session — meaningless on daily", "Lags late in session"], ["هر سشن ریست می‌شود — در روزانه بی‌معنا", "اواخر سشن کند است"], ["RVOL", "Opening range"], ["RVOL", "رنج بازگشایی"])
_e("volume_profile", "bins=24, lookback=N bars", ["POC / Value Area (70%) = accepted prices", "HVN = support/resistance, LVN = fast moves", "Balanced vs trending profile shape", "Naked POC targets"],
   ["POC / ناحیهٔ ارزش (۷۰٪) = قیمت پذیرفته‌شده", "HVN = حمایت/مقاومت، LVN = حرکت سریع", "شکل پروفایل متعادل/روندی", "هدف POC برهنه"],
   ["Price accepted above VAH (2 closes) → target next HVN", "Rejection at POC + RSI → fade to VAL"], ["پذیرش قیمت بالای VAH (۲ بسته) → هدف HVN بعدی", "پس‌زدن در POC + RSI → فید تا VAL"],
   ["Depends heavily on lookback choice"], ["به انتخاب بازهٔ نگاه بسیار وابسته"], ["VWAP", "Market structure"], ["VWAP", "ساختار بازار"])

# ------------------------------------------------------------------ levels / structure
_e("pivots", "classic / fibonacci / camarilla / woodie (daily→intraday)", ["Intraday S/R map from yesterday's H/L/C", "PP = day bias line", "R1/S1 targets, R2/S2 reversals", "Camarilla H3/L3 fades, H4/L4 breakouts"],
   ["نقشهٔ حمایت/مقاومت اینترادی از H/L/C دیروز", "PP = خط سوگیری روز", "هدف R1/S1، برگشت R2/S2", "کاماریلا فید H3/L3، شکست H4/L4"],
   ["Open above PP, pullback holds PP → long to R1", "Camarilla: reject L3 with reversal candle → long to H3"], ["بازگشایی بالای PP، پولبک PP را نگه دارد → لانگ تا R1", "کاماریلا: پس‌زدن L3 با کندل برگشتی → لانگ تا H3"],
   ["Self-fulfilling only in liquid markets"], ["فقط در بازار نقد خودمحقق‌شونده"], ["VWAP", "RVOL"], ["VWAP", "RVOL"])
_e("fibonacci", "retracement 38.2/50/61.8/78.6; extension 127/161.8/261.8", ["Pullback zones in trends (golden pocket 61.8–65)", "Profit targets via extensions", "Confluence with S/R & MAs", "Time zones (rare)"],
   ["ناحیهٔ پولبک در روند (گلدن‌پاکت ۶۱٫۸–۶۵)", "هدف سود با اکستنشن", "هم‌راستایی با حمایت/مقاومت و MA", "زون زمانی (نادر)"],
   ["Uptrend, retrace to 61.8 + bullish engulfing → long, target 161.8 extension"], ["روند صعودی، اصلاح تا ۶۱٫۸ + انگالفینگ صعودی → لانگ، هدف اکستنشن ۱۶۱٫۸"],
   ["Subjective swing choice; no evidence levels are special — use only with confluence"], ["انتخاب سوئینگ ذهنی؛ شواهدی بر خاص‌بودن سطوح نیست — فقط با هم‌راستایی"], ["S/R", "Candles", "Volume"], ["حمایت/مقاومت", "کندل", "حجم"])
_e("zigzag", "deviation=5% / ATR-based", ["Swing structure (HH/HL vs LH/LL)", "Pattern recognition input (H&S, double tops, Elliott, harmonics)", "Fibonacci anchor points", "Noise removal for analysis"],
   ["ساختار سوئینگ (HH/HL در برابر LH/LL)", "ورودی تشخیص الگو (سروشانه، دوقلو، الیوت، هارمونیک)", "نقاط لنگر فیبوناچی", "حذف نویز برای تحلیل"],
   ["Last swing prints HL after LL sequence → possible trend change; confirm on break of LH"], ["آخرین سوئینگ بعد از توالی LL یک HL بسازد → تغییر روند احتمالی؛ تأیید با شکست LH"],
   ["REPAINTS: last leg is not final until reversal threshold met — never backtest entries on it"], ["ری‌پینت می‌کند: آخرین موج تا رسیدن به آستانه نهایی نیست — هرگز ورود را روی آن بک‌تست نکنید"], ["Market structure", "Fibonacci"], ["ساختار بازار", "فیبوناچی"])
_e("heikin_ashi", "—", ["Smoothed candles show trend persistence", "Colour streaks as trend hold/exit", "Doji HA = pause", "Wickless candles = strong trend"],
   ["کندل هموار پایداری روند را نشان می‌دهد", "رشتهٔ رنگ = نگه‌داشتن/خروج", "دوجی HA = مکث", "کندل بی‌سایه = روند قوی"],
   ["Stay long while HA green with no lower wick; exit on first red with upper wick"], ["تا وقتی HA سبز بدون سایهٔ پایین است لانگ بمانید؛ خروج در اولین قرمز با سایهٔ بالا"],
   ["HA close ≠ real price — always execute off real candles"], ["بستهٔ HA ≠ قیمت واقعی — همیشه با کندل واقعی اجرا کنید"], ["ATR stop", "EMA"], ["استاپ ATR", "EMA"])
_e("rs_vs", "benchmark (BTC / SPX / sector), length=50", ["Relative strength line vs benchmark (O'Neil RS)", "Buy leaders (RS line new high before price)", "Rotation & pairs"],
   ["خط قدرت نسبی در برابر بنچمارک (RS اونیل)", "خرید رهبران (RS سقف جدید قبل از قیمت)", "چرخش و جفت"],
   ["Market pulls back but RS line rises → leader, buy the breakout"], ["بازار اصلاح کند ولی خط RS بالا برود → رهبر، شکست را بخرید"], ["Benchmark choice matters"], ["انتخاب بنچمارک مهم است"], ["Breakout", "Volume"], ["شکست", "حجم"])

# ------------------------------------------------------------------ new catalog entries for functions that had none
NEW_CATALOG = [
    dict(key="bb_percent_b", group="Volatility", name_en="Bollinger %B", name_fa="درصد B بولینگر",
         how_en="(close − lower band) ÷ (upper − lower): 0 at lower band, 1 at upper.", how_fa="(بسته − باند پایین) ÷ (بالا − پایین): ۰ در باند پایین، ۱ در بالا.",
         read_en="Normalised band position; >1 = outside upper band; usable in screeners and as ML feature.", read_fa="موقعیت نرمال‌شده در باند؛ >۱ بیرون باند بالا؛ برای اسکنر و ویژگی ML."),
    dict(key="momentum", group="Momentum", name_en="Momentum (price difference)", name_fa="مومنتوم (اختلاف قیمت)",
         how_en="close − close[n].", how_fa="بسته − بستهٔ n کندل قبل.", read_en="Zero cross = trend change; slope = acceleration.", read_fa="کراس صفر = تغییر روند؛ شیب = شتاب."),
    dict(key="stdev_bands", group="Volatility", name_en="Standard-deviation bands (generic)", name_fa="باند انحراف معیار (عمومی)",
         how_en="Any MA ± k·σ of price.", how_fa="هر MA ± k·σ قیمت.", read_en="Same reading as Bollinger; use with EMA/HMA centres.", read_fa="مانند بولینگر؛ با مرکز EMA/HMA."),
    dict(key="lin_reg_channel", group="Trend", name_en="Linear regression channel", name_fa="کانال رگرسیون خطی",
         how_en="Least-squares line over N bars ± 2σ of residuals.", how_fa="خط حداقل مربعات روی N کندل ± ۲σ باقیمانده‌ها.",
         read_en="Slope = trend; touches of ±2σ = stretched; break of channel = regime change.", read_fa="شیب = روند؛ لمس ±۲σ = کشیده؛ شکست کانال = تغییر رژیم."),
    dict(key="williams_ad", group="Volume", name_en="Williams Accumulation/Distribution", name_fa="انباشت/توزیع ویلیامز",
         how_en="Cumulative true-range-based buying/selling pressure (no volume).", how_fa="فشار خرید/فروش تجمعی بر پایهٔ رنج واقعی (بدون حجم).",
         read_en="Divergence vs price; works on FX where volume is unreliable.", read_fa="واگرایی با قیمت؛ در فارکس که حجم نامعتبر است کار می‌کند."),
    dict(key="percent_rank", group="Momentum", name_en="Percent rank", name_fa="رتبهٔ درصدی",
         how_en="Percentile of today's value within the last N values.", how_fa="صدک مقدار امروز در N مقدار اخیر.",
         read_en="Component of Connors RSI; >90 / <10 extremes.", read_fa="جزء Connors RSI؛ اکستریم >۹۰ / <۱۰."),
    dict(key="swing_points", group="Levels", name_en="Swing highs / lows (fractals)", name_fa="سوئینگ‌های سقف/کف (فراکتال)",
         how_en="Bar with the highest high (lowest low) among k bars each side.", how_fa="کندلی که بالاترین سقف (پایین‌ترین کف) بین k کندل هر طرف است.",
         read_en="Structure (HH/HL), stop placement beyond last swing, breakout triggers (Williams fractals).", read_fa="ساختار (HH/HL)، استاپ پشت آخرین سوئینگ، تریگر شکست (فراکتال ویلیامز)."),
    dict(key="true_range", group="Volatility", name_en="True Range", name_fa="رنج واقعی",
         how_en="max(high−low, |high−prev close|, |low−prev close|).", how_fa="بیشینهٔ (سقف−کف، |سقف−بستهٔ قبل|، |کف−بستهٔ قبل|).",
         read_en="Raw volatility per bar incl. gaps; ATR is its average.", read_fa="نوسان خام هر کندل شامل گپ؛ ATR میانگین آن است."),
    dict(key="candle_anatomy", group="Levels", name_en="Candle anatomy (body, wicks, range)", name_fa="آناتومی کندل (بدنه، سایه‌ها، رنج)",
         how_en="body=|close−open|, upper wick, lower wick, range; ratios to ATR.", how_fa="بدنه=|بسته−باز|، سایهٔ بالا، سایهٔ پایین، رنج؛ نسبت به ATR.",
         read_en="Pin bars (wick ≥ 2× body), marubozu (no wicks), doji (body < 10 % range) — the raw material of Nison patterns.", read_fa="پین‌بار (سایه ≥ ۲ برابر بدنه)، ماروبوزو (بی‌سایه)، دوجی (بدنه < ۱۰٪ رنج) — مادهٔ خام الگوهای نیسون."),
]
_e("bb_percent_b", "length=20, std=2", ["Screener: %B<0 oversold list", "ML feature", "Divergence of %B vs price"], ["اسکنر: لیست %B<۰", "ویژگی ML", "واگرایی %B با قیمت"],
   ["%B<0 then back above 0 in uptrend → buy"], ["%B<۰ سپس بالای ۰ در روند صعودی → خرید"], ["Same as Bollinger"], ["مانند بولینگر"], ["RSI"], ["RSI"])
_e("momentum", "length=10", ["Simple trend/acceleration gauge", "Zero cross"], ["سنجهٔ سادهٔ روند/شتاب", "کراس صفر"], ["Crosses above 0 with rising slope → buy"], ["از ۰ بالا برود با شیب صعودی → خرید"],
   ["Unbounded, price-scale dependent (use ROC to compare)"], ["بی‌کران و وابسته به مقیاس قیمت (برای مقایسه از ROC)"], ["MA"], ["MA"])
_e("stdev_bands", "length=20, k=2", ["Custom bands on any MA"], ["باند دلخواه روی هر MA"], ["As Bollinger"], ["مانند بولینگر"], ["As Bollinger"], ["مانند بولینگر"], ["RSI"], ["RSI"])
_e("lin_reg_channel", "length=100, k=2", ["Trend channel & slope", "Mean-reversion inside channel", "Breakout on channel exit"], ["کانال و شیب روند", "بازگشت‌به‌میانگین داخل کانال", "شکست با خروج از کانال"],
   ["Touch −2σ in rising channel → long to midline"], ["لمس −۲σ در کانال صعودی → لانگ تا خط میانی"], ["Redraws as window moves"], ["با حرکت پنجره بازترسیم می‌شود"], ["RSI", "Volume"], ["RSI", "حجم"])
_e("williams_ad", "—", ["FX-friendly accumulation gauge", "Divergence"], ["سنجهٔ انباشت مناسب فارکس", "واگرایی"], ["Price lower low, WAD higher low → bullish divergence"], ["قیمت کف پایین‌تر، WAD کف بالاتر → واگرایی صعودی"],
   ["Slow"], ["کند"], ["S/R"], ["حمایت/مقاومت"])
_e("percent_rank", "length=100", ["Normalise any series to 0–100"], ["نرمال‌سازی هر سری به ۰–۱۰۰"], ["PR of ROC>95 → extended"], ["PR مربوط به ROC>۹۵ → کشیده"], ["Window length matters"], ["طول پنجره مهم است"], ["Connors RSI"], ["Connors RSI"])
_e("swing_points", "k=2 (fractal) / 5 (major)", ["Market structure", "Stop placement", "Fractal breakout (Williams)", "Pattern vertices"], ["ساختار بازار", "جای استاپ", "شکست فراکتال (ویلیامز)", "رئوس الگو"],
   ["Break of last swing high with Alligator open → buy"], ["شکست آخرین سوئینگ سقف با الیگیتور باز → خرید"], ["Confirmed only k bars later (lag)"], ["فقط k کندل بعد تأیید می‌شود (تأخیر)"], ["Alligator", "Volume"], ["الیگیتور", "حجم"])
_e("true_range", "—", ["Gap-aware volatility per bar"], ["نوسان هر کندل با احتساب گپ"], ["TR > 3× ATR → event bar, wait"], ["TR > ۳ برابر ATR → کندل رویداد، صبر کنید"], ["Single-bar noise"], ["نویز تک‌کندلی"], ["ATR"], ["ATR"])
_e("candle_anatomy", "pin: wick≥2×body; doji: body<10% range", ["Pattern building blocks", "Rejection detection at levels", "Conviction (marubozu with volume)"],
   ["اجزای سازندهٔ الگو", "تشخیص پس‌زدن در سطوح", "قاطعیت (ماروبوزو با حجم)"], ["Pin bar at support in uptrend + RVOL>1.2 → long above pin high"],
   ["پین‌بار در حمایت در روند صعودی + RVOL>۱٫۲ → لانگ بالای سقف پین"], ["Meaningless without location (level/trend)"], ["بدون موقعیت (سطح/روند) بی‌معنا"], ["S/R", "Volume", "Trend"], ["حمایت/مقاومت", "حجم", "روند"])


def full_catalog():
    """INDICATOR_CATALOG + NEW_CATALOG merged with usage sheets."""
    from core.indicators2 import INDICATOR_CATALOG
    out = []
    for d in list(INDICATOR_CATALOG) + NEW_CATALOG:
        e = dict(d); e.update(U.get(d["key"], {}))
        out.append(e)
    return out


def coverage():
    """(n_total, n_with_usage) — used by tests"""
    c = full_catalog()
    return len(c), sum(1 for d in c if "uses_en" in d)
