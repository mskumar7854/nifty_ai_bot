from dataclasses import dataclass
from typing import Optional

@dataclass
class ExecutionAttribution:
    """
    Mutable/Analytics representation of why an execution occurred.
    This model is produced by the Replay engine and is strictly decoupled from the immutable Execution ledger.
    """
    replay_version: int
    research_version: str  # e.g., 'Trend v4, Momentum v2'
    learning_version: str  # e.g., 'v8'

    trade_id: str
    decision_snapshot_id: str
    
    # Cryptographic linkage to the immutable reality
    executed_trade_fingerprint: str
    
    # Replay Reconstructed Intelligence
    trend_score: float
    momentum_score: float
    volatility_score: float
    structure_score: float
    confidence: float
    expected_value: float
    
    market_regime: str
    
    # Replay Analytics
    execution_latency: float
    replay_outcome: str  # e.g., 'MATCH', 'DRIFT'
    notes: Optional[str] = None
