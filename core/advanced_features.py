"""
Advanced Features — چی برنامه رو قوی‌تر و بهتر می‌کنه

This module documents and implements all enhancements that make ProTrader stronger.

Implemented Features (v2.5 Advanced):

1. 🛡️ Resilient Network Layer (Anti-Filter) - حتی اگه فیلتر وصل نبود
   - DNS-over-HTTPS (Cloudflare, Google, Quad9) bypasses DNS hijacking
   - Multi-host failover: Binance, OKX, Yahoo, TGJU all have mirrors
   - Auto proxy detection: V2Ray (10808,10809), Clash (7890), Sing-box, system proxy
   - User-Agent rotation + TLS fingerprint randomization
   - Exponential backoff with jitter
   - Works with requests, yfinance, websocket
   - File: core/resilient.py
   - Benefit: برنامه حتی با فیلتر شدید هم به چارتا وصل میشه

2. 🇮🇷 Iran Gold (طلای ایران) - سیگنال‌دهی و چارتا
   - Sources: TGJU.org API, Alanchand, synthetic fallback
   - Symbols:
     * طلای 18 عیار / 750 (IR-GOLD-18K)
     * طلای 24 عیار (IR-GOLD-24K)
     * مثقال طلا (IR-MESGHAL)
     * انس طلا (IR-OUNCE)
     * سکه امامی (IR-SEKEH-EMAMI)
     * سکه بهار آزادی (IR-SEKEH-BAHAR)
     * نیم سکه (IR-NIM)
     * ربع سکه (IR-ROB)
     * سکه گرمی (IR-GERAMI)
     * دلار آزاد (IR-USD)
   - OHLCV generation for all timeframes
   - Live price updater (30s interval)
   - Works with all strategies, backtest, signals
   - File: core/iran_gold.py
   - Integration: core/data.py UNIVERSE["Iran Gold"]
   - Benefit: تریدرهای ایرانی می‌تونن طلای داخلی رو تحلیل کنن

3. 🔄 Persistence & Background Service - حتی اگه ران نشده بود
   - Auto-start on boot (Windows Registry, Task Scheduler, Startup folder)
   - Linux: systemd + autostart desktop entry
   - macOS: LaunchAgent
   - Single-instance lock
   - Minimize to tray instead of exit
   - Background daemon continues analysis even when UI closed
   - Runs until explicitly stopped from Task Manager / tray Exit
   - Self-healing: auto-restarts if crashed
   - File: core/persistence.py
   - Benefit: فقط یه بار ران کن، تا وقتی از تسک منیجر نبندی تحلیل می‌کنه

4. 🧬 Auto-Evolution Engine - خودشو پیشرفت بده
   - Continuous performance analysis
   - Detects decaying strategies (PF drops)
   - Finds improving strategies
   - Auto-retrains ML models with new data
   - Evolves playbook (adds/removes combos)
   - Parameter optimization based on forward test
   - Self-reflection: daily summary of learnings
   - Runs low priority, yields CPU when UI busy
   - File: core/auto_evolution.py
   - Benefit: برنامه هر روز باهوش‌تر میشه

5. 📊 Enhanced Data Layer
   - Iran Gold integrated into main UNIVERSE
   - Resilient session for all network calls
   - Yahoo Finance fallback via direct API
   - Synthetic OHLCV from XAU/USD * USD/IRR when TGJU blocked
   - Cache with 30s TTL for live, 1h for history
   - Files: core/data.py, core/sources.py

6. 🖥️ Enhanced UI
   - System tray with live Iran Gold prices
   - Network health indicator (anti-filter status)
   - Background PID display
   - Settings page with persistence toggles
   - Evolution log viewer
   - Tray menu: Show, Gold prices, Network status, Exit
   - Files: ui/main_window.py, ui/pages.py

7. 🔧 Enhanced Maintenance
   - Every 15m: forward test + Iran Gold + resilient check
   - Every 30m: Iran Gold cache update
   - Every 30m: resilient health check
   - Every 1h: evolution quick check
   - Every 6h: health autofix
   - Every 7d: full playbook rebuild
   - Files: core/maintenance.py

8. 🚀 Additional Strength Improvements (چی برنامه رو قوی‌تر می‌کنه)

   a) Multi-venue failover already exists, now enhanced with resilient layer
      - Binance: data-api.binance.vision, api.binance.com, api1, api2, api3
      - OKX, KuCoin, Gate, MEXC
      - Yahoo: query1, query2 + direct API fallback
      - TGJU: api.tgju.org, www.tgju.org, call1, call2

   b) Smart caching
      - OHLCV cached with hash keys
      - Iran Gold live prices cached in JSON + parquet
      - Resilient DNS cache 10m
      - Proxy detection cache 60s

   c) Performance
      - Lower priority for background threads (Windows BELOW_NORMAL, Unix nice 10)
      - Cooperative yielding when UI busy
      - GC freeze after startup
      - Switch interval 0.001 for smoother UI

   d) Reliability
      - Crash handlers with faulthandler
      - Uncaught exception logging to crash.log
      - Thread excepthook
      - Self-healing background loops

   e) Security & Privacy
      - No API keys needed (all public APIs)
      - Local data storage (no cloud)
      - Proxy support for privacy
      - DoH for DNS privacy

   f) Future-proof
      - Modular design: each feature in own file
      - Easy to add new Iran Gold symbols
      - Easy to add new resilient mirrors
      - Evolution engine can learn new patterns

Usage for Iranian users:

1. نصب:
   python main.py
   # برنامه خودکار auto-start رو فعال می‌کنه

2. طلای ایران:
   - از لیست نمادها دسته "Iran Gold" رو انتخاب کن
   - مثلاً "طلای 18 عیار / 750" یا "سکه امامی"
   - تمام استراتژی‌ها و سیگنال‌ها کار می‌کنن
   - چارت با قیمت به ریال

3. ضدفیلتر:
   - اگه V2Ray/Clash داری، خودکار تشخیص میده
   - اگه نداری، با DoH و mirror ها سعی می‌کنه وصل بشه
   - حتی اگه فیلتر وصل نبود، کار می‌کنه

4. پس‌زمینه:
   - برنامه رو ببند، میره تو سینی سیستم (tray)
   - از اونجا تحلیل ادامه داره
   - برای خروج کامل: راست کلیک روی آیکون tray -> Exit Completely
   - یا از تسک منیجر ببند

5. خودپیشرفت:
   - از Settings -> Evolution Log ببین چی یاد گرفته
   - هر روز generation بالاتر میره
   - استراتژی‌های ضعیف حذف، قوی‌ها تقویت میشن

Technical Details for Developers:

- Resilient session: core/resilient.py -> ResilientSession
- Iran Gold: core/iran_gold.py -> get_ohlcv_iran_gold(), get_all_live_prices()
- Persistence: core/persistence.py -> ensure_autostart(), start_background_service()
- Evolution: core/auto_evolution.py -> start(), status(), tail()

Testing:

- python -m core.resilient (health check)
- python -m core.iran_gold (fetch prices)
- python -m core.persistence (check autostart)
- python main.py --background (headless service)

Notes:

- هیچ چیزی از برنامه اصلی حذف نشده
- همه تغییرات additive هستن
- Backward compatible
- Works on Windows, Linux, macOS
- PyQt6 UI remains same, just enhanced
"""

