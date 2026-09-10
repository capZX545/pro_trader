"""
Risk Management for Iran Gold — مدیریت ریسک طلای ایران
ریسک‌های خاص طلای ایران و نحوه مدیریت آن‌ها

ریسک‌های طلای ایران:
1. نوسان دلار (USD/IRR) - بزرگترین عامل
2. نوسان انس جهانی (XAU/USD)
3. حباب سکه - ریسک حباب
4. نقدشوندگی - اختلاف قیمت خرید و فروش
5. کارمزد طلا فروشی - 1-2%
6. ریسک نگهداری فیزیکی
7. ریسک فصلی (قبل عید، محرم)
"""

from typing import Dict, Optional, Tuple
import time

# کارمزدها و اسپردهای واقعی بازار طلای ایران
IRAN_GOLD_COSTS = {
    "طلای 18 عیار / 750": {
        "buy_spread": 0.005,  # 0.5% اختلاف خرید و فروش
        "sell_spread": 0.005,
        "commission": 0.01,  # 1% کارمزد
        "total_roundtrip": 0.02,  # 2% رفت و برگشت
    },
    "سکه امامی": {
        "buy_spread": 0.003,
        "sell_spread": 0.003,
        "commission": 0.005,
        "total_roundtrip": 0.011,
    },
    "نیم سکه": {
        "buy_spread": 0.005,
        "sell_spread": 0.005,
        "commission": 0.008,
        "total_roundtrip": 0.018,
    },
    "ربع سکه": {
        "buy_spread": 0.008,
        "sell_spread": 0.008,
        "commission": 0.01,
        "total_roundtrip": 0.026,
    },
    "سکه گرمی": {
        "buy_spread": 0.01,
        "sell_spread": 0.01,
        "commission": 0.015,
        "total_roundtrip": 0.035,
    },
    "default": {
        "buy_spread": 0.005,
        "sell_spread": 0.005,
        "commission": 0.01,
        "total_roundtrip": 0.02,
    }
}

def get_gold_costs(symbol: str) -> Dict:
    """دریافت کارمزد و اسپرد برای نماد طلا"""
    return IRAN_GOLD_COSTS.get(symbol, IRAN_GOLD_COSTS["default"])

def calculate_position_size(
    capital_rial: float,
    risk_percent: float,
    entry_price: float,
    stop_loss: float,
    symbol: str = "طلای 18 عیار / 750",
) -> Dict:
    """
    محاسبه حجم پوزیشن بر اساس مدیریت ریسک
    capital_rial: سرمایه به ریال
    risk_percent: درصد ریسک (مثلاً 1%)
    entry_price: قیمت ورود
    stop_loss: حد ضرر
    """
    try:
        costs = get_gold_costs(symbol)
        
        # فاصله حد ضرر
        stop_distance = abs(entry_price - stop_loss)
        if stop_distance == 0:
            return {"error": "Stop loss equals entry"}
        
        # ریسک به ریال
        risk_rial = capital_rial * (risk_percent / 100)
        
        # با احتساب کارمزد
        total_cost_factor = 1 + costs["total_roundtrip"]
        
        # حجم (گرم یا تعداد سکه)
        # برای طلا: گرم
        # برای سکه: تعداد
        if "سکه" in symbol:
            # تعداد سکه
            position_size = risk_rial / (stop_distance * total_cost_factor)
        else:
            # گرم طلا
            position_size = risk_rial / (stop_distance * total_cost_factor)
        
        # ارزش پوزیشن
        position_value = position_size * entry_price
        
        # کارمزد کل
        total_commission = position_value * costs["total_roundtrip"]
        
        return {
            "position_size": position_size,
            "position_value_rial": position_value,
            "position_value_toman": position_value / 10,
            "risk_rial": risk_rial,
            "risk_toman": risk_rial / 10,
            "stop_distance": stop_distance,
            "commission_rial": total_commission,
            "commission_toman": total_commission / 10,
            "symbol": symbol,
            "risk_percent": risk_percent,
            "is_affordable": position_value <= capital_rial,
            "remaining_capital_rial": capital_rial - position_value,
            "remaining_capital_toman": (capital_rial - position_value) / 10,
        }
    except Exception as e:
        return {"error": str(e)}

