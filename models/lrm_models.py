"""
============================================
📊 LIQUIDITY REACTION MODEL — DATA MODELS

Core data structures for the LRM research
shadow layer. These are observation-only
models — they never influence V2 decisions.

Design principles:
  - Every component is a MEASUREMENT, not a
    quality judgment. We don't know the weights
    yet — the data will tell us.
  - Additive scoring, not multiplicative.
    Missing data uses availability-adjusted
    score, never zero.
  - ALL zone interactions are logged, not just
    events. This provides a proper denominator
    for statistical comparison.
  - MAE/MFE are first-class citizens for
    determining tradable edge.
============================================
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict


# ── Enumerations ──

class ApproachType(str, Enum):
    """How price is approaching a liquidity zone."""
    IMPULSIVE = "IMPULSIVE"         # Fast, expanding volume, strong momentum
    GRINDING = "GRINDING"           # Slow, steady, moderate volume
    EXHAUSTION = "EXHAUSTION"       # Decelerating, declining volume
    INSUFFICIENT = "INSUFFICIENT"   # Not enough data to classify


class LiquidityEventType(str, Enum):
    """What happened when price reached the zone."""
    SWEEP = "SWEEP"                 # Breached zone, triggered stops, reversed
    REJECTION = "REJECTION"         # Tested zone, reversed without breaching
    ABSORPTION = "ABSORPTION"       # Sat at zone, volume absorbed, held
    ACCEPTANCE = "ACCEPTANCE"       # Broke through cleanly — zone invalidated
    NONE = "NONE"                   # No event detected (yet)


class FlowDirection(str, Enum):
    """Aggregated order flow direction."""
    BUYING = "BUYING"
    SELLING = "SELLING"
    BALANCED = "BALANCED"
    UNAVAILABLE = "UNAVAILABLE"     # Data not available from broker


class LRMSignal(str, Enum):
    """LRM shadow decision — observation only, never routed."""
    LONG_CANDIDATE = "LONG_CANDIDATE"
    SHORT_CANDIDATE = "SHORT_CANDIDATE"
    NO_TRADE = "NO_TRADE"


# ── Component Measurement Models ──

@dataclass
class ZoneSourceContribution:
    """
    One source's contribution to a liquidity zone.

    Each source is recorded independently so we can later
    test which combinations are predictive, without
    assuming weights upfront.
    """
    source: str                     # "OI", "SWING", "PIVOT", "VWAP", "PREV_DAY", "OPENING_RANGE"
    level: float                    # The price level this source identifies
    strength: float = 0.0           # Source-specific strength (0-100), raw measurement
    data_available: bool = True     # False if source data was unavailable this cycle


@dataclass
class LiquidityZone:
    """
    A fused liquidity zone from multiple independent sources.

    The zone_measurement_score is NOT a quality judgment.
    It is a count/density of how many independent sources
    cluster at this price region. Higher = more confluent.
    """
    zone_id: str
    price_low: float
    price_high: float
    mid: float = 0.0
    role: str = "SUPPORT"           # "SUPPORT" | "RESISTANCE"

    # ── Source breakdown (preserved individually) ──
    sources: List[ZoneSourceContribution] = field(default_factory=list)
    source_count: int = 0           # How many independent sources cluster here

    # ── Raw component measurements (0-100 each, equal initial weight) ──
    oi_measurement: float = 0.0     # OI concentration at this zone
    price_structure_measurement: float = 0.0  # Pivot density, swing significance
    volume_measurement: float = 0.0  # Volume profile at this zone
    vwap_measurement: float = 0.0   # Proximity to VWAP
    sweep_potential_measurement: float = 0.0  # Obvious high/low with likely stops
    imbalance_measurement: float = 0.0  # Order flow imbalance near zone

    # ── Composite measurement score (additive, equal weights) ──
    zone_measurement_score: float = 0.0  # Sum of available components / count
    components_available: int = 0   # How many components had data
    components_total: int = 6       # Total possible components

    # ── Context ──
    touch_count: int = 0
    freshness: float = 1.0          # 0-1 decay
    distance_to_price: float = 0.0  # Current distance in points
    distance_atr: float = 0.0       # Distance normalized by ATR

    def __post_init__(self):
        self.mid = (self.price_low + self.price_high) / 2.0

    def contains_price(self, price: float) -> bool:
        return self.price_low <= price <= self.price_high

    def to_dict(self) -> dict:
        return {
            "zone_id": self.zone_id,
            "price_low": round(self.price_low, 1),
            "price_high": round(self.price_high, 1),
            "mid": round(self.mid, 1),
            "role": self.role,
            "source_count": self.source_count,
            "oi_measurement": round(self.oi_measurement, 2),
            "price_structure_measurement": round(self.price_structure_measurement, 2),
            "volume_measurement": round(self.volume_measurement, 2),
            "vwap_measurement": round(self.vwap_measurement, 2),
            "sweep_potential_measurement": round(self.sweep_potential_measurement, 2),
            "imbalance_measurement": round(self.imbalance_measurement, 2),
            "zone_measurement_score": round(self.zone_measurement_score, 2),
            "components_available": self.components_available,
            "touch_count": self.touch_count,
            "freshness": round(self.freshness, 3),
            "distance_to_price": round(self.distance_to_price, 1),
            "distance_atr": round(self.distance_atr, 3),
        }


@dataclass
class ApproachProfile:
    """
    Characterizes HOW price is approaching a zone.

    Raw metrics are preserved separately from the
    classification so we can validate the classifier
    against outcomes.
    """
    # ── Raw metrics ──
    velocity: float = 0.0           # Points per candle toward zone, ATR-normalized
    acceleration: float = 0.0       # Change in velocity (positive = speeding up)
    volume_trend: float = 0.0       # Slope of volume on approach (-1 to +1)
    momentum: float = 0.0           # RSI slope on approach candles (-1 to +1)
    candles_measured: int = 0       # How many candles were used for measurement

    # ── Classification ──
    approach_type: ApproachType = ApproachType.INSUFFICIENT

    # ── Normalized component score (0-100) ──
    approach_score: float = 0.0     # Composite approach measurement

    def to_dict(self) -> dict:
        return {
            "velocity": round(self.velocity, 4),
            "acceleration": round(self.acceleration, 4),
            "volume_trend": round(self.volume_trend, 4),
            "momentum": round(self.momentum, 4),
            "candles_measured": self.candles_measured,
            "approach_type": self.approach_type.value,
            "approach_score": round(self.approach_score, 2),
        }


@dataclass
class LiquidityEvent:
    """
    What happened when price interacted with a liquidity zone.

    Deterministic detection with ATR-calibrated thresholds.
    Confidence is based on confirming factor count, not
    subjective judgment.
    """
    event_type: LiquidityEventType = LiquidityEventType.NONE
    confidence: float = 0.0         # 0-1, based on confirming factor count

    # ── Sweep-specific ──
    breach_distance: float = 0.0    # How far price breached beyond zone (points)
    breach_distance_atr: float = 0.0  # Breach distance normalized by ATR
    candles_beyond: int = 0         # How many candles spent beyond zone
    closed_back_inside: bool = False  # Did price close back inside?

    # ── Rejection-specific ──
    wick_ratio: float = 0.0         # Upper/lower wick ratio on rejection candle
    rejection_volume_ratio: float = 0.0  # Volume at rejection vs recent average

    # ── Confirming factors ──
    oi_confirmed: bool = False      # OI increase at zone strike
    volume_spike: bool = False      # Above-average volume on event candle
    amd_aligned: bool = False       # AMD Engine in MANIPULATION phase at same zone
    confirming_factor_count: int = 0

    # ── Normalized component score (0-100) ──
    event_score: float = 0.0        # Composite event measurement

    def to_dict(self) -> dict:
        return {
            "event_type": self.event_type.value,
            "confidence": round(self.confidence, 3),
            "breach_distance": round(self.breach_distance, 2),
            "breach_distance_atr": round(self.breach_distance_atr, 3),
            "candles_beyond": self.candles_beyond,
            "closed_back_inside": self.closed_back_inside,
            "wick_ratio": round(self.wick_ratio, 3),
            "rejection_volume_ratio": round(self.rejection_volume_ratio, 3),
            "oi_confirmed": self.oi_confirmed,
            "volume_spike": self.volume_spike,
            "amd_aligned": self.amd_aligned,
            "confirming_factor_count": self.confirming_factor_count,
            "event_score": round(self.event_score, 2),
        }


@dataclass
class OrderFlowState:
    """
    Order flow imbalance measurements.

    Graceful degradation: when broker data is unavailable,
    data_available=False and all metrics are neutral.
    The LRM uses availability-adjusted scoring — this
    component is excluded from the denominator, not
    treated as zero.
    """
    data_available: bool = False

    # ── Raw metrics ──
    delta: float = 0.0              # bid_volume - ask_volume
    cumulative_delta: float = 0.0   # Running session sum
    imbalance_ratio: float = 0.0    # abs(bid-ask)/(bid+ask), 0-1
    large_order_imbalance: int = 0  # large_buy - large_sell

    # ── Classification ──
    flow_direction: FlowDirection = FlowDirection.UNAVAILABLE

    # ── Normalized component score (0-100) ──
    flow_score: float = 50.0        # 50 = neutral (not zero)

    def to_dict(self) -> dict:
        return {
            "data_available": self.data_available,
            "delta": round(self.delta, 1),
            "cumulative_delta": round(self.cumulative_delta, 1),
            "imbalance_ratio": round(self.imbalance_ratio, 4),
            "large_order_imbalance": self.large_order_imbalance,
            "flow_direction": self.flow_direction.value,
            "flow_score": round(self.flow_score, 2),
        }


@dataclass
class StructuralState:
    """
    Structural leg state from the existing TrendStructureTracker.

    Read-only snapshot — we never modify the tracker.
    """
    has_bos: bool = False           # Break of structure detected
    has_choch: bool = False         # Change of character detected
    has_liquidity_sweep: bool = False
    has_vwap_reclaim: bool = False
    active_direction: str = ""      # "BULLISH", "BEARISH", or ""
    leg_id: int = 0
    entries_in_leg: int = 0

    # ── Alignment with LRM direction ──
    agrees_with_lrm: bool = False   # Does structure agree with the LRM signal?

    # ── Normalized component score (0-100) ──
    structure_score: float = 0.0

    def to_dict(self) -> dict:
        return {
            "has_bos": self.has_bos,
            "has_choch": self.has_choch,
            "has_liquidity_sweep": self.has_liquidity_sweep,
            "has_vwap_reclaim": self.has_vwap_reclaim,
            "active_direction": self.active_direction,
            "leg_id": self.leg_id,
            "entries_in_leg": self.entries_in_leg,
            "agrees_with_lrm": self.agrees_with_lrm,
            "structure_score": round(self.structure_score, 2),
        }


# ── Forward Return + MAE/MFE Tracking ──

@dataclass
class ForwardMetrics:
    """
    Forward return measurements for a zone interaction.

    Filled retrospectively as time passes. MAE/MFE are
    tracked continuously from the interaction timestamp.

    MAE = Maximum Adverse Excursion (worst drawdown from entry)
    MFE = Maximum Favorable Excursion (best runup from entry)
    """
    price_at_interaction: float = 0.0
    interaction_timestamp: Optional[datetime] = None

    # ── Forward returns (filled retrospectively) ──
    forward_5m: Optional[float] = None
    forward_10m: Optional[float] = None
    forward_15m: Optional[float] = None
    forward_30m: Optional[float] = None

    # ── MAE/MFE (updated every cycle until 30m window closes) ──
    mae_points: float = 0.0        # Maximum adverse excursion (points, always >= 0)
    mfe_points: float = 0.0        # Maximum favorable excursion (points, always >= 0)
    mae_atr: float = 0.0           # MAE normalized by ATR at interaction time
    mfe_atr: float = 0.0           # MFE normalized by ATR at interaction time

    # ── Context ──
    atr_at_interaction: float = 0.0  # ATR at the time of interaction
    direction: str = ""             # "LONG" or "SHORT" — determines MAE/MFE sign convention
    resolved: bool = False          # True once 30m window has closed

    def to_dict(self) -> dict:
        return {
            "price_at_interaction": round(self.price_at_interaction, 1),
            "forward_5m": round(self.forward_5m, 2) if self.forward_5m is not None else None,
            "forward_10m": round(self.forward_10m, 2) if self.forward_10m is not None else None,
            "forward_15m": round(self.forward_15m, 2) if self.forward_15m is not None else None,
            "forward_30m": round(self.forward_30m, 2) if self.forward_30m is not None else None,
            "mae_points": round(self.mae_points, 2),
            "mfe_points": round(self.mfe_points, 2),
            "mae_atr": round(self.mae_atr, 3),
            "mfe_atr": round(self.mfe_atr, 3),
            "direction": self.direction,
            "resolved": self.resolved,
        }


# ── Complete Cycle Snapshot ──

@dataclass
class LRMCycleSnapshot:
    """
    Complete per-cycle LRM observation.

    This is what gets logged to CSV. EVERY zone interaction
    is recorded — not just events. This provides the proper
    denominator for statistical comparison.

    The LRM decision is a shadow observation. It is NEVER
    routed to OMS or used by V2.
    """
    # ── Identity ──
    timestamp: datetime = field(default_factory=datetime.now)
    cycle_id: str = ""
    lrm_schema_version: str = "v1.0"
    git_commit: str = ""

    # ── Market context ──
    price: float = 0.0
    atr: float = 0.0
    vwap: float = 0.0
    regime: str = ""

    # ── Was price AT a zone? ──
    at_zone: bool = False           # True if price within proximity threshold
    nearest_zone: Optional[LiquidityZone] = None

    # ── Five layer measurements ──
    approach: Optional[ApproachProfile] = None
    event: Optional[LiquidityEvent] = None
    flow: Optional[OrderFlowState] = None
    structure: Optional[StructuralState] = None

    # ── Additive LRM score ──
    # Each component normalized to 0-100, then summed.
    # Score = (location + approach + event + flow + structure) / components_available
    # NOT multiplicative. Missing data excluded from denominator.
    location_score: float = 0.0     # Zone measurement score
    approach_score: float = 0.0     # Approach profile score
    event_score: float = 0.0        # Liquidity event score
    flow_score: float = 0.0         # Order flow score
    structure_score: float = 0.0    # Structural state score
    components_available: int = 0   # How many of the 5 had data
    lrm_composite_score: float = 0.0  # Availability-adjusted average

    # ── Shadow decision ──
    lrm_signal: LRMSignal = LRMSignal.NO_TRADE
    lrm_signal_reason: str = ""

    # ── V2 comparison (what the frozen system did) ──
    v2_decision: str = ""           # "EXECUTE", "REJECTED", "NO_SIGNAL"
    v2_kill_reason: str = ""

    # ── Forward metrics (filled retrospectively) ──
    forward_metrics: Optional[ForwardMetrics] = None

    # ── Engine telemetry ──
    engine_latency_ms: float = 0.0

    def to_dict(self) -> dict:
        result = {
            "timestamp": self.timestamp.isoformat() if self.timestamp else "",
            "cycle_id": self.cycle_id,
            "lrm_schema_version": self.lrm_schema_version,
            "git_commit": self.git_commit,
            "price": round(self.price, 1),
            "atr": round(self.atr, 2),
            "vwap": round(self.vwap, 1),
            "regime": self.regime,
            "at_zone": self.at_zone,
            "location_score": round(self.location_score, 2),
            "approach_score": round(self.approach_score, 2),
            "event_score": round(self.event_score, 2),
            "flow_score": round(self.flow_score, 2),
            "structure_score": round(self.structure_score, 2),
            "components_available": self.components_available,
            "lrm_composite_score": round(self.lrm_composite_score, 2),
            "lrm_signal": self.lrm_signal.value,
            "lrm_signal_reason": self.lrm_signal_reason,
            "v2_decision": self.v2_decision,
            "v2_kill_reason": self.v2_kill_reason,
            "engine_latency_ms": round(self.engine_latency_ms, 2),
        }
        if self.nearest_zone:
            result["nearest_zone"] = self.nearest_zone.to_dict()
        if self.approach:
            result["approach"] = self.approach.to_dict()
        if self.event:
            result["event"] = self.event.to_dict()
        if self.flow:
            result["flow"] = self.flow.to_dict()
        if self.structure:
            result["structure"] = self.structure.to_dict()
        if self.forward_metrics:
            result["forward_metrics"] = self.forward_metrics.to_dict()
        return result
