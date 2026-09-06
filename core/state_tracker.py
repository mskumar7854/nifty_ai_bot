import logging
from typing import Optional

logger = logging.getLogger("state_tracker")

class StateTracker:
    """
    Memory layer for tracking system state transitions.
    Prevents log spam by emitting telemetry ONLY when state changes.
    """
    def __init__(self):
        self.last_environment_state: Optional[bool] = None
        self.last_environment_reason: Optional[str] = None
        
        self.last_regime_state: Optional[str] = None
        
        self.last_execution_state: Optional[bool] = None
        self.last_execution_reason: Optional[str] = None
        
        self.last_uncertainty_band: Optional[float] = None

    def track_environment(self, is_valid: bool, reason: str = "") -> bool:
        """Returns True if state changed, allowing caller to log."""
        changed = False
        if self.last_environment_state != is_valid or self.last_environment_reason != reason:
            changed = True
            
            old_state_str = "VALID" if self.last_environment_state else ("INVALID" if self.last_environment_state is False else "NONE")
            new_state_str = "VALID" if is_valid else "INVALID"
            
            if old_state_str != "NONE" or not is_valid:
                logger.info(
                    f"🔄 ENVIRONMENT_STATE_CHANGED: {old_state_str} → {new_state_str} | "
                    f"reason=\"{reason}\""
                )
            elif old_state_str == "NONE" and is_valid:
                # First ever successful state
                logger.info(f"🔄 ENVIRONMENT_STATE_INITIALIZED: {new_state_str} | reason=\"{reason}\"")
                
            self.last_environment_state = is_valid
            self.last_environment_reason = reason
        return changed

    def track_execution(self, is_authorized: bool, reason: str = "") -> bool:
        changed = False
        if self.last_execution_state != is_authorized or self.last_execution_reason != reason:
            changed = True
            self.last_execution_state = is_authorized
            self.last_execution_reason = reason
        return changed
