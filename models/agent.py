from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional
from enum import Enum

from .signal import Direction, Strength

@dataclass
class AgentOutput:
    agent_name: str
    timestamp: datetime
    direction: Direction
    confidence: float
    strength: Strength
    details: Dict = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    is_blocker: bool = False
    blocker_reason: str = ""
    sub_scores: Dict[str, float] = field(default_factory=dict)
    weight: float = 1.0

    def get_clamped_confidence(self) -> float:
        val = self.confidence / 100.0 if self.confidence > 1 else self.confidence
        return max(0.1, min(val, 0.95))

    def to_dict(self) -> dict:
        return {
            "agent": self.agent_name,
            "time": self.timestamp.strftime("%H:%M:%S"),
            "direction": self.direction.value,
            "confidence": self.confidence,
            "strength": self.strength.value,
            "details": self.details,
            "warnings": self.warnings,
            "is_blocker": self.is_blocker,
            "weight": self.weight,
        }

@dataclass
class ConfluenceResult:
    total_agents: int = 0
    bullish_agents: int = 0
    bearish_agents: int = 0
    neutral_agents: int = 0
    blocker_agents: int = 0
    
    weighted_bull_score: float = 0
    weighted_bear_score: float = 0
    
    confluence_ratio: float = 0
    dominant_direction: Direction = Direction.NEUTRAL
    
    agreeing_agents: List[str] = field(default_factory=list)
    disagreeing_agents: List[str] = field(default_factory=list)
    blocker_reasons: List[str] = field(default_factory=list)
