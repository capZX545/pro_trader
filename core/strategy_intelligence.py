"""
Strategy Intelligence Module - هوش استراتژی

Automatically selects the best strategy for a given chart/timeframe
based on market regime, timeframe suitability, historical performance,
and recent forward testing.

This is the brain that teaches the bot how to choose strategies.
"""

import re
import time
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional
import numpy as np
import pandas as pd

# Timeframe order for scoring
TF_ORDER = ["1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "12h", "1d", "3d", "1wk", "1mo"]
TF_INDEX = {tf: i for i, tf in enumerate(TF_ORDER)}

# Market regimes
REGIMES = {
    "strong_trend_bull": {"fa": "روند صعودی قوی", "en": "Strong Bull Trend"},
    "strong_trend_bear": {"fa": "روند نزولی قوی", "en": "Strong Bear Trend"},
    "weak_trend_bull": {"fa": "روند صعودی ضعیف", "en": "Weak Bull Trend"},
    "weak_trend_bear": {"fa": "روند نزولی ضعیف", "en": "Weak Bear Trend"},
    "ranging": {"fa": "رنج / خنثی", "en": "Ranging / Sideways"},
    "high_vol_breakout": {"fa": "نوسان بالا - شکست", "en": "High Volatility - Breakout"},
    "low_vol_squeeze": {"fa": "نوسان پایین - فشردگی", "en": "Low Volatility - Squeeze"},
    "volatile_choppy": {"fa": "پرنوسان و نامنظم", "en": "Volatile & Choppy"},
}

# Category suitability by regime (0-100 score)
REGIME_CATEGORY_SCORES = {
    "strong_trend_bull": {
        "Trend": 95, "Momentum": 90, "Smart-Money": 85, "Price-Action": 75,
        "Price Action": 75, "Volume": 70, "Volatility": 60,
        "Mean-Reversion": 20, "Mean Reversion": 20, "Mean reversion": 20
    },
    "strong_trend_bear": {
        "Trend": 95, "Momentum": 90, "Smart-Money": 85, "Price-Action": 75,
        "Price Action": 75, "Volume": 70, "Volatility": 60,
        "Mean-Reversion": 20, "Mean Reversion": 20
    },
    "weak_trend_bull": {
        "Trend": 75, "Momentum": 70, "Smart-Money": 80, "Price-Action": 80,
        "Mean-Reversion": 60, "Mean Reversion": 60, "Volume": 65, "Volatility": 55
    },
    "weak_trend_bear": {
        "Trend": 75, "Momentum": 70, "Smart-Money": 80, "Price-Action": 80,
        "Mean-Reversion": 60, "Mean Reversion": 60, "Volume": 65, "Volatility": 55
    },
    "ranging": {
        "Mean-Reversion": 95, "Mean Reversion": 95, "Mean reversion": 95,
        "Price-Action": 85, "Price Action": 85, "Volatility": 70,
        "Trend": 25, "Momentum": 40, "Smart-Money": 60
    },
    "high_vol_breakout": {
        "Volatility": 95, "Volume": 90, "Momentum": 85, "Price-Action": 80,
        "Trend": 70, "Smart-Money": 75, "Mean-Reversion": 30
    },
    "low_vol_squeeze": {
        "Volatility": 90, "Mean-Reversion": 80, "Mean Reversion": 80,
        "Price-Action": 75, "Volume": 70, "Trend": 40
    },
    "volatile_choppy": {
        "Volatility": 80, "Volume": 75, "Smart-Money": 70,
        "Mean-Reversion": 60, "Trend": 30, "Momentum": 35
    },
}


@dataclass
class MarketAnalysis:
    regime: str
    regime_fa: str
    regime_en: str
    trend_strength: float  # 0-100
    volatility_level: float  # 0-100 (0=low, 100=high)
    volatility_vs_median: float
    adx: float
    rsi: float
    ema_trend: str  # bull/bear/range
    volume_trend: str
    confidence: float  # 0-100
    details: Dict = field(default_factory=dict)


@dataclass
class StrategyScore:
    strategy_id: str
    strategy_name: str
    strategy_name_fa: str
    category: str
    total_score: float
    breakdown: Dict[str, float]  # tf_match, regime_match, historical, success, quality, etc.
    win_rate: Optional[float] = None
    profit_factor: Optional[float] = None
    grade: str = "D"
    success_label: str = ""
    reasoning_fa: str = ""
    reasoning_en: str = ""
    confidence: float = 0.0


@dataclass
class IntelligenceResult:
    symbol: str
    timeframe: str
    market: MarketAnalysis
    best: StrategyScore
    top_5: List[StrategyScore]
    all_scored: List[StrategyScore]
    timestamp: float = field(default_factory=time.time)
    analysis_time_ms: int = 0


def _parse_tf_range(tf_str: str) -> Tuple[int, int]:
    """Parse '1h – 1d' or '15m – 4h' or 'any' into (min_idx, max_idx)"""
    if not tf_str or tf_str.lower() == "any":
        return (0, len(TF_ORDER) - 1)
    
    # Clean up
    s = tf_str.replace("–", "-").replace("—", "-").replace(" ", "")
    # Handle cases like "1d(stocks/indices/BTC-ETHdaily)" -> extract first part
    s = re.split(r'[\(\)]', s)[0]
    
    if "-" in s:
        parts = s.split("-")
        start = parts[0].strip()
        end = parts[-1].strip()
        # Normalize
        start = start.replace("–", "").strip()
        end = end.replace("–", "").strip()
        # Find closest match
        si = TF_INDEX.get(start, 0)
        ei = TF_INDEX.get(end, len(TF_ORDER)-1)
        # If not found, try to find partial
        if start not in TF_INDEX:
            for k in TF_ORDER:
                if k in start or start in k:
                    si = TF_INDEX[k]
                    break
        if end not in TF_INDEX:
            for k in TF_ORDER:
                if k in end or end in k:
                    ei = TF_INDEX[k]
                    break
        return (min(si, ei), max(si, ei))
    else:
        # Single TF
        tf_clean = s.strip()
        if tf_clean in TF_INDEX:
            idx = TF_INDEX[tf_clean]
            return (max(0, idx-1), min(len(TF_ORDER)-1, idx+1))  # ±1 for flexibility
        # Try partial match
        for k in TF_ORDER:
            if k in tf_clean:
                idx = TF_INDEX[k]
                return (max(0, idx-1), min(len(TF_ORDER)-1, idx+1))
        return (0, len(TF_ORDER)-1)


def tf_match_score(strategy_tfs: str, target_tf: str) -> float:
    """Score 0-100 how well strategy's timeframe matches target"""
    if not target_tf:
        return 50.0
    
    target_idx = TF_INDEX.get(target_tf, 5)  # default to 1h
    s_min, s_max = _parse_tf_range(strategy_tfs)
    
    if s_min <= target_idx <= s_max:
        # Perfect match inside range - higher score if closer to center
        center = (s_min + s_max) / 2
        dist = abs(target_idx - center)
        range_size = max(1, s_max - s_min)
        # Score 90-100 if inside, higher if closer to center
        return 100 - (dist / range_size * 20)
    else:
        # Outside range - score based on distance
        if target_idx < s_min:
            dist = s_min - target_idx
        else:
            dist = target_idx - s_max
        # Penalize distance: -15 per TF step
        return max(0, 85 - dist * 15)


def analyze_market_regime(df: pd.DataFrame) -> MarketAnalysis:
    """Analyze market regime from OHLCV data"""
    try:
        from core import indicators as ta
        
        if df is None or len(df) < 50:
            return MarketAnalysis(
                regime="ranging", regime_fa="رنج / خنثی", regime_en="Ranging",
                trend_strength=50, volatility_level=50, volatility_vs_median=1.0,
                adx=20, rsi=50, ema_trend="range", volume_trend="neutral",
                confidence=30, details={"error": "insufficient data"}
            )
        
        close = df['close'] if 'close' in df.columns else df.close
        high = df['high'] if 'high' in df.columns else df.high
        low = df['low'] if 'low' in df.columns else df.low
        volume = df['volume'] if 'volume' in df.columns else None
        
        # EMA trend
        ema50 = ta.ema(close, 50)
        ema200 = ta.ema(close, 200)
        ema50_last = ema50.iloc[-1] if len(ema50) > 0 else close.iloc[-1]
        ema200_last = ema200.iloc[-1] if len(ema200) > 0 else close.iloc[-1]
        price_last = close.iloc[-1]
        
        # ADX for trend strength
        try:
            adx_series, _, _ = ta.adx(df)
            adx_last = float(adx_series.iloc[-1]) if len(adx_series) > 0 and not np.isnan(adx_series.iloc[-1]) else 20.0
        except:
            adx_last = 20.0
        
        # RSI
        try:
            rsi_series = ta.rsi(close)
            rsi_last = float(rsi_series.iloc[-1]) if len(rsi_series) > 0 and not np.isnan(rsi_series.iloc[-1]) else 50.0
        except:
            rsi_last = 50.0
        
        # ATR for volatility
        try:
            atr_series = ta.atr(df)
            atr_last = float(atr_series.iloc[-1]) if len(atr_series) > 0 else 0
            atr_median = float(atr_series.rolling(100).median().iloc[-1]) if len(atr_series) > 100 else atr_last
            vol_vs_median = atr_last / atr_median if atr_median and atr_median != 0 else 1.0
            vol_level = min(100, max(0, (vol_vs_median - 0.5) * 100))  # 0.5x=0, 1.5x=100
        except:
            atr_last = 0
            vol_vs_median = 1.0
            vol_level = 50
        
        # Determine EMA trend
        if price_last > ema50_last > ema200_last:
            ema_trend = "bull"
            trend_strength = min(100, 60 + adx_last)
        elif price_last < ema50_last < ema200_last:
            ema_trend = "bear"
            trend_strength = min(100, 60 + adx_last)
        elif price_last > ema50_last or price_last > ema200_last:
            ema_trend = "weak_bull"
            trend_strength = 40 + adx_last * 0.5
        elif price_last < ema50_last or price_last < ema200_last:
            ema_trend = "weak_bear"
            trend_strength = 40 + adx_last * 0.5
        else:
            ema_trend = "range"
            trend_strength = max(0, 50 - adx_last)
        
        # Volume trend
        if volume is not None and len(volume) > 20:
            vol_ma = volume.rolling(20).mean().iloc[-1]
            vol_last = volume.iloc[-1]
            if vol_last > vol_ma * 1.3:
                volume_trend = "increasing"
            elif vol_last < vol_ma * 0.7:
                volume_trend = "decreasing"
            else:
                volume_trend = "neutral"
        else:
            volume_trend = "neutral"
        
        # Determine regime
        if adx_last > 25 and trend_strength > 70:
            if ema_trend == "bull":
                regime = "strong_trend_bull"
            elif ema_trend == "bear":
                regime = "strong_trend_bear"
            else:
                regime = "strong_trend_bull" if price_last > ema50_last else "strong_trend_bear"
        elif adx_last > 20 and trend_strength > 50:
            if ema_trend in ("bull", "weak_bull"):
                regime = "weak_trend_bull"
            elif ema_trend in ("bear", "weak_bear"):
                regime = "weak_trend_bear"
            else:
                regime = "ranging"
        elif vol_vs_median > 1.5:
            regime = "high_vol_breakout"
        elif vol_vs_median < 0.7:
            regime = "low_vol_squeeze"
        elif vol_level > 70 and adx_last < 20:
            regime = "volatile_choppy"
        else:
            regime = "ranging"
        
        regime_info = REGIMES.get(regime, REGIMES["ranging"])
        
        confidence = 50
        if adx_last > 30:
            confidence += 20
        if abs(price_last - ema50_last) / price_last > 0.02:
            confidence += 10
        if vol_vs_median > 1.2 or vol_vs_median < 0.8:
            confidence += 10
        confidence = min(95, confidence)
        
        return MarketAnalysis(
            regime=regime,
            regime_fa=regime_info["fa"],
            regime_en=regime_info["en"],
            trend_strength=trend_strength,
            volatility_level=vol_level,
            volatility_vs_median=vol_vs_median,
            adx=adx_last,
            rsi=rsi_last,
            ema_trend=ema_trend,
            volume_trend=volume_trend,
            confidence=confidence,
            details={
                "price": float(price_last),
                "ema50": float(ema50_last),
                "ema200": float(ema200_last),
                "atr": float(atr_last) if 'atr_last' in locals() else 0,
            }
        )
    except Exception as e:
        # Fallback
        return MarketAnalysis(
            regime="ranging", regime_fa="رنج / خنثی", regime_en="Ranging",
            trend_strength=50, volatility_level=50, volatility_vs_median=1.0,
            adx=20, rsi=50, ema_trend="range", volume_trend="neutral",
            confidence=30, details={"error": str(e)}
        )


def _get_strategy_performance(sid: str, symbol: str, tf: str) -> Dict:
    """Get historical performance for a strategy"""
    perf = {
        "win_rate": None,
        "profit_factor": None,
        "grade": "D",
        "score": 35,
        "proven": False,
        "success_label": "",
        "pb_stats": None,
    }
    
    try:
        from core import playbook as PB
        pb = PB.stats_for(sid, tf, symbol)
        if pb:
            perf["pb_stats"] = pb
            perf["win_rate"] = pb.get("wr")
            perf["profit_factor"] = pb.get("pf")
            perf["grade"] = pb.get("grade", "D")
            perf["proven"] = True
            # Grade to score
            grade_scores = {"A": 90, "B": 75, "C": 55, "D": 35}
            perf["score"] = grade_scores.get(perf["grade"], 35)
    except:
        pass
    
    try:
        from core import success as SR
        s = SR.get(sid, symbol, tf)
        if s:
            if perf["win_rate"] is None:
                perf["win_rate"] = s.get("wr")
            if perf["profit_factor"] is None:
                perf["profit_factor"] = s.get("pf")
            perf["success_label"] = SR.label(sid, symbol, tf, short=True) or ""
    except:
        pass
    
    try:
        import core.validation as V
        cache = V.load_cache()
        if sid in cache:
            v = cache[sid]
            v_score = v.get("score", 0)
            # Blend with existing score
            if perf["score"] < 50:
                perf["score"] = max(perf["score"], v_score * 0.7)
    except:
        pass
    
    try:
        from core import quality as Q
        qs = Q.score(sid, symbol, tf)
        if qs:
            # Quality score influences
            q_score = qs.get("score", 0)
            if q_score > 70:
                perf["score"] = min(95, perf["score"] + 10)
    except:
        pass
    
    return perf


def score_strategies(symbol: str, tf: str, df: pd.DataFrame, market: MarketAnalysis = None) -> List[StrategyScore]:
    """Score all 196 strategies for given symbol/tf/market regime"""
    if market is None:
        market = analyze_market_regime(df)
    
    import strategies as S
    
    scored = []
    regime_scores = REGIME_CATEGORY_SCORES.get(market.regime, {})
    
    for cls in S.ALL_STRATEGIES:
        sid = cls.id
        
        # TF match
        tf_score = tf_match_score(cls.timeframes, tf)
        
        # Regime match
        # Normalize category for lookup
        cat = cls.category
        # Try exact, then fallback
        regime_score = regime_scores.get(cat, 50)
        # If not found, try case-insensitive or partial
        if regime_score == 50:
            for k, v in regime_scores.items():
                if k.lower() in cat.lower() or cat.lower() in k.lower():
                    regime_score = v
                    break
        
        # Historical performance
        perf = _get_strategy_performance(sid, symbol, tf)
        hist_score = perf["score"]
        
        # Success rate bonus
        success_bonus = 0
        if perf["win_rate"] is not None:
            # WR 50% = 0, 65% = +15, 75% = +25
            if perf["win_rate"] >= 65:
                success_bonus += 15 + (perf["win_rate"] - 65) * 1.0
            elif perf["win_rate"] >= 55:
                success_bonus += (perf["win_rate"] - 50) * 1.0
        
        # PF bonus
        pf_bonus = 0
        if perf["profit_factor"] is not None:
            if perf["profit_factor"] >= 1.5:
                pf_bonus += 10 + (perf["profit_factor"] - 1.5) * 10
            elif perf["profit_factor"] >= 1.2:
                pf_bonus += (perf["profit_factor"] - 1.0) * 10
        
        # Proven bonus
        proven_bonus = 20 if perf["proven"] else 0
        
        # Difficulty adjustment (easier strategies slightly preferred for stability)
        difficulty_penalty = (cls.difficulty - 1) * 2  # 0-8 penalty
        
        # Combine with weights
        # Weights: TF 30%, Regime 30%, Historical 25%, Success/PF 15%
        total = (
            tf_score * 0.30 +
            regime_score * 0.30 +
            hist_score * 0.25 +
            (success_bonus + pf_bonus + proven_bonus) * 0.15 -
            difficulty_penalty
        )
        total = max(0, min(100, total))
        
        # Reasoning
        reasoning_fa_parts = []
        reasoning_en_parts = []
        
        if tf_score >= 85:
            reasoning_fa_parts.append(f"تایم‌فریم {tf} کاملاً مناسب ({cls.timeframes})")
            reasoning_en_parts.append(f"Timeframe {tf} perfect match ({cls.timeframes})")
        elif tf_score >= 70:
            reasoning_fa_parts.append(f"تایم‌فریم {tf} مناسب ({cls.timeframes})")
            reasoning_en_parts.append(f"Timeframe {tf} good match ({cls.timeframes})")
        else:
            reasoning_fa_parts.append(f"تایم‌فریم {tf} متوسط ({cls.timeframes})")
            reasoning_en_parts.append(f"Timeframe {tf} moderate ({cls.timeframes})")
        
        if regime_score >= 80:
            reasoning_fa_parts.append(f"برای {market.regime_fa} عالیه ({cat})")
            reasoning_en_parts.append(f"Excellent for {market.regime_en} ({cat})")
        elif regime_score >= 60:
            reasoning_fa_parts.append(f"برای {market.regime_fa} خوبه")
            reasoning_en_parts.append(f"Good for {market.regime_en}")
        else:
            reasoning_fa_parts.append(f"برای {market.regime_fa} معمولی")
            reasoning_en_parts.append(f"Moderate for {market.regime_en}")
        
        if perf["proven"]:
            reasoning_fa_parts.append(f"اثبات شده Grade {perf['grade']} - WR {perf['win_rate']:.0f}% PF {perf['profit_factor']:.1f}" if perf["win_rate"] else f"اثبات شده Grade {perf['grade']}")
            reasoning_en_parts.append(f"Proven Grade {perf['grade']} - WR {perf['win_rate']:.0f}% PF {perf['profit_factor']:.1f}" if perf["win_rate"] else f"Proven Grade {perf['grade']}")
        
        if perf["win_rate"] and perf["win_rate"] >= 65:
            reasoning_fa_parts.append(f"وین‌ریت بالا {perf['win_rate']:.0f}%")
            reasoning_en_parts.append(f"High WR {perf['win_rate']:.0f}%")
        
        reasoning_fa = " • ".join(reasoning_fa_parts)
        reasoning_en = " • ".join(reasoning_en_parts)
        
        # Confidence based on total and data availability
        conf = 50
        if perf["proven"]:
            conf += 20
        if perf["win_rate"] is not None:
            conf += 10
        if tf_score >= 80 and regime_score >= 70:
            conf += 15
        conf = min(95, conf * (total / 100))
        
        scored.append(StrategyScore(
            strategy_id=sid,
            strategy_name=cls.name_en,
            strategy_name_fa=cls.name_fa,
            category=cat,
            total_score=total,
            breakdown={
                "tf_match": tf_score,
                "regime_match": regime_score,
                "historical": hist_score,
                "success_bonus": success_bonus,
                "pf_bonus": pf_bonus,
                "proven_bonus": proven_bonus,
            },
            win_rate=perf["win_rate"],
            profit_factor=perf["profit_factor"],
            grade=perf["grade"],
            success_label=perf["success_label"],
            reasoning_fa=reasoning_fa,
            reasoning_en=reasoning_en,
            confidence=conf,
        ))
    
    # Sort by total score descending
    scored.sort(key=lambda x: x.total_score, reverse=True)
    return scored


def select_best_strategy(symbol: str, tf: str, df: pd.DataFrame = None, market: MarketAnalysis = None) -> IntelligenceResult:
    """
    Main entry: select best strategy for symbol/tf
    
    This is the brain - teaches bot how to choose.
    """
    start = time.time()
    
    if df is None:
        try:
            from core.data import get_ohlcv
            df, _ = get_ohlcv(symbol, tf), True
        except:
            try:
                from core.data import generate_synthetic
                df = generate_synthetic(seed=abs(hash(symbol+tf)) % 10000)
            except:
                df = None
    
    if market is None:
        market = analyze_market_regime(df)
    
    all_scored = score_strategies(symbol, tf, df, market)
    
    best = all_scored[0] if all_scored else None
    top_5 = all_scored[:5]
    
    elapsed_ms = int((time.time() - start) * 1000)
    
    return IntelligenceResult(
        symbol=symbol,
        timeframe=tf,
        market=market,
        best=best,
        top_5=top_5,
        all_scored=all_scored,
        analysis_time_ms=elapsed_ms,
    )


def auto_analyze(symbol: str, tf: str, df: pd.DataFrame = None) -> Dict:
    """
    Auto-run analysis with best strategy - returns signals
    """
    result = select_best_strategy(symbol, tf, df)
    
    if not result.best:
        return {"error": "No strategy found"}
    
    try:
        import strategies as S
        from core.backtest import run_backtest
        
        if df is None:
            from core.data import get_ohlcv
            df, _ = get_ohlcv(symbol, tf), True
        
        sid = result.best.strategy_id
        strat = S.get(sid)
        res = strat.run(df)
        bt = run_backtest(df, res)
        
        # Last signal
        sig = res.signal
        last_idx = None
        last_side = 0
        if len(sig) > 0:
            # Find last non-zero
            nz = np.where(sig.values != 0)[0]
            if len(nz) > 0:
                last_idx = int(nz[-1])
                last_side = int(sig.values[last_idx])
        
        return {
            "intelligence": result,
            "backtest": bt,
            "result": res,
            "last_signal": {
                "index": last_idx,
                "side": last_side,
                "bars_ago": len(df) - 1 - last_idx if last_idx is not None else None,
            },
            "stats": bt.stats if bt else {},
        }
    except Exception as e:
        return {
            "intelligence": result,
            "error": str(e),
        }


# ---- Learning / Teaching the bot ----

def learn_from_forward(symbol: str = None, tf: str = None):
    """
    Learn from forward testing results - adjust scoring
    This teaches the bot what works recently
    """
    try:
        from core import forward as FW
        report = FW.report()
        # Could adjust weights based on recent forward performance
        # For now, just return report - future: update regime scores
        return report
    except Exception as e:
        return {"error": str(e)}


def get_intelligence_summary(symbol: str, tf: str, lang: str = "en") -> str:
    """Get human-readable summary"""
    res = select_best_strategy(symbol, tf)
    
    if lang == "fa":
        txt = f"""🧠 هوش استراتژی - {symbol} {tf}

بازار: {res.market.regime_fa} (ADX {res.market.adx:.0f}, RSI {res.market.rsi:.0f})
قدرت روند: {res.market.trend_strength:.0f}% | نوسان: {res.market.volatility_level:.0f}%
اطمینان تحلیل بازار: {res.market.confidence:.0f}%

✅ بهترین استراتژی: {res.best.strategy_name_fa} ({res.best.strategy_id})
دسته: {res.best.category} | امتیاز: {res.best.total_score:.0f}/100 | اطمینان: {res.best.confidence:.0f}%
Grade: {res.best.grade} | {res.best.success_label}
دلیل: {res.best.reasoning_fa}

🔝 5 استراتژی برتر:
"""
        for i, s in enumerate(res.top_5, 1):
            txt += f"{i}. {s.strategy_name_fa} - {s.total_score:.0f} - {s.reasoning_fa[:60]}...\n"
        
        txt += f"\n⏱ تحلیل در {res.analysis_time_ms}ms"
        return txt
    else:
        txt = f"""🧠 Strategy Intelligence - {symbol} {tf}

Market: {res.market.regime_en} (ADX {res.market.adx:.0f}, RSI {res.market.rsi:.0f})
Trend Strength: {res.market.trend_strength:.0f}% | Volatility: {res.market.volatility_level:.0f}%
Market Confidence: {res.market.confidence:.0f}%

✅ Best Strategy: {res.best.strategy_name} ({res.best.strategy_id})
Category: {res.best.category} | Score: {res.best.total_score:.0f}/100 | Confidence: {res.best.confidence:.0f}%
Grade: {res.best.grade} | {res.best.success_label}
Reason: {res.best.reasoning_en}

🔝 Top 5 Strategies:
"""
        for i, s in enumerate(res.top_5, 1):
            txt += f"{i}. {s.strategy_name} - {s.total_score:.0f} - {s.reasoning_en[:60]}...\n"
        
        txt += f"\n⏱ Analyzed in {res.analysis_time_ms}ms"
        return txt
