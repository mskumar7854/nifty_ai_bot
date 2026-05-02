"""
============================================
🏛️ INSTITUTIONAL AGENT
Why: Tracks FII/DII net flows. Don't fight
     the institutions.
============================================
"""

import pandas as pd
from datetime import datetime

from agents.base_agent import BaseAgent, AgentCategory
from models.signals import AgentOutput, Direction, Strength, MarketSnapshot
from config.settings import Settings


class InstitutionalAgent(BaseAgent):
    """
    Usually End-of-Day data, but can use real-time
    block deals or futures OI to estimate bias.
    """

    def __init__(self, settings: Settings):
        super().__init__("institutional", settings, AgentCategory.SPECIAL)
        self.th = settings.thresholds

    def analyze(self, df: pd.DataFrame, snapshot: MarketSnapshot) -> AgentOutput:
        warnings = []
        details = {}

        fii_net = snapshot.fii_net
        dii_net = snapshot.dii_net
        fii_fut = snapshot.fii_index_futures_oi_change

        if fii_net == 0 and fii_fut == 0:
            return self._neutral_output("No Institutional Data")

        details["fii_cash"] = f"₹{fii_net:,.0f} Cr"
        details["dii_cash"] = f"₹{dii_net:,.0f} Cr"
        details["fii_fut_change"] = f"{fii_fut:,.0f} contracts"

        score = 50
        bullish_factors = 0
        bearish_factors = 0

        if fii_net > self.th.fii_bullish_threshold:
            bullish_factors += 1
            score += 15
        elif fii_net < self.th.fii_bearish_threshold:
            bearish_factors += 1
            score += 15

        if dii_net > self.th.fii_bullish_threshold:
            bullish_factors += 0.5
        elif dii_net < self.th.fii_bearish_threshold:
            bearish_factors += 0.5

        if fii_fut > 5000:
            bullish_factors += 1
            score += 10
        elif fii_fut < -5000:
            bearish_factors += 1
            score += 10

        if bullish_factors > bearish_factors:
            direction = Direction.BULLISH
        elif bearish_factors > bullish_factors:
            direction = Direction.BEARISH
        else:
            direction = Direction.NEUTRAL

        score = min(95, score)

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
