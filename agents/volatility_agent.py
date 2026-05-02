"""
============================================
🌊 VOLATILITY AGENT
Why: Volatility tells you WHEN a big move is coming.
     Squeeze → Expansion = explosive move.
     High vol = wide stops. Low vol = tight stops.
============================================
"""

import pandas as pd
import numpy as np
from datetime import datetime

from agents.base_agent import BaseAgent, AgentCategory
from models.signals import (
    AgentOutput, Direction, Strength, MarketSnapshot, MarketRegime
)
from utils.indicators import calculate_atr
from config.settings import Settings


class VolatilityAgent(BaseAgent):
    """
    Detects:
    - Bollinger Band squeeze (compression → expansion)
    - ATR trend (expanding or contracting)
    - Volatility regime (trending vs ranging)
    - Optimal SL/target based on current vol
    """

    def __init__(self, settings: Settings):
        super().__init__("volatility", settings, AgentCategory.CONFIRMATION)
        self.th = settings.thresholds
        self.bb_width_history: list = []

    def analyze(self, df: pd.DataFrame, snapshot: MarketSnapshot) -> AgentOutput:
        warnings = []
        details = {}

        if len(df) < 25:
            return self._neutral_output("Not enough data")

        # ── 1. BOLLINGER BAND ANALYSIS ──
        bb_upper = snapshot.bb_upper
        bb_lower = snapshot.bb_lower
        bb_middle = snapshot.bb_middle
        bb_width = snapshot.bb_width
        price = snapshot.price

        if bb_upper == 0 or bb_lower == 0:
            # Fallback if BB not in snapshot
            bb = self._calculate_bollinger(df)
            if not bb:
                return self._neutral_output("BB calc failed")
            bb_upper = bb["upper"]
            bb_lower = bb["lower"]
            bb_middle = bb["middle"]
            bb_width = bb["width"]

        bb_range = bb_upper - bb_lower
        if bb_range == 0:
            return self._neutral_output()

        bb_pct_b = (price - bb_lower) / bb_range

        self.bb_width_history.append(bb_width)
        self.bb_width_history = self.bb_width_history[-50:]

        details["bb_width"] = f"{bb_width:.2f}%"

        # Check for squeeze
        is_squeeze = False
        if len(self.bb_width_history) >= 20:
            avg_width = sum(self.bb_width_history[-20:]) / 20
            if bb_width < avg_width * self.th.squeeze_threshold:
                is_squeeze = True
                details["squeeze"] = "ACTIVE (Prepare for big move)"
                warnings.append("Squeeze detected — tight consolidation")

        # Check for expansion/breakout
        is_expansion = False
        if len(self.bb_width_history) >= 5:
            recent_min = min(self.bb_width_history[-5:-1])
            if bb_width > recent_min * self.th.expansion_multiplier:
                is_expansion = True
                details["expansion"] = "ACTIVE (Volatility increasing)"

        # ── 2. ATR TREND ──
        atr = snapshot.atr
        atr_slow = snapshot.atr_15m if snapshot.atr_15m > 0 else atr

        if atr > atr_slow * 1.2:
            details["atr_trend"] = "EXPANDING"
        elif atr < atr_slow * 0.8:
            details["atr_trend"] = "CONTRACTING"
        else:
            details["atr_trend"] = "STABLE"

        # ── 3. PRICE POSITION IN BANDS ──
        direction = Direction.NEUTRAL
        score = 50

        if bb_pct_b > 1.05:
            # Extreme upper band — potential reversal or strong trend
            if is_expansion:
                direction = Direction.BULLISH
                score = 80
                details["position"] = "Riding Upper Band (Trend)"
            else:
                direction = Direction.BEARISH  # Mean reversion
                score = 60
                details["position"] = "Outside Upper Band (Reversion)"
                warnings.append("Price extended outside upper BB")

        elif bb_pct_b < -0.05:
            if is_expansion:
                direction = Direction.BEARISH
                score = 80
                details["position"] = "Riding Lower Band (Trend)"
            else:
                direction = Direction.BULLISH  # Mean reversion
                score = 60
                details["position"] = "Outside Lower Band (Reversion)"
                warnings.append("Price extended outside lower BB")

        elif 0.45 <= bb_pct_b <= 0.55:
            details["position"] = "Near Middle Band (Neutral)"
            score = 30

        else:
            if bb_pct_b > 0.5:
                direction = Direction.BULLISH
                score = 60 + (bb_pct_b - 0.5) * 40
                details["position"] = f"Upper Half ({bb_pct_b:.2f})"
            else:
                direction = Direction.BEARISH
                score = 60 + (0.5 - bb_pct_b) * 40
                details["position"] = f"Lower Half ({bb_pct_b:.2f})"

        # ── COMBINE ──
        if is_squeeze:
            # During a squeeze, direction is uncertain until breakout
            direction = Direction.NEUTRAL
            score = 30
            details["regime"] = MarketRegime.SQUEEZE.value

        elif is_expansion:
            # During expansion, follow the breakout direction
            score = min(100, score + 20)
            details["regime"] = MarketRegime.VOLATILE.value
        else:
            details["regime"] = MarketRegime.RANGING.value

        confidence = score
        strength = Strength.STRONG if confidence >= 70 else (
            Strength.MODERATE if confidence >= 45 else Strength.WEAK
        )

        return AgentOutput(
            agent_name=self.name,
            timestamp=datetime.now(),
            direction=direction,
            confidence=round(confidence, 1),
            strength=strength,
            details=details,
            warnings=warnings,
            sub_scores={"bb_position": score}
        )

    def _calculate_bollinger(self, df: pd.DataFrame) -> dict:
        if len(df) < self.th.bb_period:
            return None

        closes = df['close']
        ma = closes.rolling(window=self.th.bb_period).mean()
        std = closes.rolling(window=self.th.bb_period).std()

        upper = ma + (std * self.th.bb_std)
        lower = ma - (std * self.th.bb_std)

        latest_close = closes.iloc[-1]
        latest_ma = ma.iloc[-1]
        latest_upper = upper.iloc[-1]
        latest_lower = lower.iloc[-1]

        width = ((latest_upper - latest_lower) / latest_ma) * 100 if latest_ma > 0 else 0

        return {
            "middle": latest_ma,
            "upper": latest_upper,
            "lower": latest_lower,
            "width": width
        }
