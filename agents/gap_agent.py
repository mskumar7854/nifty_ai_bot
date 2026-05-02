"""
============================================
🫧 GAP AGENT
Why: "Gaps are meant to be filled."
     Runaway gaps vs Exhaustion gaps.
============================================
"""

import pandas as pd
from datetime import datetime

from agents.base_agent import BaseAgent, AgentCategory
from models.signals import AgentOutput, Direction, Strength, MarketSnapshot
from config.settings import Settings


class GapAgent(BaseAgent):
    """
    Identifies morning gaps, partial fills, and gap-and-go scenarios.
    """

    def __init__(self, settings: Settings):
        super().__init__("gap", settings, AgentCategory.FILTER)
        self.th = settings.thresholds

    def analyze(self, df: pd.DataFrame, snapshot: MarketSnapshot) -> AgentOutput:
        warnings = []
        details = {}
        
        if len(df) < 5:
            return self._neutral_output()

        price = snapshot.price
        prev_close = snapshot.prev_day_close
        
        if prev_close == 0:
            prev_close = df['close'].iloc[-2] # fallback

        day_open = snapshot.day_open if snapshot.day_open > 0 else df['open'].iloc[-1]
        
        gap = day_open - prev_close
        abs_gap = abs(gap)

        details["gap"] = f"{gap:+.1f} pts"

        if abs_gap < self.th.gap_significant_points:
            return self._neutral_output("No significant gap")

        # Gap analysis
        direction = Direction.NEUTRAL
        score = 50

        # Gap Up
        if gap > 0:
            details["gap_type"] = "Gap Up"
            if price < day_open: # fading the gap
                direction = Direction.BEARISH
                score = 70
                details["action"] = "Fading Gap Up (Targeting Fill)"
            else:
                direction = Direction.BULLISH
                score = 65
                details["action"] = "Gap and Go (Strength)"
                
        # Gap Down
        elif gap < 0:
            details["gap_type"] = "Gap Down"
            if price > day_open: # fading the gap
                direction = Direction.BULLISH
                score = 70
                details["action"] = "Fading Gap Down (Targeting Fill)"
            else:
                direction = Direction.BEARISH
                score = 65
                details["action"] = "Gap and Go (Weakness)"

        # Check if gap is filled
        if (gap > 0 and price <= prev_close) or (gap < 0 and price >= prev_close):
            details["gap_status"] = "FILLED"
            direction = Direction.NEUTRAL
            score = 30
            warnings.append("Gap has been filled. Look for bounce/rejection structure.")
        else:
            details["gap_status"] = "UNFILLED"

        strength = Strength.STRONG if score >= 75 else (
            Strength.MODERATE if score >= 50 else Strength.WEAK
        )
        
        return AgentOutput(
            agent_name=self.name,
            timestamp=datetime.now(),
            direction=direction,
            confidence=score,
            strength=strength,
            details=details,
            warnings=warnings,
        )
