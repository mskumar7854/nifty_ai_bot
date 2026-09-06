import os
import json
from datetime import datetime
from typing import Dict, Any, Optional

class MetricsLogger:
    """
    Structured metrics telemetry.
    Appends cycle state and regime transitions to a JSONL file.
    Does not control execution - strictly for observability.
    """
    
    def __init__(self, log_dir: str = "data"):
        os.makedirs(log_dir, exist_ok=True)
        self.metrics_file = os.path.join(log_dir, "execution_metrics.jsonl")
        self.transitions_file = os.path.join(log_dir, "regime_transitions.jsonl")
        
        # Stability tracking
        self._last_regime: Optional[str] = None
        self._stable_for_cycles: int = 0
        
    def log_execution_truth(self, payload: Dict[str, Any]):
        """
        Log the canonical decision cycle execution truth to the high-frequency stream.
        """
        try:
            with open(self.metrics_file, "a") as f:
                f.write(json.dumps(payload) + "\n")
        except Exception:
            pass
            
    def log_cycle(self, metrics: Dict[str, Any]):
        """Log the full system state for a single cycle."""
        metrics["timestamp"] = datetime.now().isoformat()
        
        # Track regime stability
        current_regime = metrics.get("regime")
        if current_regime:
            if self._last_regime is None:
                self._last_regime = current_regime
                self._stable_for_cycles = 1
            elif current_regime == self._last_regime:
                self._stable_for_cycles += 1
            else:
                # Regime changed
                self._log_transition(
                    from_regime=self._last_regime,
                    to_regime=current_regime,
                    confidence=metrics.get("regime_confidence", 0.0)
                )
                self._last_regime = current_regime
                self._stable_for_cycles = 1
                
        metrics["classification_stability_cycles"] = self._stable_for_cycles
        
        # Write to JSONL
        try:
            with open(self.metrics_file, "a") as f:
                f.write(json.dumps(metrics) + "\n")
        except Exception:
            # Failsafe so telemetry failure never crashes the trading loop
            pass
            
    def _log_transition(self, from_regime: str, to_regime: str, confidence: float):
        """Explicitly log regime transition zones."""
        transition_event = {
            "timestamp": datetime.now().isoformat(),
            "event": "REGIME_TRANSITION",
            "from": from_regime,
            "to": to_regime,
            "confidence": round(confidence, 2),
            "stable_prior_cycles": self._stable_for_cycles
        }
        try:
            with open(self.transitions_file, "a") as f:
                f.write(json.dumps(transition_event) + "\n")
        except Exception:
            pass
