"""
============================================
🎯 CONFLUENCE SCORER v2
Why: Instead of simple voting, we score
     agreements across 18 specialized agents.
     Quality of agreement > Quantity.
============================================
"""

from typing import List, Dict
from models.signals import AgentOutput, Direction, ConfluenceResult
from config.settings import Settings


class ConfluenceScorer:
    """
    Evaluates how strongly the 18 agents agree on a direction.
    Applies weights based on AgentCategory (Primary vs Confirmation).
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self.weights = settings.thresholds.agent_weights

    def score(self, agent_outputs: List[AgentOutput]) -> ConfluenceResult:
        result = ConfluenceResult()
        
        bull_score = 0
        bear_score = 0
        total_weight = 0

        for output in agent_outputs:
            result.total_agents += 1
            
            if output.is_blocker:
                result.blocker_agents += 1
                result.blocker_reasons.append(output.blocker_reason)

            if output.direction == Direction.NEUTRAL:
                continue

            weight = self.weights.get(output.agent_name, 0.05)
            
            # Adjust weight based on agent confidence (0 to 1 multiplier)
            confidence_multiplier = output.confidence / 100
            final_weight = weight * confidence_multiplier
            total_weight += final_weight

            if output.direction == Direction.BULLISH:
                bull_score += final_weight
                result.bullish_agents += 1
                result.agreeing_agents.append(output.agent_name)
            elif output.direction == Direction.BEARISH:
                bear_score += final_weight
                result.bearish_agents += 1
                result.disagreeing_agents.append(output.agent_name)

        # Calculate final normalized scores
        if total_weight > 0:
            result.weighted_bull_score = (bull_score / total_weight) * 100
            result.weighted_bear_score = (bear_score / total_weight) * 100
        else:
            result.weighted_bull_score = 0
            result.weighted_bear_score = 0

        # Determine dominant direction and confluence ratio
        if result.weighted_bull_score > result.weighted_bear_score:
            result.dominant_direction = Direction.BULLISH
            result.confluence_ratio = bull_score / total_weight if total_weight else 0
        elif result.weighted_bear_score > result.weighted_bull_score:
            result.dominant_direction = Direction.BEARISH
            result.confluence_ratio = bear_score / total_weight if total_weight else 0
            # swap agreeing/disagreeing lists to match dominant direction
            result.agreeing_agents, result.disagreeing_agents = result.disagreeing_agents, result.agreeing_agents
        else:
            result.dominant_direction = Direction.NEUTRAL
            result.confluence_ratio = 0

        return result
