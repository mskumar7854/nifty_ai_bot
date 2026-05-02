"""
============================================
🔺 DELTA/GAMMA AGENT
Why: Tracks net market maker exposure.
     Gamma walls act as heavy resistance unless
     squeezed.
============================================
"""

import pandas as pd
from datetime import datetime

from agents.base_agent import BaseAgent, AgentCategory
from models.signals import AgentOutput, Direction, Strength, MarketSnapshot
from config.settings import Settings


class DeltaGammaAgent(BaseAgent):
    """
    Advanced Options Greeks Analysis.
    Requires live greek calculations.
    """

    def __init__(self, settings: Settings):
        super().__init__("delta_gamma", settings, AgentCategory.SPECIAL)
        self.th = settings.thresholds

    def analyze(self, df: pd.DataFrame, snapshot: MarketSnapshot) -> AgentOutput:
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

        net_delta = snapshot.net_delta
        net_gamma = snapshot.net_gamma

        if net_delta == 0 and net_gamma == 0:
            return self._neutral_output("Greeks Data Missing or Zero")

        details["net_delta"] = f"{net_delta:,.0f}"
        details["net_gamma"] = f"{net_gamma:,.0f}"

        score = 50
        
        # Dealer long gamma vs short gamma (simplified proxy)
        if net_gamma < -self.th.gamma_wall_threshold:
            details["gamma_regime"] = "Short Gamma (High Volatility, Trend Chasing)"
            warnings.append("⚠️ Short Gamma Regime: Expect wild moves and overshoots.")
            # In short gamma, dealers hedge by buying when market goes up, accelerating it
            direction = Direction.NEUTRAL  # Relies on other agents for direction
            score = 60
        elif net_gamma > self.th.gamma_wall_threshold:
            details["gamma_regime"] = "Long Gamma (Low Volatility, Mean Reversion)"
            # Dealers hedge by selling when market goes up, suppressing volatility
            direction = Direction.NEUTRAL
            score = 60
        else:
            details["gamma_regime"] = "Neutral Gamma"
            direction = Direction.NEUTRAL

        # Delta exposure
        if net_delta > self.th.delta_neutral_range[1]:
            direction = Direction.BULLISH
            score = 75
            details["delta_bias"] = "Bullish Dealers"
        elif net_delta < self.th.delta_neutral_range[0]:
            direction = Direction.BEARISH
            score = 75
            details["delta_bias"] = "Bearish Dealers"

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
