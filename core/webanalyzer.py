"""
Web page analyzer for trading sites.
Give it a URL → fetches page → extracts:
  • title / description / headings / outline
  • instruments mentioned (crypto, forex, metals, indices, stocks) — also from URL (TradingView, Binance, Yahoo...)
  • indicators & trading concepts mentioned → mapped to built-in strategies
  • explicit trading rules (sentences with entry/exit/stop/target language)
  • price levels & numbers near instruments
  • sentiment (bullish vs bearish vocabulary)
  • site capabilities ("what does this site offer for trading")
  • red flags (scam / unrealistic promise language)
Then the UI runs the built-in strategies on detected instruments for live signals.
"""
import re
import json
from dataclasses import dataclass, field, asdict
from urllib.parse import urlparse, unquote
import requests

try:
    from bs4 import BeautifulSoup
except Exception:  # pragma: no cover
    BeautifulSoup = None

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36",
      "Accept-Language": "en,fa;q=0.8"}

# ---------------------------------------------------------------- knowledge tables
INSTRUMENTS = {
    # name in our UNIVERSE : regex alternatives
    "BTC/USDT": r"\b(btc|bitcoin|btcusd[t]?|xbt)\b|بیت\s?کوین",
    "ETH/USDT": r"\b(eth|ethereum|ethusd[t]?)\b|اتریوم",
    "SOL/USDT": r"\b(solana|solusd[t]?|\$sol)\b|سولانا",
    "BNB/USDT": r"\b(bnb|binance coin|bnbusd[t]?)\b",
    "XRP/USDT": r"\b(xrp|ripple|xrpusd[t]?)\b|ریپل",
    "ADA/USDT": r"\b(cardano|adausd[t]?|\$ada)\b|کاردانو",
    "DOGE/USDT": r"\b(doge|dogecoin|dogeusd[t]?)\b|دوج",
    "AVAX/USDT": r"\b(avax|avalanche)\b",
    "LINK/USDT": r"\b(chainlink|linkusd[t]?|\$link)\b",
    "DOT/USDT": r"\b(polkadot|dotusd[t]?|\$dot)\b",
    "TON/USDT": r"\b(toncoin|tonusd[t]?|\$ton)\b",
    "LTC/USDT": r"\b(ltc|litecoin)\b",
    "EUR/USD": r"\b(eur\s?/?\s?usd|eurusd|euro dollar|fiber)\b|یورو\s?دلار",
    "GBP/USD": r"\b(gbp\s?/?\s?usd|gbpusd|cable)\b|پوند\s?دلار",
    "USD/JPY": r"\b(usd\s?/?\s?jpy|usdjpy)\b|دلار\s?ین",
    "USD/CHF": r"\b(usd\s?/?\s?chf|usdchf)\b",
    "AUD/USD": r"\b(aud\s?/?\s?usd|audusd|aussie)\b",
    "USD/CAD": r"\b(usd\s?/?\s?cad|usdcad|loonie)\b",
    "NZD/USD": r"\b(nzd\s?/?\s?usd|nzdusd|kiwi)\b",
    "EUR/GBP": r"\b(eur\s?/?\s?gbp|eurgbp)\b",
    "EUR/JPY": r"\b(eur\s?/?\s?jpy|eurjpy)\b",
    "GBP/JPY": r"\b(gbp\s?/?\s?jpy|gbpjpy)\b",
    "DXY": r"\b(dxy|dollar index)\b|شاخص\s?دلار",
    "Gold (XAU/USD)": r"\b(xau\s?/?\s?usd|xauusd|gold|gc=f)\b|طلا|انس",
    "Silver (XAG/USD)": r"\b(xag\s?/?\s?usd|xagusd|silver)\b|نقره",
    "Crude Oil (WTI)": r"\b(wti|crude oil|usoil|cl=f)\b|نفت",
    "Brent Oil": r"\b(brent|ukoil)\b|برنت",
    "Natural Gas": r"\b(natural gas|natgas|ng=f)\b|گاز طبیعی",
    "Copper": r"\b(copper|hg=f)\b|مس\b",
    "S&P 500": r"\b(s&p\s?500|spx|spy|es=f|us500|sp500)\b|اس\s?اند\s?پی",
    "Nasdaq 100": r"\b(nasdaq|ndx|qqq|nq=f|us100|nas100)\b|نزدک",
    "Dow Jones": r"\b(dow jones|djia|dji|us30|ym=f)\b|داوجونز",
    "DAX": r"\b(dax|ger40|de40)\b|داکس",
    "FTSE 100": r"\b(ftse|uk100)\b",
    "Nikkei 225": r"\b(nikkei|jp225)\b",
    "VIX": r"\b(vix|volatility index)\b",
    "Apple (AAPL)": r"\b(aapl|apple)\b|اپل",
    "Microsoft (MSFT)": r"\b(msft|microsoft)\b|مایکروسافت",
    "NVIDIA (NVDA)": r"\b(nvda|nvidia)\b|انویدیا",
    "Tesla (TSLA)": r"\b(tsla|tesla)\b|تسلا",
    "Amazon (AMZN)": r"\b(amzn|amazon)\b|آمازون",
    "Google (GOOGL)": r"\b(googl|alphabet inc|google stock)\b|سهام گوگل",
    "Meta (META)": r"\b(meta platforms|\$meta|nasdaq:\s?meta|facebook stock)\b",
    "AMD": r"\b(amd)\b",
    "Coinbase (COIN)": r"\b(coinbase|\$coin|nasdaq:\s?coin)\b",
    "MicroStrategy (MSTR)": r"\b(mstr|microstrategy)\b",
}

