from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field

# Base Contract Schema Version
class BaseReport(BaseModel):
    schema_version: str = "1.0"

class BotHealth(BaseReport):
    bot_name: str
    status: str  # HEALTHY, DEGRADED, FATAL
    latency_ms: float
    data_freshness_sec: float
    message: str = ""

class MarketReport(BaseReport):
    regime: str = "UNKNOWN"
    trend_strength: float = 0.0
    key_levels: Dict[str, float] = Field(default_factory=dict)
    structure_state: str = "UNKNOWN"
    confidence: float = 0.0
    plugin_data: Dict[str, Any] = Field(default_factory=dict)

class OptionsReport(BaseReport):
    directional_bias: str = "NEUTRAL"
    oi_pressure_score: float = 0.0
    gamma_risk_level: str = "LOW"
    recommended_contract: str = "NONE"
    confidence: float = 0.0
    plugin_data: Dict[str, Any] = Field(default_factory=dict)

class SentimentReport(BaseReport):
    bias: str = "NEUTRAL"
    confidence: float = 0.0
    plugin_data: Dict[str, Any] = Field(default_factory=dict)

class SignalReport(BaseReport):
    direction: str = "NONE"
    calibrated_pwin: float = 0.0
    signal_grade: str = "C"
    consensus_score: float = 0.0
    agent_reports: Dict[str, Any] = Field(default_factory=dict)

class PortfolioReport(BaseReport):
    ev_r: float = 0.0
    ev_score: float = 0.0
    risk_budget_approved: bool = False
    max_position_size: int = 0
    structure_reset: bool = False
    rejection_reason: str = ""

class DecisionReport(BaseReport):
    final_decision: str = "REJECTED"
    order_type: str = ""
    target_price: float = 0.0
    stop_price: float = 0.0
    position_size: int = 0
    why: List[str] = Field(default_factory=list)
    why_not: List[str] = Field(default_factory=list)
    gate_telemetry: List[Dict] = Field(default_factory=list)

class OMSReport(BaseReport):
    order_id: Optional[str] = None
    status: str = "PENDING"
    fill_price: float = 0.0
    slippage: float = 0.0
