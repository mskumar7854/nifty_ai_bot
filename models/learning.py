from dataclasses import dataclass
from typing import Dict, Any, Optional

@dataclass
class LearningEvent:
    """
    Append-only representation of an adaptation or calibration made by the Learning Engine.
    Forms the third ledger in the immutable Phase 3 Architecture.
    """
    event_id: str  # UUIDv7 recommended for time-sorting
    timestamp: str # ISO Format
    
    # Traceability
    trade_id: str
    executed_trade_fingerprint: str
    
    # What was learned
    learning_version: str
    outcome_classification: str  # e.g., 'SUCCESS', 'REGIME_FAILURE', 'PREMATURE_EXIT'
    
    # The actual adaptation
    agent_reliability_updates: Dict[str, float]  # e.g., {'TrendAgent': -0.05, 'VolatilityAgent': +0.02}
    calibration_notes: Optional[str] = None
