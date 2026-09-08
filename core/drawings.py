"""Persistent chart drawings (TradingView-style tools): per symbol|tf list of dicts stored in data/drawings.json.
Each drawing: {"type": "trend"|"ray"|"hline"|"vline"|"rect"|"fib"|"text"|"measure", "pts": [[ts_iso, price], ...], "text": str, "color": str}.
Points are stored as (UTC timestamp, price) — not bar index — so they survive new bars, timeframe reloads and app restarts."""
import json, os
from core.paths import data as _data

PATH = _data("drawings.json")


def load_all():
    try:
        return json.load(open(PATH))
    except Exception:
        return {}


def load(sym, tf):
    return load_all().get(f"{sym}|{tf}", [])


def save(sym, tf, items):
    d = load_all()
    d[f"{sym}|{tf}"] = items
    os.makedirs(os.path.dirname(PATH), exist_ok=True)
    tmp = PATH + ".tmp"
    json.dump(d, open(tmp, "w"), indent=0)
    os.replace(tmp, PATH)