# concept -> (labels regex, mapped strategy ids)
CONCEPTS = {
    "RSI": (r"\brsi\b|relative strength index|آر\s?اس\s?آی", ["rsi_reversal", "rsi2", "rsi_div", "triple_rsi"]),
    "MACD": (r"\bmacd\b|مکدی", ["macd_trend"]),
    "Moving Average": (r"\b(ema|sma|moving average|golden cross|death cross|ma\s?\d{2,3})\b|میانگین متحرک|مووینگ", ["ema_cross", "triple_ema", "golden_cross", "hull"]),
    "Bollinger Bands": (r"bollinger|بولینگر", ["bb_bounce", "bb_squeeze"]),
    "Stochastic": (r"stochastic|استوکاستیک", ["stoch_rsi", "anti"]),
    "ADX / DMI": (r"\badx\b|directional movement|\bdmi\b", ["adx_dmi", "holy_grail", "supertrend"]),
    "Ichimoku": (r"ichimoku|kumo|tenkan|kijun|ایچیموکو", ["ichimoku"]),
    "Supertrend": (r"supertrend|سوپرترند", ["supertrend"]),
    "Parabolic SAR": (r"parabolic|\bsar\b|پارابولیک", ["psar"]),
    "VWAP": (r"\bvwap\b", ["vwap"]),
    "Volume / OBV / MFI": (r"\bobv\b|on.balance volume|money flow|\bmfi\b|volume profile|حجم", ["obv_trend", "mfi"]),
    "ATR / Volatility": (r"\batr\b|average true range|volatility breakout|squeeze|keltner", ["bb_squeeze", "lw_vol_breakout", "nr7"]),
    "Donchian / Turtle": (r"donchian|turtle|لاک.?پشت", ["turtle"]),
    "Fibonacci": (r"fibonacci|\bfib\b|golden pocket|\bote\b|فیبوناچی", ["fib_pullback"]),
    "Support / Resistance": (r"support|resistance|key level|حمایت|مقاومت", ["sr_breakout_retest"]),
    "Breakout": (r"break\s?out|شکست", ["turtle", "inside_bar", "orb", "nr7", "false_breakout"]),
    "Pin Bar / Candlesticks": (r"pin ?bar|hammer|doji|engulfing|shooting star|morning star|evening star|candlestick|پین.?بار|کندل", ["pinbar", "engulfing", "morning_evening_star"]),
    "Inside Bar": (r"inside bar|اینساید", ["inside_bar"]),
    "Divergence": (r"divergen|واگرایی", ["rsi_div"]),
    "Supply & Demand": (r"supply|demand|عرضه|تقاضا", ["supply_demand"]),
    "Order Block": (r"order ?block|\bob\b|اوردر.?بلاک|اردر.?بلاک", ["ict_ob"]),
    "Fair Value Gap": (r"fair value gap|\bfvg\b|imbalance|گپ ارزش|اف.?وی.?جی", ["ict_fvg", "silver_bullet"]),
    "Liquidity / Stop Hunt": (r"liquidity|stop ?hunt|sweep|turtle soup|نقدینگی|استاپ هانت", ["liquidity_sweep", "silver_bullet"]),
    "Market Structure (BOS/CHoCH)": (r"\bbos\b|choch|market structure|break of structure|higher high|lower low|ساختار بازار", ["market_structure", "ict_ob"]),
    "ICT / Smart Money": (r"\bict\b|smart money|\bsmc\b|inner circle|kill ?zone|silver bullet|power of three|\bamd\b|judas|اسمارت مانی|پول هوشمند", ["ict_fvg", "ict_ob", "silver_bullet", "po3", "liquidity_sweep"]),
    "Wyckoff": (r"wyckoff|accumulation|distribution|spring|upthrust|وایکوف", ["wyckoff_spring"]),
    "Elliott Wave": (r"elliott|wave count|impulse wave|الیوت", []),
    "Harmonic Patterns": (r"harmonic|gartley|bat pattern|butterfly|crab|هارمونیک", []),
    "Chart Patterns": (r"head and shoulders|double top|double bottom|triangle|flag|wedge|cup and handle|سر و شانه|مثلث|پرچم", ["sr_breakout_retest", "inside_bar"]),
    "Mean Reversion": (r"mean reversion|oversold|overbought|اشباع", ["rsi_reversal", "bb_bounce", "ibs", "rsi2"]),
    "Trend Following": (r"trend following|trend trading|ride the trend|روندگیری|روند", ["ema_cross", "supertrend", "turtle", "holy_grail"]),
    "Scalping": (r"scalp|اسکالپ", ["vwap", "orb", "silver_bullet"]),
    "Swing Trading": (r"swing trad|سوئینگ", ["holy_grail", "pinbar", "fib_pullback"]),
    "Day Trading / Sessions": (r"day trad|intraday|opening range|london session|new york session|asian session|سشن", ["orb", "silver_bullet", "po3", "vwap"]),
    "Seasonality / Calendar": (r"seasonal|turnaround tuesday|day of week|monthly effect|فصلی", ["turnaround_tuesday"]),
    "Risk Management": (r"risk management|position siz|risk.reward|r:r|stop.?loss|take.?profit|drawdown|مدیریت ریسک|حد ضرر|حد سود", []),
    "Options": (r"\boptions?\b|covered call|put|call spread|theta|wheel strategy|آپشن", []),
    "Fundamental / News": (r"fundamental|earnings|cpi|fomc|interest rate|nfp|inflation|فاندامنتال|نرخ بهره|تورم", []),
    "On-chain": (r"on.chain|whale|exchange inflow|mvrv|nupl|hash ?rate", []),
    "Algo / Bots": (r"algorithm|\bbot\b|automated|pine ?script|backtest|expert advisor|\bea\b|ربات|بک.?تست", []),
    "Copy / Signals": (r"copy trad|signal group|vip signal|telegram signal|سیگنال", []),
    "Prop Firm": (r"prop firm|funded account|ftmo|challenge|پراپ", []),
}

