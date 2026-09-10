"""
Correlation Analysis — تحلیل همبستگی
همبستگی بین طلای ایران، دلار، انس جهانی، و سایر بازارها

Features:
- Correlation between Iran Gold and USD/IRR
- Correlation between Iran Gold and XAU/USD
- Correlation between coins and gold
- Lead-lag analysis (which moves first?)
- Dollar impact on gold price
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
import time

def calculate_correlation(df1: pd.DataFrame, df2: pd.DataFrame, window: int = 30) -> Dict:
    """
    محاسبه همبستگی بین دو سری قیمت
    Returns: correlation, lead-lag, etc.
    """
    try:
        # Align indices
        combined = pd.DataFrame({
            "close1": df1["close"],
            "close2": df2["close"],
        }).dropna()
        
        if len(combined) < window:
            return {"error": "Not enough data"}
        
        # Rolling correlation
        rolling_corr = combined["close1"].pct_change().rolling(window).corr(combined["close2"].pct_change())
        
        # Overall correlation
        overall_corr = combined["close1"].pct_change().corr(combined["close2"].pct_change())
        
        # Lead-lag: which moves first?
        # Calculate correlation with lagged series
        best_lag = 0
        best_corr = overall_corr
        for lag in range(-5, 6):
            if lag == 0:
                continue
            try:
                if lag > 0:
                    c = combined["close1"].pct_change().shift(lag).corr(combined["close2"].pct_change())
                else:
                    c = combined["close1"].pct_change().corr(combined["close2"].pct_change().shift(-lag))
                if abs(c) > abs(best_corr):
                    best_corr = c
                    best_lag = lag
            except Exception:
                continue
        
        return {
            "overall_correlation": float(overall_corr) if not np.isnan(overall_corr) else 0,
            "rolling_correlation": float(rolling_corr.iloc[-1]) if len(rolling_corr) > 0 and not np.isnan(rolling_corr.iloc[-1]) else 0,
            "rolling_mean": float(rolling_corr.mean()) if len(rolling_corr) > 0 else 0,
            "best_lag": best_lag,
            "best_lag_corr": float(best_corr),
            "lead": "df1 leads" if best_lag > 0 else "df2 leads" if best_lag < 0 else "synchronized",
            "strength": "strong" if abs(overall_corr) > 0.7 else "moderate" if abs(overall_corr) > 0.4 else "weak",
        }
    except Exception as e:
        return {"error": str(e)}

def analyze_iran_gold_correlations(timeframe: str = "1d", window: int = 30) -> Dict:
    """
    تحلیل همبستگی طلای ایران با دلار و انس
    """
    try:
        from core.data import get_ohlcv
        from core import iran_gold
        
        results = {}
        
        # Get data
        try:
            # Iran Gold 18K
            gold_18k = iran_gold.get_ohlcv_iran_gold("طلای 18 عیار / 750", timeframe, limit=100)
        except Exception:
            try:
                gold_18k = get_ohlcv("طلای 18 عیار / 750", timeframe)
            except Exception as e:
                return {"error": f"Cannot get Iran Gold data: {e}"}
        
        try:
            usd_irr = iran_gold.get_ohlcv_iran_gold("دلار آزاد", timeframe, limit=100)
        except Exception:
            try:
                usd_irr = get_ohlcv("دلار آزاد", timeframe)
            except Exception:
                usd_irr = None
        
        try:
            xau_usd = get_ohlcv("Gold (XAU/USD)", timeframe, limit=100)
        except Exception:
            xau_usd = None
        
        try:
            emami = iran_gold.get_ohlcv_iran_gold("سکه امامی", timeframe, limit=100)
        except Exception:
            emami = None
        
        # Correlations
        if usd_irr is not None and len(usd_irr) >= window:
            corr = calculate_correlation(gold_18k, usd_irr, window)
            results["gold18k_vs_usd"] = {
                "pair": "طلای 18 عیار vs دلار آزاد",
                "pair_en": "Gold 18K vs USD/IRR",
                **corr,
                "interpretation_fa": f"همبستگی {corr.get('overall_correlation',0):.2f} - "
                                     f"{'دلار تأثیر قوی دارد' if abs(corr.get('overall_correlation',0))>0.7 else 'تأثیر متوسط' if abs(corr.get('overall_correlation',0))>0.4 else 'تأثیر ضعیف'}",
                "interpretation_en": f"Correlation {corr.get('overall_correlation',0):.2f}",
            }
        
        if xau_usd is not None and len(xau_usd) >= window:
            corr = calculate_correlation(gold_18k, xau_usd, window)
            results["gold18k_vs_xau"] = {
                "pair": "طلای 18 عیار vs انس جهانی",
                "pair_en": "Gold 18K vs XAU/USD",
                **corr,
                "interpretation_fa": f"همبستگی {corr.get('overall_correlation',0):.2f} با انس جهانی",
                "interpretation_en": f"Correlation {corr.get('overall_correlation',0):.2f} with XAU",
            }
        
        if emami is not None and len(emami) >= window:
            corr = calculate_correlation(gold_18k, emami, window)
            results["gold18k_vs_emami"] = {
                "pair": "طلای 18 عیار vs سکه امامی",
                "pair_en": "Gold 18K vs Emami Coin",
                **corr,
            }
        
        # Dollar vs XAU (global factors)
        if usd_irr is not None and xau_usd is not None and len(usd_irr) >= window and len(xau_usd) >= window:
            corr = calculate_correlation(usd_irr, xau_usd, window)
            results["usd_vs_xau"] = {
                "pair": "دلار آزاد vs انس جهانی",
                "pair_en": "USD/IRR vs XAU/USD",
                **corr,
            }
        
        return results
    except Exception as e:
        return {"error": str(e)}

def get_dollar_impact_on_gold() -> Dict:
    """
    تحلیل تأثیر دلار بر طلای ایران
    فرمول: طلای ایران = انس * دلار / 31.1035 * عیار
    بنابراین: % تغییر طلا ≈ % تغییر انس + % تغییر دلار
    """
    try:
        from core.data import get_ohlcv
        from core import iran_gold
        
        # Get recent changes
        try:
            gold_df = iran_gold.get_ohlcv_iran_gold("طلای 18 عیار / 750", "1d", limit=30)
            usd_df = iran_gold.get_ohlcv_iran_gold("دلار آزاد", "1d", limit=30)
            xau_df = get_ohlcv("Gold (XAU/USD)", "1d", limit=30)
        except Exception as e:
            return {"error": str(e)}
        
        # Calculate daily returns
        gold_ret = gold_df["close"].pct_change().iloc[-1]
        usd_ret = usd_df["close"].pct_change().iloc[-1] if usd_df is not None else 0
        xau_ret = xau_df["close"].pct_change().iloc[-1] if xau_df is not None else 0
        
        # Expected gold return from formula
        expected_gold_ret = usd_ret + xau_ret  # approximate
        
        # Difference = bubble change or other factors
        diff = gold_ret - expected_gold_ret
        
        return {
            "gold_18k_change": float(gold_ret * 100),
            "usd_change": float(usd_ret * 100),
            "xau_change": float(xau_ret * 100),
            "expected_gold_change": float(expected_gold_ret * 100),
            "unexplained": float(diff * 100),
            "usd_contribution": float((usd_ret / gold_ret * 100) if gold_ret != 0 else 0),
            "xau_contribution": float((xau_ret / gold_ret * 100) if gold_ret != 0 else 0),
            "interpretation_fa": (
                f"طلا {gold_ret*100:+.2f}%: "
                f"دلار {usd_ret*100:+.2f}% + انس {xau_ret*100:+.2f}% = {expected_gold_ret*100:+.2f}% انتظاری، "
                f"اختلاف {diff*100:+.2f}% (حباب/عوامل دیگر)"
            ),
            "interpretation_en": (
                f"Gold {gold_ret*100:+.2f}%: USD {usd_ret*100:+.2f}% + XAU {xau_ret*100:+.2f}% = {expected_gold_ret*100:+.2f}% expected"
            ),
        }
    except Exception as e:
        return {"error": str(e)}

def get_correlation_matrix(symbols: List[str] = None, timeframe: str = "1d") -> pd.DataFrame:
    """
    ماتریس همبستگی بین چند نماد طلای ایران
    """
    if symbols is None:
        symbols = ["طلای 18 عیار / 750", "سکه امامی", "نیم سکه", "دلار آزاد", "انس طلا"]
    
    try:
        from core import iran_gold
        from core.data import get_ohlcv
        
        data = {}
        for sym in symbols:
            try:
                if "انس" in sym or "Gold (XAU" in sym:
                    df = get_ohlcv("Gold (XAU/USD)", timeframe, limit=60)
                else:
                    df = iran_gold.get_ohlcv_iran_gold(sym, timeframe, limit=60)
                data[sym] = df["close"].pct_change().dropna()
            except Exception:
                continue
        
        if len(data) < 2:
            return pd.DataFrame()
        
        # Align and create DataFrame
        df_combined = pd.DataFrame(data).dropna()
        corr_matrix = df_combined.corr()
        
        return corr_matrix
    except Exception as e:
        print(f"[correlation] matrix failed: {e}")
        return pd.DataFrame()

if __name__ == "__main__":
    print("=== Correlation Analysis ===")
    result = analyze_iran_gold_correlations()
    import json
    print(json.dumps(result, indent=2, ensure_ascii=False))
    
    print("\n=== Dollar Impact ===")
    impact = get_dollar_impact_on_gold()
    print(json.dumps(impact, indent=2, ensure_ascii=False))
