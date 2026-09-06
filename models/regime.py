from enum import Enum
from dataclasses import dataclass
from typing import Dict, Any, Optional

class MarketRegime(Enum):
    STRONG_TREND_UP = "STRONG_TREND_UP"
    WEAK_TREND_UP = "WEAK_TREND_UP"
    STRONG_TREND_DOWN = "STRONG_TREND_DOWN"
    WEAK_TREND_DOWN = "WEAK_TREND_DOWN"
    RANGING = "RANGING"
    VOLATILE_CHOPPY = "VOLATILE_CHOPPY"
    SQUEEZE = "SQUEEZE"
    BREAKOUT = "BREAKOUT"
    UNKNOWN = "UNKNOWN"
    # Legacy compatibility aliases
    TRENDING_UP = "TRENDING_UP"
    TRENDING_DOWN = "TRENDING_DOWN"
    VOLATILE = "VOLATILE"
    LOW_VOL = "LOW_VOL"
    TREND_UP = "TREND_UP"
    TREND_DOWN = "TREND_DOWN"
    RANGE = "RANGE"

@dataclass
class RegimeContext:
    raw_regime: str
    normalized_regime: MarketRegime
    trend_strength: str  # "STRONG" | "WEAK" | "NEUTRAL"
    strike_policy: str   # "ATM" | "ITM_1_STEP" | "NO_TRADE"
    details: Dict[str, Any] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "raw_regime": self.raw_regime,
            "normalized_regime": self.normalized_regime.value if hasattr(self.normalized_regime, "value") else str(self.normalized_regime),
            "trend_strength": self.trend_strength,
            "strike_policy": self.strike_policy,
            "details": self.details or {}
        }

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


def normalize_regime_family(val: Any) -> Optional[str]:
    """
    Normalize regime representations (MarketRegime enum, string, or alias)
    into canonical regime families. Compatible aliases map to identical family names.
    Returns: 'TREND_DOWN' | 'TREND_UP' | 'RANGE' | 'VOLATILE' | 'BREAKOUT' | None
    """
    if val is None:
        return None
        
    val_str = val.value if hasattr(val, "value") else str(val)
    val_str = val_str.strip().upper()
    if not val_str or val_str in ("NONE", "UNKNOWN", "N/A"):
        return None
        
    if any(k in val_str for k in ("DOWN", "BEAR")):
        return "TREND_DOWN"
    if any(k in val_str for k in ("UP", "BULL")):
        return "TREND_UP"
    if val_str in ("RANGE", "RANGING", "SQUEEZE", "LOW_VOL"):
        return "RANGE"
    if "VOLATILE" in val_str:
        return "VOLATILE"
    if "BREAKOUT" in val_str:
        return "BREAKOUT"
        
    return None

