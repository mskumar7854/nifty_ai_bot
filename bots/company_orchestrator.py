from typing import Dict, Any, List
import logging
from bots.contracts.blackboard import TradingBlackboard, MarketSnapshot
from bots.base.bot import DomainBot
from bots.core_services.supervisor import Supervisor

logger = logging.getLogger("CompanyOrchestrator")

class CompanyOrchestrator:
    """
    Central Coordinator. 
    Implements Rule 1: Only Orchestrator calls bots, bots never call each other.
    """
    def __init__(self, 
                 supervisor: Supervisor,
                 market_bot: DomainBot,
                 options_bot: DomainBot,
                 sentiment_bot: DomainBot,
                 signal_bot: DomainBot,
                 portfolio_bot: DomainBot,
                 decision_bot: DomainBot,
                 oms_bot: DomainBot,
                 event_bus_publish_fn=None):
        
        self.supervisor = supervisor
        self.market_bot = market_bot
        self.options_bot = options_bot
        self.sentiment_bot = sentiment_bot
        self.signal_bot = signal_bot
        self.portfolio_bot = portfolio_bot
        self.decision_bot = decision_bot
        self.oms_bot = oms_bot
        self.event_bus_publish_fn = event_bus_publish_fn
        
    def evaluate_tick(self, snapshot: MarketSnapshot) -> TradingBlackboard:
        """
        Main trading loop evaluation for a single snapshot.
        """
        if self.supervisor.is_safe_mode:
            logger.warning("Supervisor in SAFE MODE. Dropping tick.")
            return None
            
        # Initialize Blackboard
        blackboard = TradingBlackboard(snapshot=snapshot)
        
        # 1. Intelligence Phase (Facts) - Could run in parallel
        market_report = self.market_bot.evaluate(blackboard)
        blackboard = blackboard.with_report(market_report)
        
        options_report = self.options_bot.evaluate(blackboard)
        blackboard = blackboard.with_report(options_report)
        
        sentiment_report = self.sentiment_bot.evaluate(blackboard)
        blackboard = blackboard.with_report(sentiment_report)
        
        # 2. Signal Phase (Opinions based on Facts)
        signal_report = self.signal_bot.evaluate(blackboard)
        blackboard = blackboard.with_report(signal_report)
        
        # 3. Portfolio & Risk Phase
        portfolio_report = self.portfolio_bot.evaluate(blackboard)
        blackboard = blackboard.with_report(portfolio_report)
        
        # 4. Decision Phase
        decision_report = self.decision_bot.evaluate(blackboard)
        blackboard = blackboard.with_report(decision_report)
        
        # 5. OMS Phase (If approved)
        if decision_report.final_decision == "EXECUTE":
            oms_report = self.oms_bot.evaluate(blackboard)
            blackboard = blackboard.with_report(oms_report)
            
        # 6. Publish to Async Event Bus (Analytics / Learning)
        if self.event_bus_publish_fn:
            self.event_bus_publish_fn("EVALUATION_COMPLETE", blackboard.model_dump())
            
        return blackboard
