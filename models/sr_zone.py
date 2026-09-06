"""
============================================
📊 SUPPORT/RESISTANCE ZONE MODELS

Data structures for the Market Structure
S/R Engine. These represent zones, price
interactions with zones, and the composite
S/R state consumed by the decision engine.

Key design decisions:
  - Zones, NOT levels. Markets reverse in
    bands (±10-30pts), not at exact prices.
  - State machine per zone: ACTIVE → TESTED
    → REJECTION/BREAKOUT → RETEST → FLIPPED
  - Strength is a composite of price-action,
    OI, volume, touches, and freshness.
  - Bias values are NOT hardcoded. They are
    logged with forward returns for empirical
    validation before promotion.
============================================
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List


# ── Interaction Event Types ──
# These describe what price is doing relative to a zone.
INTERACTION_TYPES = {
    "APPROACH",          # Price moving toward zone, within proximity threshold
    "TEST",              # Price touching/entering zone bounds
    "REJECTION",         # Price tested zone and reversed away
    "BREAKOUT",          # Price decisively moved through zone
    "RETEST",            # After breakout, price returned to zone and held
    "FAILED_BREAKOUT",   # After breakout, price re-entered and closed on original side
}

# ── Zone States ──
ZONE_STATES = {
    "ACTIVE",    # Zone is live and relevant
    "TESTED",    # Price is currently at/in the zone
    "BROKEN",    # Price broke through (pending retest confirmation)
    "FLIPPED",   # Role reversal confirmed (resistance → support or vice versa)
    "EXPIRED",   # Zone aged out or is no longer relevant
}

# ── Zone Roles ──
ZONE_ROLES = {"SUPPORT", "RESISTANCE"}


@dataclass
class SRZone:
    """
    A Support/Resistance zone with full context.

    Unlike a bare level (e.g. support=24800), this captures:
    - Zone bounds (24780-24810)
    - Multi-source strength scores
    - Touch history
    - Temporal freshness
    - Current behavioral state
    - Role reversal tracking
    """
    zone_id: str                          # Unique ID for tracking across cycles
    price_low: float                      # Zone lower bound (e.g. 24780)
    price_high: float                     # Zone upper bound (e.g. 24810)
    mid: float = 0.0                      # Midpoint (computed)

    # ── Strength Components (0-100 each) ──
    price_action_score: float = 0.0       # Pivot density, swing significance
    oi_score: float = 0.0                 # OI concentration confirmation
    volume_score: float = 0.0             # Volume profile at this zone

    # ── Touch History ──
    touch_count: int = 0                  # How many times price tested this zone
    last_touch_price: float = 0.0         # Price at last touch

    # ── Temporal ──
    freshness: float = 1.0               # 0-1: decays as zone ages (1.0 = just formed)
    first_seen_ts: Optional[datetime] = None   # When zone was first discovered
    last_touch_ts: Optional[datetime] = None   # Last time price interacted

    # ── Derived ──
    strength: float = 0.0                 # 0-100: composite score
    breakout_risk: float = 0.0            # 0-1: estimated probability of breakout

    # ── Role & State ──
    role: str = "SUPPORT"                 # "SUPPORT" | "RESISTANCE"
    state: str = "ACTIVE"                 # See ZONE_STATES
    previous_role: Optional[str] = None   # For role reversal tracking

    def __post_init__(self):
        self.mid = (self.price_low + self.price_high) / 2.0

    def contains_price(self, price: float) -> bool:
        """Check if a price falls within this zone's bounds."""
        return self.price_low <= price <= self.price_high

    def distance_to(self, price: float) -> float:
        """Signed distance from price to nearest zone boundary.
        Positive = price is above zone, Negative = price is below."""
        if price > self.price_high:
            return price - self.price_high
        elif price < self.price_low:
            return price - self.price_low
        return 0.0  # Price is inside the zone

    def to_dict(self) -> dict:
        return {
            "zone_id": self.zone_id,
            "price_low": self.price_low,
            "price_high": self.price_high,
            "mid": round(self.mid, 1),
            "strength": round(self.strength, 1),
            "price_action_score": round(self.price_action_score, 1),
            "oi_score": round(self.oi_score, 1),
            "volume_score": round(self.volume_score, 1),
            "touch_count": self.touch_count,
            "freshness": round(self.freshness, 3),
            "breakout_risk": round(self.breakout_risk, 3),
            "role": self.role,
            "state": self.state,
            "previous_role": self.previous_role,
        }


