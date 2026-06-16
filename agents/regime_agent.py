"""
============================================
🔄 MARKET REGIME AGENT

Classifies the market into distinct regimes:

1. STRONG TREND UP    — ride the wave
2. WEAK TREND UP      — cautious longs
3. RANGING            — mean reversion
4. WEAK TREND DOWN    — cautious shorts
5. STRONG TREND DOWN  — ride the wave
6. VOLATILE/CHOPPY    — reduce size or sit out
7. SQUEEZE            — prepare for breakout
8. BREAKOUT           — aggressive entry

WHY THIS IS CRITICAL:
A momentum strategy that wins 70% in trends
will LOSE 70% in ranges.

The WRONG strategy in the WRONG regime = death.
============================================
"""

import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List, Tuple
from collections import deque
from enum import Enum

from agents.base_agent import BaseAgent
from models.signals import (
    AgentOutput, Direction, Strength,
    MarketSnapshot, MarketRegime,
)
from utils.indicators import (
    calculate_adx, calculate_bollinger_bands,
    calculate_atr, calculate_ema, calculate_rsi,
    calculate_supertrend,
)
from config.settings import Settings


class DetailedRegime(Enum):
    STRONG_TREND_UP = "STRONG_TREND_UP"
    WEAK_TREND_UP = "WEAK_TREND_UP"
    RANGING = "RANGING"
    WEAK_TREND_DOWN = "WEAK_TREND_DOWN"
    STRONG_TREND_DOWN = "STRONG_TREND_DOWN"
    VOLATILE_CHOPPY = "VOLATILE_CHOPPY"
    SQUEEZE = "SQUEEZE"
    BREAKOUT = "BREAKOUT"


# Strategy recommendations per regime
REGIME_STRATEGIES = {
    DetailedRegime.STRONG_TREND_UP: {
        "primary": "Momentum long",
        "avoid": "Mean reversion shorts",
        "sl_multiplier": 1.5,
        "size_multiplier": 1.2,
        "min_confidence": 65,
    },
    DetailedRegime.WEAK_TREND_UP: {
        "primary": "Pullback long",
        "avoid": "Breakout chasing",
        "sl_multiplier": 1.2,
        "size_multiplier": 1.0,
        "min_confidence": 70,
    },
    DetailedRegime.RANGING: {
        "primary": "Mean reversion",
        "avoid": "Breakout, Momentum",
        "sl_multiplier": 0.8,
        "size_multiplier": 0.8,
        "min_confidence": 75,
    },
    DetailedRegime.WEAK_TREND_DOWN: {
        "primary": "Pullback short",
        "avoid": "Breakout chasing",
        "sl_multiplier": 1.2,
        "size_multiplier": 1.0,
        "min_confidence": 70,
    },
    DetailedRegime.STRONG_TREND_DOWN: {
        "primary": "Momentum short",
        "avoid": "Mean reversion longs",
        "sl_multiplier": 1.5,
        "size_multiplier": 1.2,
        "min_confidence": 65,
    },
    DetailedRegime.VOLATILE_CHOPPY: {
        "primary": "Reduce size or sit out",
        "avoid": "ALL directional",
        "sl_multiplier": 2.0,
        "size_multiplier": 0.5,
        "min_confidence": 85,
    },
    DetailedRegime.SQUEEZE: {
        "primary": "Prepare for breakout",
        "avoid": "Large positions until breakout",
        "sl_multiplier": 1.0,
        "size_multiplier": 0.7,
        "min_confidence": 75,
    },
    DetailedRegime.BREAKOUT: {
        "primary": "Breakout entry",
        "avoid": "Fading the move",
        "sl_multiplier": 1.3,
        "size_multiplier": 1.3,
        "min_confidence": 70,
    },
}


