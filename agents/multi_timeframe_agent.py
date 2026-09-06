"""
============================================
📐 MULTI-TIMEFRAME AGENT
Why: A signal on 1-minute chart means NOTHING
     if 5m and 15m disagree. This agent confirms
     alignment across timeframes.
============================================
"""

import pandas as pd
from datetime import datetime

from agents.base_agent import BaseAgent, AgentCategory
from models import AgentOutput, Direction, Strength, MarketSnapshot
from config.settings import Settings


class MultiTimeframeAgent(BaseAgent):
    """
    KEY INSIGHT:
    Trade in direction of HIGHER timeframe.
    Enter on LOWER timeframe.

    If 15m = UP, 5m = UP, 1m = UP → STRONG alignment → high confidence
    If 15m = UP, 5m = DOWN → conflict → low confidence
    """

    def __init__(self, settings: Settings):
        super().__init__("multi_timeframe", settings, AgentCategory.PRIMARY)
        self.th = settings.thresholds

    def analyze(self, df: pd.DataFrame, snapshot: MarketSnapshot) -> AgentOutput:
        warnings = []
        details = {}

        # ── 1. ANALYZE EACH TIMEFRAME ──
        tf_signals = {}

        # 1-minute (from main df / snapshot)
        tf_1m = self._analyze_timeframe(
            "1m",
            snapshot.price, snapshot.vwap,
            snapshot.rsi, snapshot.ema_fast, snapshot.ema_slow,
        )
        tf_signals["1m"] = tf_1m

        # 5-minute
        tf_5m = self._analyze_timeframe(
            "5m",
            snapshot.price, snapshot.vwap_5m if snapshot.vwap_5m else snapshot.vwap,
            snapshot.rsi_5m,
            snapshot.ema_fast_5m if snapshot.ema_fast_5m else snapshot.ema_fast,
            snapshot.ema_slow_5m if snapshot.ema_slow_5m else snapshot.ema_slow,
        )
        tf_signals["5m"] = tf_5m

        # 15-minute
        tf_15m = self._analyze_timeframe(
            "15m",
            snapshot.price, snapshot.vwap,
            snapshot.rsi_15m,
            snapshot.ema_fast_15m if snapshot.ema_fast_15m else snapshot.ema_fast,
            snapshot.ema_slow_15m if snapshot.ema_slow_15m else snapshot.ema_slow,
        )
        tf_signals["15m"] = tf_15m

        for tf, result in tf_signals.items():
            details[tf] = result

        # ── 2. CHECK ALIGNMENT ──
        directions = [r["direction"] for r in tf_signals.values()]
        bull_count = sum(1 for d in directions if d == Direction.BULLISH)
        bear_count = sum(1 for d in directions if d == Direction.BEARISH)
        total = len(directions)

        # ── 3. ALIGNMENT SCORING ──
        if bull_count == total:
            # Perfect bullish alignment
            alignment_score = 95
            direction = Direction.BULLISH
            details["alignment"] = f"PERFECT BULLISH ({bull_count}/{total})"
        elif bear_count == total:
            alignment_score = 95
            direction = Direction.BEARISH
            details["alignment"] = f"PERFECT BEARISH ({bear_count}/{total})"
        elif bull_count >= self.th.mtf_alignment_threshold:
            alignment_score = 65
            direction = Direction.BULLISH
            details["alignment"] = f"MOSTLY BULLISH ({bull_count}/{total})"
            warnings.append(f"{total - bull_count} timeframe(s) disagree")
        elif bear_count >= self.th.mtf_alignment_threshold:
            alignment_score = 65
            direction = Direction.BEARISH
            details["alignment"] = f"MOSTLY BEARISH ({bear_count}/{total})"
            warnings.append(f"{total - bear_count} timeframe(s) disagree")
        else:
            alignment_score = 20
            direction = Direction.NEUTRAL
            details["alignment"] = "CONFLICTING — no clear direction"
            warnings.append("⚠️ Timeframes in conflict — avoid trading")

        # ── 4. HIGHER TIMEFRAME WEIGHT ──
        # 15m direction gets more weight
        htf_direction = tf_signals["15m"]["direction"]
        if htf_direction == direction:
            alignment_score = min(100, alignment_score + 10)
            details["htf_confirmation"] = "15m CONFIRMS"
        elif htf_direction != Direction.NEUTRAL and direction != Direction.NEUTRAL:
            alignment_score = max(0, alignment_score - 20)
            warnings.append("⚠️ 15m (higher TF) DISAGREES — dangerous")
            details["htf_confirmation"] = "15m DISAGREES"

        # ── 5. TREND CONSISTENCY ──
        avg_scores = [r["score"] for r in tf_signals.values()]
        consistency = sum(avg_scores) / len(avg_scores) if avg_scores else 50

        factors = {
            "alignment": (alignment_score, 0.6),
            "consistency": (consistency, 0.4),
        }
        confidence = self._calculate_confidence(factors)

        if confidence >= 75:
            strength = Strength.STRONG
        elif confidence >= 50:
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
                "alignment": round(alignment_score, 1),
                "consistency": round(consistency, 1),
            },
        )

    def _analyze_timeframe(
        self, tf_name: str,
        price: float, vwap: float,
        rsi: float, ema_fast: float, ema_slow: float,
    ) -> dict:
        """Analyze a single timeframe"""
        bull_signals = 0
        bear_signals = 0

        # VWAP position
        if price > vwap and vwap > 0:
            bull_signals += 1
        elif price < vwap and vwap > 0:
            bear_signals += 1

        # EMA crossover
        if ema_fast > ema_slow and ema_slow > 0:
            bull_signals += 1
        elif ema_fast < ema_slow and ema_slow > 0:
            bear_signals += 1

        # RSI
        if rsi > 55:
            bull_signals += 1
        elif rsi < 45:
            bear_signals += 1

        if bull_signals >= 2:
            direction = Direction.BULLISH
            score = 70 + (bull_signals * 10)
        elif bear_signals >= 2:
            direction = Direction.BEARISH
            score = 70 + (bear_signals * 10)
        else:
            direction = Direction.NEUTRAL
            score = 40

        return {
            "direction": direction,
            "score": min(100, score),
            "bull_signals": bull_signals,
            "bear_signals": bear_signals,
            "rsi": round(rsi, 1),
        }