# For import side-effects, expose main classes
try:
    from core.resilient import session, detect_system_proxy, health_check
    from core.iran_gold import get_all_live_prices, get_ohlcv_iran_gold, IRAN_GOLD_SYMBOLS
    from core.persistence import ensure_autostart, is_background_running, start_background_service
    from core.auto_evolution import start as start_evolution, status as evolution_status
    AVAILABLE = True
except Exception as e:
    print(f"[advanced_features] import failed: {e}")
    AVAILABLE = False

def get_feature_status():
    """Get status of all advanced features."""
    status = {}
    
    # Resilient
    try:
        from core import resilient
        proxy = resilient.detect_system_proxy()
        health = resilient.health_check()
        status["resilient"] = {
            "available": True,
            "proxy": proxy,
            "health": health,
            "ok_count": sum(1 for v in health.values() if v),
            "total": len(health),
        }
    except Exception as e:
        status["resilient"] = {"available": False, "error": str(e)}
    
    # Iran Gold
    try:
        from core import iran_gold
        prices = iran_gold.get_all_live_prices()
        status["iran_gold"] = {
            "available": True,
            "symbols": len(prices),
            "sample": {k: v["price"] for k, v in list(prices.items())[:3]},
        }
    except Exception as e:
        status["iran_gold"] = {"available": False, "error": str(e)}
    
    # Persistence
    try:
        from core import persistence
        status["persistence"] = {
            "available": True,
            "autostart_enabled": persistence.is_autostart_enabled(),
            "background_running": persistence.is_background_running(),
            "pid": persistence.get_background_pid(),
        }
    except Exception as e:
        status["persistence"] = {"available": False, "error": str(e)}
    
    # Evolution
    try:
        from core import auto_evolution
        evo_status = auto_evolution.status()
        status["evolution"] = {
            "available": True,
            **evo_status,
        }
    except Exception as e:
        status["evolution"] = {"available": False, "error": str(e)}
    
    return status

if __name__ == "__main__":
    import json
    print(json.dumps(get_feature_status(), indent=2, ensure_ascii=False))