def assess_gold_risk(
    symbol: str,
    timeframe: str = "1d",
) -> Dict:
    """
    ارزیابی ریسک طلای ایران
    """
    try:
        from core import iran_gold
        from core.bubble import get_bubble_signal
        from core.correlation import get_dollar_impact_on_gold
        from core.jalali import get_seasonal_pattern
        
        risks = {
            "symbol": symbol,
            "overall_risk": "medium",  # low, medium, high, very_high
            "risk_score": 50,  # 0-100
            "factors": [],
            "recommendations_fa": [],
            "recommendations_en": [],
        }
        
        score = 50  # base
        
        # 1. حباب
        try:
            if "سکه" in symbol:
                bubble_sig = get_bubble_signal(symbol)
                if bubble_sig:
                    bubble_pct = bubble_sig["bubble_percent"]
                    if bubble_pct > 10:
                        risks["factors"].append({
                            "factor": "حباب مثبت بالا",
                            "factor_en": "High positive bubble",
                            "risk": "high",
                            "value": bubble_pct,
                            "description_fa": f"حباب {bubble_pct:.1f}% - ریسک اصلاح",
                            "description_en": f"Bubble {bubble_pct:.1f}% - correction risk",
                        })
                        score += 20
                        risks["recommendations_fa"].append("حباب بالا - احتیاط در خرید، حد ضرر نزدیک")
                    elif bubble_pct < -5:
                        risks["factors"].append({
                            "factor": "حباب منفی - فرصت",
                            "factor_en": "Negative bubble - opportunity",
                            "risk": "low",
                            "value": bubble_pct,
                            "description_fa": f"حباب منفی {bubble_pct:.1f}% - فرصت خرید",
                        })
                        score -= 10
        except Exception:
            pass
        
        # 2. تأثیر دلار
        try:
            impact = get_dollar_impact_on_gold()
            usd_change = impact.get("usd_change", 0)
            if abs(usd_change) > 3:
                risks["factors"].append({
                    "factor": "نوسان دلار",
                    "factor_en": "USD volatility",
                    "risk": "high" if abs(usd_change) > 5 else "medium",
                    "value": usd_change,
                    "description_fa": f"دلار {usd_change:+.2f}% - تأثیر مستقیم بر طلا",
                })
                score += 10 if abs(usd_change) > 5 else 5
        except Exception:
            pass
        
        # 3. الگوی فصلی
        try:
            seasonal = get_seasonal_pattern()
            demand = seasonal.get("gold_demand", "normal")
            if demand == "very_high":
                risks["factors"].append({
                    "factor": "تقاضای فصلی بالا",
                    "factor_en": "High seasonal demand",
                    "risk": "medium",
                    "description_fa": f"{seasonal.get('season','')} - {seasonal.get('reason_fa','')}",
                })
                score += 5
            elif demand == "low":
                risks["factors"].append({
                    "factor": "تقاضای فصلی پایین",
                    "factor_en": "Low seasonal demand",
                    "risk": "low",
                    "description_fa": seasonal.get('reason_fa',''),
                })
                score -= 5
        except Exception:
            pass
        
        # 4. کارمزد
        costs = get_gold_costs(symbol)
        if costs["total_roundtrip"] > 0.02:
            risks["factors"].append({
                "factor": "کارمزد بالا",
                "factor_en": "High fees",
                "risk": "medium",
                "value": costs["total_roundtrip"] * 100,
                "description_fa": f"کارمزد رفت و برگشت {costs['total_roundtrip']*100:.1f}%",
            })
            score += 5
        
        # Overall risk
        risks["risk_score"] = max(0, min(100, score))
        
        if score >= 80:
            risks["overall_risk"] = "very_high"
            risks["overall_risk_fa"] = "خیلی بالا"
        elif score >= 60:
            risks["overall_risk"] = "high"
            risks["overall_risk_fa"] = "بالا"
        elif score >= 40:
            risks["overall_risk"] = "medium"
            risks["overall_risk_fa"] = "متوسط"
        else:
            risks["overall_risk"] = "low"
            risks["overall_risk_fa"] = "پایین"
        
        # Recommendations
        if risks["overall_risk"] in ["high", "very_high"]:
            risks["recommendations_fa"].extend([
                "ریسک بالا - حجم پوزیشن را کم کن (0.5% سرمایه)",
                "حد ضرر نزدیک بگذار",
                "از اهرم استفاده نکن",
            ])
            risks["recommendations_en"].extend([
                "High risk - reduce position size",
                "Use tight stop loss",
            ])
        elif risks["overall_risk"] == "low":
            risks["recommendations_fa"].append("ریسک پایین - فرصت مناسب با مدیریت سرمایه")
        
        risks["recommendations_fa"].append(f"کارمزد {costs['total_roundtrip']*100:.1f}% را در نظر بگیر")
        
        return risks
    except Exception as e:
        return {"error": str(e), "overall_risk": "unknown", "risk_score": 50}

def get_kelly_for_gold(
    win_rate: float,
    avg_win: float,
    avg_loss: float,
    symbol: str = "طلای 18 عیار / 750",
) -> Dict:
    """
    Kelly Criterion برای طلای ایران
    با احتساب کارمزد
    """
    try:
        costs = get_gold_costs(symbol)
        
        # Adjust win/loss for costs
        adj_win = avg_win * (1 - costs["total_roundtrip"])
        adj_loss = avg_loss * (1 + costs["total_roundtrip"])
        
        if adj_loss == 0:
            return {"kelly": 0, "error": "avg_loss is zero"}
        
        # Kelly: f = p - (1-p)/b where b = avg_win/avg_loss
        p = win_rate / 100
        b = adj_win / adj_loss if adj_loss != 0 else 0
        
        if b == 0:
            kelly = 0
        else:
            kelly = p - (1 - p) / b
        
        # Conservative: quarter Kelly
        quarter_kelly = kelly / 4
        
        # Cap at 25% for gold (conservative)
        capped_kelly = min(quarter_kelly, 0.25)
        capped_kelly = max(0, capped_kelly)
        
        return {
            "kelly": kelly,
            "quarter_kelly": quarter_kelly,
            "capped_kelly": capped_kelly,
            "recommended_percent": capped_kelly * 100,
            "win_rate": win_rate,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "costs": costs["total_roundtrip"] * 100,
            "interpretation_fa": f"Kelly {kelly*100:.1f}%، یک چهارم {quarter_kelly*100:.1f}%، پیشنهادی {capped_kelly*100:.1f}% سرمایه",
        }
    except Exception as e:
        return {"error": str(e), "kelly": 0}

if __name__ == "__main__":
    print(calculate_position_size(100_000_000, 1, 30_000_000, 29_000_000, "طلای 18 عیار / 750"))
    print(assess_gold_risk("سکه امامی"))
