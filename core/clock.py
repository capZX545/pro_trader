"""Time helpers (Phase 17): data is stored in UTC; the UI shows the computer's local clock (exact system timezone)
plus UTC in the header. `to_local()` converts naive-UTC timestamps for display; `fmt()` formats them."""
import datetime as _dt
import pandas as pd


def system_tz():
    return _dt.datetime.now().astimezone().tzinfo


def tz_name():
    tz = system_tz()
    now = _dt.datetime.now(tz)
    off = now.utcoffset() or _dt.timedelta(0)
    sign = "+" if off >= _dt.timedelta(0) else "−"
    off = abs(off); h, m = divmod(int(off.total_seconds()) // 60, 60)
    return f"{now.tzname() or 'local'} (UTC{sign}{h:02d}:{m:02d})"


def display_mode():
    """'local' (default) or 'utc' from settings.json."""
    try:
        import json
        from core.paths import data as _data
        return json.load(open(_data("settings.json"))).get("chart_tz", "local")
    except Exception:
        return "local"


def to_local(ts):
    """naive UTC pandas Timestamp / DatetimeIndex → naive local time (or unchanged if mode is 'utc')."""
    if display_mode() == "utc":
        return ts
    try:
        if isinstance(ts, pd.DatetimeIndex):
            return ts.tz_localize("UTC").tz_convert(system_tz()).tz_localize(None)
        t = pd.Timestamp(ts)
        if t.tzinfo is None:
            t = t.tz_localize("UTC")
        return t.tz_convert(system_tz()).tz_localize(None)
    except Exception:
        return ts


def fmt(ts, f="%Y-%m-%d %H:%M"):
    return pd.Timestamp(to_local(ts)).strftime(f)


def now_strings():
    """(local 'HH:MM:SS  YYYY-MM-DD', 'UTC HH:MM:SS')"""
    loc = _dt.datetime.now(system_tz()); utc = _dt.datetime.now(_dt.timezone.utc)
    return loc.strftime("%H:%M:%S"), loc.strftime("%Y-%m-%d"), utc.strftime("%H:%M:%S")


WORLD = [("NY", "America/New_York"), ("LDN", "Europe/London"), ("FRA", "Europe/Berlin"), ("THR", "Asia/Tehran"), ("DXB", "Asia/Dubai"),
         ("TYO", "Asia/Tokyo"), ("SYD", "Australia/Sydney")]


def world_line(items=None):
    """'UTC 12:00 · NY 08:00 · LDN 13:00 · …' for the top-corner world clock (session opens are marked with •)."""
    try:
        from zoneinfo import ZoneInfo
    except Exception:
        return "UTC " + _dt.datetime.now(_dt.timezone.utc).strftime("%H:%M")
    now = _dt.datetime.now(_dt.timezone.utc)
    parts = ["UTC " + now.strftime("%H:%M")]
    for name, tz in (items or WORLD):
        try:
            lt = now.astimezone(ZoneInfo(tz))
            open_ = 8 <= lt.hour < 17 and lt.weekday() < 5
            parts.append(f"{name} {lt.strftime('%H:%M')}{'•' if open_ else ''}")
        except Exception:
            pass
    return " · ".join(parts)
