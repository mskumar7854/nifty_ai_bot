"""
============================================
🕯️ PRICE ACTION AGENT
Why: Candlestick patterns reveal what
     buyers and sellers are ACTUALLY doing.
     No lagging indicator — pure price truth.
============================================
"""

import pandas as pd
import numpy as np
from datetime import datetime

from agents.base_agent import BaseAgent, AgentCategory
from models.signals import AgentOutput, Direction, Strength, MarketSnapshot
from utils.indicators import candle_analysis
from config.settings import Settings


class PriceActionAgent(BaseAgent):
    """
    Detects:
    - Engulfing patterns (bullish/bearish reversal)
    - Pin bars / hammer (rejection from levels)
    - Inside bars (compression before expansion)
    - Double top/bottom (reversal patterns)
    - Higher highs / lower lows (trend structure)
    - Order blocks (institutional entry zones)
    """

    def __init__(self, settings: Settings):
        super().__init__("price_action", settings, AgentCategory.PRIMARY)
        self.th = settings.thresholds

    def analyze(self, df: pd.DataFrame, snapshot: MarketSnapshot) -> AgentOutput:
        warnings = []
        details = {}
        patterns_found = []

        if len(df) < 20:
            return self._neutral_output("Not enough data")

        # ── 1. ENGULFING PATTERN ──
        engulfing = self._detect_engulfing(df)
        if engulfing["detected"]:
            patterns_found.append(engulfing)
            details["engulfing"] = engulfing

        # ── 2. PIN BAR / HAMMER ──
        pin_bar = self._detect_pin_bar(df)
        if pin_bar["detected"]:
            patterns_found.append(pin_bar)
            details["pin_bar"] = pin_bar

        # ── 3. INSIDE BAR ──
        inside_bar = self._detect_inside_bar(df)
        if inside_bar["detected"]:
            patterns_found.append(inside_bar)
            details["inside_bar"] = inside_bar

        # ── 4. DOUBLE TOP / BOTTOM ──
        double_pattern = self._detect_double_pattern(df)
        if double_pattern["detected"]:
            patterns_found.append(double_pattern)
            details["double_pattern"] = double_pattern

        # ── 5. MARKET STRUCTURE (HH/HL or LH/LL) ──
        structure = self._analyze_structure(df)
        details["structure"] = structure

        # ── 6. ORDER BLOCK DETECTION ──
        order_block = self._detect_order_block(df)
        if order_block["detected"]:
            patterns_found.append(order_block)
            details["order_block"] = order_block

        # ── COMBINE PATTERNS ──
        bull_patterns = sum(1 for p in patterns_found
                          if p.get("bias") == "bullish")
        bear_patterns = sum(1 for p in patterns_found
                          if p.get("bias") == "bearish")

        # Structure adds weight
        if structure["type"] == "uptrend":
            bull_patterns += 1
        elif structure["type"] == "downtrend":
            bear_patterns += 1

        details["patterns_count"] = len(patterns_found)
        details["bull_patterns"] = bull_patterns
        details["bear_patterns"] = bear_patterns

        # Score based on patterns found
        if bull_patterns > bear_patterns and bull_patterns >= 1:
            direction = Direction.BULLISH
            pattern_score = min(90, 50 + bull_patterns * 20)
        elif bear_patterns > bull_patterns and bear_patterns >= 1:
            direction = Direction.BEARISH
            pattern_score = min(90, 50 + bear_patterns * 20)
        else:
            direction = Direction.NEUTRAL
            pattern_score = 30

        # Candle quality of latest
        latest = candle_analysis(df.iloc[-1])
        candle_quality = latest["body_ratio"] * 100
        details["latest_candle"] = latest["type"]

        factors = {
            "patterns": (pattern_score, 0.6),
            "structure": (structure["score"], 0.25),
            "candle_quality": (candle_quality, 0.15),
        }
        confidence = self._calculate_confidence(factors)

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
            sub_scores={
                "patterns": round(pattern_score, 1),
                "structure": round(structure["score"], 1),
            },
        )

    def _detect_engulfing(self, df: pd.DataFrame) -> dict:
        if len(df) < 2:
            return {"detected": False}

        prev = df.iloc[-2]
        curr = df.iloc[-1]

        prev_body = abs(prev['close'] - prev['open'])
        curr_body = abs(curr['close'] - curr['open'])

        if curr_body < prev_body * self.th.engulfing_min_ratio:
            return {"detected": False}

        # Bullish engulfing
        if (prev['close'] < prev['open'] and  # prev bearish
            curr['close'] > curr['open'] and   # curr bullish
            curr['open'] <= prev['close'] and
            curr['close'] >= prev['open']):
            return {
                "detected": True,
                "type": "bullish_engulfing",
                "bias": "bullish",
                "score": 80,
            }

        # Bearish engulfing
        if (prev['close'] > prev['open'] and
            curr['close'] < curr['open'] and
            curr['open'] >= prev['close'] and
            curr['close'] <= prev['open']):
            return {
                "detected": True,
                "type": "bearish_engulfing",
                "bias": "bearish",
                "score": 80,
            }

        return {"detected": False}

    def _detect_pin_bar(self, df: pd.DataFrame) -> dict:
        if len(df) < 1:
            return {"detected": False}

        row = df.iloc[-1]
        body = abs(row['close'] - row['open'])
        total = row['high'] - row['low']

        if total == 0:
            return {"detected": False}

        upper_wick = row['high'] - max(row['open'], row['close'])
        lower_wick = min(row['open'], row['close']) - row['low']

        # Bullish pin bar (long lower wick)
        if lower_wick > body * self.th.pin_bar_wick_ratio and lower_wick > upper_wick * 2:
            return {
                "detected": True,
                "type": "bullish_pin_bar",
                "bias": "bullish",
                "score": 75,
                "rejection_level": row['low'],
            }

        # Bearish pin bar (long upper wick)
        if upper_wick > body * self.th.pin_bar_wick_ratio and upper_wick > lower_wick * 2:
            return {
                "detected": True,
                "type": "bearish_pin_bar",
                "bias": "bearish",
                "score": 75,
                "rejection_level": row['high'],
            }

        return {"detected": False}

    def _detect_inside_bar(self, df: pd.DataFrame) -> dict:
        if len(df) < 3:
            return {"detected": False}

        mother = df.iloc[-2]
        inside = df.iloc[-1]

        if (inside['high'] < mother['high'] and
            inside['low'] > mother['low']):
            return {
                "detected": True,
                "type": "inside_bar",
                "bias": "neutral",  # direction unknown until breakout
                "score": 60,
                "breakout_up": mother['high'],
                "breakout_down": mother['low'],
            }

        return {"detected": False}

    def _detect_double_pattern(self, df: pd.DataFrame) -> dict:
        if len(df) < 20:
            return {"detected": False}

        recent = df.tail(20)
        highs = recent['high']
        lows = recent['low']

        # Find peaks and troughs
        tolerance = self.th.double_top_tolerance / 100

        # Double top
        top1_idx = highs.idxmax()
        top1 = highs[top1_idx]
        remaining = highs.drop(top1_idx)
        if len(remaining) > 0:
            top2_idx = remaining.idxmax()
            top2 = remaining[top2_idx]

            if abs(top1 - top2) / top1 < tolerance and abs(top1_idx - top2_idx) > 5:
                current_price = df.iloc[-1]['close']
                if current_price < top1 * 0.995:
                    return {
                        "detected": True,
                        "type": "double_top",
                        "bias": "bearish",
                        "score": 70,
                        "level": round((top1 + top2) / 2, 1),
                    }

        # Double bottom
        bot1_idx = lows.idxmin()
        bot1 = lows[bot1_idx]
        remaining = lows.drop(bot1_idx)
        if len(remaining) > 0:
            bot2_idx = remaining.idxmin()
            bot2 = remaining[bot2_idx]

            if abs(bot1 - bot2) / bot1 < tolerance and abs(bot1_idx - bot2_idx) > 5:
                current_price = df.iloc[-1]['close']
                if current_price > bot1 * 1.005:
                    return {
                        "detected": True,
                        "type": "double_bottom",
                        "bias": "bullish",
                        "score": 70,
                        "level": round((bot1 + bot2) / 2, 1),
                    }

        return {"detected": False}

    def _analyze_structure(self, df: pd.DataFrame) -> dict:
        if len(df) < 10:
            return {"type": "unknown", "score": 50}

        recent = df.tail(10)

        # Check for higher highs + higher lows (uptrend)
        highs = recent['high'].values
        lows = recent['low'].values

        hh_count = sum(1 for i in range(1, len(highs)) if highs[i] > highs[i-1])
        hl_count = sum(1 for i in range(1, len(lows)) if lows[i] > lows[i-1])
        ll_count = sum(1 for i in range(1, len(lows)) if lows[i] < lows[i-1])
        lh_count = sum(1 for i in range(1, len(highs)) if highs[i] < highs[i-1])

        total = len(highs) - 1

        if hh_count >= total * 0.6 and hl_count >= total * 0.5:
            return {"type": "uptrend", "score": 80, "hh": hh_count, "hl": hl_count}
        elif ll_count >= total * 0.6 and lh_count >= total * 0.5:
            return {"type": "downtrend", "score": 80, "ll": ll_count, "lh": lh_count}
        else:
            return {"type": "ranging", "score": 40}

    def _detect_order_block(self, df: pd.DataFrame) -> dict:
        """
        Order block: Last bearish candle before a strong bullish move (bullish OB)
        or last bullish candle before a strong bearish move (bearish OB)
        """
        if len(df) < 10:
            return {"detected": False}

        recent = df.tail(10)
        price = df.iloc[-1]['close']

        for i in range(len(recent) - 3, 0, -1):
            candle = recent.iloc[i]
            next_candles = recent.iloc[i+1:i+3]

            candle_bearish = candle['close'] < candle['open']
            candle_bullish = candle['close'] > candle['open']

            if candle_bearish:
                # Check if followed by strong bullish move
                move_up = next_candles['close'].max() - candle['low']
                if move_up > (candle['high'] - candle['low']) * 2:
                    ob_top = candle['open']
                    ob_bottom = candle['close']
                    if ob_bottom <= price <= ob_top * 1.005:
                        return {
                            "detected": True,
                            "type": "bullish_order_block",
                            "bias": "bullish",
                            "score": 75,
                            "zone_top": round(ob_top, 1),
                            "zone_bottom": round(ob_bottom, 1),
                        }

            if candle_bullish:
                move_down = candle['high'] - next_candles['close'].min()
                if move_down > (candle['high'] - candle['low']) * 2:
                    ob_top = candle['close']
                    ob_bottom = candle['open']
                    if ob_bottom * 0.995 <= price <= ob_top:
                        return {
                            "detected": True,
                            "type": "bearish_order_block",
                            "bias": "bearish",
                            "score": 75,
                            "zone_top": round(ob_top, 1),
                            "zone_bottom": round(ob_bottom, 1),
                        }

        return {"detected": False}
