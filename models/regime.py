from enum import Enum
from dataclasses import dataclass
from typing import Dict, Any

class MarketRegime(Enum):
    TRENDING_UP = "TRENDING_UP"
    TRENDING_DOWN = "TRENDING_DOWN"
    RANGING = "RANGING"
    VOLATILE = "VOLATILE"
    SQUEEZE = "SQUEEZE"
    BREAKOUT = "BREAKOUT"
    LOW_VOL = "LOW_VOL"
    TREND_UP = "TREND_UP"     # Legacy compatibility
    TREND_DOWN = "TREND_DOWN" # Legacy compatibility
    RANGE = "RANGE"           # Legacy compatibility
    UNKNOWN = "UNKNOWN"

@dataclass
class RegimeState:
    regime: MarketRegime
    confidence: float
    volatility_state: str
    trend_strength: float
    tradability: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "regime": self.regime.value,
            "confidence": round(self.confidence, 2),
            "volatility_state": self.volatility_state,
            "trend_strength": round(self.trend_strength, 2),
            "tradability": round(self.tradability, 2)
        }
