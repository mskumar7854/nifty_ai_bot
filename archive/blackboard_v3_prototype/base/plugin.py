from typing import Any, Dict
from abc import ABC, abstractmethod
from bots.contracts.blackboard import TradingBlackboard

class IntelligencePlugin(ABC):
    """
    Base class for dynamically loaded intelligence plugins (e.g. PriceActionPlugin, MomentumPlugin).
    """
    def __init__(self, name: str):
        self.name = name
        
    @abstractmethod
    def analyze(self, blackboard: TradingBlackboard) -> Dict[str, Any]:
        """
        Returns objective facts discovered by the plugin.
        These facts are aggregated by the parent DomainBot.
        """
        pass