CAPABILITIES = {
    "Charts": r"chart|candlestick|tradingview|چارت|نمودار",
    "Screener / Scanner": r"screener|scanner|اسکرینر|اسکنر",
    "Backtesting": r"backtest|strategy tester|بک.?تست",
    "Paper trading": r"paper trad|demo account|دمو",
    "Live trading / Broker": r"open account|deposit|withdraw|leverage|margin|spread|commission|broker|exchange|افتتاح حساب|واریز|برداشت|اهرم|کارگزار|صرافی",
    "API": r"\bapi\b|websocket|rest api",
    "Education / Courses": r"course|academy|tutorial|lesson|webinar|ebook|دوره|آموزش|آکادمی",
    "Signals": r"signal|alert|سیگنال|هشدار",
    "News / Calendar": r"economic calendar|news feed|breaking|تقویم اقتصادی|اخبار",
    "Community / Ideas": r"community|forum|ideas|comment|discussion|انجمن|ایده",
    "Copy trading": r"copy trad|social trad|کپی ترید",
    "Bots / Automation": r"\bbot|automation|grid|dca bot|ربات",
    "Indicators library": r"indicator|pine script|اندیکاتور",
    "Portfolio / Journal": r"portfolio|journal|tracker|پرتفوی|ژورنال",
    "Mobile app": r"app store|google play|ios app|android app|اپلیکیشن",
    "Prop / Funded": r"funded|prop firm|challenge|payout",
}

