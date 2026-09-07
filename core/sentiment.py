"""
News / social sentiment desk (Phase 11 — FinBERT, VADER, TextBlob, Flair, Stanza, financial LLMs).

What we learned from each and what is implemented:

  VADER (Hutto & Gilbert)  → rule-based lexicon with *valence intensities*, booster words ("very", "extremely"),
                             negation window (3 tokens), "but" clause re-weighting, punctuation/caps emphasis, and the
                             compound score = Σ/√(Σ²+15).                                    → `vader_like()` (full rules)
  Loughran–McDonald (the finance lexicon behind most "FinBERT-before-BERT" work) → generic lexicons mislabel finance
                             words ("liability", "tax", "cost" are not negative in filings; "crude", "gross" aren't bad).
                             We embed an LM-style domain lexicon + finance boosters ("beats", "misses", "guidance cut",
                             "downgrade", "record high").                                    → `FIN_LEXICON`
  TextBlob                 → polarity ∈[-1,1] & subjectivity ∈[0,1]; subjectivity matters: opinion ≠ fact.
                                                                                              → `subjectivity()`
  FinBERT / Flair / Stanza / LLMs → context models: entity-aware ("AAPL up, MSFT down" → per-ticker), aspect & sarcasm.
                             Optional backend: if `transformers` is installed and the model is cached, `ProsusAI/finbert`
                             is used and blended (see `transformer_backend()`); otherwise the lexicon engine runs alone.
                             Per-ticker attribution is implemented rule-based: sentiment of the clause nearest a ticker.
  Research consensus (Tetlock 2007; Bollen 2011 replication failures): headline sentiment has weak, short-lived
  predictive power; it is *most useful as a regime/risk input* (crowded bullishness → reduce size). The desk therefore
  outputs an "attention & extremity" index and feeds Elder's 6% / psychology gates, not a buy signal.
"""
import re
import math
import numpy as np

# ------------------------------------------------------------------ lexicons (compact, domain-specific)
FIN_LEXICON = {
    # positive
    "beat": 2.0, "beats": 2.0, "surge": 2.5, "surges": 2.5, "soar": 2.5, "soars": 2.5, "rally": 2.0, "rallies": 2.0, "record": 1.5,
    "upgrade": 2.2, "upgraded": 2.2, "outperform": 2.0, "bullish": 2.5, "breakout": 1.8, "gain": 1.5, "gains": 1.5, "profit": 1.5,
    "profits": 1.5, "growth": 1.5, "strong": 1.5, "buy": 1.2, "accumulate": 1.2, "recover": 1.5, "recovery": 1.5, "rebound": 1.8,
    "approval": 1.8, "approved": 1.8, "partnership": 1.2, "dividend": 1.0, "buyback": 1.5, "raises": 1.5, "raised": 1.5, "optimistic": 1.8,
    "momentum": 0.8, "support": 0.6, "adoption": 1.2, "etf approval": 2.5, "halving": 0.8, "all-time high": 2.5, "ath": 2.0, "moon": 1.5,
    "green": 0.8, "pump": 1.0, "long": 0.5, "undervalued": 1.5, "beat expectations": 2.5, "guidance raised": 2.5, "positive": 1.5,
    # negative
    "miss": -2.0, "misses": -2.0, "missed": -2.0, "plunge": -2.8, "plunges": -2.8, "crash": -3.0, "crashes": -3.0, "tumble": -2.2,
    "tumbles": -2.2, "slump": -2.0, "downgrade": -2.2, "downgraded": -2.2, "underperform": -2.0, "bearish": -2.5, "breakdown": -1.8,
    "loss": -1.5, "losses": -1.8, "decline": -1.2, "declines": -1.2, "weak": -1.5, "sell": -1.2, "selloff": -2.2, "sell-off": -2.2,
    "lawsuit": -1.8, "probe": -1.5, "investigation": -1.5, "fraud": -3.0, "hack": -2.5, "hacked": -2.5, "exploit": -2.2, "bankruptcy": -3.0,
    "default": -2.2, "layoffs": -1.5, "cuts": -1.2, "cut": -1.0, "guidance cut": -2.8, "warning": -1.8, "warns": -1.8, "recession": -2.0,
    "inflation": -0.8, "rate hike": -1.2, "hawkish": -1.2, "dovish": 1.0, "tariff": -1.0, "tariffs": -1.0, "sanction": -1.2, "ban": -1.8,
    "banned": -1.8, "delist": -2.5, "delisted": -2.5, "liquidation": -2.0, "liquidations": -2.0, "fear": -1.5, "panic": -2.5, "red": -0.8,
    "dump": -1.5, "short": -0.5, "overvalued": -1.5, "bubble": -1.8, "negative": -1.5, "risk": -0.6, "volatile": -0.6, "sec": -0.5,
    "rug": -3.0, "scam": -3.0, "exit scam": -3.5,
}
# words generic lexicons call negative but are neutral in finance (Loughran–McDonald insight)
FIN_NEUTRAL = {"liability", "liabilities", "tax", "taxes", "cost", "costs", "crude", "gross", "capital", "debt", "vice", "mine", "mining"}
BOOSTERS = {"very": 0.293, "extremely": 0.293, "hugely": 0.293, "massively": 0.293, "sharply": 0.293, "significantly": 0.2, "strongly": 0.2,
            "slightly": -0.293, "marginally": -0.293, "somewhat": -0.293, "barely": -0.293, "modestly": -0.2}
