from dataclasses import dataclass
from typing import Any, Optional

@dataclass
class RuntimeContext:
    """
    Shared dependency container for all pipelines and the orchestrator.
    It intentionally does NOT hold mutable trading state (like current signal).
    """
    settings: Any
    mode: str = "SIMULATION"
    is_simulation: bool = True
    telegram_enabled: bool = False
    
    # Core Infrastructure
    event_manager: Optional[Any] = None
    db_manager: Optional[Any] = None
    data_manager: Optional[Any] = None
    broker_health: Optional[Any] = None
    oms: Optional[Any] = None
    
    # Trackers & Scorer
    burnin_tracker: Optional[Any] = None
    readiness_scorer: Optional[Any] = None
    simulation: Optional[Any] = None
    
    # Telemetry
    telemetry: Optional[Any] = None
