from dataclasses import dataclass
from typing import Optional, List
from datetime import datetime

@dataclass
class ExecutionResult:
    status: str # "queued", "simulated", "filled", "failed", "rejected", "blocked"
    broker_order_id: str
    filled_price: float
    fill_time: Optional[datetime]
    latency_ms: float
    slippage: float
    execution_quality: str # "EXCELLENT", "GOOD", "POOR", "FAILED"
    errors: List[str]
    position_id: str = "" # If successful, maps to PositionManager position_id

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "broker_order_id": self.broker_order_id,
            "filled_price": self.filled_price,
            "fill_time": self.fill_time.isoformat() if self.fill_time else None,
            "latency_ms": self.latency_ms,
            "slippage": self.slippage,
            "execution_quality": self.execution_quality,
            "errors": self.errors,
            "position_id": self.position_id
        }

@dataclass
class ExecutionPolicy:
    suppressed: bool = False
    reason: str = ""
    original_sl: float = 0
    adapted_sl: float = 0
    original_qty: int = 0
    adapted_qty: int = 0
    sl_multiplier: float = 1.0
    tp2_multiplier: float = 1.0
    position_scale: float = 1.0

    def to_dict(self) -> dict:
        return {
            "suppressed": self.suppressed,
            "reason": self.reason,
            "original_sl": self.original_sl,
            "adapted_sl": self.adapted_sl,
            "original_qty": self.original_qty,
            "adapted_qty": self.adapted_qty,
            "sl_multiplier": self.sl_multiplier,
            "tp2_multiplier": self.tp2_multiplier,
            "position_scale": self.position_scale,
        }

@dataclass(frozen=True)
class ExecutedTrade:
    """
    Immutable representation of an execution reality.
    This model contains strictly what happened, decoupled from why it happened.
    """
    schema_version: int
    execution_version: int

    trade_id: str
    decision_snapshot_id: str
    execution_context: str  # e.g., 'SIMULATION', 'DHAN_LIVE'

    timestamp: str  # ISO Format
    
    # Immutable Contract Metadata
    security_id: str
    trading_symbol: str
    expiry: str
    strike: float
    option_type: str
    
    quantity: int
    side: str  # 'BUY' | 'SELL'
    
    # Execution Facts
    entry_price: float
    exit_price: float
    fill_timestamp: str  # ISO Format
    broker_order_id: Optional[str]
    
    initial_sl: float
    final_sl: float
    target_price: float
    
    pnl: float
    realized_r: float

