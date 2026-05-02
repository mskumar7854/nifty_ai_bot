"""
============================================
📈 MOMENTUM AGENT
Detects: RSI strength, Volume confirmation,
         Candle quality, Move authenticity
============================================
"""

import pandas as pd
from datetime import datetime

from agents.base_agent import BaseAgent
from models.signals import AgentOutput, Direction, Strength, MarketSnapshot
from utils.indicators import candle_analysis, calculate_volume_sma
from config.settings import Settings


class MomentumAgent(BaseAgent):
    """
    Validates whether a move has REAL force behind it.
    Prevents entering on weak, fake moves.
    """

    def __init__(self, settings: Settings):
        super().__init__("momentum", settings)
        self.th = settings.thresholds

    def analyze(
        self, df: pd.DataFrame, snapshot: MarketSnapshot
    ) -> AgentOutput:
        """
        Analysis pipeline:
        1. RSI zones (overbought/oversold/momentum)
        2. Volume analysis (spike vs dry)
        3. Candle quality (body ratio, wicks)
        4. Multi-candle momentum pattern
        """

        warnings = []
        details = {}

        # ── 1. RSI ANALYSIS ──
        rsi = snapshot.rsi

        if rsi >= self.th.rsi_overbought:
            rsi_direction = Direction.BULLISH
            rsi_score = 60  # Still bullish but careful
            details["rsi"] = f"OVERBOUGHT ({rsi:.1f})"
            warnings.append(f"RSI overbought at {rsi:.1f} — pullback risk")
        elif rsi >= self.th.rsi_bull_zone:
            rsi_direction = Direction.BULLISH
            rsi_score = 80
            details["rsi"] = f"BULLISH MOMENTUM ({rsi:.1f})"
        elif rsi <= self.th.rsi_oversold:
            rsi_direction = Direction.BEARISH
            rsi_score = 60
            details["rsi"] = f"OVERSOLD ({rsi:.1f})"
            warnings.append(f"RSI oversold at {rsi:.1f} — bounce risk")
        elif rsi <= self.th.rsi_bear_zone:
            rsi_direction = Direction.BEARISH
            rsi_score = 80
            details["rsi"] = f"BEARISH MOMENTUM ({rsi:.1f})"
        else:
            rsi_direction = Direction.NEUTRAL
            rsi_score = 25
            details["rsi"] = f"NEUTRAL ZONE ({rsi:.1f})"
            warnings.append("RSI in no-man's land (40-60)")

        # ── 2. VOLUME ANALYSIS ──
        current_volume = snapshot.volume
        vol_sma = calculate_volume_sma(df['volume'], 20)

        if len(vol_sma) > 0 and vol_sma.iloc[-1] > 0:
            avg_vol = vol_sma.iloc[-1]
            vol_ratio = current_volume / avg_vol

            if vol_ratio >= self.th.volume_spike_multiplier:
                vol_score = 85
                details["volume"] = f"SPIKE ({vol_ratio:.1f}x average)"
            elif vol_ratio >= 1.0:
                vol_score = 60
                details["volume"] = f"ABOVE AVG ({vol_ratio:.1f}x)"
            elif vol_ratio >= 0.7:
                vol_score = 35
                details["volume"] = f"BELOW AVG ({vol_ratio:.1f}x)"
                warnings.append("Low volume — weak conviction")
            else:
                vol_score = 15
                details["volume"] = f"DRY ({vol_ratio:.1f}x)"
                warnings.append("Very low volume — likely fake move")
        else:
            vol_score = 50
            vol_ratio = 1.0
            details["volume"] = "NO DATA"

        # ── 3. CANDLE QUALITY ──
        if len(df) > 0:
            latest_candle = candle_analysis(df.iloc[-1])
            details["candle_type"] = latest_candle["type"]
            details["body_ratio"] = latest_candle["body_ratio"]

            if latest_candle["body_ratio"] >= self.th.candle_body_ratio:
                candle_score = 80
                details["candle_strength"] = "STRONG"
            elif latest_candle["body_ratio"] >= 0.4:
                candle_score = 55
                details["candle_strength"] = "MODERATE"
            else:
                candle_score = 25
                details["candle_strength"] = "WEAK (big wicks)"
                warnings.append("Candle has large wicks — indecision")

            candle_bullish = latest_candle["is_bullish"]
        else:
            candle_score = 50
            candle_bullish = True
            details["candle_strength"] = "NO DATA"

        # ── 4. CONSECUTIVE CANDLE PATTERN ──
        if len(df) >= 3:
            last_3 = df.tail(3)
            bull_candles = sum(
                1 for _, row in last_3.iterrows() if row['close'] > row['open']
            )
            bear_candles = 3 - bull_candles

            if bull_candles == 3:
                pattern_score = 85
                pattern_dir = Direction.BULLISH
                details["pattern"] = "3 consecutive bullish candles"
            elif bear_candles == 3:
                pattern_score = 85
                pattern_dir = Direction.BEARISH
                details["pattern"] = "3 consecutive bearish candles"
            elif bull_candles == 2:
                pattern_score = 60
                pattern_dir = Direction.BULLISH
                details["pattern"] = "2/3 bullish"
            elif bear_candles == 2:
                pattern_score = 60
                pattern_dir = Direction.BEARISH
                details["pattern"] = "2/3 bearish"
            else:
                pattern_score = 30
                pattern_dir = Direction.NEUTRAL
                details["pattern"] = "Mixed / choppy"
        else:
            pattern_score = 50
            pattern_dir = Direction.NEUTRAL

        # ── COMBINE MOMENTUM SIGNALS ──
        factors = {
            "rsi": (rsi_score, 0.35),
            "volume": (vol_score, 0.25),
            "candle": (candle_score, 0.25),
            "pattern": (pattern_score, 0.15),
        }
        confidence = self._calculate_confidence(factors)

        # Determine overall direction
        bull_indicators = sum([
            rsi_direction == Direction.BULLISH,
            candle_bullish,
            pattern_dir == Direction.BULLISH,
        ])

        if bull_indicators >= 2 and rsi_direction != Direction.NEUTRAL:
            direction = Direction.BULLISH
        elif bull_indicators <= 1 and rsi_direction != Direction.NEUTRAL:
            direction = Direction.BEARISH
        else:
            direction = Direction.NEUTRAL
            confidence = min(confidence, 35)

        # Strength
        if confidence >= 70:
            strength = Strength.STRONG
        elif confidence >= 45:
            strength = Strength.MODERATE
        else:
            strength = Strength.WEAK

        return AgentOutput(
            agent_name=self.name,
            timestamp=datetime.now(),
            direction=direction,
            confidence=round(confidence, 1),
            strength=strength,
            details=details,
            warnings=warnings,
        )
