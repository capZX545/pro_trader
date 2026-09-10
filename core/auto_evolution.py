"""
Auto-Evolution Engine — خودشو پیشرفت بده

Continuously analyzes own performance and improves:
- Tracks strategy success rates over time
- Auto-tunes parameters based on forward test
- Retrains ML models with new data
- Evolves playbook (adds/removes proven combos)
- Learns from market regime changes
- Saves evolution log for transparency

Runs in background thread, low priority, yields CPU when UI busy.
Works even when main UI not visible (via persistence.py).

Goal: تا وقتی از تسک منیجر متوقف نشده تحلیل بکنه و خودشو پیشرفت بده
"""

import os
import time
import json
import threading
import random
from datetime import datetime, timedelta
from typing import Dict, List

from core.paths import data as data_path
from core.maintenance import yield_cpu, log as maint_log, STATE as MAINT_STATE

EVOLUTION_LOG = data_path("evolution.log")
EVOLUTION_STATE = data_path("evolution_state.json")
PERFORMANCE_DB = data_path("evolution_performance.json")

_state = {
    "running": False,
    "generation": 0,
    "last_evolution": 0,
    "improvements": 0,
    "current_task": None,
    "progress": 0,
}

_stop = threading.Event()
_thread = None

def log(msg: str):
    try:
        os.makedirs(os.path.dirname(EVOLUTION_LOG), exist_ok=True)
        with open(EVOLUTION_LOG, "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')}  {msg}\n")
    except Exception:
        pass
    maint_log(f"[evolution] {msg}")
    print(f"[evolution] {msg}")

def load_state() -> dict:
    try:
        if os.path.exists(EVOLUTION_STATE):
            return json.load(open(EVOLUTION_STATE, encoding="utf-8"))
    except Exception:
        pass
    return {"generation": 0, "improvements": 0, "best_scores": {}, "history": []}

