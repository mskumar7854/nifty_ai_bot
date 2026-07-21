import uuid
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

@dataclass
class DomainEvent:
    """Base class for all domain events."""
    event_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    timestamp: float = field(default_factory=time.time)
    correlation_id: Optional[str] = None
    source: str = "Unknown"
    payload: Dict[str, Any] = field(default_factory=dict)

# ── Market Events ──
@dataclass
class MarketSnapshotCreated(DomainEvent):
    pass

@dataclass
class SessionChanged(DomainEvent):
    pass

@dataclass
class MarketDataUnavailable(DomainEvent):
    pass

@dataclass
class MarketDataRecovered(DomainEvent):
    pass

# ── Decision Events ──
@dataclass
class DecisionGenerated(DomainEvent):
    pass

@dataclass
class DecisionApproved(DomainEvent):
    pass

@dataclass
class DecisionRejected(DomainEvent):
    pass

@dataclass
class DecisionExpired(DomainEvent):
    pass

# ── Execution Events ──
@dataclass
class OrderSubmitted(DomainEvent):
    pass

@dataclass
class OrderAcknowledged(DomainEvent):
    pass

@dataclass
class OrderFilled(DomainEvent):
    pass

@dataclass
class OrderRejected(DomainEvent):
    pass

@dataclass
class ExecutionFailed(DomainEvent):
    pass

@dataclass
class ExecutionRetried(DomainEvent):
    pass

# ── Position Events ──
@dataclass
class PositionOpened(DomainEvent):
    pass

@dataclass
class TradeHealthChanged(DomainEvent):
    pass

@dataclass
class StopLossUpdated(DomainEvent):
    pass

@dataclass
class BreakevenEnabled(DomainEvent):
    pass

@dataclass
class PartialExitExecuted(DomainEvent):
    pass

@dataclass
class PositionClosed(DomainEvent):
    pass

# ── Risk Events ──
@dataclass
class CooldownStarted(DomainEvent):
    pass

@dataclass
class CooldownEnded(DomainEvent):
    pass

@dataclass
class DailyLossLimitReached(DomainEvent):
    pass

@dataclass
class WeeklyLossLimitReached(DomainEvent):
    pass

@dataclass
class DrawdownTriggered(DomainEvent):
    pass

@dataclass
class EndOfDayTriggered(DomainEvent):
    pass
