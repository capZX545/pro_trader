"""
حباب سکه - Coin Bubble Calculation
محاسبه حباب سکه‌های طلا نسبت به ارزش ذاتی

فرمول:
- ارزش ذاتی سکه = (انس طلا * نرخ دلار / 31.1035) * وزن * عیار + حق ضرب
- حباب = (قیمت بازار - ارزش ذاتی) / ارزش ذاتی * 100
- حباب مثبت = قیمت بازار بیشتر از ارزش ذاتی (معمولاً به خاطر تقاضا)
- حباب منفی = قیمت بازار کمتر از ارزش ذاتی (فرصت خرید)

وزن و عیار سکه‌ها:
- سکه امامی: 8.133 گرم، عیار 900، حق ضرب ~5000 تومان
- بهار آزادی: 8.133 گرم، عیار 900
- نیم سکه: 4.0665 گرم، عیار 900
- ربع سکه: 2.03225 گرم، عیار 900
- گرمی: 1.01 گرم، عیار 900
"""

from typing import Dict, Optional, Tuple
import time

# مشخصات سکه‌ها
COIN_SPECS = {
    "سکه امامی": {"weight": 8.133, "purity": 0.90, "mint_fee": 50000},  # 5000 تومان حق ضرب به ریال
    "سکه بهار آزادی": {"weight": 8.133, "purity": 0.90, "mint_fee": 50000},
    "نیم سکه": {"weight": 4.0665, "purity": 0.90, "mint_fee": 40000},
    "ربع سکه": {"weight": 2.03225, "purity": 0.90, "mint_fee": 30000},
    "سکه گرمی": {"weight": 1.01, "purity": 0.90, "mint_fee": 20000},
    # English aliases
    "Emami Coin": {"weight": 8.133, "purity": 0.90, "mint_fee": 50000},
    "Bahar Azadi Coin": {"weight": 8.133, "purity": 0.90, "mint_fee": 50000},
    "Half Coin": {"weight": 4.0665, "purity": 0.90, "mint_fee": 40000},
    "Quarter Coin": {"weight": 2.03225, "purity": 0.90, "mint_fee": 30000},
    "Gram Coin": {"weight": 1.01, "purity": 0.90, "mint_fee": 20000},
}

def calculate_intrinsic_value(
    ounce_usd: float,
    usd_irr: float,
    coin_type: str,
) -> Optional[float]:
    """
    محاسبه ارزش ذاتی سکه به ریال
    ounce_usd: قیمت انس طلا به دلار
    usd_irr: نرخ دلار آزاد به ریال
    coin_type: نوع سکه
    """
    spec = COIN_SPECS.get(coin_type)
    if not spec:
        return None
    
    try:
        # فرمول: (انس * دلار / 31.1035) * وزن * عیار + حق ضرب
        intrinsic = (ounce_usd * usd_irr / 31.1035) * spec["weight"] * spec["purity"] + spec["mint_fee"]
        return intrinsic
    except Exception:
        return None

def calculate_bubble(
    market_price: float,
    intrinsic_value: float,
) -> Optional[Dict]:
    """
    محاسبه حباب
    Returns: dict with bubble_percent, bubble_amount, is_overvalued
    """
    if not intrinsic_value or intrinsic_value <= 0:
        return None
    
    try:
        bubble_amount = market_price - intrinsic_value
        bubble_percent = (bubble_amount / intrinsic_value) * 100
        
        return {
            "bubble_amount": bubble_amount,
            "bubble_percent": bubble_percent,
            "is_overvalued": bubble_percent > 0,
            "is_undervalued": bubble_percent < 0,
            "bubble_toman": bubble_amount / 10,  # به تومان
        }
    except Exception:
        return None

def get_all_bubbles() -> Dict[str, Dict]:
    """
    دریافت حباب تمام سکه‌ها
    Returns: dict coin_type -> bubble_info
    """
    try:
        from core import iran_gold
        prices = iran_gold.get_all_live_prices()
        
        # Get required prices
        ounce_price = None
        usd_price = None
        
        # Try to get ounce in USD
        ounce_data = prices.get("انس طلا") or prices.get("IR-OUNCE")
        if ounce_data:
            # If price is in IRR, convert back? Actually ounce in our system is USD
            # Check currency
            if ounce_data.get("currency") == "USD":
                ounce_price = ounce_data["price"]
            else:
                # It's in IRR, need to convert using USD price
                # For now, try to get from XAU/USD directly
                try:
                    from core.data import get_ohlcv
                    df = get_ohlcv("Gold (XAU/USD)", "1d", max_age_sec=3600)
                    ounce_price = float(df.close.iloc[-1])
                except Exception:
                    ounce_price = 2000  # fallback
        
        usd_data = prices.get("دلار آزاد")
        if usd_data:
            usd_price = usd_data["price"]
        
        if not ounce_price or not usd_price:
            # Try synthetic
            try:
                from core.data import get_ohlcv
                df = get_ohlcv("Gold (XAU/USD)", "1d", max_age_sec=3600)
                ounce_price = float(df.close.iloc[-1])
            except Exception:
                ounce_price = 2000
            if not usd_price:
                usd_price = 600000  # fallback 60k toman *10
        
        results = {}
        
        for coin_type in ["سکه امامی", "سکه بهار آزادی", "نیم سکه", "ربع سکه", "سکه گرمی"]:
            try:
                coin_data = prices.get(coin_type)
                if not coin_data:
                    continue
                
                market_price = coin_data["price"]
                intrinsic = calculate_intrinsic_value(ounce_price, usd_price, coin_type)
                if not intrinsic:
                    continue
                
                bubble = calculate_bubble(market_price, intrinsic)
                if not bubble:
                    continue
                
                results[coin_type] = {
                    "market_price": market_price,
                    "intrinsic_value": intrinsic,
                    "ounce_usd": ounce_price,
                    "usd_irr": usd_price,
                    **bubble,
                    "market_price_toman": market_price / 10,
                    "intrinsic_toman": intrinsic / 10,
                }
            except Exception as e:
                print(f"[bubble] {coin_type} failed: {e}")
                continue
        
        return results
    except Exception as e:
        print(f"[bubble] get_all_bubbles failed: {e}")
        return {}

