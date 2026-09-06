from dataclasses import dataclass
from enum import Enum
from typing import Optional
from datetime import datetime


class AMDPhase(str, Enum):
    IDLE = "IDLE"
    ACCUMULATION = "ACCUMULATION"
    MANIPULATION = "MANIPULATION"
    EXPANSION = "EXPANSION"
    EXPANSION_BREAKOUT = "EXPANSION_BREAKOUT"
    INVALIDATED = "INVALIDATED"


@dataclass
class AMDState:
    phase: AMDPhase = AMDPhase.IDLE
    
    # Observability
    amd_status: str = "OK"
    amd_error_type: Optional[str] = None
    
    # Metadata Context
    timeframe_minutes: int = 0
    
    # Facts: Range
    range_high: float = 0.0
    range_low: float = 0.0
    range_mid: float = 0.0
    range_start_timestamp: Optional[datetime] = None
    range_duration_candles: int = 0
    range_duration_minutes: float = 0.0
    
    # Facts: Sweep & Rejection
    sweep_side: Optional[str] = None          # "BSL" or "SSL"
    sweep_extreme_price: float = 0.0
    sweep_depth_pts: float = 0.0
    lower_wick_ratio: float = 0.0
    upper_wick_ratio: float = 0.0
    close_location: float = 0.0
    
    # Facts: Confirmation / State Status
    rejection_confirmed: bool = False
    acceptance_confirmed: bool = False
    msb_confirmed: bool = False               # Micro-structure break
    confirmation_candles: int = 0
    
    # Aggregated bias (BULLISH, BEARISH, or NEUTRAL)
    inferred_bias: str = "NEUTRAL"
    
    # Telemetry Identifiers
    timestamp: Optional[datetime] = None
    config_version: str = "AMD_V1_1"
    engine_version: str = "v1.0"

    def to_dict(self) -> dict:
        from dataclasses import asdict
        data = asdict(self)
        data["phase"] = self.phase.value
        return data
