"""
============================================
📅 EXPIRY AGENT
Why: Expiry days have intense gamma risk,
     theta decay traps, and pin risk around
     round numbers.
============================================
"""

import pandas as pd
from datetime import datetime

from agents.base_agent import BaseAgent, AgentCategory
from models.signals import AgentOutput, Direction, Strength, MarketSnapshot
from config.settings import Settings


class ExpiryAgent(BaseAgent):
    """
    Acts primarily as a FILTER on or near expiry days.
    Warns about gamma blasts and theta traps.
    """

    def __init__(self, settings: Settings):
        super().__init__("expiry", settings, AgentCategory.FILTER)
        self.th = settings.thresholds

    def analyze(self, df: pd.DataFrame, snapshot: MarketSnapshot) -> AgentOutput:
        warnings = []
        details = {}
        
        # We need DTE (Days to Expiry). If not provided properly, default to neutral
        dte = snapshot.days_to_expiry

        details["dte"] = dte
        
        if not snapshot.is_expiry_day and dte > self.th.theta_decay_acceleration_dte:
            return self._neutral_output(f"Normal day (DTE: {dte})")

        score = 50
        direction = Direction.NEUTRAL
        
        if snapshot.is_expiry_day:
            details["day_type"] = "EXPIRY DAY"
            warnings.append("🚨 EXPIRY DAY: High Gamma/Theta risk. Quick scalps only.")
            
            # Check Pin Risk near round numbers
            price = snapshot.price
            nearest_hundred = round(price / 100) * 100
            diff = abs(price - nearest_hundred)
            
            # If price is very close to a round number strike
            if diff <= (price * (self.th.pin_risk_range / 100)):
                warnings.append(f"📌 Pin Risk: Price is sticky around {nearest_hundred}")
                score = 30  # Low confidence, high manipulation
                details["pin_risk"] = f"Near {nearest_hundred}"

        elif dte <= self.th.theta_decay_acceleration_dte:
            details["day_type"] = f"{dte} DTE - Accelerated Theta"
            warnings.append("⚠️ Rapid Theta decay phase. Avoid holding deep OTM.")
            score = 45
            
        strength = Strength.MODERATE if score >= 45 else Strength.WEAK
        
        return AgentOutput(
            agent_name=self.name,
            timestamp=datetime.now(),
            direction=direction,
            confidence=score,
            strength=strength,
            details=details,
            warnings=warnings,
        )
