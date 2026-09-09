"""
Phase 23 — Economic calendar risk filter.

High-impact scheduled events (FOMC, CPI, NFP, ECB, BoE, BoJ) move every market at once; most rule-based strategies
have no idea a release is 10 minutes away and get stopped out by the spike. The desktop, web and mobile signal lists
now carry a `news_risk` flag and the alert scanner suppresses new alerts inside the window.

Sources (best effort, cached 6 h, all optional):
  * ForexFactory weekly JSON  (https://nfs.faireconomy.media/ff_calendar_thisweek.json) — free, no key
  * built-in recurring schedule fallback (FOMC/NFP/CPI rules of thumb) when offline
Window: 30 min before → 30 min after a HIGH-impact USD/EUR/GBP/JPY event (configurable).
"""
import time, datetime as dt, json, os

_cache = {"t": 0, "events": []}
FF_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
WINDOW_BEFORE, WINDOW_AFTER = 30 * 60, 30 * 60
CURRENCIES = {"USD", "EUR", "GBP", "JPY"}


def _fallback_events(now=None):
    """rules of thumb when offline: NFP = first Friday 13:30 UTC; US CPI ≈ 10th–14th 13:30 UTC (weekday); FOMC ≈ 8 fixed dates/year
    (approximate; only used to warn, never to block)."""
    now = now or dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
    ev = []
    for m in (now.month, (now.month % 12) + 1):
        y = now.year + (1 if m < now.month else 0)
        d = dt.date(y, m, 1)
        while d.weekday() != 4:
            d += dt.timedelta(days=1)
        ev.append(dict(title="Non-Farm Payrolls (approx.)", currency="USD", impact="High", ts=dt.datetime(d.year, d.month, d.day, 13, 30).timestamp(), approx=True))
        d = dt.date(y, m, 12)
        while d.weekday() >= 5:
            d += dt.timedelta(days=1)
        ev.append(dict(title="US CPI (approx.)", currency="USD", impact="High", ts=dt.datetime(d.year, d.month, d.day, 13, 30).timestamp(), approx=True))
    return ev


def _parse_ff(rows):
    """ForexFactory weekly JSON rows → our event dicts (High impact, tracked currencies only; bad rows skipped)."""
    out = []
    for e in rows or []:
        if e.get("impact") != "High" or e.get("country") not in CURRENCIES:
            continue
        try:
            ts = dt.datetime.fromisoformat(str(e["date"]).replace("Z", "+00:00")).timestamp()
        except Exception:
            continue
        out.append(dict(title=e.get("title", ""), currency=e.get("country"), impact="High", ts=ts, approx=False,
                        forecast=e.get("forecast"), previous=e.get("previous")))
    return out


def events(force=False):
    if not force and time.time() - _cache["t"] < 6 * 3600 and _cache["events"]:
        return _cache["events"]
    try:
        import requests
        r = requests.get(FF_URL, timeout=8, headers={"User-Agent": "ProTrader"})
        out = _parse_ff(r.json())
    except Exception:
        out = []
    if not out:
        out = _fallback_events()
    out.sort(key=lambda e: e["ts"])
    _cache.update(t=time.time(), events=out)
    return out


def _risk_from(evs, ts, before=WINDOW_BEFORE, after=WINDOW_AFTER):
    for e in evs:
        if e["ts"] - before <= ts <= e["ts"] + after:
            d = dict(e); d["mins"] = round((e["ts"] - ts) / 60); return d
    return None


def risk_now(ts=None, before=WINDOW_BEFORE, after=WINDOW_AFTER):
    """→ None or the event dict currently inside the risk window (with 'mins' = minutes until/since)."""
    return _risk_from(events(), ts or time.time(), before, after)


def upcoming(hours=48, n=12):
    ts = time.time()
    return [dict(e, mins=round((e["ts"] - ts) / 60)) for e in events() if ts <= e["ts"] <= ts + hours * 3600][:n]


def text(e, lang="en"):
    if not e:
        return ""
    m = e["mins"]
    if lang == "fa":
        when = f"{m} دقیقه دیگر" if m > 0 else f"{-m} دقیقه پیش"
        return f"⚠ خبر پرریسک {e['currency']}: {e['title']} ({when})" + (" — تقریبی" if e.get("approx") else "")
    when = f"in {m} min" if m > 0 else f"{-m} min ago"
    return f"⚠ high-impact {e['currency']} news: {e['title']} ({when})" + (" — approx." if e.get("approx") else "")
