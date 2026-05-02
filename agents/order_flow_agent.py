"""
============================================
💹 ORDER FLOW AGENT
Why: Order flow shows immediate intention.
     Imbalances between bids/asks indicate 
     aggressive buyers/sellers.
============================================
"""

import pandas as pd
from datetime import datetime

from agents.base_agent import BaseAgent, AgentCategory
from models.signals import AgentOutput, Direction, Strength, MarketSnapshot
from config.settings import Settings


class OrderFlowAgent(BaseAgent):
    """
    Analyzes Volume Imbalances, Large Trade tracking.
    """

    def __init__(self, settings: Settings):
        super().__init__("order_flow", settings, AgentCategory.CONFIRMATION)
        self.th = settings.thresholds

    def analyze(self, df: pd.DataFrame, snapshot: MarketSnapshot) -> AgentOutput:
        warnings = []
        details = {}
        
        bid_vol = snapshot.bid_volume
        ask_vol = snapshot.ask_volume
        
        if bid_vol == 0 and ask_vol == 0:
            return self._neutral_output("No Order Flow Data Available")

        total_vol = bid_vol + ask_vol
        bid_pct = bid_vol / total_vol
        ask_pct = ask_vol / total_vol
        
        details["bid_pct"] = f"{bid_pct:.1%}"
        details["ask_pct"] = f"{ask_pct:.1%}"
        
        # ── 1. AGGRESSIVE BUYING/SELLING ──
        if bid_vol > ask_vol * self.th.bid_ask_imbalance_threshold:
            direction = Direction.BEARISH # High bid volume = Sellers are hitting the bid (aggressive selling)
            score = 75
            details["imbalance"] = "Aggressive Selling (Hitting Bids)"
            warnings.append("Heavy sellers hitting the bid")
        elif ask_vol > bid_vol * self.th.bid_ask_imbalance_threshold:
            direction = Direction.BULLISH # High ask volume = Buyers are lifting the offer (aggressive buying)
            score = 75
            details["imbalance"] = "Aggressive Buying (Lifting Offers)"
            warnings.append("Heavy buyers lifting the offer")
        else:
            direction = Direction.NEUTRAL
            score = 40
            details["imbalance"] = "Balanced"

        # ── 2. LARGE ORDERS ──
        if snapshot.large_buy_orders > snapshot.large_sell_orders * 1.5:
            score = min(95, score + 15)
            direction = Direction.BULLISH if direction == Direction.NEUTRAL else direction
            details["large_orders"] = "Bullish Dominance"
        elif snapshot.large_sell_orders > snapshot.large_buy_orders * 1.5:
            score = min(95, score + 15)
            direction = Direction.BEARISH if direction == Direction.NEUTRAL else direction
            details["large_orders"] = "Bearish Dominance"
            
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