RED_FLAGS = {
    "Guaranteed profit language": r"guarantee[d]?\s+(\d+%\s+)?(profit|return|income|gain|win)|risk.?free|no risk|100% (win|accuracy|profit)|never lose|سود تضمینی|بدون ریسک|صد درصد",
    "Unrealistic returns": r"\b(\d{3,4})\s?%\s?(per|a|/)\s?(day|week|month)|double your money|10x in|daily profit|سود روزانه|روزی\s?\d+\s?درصد",
    "Urgency / pressure": r"limited (time|spots|seats)|act now|last chance|only \d+ (spots|seats) left|hurry|فرصت محدود|همین حالا",
    "Pay for signals / VIP": r"vip\s+(telegram\s+)?(signal|group|channel)|premium signals|join (our|my) (vip\s+)?telegram|paid signals|سیگنال vip|کانال vip",
    "Recruit / MLM": r"referral bonus|invite friends and earn|affiliate|mlm|multi.?level|زیرمجموعه|کد معرف",
    "Ask for deposit to you personally": r"send (btc|usdt|crypto) to|wallet address|deposit to this|واریز به این آدرس|ارسال به کیف پول",
    "Anonymous / no regulation": r"unregulated|offshore|no kyc|no verification|بدون احراز هویت",
}

BULLISH = r"\b(bullish|buy|long|breakout|rally|uptrend|higher high|support holds|accumulate|moon|pump|upside|bottom is in)\b|صعودی|خرید|رشد|بالا"
BEARISH = r"\b(bearish|sell|short|breakdown|dump|downtrend|lower low|resistance holds|distribution|crash|downside|top is in)\b|نزولی|فروش|ریزش|سقوط|پایین"

RULE_HINT = r"\b(buy|sell|long|short|enter|entry|exit|stop.?loss|take.?profit|target|when|if|above|below|cross|breaks?|close[sd]? (above|below)|retest|confirm)\b|خرید|فروش|ورود|خروج|حد ضرر|حد سود|هدف|وقتی|اگر|بالای|زیر|شکست|تأیید|تایید"

PRICE_RE = r"(?<![\w.])\$?\s?(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+\.\d{2,6}|\d{4,6})(?![\w.])"


@dataclass
class PageAnalysis:
    url: str = ""
    domain: str = ""
    title: str = ""
    description: str = ""
    lang: str = ""
    word_count: int = 0
    headings: list = field(default_factory=list)
    instruments: list = field(default_factory=list)      # [(name, count)]
    url_symbol: str = ""
    concepts: list = field(default_factory=list)         # [(concept, count, [strategy_ids])]
    rules: list = field(default_factory=list)            # sentences
    prices: list = field(default_factory=list)           # [(instrument, [levels])]
    sentiment: dict = field(default_factory=dict)        # {bull, bear, score}
    capabilities: list = field(default_factory=list)     # [(cap, count)]
    red_flags: list = field(default_factory=list)        # [(flag, example)]
    trust_score: int = 100
    timeframes: list = field(default_factory=list)
    links: list = field(default_factory=list)            # (text, href) internal trading links
    text_preview: str = ""
    error: str = ""

    def to_dict(self):
        return asdict(self)


# ---------------------------------------------------------------- helpers
def _clean(t: str) -> str:
    t = re.sub(r"[ \t\r\f\v]+", " ", t)
    t = re.sub(r"\n\s*\n+", "\n", t)
    return t.strip()