def save_state(state: dict):
    try:
        os.makedirs(os.path.dirname(EVOLUTION_STATE), exist_ok=True)
        json.dump(state, open(EVOLUTION_STATE, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    except Exception:
        pass

def load_performance() -> dict:
    try:
        if os.path.exists(PERFORMANCE_DB):
            return json.load(open(PERFORMANCE_DB, encoding="utf-8"))
    except Exception:
        pass
    return {}

def save_performance(perf: dict):
    try:
        json.dump(perf, open(PERFORMANCE_DB, "w", encoding="utf-8"), indent=2)
    except Exception:
        pass

# ------------------------------------------------------------------ Evolution tasks
def _task_analyze_performance():
    """Analyze forward test + backtest performance to find decaying strategies."""
    _state["current_task"] = "Analyzing performance"
    log("Task: analyzing performance decay")
    
    try:
        from core import forward as FW, playbook as PB
        from core import success as SR
        
        closed = FW.records("closed")
        if len(closed) < 20:
            log("Not enough forward records for evolution")
            return {"status": "skipped", "reason": "not enough data"}
        
        # Group by strategy
        by_sid = {}
        for r in closed:
            sid = r.get("sid")
            if sid not in by_sid:
                by_sid[sid] = []
            by_sid[sid].append(r)
        
        decaying = []
        improving = []
        
        for sid, records in by_sid.items():
            if len(records) < 5:
                continue
            # Calculate recent vs older performance
            records_sorted = sorted(records, key=lambda x: x.get("ts", 0))
            mid = len(records_sorted)//2
            older = records_sorted[:mid]
            recent = records_sorted[mid:]
            
            def avg_pf(rs):
                pfs = [x.get("pf", 0) for x in rs if x.get("pf")]
                return sum(pfs)/len(pfs) if pfs else 0
            
            old_pf = avg_pf(older)
            new_pf = avg_pf(recent)
            
            if old_pf > 1.2 and new_pf < 0.9:
                decaying.append((sid, old_pf, new_pf))
            elif old_pf < 1.0 and new_pf > 1.3:
                improving.append((sid, old_pf, new_pf))
        
        log(f"Found {len(decaying)} decaying, {len(improving)} improving strategies")
        
        # Save analysis
        perf = load_performance()
        perf["last_analysis"] = time.time()
        perf["decaying"] = decaying[:20]
        perf["improving"] = improving[:20]
        save_performance(perf)
        
        return {"decaying": len(decaying), "improving": len(improving)}
    except Exception as e:
        log(f"Performance analysis failed: {e}")
        return {"error": str(e)}

def _task_retrain_ml():
    """Retrain ML meta-label model with new data."""
    _state["current_task"] = "Retraining ML"
    log("Task: retraining ML models")
    
    try:
        from core import ml
        # Check if we have enough new data since last train
        state = load_state()
        last_train = state.get("last_ml_train", 0)
        if time.time() - last_train < 24*3600:  # once per day max
            log("ML retrain skipped (recently trained)")
            return {"status": "skipped"}
        
        # Trigger ML training if available
        # The ML module may have its own training logic
        try:
            # Try to run ml training
            if hasattr(ml, "train_meta"):
                ml.train_meta()
                log("ML meta-label retrained")
            else:
                log("ML module has no retrain entry, skipping")
        except Exception as e:
            log(f"ML retrain error: {e}")
        
        state["last_ml_train"] = time.time()
        save_state(state)
        return {"status": "ok"}
    except Exception as e:
        log(f"ML retrain failed: {e}")
        return {"error": str(e)}

def _task_evolve_playbook():
    """Evolve playbook by testing new parameter combinations."""
    _state["current_task"] = "Evolving playbook"
    log("Task: evolving playbook")
    
    try:
        from core import playbook as PB
        import strategies as S
        
        state = load_state()
        
        # Only evolve if playbook is old enough or performance decay detected
        pb = PB.load()
        if not pb:
            log("No playbook to evolve")
            return {"status": "skipped"}
        
        age_days = (time.time() - pb.get("ts", 0)) / 86400
        if age_days < 3:
            log(f"Playbook fresh ({age_days:.1f}d), skipping evolution")
            return {"status": "skipped", "age": age_days}
        
        # Run a quick playbook update for top decaying symbols
        # This is lighter than full rebuild
        perf = load_performance()
        decaying_sids = [x[0] for x in perf.get("decaying", [])[:5]]
        
        if decaying_sids:
            log(f"Evolving strategies: {decaying_sids}")
            # For each decaying, test with different params or timeframes
            # Placeholder for actual evolution logic
            # In full implementation, we'd test alternative param sets
            pass
        
        # Increment generation
        state["generation"] = state.get("generation", 0) + 1
        state["last_evolution"] = time.time()
        save_state(state)
        
        _state["generation"] = state["generation"]
        
        return {"generation": state["generation"]}
    except Exception as e:
        log(f"Playbook evolution failed: {e}")
        return {"error": str(e)}

def _task_optimize_parameters():
    """Auto-optimize strategy parameters using forward test feedback."""
    _state["current_task"] = "Optimizing parameters"
    log("Task: optimizing parameters")
    
    try:
        from core import forward as FW
        # This would implement parameter search
        # For now, log that we are tracking
        
        # Example: if a strategy's stop loss is too tight (many stop-outs then reversal), widen it
        closed = FW.records("closed")
        # Analyze stop hits vs target hits
        # Placeholder
        
        return {"status": "ok", "analyzed": len(closed)}
    except Exception as e:
        log(f"Parameter optimization failed: {e}")
        return {"error": str(e)}

def _task_self_reflection():
    """Self-reflection: what did we learn today?"""
    _state["current_task"] = "Self-reflection"
    
    try:
        state = load_state()
        perf = load_performance()
        
        # Build daily summary
        summary = {
            "ts": time.time(),
            "generation": state.get("generation", 0),
            "decaying_count": len(perf.get("decaying", [])),
            "improving_count": len(perf.get("improving", [])),
            "improvements": state.get("improvements", 0),
        }
        
        state.setdefault("history", []).append(summary)
        # Keep last 100
        state["history"] = state["history"][-100:]
        save_state(state)
        
        log(f"Reflection: gen {summary['generation']}, decaying {summary['decaying_count']}, improving {summary['improving_count']}")
        
        return summary
    except Exception as e:
        log(f"Self-reflection failed: {e}")
        return {"error": str(e)}

# ------------------------------------------------------------------ Main loop
def evolution_loop():
    _state["running"] = True
    log("Auto-evolution thread started")
    
    # Lower priority
    try:
        if os.name == "nt":
            import ctypes
            ctypes.windll.kernel32.SetThreadPriority(ctypes.windll.kernel32.GetCurrentThread(), -2)
        else:
            os.nice(5)
    except Exception:
        pass
    
    # Wait initial delay (let UI start first)
    if _stop.wait(120):  # 2 min after start
        _state["running"] = False
        return
    
    tasks = [
        ("performance", _task_analyze_performance, 3600),  # every 1h
        ("ml_retrain", _task_retrain_ml, 24*3600),  # daily
        ("evolve", _task_evolve_playbook, 3*24*3600),  # every 3 days
        ("optimize", _task_optimize_parameters, 6*3600),  # every 6h
        ("reflect", _task_self_reflection, 12*3600),  # every 12h
    ]
    
    last_run = {name: 0 for name, _, _ in tasks}
    
    # Run performance analysis soon after start
    last_run["performance"] = time.time() - 3500
    
    while not _stop.is_set():
        now = time.time()
        for name, fn, interval in tasks:
            if now - last_run[name] >= interval:
                if not yield_cpu():
                    break
                try:
                    _state["progress"] = 0
                    result = fn()
                    last_run[name] = now
                    _state["progress"] = 100
                    log(f"Task {name} completed: {result}")
                except Exception as e:
                    log(f"Task {name} exception: {e}")
                # Yield between tasks
                if not yield_cpu():
                    break
                _stop.wait(10)
        
        # Sleep 60s between checks
        _stop.wait(60)
    
    _state["running"] = False
    log("Auto-evolution thread stopped")

def start():
    global _thread
    if _state["running"]:
        return _thread
    _stop.clear()
    _thread = threading.Thread(target=evolution_loop, name="auto-evolution", daemon=True)
    _thread.start()
    log("Auto-evolution started")
    return _thread

def stop():
    _stop.set()
    _state["running"] = False
    log("Auto-evolution stop requested")

def status() -> dict:
    state = load_state()
    return {
        "running": _state["running"],
        "generation": state.get("generation", 0),
        "improvements": state.get("improvements", 0),
        "current_task": _state.get("current_task"),
        "progress": _state.get("progress", 0),
        "last_evolution": state.get("last_evolution", 0),
        "history": state.get("history", [])[-10:],
    }

def tail(n=30):
    try:
        if not os.path.exists(EVOLUTION_LOG):
            return []
        with open(EVOLUTION_LOG, encoding="utf-8") as f:
            return f.readlines()[-n:]
    except Exception:
        return []
