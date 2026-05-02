"""
============================================
ENHANCED BASE AGENT v2
Adds: blocker capability, sub-scoring,
      category tagging, state memory
============================================
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional, List, Dict
from enum import Enum
import pandas as pd

from models.signals import AgentOutput, Direction, Strength, MarketSnapshot
from utils.logger import AgentLogger
from config.settings import Settings


class AgentCategory(Enum):
    PRIMARY = "primary"           # core signal generators
    CONFIRMATION = "confirmation" # confirms/denies signals
    FILTER = "filter"             # blocks bad signals
    SPECIAL = "special"           # optional enhancers


class BaseAgent(ABC):

    def __init__(self, name: str, settings: Settings,
                 category: AgentCategory = AgentCategory.PRIMARY):
        self.name = name
        self.category = category
        self.settings = settings
        self.logger = AgentLogger(name)
        self.last_output: Optional[AgentOutput] = None
        self.run_count = 0
        self.is_active = True

        # v2: State memory — agents remember recent outputs
        self.output_history: List[AgentOutput] = []
        self.max_history = 50
        self.consecutive_same_direction = 0
        self.last_direction: Optional[Direction] = None

    @abstractmethod
    def analyze(self, df: pd.DataFrame, snapshot: MarketSnapshot) -> AgentOutput:
        pass

    def run(self, df: pd.DataFrame, snapshot: MarketSnapshot) -> AgentOutput:
        if not self.is_active:
            return self._neutral_output("Agent disabled")

        try:
            self.run_count += 1
            output = self.analyze(df, snapshot)
            self.last_output = output

            # Track direction consistency
            if output.direction == self.last_direction:
                self.consecutive_same_direction += 1
            else:
                self.consecutive_same_direction = 1
            self.last_direction = output.direction

            # Store history
            self.output_history.append(output)
            if len(self.output_history) > self.max_history:
                self.output_history = self.output_history[-self.max_history:]

            self.logger.signal(
                f"[bold]{output.direction.value}[/bold] | "
                f"Conf: {output.confidence:.0f}% | "
                f"{output.strength.value}"
                f"{' | 🚫 BLOCKER' if output.is_blocker else ''}"
            )

            return output

        except Exception as e:
            self.logger.error(f"Error: {str(e)}")
            return self._neutral_output(f"Error: {str(e)}")

    def _neutral_output(self, reason: str = "") -> AgentOutput:
        return AgentOutput(
            agent_name=self.name,
            timestamp=datetime.now(),
            direction=Direction.NEUTRAL,
            confidence=0,
            strength=Strength.WEAK,
            details={"reason": reason},
        )

    def _blocker_output(self, reason: str) -> AgentOutput:
        """Return a blocker output that prevents trading"""
        return AgentOutput(
            agent_name=self.name,
            timestamp=datetime.now(),
            direction=Direction.NEUTRAL,
            confidence=0,
            strength=Strength.WEAK,
            details={"blocker_reason": reason},
            warnings=[f"🚫 BLOCKED: {reason}"],
            is_blocker=True,
            blocker_reason=reason,
        )

    def _calculate_confidence(self, factors: dict) -> float:
        total_weight = sum(w for _, w in factors.values())
        if total_weight == 0:
            return 0
        weighted_sum = sum(v * w for v, w in factors.values())
        return min(100, max(0, (weighted_sum / total_weight)))

    def get_direction_consistency(self) -> float:
        """How consistently has this agent been giving same direction"""
        if len(self.output_history) < 5:
            return 0.5

        recent = self.output_history[-10:]
        if not recent:
            return 0.5

        directions = [o.direction for o in recent]
        most_common = max(set(directions), key=directions.count)
        consistency = directions.count(most_common) / len(directions)
        return consistency

    def get_status(self) -> dict:
        return {
            "name": self.name,
            "category": self.category.value,
            "active": self.is_active,
            "runs": self.run_count,
            "consistency": f"{self.get_direction_consistency():.0%}",
            "consecutive": self.consecutive_same_direction,
            "last_output": self.last_output.to_dict() if self.last_output else None,
        }
