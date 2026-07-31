from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List

@dataclass(frozen=True)
class ExperimentResult:
    """
    Immutable record of an experiment result for a specific candidate.
    Provides a stable interface for analytics modules so they don't depend on replay internals.
    """
    candidate_id: str
    experiment: str
    timestamp: datetime

    decision: str
    execution_state: str

    exit_reason: Optional[str]

    pnl: float
    r_multiple: float

    rejection_reason: Optional[str]

    lifecycle: List[str] = field(default_factory=list)
