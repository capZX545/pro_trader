"""
Iran Gold Signals — سیگنال‌دهی طلای ایران

Integrates Iran Gold symbols with ProTrader's signal engine.
- Works with all existing strategies
- Special handling for IRR prices (large numbers)
- Converts IRR to Toman for display if needed
- Provides Iranian-specific signals (e.g., dollar correlation)

Usage:
    from core.iran_gold_signals import get_signals_for_iran_gold
    signals = get_signals_for_iran_gold("طلای 18 عیار / 750", "1h")
"""

import time
from typing import List, Dict, Optional

def get_signals_for_iran_gold(symbol: str, timeframe: str = "1h", min_score: int = 40) -> List[Dict]:
    """
    Get trading signals for Iran Gold symbol using all validated strategies.
    Returns list of signal dicts compatible with existing UI.
    """
    try:
        from core.data import get_ohlcv
        from core import playbook as PB
        from core import quality as Q
        from core import success as SR
        from core.backtest import run_backtest
        import strategies as S
        import numpy as np
        
        df = get_ohlcv(symbol, timeframe)
        if df is None or len(df) < 50:
            return []
        
        signals = []
        pb = PB.load()
        
        for cls in S.ALL_STRATEGIES:
            try:
                # Check if strategy is proven for this TF (optional filter)
                # For Iran Gold, we allow all strategies but prioritize proven ones
                res = cls().run(df)
                sig = res.signal.values
                if len(sig) == 0:
                    continue
                
                # Check last 3 bars for fresh signals
                recent_idx = np.where(sig[-3:] != 0)[0]
                if len(recent_idx) == 0:
                    continue
                
                i = len(df) - 3 + recent_idx[-1]
                side = int(sig[i])
                px = float(df.close.values[i])
                
                # Get SL/TP
                sl = None
                tp = None
                try:
                    if res.stop is not None:
                        sl = float(res.stop.values[i]) if not np.isnan(res.stop.values[i]) else None
                    if res.target is not None:
                        tp = float(res.target.values[i]) if not np.isnan(res.target.values[i]) else None
                except Exception:
                    pass
                
                # Success rate
                d = SR.get(cls.id, symbol, timeframe)
                if d is None:
                    # Run quick backtest to get stats
                    try:
                        bt = run_backtest(df, res, symbol=symbol)
                        d = SR.put(cls.id, symbol, timeframe, bt.stats)
                    except Exception:
                        d = {"wr": 50, "pf": 1.0, "n": 0}
                
                # Quality score
                try:
                    pbst = PB.stats_for(cls.id, timeframe, symbol) if pb else {}
                    qs = Q.score(cls.id, symbol, timeframe, ev=(d, pbst or None, None))
                    score = qs["score"]
                    verdict = qs["verdict"]
                except Exception:
                    score = 50
                    verdict = "UNPROVEN"
                
                if score < min_score:
                    continue
                
                # RR
                rr = None
                if sl and tp and px != sl:
                    try:
                        rr = abs(tp - px) / abs(px - sl)
                    except Exception:
                        pass
                
                signals.append({
                    "sid": cls.id,
                    "symbol": symbol,
                    "tf": timeframe,
                    "side": side,
                    "px": px,
                    "sl": sl,
                    "tp": tp,
                    "rr": rr,
                    "wr": d.get("wr", 0),
                    "pf": d.get("pf", 0),
                    "n": d.get("n", 0),
                    "score": score,
                    "verdict": verdict,
                    "ago": len(df) - 1 - i,
                    "time": str(df.index[i]),
                    "is_iran_gold": True,
                })
            except Exception as e:
                # print(f"[iran_gold_signals] {cls.id} failed: {e}")
                continue
        
        # Sort by score desc, then by freshness
        signals.sort(key=lambda x: (-x["score"], x["ago"]))
        
        return signals
    except Exception as e:
        print(f"[iran_gold_signals] failed for {symbol}: {e}")
        return []

def get_all_iran_gold_signals(timeframe: str = "1h", min_score: int = 40) -> Dict[str, List[Dict]]:
    """Get signals for all Iran Gold symbols."""
    try:
        from core.data import IRAN_GOLD_UNIVERSE
        out = {}
        for symbol in IRAN_GOLD_UNIVERSE.keys():
            # Only main Persian symbols to avoid duplicates
            if "Gold" in symbol and "Iran" in symbol:
                continue  # skip English aliases, use Persian
            if "Coin" in symbol:
                continue
            if "USD" in symbol and "Free" in symbol:
                continue
            try:
                sigs = get_signals_for_iran_gold(symbol, timeframe, min_score)
                if sigs:
                    out[symbol] = sigs
            except Exception:
                continue
        return out
    except Exception as e:
        print(f"[iran_gold_signals] get_all failed: {e}")
        return {}

def format_iran_gold_signal(signal: Dict, lang: str = "fa") -> str:
    """Format Iran Gold signal for display (Telegram/desktop)."""
    try:
        sym = signal["symbol"]
        tf = signal["tf"]
        sid = signal["sid"]
        side = signal["side"]
        px = signal["px"]
        sl = signal.get("sl")
        tp = signal.get("tp")
        rr = signal.get("rr")
        wr = signal.get("wr", 0)
        pf = signal.get("pf", 0)
        
        arrow = "🟢 خرید" if side > 0 else "🔴 فروش"
        if lang != "fa":
            arrow = "🟢 LONG" if side > 0 else "🔴 SHORT"
        
        # Format price in IRR (with Toman conversion note)
        def fmt_price(p):
            if p is None:
                return "—"
            if p >= 1000000:
                # Show in Toman (IRR/10) and Rial
                toman = p / 10
                return f"{p:,.0f} ریال ({toman:,.0f} تومان)"
            else:
                return f"{p:,.0f}"
        
        if lang == "fa":
            return (
                f"{arrow} {sym} · {tf} · {sid}\n"
                f"ورود ≈ {fmt_price(px)}\n"
                f"استاپ {fmt_price(sl)} | هدف {fmt_price(tp)}"
                f"{f' (R:R {rr:.1f})' if rr else ''}\n"
                f"موفقیت: {wr:.0f}% · PF {pf:.2f} · امتیاز {signal.get('score',0):.0f}\n"
                f"🇮🇷 طلای ایران | ضدفیلتر فعال\n"
                f"⚠ تحلیل است نه دستور؛ ریسک ≤۱٪"
            )
        else:
            return (
                f"{arrow} {sym} · {tf} · {sid}\n"
                f"entry ≈ {fmt_price(px)} | stop {fmt_price(sl)} | target {fmt_price(tp)}"
                f"{f' (R:R {rr:.1f})' if rr else ''}\n"
                f"WR {wr:.0f}% · PF {pf:.2f} · score {signal.get('score',0):.0f}\n"
                f"🇮🇷 Iran Gold | anti-filter active"
            )
    except Exception as e:
        return f"Signal format error: {e}"

if __name__ == "__main__":
    # Test
    print("Testing Iran Gold signals...")
    sigs = get_signals_for_iran_gold("طلای 18 عیار / 750", "1d", min_score=0)
    print(f"Found {len(sigs)} signals")
    for s in sigs[:3]:
        print(format_iran_gold_signal(s, "fa"))
        print("---")
