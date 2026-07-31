from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, Optional
from models.lifecycle import TradeLifecycle

class TradeHealth(Enum):
    HEALTHY = "HEALTHY"
    CAUTION = "CAUTION"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"

class ExitDecisionType(Enum):
    CONTINUE = "CONTINUE"
    ADJUST_STOP = "ADJUST_STOP"
    PARTIAL_EXIT = "PARTIAL_EXIT"
    FULL_EXIT = "FULL_EXIT"
    EMERGENCY_EXIT = "EMERGENCY_EXIT"

@dataclass
class ExitDecision:
    decision: ExitDecisionType
    reason: str
    new_stop_loss: Optional[float] = None
    exit_qty: Optional[int] = None
    urgency_level: str = "NORMAL" # NORMAL, HIGH, EMERGENCY

@dataclass
class PositionAction:
    position_id: str
    action_type: str # "UPDATE_SL", "PARTIAL_EXIT", "FULL_EXIT", "NONE"
    target_price: float = 0.0
    qty: int = 0
    reason: str = ""

@dataclass
class PositionState(TradeLifecycle):
    """The canonical object representing a live trade."""
    position_id: str = ""
    entry_time: Optional[datetime] = None
    signal_type: str = ""
    direction: str = ""
    entry_price: float = 0.0
    
    symbol: str = "NIFTY"
    security_id: str = ""
    intent_id: str = ""
    
    # Execution Metrics
    entry_bid: float = 0.0
    entry_ask: float = 0.0
    quote_age_ms: float = 0.0
    spread_pct_entry: float = 0.0
    slippage_entry: float = 0.0

    # Prices
    current_price: float = 0.0
    stop_loss: float = 0.0
    original_stop_loss: float = 0.0
    target_1: float = 0.0
    target_2: float = 0.0
    trailing_stop: float = 0.0

    # Size
    lots: int = 1
    qty: int = 50
    entry_premium: float = 0.0

    # Status
    is_active: bool = True
    partial_booked: bool = False
    sl_moved_to_cost: bool = False

    # P&L
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    max_favorable: float = 0.0
    max_adverse: float = 0.0

    # Context
    confidence_at_entry: float = 0.0
    regime_at_entry: str = ""
    weighted_score: float = 0.0
    calibrated_confidence: float = 0.0
    buy_score: float = 0.0
    sell_score: float = 0.0
    agent_breakdown: Dict = field(default_factory=dict)
    
    # Market Context
    volatility_at_entry: float = 0.0
    entry_type: str = "AI"
    
    # API Throttling
    last_sl_price: float = 0.0
    last_sl_update_time: float = 0.0

    # Hybrid TSL State
    tsl_active: bool = False
    tsl_breakeven_hit: bool = False
    tsl_current_trail_pct: float = 0.0
    tsl_highest_premium: float = 0.0
    tsl_highest_premium_time: datetime = field(default_factory=datetime.now)
    tsl_phase: str = "INITIAL"
    tsl_grade: str = "B"
    tsl_regime: str = "UNKNOWN"
    
    # Trade Health
    health_score: float = 100.0
    health_state: TradeHealth = TradeHealth.HEALTHY
    iv_at_entry: float = 0.0
    underlying_price_at_entry: float = 0.0
    consecutive_iv_drops: int = 0
    consecutive_critical_cycles: int = 0

    def to_dict(self):
        return {
            "position_id": self.position_id,
            "entry_time": self.entry_time.isoformat(),
            "signal_type": self.signal_type,
            "direction": self.direction,
            "entry_price": self.entry_price,
            "symbol": self.symbol,
            "current_price": self.current_price,
            "unrealized_pnl": self.unrealized_pnl,
            "health_state": self.health_state.value if isinstance(self.health_state, TradeHealth) else self.health_state,
            "qty": self.qty,
            "is_active": self.is_active,
            "tsl_phase": self.tsl_phase,
            "stop_loss": self.stop_loss
        }
