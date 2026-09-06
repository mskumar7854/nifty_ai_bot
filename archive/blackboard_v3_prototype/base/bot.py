from typing import Any, Dict
from abc import ABC, abstractmethod
from bots.contracts.blackboard import TradingBlackboard
from bots.contracts.reports import BotHealth

class DomainBot(ABC):
    """
    Base class for all Domain Bots in the AI Company architecture.
    """
    def __init__(self, name: str, state_manager: Any = None):
        self.name = name
        self.state_manager = state_manager
        
    @abstractmethod
    def evaluate(self, blackboard: TradingBlackboard) -> Any:
        """
        Pure function. Evaluates the blackboard and returns a specific Domain Report.
        Must not mutate the blackboard directly.
        """
        pass
        
    def check_health(self) -> BotHealth:
        """
        Returns the health status of this bot. Can be overridden.
        """
        return BotHealth(
            bot_name=self.name,
            status="HEALTHY",
            latency_ms=0.0,
            data_freshness_sec=0.0,
            message="OK"
        )
