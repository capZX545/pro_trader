"""
Arbitrage Detection — آربیتراژ
تشخیص فرصت‌های آربیتراژ بین بازارهای مختلف طلا

- آربیتراژ بین TGJU و انس جهانی
- آربیتراژ بین سکه‌ها (مثلاً نیم سکه vs ربع سکه)
- آربیتراژ دلار و طلا
"""

from typing import Dict, List, Optional
import time

def detect_gold_arbitrage() -> List[Dict]:
    """
    تشخیص آربیتراژ طلا
    مثلاً اگر طلای 18 عیار از فرمول انس*دلار فاصله زیادی داشته باشه
    """
    opportunities = []
    
    try:
        from core import iran_gold
        from core.data import get_ohlcv
        
        prices = iran_gold.get_all_live_prices()
        
        # Get XAU/USD
        try:
            xau_df = get_ohlcv("Gold (XAU/USD)", "1d", max_age_sec=3600)
            xau_usd = float(xau_df.close.iloc[-1])
        except Exception:
            xau_usd = 2000
        
        # Get USD/IRR
        usd_data = prices.get("دلار آزاد")
        usd_irr = usd_data["price"] if usd_data else 600000
        
        # Calculate expected prices
        # 18K: (XAU * USD / 31.1035) * 0.75
        expected_18k = (xau_usd * usd_irr / 31.1035) * 0.75
        
        # Check 18K
        gold18k_data = prices.get("طلای 18 عیار / 750")
        if gold18k_data:
            market_18k = gold18k_data["price"]
            diff_pct = (market_18k - expected_18k) / expected_18k * 100
            
            if abs(diff_pct) > 2:  # >2% difference = potential arbitrage
                opportunities.append({
                    "type": "gold_vs_formula",
                    "symbol": "طلای 18 عیار / 750",
                    "market_price": market_18k,
                    "expected_price": expected_18k,
                    "diff_percent": diff_pct,
                    "diff_amount": market_18k - expected_18k,
                    "signal": "SELL" if diff_pct > 0 else "BUY",
                    "reason_fa": f"اختلاف {diff_pct:.2f}% با ارزش محاسباتی - "
                                 f"{'گران‌تر از حد' if diff_pct>0 else 'ارزان‌تر از حد'}",
                    "reason_en": f"{diff_pct:.2f}% diff from formula",
                    "strength": "strong" if abs(diff_pct) > 5 else "moderate",
                })
        
        # Check coins vs gold
        try:
            from core.bubble import get_all_bubbles
            bubbles = get_all_bubbles()
            for coin, info in bubbles.items():
                bubble_pct = info["bubble_percent"]
                if abs(bubble_pct) > 8:  # >8% bubble = opportunity
                    opportunities.append({
                        "type": "bubble",
                        "symbol": coin,
                        "market_price": info["market_price"],
                        "intrinsic_value": info["intrinsic_value"],
                        "diff_percent": bubble_pct,
                        "signal": "SELL" if bubble_pct > 0 else "BUY",
                        "reason_fa": f"حباب {bubble_pct:.1f}% - "
                                     f"{'فروش' if bubble_pct>0 else 'خرید'}",
                        "reason_en": f"Bubble {bubble_pct:.1f}%",
                        "strength": "strong" if abs(bubble_pct) > 12 else "moderate",
                    })
        except Exception:
            pass
        
        # Check coin vs coin arbitrage (e.g., 2x نیم = 1x امامی ?)
        # نیم سکه باید تقریباً نصف امامی باشه + کمی premium
        try:
            emami = prices.get("سکه امامی")
            nim = prices.get("نیم سکه")
            rob = prices.get("ربع سکه")
            
            if emami and nim:
                expected_nim = emami["price"] / 2
                actual_nim = nim["price"]
                diff_pct = (actual_nim - expected_nim) / expected_nim * 100
                
                if abs(diff_pct) > 5:
                    opportunities.append({
                        "type": "coin_vs_coin",
                        "symbol": "نیم سکه vs امامی",
                        "market_price": actual_nim,
                        "expected_price": expected_nim,
                        "diff_percent": diff_pct,
                        "signal": "SELL نیم، BUY امامی" if diff_pct > 0 else "BUY نیم، SELL امامی",
                        "reason_fa": f"نیم سکه {diff_pct:.1f}% اختلاف با نصف امامی",
                        "reason_en": f"Half coin {diff_pct:.1f}% diff from half Emami",
                    })
            
            if nim and rob:
                expected_rob = nim["price"] / 2
                actual_rob = rob["price"]
                diff_pct = (actual_rob - expected_rob) / expected_rob * 100
                
                if abs(diff_pct) > 5:
                    opportunities.append({
                        "type": "coin_vs_coin",
                        "symbol": "ربع سکه vs نیم سکه",
                        "market_price": actual_rob,
                        "expected_price": expected_rob,
                        "diff_percent": diff_pct,
                        "signal": "SELL ربع، BUY نیم" if diff_pct > 0 else "BUY ربع، SELL نیم",
                        "reason_fa": f"ربع سکه {diff_pct:.1f}% اختلاف با نصف نیم",
                        "reason_en": f"Quarter {diff_pct:.1f}% diff",
                    })
        except Exception:
            pass
        
    except Exception as e:
        print(f"[arbitrage] failed: {e}")
    
    # Sort by diff percent
    opportunities.sort(key=lambda x: abs(x["diff_percent"]), reverse=True)
    
    return opportunities

def format_arbitrage_report(lang: str = "fa") -> str:
    opps = detect_gold_arbitrage()
    if not opps:
        return "فرصت آربیتراژ خاصی یافت نشد" if lang == "fa" else "No arbitrage opportunities"
    
    lines = []
    if lang == "fa":
        lines.append("🔍 فرصت‌های آربیتراژ طلا:")
        lines.append("="*40)
        for opp in opps[:5]:
            lines.append(f"{opp['symbol']}: {opp['diff_percent']:+.2f}% - {opp['signal']}")
            lines.append(f"  {opp['reason_fa']}")
            lines.append("")
    else:
        lines.append("Arbitrage opportunities:")
        for opp in opps[:5]:
            lines.append(f"{opp['symbol']}: {opp['diff_percent']:+.2f}% - {opp['signal']}")
    
    return "\n".join(lines)

if __name__ == "__main__":
    print(format_arbitrage_report("fa"))
