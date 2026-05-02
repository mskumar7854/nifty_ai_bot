"""
============================================
🌍 SENTIMENT AGENT
Tracks: India VIX, Global cues,
        Market regime, Fear levels
============================================
"""

import pandas as pd
from datetime import datetime

from agents.base_agent import BaseAgent
from models.signals import AgentOutput, Direction, Strength, MarketSnapshot
from config.settings import Settings


class SentimentAgent(BaseAgent):
    """
    Reads the broader market mood.
    High VIX = danger / opportunity.
    Global cues = directional bias.
    """

    def __init__(self, settings: Settings):
        super().__init__("sentiment", settings)
        self.th = settings.thresholds
        self.vix_history: list = []

    def analyze(
        self, df: pd.DataFrame, snapshot: MarketSnapshot
    ) -> AgentOutput:
        """
        Analysis:
        1. India VIX level (fear gauge)
        2. VIX change (spike detection)
        3. Market regime classification
        """

        warnings = []
        details = {}

        # ── 1. VIX LEVEL ──
        vix = snapshot.india_vix

        self.vix_history.append({"time": datetime.now(), "vix": vix})
        self.vix_history = self.vix_history[-100:]

        if vix >= self.th.vix_high:
            vix_condition = "HIGH_FEAR"
            vix_score = 40
            details["vix_level"] = f"HIGH ({vix:.1f}) — Market fearful"
            warnings.append("⚠️ High VIX — use smaller position sizes")
            warnings.append("Wide stop losses recommended")
        elif vix <= self.th.vix_low:
            vix_condition = "LOW_FEAR"
            vix_score = 75
            details["vix_level"] = f"LOW ({vix:.1f}) — Market complacent"
        else:
            vix_condition = "NORMAL"
            vix_score = 60
            details["vix_level"] = f"NORMAL ({vix:.1f})"

        # ── 2. VIX SPIKE DETECTION ──
        if len(self.vix_history) >= 2:
            prev_vix = self.vix_history[-2]["vix"]
            if prev_vix > 0:
                vix_change = ((vix - prev_vix) / prev_vix) * 100
            else:
                vix_change = 0

            if vix_change > self.th.vix_spike:
                details["vix_spike"] = f"SPIKING (+{vix_change:.1f}%)"
                warnings.append("🚨 VIX SPIKE — Potential panic / big move coming")
                spike_score = 30  # Lower confidence during spikes
            elif vix_change < -self.th.vix_spike:
                details["vix_spike"] = f"DROPPING ({vix_change:.1f}%)"
                spike_score = 70
            else:
                details["vix_spike"] = f"STABLE ({vix_change:+.1f}%)"
                spike_score = 60
        else:
            spike_score = 50
            details["vix_spike"] = "Building history..."

        # ── 3. MARKET REGIME ──
        if vix >= self.th.vix_high:
            regime = "VOLATILE"
            regime_score = 40
            details["regime"] = "HIGH VOLATILITY — Trend-following risky"
        elif vix <= self.th.vix_low:
            regime = "CALM"
            regime_score = 70
            details["regime"] = "LOW VOLATILITY — Good for range trades"
        else:
            regime = "NORMAL"
            regime_score = 60
            details["regime"] = "NORMAL VOLATILITY — Standard rules apply"

        # ── COMBINE ──
        factors = {
            "vix_level": (vix_score, 0.4),
            "vix_spike": (spike_score, 0.35),
            "regime": (regime_score, 0.25),
        }
        confidence = self._calculate_confidence(factors)

        # Sentiment doesn't give direction — it gives PERMISSION
        direction = Direction.NEUTRAL

        if confidence >= 65:
            strength = Strength.STRONG
            details["verdict"] = "CONDITIONS FAVORABLE for trading"
        elif confidence >= 40:
            strength = Strength.MODERATE
            details["verdict"] = "CONDITIONS OKAY — trade with caution"
        else:
            strength = Strength.WEAK
            details["verdict"] = "CONDITIONS UNFAVORABLE — reduce size or sit out"
            warnings.append("Consider sitting out this session")

        return AgentOutput(
            agent_name=self.name,
            timestamp=datetime.now(),
            direction=direction,
            confidence=round(confidence, 1),
            strength=strength,
            details=details,
            warnings=warnings,
        )