class RegimeAgent(BaseAgent):
    """
    Classifies market regime and adjusts system behavior.

    Detection uses:
    1. ADX (trend presence and strength)
    2. ADX slope (trend developing or dying)
    3. Bollinger Width (volatility regime)
    4. Price position relative to EMAs
    5. Supertrend state
    6. Candle structure consistency
    7. Regime transition detection
    """

    def __init__(self, settings: Settings):
        super().__init__("regime", settings)
        self.th = settings.thresholds

        self.current_regime = DetailedRegime.RANGING
        self.regime_history: deque = deque(maxlen=500)
        self.regime_duration = 0     # how long in current regime
        self.previous_regime = DetailedRegime.RANGING
        self.transition_detected = False

    def analyze(
        self, df: pd.DataFrame, snapshot: MarketSnapshot
    ) -> AgentOutput:

        warnings = []
        details = {}

        if len(df) < self.th.regime_lookback:
            return self._neutral_output("Insufficient data for regime detection")

        df = df.tail(200).copy()  # 200 rows stable for ADX(14)/BB(20)/EMA(50) — was 500 (wasted compute)

        close = df['close']

        # ── 1. ADX ANALYSIS ──
        adx_data = calculate_adx(df, 14)
        adx = adx_data['adx'].iloc[-1]
        plus_di = adx_data['plus_di'].iloc[-1]
        minus_di = adx_data['minus_di'].iloc[-1]

        if pd.isna(adx):
            adx = 0.0
            plus_di = 0.0
            minus_di = 0.0
            self.logger.debug("ADX is NaN (likely flat price data) — defaulting to 0")

        # ADX slope (trending up = strengthening)
        adx_slope = 0
        if len(adx_data['adx']) >= 5:
            adx_values = adx_data['adx'].tail(5).values
            valid = adx_values[~np.isnan(adx_values)]
            if len(valid) >= 3:
                adx_slope = np.polyfit(
                    range(len(valid)), valid, 1
                )[0]

        details["adx"] = round(adx, 1)
        details["adx_slope"] = round(adx_slope, 3)
        details["plus_di"] = round(plus_di, 1)
        details["minus_di"] = round(minus_di, 1)

        # ── 2. BOLLINGER WIDTH ──
        bb = calculate_bollinger_bands(close, 20, 2.0)
        bb_width = bb['width'].iloc[-1]
        avg_bb_width = bb['width'].tail(
            self.th.regime_lookback
        ).mean()

        if pd.isna(bb_width) or pd.isna(avg_bb_width):
            bb_ratio = 1.0
        else:
            bb_ratio = bb_width / max(avg_bb_width, 0.01)

        details["bb_width"] = round(bb_width, 2) \
            if not pd.isna(bb_width) else 0
        details["bb_ratio"] = round(bb_ratio, 2)

        # ── 3. EMA STRUCTURE ──
        ema9 = calculate_ema(close, 9).iloc[-1]
        ema21 = calculate_ema(close, 21).iloc[-1]
        ema50_series = calculate_ema(close, min(50, len(close) - 1))
        ema50 = ema50_series.iloc[-1] if len(ema50_series) > 0 \
            else close.iloc[-1]
        price = close.iloc[-1]

        ema_bullish = (price > ema9 > ema21 > ema50)
        ema_bearish = (price < ema9 < ema21 < ema50)

        details["ema_structure"] = (
            "BULLISH_STACK" if ema_bullish
            else "BEARISH_STACK" if ema_bearish
            else "MIXED"
        )

        # ── 4. SUPERTREND ──
        st = calculate_supertrend(df, 10, 3.0)
        st_dir = st['direction'].iloc[-1]
        details["supertrend"] = (
            "BULLISH" if st_dir == 1 else "BEARISH"
        )

        # ── 5. CANDLE CONSISTENCY ──
        if len(df) >= 10:
            last_10 = df.tail(10)
            bull_candles = sum(
                1 for _, r in last_10.iterrows()
                if r['close'] > r['open']
            )
            bear_candles = 10 - bull_candles

            candle_consistency = max(bull_candles, bear_candles) / 10
            details["candle_consistency"] = (
                f"{candle_consistency:.0%} "
                f"({'Bull' if bull_candles > bear_candles else 'Bear'})"
            )
        else:
            candle_consistency = 0.5

        # ══════════════════════════════════════
        # REGIME CLASSIFICATION
        # ══════════════════════════════════════

        new_regime = self._classify_regime(
            adx=adx,
            adx_slope=adx_slope,
            plus_di=plus_di,
            minus_di=minus_di,
            bb_ratio=bb_ratio,
            ema_bullish=ema_bullish,
            ema_bearish=ema_bearish,
            st_dir=st_dir,
            candle_consistency=candle_consistency,
        )

        # ── 6. TRANSITION DETECTION ──
        self.transition_detected = (
            new_regime != self.current_regime
        )

        if self.transition_detected:
            self.previous_regime = self.current_regime
            self.current_regime = new_regime
            self.regime_duration = 0

            details["transition"] = (
                f"⚡ REGIME CHANGE: "
                f"{self.previous_regime.value} → "
                f"{new_regime.value}"
            )
            warnings.append(
                f"🔄 Regime transition detected: "
                f"{self.previous_regime.value} → "
                f"{new_regime.value}"
            )
        else:
            self.regime_duration += 1

        # Record history
        self.regime_history.append({
            "time": snapshot.timestamp,
            "regime": new_regime.value,
            "adx": adx,
        })

        # ── 7. STRATEGY RECOMMENDATION ──
        strategy = REGIME_STRATEGIES.get(
            new_regime, REGIME_STRATEGIES[DetailedRegime.RANGING]
        )
        details["regime"] = new_regime.value
        details["regime_duration"] = self.regime_duration
        details["strategy"] = strategy

        # ── CONFIDENCE AND DIRECTION ──
        if new_regime in (
            DetailedRegime.STRONG_TREND_UP,
            DetailedRegime.WEAK_TREND_UP,
        ):
            direction = Direction.BULLISH
            confidence = min(85, 50 + adx)
        elif new_regime in (
            DetailedRegime.STRONG_TREND_DOWN,
            DetailedRegime.WEAK_TREND_DOWN,
        ):
            direction = Direction.BEARISH
            confidence = min(85, 50 + adx)
        elif new_regime == DetailedRegime.VOLATILE_CHOPPY:
            direction = Direction.NEUTRAL
            confidence = 25
            warnings.append(
                "⚠️ CHOPPY regime — most strategies will fail"
            )
        elif new_regime == DetailedRegime.SQUEEZE:
            direction = Direction.NEUTRAL
            confidence = 55
            warnings.append(
                "🔥 SQUEEZE — breakout imminent, wait for direction"
            )
        elif new_regime == DetailedRegime.BREAKOUT:
            if plus_di > minus_di:
                direction = Direction.BULLISH
            else:
                direction = Direction.BEARISH
            confidence = 75
        else:
            direction = Direction.NEUTRAL
            confidence = 50

        if confidence >= 70:
            strength = Strength.STRONG
        elif confidence >= 45:
            strength = Strength.MODERATE
        else:
            strength = Strength.WEAK

        return AgentOutput(
            agent_name=self.name,
            timestamp=snapshot.timestamp,
            direction=direction,
            confidence=round(confidence, 1),
            strength=strength,
            details=details,
            warnings=warnings,
        )

    def _classify_regime(
        self,
        adx: float,
        adx_slope: float,
        plus_di: float,
        minus_di: float,
        bb_ratio: float,
        ema_bullish: bool,
        ema_bearish: bool,
        st_dir: int,
        candle_consistency: float,
    ) -> DetailedRegime:
        """Multi-factor regime classification"""

        is_trending = adx >= self.th.regime_adx_trending
        is_strong_trend = adx >= self.th.regime_adx_strong_trend
        is_ranging = adx < self.th.regime_adx_ranging

        is_squeeze = bb_ratio < 0.5
        is_expanded = bb_ratio > 2.0

        is_bullish_di = plus_di > minus_di
        trend_strengthening = adx_slope > 0.5

        # ── SQUEEZE ──
        if is_squeeze and not is_trending:
            return DetailedRegime.SQUEEZE

        # ── BREAKOUT (was squeeze, now expanding) ──
        if (self.current_regime == DetailedRegime.SQUEEZE and
            is_expanded and is_trending):
            return DetailedRegime.BREAKOUT

        # ── STRONG TREND UP ──
        if (is_strong_trend and is_bullish_di and
            ema_bullish and st_dir == 1 and
            candle_consistency >= 0.7):
            return DetailedRegime.STRONG_TREND_UP

        # ── STRONG TREND DOWN ──
        if (is_strong_trend and not is_bullish_di and
            ema_bearish and st_dir == -1 and
            candle_consistency >= 0.7):
            return DetailedRegime.STRONG_TREND_DOWN

        # ── WEAK TREND UP ──
        if (is_trending and is_bullish_di and
            (ema_bullish or st_dir == 1)):
            return DetailedRegime.WEAK_TREND_UP

        # ── WEAK TREND DOWN ──
        if (is_trending and not is_bullish_di and
            (ema_bearish or st_dir == -1)):
            return DetailedRegime.WEAK_TREND_DOWN

        # ── VOLATILE CHOPPY ──
        if is_expanded and not is_trending:
            return DetailedRegime.VOLATILE_CHOPPY

        # ── RANGING ──
        if is_ranging:
            return DetailedRegime.RANGING

        # ── DEFAULT ──
        return DetailedRegime.RANGING

    def get_regime_info(self) -> Dict:
        """Get current regime with strategy"""
        strategy = REGIME_STRATEGIES.get(
            self.current_regime,
            REGIME_STRATEGIES[DetailedRegime.RANGING],
        )
        return {
            "current": self.current_regime.value,
            "duration": self.regime_duration,
            "previous": self.previous_regime.value,
            "strategy": strategy,
            "transition": self.transition_detected,
        }
