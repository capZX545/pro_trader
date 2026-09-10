"""
Monitoring & Performance — مانیتورینگ و پرفورمنس
سیستم مانیتورینگ پیشرفته برای برنامه

- CPU, RAM, Disk usage
- Network health
- Data freshness
- Background services status
- Performance metrics
"""

import os
import time
import json
import threading
import psutil
from typing import Dict, List
from core.paths import data as data_path

MONITOR_LOG = data_path("monitoring.json")
PERF_LOG = data_path("performance.log")

def get_system_stats() -> Dict:
    """آمار سیستم"""
    try:
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        
        return {
            "cpu_percent": cpu_percent,
            "memory_percent": memory.percent,
            "memory_available_mb": memory.available / 1024 / 1024,
            "disk_percent": disk.percent,
            "disk_free_gb": disk.free / 1024 / 1024 / 1024,
            "timestamp": time.time(),
        }
    except ImportError:
        # Fallback without psutil
        return {
            "cpu_percent": 0,
            "memory_percent": 0,
            "memory_available_mb": 0,
            "disk_percent": 0,
            "disk_free_gb": 0,
            "timestamp": time.time(),
            "note": "psutil not installed",
        }
    except Exception as e:
        return {"error": str(e), "timestamp": time.time()}

def get_app_stats() -> Dict:
    """آمار برنامه"""
    try:
        from core import persistence, auto_evolution, iran_gold, resilient
        from core.paths import DATA_DIR
        
        # Data files count and size
        data_files = 0
        data_size_mb = 0
        try:
            for f in os.listdir(DATA_DIR):
                fp = os.path.join(DATA_DIR, f)
                if os.path.isfile(fp):
                    data_files += 1
                    data_size_mb += os.path.getsize(fp) / 1024 / 1024
        except Exception:
            pass
        
        # Background services
        bg_running = persistence.is_background_running()
        bg_pid = persistence.get_background_pid()
        
        # Evolution
        evo_status = auto_evolution.status()
        
        # Iran Gold
        try:
            prices = iran_gold.get_all_live_prices()
            gold_count = len(prices)
        except Exception:
            gold_count = 0
        
        # Network
        try:
            health = resilient.health_check()
            net_ok = sum(1 for v in health.values() if v)
            net_total = len(health)
        except Exception:
            net_ok = 0
            net_total = 0
        
        return {
            "data_files": data_files,
            "data_size_mb": round(data_size_mb, 2),
            "background_running": bg_running,
            "background_pid": bg_pid,
            "evolution_generation": evo_status.get("generation", 0),
            "evolution_running": evo_status.get("running", False),
            "iran_gold_symbols": gold_count,
            "network_ok": net_ok,
            "network_total": net_total,
            "network_health": f"{net_ok}/{net_total}",
            "timestamp": time.time(),
        }
    except Exception as e:
        return {"error": str(e), "timestamp": time.time()}

def get_performance_metrics() -> Dict:
    """متریک‌های پرفورمنس"""
    try:
        # Try to get from existing logs
        from core.maintenance import STATE as MAINT_STATE
        from core.paths import data as _data
        
        metrics = {
            "maintenance_running": MAINT_STATE.get("running", False),
            "maintenance_current": MAINT_STATE.get("current"),
            "maintenance_progress": MAINT_STATE.get("progress", 0),
            "timestamp": time.time(),
        }
        
        # Check last maintenance log
        try:
            log_path = _data("maintenance.log")
            if os.path.exists(log_path):
                with open(log_path, encoding="utf-8") as f:
                    lines = f.readlines()[-20:]
                    metrics["last_maintenance_logs"] = lines[-5:]
        except Exception:
            pass
        
        return metrics
    except Exception as e:
        return {"error": str(e)}

def log_performance():
    """لاگ پرفورمنس"""
    try:
        sys_stats = get_system_stats()
        app_stats = get_app_stats()
        perf_stats = get_performance_metrics()
        
        combined = {
            "timestamp": time.time(),
            "system": sys_stats,
            "app": app_stats,
            "performance": perf_stats,
        }
        
        # Append to log file
        try:
            os.makedirs(os.path.dirname(MONITOR_LOG), exist_ok=True)
            
            # Load existing
            existing = []
            if os.path.exists(MONITOR_LOG):
                try:
                    existing = json.load(open(MONITOR_LOG, encoding="utf-8"))
                except Exception:
                    existing = []
            
            existing.append(combined)
            # Keep last 1000 entries
            existing = existing[-1000:]
            
            json.dump(existing, open(MONITOR_LOG, "w", encoding="utf-8"), indent=1)
        except Exception as e:
            print(f"[monitoring] log failed: {e}")
        
        return combined
    except Exception as e:
        print(f"[monitoring] log_performance failed: {e}")
        return {}

def get_monitoring_history(n: int = 100) -> List[Dict]:
    try:
        if os.path.exists(MONITOR_LOG):
            data = json.load(open(MONITOR_LOG, encoding="utf-8"))
            return data[-n:]
    except Exception:
        pass
    return []

# Background monitoring thread
_monitor_thread = None
_monitor_stop = threading.Event()

def _monitor_loop():
    while not _monitor_stop.is_set():
        try:
            log_performance()
        except Exception as e:
            print(f"[monitoring] loop error: {e}")
        
        _monitor_stop.wait(300)  # Every 5 minutes

def start_monitoring():
    global _monitor_thread
    if _monitor_thread and _monitor_thread.is_alive():
        return
    _monitor_stop.clear()
    _monitor_thread = threading.Thread(target=_monitor_loop, name="monitoring", daemon=True)
    _monitor_thread.start()
    print("[monitoring] started")

def stop_monitoring():
    _monitor_stop.set()

# Auto-start
start_monitoring()

if __name__ == "__main__":
    print(get_system_stats())
    print(get_app_stats())
    print(log_performance())
