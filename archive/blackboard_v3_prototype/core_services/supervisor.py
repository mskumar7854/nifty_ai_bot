from typing import List, Dict
import logging
from bots.base.bot import DomainBot

logger = logging.getLogger("Supervisor")

class Supervisor:
    """
    Supervisor Layer.
    Responsible for monitoring bot health, latency, broker connectivity, and triggering safe mode.
    """
    def __init__(self, bots: List[DomainBot]):
        self.bots = bots
        self.is_safe_mode = False
        
    def run_health_checks(self) -> Dict[str, str]:
        """
        Polls every bot for its health status.
        """
        health_status = {}
        for bot in self.bots:
            try:
                report = bot.check_health()
                health_status[bot.name] = report.status
                if report.status == "FATAL":
                    self.trigger_safe_mode(f"Bot {bot.name} is FATAL: {report.message}")
            except Exception as e:
                health_status[bot.name] = "ERROR"
                logger.error(f"Health check failed for {bot.name}: {e}")
                
        return health_status
        
    def trigger_safe_mode(self, reason: str):
        """
        Stops all new trading activity.
        """
        logger.critical(f"SAFE MODE TRIGGERED: {reason}")
        self.is_safe_mode = True
