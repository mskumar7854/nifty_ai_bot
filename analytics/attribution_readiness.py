import os
import json
import logging
from analytics.confidence_calibration import confidence_calibration

class AttributionReadiness:
    """
    Determines when enough data exists to trust future attribution (Sprint 3 features).
    """
    def __init__(self):
        self.logger = logging.getLogger("attribution_readiness")
        
        self.thresholds = {
            "confidence_calibration": {"min_trades": 200},
            "agent_attribution": {"min_trades": 300},
            "kelly": {"min_trades": 300, "max_ece": 0.05}
        }

    def check_readiness(self) -> dict:
        metrics = confidence_calibration.calculate_metrics()
        trades = metrics.get("trades", 0)
        ece = metrics.get("ece", 1.0)
        
        readiness = {
            "trades": trades,
            "current_ece": ece,
            "confidence_calibration_ready": trades >= self.thresholds["confidence_calibration"]["min_trades"],
            "agent_attribution_ready": trades >= self.thresholds["agent_attribution"]["min_trades"],
            "kelly_ready": (trades >= self.thresholds["kelly"]["min_trades"]) and (ece <= self.thresholds["kelly"]["max_ece"])
        }
        
        return readiness

attribution_readiness = AttributionReadiness()
