from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any
import time

class TradeState(Enum):
    SIGNAL_CREATED = "SIGNAL_CREATED"
    SIGNAL_APPROVED = "SIGNAL_APPROVED"
    ORDER_PENDING = "ORDER_PENDING"
    ORDER_FILLED = "ORDER_FILLED"
    POSITION_OPEN = "POSITION_OPEN"
    POSITION_MANAGED = "POSITION_MANAGED"
    EXIT_TRIGGERED = "EXIT_TRIGGERED"
    POSITION_CLOSED = "POSITION_CLOSED"
    TRADE_EVALUATED = "TRADE_EVALUATED"
    TRADE_ARCHIVED = "TRADE_ARCHIVED"

VALID_TRANSITIONS = {
    TradeState.SIGNAL_CREATED: [TradeState.SIGNAL_APPROVED, TradeState.TRADE_ARCHIVED],
    TradeState.SIGNAL_APPROVED: [TradeState.ORDER_PENDING, TradeState.TRADE_ARCHIVED],
    TradeState.ORDER_PENDING: [TradeState.ORDER_FILLED, TradeState.TRADE_ARCHIVED],
    TradeState.ORDER_FILLED: [TradeState.POSITION_OPEN],
    TradeState.POSITION_OPEN: [TradeState.POSITION_MANAGED, TradeState.EXIT_TRIGGERED],
    TradeState.POSITION_MANAGED: [TradeState.POSITION_MANAGED, TradeState.EXIT_TRIGGERED],
    TradeState.EXIT_TRIGGERED: [TradeState.POSITION_CLOSED],
    TradeState.POSITION_CLOSED: [TradeState.TRADE_EVALUATED, TradeState.TRADE_ARCHIVED],
    TradeState.TRADE_EVALUATED: [TradeState.TRADE_ARCHIVED],
    TradeState.TRADE_ARCHIVED: []
}

@dataclass
class TradeLifecycle:
    trade_id: str = ""
    current_state: TradeState = TradeState.SIGNAL_CREATED
    
    created_at: Optional[datetime] = None
    opened_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    
    mfe: float = 0.0
    mfe_time: Optional[datetime] = None
    mae: float = 0.0
    mae_time: Optional[datetime] = None
    
    transition_history: List[Dict[str, Any]] = field(default_factory=list)

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now()
        # Initialize transition history with creation state
        if not self.transition_history:
            self.transition_history.append({
                "state": self.current_state.value,
                "timestamp": self.created_at.isoformat(),
                "payload": {}
            })

    def transition_to(self, new_state: TradeState, event_manager: Any, payload: dict = None):
        if payload is None:
            payload = {}
            
        # 1. Validate transition
        allowed = VALID_TRANSITIONS.get(self.current_state, [])
        if new_state not in allowed and new_state != self.current_state:
            raise ValueError(
                f"Invalid lifecycle transition for trade {self.trade_id}: "
                f"{self.current_state.value} -> {new_state.value}"
            )
            
        # 2. Update state and history
        if new_state != self.current_state:
            self.current_state = new_state
            now = datetime.now()
            
            if new_state == TradeState.POSITION_OPEN and not self.opened_at:
                self.opened_at = now
            elif new_state == TradeState.POSITION_CLOSED and not self.closed_at:
                self.closed_at = now
                
            self.transition_history.append({
                "state": new_state.value,
                "timestamp": now.isoformat(),
                "payload": payload
            })
            
            # 3. Publish domain event
            if event_manager:
                from models.events import TradeStateChanged
                event = TradeStateChanged(
                    correlation_id=self.trade_id,
                    source="trade_lifecycle",
                    payload={
                        "trade_id": self.trade_id,
                        "new_state": new_state.value,
                        "timestamp": now.isoformat(),
                        **payload
                    }
                )
                event_manager.publish(event)

    def update_mfe_mae(self, unrealized_pnl: float, event_manager: Any = None):
        now = datetime.now()
        updated = False
        
        if unrealized_pnl > self.mfe:
            self.mfe = unrealized_pnl
            self.mfe_time = now
            updated = True
            if event_manager:
                from models.events import MfeUpdated
                event_manager.publish(MfeUpdated(
                    correlation_id=self.trade_id,
                    source="trade_lifecycle",
                    payload={"trade_id": self.trade_id, "mfe": self.mfe, "timestamp": now.isoformat()}
                ))
                
        if unrealized_pnl < self.mae:
            self.mae = unrealized_pnl
            self.mae_time = now
            updated = True
            if event_manager:
                from models.events import MaeUpdated
                event_manager.publish(MaeUpdated(
                    correlation_id=self.trade_id,
                    source="trade_lifecycle",
                    payload={"trade_id": self.trade_id, "mae": self.mae, "timestamp": now.isoformat()}
                ))
                
        return updated
