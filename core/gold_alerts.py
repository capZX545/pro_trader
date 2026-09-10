"""
Gold Alerts — هشدارهای طلای ایران
سیستم هشدار پیشرفته برای طلای ایران

Features:
- قیمت به حد خاصی رسید
- حباب از حدی گذشت
- آربیتراژ پیدا شد
- تغییر شدید دلار یا انس
- الگوی فصلی خاص
"""

import os
import time
import json
import threading
from typing import Dict, List, Optional, Callable
from core.paths import data as data_path

ALERTS_FILE = data_path("gold_alerts.json")
ALERTS_HISTORY = data_path("gold_alerts_history.json")

# Alert types
ALERT_TYPES = {
    "price_above": "قیمت بالاتر از حد",
    "price_below": "قیمت پایین‌تر از حد",
    "bubble_above": "حباب بالاتر از حد",
    "bubble_below": "حباب پایین‌تر از حد (فرصت)",
    "dollar_change": "تغییر شدید دلار",
    "gold_change": "تغییر شدید طلا",
    "arbitrage": "فرصت آربیتراژ",
    "seasonal": "الگوی فصلی خاص",
}

class GoldAlert:
    def __init__(self, alert_type: str, symbol: str, threshold: float, enabled: bool = True, **kwargs):
        self.id = f"{alert_type}_{symbol}_{int(time.time())}"
        self.type = alert_type
        self.symbol = symbol
        self.threshold = threshold
        self.enabled = enabled
        self.created_at = time.time()
        self.last_triggered = 0
        self.trigger_count = 0
        self.extra = kwargs
    
    def to_dict(self):
        return {
            "id": self.id,
            "type": self.type,
            "symbol": self.symbol,
            "threshold": self.threshold,
            "enabled": self.enabled,
            "created_at": self.created_at,
            "last_triggered": self.last_triggered,
            "trigger_count": self.trigger_count,
            "extra": self.extra,
        }
    
    @classmethod
    def from_dict(cls, d):
        alert = cls(d["type"], d["symbol"], d["threshold"], d.get("enabled", True), **d.get("extra", {}))
        alert.id = d["id"]
        alert.created_at = d.get("created_at", time.time())
        alert.last_triggered = d.get("last_triggered", 0)
        alert.trigger_count = d.get("trigger_count", 0)
        return alert

def load_alerts() -> List[GoldAlert]:
    try:
        if os.path.exists(ALERTS_FILE):
            data = json.load(open(ALERTS_FILE, encoding="utf-8"))
            return [GoldAlert.from_dict(d) for d in data]
    except Exception:
        pass
    return []

