from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any
import time

from .regime import MarketRegime, RegimeState
from .execution import ExecutionPolicy
from .agent import ConfluenceResult

from .enums import Direction, SignalType, Strength, SignalGrade, SignalStatus

@dataclass
class Signal:
    id: str
    timestamp: datetime
    signal_type: SignalType
    direction: Direction
    confidence: float
    strength: Strength
    
    adaptive_threshold: Optional[float] = None
    status: str = "new"
    execution_status: str = "pending"
    created_at: float = field(default_factory=time.time)
    updated_at: Optional[float] = None
    queue_position: Optional[int] = None
    metadata: Dict = field(default_factory=dict)

    entry_price: float = 0
    stop_loss: float = 0
    target_1: float = 0
    target_2: float = 0
    target_3: float = 0
    position_size: int = 0

    weighted_score: float = 0
    buy_score: float = 0
    sell_score: float = 0
    uncertainty_multiplier: float = 1.0
    agent_breakdown: Dict = field(default_factory=dict)

    grade: SignalGrade = SignalGrade.D
    confluence: Optional[ConfluenceResult] = None
    regime: MarketRegime = MarketRegime.RANGING
    session_phase: str = "MORNING"  # Storing as string or enum
    risk_reward_ratio: float = 0
    expected_value: float = 0

    agent_votes: Dict = field(default_factory=dict)
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    primary_score: float = 0
    confirmation_score: float = 0
    filter_score: float = 0
    
    key_levels_nearby: List[float] = field(default_factory=list)
    suggested_adjustment: str = ""
    execution_policy: Optional[ExecutionPolicy] = None
    trace: Optional[Any] = None  # Store the DecisionTrace

    def to_dict(self) -> dict:
        # Determine internal normalized states for dashboard UI
        signal_state = "NO_SIGNAL" if self.signal_type == SignalType.NO_TRADE else "CANDIDATE"
        execution_state = self.execution_status.upper() if getattr(self, "execution_status", "") else "PENDING"
        if signal_state == "NO_SIGNAL":
            execution_state = "NOT_REQUESTED"
            
        return {
            "time": self.timestamp.strftime("%H:%M:%S"),
            "signal": self.signal_type.value,
            "direction": self.direction.value,
            "confidence": f"{self.confidence:.1f}%",
            "execution_status": self.execution_status,
            
            # Normalized UI Telemetry Contract
            "signal_state": signal_state,
            "execution_state": execution_state,
            "rejection_reason": self.metadata.get("rejection_reason", ""),
            "rejection_stage": self.metadata.get("rejection_stage", ""),
            
            "grade": self.grade.value,
            "strength": self.strength.value,
            "entry": self.entry_price,
            "sl": self.stop_loss,
            "target1": self.target_1,
            "target2": self.target_2,
            "target3": self.target_3,
            "qty": self.position_size,
            "rr_ratio": f"{self.risk_reward_ratio:.1f}",
            "regime": self.regime.value,
            "session": str(self.session_phase),
            "confluence": {
                "bullish": self.confluence.bullish_agents if self.confluence else 0,
                "bearish": self.confluence.bearish_agents if self.confluence else 0,
                "ratio": f"{self.confluence.confluence_ratio:.0%}" if self.confluence else "0%",
            },
            "reasons": self.reasons,
            "warnings": self.warnings,
            "symbol": getattr(self, "symbol", ""),
            "execution_policy": self.execution_policy.to_dict() if self.execution_policy else None,
        }
