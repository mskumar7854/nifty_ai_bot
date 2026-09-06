from bots.base.bot import DomainBot
from bots.contracts.blackboard import TradingBlackboard
from bots.contracts.reports import OptionsReport

class OptionsBot(DomainBot):
    def __init__(self, name="OptionsBot", state_manager=None):
        super().__init__(name, state_manager)
        self.plugins = []
        
    def evaluate(self, blackboard: TradingBlackboard) -> OptionsReport:
        snap = blackboard.snapshot
        
        plugin_facts = {}
        for p in self.plugins:
            plugin_facts[p.name] = p.analyze(blackboard)
            
        report = OptionsReport(
            directional_bias="NEUTRAL",
            oi_pressure_score=0.0,
            gamma_risk_level="LOW",
            recommended_contract="NONE",
            confidence=0.0,
            plugin_data=plugin_facts
        )
        return report
