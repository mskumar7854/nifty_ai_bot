"""
============================================
📊 MARKET AGENT
Detects: Trend direction, VWAP position,
         Market structure breaks
============================================
"""

import pandas as pd
from datetime import datetime

from agents.base_agent import BaseAgent
from models.signals import AgentOutput, Direction, Strength, MarketSnapshot
from utils.indicators import (
    calculate_vwap,
    calculate_ema,
    detect_structure_break,
    calculate_support_resistance,
)
from config.settings import Settings


class MarketAgent(BaseAgent):
    """
    Determines the overall market bias.
    This is the FIRST filter — if market says NO, everything stops.
    """

    def __init__(self, settings: Settings):
        super().__init__("market", settings)
        self.th = settings.thresholds

    def analyze(
        self, df: pd.DataFrame, snapshot: MarketSnapshot
    ) -> AgentOutput:
        """
        Analysis pipeline:
        1. VWAP position (above/below)
        2. EMA crossover trend
        3. Market structure (higher highs / lower lows)
        4. Combine into directional bias
        """

        warnings = []
        details = {}

        # ── 1. VWAP ANALYSIS ──
        price = snapshot.price
        vwap = snapshot.vwap
        vwap_diff = price - vwap

        if abs(vwap_diff) < self.th.vwap_buffer:
            vwap_signal = Direction.NEUTRAL
            vwap_score = 30
            details["vwap"] = f"NEAR VWAP (diff: {vwap_diff:.1f})"
            warnings.append("Price near VWAP — choppy zone")
        elif vwap_diff > 0:
            vwap_signal = Direction.BULLISH
            vwap_score = min(90, 50 + (vwap_diff / self.th.vwap_buffer) * 10)
            details["vwap"] = f"ABOVE VWAP (+{vwap_diff:.1f})"
        else:
            vwap_signal = Direction.BEARISH
            vwap_score = min(90, 50 + (abs(vwap_diff) / self.th.vwap_buffer) * 10)
            details["vwap"] = f"BELOW VWAP ({vwap_diff:.1f})"

        # ── 2. EMA TREND ──
        ema_fast = snapshot.ema_fast
        ema_slow = snapshot.ema_slow

        if ema_fast > ema_slow:
            ema_signal = Direction.BULLISH
            ema_gap = ((ema_fast - ema_slow) / ema_slow) * 100
            ema_score = min(90, 50 + ema_gap * 20)
            details["ema"] = f"BULLISH (gap: {ema_gap:.3f}%)"
        elif ema_fast < ema_slow:
            ema_signal = Direction.BEARISH
            ema_gap = ((ema_slow - ema_fast) / ema_slow) * 100
            ema_score = min(90, 50 + ema_gap * 20)
            details["ema"] = f"BEARISH (gap: {ema_gap:.3f}%)"
        else:
            ema_signal = Direction.NEUTRAL
            ema_score = 30
            details["ema"] = "FLAT"

        # ── 3. STRUCTURE BREAK ──
        structure = detect_structure_break(
            df['high'], df['low'], self.th.structure_lookback
        )
        structure_type = structure["break_type"]

        if structure_type == "bullish":
            struct_signal = Direction.BULLISH
            struct_score = 80
            details["structure"] = f"BULLISH BREAK above {structure['level']:.0f}"
        elif structure_type == "bearish":
            struct_signal = Direction.BEARISH
            struct_score = 80
            details["structure"] = f"BEARISH BREAK below {structure['level']:.0f}"
        else:
            struct_signal = Direction.NEUTRAL
            struct_score = 40
            details["structure"] = "NO BREAK"

        # ── 4. PRICE POSITION VS RANGE ──
        day_high = df['high'].max()
        day_low = df['low'].min()
        day_range = day_high - day_low

        if day_range > 0:
            position_in_range = (price - day_low) / day_range * 100
        else:
            position_in_range = 50

        details["range_position"] = f"{position_in_range:.0f}% of day range"

        # ── 5. SUPPORT / RESISTANCE PROXIMITY ──
        sr_levels = calculate_support_resistance(df)
        details["support"] = [round(s, 0) for s in sr_levels["support"][:2]]
        details["resistance"] = [round(r, 0) for r in sr_levels["resistance"][:2]]

        # ── COMBINE ALL SIGNALS ──
        bull_count = sum(1 for s in [vwap_signal, ema_signal, struct_signal]
                         if s == Direction.BULLISH)
        bear_count = sum(1 for s in [vwap_signal, ema_signal, struct_signal]
                         if s == Direction.BEARISH)

        # Weighted confidence
        factors = {
            "vwap": (vwap_score, 0.4),
            "ema": (ema_score, 0.35),
            "structure": (struct_score, 0.25),
        }

        confidence = self._calculate_confidence(factors)

        if bull_count >= 2:
            direction = Direction.BULLISH
        elif bear_count >= 2:
            direction = Direction.BEARISH
        else:
            direction = Direction.NEUTRAL
            confidence = min(confidence, 40)
            warnings.append("Mixed signals — no clear trend")

        # Determine strength
        if confidence >= 75:
            strength = Strength.STRONG
        elif confidence >= 50:
            strength = Strength.MODERATE
        else:
            strength = Strength.WEAK

        details["bull_signals"] = bull_count
        details["bear_signals"] = bear_count

        return AgentOutput(
            agent_name=self.name,
            timestamp=datetime.now(),
            direction=direction,
            confidence=round(confidence, 1),
            strength=strength,
            details=details,
            warnings=warnings,
        )
