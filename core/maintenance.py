"""
Background maintenance — the bot keeps itself healthy without being asked.

Runs in a daemon thread started by main.py:
  • every 15 min : forward-test outcomes update (cheap, cached data)
  • every 6 h    : quick health check → auto-applies SAFE fixes (validate missing strategies, update forward)
  • every 7 days : full playbook rebuild (edge decay / new strategies), only when idle and if data reachable
  • on start     : if playbook is missing or > 14 days old, rebuild in background
All actions and their results are appended to data/maintenance.log so the Health page can show what was done.
"""
import os
import time
import threading
import traceback

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
from core.paths import data as _data
LOG = _data("maintenance.log")
STATE = {"running": False, "last": {}, "current": None, "progress": 0}
_stop = threading.Event()
_ui_busy_until = [0.0]     # UI sets this when the user launches something heavy → training yields
START_DELAY = int(os.environ.get("PROTRADER_TRAIN_DELAY", "90"))   # seconds after launch before self-training starts
THROTTLE = float(os.environ.get("PROTRADER_TRAIN_THROTTLE", "0.35"))  # fraction of time the trainer sleeps (0 = full speed)


def ui_busy(seconds=20):
    """Called by the UI when the user starts a backtest/scan: background training pauses for `seconds`."""
    _ui_busy_until[0] = max(_ui_busy_until[0], time.time() + seconds)


def _lower_priority():
    """Make the whole process background-friendly on Windows/Unix and stop numeric libs from grabbing every core."""
    try:
        if os.name == "nt":
            import ctypes
            BELOW_NORMAL = 0x00004000
            ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), BELOW_NORMAL)
            # and the calling (maintenance) thread itself to lowest
            ctypes.windll.kernel32.SetThreadPriority(ctypes.windll.kernel32.GetCurrentThread(), -2)
        else:
            os.nice(10)
    except Exception:
        pass


def yield_cpu():
    """Cooperative throttle called between strategies/symbols by long tasks: sleeps proportionally to the work
    just done (THROTTLE) and waits while the UI is busy. Returns False if stop requested."""
    if _stop.is_set():
        return False
    now = time.time()
    last = STATE.get("_y", now)
    worked = max(now - last, 0.0)
    if THROTTLE > 0 and worked > 0:
        _stop.wait(min(worked * THROTTLE / (1 - THROTTLE), 2.0))
    while time.time() < _ui_busy_until[0] and not _stop.is_set():
        _stop.wait(0.5)
    STATE["_y"] = time.time()
    return not _stop.is_set()


def log(msg):
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    line = time.strftime("%Y-%m-%d %H:%M:%S") + "  " + msg
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")
    return line


def tail(n=40):
    if not os.path.exists(LOG):
        return []
    with open(LOG, encoding="utf-8") as f:
        return f.readlines()[-n:]


def _run(name, fn):
    STATE["current"] = name
    t0 = time.time()
    try:
        r = fn()
        STATE["last"][name] = time.time(); STATE["_files_changed"] = True
        log(f"{name}: ok ({time.time() - t0:.0f}s) {r if r is not None else ''}")
    except Exception as e:
        log(f"{name}: FAILED {e}")
    finally:
        STATE["current"] = None


def task_forward():
    from core import forward as FW
    r = FW.update()
    try:
        from core import alerts as AL
        sent = AL.scan()
        if sent:
            log(f"alerts: {len(sent)} new signal(s) pushed")
    except Exception as e:
        log(f"alerts error: {e}")
    # Iran Gold signals scan
    try:
        from core import iran_gold
        prices = iran_gold.get_all_live_prices()
        if prices:
            log(f"iran_gold: {len(prices)} symbols updated")
    except Exception as e:
        log(f"iran_gold error: {e}")
    # Resilient network health
    try:
        from core import resilient
        health = resilient.health_check()
        failed = [k for k,v in health.items() if not v]
        if failed:
            log(f"resilient: failed hosts {failed} - anti-filter will retry with mirrors")
        else:
            log(f"resilient: all hosts OK - anti-filter active")
    except Exception as e:
        log(f"resilient health error: {e}")
    return r

def task_iran_gold():
    """Update Iran Gold prices and generate OHLCV caches"""
    try:
        from core import iran_gold
        prices = iran_gold.get_all_live_prices()
        # Pre-cache OHLCV for major Iran Gold symbols
        for sym in ["طلای 18 عیار / 750", "سکه امامی", "دلار آزاد"][:2]:
            try:
                iran_gold.get_ohlcv_iran_gold(sym, "1d", limit=500)
                iran_gold.get_ohlcv_iran_gold(sym, "1h", limit=500)
            except Exception:
                pass
        return f"iran_gold updated {len(prices)} symbols"
    except Exception as e:
        return f"iran_gold failed: {e}"

def task_resilient_check():
    """Check and log resilient network status"""
    try:
        from core import resilient
        health = resilient.health_check(verbose=False)
        proxy = resilient.detect_system_proxy()
        return f"resilient: proxy={proxy}, health={health}"
    except Exception as e:
        return f"resilient check failed: {e}"

def task_auto_evolution_quick():
    """Quick auto-evolution check"""
    try:
        from core import auto_evolution
        # Just run performance analysis quickly
        from core.auto_evolution import _task_analyze_performance
        result = _task_analyze_performance()
        return f"evolution: {result}"
    except Exception as e:
        return f"evolution quick failed: {e}"