@dataclass
class SRInteraction:
    """
    Tracks a single price-zone interaction event.

    The S/R Engine emits one of these every time price
    changes its relationship with a zone (approach, test,
    rejection, breakout, retest, failed breakout).

    Forward returns are populated AFTER the event for
    empirical validation of the event's predictive value.
    """
    zone_id: str
    event_type: str                       # See INTERACTION_TYPES
    timestamp: datetime
    price_at_event: float
    volume_at_event: float = 0.0
    candles_in_zone: int = 0              # How many candles spent near/in the zone
    oi_confirmed: bool = False            # Whether OI data confirms the event

    # ── Zone Context at time of event ──
    zone_role: str = ""                   # "SUPPORT" | "RESISTANCE"
    zone_strength: float = 0.0            # Zone strength at the time of the event
    zone_mid: float = 0.0                 # Zone midpoint

    # ── Forward Returns (populated later for shadow validation) ──
    forward_5m: Optional[float] = None    # Price change 5 min after event
    forward_10m: Optional[float] = None   # Price change 10 min after event
    forward_15m: Optional[float] = None   # Price change 15 min after event
    forward_30m: Optional[float] = None   # Price change 30 min after event

    def to_dict(self) -> dict:
        return {
            "zone_id": self.zone_id,
            "event_type": self.event_type,
            "timestamp": self.timestamp.isoformat() if self.timestamp else "",
            "price_at_event": round(self.price_at_event, 1),
            "volume_at_event": round(self.volume_at_event, 0),
            "candles_in_zone": self.candles_in_zone,
            "oi_confirmed": self.oi_confirmed,
            "zone_role": self.zone_role,
            "zone_strength": round(self.zone_strength, 1),
            "zone_mid": round(self.zone_mid, 1),
            "forward_5m": round(self.forward_5m, 2) if self.forward_5m is not None else None,
            "forward_10m": round(self.forward_10m, 2) if self.forward_10m is not None else None,
            "forward_15m": round(self.forward_15m, 2) if self.forward_15m is not None else None,
            "forward_30m": round(self.forward_30m, 2) if self.forward_30m is not None else None,
        }


@dataclass
class SRState:
    """
    Complete S/R state snapshot for a single cycle.

    This is what the decision engine consumes. It contains
    the current zone map, recent interactions, and a
    summary bias score.

    The bias score is SHADOW-ONLY initially. It does NOT
    influence trade decisions until promoted after
    empirical validation (Gate 3).
    """
    # ── Active Zones (sorted by proximity to current price) ──
    support_zones: List[SRZone] = field(default_factory=list)
    resistance_zones: List[SRZone] = field(default_factory=list)

    # ── Nearest Zones (convenience accessors) ──
    nearest_support: Optional[SRZone] = None
    nearest_resistance: Optional[SRZone] = None

    # ── Latest Interaction ──
    latest_event: Optional[SRInteraction] = None
    active_events: List[SRInteraction] = field(default_factory=list)

    # ── Summary Bias (SHADOW ONLY — not used for decisions yet) ──
    sr_bias: str = "NEUTRAL"              # "BULLISH" | "BEARISH" | "NEUTRAL"
    sr_bias_score: float = 0.0            # Raw bias score (for logging)
    trade_context: str = ""               # Human-readable summary

    # ── Metadata ──
    total_zones: int = 0
    engine_latency_ms: float = 0.0
    timestamp: Optional[datetime] = None

    def to_dict(self) -> dict:
        return {
            "sr_bias": self.sr_bias,
            "sr_bias_score": round(self.sr_bias_score, 2),
            "trade_context": self.trade_context,
            "total_zones": self.total_zones,
            "nearest_support": self.nearest_support.to_dict() if self.nearest_support else None,
            "nearest_resistance": self.nearest_resistance.to_dict() if self.nearest_resistance else None,
            "latest_event": self.latest_event.to_dict() if self.latest_event else None,
            "support_zones": [z.to_dict() for z in self.support_zones],
            "resistance_zones": [z.to_dict() for z in self.resistance_zones],
            "active_events": [e.to_dict() for e in self.active_events],
            "engine_latency_ms": round(self.engine_latency_ms, 1),
        }
