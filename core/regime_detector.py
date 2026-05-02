"""
============================================
🗺️ REGIME DETECTOR v2
Why: The same strategy fails when the regime
     changes. We must adapt rules based on 
     current market conditions.
============================================
"""

from typing import List
from models.signals import AgentOutput, MarketRegime, MarketSnapshot, Direction
from agents.base_agent import AgentCategory


class RegimeDetector:
    """
    Synthesizes outputs from Volatility, Trend, and Structure agents
    to determine the current overarching Market Regime.
    """

    def detect(self, snapshot: MarketSnapshot, agent_outputs: List[AgentOutput]) -> MarketRegime:
        try:
            volatility_output = next((o for o in agent_outputs if o.agent_name == "volatility"), None)
            market_output = next((o for o in agent_outputs if o.agent_name == "market"), None)
            consolidation_output = next((o for o in agent_outputs if o.agent_name == "consolidation"), None)
            gap_output = next((o for o in agent_outputs if o.agent_name == "gap"), None)

            if volatility_output and volatility_output.details.get("regime") == MarketRegime.SQUEEZE.value:
                return MarketRegime.SQUEEZE

            if consolidation_output and consolidation_output.confidence > 50 and consolidation_output.direction == Direction.NEUTRAL:
                return MarketRegime.RANGING

            is_high_vol = snapshot.atr > (snapshot.atr_15m * 1.5) if snapshot.atr_15m else False

            if not market_output:
                return MarketRegime.VOLATILE if is_high_vol else MarketRegime.RANGING

            if market_output.direction == Direction.BULLISH and market_output.confidence > 60:
                return MarketRegime.TRENDING_UP
            elif market_output.direction == Direction.BEARISH and market_output.confidence > 60:
                return MarketRegime.TRENDING_DOWN
            elif is_high_vol:
                return MarketRegime.VOLATILE
            else:
                return MarketRegime.RANGING
        except Exception as e:
            print(f"Regime detection error: {e}")
            return MarketRegime.UNKNOWN