def _symbol_from_url(url: str) -> str:
    u = unquote(url).lower()
    m = re.search(r"tradingview\.com/(?:symbols|chart)/[^/]*?([a-z]{2,10}[:_-]?[a-z0-9]{2,12})", u)
    cand = ""
    if m:
        cand = m.group(1).split(":")[-1].split("-")[-1]
    m2 = re.search(r"(?:symbol|pair|ticker|s|q)=([a-z0-9:._-]{2,15})", u)
    if m2:
        cand = m2.group(1).split(":")[-1]
    m3 = re.search(r"(?:binance|bybit|okx|kucoin|coinbase)\.com/.*?/([a-z]{2,6})[_-]?(usdt|usd|busd|btc)", u)
    if m3:
        cand = m3.group(1) + m3.group(2)
    m4 = re.search(r"finance\.yahoo\.com/quote/([a-z0-9^=.-]+)", u)
    if m4:
        cand = m4.group(1)
    m5 = re.search(r"coinmarketcap\.com/currencies/([a-z-]+)|coingecko\.com/(?:en/)?coins/([a-z-]+)", u)
    if m5:
        cand = (m5.group(1) or m5.group(2) or "").replace("-", " ")
    return cand


def _match_instruments(text: str) -> list:
    out = []
    low = text.lower()
    for name, rx in INSTRUMENTS.items():
        n = len(re.findall(rx, low, flags=re.I))
        if n:
            out.append((name, n))
    # de-dup noisy generic words: "gold" also hits "golden cross" rarely — fine
    out.sort(key=lambda x: -x[1])
    return out


def _sentences(text: str) -> list:
    parts = re.split(r"(?<=[.!?؟])\s+|\n+|•|\u2022|-\s(?=[A-Z])", text)
    return [p.strip() for p in parts if 25 <= len(p.strip()) <= 320]


def analyze_text(text: str, url: str = "", title: str = "", description: str = "", headings=None, links=None) -> PageAnalysis:
    pa = PageAnalysis(url=url, domain=urlparse(url).netloc.replace("www.", "") if url else "", title=title, description=description)
    text = _clean(text)
    low = text.lower()
    pa.word_count = len(text.split())
    pa.lang = "fa" if len(re.findall(r"[\u0600-\u06FF]", text)) > len(text) * 0.15 else "en"
    pa.headings = (headings or [])[:25]
    pa.links = (links or [])[:30]
    pa.text_preview = text[:1500]
    pa.url_symbol = _symbol_from_url(url) if url else ""
    # instruments (URL symbol boosted)
    inst = _match_instruments(text + " " + pa.url_symbol * 3 + " " + title * 2)
    pa.instruments = inst[:12]
    # concepts
    conc = []
    for c, (rx, sids) in CONCEPTS.items():
        n = len(re.findall(rx, low, flags=re.I))
        if n:
            conc.append((c, n, sids))
    conc.sort(key=lambda x: -x[1])
    pa.concepts = conc
    # rules
    rules = []
    for s in _sentences(text):
        hits = len(re.findall(RULE_HINT, s, flags=re.I))
        if hits >= 2 and re.search(r"\d|above|below|cross|break|بالای|زیر|شکست", s, flags=re.I):
            rules.append(s)
        if len(rules) >= 25:
            break
    pa.rules = rules
    # prices near instruments
    prices = []
    for name, _ in pa.instruments[:5]:
        rx = INSTRUMENTS[name]
        lv = set()
        for m in re.finditer(rx, low, flags=re.I):
            window = text[max(0, m.start() - 120): m.end() + 160]
            for pm in re.finditer(PRICE_RE, window):
                try:
                    v = float(pm.group(1).replace(",", ""))
                    if 0.0001 < v < 10_000_000 and not (1900 <= v <= 2100 and v == int(v)):
                        lv.add(v)
                except Exception:
                    pass
        if lv:
            prices.append((name, sorted(lv)[:12]))
    pa.prices = prices
    # sentiment
    bull = len(re.findall(BULLISH, low, flags=re.I))
    bear = len(re.findall(BEARISH, low, flags=re.I))
    tot = bull + bear
    pa.sentiment = {"bull": bull, "bear": bear, "score": round((bull - bear) / tot, 2) if tot else 0.0}
    # capabilities
    caps = []
    for c, rx in CAPABILITIES.items():
        n = len(re.findall(rx, low, flags=re.I))
        if n:
            caps.append((c, n))
    caps.sort(key=lambda x: -x[1])
    pa.capabilities = caps
    # red flags
    flags = []
    for f, rx in RED_FLAGS.items():
        m = re.search(rx, text, flags=re.I)
        if m:
            s = text[max(0, m.start() - 60): m.end() + 60].replace("\n", " ")
            flags.append((f, "…" + s + "…"))
    pa.red_flags = flags
    penalty = {"Guaranteed profit language": 35, "Unrealistic returns": 30, "Ask for deposit to you personally": 40,
               "Pay for signals / VIP": 15, "Urgency / pressure": 10, "Recruit / MLM": 15, "Anonymous / no regulation": 15}
    pa.trust_score = max(0, 100 - sum(penalty.get(f, 10) for f, _ in flags))
    # timeframes
    tfs = re.findall(r"\b(\d{1,3})\s?-?\s?(min|minute|m|h|hour|hr|d|day|daily|w|week|weekly)\b", low)
    norm = []
    for n, u in tfs:
        u = u[0]
        key = {"m": "m", "h": "h", "d": "d", "w": "wk"}.get(u, u)
        s = f"{n}{key}" if key != "d" or n != "1" else "1d"
        if s in ("1m", "5m", "15m", "30m", "1h", "4h", "1d", "1wk", "2h", "12h", "3m"):
            norm.append(s)
    from collections import Counter
    pa.timeframes = [k for k, _ in Counter(norm).most_common(5)]
    return pa


