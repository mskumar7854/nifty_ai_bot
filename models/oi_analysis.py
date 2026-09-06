from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List

@dataclass
class StrikeZone:
    low: float                    # e.g., 24850
    high: float                   # e.g., 24900  
    strength: float               # 0-100
    total_oi: float               # aggregate OI in zone
    peak_strike: float            # strike with highest OI in zone
    num_strikes: int              # how many strikes in the zone

@dataclass
class OIAnalysis:
    # ── Direction + Reliability (SEPARATED) ──
    pressure_score: float         # -100 (bearish) to +100 (bullish) — DIRECTION
    reliability_score: float      # 0-100 — data quality + signal consistency
    conviction: float             # 0-100 — multi-factor alignment

    # ── Zones ──
    support_zone: Optional[StrikeZone]
    resistance_zone: Optional[StrikeZone]

    # ── Migration ──
    migration_direction: str      # "UP", "DOWN", "STABLE"
    migration_velocity: float     # 0.0-1.0

    # ── Tactical Signals ──
    flip_detected: bool
    flip_side: str                # "CALL_UNWIND", "PUT_UNWIND", "NONE"
    wall_absorption: bool
    wall_break: bool
    wall_break_direction: str     # "BULLISH", "BEARISH", "NONE"
    trap_detected: bool           # OI trap signal
    trap_type: str                # "CALL_TRAP", "PUT_TRAP", "NONE"

    # ── Pressure Gradient ──
    pressure_above: float
    pressure_below: float
    pressure_ratio: float

    # ── PCR ──
    near_atm_pcr: float
    pcr_trend: str                # "RISING", "FALLING", "STABLE"

    # ── Structural vs Tactical ──
    structural_score: float       # 0-100
    tactical_score: float         # 0-100

    # ── Expiry Phase ──
    expiry_phase: str             # "EARLY", "MID", "EXPIRY_DAY", "EXPIRY_AFTERNOON"
    expiry_confidence_multiplier: float  # 0.4-1.0

    # ── Freshness ──
    data_age_seconds: float
    freshness_multiplier: float   # 0.4-1.0

    # ── Market Context ──
    market_state: str             # "BULLISH", "BEARISH", "NEUTRAL", "CHOPPY"
    data_quality: str             # "LIVE", "STALE", "SIMULATED"
    timestamp: datetime

    # ── Explainability ──
    explanation: List[str]        # ["✓ Put zone strengthened", "✓ Resistance shifted up", ...]
    feature_attribution: dict     # {"Zone Score": +18, "Migration": +22, "PCR": -11, "Trap": +18}

@dataclass
class MarketStructureAnalysis:
    """Future-proof wrapper. Only OI is populated now.
    IV, Greeks, dealer positioning can be added later."""
    oi: Optional[OIAnalysis] = None
    # Future slots:
    # iv: Optional[IVAnalysis] = None
    # greeks: Optional[GreeksAnalysis] = None
    # dealer: Optional[DealerAnalysis] = None
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        result = {"timestamp": self.timestamp.isoformat()}
        if self.oi:
            oi_dict = {
                "pressure_score": self.oi.pressure_score,
                "reliability_score": self.oi.reliability_score,
                "conviction": self.oi.conviction,
                "migration_direction": self.oi.migration_direction,
                "migration_velocity": self.oi.migration_velocity,
                "flip_detected": self.oi.flip_detected,
                "flip_side": self.oi.flip_side,
                "wall_absorption": self.oi.wall_absorption,
                "wall_break": self.oi.wall_break,
                "wall_break_direction": self.oi.wall_break_direction,
                "trap_detected": self.oi.trap_detected,
                "trap_type": self.oi.trap_type,
                "pressure_ratio": self.oi.pressure_ratio,
                "near_atm_pcr": self.oi.near_atm_pcr,
                "pcr_trend": self.oi.pcr_trend,
                "structural_score": self.oi.structural_score,
                "tactical_score": self.oi.tactical_score,
                "expiry_phase": self.oi.expiry_phase,
                "data_age_seconds": self.oi.data_age_seconds,
                "market_state": self.oi.market_state,
                "data_quality": self.oi.data_quality,
                "explanation": self.oi.explanation,
                "feature_attribution": self.oi.feature_attribution,
            }
            if self.oi.support_zone:
                oi_dict["support_zone"] = {
                    "low": self.oi.support_zone.low,
                    "high": self.oi.support_zone.high,
                    "strength": self.oi.support_zone.strength,
                    "peak_strike": self.oi.support_zone.peak_strike,
                }
            if self.oi.resistance_zone:
                oi_dict["resistance_zone"] = {
                    "low": self.oi.resistance_zone.low,
                    "high": self.oi.resistance_zone.high,
                    "strength": self.oi.resistance_zone.strength,
                    "peak_strike": self.oi.resistance_zone.peak_strike,
                }
            result["oi"] = oi_dict
        return result
