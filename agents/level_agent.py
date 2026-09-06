"""
============================================
📏 LEVEL AGENT
Why: Markets react strongly at key technical 
     levels (CPR, Pivots, Previous Day High/Low, 
     Round numbers).
============================================
"""

import pandas as pd
from datetime import datetime

from agents.base_agent import BaseAgent, AgentCategory
from models import AgentOutput, Direction, Strength, MarketSnapshot
from config.settings import Settings


class LevelAgent(BaseAgent):
    """
    Analyzes price proximity to key levels.
    """

    def __init__(self, settings: Settings):
        super().__init__("level", settings, AgentCategory.CONFIRMATION)
        self.th = settings.thresholds

    def analyze(self, df: pd.DataFrame, snapshot: MarketSnapshot) -> AgentOutput:
        warnings = []
        details = {}
        
        price = snapshot.price
        prox = self.th.level_proximity_points
        
        # Build list of key levels
        levels = {
            "Prev Day High": snapshot.prev_day_high,
            "Prev Day Low": snapshot.prev_day_low,
            "Prev Day Close": snapshot.prev_day_close,
            "Day Open": snapshot.day_open,
            "Pivot": snapshot.pivot,
            "R1": snapshot.r1,
            "S1": snapshot.s1,
            "CPR Top": snapshot.cpr_top,
            "CPR Bottom": snapshot.cpr_bottom,
            "Round Number (Upper)": (round((price + self.th.round_number_interval/2) / self.th.round_number_interval) * self.th.round_number_interval),
            "Round Number (Lower)": (round((price - self.th.round_number_interval/2) / self.th.round_number_interval) * self.th.round_number_interval),
        }
        
        # Filter out 0s
        levels = {k: v for k, v in levels.items() if v > 0}
        
        if not levels:
            return self._neutral_output("No levels loaded")

        nearby_levels = []
        for name, level_price in levels.items():
            if abs(price - level_price) <= prox:
                nearby_levels.append((name, level_price))
                
        details["nearby_levels"] = [f"{n}: {p:.1f}" for n, p in nearby_levels]

        # Determine reaction
        # If we are slightly above a level, it might act as support (Bullish)
        # If we are slightly below a level, it might act as resistance (Bearish)

        bullish_score = 0
        bearish_score = 0
        
        for name, level_price in nearby_levels:
            if price > level_price:
                bullish_score += 10
                details["reaction"] = f"Holding above {name}"
            elif price < level_price:
                bearish_score += 10
                details["reaction"] = f"Rejecting below {name}"

        score = max(bullish_score, bearish_score) * 5
        score = min(score, 90)

        if bullish_score > bearish_score:
            direction = Direction.BULLISH
        elif bearish_score > bullish_score:
            direction = Direction.BEARISH
        else:
            direction = Direction.NEUTRAL
            score = 30
            if not nearby_levels:
                details["status"] = "In open space (No nearby key levels)"

        if nearby_levels:
            warnings.append(f"Price is at key level zone: {nearby_levels[0][0]}")

        strength = Strength.STRONG if score >= 75 else (
            Strength.MODERATE if score >= 50 else Strength.WEAK
        )
        
        return AgentOutput(
            agent_name=self.name,
            timestamp=datetime.now(),
            direction=direction,
            confidence=round(score, 1),
            strength=strength,
            details=details,
            warnings=warnings,
        )