def fetch(url: str, timeout: int = 20) -> tuple:
    """Return (text, title, description, headings, links)."""
    if not url.lower().startswith(("http://", "https://")):
        url = "https://" + url
    r = requests.get(url, headers=UA, timeout=timeout, allow_redirects=True)
    r.raise_for_status()
    ctype = r.headers.get("content-type", "")
    html = r.text
    if BeautifulSoup is None or "json" in ctype:
        return _clean(re.sub(r"<[^>]+>", " ", html)), "", "", [], []
    soup = BeautifulSoup(html, "lxml") if "lxml" in globals() or True else BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg", "iframe", "form", "nav", "footer"]):
        tag.decompose()
    title = (soup.title.string if soup.title and soup.title.string else "").strip()
    og = soup.find("meta", property="og:title")
    if og and og.get("content"):
        title = title or og["content"]
    desc = ""
    for sel in ({"name": "description"}, {"property": "og:description"}, {"name": "twitter:description"}):
        m = soup.find("meta", attrs=sel)
        if m and m.get("content"):
            desc = m["content"].strip()
            break
    headings = [h.get_text(" ", strip=True) for h in soup.find_all(["h1", "h2", "h3"]) if h.get_text(strip=True)]
    links = []
    base = urlparse(url).netloc
    for a in soup.find_all("a", href=True):
        txt = a.get_text(" ", strip=True)
        href = a["href"]
        if 3 <= len(txt) <= 80 and re.search(r"strateg|indicator|signal|chart|analysis|idea|course|academy|screener|backtest|market|crypto|forex|stock|استراتژی|اندیکاتور|سیگنال|تحلیل|آموزش", txt + href, flags=re.I):
            if href.startswith("/"):
                href = f"https://{base}{href}"
            links.append((txt, href))
    # main text: prefer article/main
    main = soup.find("article") or soup.find("main") or soup.body or soup
    text = main.get_text("\n", strip=True)
    if len(text) < 400:
        text = soup.get_text("\n", strip=True)
    return _clean(text), title, desc, headings, links


BLOCK_RX = r"bot verification|just a moment|access denied|enable javascript|cloudflare|captcha|verify you are human|403 forbidden"


def fetch_via_reader(url: str, timeout: int = 30) -> tuple:
    """Fallback: r.jina.ai renders JS pages & bypasses many bot walls, returns markdown."""
    if not url.lower().startswith(("http://", "https://")):
        url = "https://" + url
    r = requests.get("https://r.jina.ai/" + url, headers={"Accept": "text/plain", "X-Return-Format": "markdown"}, timeout=timeout)
    r.raise_for_status()
    md = r.text
    title = ""
    m = re.match(r"Title:\s*(.+)", md)
    if m:
        title = m.group(1).strip()
    headings = re.findall(r"^#{1,3}\s+(.+)$", md, flags=re.M)
    links = [(t, h) for t, h in re.findall(r"\[([^\]]{3,80})\]\((https?://[^)\s]+)\)", md)
             if re.search(r"strateg|indicator|signal|chart|analysis|idea|course|academy|screener|backtest", t + h, flags=re.I)]
    body = re.sub(r"^(Title|URL Source|Published Time|Markdown Content):.*$", "", md, flags=re.M)
    body = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", body)
    body = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", body)
    return _clean(body), title, "", headings, links


