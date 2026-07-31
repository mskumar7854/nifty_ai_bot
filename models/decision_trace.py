from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, List, Optional
from enum import Enum

class StageAction(Enum):
    PASSED = "PASSED"
    REJECTED = "REJECTED"
    WAITING = "WAITING"
    SKIPPED = "SKIPPED"
    ERROR = "ERROR"

class ReplayMode(Enum):
    HISTORICAL = "HISTORICAL"
    COUNTERFACTUAL = "COUNTERFACTUAL"
    LIVE = "LIVE"

class ReplayFidelity(Enum):
    EXACT = "EXACT"
    PARTIAL = "PARTIAL"
    COUNTERFACTUAL = "COUNTERFACTUAL"
    LIVE = "LIVE"

@dataclass(frozen=True)
class HistoricalContextOverride:
    mode: ReplayMode
    fidelity: ReplayFidelity
    confidence: float
    confidence_threshold: Optional[float] = None
    regime_penalty: Optional[float] = None
    gap_multiplier: Optional[float] = None

@dataclass
class TraceStage:
    stage_name: str
    entered_at: datetime
    exited_at: datetime
    duration_ms: float
    action: StageAction
    reason: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class DecisionTrace:
    cycle_id: str
    timestamp: datetime
    engine_version: str
    experiment_id: str
    benchmark_version: str
    git_commit: str
    replay_mode: ReplayMode = ReplayMode.LIVE
    replay_fidelity: ReplayFidelity = ReplayFidelity.LIVE
    replay_confidence: float = 1.0
    stages: List[TraceStage] = field(default_factory=list)
    final_pnl: Optional[float] = None
    _is_finalized: bool = False

    def add_stage(self, 
                  stage_name: str, 
                  entered_at: datetime, 
                  exited_at: datetime, 
                  action: StageAction, 
                  reason: Optional[str] = None, 
                  metadata: Dict[str, Any] = None):
        if self._is_finalized:
            raise RuntimeError("Cannot modify a finalized DecisionTrace.")
            
        duration_ms = (exited_at - entered_at).total_seconds() * 1000.0
        
        self.stages.append(TraceStage(
            stage_name=stage_name,
            entered_at=entered_at,
            exited_at=exited_at,
            duration_ms=duration_ms,
            action=action,
            reason=reason,
            metadata=metadata or {}
        ))

    def finalize(self):
        self._is_finalized = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cycle_id": self.cycle_id,
            "timestamp": self.timestamp.isoformat() if isinstance(self.timestamp, datetime) else self.timestamp,
            "engine_version": self.engine_version,
            "experiment_id": self.experiment_id,
            "benchmark_version": self.benchmark_version,
            "git_commit": self.git_commit,
            "replay_mode": self.replay_mode.value,
            "replay_fidelity": self.replay_fidelity.value,
            "replay_confidence": self.replay_confidence,
            "stages": [
                {
                    "stage_name": s.stage_name,
                    "entered_at": s.entered_at.isoformat() if isinstance(s.entered_at, datetime) else s.entered_at,
                    "exited_at": s.exited_at.isoformat() if isinstance(s.exited_at, datetime) else s.exited_at,
                    "duration_ms": s.duration_ms,
                    "action": s.action.value,
                    "reason": s.reason,
                    "metadata": s.metadata
                } for s in self.stages
            ],
            "final_pnl": self.final_pnl
        }