NEGATIONS = {"not", "no", "never", "n't", "without", "hardly", "neither", "nor", "fails", "fail", "failed", "isn't", "wasn't", "won't", "doesn't", "didn't"}
SUBJECTIVE = {"think", "believe", "feel", "seems", "likely", "probably", "maybe", "could", "might", "expect", "hope", "fear", "opinion", "should", "imo", "bullish", "bearish", "moon", "dump"}

STOPCAPS = {"THE", "AND", "FOR", "CEO", "SEC", "ETF", "USD", "USDT", "FED", "GDP", "CPI", "AI", "US", "UK", "EU", "IPO", "ATH", "IMO", "NEW", "ALL", "NOT", "BUY", "SELL", "HOLD", "NOW", "TODAY", "BIG"}
TICKER_RE = re.compile(r"\$?\b([A-Z]{2,6})\b|\$([a-z]{2,6})\b")


def _tokens(text):
    t = text.replace("n't", " n't")
    return re.findall(r"[A-Za-z][A-Za-z'\-]*|[!?]+|\d+(?:\.\d+)?%?", t)


def vader_like(text):
    """VADER algorithm with the finance lexicon. returns dict(compound, pos, neg, neu, hits)"""
    raw = text
    toks = _tokens(text)
    low = [w.lower() for w in toks]
    n = len(low)
    # multi-word phrases first
    joined = " ".join(low)
    phrase_scores = []
    for ph, val in FIN_LEXICON.items():
        if " " in ph and ph in joined:
            phrase_scores.append((ph, val))
            joined = joined.replace(ph, " ")
    scores = []
    hits = []
    caps_diff = sum(1 for w in toks if w.isupper() and len(w) > 1) not in (0, sum(1 for w in toks if len(w) > 1))
    i = 0
    for i, w in enumerate(low):
        if w in FIN_NEUTRAL or w not in FIN_LEXICON or " " in w:
            continue
        v = FIN_LEXICON[w]
        # caps emphasis (only when text is mixed case)
        if caps_diff and toks[i].isupper() and len(toks[i]) > 1:
            v += 0.733 if v > 0 else -0.733
        # boosters within 3 tokens before, with distance decay (VADER: 1.0, 0.95, 0.9)
        for d in (1, 2, 3):
            j = i - d
            if j >= 0 and low[j] in BOOSTERS:
                b = BOOSTERS[low[j]] * (1.0, 0.95, 0.9)[d - 1]
                v += b if v > 0 else -b
        # negation within 3 tokens before → flip and scale by 0.74
        if any(low[i - d] in NEGATIONS for d in (1, 2, 3) if i - d >= 0):
            v *= -0.74
        scores.append(v); hits.append((w, round(v, 2)))
    for ph, val in phrase_scores:
        scores.append(val); hits.append((ph, val))
    # "but" rule: what comes after "but" weighs more (VADER: before ×0.5, after ×1.5)
    if "but" in low and scores:
        bi = low.index("but")
        adj = []
        for (w, v), sc in zip(hits, scores):
            pos = low.index(w.split()[0]) if w.split()[0] in low else bi
            adj.append(sc * (0.5 if pos < bi else 1.5))
        scores = adj
    total = float(sum(scores))
    # punctuation emphasis
    ex = min(raw.count("!"), 4) * 0.292
    qm = raw.count("?"); qm_amp = 0.18 * qm if 1 < qm <= 3 else (0.96 if qm > 3 else 0)
    if total > 0:
        total += ex + qm_amp
    elif total < 0:
        total -= ex + qm_amp
    compound = total / math.sqrt(total * total + 15) if total else 0.0
    pos = sum(s for s in scores if s > 0); neg = -sum(s for s in scores if s < 0); neu = max(n - len(scores), 0)
    tot = pos + neg + neu or 1
    return dict(compound=float(compound), pos=pos / tot, neg=neg / tot, neu=neu / tot, hits=hits)


