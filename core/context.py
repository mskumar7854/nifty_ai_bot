from dataclasses import dataclass
from typing import Any, Optional

@dataclass
class RuntimeContext:
    """Shared state container for all pipelines to avoid hidden global dependencies."""
    settings: Any
    mode: str = "SIMULATION"
    is_simulation: bool = True
    telegram_enabled: bool = False
    
    # Core Managers & Engines
    db_manager: Optional[Any] = None
    data_manager: Optional[Any] = None
    
    # Trackers
    burnin_tracker: Optional[Any] = None
    readiness_scorer: Optional[Any] = None
    simulation: Optional[Any] = None
    
    # Orchestrator hooks (temporary until full orchestrator extraction)
    system: Optional[Any] = None
    
    # Pipelines
    telemetry: Optional[Any] = None
    market_data: Optional[Any] = None
    decision: Optional[Any] = None
    execution: Optional[Any] = None
    position: Optional[Any] = None
