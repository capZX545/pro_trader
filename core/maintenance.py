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
        STATE["last"][name] = time.time()
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
    return r


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


def task_playbook():
    """stage 2: full universe, all timeframes (hours; resumable per timeframe)"""
    from core import playbook as PB
    import strategies as S
    PB.build_playbook(S.ALL_STRATEGIES, progress=_prog("playbook-full"),
                      tfs=["1d", "4h", "1h", "15m", "30m", "2h", "12h", "5m", "6h", "1wk", "3d", "3m", "1m"])
    return "rebuilt"


def training_status():
    """for the Dashboard: what the bot is doing to itself right now"""
    from core import playbook as PB, audit as A
    pb = PB.load(); a = A.load()
    n_proven = sum(len(r) for gd in (pb or {}).get("best", {}).values() for r in gd.values())
    return dict(stage=STATE.get("stage"), progress=STATE.get("progress", 0), detail=STATE.get("detail", ""),
                audited=bool(a), audit_summary=(a or {}).get("summary"), playbook=bool(pb),
                playbook_tfs=list((pb or {}).get("table", {}).keys()), proven_combos=n_proven,
                playbook_age_days=round(_playbook_age_days(), 1) if pb else None, last=STATE.get("last", {}))


def _playbook_age_days():
    from core import playbook as PB
    pb = PB.load()
    return 1e9 if not pb else (time.time() - pb.get("ts", 0)) / 86400


def loop(forward_every=900, health_every=6 * 3600, playbook_every=7 * 86400):
    STATE["running"] = True
    log("maintenance thread started")
    last_fw = last_h = last_pb = 0.0
    # ---- self-training on first run (the user never has to "teach" anything)
    _run("audit", task_audit)
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
    while not _stop.is_set():
        now = time.time()
        if now - last_fw >= forward_every:
            _run("forward", task_forward); last_fw = time.time()
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