def subjectivity(text):
    """TextBlob-style subjectivity proxy: share of opinion/modal words + exclamation density"""
    low = [w.lower() for w in _tokens(text)]
    if not low:
        return 0.0
    s = sum(1 for w in low if w in SUBJECTIVE) / len(low) * 4 + min(text.count("!"), 3) * 0.1
    return float(min(1.0, s))


def per_ticker(text):
    """entity-aware sentiment: split into clauses, score each, attribute to tickers mentioned in that clause"""
    clauses = re.split(r"[;,.]| but | while | whereas | however ", text)
    out = {}
    for cl in clauses:
        tks = {m.group(1) or m.group(2).upper() for m in TICKER_RE.finditer(cl)}
        tks = {t_ for t_ in tks if t_.lower() not in FIN_LEXICON and t_ not in STOPCAPS}
        if not tks:
            continue
        sc = vader_like(cl)["compound"]
        for tk in tks:
            out.setdefault(tk, []).append(sc)
    return {k: float(np.mean(v)) for k, v in out.items()}


def transformer_backend():
    """returns a callable(text)->(label, score) using FinBERT if transformers + cached weights are available, else None"""
    try:
        import os
        if os.environ.get("PROTRADER_NO_TRANSFORMERS"):
            return None
        from transformers import pipeline  # noqa
        p = pipeline("text-classification", model="ProsusAI/finbert", top_k=None, truncation=True)
        def run(text):
            res = p(text[:512])[0]
            d = {r["label"]: r["score"] for r in res}
            return d.get("positive", 0) - d.get("negative", 0), d
        return run
    except Exception:
        return None


def score_headlines(headlines, backend=None):
    """list[str] → DataFrame(text, compound, subjectivity, tickers, finbert) + aggregate index"""
    import pandas as pd
    rows = []
    for h in headlines:
        v = vader_like(h)
        fb = None
        if backend:
            try:
                fb = backend(h)[0]
            except Exception:
                fb = None
        rows.append(dict(text=h, compound=v["compound"], subjectivity=subjectivity(h), tickers=per_ticker(h), hits=v["hits"], finbert=fb))
    df = pd.DataFrame(rows)
    if len(df) == 0:
        return df, {}
    comp = df["finbert"].fillna(df["compound"]) if backend else df["compound"]
    agg = dict(mean=float(comp.mean()), share_pos=float((comp > 0.05).mean()), share_neg=float((comp < -0.05).mean()),
               extremity=float(np.mean(np.abs(comp))), subjectivity=float(df["subjectivity"].mean()), n=int(len(df)))
    # crowd-extremity flag (Kahneman/Taleb/Douglas): unanimous, emotional, subjective → contrarian risk flag
    agg["crowded"] = (agg["share_pos"] > 0.8 or agg["share_neg"] > 0.8) and agg["extremity"] > 0.4 and agg["subjectivity"] > 0.3
    agg["regime"] = "euphoric" if agg["mean"] > 0.4 and agg["crowded"] else ("panic" if agg["mean"] < -0.4 and agg["crowded"] else
                    ("positive" if agg["mean"] > 0.1 else ("negative" if agg["mean"] < -0.1 else "neutral")))
    return df, agg


def fetch_headlines(symbol, limit=40):
    """RSS-based headline fetcher (Google News + CoinDesk/Yahoo) — no API key. Returns list[str] (may be empty offline)."""
    import requests
    import xml.etree.ElementTree as ET
    q = symbol.split("/")[0].split(" (")[-1].rstrip(")") if "(" in symbol else symbol.split("/")[0]
    urls = [f"https://news.google.com/rss/search?q={q}+stock+OR+crypto+OR+price&hl=en-US&gl=US&ceid=US:en"]
    if "USDT" in symbol or "USD" in symbol and "/" in symbol:
        urls.append("https://www.coindesk.com/arc/outboundfeeds/rss/")
    out = []
    for u in urls:
        try:
            r = requests.get(u, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
            root = ET.fromstring(r.content)
            for it in root.iter("item"):
                t = it.findtext("title")
                if t:
                    out.append(t.strip())
        except Exception:
            continue
        if len(out) >= limit:
            break
    return out[:limit]
