from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict

from .signal import SignalType, Direction

@dataclass
class TradeOutcome:
    trade_id: str
    timestamp_entry: datetime
    timestamp_exit: Optional[datetime] = None
    signal_type: SignalType = SignalType.NO_TRADE
    direction: Direction = Direction.NEUTRAL
    entry_price: float = 0
    exit_price: float = 0
    stop_loss: float = 0
    target_1: float = 0
    option_entry_premium: float = 0
    option_exit_premium: float = 0
    pnl: float = 0
    pnl_pct: float = 0
    result: str = "OPEN"
    confidence_at_entry: float = 0
    confluence_at_entry: float = 0
    agent_agreement_at_entry: float = 0
    regime_at_entry: str = ""
    session_phase_at_entry: str = ""
    rsi_at_entry: float = 0
    vwap_position_at_entry: str = ""
    atr_at_entry: float = 0
    vix_at_entry: float = 0
    dte_at_entry: int = 0
    is_expiry_day_trade: bool = False
    pcr_at_entry: float = 0
    agent_votes_at_entry: Dict = field(default_factory=dict)
    hold_duration_minutes: float = 0
    entry_hour: int = 0
    entry_minute: int = 0
    day_of_week: int = 0
    market_condition: str = ""
    entry_quality: str = ""
    exit_reason: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.trade_id,
            "entry_time": self.timestamp_entry.isoformat() if self.timestamp_entry else "",
            "exit_time": self.timestamp_exit.isoformat() if self.timestamp_exit else "",
            "signal": self.signal_type.value,
            "direction": self.direction.value,
            "entry": self.entry_price,
            "exit": self.exit_price,
            "pnl": self.pnl,
            "result": self.result,
            "confidence": self.confidence_at_entry,
            "confluence": self.confluence_at_entry,
            "regime": self.regime_at_entry,
            "session": self.session_phase_at_entry,
            "hold_minutes": self.hold_duration_minutes,
            "dte": self.dte_at_entry,
            "is_expiry": self.is_expiry_day_trade,
            "agents": self.agent_votes_at_entry,
        }
