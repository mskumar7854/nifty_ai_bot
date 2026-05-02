"""
============================================
🔗 CORRELATION AGENT
Why: Nifty heavily depends on Bank Nifty,
     Reliance, HDFC Bank, and Global futures.
     If Nifty is breaking out but Bank Nifty
     is tanking, it's probably a fakeout.
============================================
"""

import pandas as pd
from datetime import datetime

from agents.base_agent import BaseAgent, AgentCategory
from models.signals import AgentOutput, Direction, Strength, MarketSnapshot
from config.settings import Settings


class CorrelationAgent(BaseAgent):
    """
    Checks correlation with:
    1. Bank Nifty (Heaviest sector)
    2. Global Cues (Dow Futures / SGX)
    """

    def __init__(self, settings: Settings):
        super().__init__("correlation", settings, AgentCategory.CONFIRMATION)
        self.th = settings.thresholds

    def analyze(self, df: pd.DataFrame, snapshot: MarketSnapshot) -> AgentOutput:
        warnings = []
        details = {}

        bnf_change = snapshot.banknifty_change_pct
        dow_fut = snapshot.dow_futures

        # Without external data, act neutral
        if bnf_change == 0 and dow_fut == 0:
            return self._neutral_output("No correlation data available")

        # ── 1. BANK NIFTY (Primary Driver) ──
        if bnf_change >= 0.5:
            bnf_dir = Direction.BULLISH
            bnf_score = 80
            details["banknifty"] = f"STRONG BULLISH (+{bnf_change:.2f}%)"
        elif bnf_change > 0:
            bnf_dir = Direction.BULLISH
            bnf_score = 55
            details["banknifty"] = f"MILD BULLISH (+{bnf_change:.2f}%)"
        elif bnf_change <= -0.5:
            bnf_dir = Direction.BEARISH
            bnf_score = 80
            details["banknifty"] = f"STRONG BEARISH ({bnf_change:.2f}%)"
        else:
            bnf_dir = Direction.BEARISH
            bnf_score = 55
            details["banknifty"] = f"MILD BEARISH ({bnf_change:.2f}%)"

        # ── 2. GLOBAL CUES ──
        if dow_fut >= 0.5:
            dow_dir = Direction.BULLISH
            dow_score = 70
            details["global"] = f"BULLISH (+{dow_fut:.2f}%)"
        elif dow_fut <= -0.5:
            dow_dir = Direction.BEARISH
            dow_score = 70
            details["global"] = f"BEARISH ({dow_fut:.2f}%)"
        else:
            dow_dir = Direction.NEUTRAL
            dow_score = 40
            details["global"] = f"NEUTRAL ({dow_fut:.2f}%)"

        # ── COMBINE ──
        bull_weight = 0
        bear_weight = 0

        if bnf_dir == Direction.BULLISH:
            bull_weight += bnf_score * self.th.banknifty_weight
        elif bnf_dir == Direction.BEARISH:
            bear_weight += bnf_score * self.th.banknifty_weight

        if dow_dir == Direction.BULLISH:
            bull_weight += dow_score * (1 - self.th.banknifty_weight)
        elif dow_dir == Direction.BEARISH:
            bear_weight += dow_score * (1 - self.th.banknifty_weight)

        if bull_weight > bear_weight:
            direction = Direction.BULLISH
            confidence = bull_weight
        elif bear_weight > bull_weight:
            direction = Direction.BEARISH
            confidence = bear_weight
        else:
            direction = Direction.NEUTRAL
            confidence = 30

        # Divergence warning
        if bnf_dir != dow_dir and dow_dir != Direction.NEUTRAL:
            warnings.append("⚠️ Domestic & Global cues divergent")

        strength = Strength.STRONG if confidence >= 70 else (
            Strength.MODERATE if confidence >= 45 else Strength.WEAK
        )

        return AgentOutput(
            agent_name=self.name,
            timestamp=datetime.now(),
            direction=direction,
            confidence=round(confidence, 1),
            strength=strength,
            details=details,
            warnings=warnings,
        )