def save_alerts(alerts: List[GoldAlert]):
    try:
        os.makedirs(os.path.dirname(ALERTS_FILE), exist_ok=True)
        data = [a.to_dict() for a in alerts]
        json.dump(data, open(ALERTS_FILE, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[gold_alerts] save failed: {e}")

def add_alert(alert_type: str, symbol: str, threshold: float, **kwargs) -> GoldAlert:
    alerts = load_alerts()
    alert = GoldAlert(alert_type, symbol, threshold, **kwargs)
    alerts.append(alert)
    save_alerts(alerts)
    return alert

def remove_alert(alert_id: str):
    alerts = load_alerts()
    alerts = [a for a in alerts if a.id != alert_id]
    save_alerts(alerts)

def check_alerts() -> List[Dict]:
    """
    بررسی هشدارها و برگرداندن هشدارهای فعال شده
    """
    alerts = load_alerts()
    triggered = []
    
    if not alerts:
        return []
    
    try:
        from core import iran_gold
        from core.bubble import get_all_bubbles
        
        prices = iran_gold.get_all_live_prices()
        bubbles = get_all_bubbles()
        
        for alert in alerts:
            if not alert.enabled:
                continue
            
            # Cooldown: at least 1 hour between triggers for same alert
            if time.time() - alert.last_triggered < 3600:
                continue
            
            should_trigger = False
            current_value = None
            message = ""
            
            if alert.type == "price_above":
                data = prices.get(alert.symbol)
                if data:
                    current_value = data["price"]
                    if current_value >= alert.threshold:
                        should_trigger = True
                        message = f"{alert.symbol} به {current_value:,.0f} ریال رسید (حد: {alert.threshold:,.0f})"
            
            elif alert.type == "price_below":
                data = prices.get(alert.symbol)
                if data:
                    current_value = data["price"]
                    if current_value <= alert.threshold:
                        should_trigger = True
                        message = f"{alert.symbol} به {current_value:,.0f} ریال افت کرد (حد: {alert.threshold:,.0f})"
            
            elif alert.type == "bubble_above":
                bubble_info = bubbles.get(alert.symbol)
                if bubble_info:
                    current_value = bubble_info["bubble_percent"]
                    if current_value >= alert.threshold:
                        should_trigger = True
                        message = f"حباب {alert.symbol} به {current_value:.1f}% رسید (حد: {alert.threshold:.1f}%) - ریسک بالا"
            
            elif alert.type == "bubble_below":
                bubble_info = bubbles.get(alert.symbol)
                if bubble_info:
                    current_value = bubble_info["bubble_percent"]
                    if current_value <= alert.threshold:
                        should_trigger = True
                        message = f"حباب {alert.symbol} به {current_value:.1f}% افت کرد (حد: {alert.threshold:.1f}%) - فرصت خرید"
            
            if should_trigger:
                alert.last_triggered = time.time()
                alert.trigger_count += 1
                
                triggered.append({
                    "alert": alert.to_dict(),
                    "current_value": current_value,
                    "message": message,
                    "message_en": message,  # TODO: translate
                    "timestamp": time.time(),
                })
        
        # Save updated alerts
        if triggered:
            save_alerts(alerts)
            
            # Save to history
            try:
                history = []
                if os.path.exists(ALERTS_HISTORY):
                    history = json.load(open(ALERTS_HISTORY, encoding="utf-8"))
                history.extend(triggered)
                # Keep last 500
                history = history[-500:]
                json.dump(history, open(ALERTS_HISTORY, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
            except Exception:
                pass
    
    except Exception as e:
        print(f"[gold_alerts] check failed: {e}")
    
    return triggered

def get_alerts_history(n: int = 50) -> List[Dict]:
    try:
        if os.path.exists(ALERTS_HISTORY):
            data = json.load(open(ALERTS_HISTORY, encoding="utf-8"))
            return data[-n:][::-1]
    except Exception:
        pass
    return []

# Background checker
_checker_thread = None
_checker_stop = threading.Event()
_on_alert_callback = None

def set_alert_callback(callback: Callable[[Dict], None]):
    """Set callback for when alert triggers (e.g., send Telegram, desktop notification)"""
    global _on_alert_callback
    _on_alert_callback = callback

def _checker_loop():
    while not _checker_stop.is_set():
        try:
            triggered = check_alerts()
            for trig in triggered:
                if _on_alert_callback:
                    try:
                        _on_alert_callback(trig)
                    except Exception as e:
                        print(f"[gold_alerts] callback failed: {e}")
                # Also try to send via existing alerts system
                try:
                    from core.alerts import push
                    push(
                        f"طلای ایران - {trig['alert']['symbol']}",
                        trig["message"],
                        meta={"type": "gold_alert", **trig}
                    )
                except Exception:
                    pass
        except Exception as e:
            print(f"[gold_alerts] checker error: {e}")
        
        _checker_stop.wait(60)  # Check every minute

def start_checker():
    global _checker_thread
    if _checker_thread and _checker_thread.is_alive():
        return
    _checker_stop.clear()
    _checker_thread = threading.Thread(target=_checker_loop, name="gold-alerts-checker", daemon=True)
    _checker_thread.start()
    print("[gold_alerts] checker started")

def stop_checker():
    _checker_stop.set()

# Auto-start
start_checker()

if __name__ == "__main__":
    # Test
    print("Adding test alert...")
    add_alert("price_above", "طلای 18 عیار / 750", 40000000)
    print(f"Alerts: {load_alerts()}")
    print(f"Triggered: {check_alerts()}")
