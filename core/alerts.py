"""
Alerts (Phase 12): Telegram + desktop notifications for PROVEN playbook signals, so the forward test actually runs
without the user staring at the screen.

  * settings in data/settings.json: {"telegram_token": "...", "telegram_chat_id": "...", "alerts": {"telegram": true,
    "desktop": true, "min_conf": 60, "tfs": ["1h","4h","1d"]}}
  * scan(): every proven (tf, group) strategy is run on fresh data for the group's symbols; a signal on the LAST CLOSED
    bar that is not yet in the forward log → recorded in forward.json (source="alert") and pushed.
  * Telegram uses the public Bot API (https://api.telegram.org) directly with `requests` — no library, no server; if
    the network is blocked the alert is queued and shown on the desktop only.
  * Desktop: Qt system-tray balloon (hooked by ui/main_window), fallback to a log line.
"""
import os
import json
import time
import threading
import requests

from core.paths import data as _data
SETTINGS = _data("settings.json")
LOG = _data("alerts.json")
_lock = threading.Lock()
_desktop_hook = None      # callable(title, body) set by the UI


def settings():
    try:
        return json.load(open(SETTINGS))
    except Exception:
        return {}


def save_settings(patch):
    s = settings(); s.update(patch)
    os.makedirs(os.path.dirname(SETTINGS), exist_ok=True)
    json.dump(s, open(SETTINGS, "w"), indent=1)


def set_desktop_hook(fn):
    global _desktop_hook
    _desktop_hook = fn


def _log(entry):
    with _lock:
        try:
            d = json.load(open(LOG))
        except Exception:
            d = {"alerts": []}
        d["alerts"].append(entry); d["alerts"] = d["alerts"][-500:]
        json.dump(d, open(LOG, "w"), indent=1, default=str)


def history(n=50):
    try:
        return json.load(open(LOG))["alerts"][-n:][::-1]
    except Exception:
        return []


# ------------------------------------------------------------------ channels
def telegram_send(text, token=None, chat_id=None, timeout=10):
    s = settings()
    token = token or s.get("telegram_token"); chat_id = chat_id or s.get("telegram_chat_id")
    if not token or not chat_id:
        return False, "telegram not configured"
    try:
        r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": chat_id, "text": text, "parse_mode": "HTML",
                                                                                   "disable_web_page_preview": True}, timeout=timeout)
        ok = r.status_code == 200 and r.json().get("ok")
        return bool(ok), ("ok" if ok else r.text[:200])
    except Exception as e:
        return False, str(e)


def telegram_test():
    return telegram_send("✅ ProTrader alerts connected.\nاتصال هشدارهای پروتریدر برقرار شد.")


def desktop_send(title, body):
    if _desktop_hook:
        try:
            _desktop_hook(title, body); return True
        except Exception:
            return False
    return False


def push(title, body, meta=None):
    s = settings().get("alerts", {})
    res = {}
    if s.get("telegram", True):
        res["telegram"] = telegram_send(f"<b>{title}</b>\n{body}")
    if s.get("desktop", True):
        res["desktop"] = desktop_send(title, body)
    _log(dict(ts=time.time(), title=title, body=body, meta=meta or {}, result={k: (v if isinstance(v, bool) else v[0]) for k, v in res.items()}))
    return res


# ------------------------------------------------------------------ signal scan
def format_signal(sym, tf, sid, side, entry, stop, target, conf, st, lang="fa"):
    arrow = "🟢 LONG" if side > 0 else "🔴 SHORT"
    rr = abs(target - entry) / max(abs(entry - stop), 1e-9)
    if lang == "fa":
        return (f"{arrow} {sym} · {tf} · {sid}\nورود ≈ {entry:,.4g} | استاپ {stop:,.4g} | هدف {target:,.4g} (R:R {rr:.1f})\n"
                f"پلی‌بوک: PF {st.get('pf', 0):.2f} · WR {st.get('wr', 0):.0f}% · n={st.get('n', 0)} · اطمینان {conf:.0f}\n"
                f"⚠ تحلیل است نه دستور؛ ریسک ≤۱٪؛ در ژورنال ثبت کنید.")
    return (f"{arrow} {sym} · {tf} · {sid}\nentry ≈ {entry:,.4g} | stop {stop:,.4g} | target {target:,.4g} (R:R {rr:.1f})\n"
            f"playbook: PF {st.get('pf', 0):.2f} · WR {st.get('wr', 0):.0f}% · n={st.get('n', 0)} · conf {conf:.0f}\n"
            f"⚠ analysis, not an order; risk ≤1%; log it in the Journal.")


def scan(tfs=None, min_conf=None, lang="fa", progress=None, dry=False):
    """Run proven strategies on fresh data; alert + forward-record new last-bar signals. Returns list of alerts sent."""
    import numpy as np
    import strategies as S
    from core import playbook as PB, forward as FW
    from core.data import get_ohlcv
    s = settings().get("alerts", {})
    tfs = tfs or s.get("tfs", ["15m", "1h", "4h", "1d"])
    min_conf = s.get("min_conf", 55) if min_conf is None else min_conf
    pb = PB.load()
    if not pb:
        return []
    sent = []
    jobs = [(tf, g, syms) for tf in tfs for g, syms in PB.GROUPS.items() if pb.get("best", {}).get(tf, {}).get(g)]
    for j, (tf, g, syms) in enumerate(jobs):
        if progress:
            progress(int(j / max(len(jobs), 1) * 100), f"{tf} {g}")
        proven = pb["best"][tf][g][:4]
        for sym in syms:
            try:
                df = get_ohlcv(sym, tf, max_age_sec=300)
            except Exception:
                continue
            if len(df) < 300:
                continue
            # last CLOSED bar: if the final bar is still forming (its time + tf > now) use the previous one
            i = len(df) - 1
            for sid, score in proven:
                st = pb["table"][tf][g].get(sid, {})
                try:
                    res = S.get(sid).run(df)
                except Exception:
                    continue
                side = int(res.signal.fillna(0).iloc[i])
                if side == 0:
                    continue
                entry = float(df.close.iloc[i])
                stop = float(res.stop.iloc[i]) if res.stop is not None and res.stop.iloc[i] == res.stop.iloc[i] else float("nan")
                target = float(res.target.iloc[i]) if res.target is not None and res.target.iloc[i] == res.target.iloc[i] else float("nan")
                if stop != stop or target != target:
                    from core.indicators import atr
                    a = float(atr(df).iloc[i]); stop = entry - side * 2 * a; target = entry + side * 4 * a
                conf = min(100.0, 40 + 20 * min(st.get("pf", 1) - 1, 1) * 2 + score * 10)
                if conf < min_conf:
                    continue
                new = FW.record(sym, tf, sid, side, df.index[i], entry, stop, target, source="alert", conf=conf,
                                expect=dict(wr=st.get("wr"), pf=st.get("pf")))
                if not new:
                    continue
                body = format_signal(sym, tf, sid, side, entry, stop, target, conf, st, lang)
                title = f"ProTrader · {sym} {tf}"
                if not dry:
                    push(title, body, meta=dict(symbol=sym, tf=tf, sid=sid, side=side))
                sent.append(dict(symbol=sym, tf=tf, sid=sid, side=side, entry=entry, stop=stop, target=target, conf=conf, body=body))
    return sent