def task_health_autofix():
    from core import health as H
    fs = H.run_checks(quick=True)
    done = []
    for f in fs:
        # only SAFE auto-fixes (validation of new strategies, forward update); playbook rebuild handled separately
        if f.fix and f.area in ("validation", "forward"):
            try:
                f.fix(); done.append(f.area)
            except Exception as e:
                log(f"autofix {f.area} failed: {e}")
    return dict(findings=len(fs), fixed=done)


def _prog(stage):
    def f(p, m):
        yield_cpu()
        STATE["progress"] = p; STATE["stage"] = stage; STATE["detail"] = m
    return f


def task_audit():
    from core import audit as A
    import strategies as S
    if A.load() and (time.time() - A.load().get("ts", 0)) < 30 * 86400:
        return "audit fresh"
    A.run_all(S.ALL_STRATEGIES, progress=_prog("audit"))
    return "audited"


def task_playbook_quick():
    """stage 1 of self-training: 1d/4h/1h on 6 symbols per group (~30 min) → app is useful within the first hour"""
    from core import playbook as PB
    import strategies as S
    os.environ["PB_MAX_SYMS"] = "6"
    try:
        PB.build_playbook(S.ALL_STRATEGIES, progress=_prog("playbook-quick"), tfs=["1d", "4h", "1h"], resume=False)
    finally:
        os.environ.pop("PB_MAX_SYMS", None)
    return "quick playbook"


def task_success_rates():
    """Phase 19: fill core/success.py for the default universe so every signal shows its measured success % on first run."""
    from core import success as SR
    SR.precompute(progress=lambda p, m: STATE.update(progress=p, detail=f"success-rates {m}"), stop=_stop.is_set)
    return "success rates"


def task_playbook():
    """stage 2: full universe, all timeframes (hours; resumable per timeframe)"""
    from core import playbook as PB
    import strategies as S
    PB.build_playbook(S.ALL_STRATEGIES, progress=_prog("playbook-full"),
                      tfs=["1d", "4h", "1h", "15m", "30m", "2h", "12h", "5m", "6h", "1wk", "3d", "3m", "1m"])
    return "rebuilt"


_ts_cache = {"t": 0.0, "pb": None, "a": None}


def training_status():
    """for the Dashboard: what the bot is doing to itself right now (playbook/audit files re-read at most every 60 s)"""
    from core import playbook as PB, audit as A
    now = time.time()
    if now - _ts_cache["t"] > 60 or STATE.get("_files_changed"):
        _ts_cache.update(t=now, pb=PB.load(), a=A.load()); STATE["_files_changed"] = False
    pb, a = _ts_cache["pb"], _ts_cache["a"]
    n_proven = sum(len(r) for gd in (pb or {}).get("best", {}).values() for r in gd.values())
    return dict(stage=STATE.get("stage"), progress=STATE.get("progress", 0), detail=STATE.get("detail", ""),
                audited=bool(a), audit_summary=(a or {}).get("summary"), playbook=bool(pb),
                playbook_tfs=list((pb or {}).get("table", {}).keys()), proven_combos=n_proven,
                playbook_age_days=round(_playbook_age_days(), 1) if pb else None, last=STATE.get("last", {}))


def _playbook_age_days():
    from core import playbook as PB
    pb = PB.load()
    return 1e9 if not pb else (time.time() - pb.get("ts", 0)) / 86400


def loop(forward_every=900, health_every=6 * 3600, playbook_every=7 * 86400, iran_gold_every=1800, resilient_every=1800, evolution_every=3600):
    STATE["running"] = True
    _lower_priority()
    log("maintenance thread started (low priority)")
    last_fw = last_h = last_pb = 0.0
    # let the UI come up and the user look around before any heavy work
    STATE["stage"] = "idle"; STATE["detail"] = f"starting in {START_DELAY}s"
    if _stop.wait(START_DELAY):
        STATE["running"] = False; return
    # ---- self-training on first run (the user never has to "teach" anything)
    _run("audit", task_audit)
    _run("success-rates", task_success_rates)          # WR/PF next to every signal, majors first (fast, resumable)
    from core import playbook as PB
    pb = PB.load()
    if not pb:
        log("no playbook → stage 1: quick playbook (1d/4h/1h, 6 symbols/group)")
        _run("playbook-quick", task_playbook_quick)
        pb = PB.load()
    full = pb and len(pb.get("table", {})) >= 10
    if not full or _playbook_age_days() > 14:
        log("stage 2: full playbook in background (resumable)")
        _run("playbook", task_playbook); last_pb = time.time()
    last_ig = last_rs = last_ev = 0.0
    while not _stop.is_set():
        now = time.time()
        if now - last_fw >= forward_every:
            _run("forward", task_forward); last_fw = time.time()
        if now - last_ig >= iran_gold_every:
            _run("iran_gold", task_iran_gold); last_ig = time.time()
        if now - last_rs >= resilient_every:
            _run("resilient", task_resilient_check); last_rs = time.time()
        if now - last_ev >= evolution_every:
            _run("evolution_quick", task_auto_evolution_quick); last_ev = time.time()
        if now - last_h >= health_every:
            _run("health", task_health_autofix); last_h = time.time()
        if now - last_pb >= playbook_every and _playbook_age_days() > 7:
            _run("playbook", task_playbook); last_pb = time.time()
        _stop.wait(60)
    STATE["running"] = False


def start():
    if STATE["running"]:
        return
    th = threading.Thread(target=loop, name="maintenance", daemon=True)
    th.start()
    return th


def stop():
    _stop.set()
