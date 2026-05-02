"""
============================================
📦 OPTIONS OI AGENT (CORE EDGE)
Tracks: OI buildup/unwinding, PCR,
        Put/Call dominance, Smart money flow
============================================
"""

import pandas as pd
from datetime import datetime

from agents.base_agent import BaseAgent
from models.signals import AgentOutput, Direction, Strength, MarketSnapshot
from config.settings import Settings


class OIAgent(BaseAgent):
    """
    The OPTIONS INTELLIGENCE agent.
    This is where the real edge comes from — understanding
    what option writers (smart money) are doing.
    """

    def __init__(self, settings: Settings):
        super().__init__("oi", settings)
        self.th = settings.thresholds
        self.previous_ce_oi = 0
        self.previous_pe_oi = 0
        self.oi_history = []

    def analyze(
        self, df: pd.DataFrame, snapshot: MarketSnapshot
    ) -> AgentOutput:
        """
        Analysis pipeline:
        1. PCR (Put-Call Ratio) — overall sentiment
        2. OI Change direction — where is writing happening
        3. Max Pain proximity — magnet level
        4. CE vs PE OI buildup — resistance/support mapping
        """

        warnings = []
        details = {}

        # ⚠️ P1.2 Guard: Don't trade on fictional data
        from models.signals import DataSource
        if snapshot.oi_data_source != DataSource.REAL and self.settings.system_mode.mode == "LIVE":
            return AgentOutput(
                agent_name=self.name,
                timestamp=datetime.now(),
                direction=Direction.NEUTRAL,
                confidence=0,
                strength=Strength.WEAK,
                warnings=["Simulated OI data — agent abstaining"],
                details={"abstained": True, "reason": "no_real_oi_data"},
            )

        # ── 1. PCR ANALYSIS ──
        pcr = snapshot.pcr

        if pcr >= self.th.pcr_bullish:
            pcr_direction = Direction.BULLISH
            pcr_score = min(85, 50 + (pcr - 1.0) * 50)
            details["pcr"] = f"BULLISH ({pcr:.2f}) — Put writers dominant"
        elif pcr <= self.th.pcr_bearish:
            pcr_direction = Direction.BEARISH
            pcr_score = min(85, 50 + (1.0 - pcr) * 50)
            details["pcr"] = f"BEARISH ({pcr:.2f}) — Call writers dominant"
        else:
            pcr_direction = Direction.NEUTRAL
            pcr_score = 35
            details["pcr"] = f"NEUTRAL ({pcr:.2f})"

        # ── 2. OI CHANGE ANALYSIS ──
        current_ce_oi = snapshot.total_ce_oi
        current_pe_oi = snapshot.total_pe_oi

        ce_oi_change = current_ce_oi - self.previous_ce_oi
        pe_oi_change = current_pe_oi - self.previous_pe_oi

        # Store history
        self.oi_history.append({
            "time": datetime.now(),
            "ce_change": ce_oi_change,
            "pe_change": pe_oi_change,
        })

        # Keep only last 50 readings
        self.oi_history = self.oi_history[-50:]

        # Interpret OI changes
        if pe_oi_change > self.th.oi_change_threshold and ce_oi_change < 0:
            # PE OI increasing + CE OI decreasing = STRONG BULLISH
            oi_direction = Direction.BULLISH
            oi_score = 90
            details["oi_flow"] = "PE writing + CE unwinding = STRONG BULL"
        elif pe_oi_change > self.th.oi_change_threshold:
            # PE OI increasing = support building
            oi_direction = Direction.BULLISH
            oi_score = 70
            details["oi_flow"] = f"PE writing (+{pe_oi_change:.0f}) = Support building"
        elif ce_oi_change > self.th.oi_change_threshold and pe_oi_change < 0:
            # CE OI increasing + PE unwinding = STRONG BEARISH
            oi_direction = Direction.BEARISH
            oi_score = 90
            details["oi_flow"] = "CE writing + PE unwinding = STRONG BEAR"
        elif ce_oi_change > self.th.oi_change_threshold:
            # CE OI increasing = resistance building
            oi_direction = Direction.BEARISH
            oi_score = 70
            details["oi_flow"] = f"CE writing (+{ce_oi_change:.0f}) = Resistance"
        elif abs(ce_oi_change) < 10000 and abs(pe_oi_change) < 10000:
            oi_direction = Direction.NEUTRAL
            oi_score = 30
            details["oi_flow"] = "No significant OI change"
            warnings.append("OI flat — no conviction from writers")
        else:
            oi_direction = Direction.NEUTRAL
            oi_score = 40
            details["oi_flow"] = f"CE: {ce_oi_change:+.0f} | PE: {pe_oi_change:+.0f}"

        details["ce_oi_change"] = f"{ce_oi_change:+,.0f}"
        details["pe_oi_change"] = f"{pe_oi_change:+,.0f}"

        # ── 3. MAX PAIN ANALYSIS ──
        if snapshot.max_pain > 0:
            price = snapshot.price
            max_pain = snapshot.max_pain
            pain_diff = price - max_pain
            pain_pct = abs(pain_diff) / max_pain * 100

            if pain_pct < 0.5:
                details["max_pain"] = f"AT Max Pain ({max_pain:.0f})"
                warnings.append("Price at max pain — could stick here")
                mp_score = 40
            elif pain_diff > 0:
                details["max_pain"] = f"ABOVE Max Pain by {pain_diff:.0f}"
                mp_score = 60
            else:
                details["max_pain"] = f"BELOW Max Pain by {abs(pain_diff):.0f}"
                mp_score = 60
        else:
            mp_score = 50
            details["max_pain"] = "N/A"

        # ── 4. OI TREND (Last N readings) ──
        if len(self.oi_history) >= 5:
            recent_pe = sum(h["pe_change"] for h in self.oi_history[-5:])
            recent_ce = sum(h["ce_change"] for h in self.oi_history[-5:])

            if recent_pe > recent_ce * 1.5:
                details["oi_trend"] = "Consistent PE writing (BULLISH)"
                trend_score = 75
            elif recent_ce > recent_pe * 1.5:
                details["oi_trend"] = "Consistent CE writing (BEARISH)"
                trend_score = 75
            else:
                details["oi_trend"] = "Mixed OI trend"
                trend_score = 40
        else:
            trend_score = 50
            details["oi_trend"] = "Building history..."

        # Update previous values
        self.previous_ce_oi = current_ce_oi
        self.previous_pe_oi = current_pe_oi

        # ── COMBINE ──
        factors = {
            "pcr": (pcr_score, 0.3),
            "oi_flow": (oi_score, 0.35),
            "max_pain": (mp_score, 0.15),
            "oi_trend": (trend_score, 0.2),
        }
        confidence = self._calculate_confidence(factors)

        bull_count = sum(1 for d in [pcr_direction, oi_direction]
                         if d == Direction.BULLISH)
        bear_count = sum(1 for d in [pcr_direction, oi_direction]
                         if d == Direction.BEARISH)

        if bull_count > bear_count:
            direction = Direction.BULLISH
        elif bear_count > bull_count:
            direction = Direction.BEARISH
        else:
            direction = Direction.NEUTRAL
            confidence = min(confidence, 40)

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
