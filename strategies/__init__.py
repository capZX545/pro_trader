import warnings as _w
import pandas as _pd
try:  # pandas ≥2.2: opt in to the future (non-downcasting) behaviour so .fillna(False) on bool masks stays bool and silent
    _pd.set_option("future.no_silent_downcasting", True)
except Exception:
    pass
_w.filterwarnings("ignore", category=FutureWarning, module=r"strategies\..*")
from .base import Strategy, StrategyResult
from . import trend, meanrev, priceaction, masters, bots, ensemble, highwr, masters2, bots2, bots3, scalp, orderflow, ichimoku, indicator_signals, world_masters, world_masters2

ALL_STRATEGIES = [
    # Trend
    trend.EMACross, trend.TripleEMA, trend.GoldenCross, trend.SupertrendStrat, trend.IchimokuStrat,
    trend.ParabolicSARStrat, trend.TurtleBreakout, trend.ADXTrend, trend.HullMA,
    # Momentum
    trend.MACDTrend, meanrev.StochRSIStrat, meanrev.RSIDivergence,
    # Mean reversion
    meanrev.RSIReversal, meanrev.RSI2Connors, meanrev.BollingerBounce, meanrev.VWAPReversion,
    # Volatility
    meanrev.BollingerSqueeze,
    # Volume
    meanrev.OBVDivergence, meanrev.MFIStrat,
    # Price action
    priceaction.PinBar, priceaction.EngulfingStrat, priceaction.InsideBarBreakout, priceaction.ThreeBarReversal,
    priceaction.SupportResistanceBreak, priceaction.FibPullback, priceaction.OpeningRangeBreakout,
    # Smart money
    priceaction.SupplyDemand, priceaction.ICTFairValueGap, priceaction.ICTOrderBlock,
    priceaction.LiquiditySweep, priceaction.BOSMarketStructure, priceaction.WyckoffSpring,
    # Masters & quantified research (2026 research pass)
    masters.RaschkeHolyGrail, masters.RaschkeAnti, masters.LarryWilliamsVolBreakout, masters.TripleRSI,
    masters.IBSMeanReversion, masters.TurnaroundTuesday, masters.NR7Breakout, masters.ICTSilverBullet,
    masters.PowerOfThree, masters.FalseBreakout,
    # Ported from open-source bots & top community scripts
    bots.FT_EMA800Cross, bots.FT_DoubleEMATrend, bots.FT_RSIDirectional, bots.BinHV45, bots.ClucMay, bots.BbandRsiBot,
    bots.ADXMomentumBot, bots.MACDCCIBot, bots.WaveTrendStrat, bots.ElderImpulse, bots.ChandelierChopStrat, bots.NFILiteDip,
    ensemble.RobustEnsemble,
    highwr.ConnorsRSI2Classic, highwr.CumulativeRSI2, highwr.Double7, highwr.ThreeDayHighLow, highwr.IBSLow,
    highwr.RSI2Dual, highwr.BBLowerRSI2, highwr.HighWRPortfolio,
    masters2.WilderDMIExtreme, masters2.LaneStochDivergence, masters2.AppelMACD, masters2.BollingerWBottom, masters2.ElderTripleScreen,
    masters2.WilliamsAlligatorFractal, masters2.WeinsteinStage2, masters2.MinerviniTrendTemplate, masters2.ONeilCupHandle,
    masters2.ChaikinMoneyFlow, masters2.ChandeAroonCMO, masters2.KaufmanKAMA, masters2.LambertCCI, masters2.WilliamsPercentR, masters2.PringKST,
    bots2.JesseTrendATR, bots2.OctoBotDailyMix, bots2.SuperalgosLRC, bots2.HummingbotFairValue, bots2.GekkoMACD, bots2.GekkoDEMA,
    bots2.ZenbotTrendEMA, bots2.GridBotSignal, bots2.DCABotSignal, bots2.ElderForceIndex2, bots2.ONeilCANSLIM, bots2.MurphyConfirmation,
    bots2.NisonCandleReversal, bots2.BulkowskiTopPatterns, bots2.ChanStatArb, bots2.RegimeAdaptiveEnsemble,
    bots3.ChanKalmanMR, bots3.ElderImpulseSafeZone, bots3.JesseAnchorPullback, bots3.ONeilSellRules, bots3.FreqtradeSample, bots3.DaveyRobustBreakout,
    # Phase 16: low-timeframe / scalping research pass (VWAP, order-flow, Brooks, Volman, Crabel, Market Profile, funding)
    *scalp.SCALP_STRATEGIES,
    *orderflow.ORDERFLOW_STRATEGIES,
    *ichimoku.ICHIMOKU_STRATEGIES,
    *indicator_signals.INDICATOR_STRATEGIES,
    *world_masters.WORLD_STRATEGIES,
    *world_masters2.WORLD_MASTERS2_STRATEGIES,
]

REGISTRY = {s.id: s for s in ALL_STRATEGIES}
CATEGORIES = sorted({s.category for s in ALL_STRATEGIES})


def get(strategy_id: str, **params) -> Strategy:
    return REGISTRY[strategy_id](**params)