def analyze_url(url: str) -> PageAnalysis:
    try:
        text, title, desc, headings, links = fetch(url)
        if len(text.split()) < 80 or re.search(BLOCK_RX, (title + " " + text[:600]), flags=re.I):
            try:
                text2, title2, desc2, h2, l2 = fetch_via_reader(url)
                if len(text2.split()) > len(text.split()):
                    text, title, desc, headings, links = text2, title2 or title, desc2 or desc, h2 or headings, l2 or links
            except Exception:
                pass
    except Exception as e:
        try:
            text, title, desc, headings, links = fetch_via_reader(url)
            return analyze_text(text, url, title, desc, headings, links)
        except Exception:
            pass
        pa = PageAnalysis(url=url, domain=urlparse(url if "://" in url else "https://" + url).netloc.replace("www.", ""))
        pa.error = f"{type(e).__name__}: {e}"
        # still try URL-only inference
        pa.url_symbol = _symbol_from_url(url)
        pa.instruments = _match_instruments(pa.url_symbol + " " + unquote(url).replace("-", " ").replace("_", " "))
        return pa
    return analyze_text(text, url, title, desc, headings, links)


def filter_levels(pa: PageAnalysis, live_prices: dict) -> PageAnalysis:
    """Keep only levels within a plausible band (0.4x–2.5x) of the instrument's current price."""
    out = []
    for name, lv in pa.prices:
        px = live_prices.get(name)
        if px:
            lv = [v for v in lv if 0.4 * px <= v <= 2.5 * px]
        if lv:
            out.append((name, lv))
    pa.prices = out
    return pa


def to_markdown(pa: PageAnalysis, lang="en") -> str:
    fa = lang == "fa"
    L = (lambda en, f: f if fa else en)
    lines = [f"# {L('Trading Page Analysis', 'تحلیل صفحه تریدینگ')}: {pa.title or pa.domain}", f"**URL:** {pa.url}", ""]
    if pa.error:
        lines += [f"> ⚠️ {L('Fetch error', 'خطای دریافت')}: {pa.error}", ""]
    if pa.description:
        lines += [f"_{pa.description}_", ""]
    lines += [f"**{L('Words', 'کلمات')}:** {pa.word_count} · **{L('Language', 'زبان')}:** {pa.lang} · **{L('Trust score', 'امتیاز اعتماد')}:** {pa.trust_score}/100", ""]
    if pa.instruments:
        lines += [f"## {L('Instruments mentioned', 'نمادهای ذکرشده')}", ", ".join(f"{n} (×{c})" for n, c in pa.instruments), ""]
    if pa.concepts:
        lines += [f"## {L('Concepts & indicators', 'مفاهیم و اندیکاتورها')}"]
        lines += [f"- **{c}** ×{n}" + (f" → {', '.join(s)}" if s else "") for c, n, s in pa.concepts]
        lines.append("")
    if pa.capabilities:
        lines += [f"## {L('What this site offers for trading', 'این سایت برای ترید چه دارد')}", ", ".join(f"{c} (×{n})" for c, n in pa.capabilities), ""]
    if pa.rules:
        lines += [f"## {L('Extracted trading rules', 'قوانین معاملاتی استخراج‌شده')}"] + [f"- {r}" for r in pa.rules] + [""]
    if pa.prices:
        lines += [f"## {L('Price levels', 'سطوح قیمتی')}"] + [f"- {n}: {', '.join(f'{v:,.6g}' for v in lv)}" for n, lv in pa.prices] + [""]
    s = pa.sentiment
    lines += [f"## {L('Sentiment', 'احساسات')}", f"{L('Bullish', 'صعودی')} {s.get('bull', 0)} · {L('Bearish', 'نزولی')} {s.get('bear', 0)} · score {s.get('score', 0):+.2f}", ""]
    if pa.red_flags:
        lines += [f"## 🚩 {L('Red flags', 'پرچم‌های قرمز')}"] + [f"- **{f}**: {ex}" for f, ex in pa.red_flags] + [""]
    return "\n".join(lines)
