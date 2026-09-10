"""Android entry point (Chaquopy) - COMPLETE desktop engine, FAST, OFFLINE, NO extra installs

All 196 strategies, TradingView advanced chart, Iran Gold, all markets - everything from desktop, pre-installed.
No need to install anything extra, no waiting for engine, works immediately offline.
"""
import os, sys, shutil, threading, time

def _seed(dst):
    """First run: copy ALL bundled seed data into writable dir - FAST, only once"""
    try:
        import ptdata
        src = os.path.dirname(ptdata.__file__)
    except Exception:
        return
    
    # All important files from desktop
    important_files = [
        "playbook.json", "validation.json", "audit.json", "success.json",
        "vision_real.json", "vision_robustness.json", "gold_alerts.json",
        "iran_gold_live.json", "evolution_state.json"
    ]
    
    # Copy only if not exists - fast
    for name in os.listdir(src):
        if name.startswith("__"):
            continue
        s = os.path.join(src, name)
        d = os.path.join(dst, name)
        if os.path.exists(d):
            continue
        try:
            if os.path.isdir(s):
                shutil.copytree(s, d, dirs_exist_ok=True)
            else:
                shutil.copy2(s, d)
        except Exception:
            pass

def _find_web(root_hint):
    """Find web UI - including advanced TradingView chart"""
    try:
        import web
        return os.path.dirname(web.__file__)
    except Exception:
        pass
    for base in [root_hint] + sys.path:
        # Check for advanced chart first
        p = os.path.join(base, "web", "index.html")
        if os.path.isfile(p):
            return os.path.dirname(p)
        p2 = os.path.join(base, "web", "advanced_chart.html")
        if os.path.isfile(p2):
            return os.path.dirname(p2)
    return None

_port = [0]
_started = [False]

def start(port=8765):
    """Fast, idempotent start - returns port immediately, engine pre-loaded"""
    if _port[0] and _started[0]:
        return _port[0]
    
    home = os.environ.get("HOME") or "/data/local/tmp"
    data = os.path.join(home, "protrader")
    os.makedirs(data, exist_ok=True)
    os.makedirs(os.path.join(data, "cache"), exist_ok=True)
    
    os.environ.setdefault("PROTRADER_DATA", data)
    os.environ.setdefault("PROTRADER_NO_MAINT", "0")
    os.environ.setdefault("MPLCONFIGDIR", os.path.join(home, "mpl"))
    os.environ.setdefault("PROTRADER_FAST_START", "1")  # Fast start mode
    
    # Fast seed - only copy missing files
    _seed(data)
    
    # Find web UI
    from core import webapp
    web = _find_web(webapp.ROOT)
    if web:
        webapp.WEB_DIR = web
    
    # Start webapp FAST - no delay
    try:
        url, p = webapp.start(port=port, host="127.0.0.1")
        _port[0] = p
        _started[0] = True
        
        # Preload strategies in background - so first Run is fast
        def preload():
            try:
                time.sleep(0.5)  # Let webapp start first
                import strategies as S
                from core.data import UNIVERSE
                # Touch registry to load all strategies
                _ = len(S.ALL_STRATEGIES)
                # Preload playbook
                try:
                    from core import playbook as PB
                    _ = PB.proven_ids()
                except Exception:
                    pass
                # Preload success rates
                try:
                    from core import success as SR
                    _ = SR.summary()
                except Exception:
                    pass
            except Exception:
                pass
        
        threading.Thread(target=preload, daemon=True).start()
        
        # Start maintenance in background (like desktop)
        try:
            from core import maintenance
            if os.environ.get("PROTRADER_NO_MAINT") != "1":
                maintenance.start()
        except Exception:
            pass
        
        # Alert loop
        threading.Thread(target=_alert_loop, name="pt-alerts", daemon=True).start()
        
        return p
    except Exception as e:
        # If port in use, try to find existing
        if _port[0]:
            return _port[0]
        raise e

def _alert_loop(every=900):
    """Same alert scanner as desktop - proven strategies, news-aware, works in background"""
    time.sleep(30)  # Wait for engine to be ready
    while True:
        try:
            from core import alerts as AL
            AL.scan(tfs=["1h", "4h"], lang="en")  # English only per user request
        except Exception:
            pass
        time.sleep(every)

def port():
    return _port[0]

def version():
    try:
        from core import webapp
        return webapp._version()
    except Exception:
        return "1.13.0"

def is_ready():
    """Check if engine is ready - for fast UI"""
    return _started[0] and _port[0] != 0
