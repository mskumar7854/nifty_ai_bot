"""
============================================
⚠️ TRAP DETECTION AGENT
Detects: Fake breakouts, Liquidity sweeps,
         Stop hunts, Bull/Bear traps
============================================
"""

import pandas as pd
from datetime import datetime
from typing import List

from agents.base_agent import BaseAgent
from models import (
    AgentOutput, Direction, Strength, MarketSnapshot, TrapType
)
from utils.indicators import candle_analysis
from config.settings import Settings


class TrapAgent(BaseAgent):
    """
    The PROTECTION agent.
    Detects manipulation patterns that would trap retail traders.
    When trap detected → signal should be REJECTED or REVERSED.
    """

    def __init__(self, settings: Settings):
        super().__init__("trap", settings)
        self.th = settings.thresholds
        self.recent_traps: List[dict] = []

    def analyze(
        self, df: pd.DataFrame, snapshot: MarketSnapshot
    ) -> AgentOutput:
        """
        Detection pipeline:
        1. Fake breakout (break + immediate reversal)
        2. Wick rejection (long wick, small body)
        3. Volume divergence (breakout on low volume)
        4. Liquidity sweep pattern
        """

        warnings = []
        details = {}
        traps_detected = []

        if len(df) < 10:
            return self._neutral_output("Not enough data for trap detection")

        # ── 1. FAKE BREAKOUT DETECTION ──
        fake_breakout = self._detect_fake_breakout(df)
        if fake_breakout["detected"]:
            traps_detected.append(TrapType.FAKE_BREAKOUT_UP
                                  if fake_breakout["direction"] == "up"
                                  else TrapType.FAKE_BREAKOUT_DOWN)
            details["fake_breakout"] = fake_breakout
            warnings.append(
                f"⚠️ FAKE BREAKOUT {fake_breakout['direction'].upper()} detected!"
            )

        # ── 2. WICK REJECTION ──
        wick_trap = self._detect_wick_rejection(df)
        if wick_trap["detected"]:
            traps_detected.append(TrapType.STOP_HUNT)
            details["wick_rejection"] = wick_trap
            warnings.append(
                f"⚠️ Wick rejection at {wick_trap['level']:.0f} — possible stop hunt"
            )

        # ── 3. VOLUME DIVERGENCE ──
        vol_divergence = self._detect_volume_divergence(df)
        if vol_divergence["detected"]:
            details["volume_divergence"] = vol_divergence
            warnings.append("⚠️ Price moving on declining volume — weak move")

        # ── 4. LIQUIDITY SWEEP ──
        liq_sweep = self._detect_liquidity_sweep(df)
        if liq_sweep["detected"]:
            traps_detected.append(TrapType.LIQUIDITY_SWEEP)
            details["liquidity_sweep"] = liq_sweep
            warnings.append(
                f"⚠️ Liquidity sweep at {liq_sweep['level']:.0f}"
            )

        # ── DETERMINE TRAP STATUS ──
        trap_detected = len(traps_detected) > 0
        num_traps = len(traps_detected)

        details["traps_found"] = num_traps
        details["trap_types"] = [t.value for t in traps_detected]

        if num_traps >= 2:
            confidence = 90
            strength = Strength.STRONG
            warnings.append("🚨 MULTIPLE TRAPS — HIGH DANGER ZONE")
        elif num_traps == 1:
            confidence = 70
            strength = Strength.MODERATE
        else:
            confidence = 10
            strength = Strength.WEAK

        # Direction: when trap detected, the OPPOSITE is likely true
        if trap_detected:
            if TrapType.FAKE_BREAKOUT_UP in traps_detected:
                direction = Direction.BEARISH  # fake bull → actually bearish
            elif TrapType.FAKE_BREAKOUT_DOWN in traps_detected:
                direction = Direction.BULLISH   # fake bear → actually bullish
            else:
                direction = Direction.NEUTRAL
        else:
            direction = Direction.NEUTRAL  # No trap = no opinion

        # Store trap
        if trap_detected:
            self.recent_traps.append({
                "time": datetime.now(),
                "types": [t.value for t in traps_detected],
                "price": snapshot.price,
            })
            self.recent_traps = self.recent_traps[-20:]

        return AgentOutput(
            agent_name=self.name,
            timestamp=datetime.now(),
            direction=direction,
            confidence=round(confidence, 1),
            strength=strength,
            details=details,
            warnings=warnings,
        )

    def _detect_fake_breakout(self, df: pd.DataFrame) -> dict:
        """
        Fake breakout: Price breaks a level then immediately reverses.
        Pattern: Candle 1 breaks high → Candle 2+3 close below
        """
        n = self.th.fake_breakout_candles
        if len(df) < n + 5:
            return {"detected": False}

        recent = df.tail(n + 5)
        lookback_high = recent['high'].iloc[:-n].max()
        lookback_low = recent['low'].iloc[:-n].min()
        last_n = recent.tail(n)

        # Check upside fake breakout
        if last_n['high'].max() > lookback_high:
            # Did it break above BUT close back below?
            if last_n['close'].iloc[-1] < lookback_high:
                return {
                    "detected": True,
                    "direction": "up",
                    "broke_level": lookback_high,
                    "current_close": last_n['close'].iloc[-1],
                }

        # Check downside fake breakout
        if last_n['low'].min() < lookback_low:
            if last_n['close'].iloc[-1] > lookback_low:
                return {
                    "detected": True,
                    "direction": "down",
                    "broke_level": lookback_low,
                    "current_close": last_n['close'].iloc[-1],
                }

        return {"detected": False}

    def _detect_wick_rejection(self, df: pd.DataFrame) -> dict:
        """
        Long wick with small body = rejection at that level.
        Could be a stop hunt.
        """
        if len(df) < 1:
            return {"detected": False}

        latest = candle_analysis(df.iloc[-1])

        if latest["body_ratio"] < (1 - self.th.trap_wick_ratio):
            # Big wick, small body
            if latest["wick_upper"] > latest["wick_lower"]:
                level = df.iloc[-1]['high']
                return {
                    "detected": True,
                    "direction": "rejection_from_top",
                    "level": level,
                    "wick_ratio": 1 - latest["body_ratio"],
                }
            elif latest["wick_lower"] > latest["wick_upper"]:
                level = df.iloc[-1]['low']
                return {
                    "detected": True,
                    "direction": "rejection_from_bottom",
                    "level": level,
                    "wick_ratio": 1 - latest["body_ratio"],
                }

        return {"detected": False}

    def _detect_volume_divergence(self, df: pd.DataFrame) -> dict:
        """
        Price making new high/low but volume is declining.
        Sign of a weak, potentially fake move.
        """
        if len(df) < 5:
            return {"detected": False}

        last_5 = df.tail(5)
        price_trend_up = last_5['close'].iloc[-1] > last_5['close'].iloc[0]
        vol_trend_down = last_5['volume'].iloc[-1] < (
            last_5['volume'].iloc[0] * self.th.trap_volume_drop
        )

        price_trend_down = last_5['close'].iloc[-1] < last_5['close'].iloc[0]

        if (price_trend_up and vol_trend_down) or \
           (price_trend_down and vol_trend_down):
            return {
                "detected": True,
                "type": "volume_declining_with_price_move",
                "price_change": last_5['close'].iloc[-1] - last_5['close'].iloc[0],
                "vol_ratio": last_5['volume'].iloc[-1] / max(
                    last_5['volume'].iloc[0], 1
                ),
            }

        return {"detected": False}

    def _detect_liquidity_sweep(self, df: pd.DataFrame) -> dict:
        """
        Quick spike below support or above resistance
        then immediate recovery = liquidity grab
        """
        if len(df) < 10:
            return {"detected": False}

        # Check if recent low went below previous support then recovered
        recent = df.tail(10)
        prev_low = recent['low'].iloc[:-2].min()
        last_low = recent['low'].iloc[-1]
        last_close = recent['close'].iloc[-1]

        if last_low < prev_low and last_close > prev_low:
            return {
                "detected": True,
                "direction": "downside_sweep",
                "level": prev_low,
                "sweep_depth": prev_low - last_low,
            }

        prev_high = recent['high'].iloc[:-2].max()
        last_high = recent['high'].iloc[-1]

        if last_high > prev_high and last_close < prev_high:
            return {
                "detected": True,
                "direction": "upside_sweep",
                "level": prev_high,
                "sweep_depth": last_high - prev_high,
            }

        return {"detected": False}