def get_bubble_signal(coin_type: str) -> Optional[Dict]:
    """
    سیگنال بر اساس حباب:
    - حباب > 10%: فروش (overvalued)
    - حباب < -5%: خرید (undervalued, فرصت)
    - حباب 0-10%: نگهداری
    """
    bubbles = get_all_bubbles()
    info = bubbles.get(coin_type)
    if not info:
        return None
    
    bubble_pct = info["bubble_percent"]
    
    if bubble_pct > 15:
        signal = "SELL"
        strength = "قوی"
        reason_fa = f"حباب {bubble_pct:.1f}% - بیش از حد گران، ریسک بالا"
        reason_en = f"Bubble {bubble_pct:.1f}% - overvalued, high risk"
    elif bubble_pct > 10:
        signal = "SELL"
        strength = "متوسط"
        reason_fa = f"حباب {bubble_pct:.1f}% - کمی گران"
        reason_en = f"Bubble {bubble_pct:.1f}% - slightly overvalued"
    elif bubble_pct < -5:
        signal = "BUY"
        strength = "قوی"
        reason_fa = f"حباب منفی {bubble_pct:.1f}% - فرصت خرید، زیر ارزش ذاتی"
        reason_en = f"Negative bubble {bubble_pct:.1f}% - buying opportunity"
    elif bubble_pct < 0:
        signal = "BUY"
        strength = "ضعیف"
        reason_fa = f"حباب منفی {bubble_pct:.1f}% - کمی زیر ارزش ذاتی"
        reason_en = f"Negative bubble {bubble_pct:.1f}% - slightly undervalued"
    else:
        signal = "HOLD"
        strength = "خنثی"
        reason_fa = f"حباب {bubble_pct:.1f}% - متعادل"
        reason_en = f"Bubble {bubble_pct:.1f}% - balanced"
    
    return {
        "coin": coin_type,
        "signal": signal,
        "strength": strength,
        "bubble_percent": bubble_pct,
        "reason_fa": reason_fa,
        "reason_en": reason_en,
        **info,
    }

def format_bubble_report(lang: str = "fa") -> str:
    """گزارش کامل حباب سکه‌ها"""
    bubbles = get_all_bubbles()
    if not bubbles:
        return "داده‌ای برای حباب موجود نیست" if lang == "fa" else "No bubble data"
    
    lines = []
    if lang == "fa":
        lines.append("💰 گزارش حباب سکه‌ها:")
        lines.append("="*40)
        for coin, info in bubbles.items():
            bp = info["bubble_percent"]
            mp_toman = info["market_price_toman"]
            iv_toman = info["intrinsic_toman"]
            bubble_toman = info["bubble_toman"]
            
            status = "🔴 حباب مثبت" if bp > 0 else "🟢 حباب منفی" if bp < 0 else "⚪ متعادل"
            lines.append(f"{coin}:")
            lines.append(f"  بازار: {mp_toman:,.0f} تومان")
            lines.append(f"  ذاتی: {iv_toman:,.0f} تومان")
            lines.append(f"  حباب: {bubble_toman:,.0f} تومان ({bp:+.1f}%) {status}")
            lines.append("")
    else:
        lines.append("💰 Coin Bubble Report:")
        lines.append("="*40)
        for coin, info in bubbles.items():
            bp = info["bubble_percent"]
            lines.append(f"{coin}: Market {info['market_price']:,.0f} IRR, Intrinsic {info['intrinsic_value']:,.0f} IRR, Bubble {bp:+.1f}%")
    
    return "\n".join(lines)

if __name__ == "__main__":
    print(format_bubble_report("fa"))
    print("\n--- Signals ---")
    for coin in ["سکه امامی", "نیم سکه", "ربع سکه"]:
        sig = get_bubble_signal(coin)
        if sig:
            print(f"{sig['coin']}: {sig['signal']} ({sig['strength']}) - {sig['reason_fa']}")
