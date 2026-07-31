from bots.base.bot import DomainBot
from bots.contracts.blackboard import TradingBlackboard
from bots.contracts.reports import SentimentReport

class SentimentBot(DomainBot):
    def __init__(self, name="SentimentBot", state_manager=None):
        super().__init__(name, state_manager)
        self.plugins = []
        
    def evaluate(self, blackboard: TradingBlackboard) -> SentimentReport:
        plugin_facts = {}
        for p in self.plugins:
            plugin_facts[p.name] = p.analyze(blackboard)
            
        return SentimentReport(
            bias="NEUTRAL",
            confidence=0.0,
            plugin_data=plugin_facts
        )
