import uuid
from dataclasses import dataclass, asdict, field
from typing import Dict, Any, Optional
from datetime import datetime
from utils.id_generator import TradeIdGenerator

@dataclass
class TradeRecord:
    """
    MASTER PERFORMANCE RECORD
    Connects Score -> Market Context -> Outcome
    """
    # Identification
    trade_id: str = field(default_factory=lambda: TradeIdGenerator.generate())
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    system_version: str = "v5.0"
    signal: str = "UNKNOWN"
    
    # Intelligence Layer
    weighted_score: float = 0.0
    buy_score: float = 0.0
    sell_score: float = 0.0
    gap: float = 0.0
    agent_breakdown: Dict[str, Any] = field(default_factory=dict)

    # Market Context (Edge Discovery)
    market_regime: str = "UNKNOWN"
    volatility: float = 0.0
    time_of_day: str = field(default_factory=lambda: datetime.now().strftime("%H:%M:%S"))
    entry_type: str = "AI"  # AI, TELEGRAM, MANUAL, CONFIRMED

    # System State (Refinement 4)
    account_balance: float = 0.0
    open_positions: int = 0

    # Execution Details
    entry_price: float = 0.0
    exit_price: float = 0.0
    quantity: int = 0

    # Outcome Details
    pnl: float = 0.0
    outcome: str = "UNKNOWN"  # WIN / LOSS / BREAKEVEN
    max_favorable: float = 0.0  # MFE
    max_adverse: float = 0.0    # MAE
    time_in_trade: float = 0.0  # minutes

    def to_dict(self):
        return asdict(self)

@dataclass
class RejectionRecord:
    """
    Logs why a trade was NOT taken (Refinement 5)
    """
    type: str = "REJECTED"
    trade_id: str = field(default_factory=lambda: TradeIdGenerator.generate())
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    system_version: str = "v5.0"
    signal_type: str = "UNKNOWN"
    score: float = 0.0
    reason: str = ""
    gate: str = "MasterDecisionEngine"
    market_regime: str = "UNKNOWN"

    def to_dict(self):
        return asdict(self)
