"""
============================================
🔄 CONSOLIDATION AGENT
Why: Breakouts from tight consolidations are
     the highest probability trades. Avoids
     chopping in the same box.
============================================
"""

import pandas as pd
from datetime import datetime

from agents.base_agent import BaseAgent, AgentCategory
from models import AgentOutput, Direction, Strength, MarketSnapshot
from config.settings import Settings


class ConsolidationAgent(BaseAgent):
    """
    Detects ranges, boxes, and flags.
    Waits for breakout volume confirmation.
    """

    def __init__(self, settings: Settings):
        super().__init__("consolidation", settings, AgentCategory.CONFIRMATION)
        self.th = settings.thresholds

    def analyze(self, df: pd.DataFrame, snapshot: MarketSnapshot) -> AgentOutput:
        warnings = []
        details = {}
        
        min_candles = self.th.consolidation_min_candles
        if len(df) < min_candles + 5:
            return self._neutral_output()

        # Lookback window for consolidation
        window = df.tail(min_candles + 5)
        consolidation_window = window.iloc[:-2] # Exclude last 2 candles for breakout check
        
        recent_high = consolidation_window['high'].max()
        recent_low = consolidation_window['low'].min()
        box_range = recent_high - recent_low
        
        atr = snapshot.atr
        if atr == 0:
            atr = 20

        # Check if it was tightly consolidating
        is_consolidation = box_range < (atr * self.th.consolidation_range_atr_ratio * min_candles/2)
        
        if not is_consolidation:
            return self._neutral_output("No tight consolidation box detected")
            
        details["box_high"] = f"{recent_high:.1f}"
        details["box_low"] = f"{recent_low:.1f}"
        details["box_range"] = f"{box_range:.1f} pts"

        # Check Breakout
        current_price = snapshot.price
        direction = Direction.NEUTRAL
        score = 50

        if current_price > recent_high:
            direction = Direction.BULLISH
            score = 80
            details["breakout"] = "UPWARD"
            warnings.append("Bullish Box Breakout")
        elif current_price < recent_low:
            direction = Direction.BEARISH
            score = 80
            details["breakout"] = "DOWNWARD"
            warnings.append("Bearish Box Breakdown")
        else:
            details["breakout"] = "Still inside box"
            score = 20

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
