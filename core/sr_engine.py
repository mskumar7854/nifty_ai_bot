"""
============================================
🏗️ SUPPORT/RESISTANCE ENGINE

Market Structure S/R computation engine.
This is a SHARED UTILITY (like ConfluenceScorer
or GapPenaltyManager) — not an agent.

Responsibilities:
  1. Zone Discovery: cluster pivot points into zones
  2. OI Overlay: merge OI StrikeZone with price zones
  3. State Machine: track zone interactions
  4. Bias Calculator: compute net S/R bias (shadow only)

Design decisions:
  - ATR-based zone clustering (0.3×ATR, floor 10pts)
  - Exponential freshness decay (half-life: 30 min)
  - State machine per zone
  - No hardcoded bias weights — all logged for validation
  - Session-scoped: zones reset at market open

⚠️ SHADOW MODE: This engine runs every cycle but
does NOT influence trade decisions. It logs data
for empirical validation via SRAnalyticsLogger.
============================================
"""

import math
import uuid
from collections import deque
from datetime import datetime, timedelta
from time import perf_counter
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from config.settings import Settings
from models.sr_zone import SRZone, SRInteraction, SRState
from models.oi_analysis import StrikeZone
from utils.indicators import calculate_support_resistance, find_swing_points
from utils.logger import get_logger


logger = get_logger("sr_engine")


# ── Configuration Constants ──
# These control zone discovery and interaction detection.
# They are intentionally NOT in settings.py yet — they stay
# here until shadow validation proves their values are stable.

ZONE_CLUSTER_ATR_MULT = 0.3      # Zone width = max(ATR × this, ZONE_MIN_WIDTH)
ZONE_MIN_WIDTH = 10.0            # Minimum zone width in points
ZONE_MAX_COUNT = 6               # Max zones per side (support/resistance)
FRESHNESS_HALF_LIFE_MIN = 30.0   # Half-life for freshness decay (minutes)
APPROACH_PROXIMITY_ATR = 0.5     # "Approaching zone" threshold
REJECTION_DISTANCE_ATR = 0.3     # Distance from zone to confirm rejection
REJECTION_CANDLES = 3             # Candles to confirm rejection
BREAKOUT_MARGIN_ATR = 0.2        # Distance beyond zone to confirm breakout
BREAKOUT_CANDLES = 2              # Consecutive candles beyond zone for breakout
FAILED_BREAKOUT_CANDLES = 5      # Window to detect failed breakout
ROLE_REVERSAL_MEMORY_MIN = 60    # Minutes to remember old role after flip
PIVOT_LOOKBACK = 50              # Candles for pivot detection
SWING_ORDER = 5                  # Swing point detection order


class SREngine:
    """
    Market Structure Support/Resistance Engine.

    Called every decision cycle. Maintains stateful zone tracking
    across cycles within a single trading session.

    Usage:
        engine = SREngine(settings)
        sr_state = engine.update(df, snapshot, oi_sup, oi_res)
    """

    def __init__(self, settings: Settings):
        self.settings = settings

        # ── Persistent State (session-scoped) ──
        self._zones: List[SRZone] = []
        self._interactions: deque = deque(maxlen=500)
        self._pending_forward: List[Dict] = []  # Events awaiting forward return fill
        self._last_update_ts: Optional[datetime] = None
        self._session_date: Optional[str] = None  # Reset zones on new session

        # ── Cycle tracking ──
        self._candles_at_zone: Dict[str, int] = {}  # zone_id → consecutive candles in zone
        self._breakout_tracking: Dict[str, Dict] = {}  # zone_id → breakout state

    def update(
        self,
        df: pd.DataFrame,
        snapshot,   # MarketSnapshot
        oi_support: Optional[StrikeZone] = None,
        oi_resistance: Optional[StrikeZone] = None,
    ) -> SRState:
        """
        Main entry point — called every decision engine cycle.

        Returns a complete SRState snapshot with zones, interactions,
        and bias score. The bias score is for SHADOW LOGGING ONLY.
        """
        t0 = perf_counter()

        if df is None or df.empty or len(df) < 10:
            return SRState(timestamp=datetime.now(), trade_context="Insufficient data")

        price = snapshot.price
        atr = snapshot.atr if snapshot.atr > 0 else 15.0  # Fallback ATR
        now = datetime.now()

        # ── Session Reset ──
        today = now.strftime("%Y-%m-%d")
        if self._session_date != today:
            self._reset_session(today)

        # ── 1. Resolve forward returns for pending events ──
        self._resolve_forward_returns(price, now)

        # ── 2. Discover / refresh zones ──
        discovered = self._discover_zones(df, atr)

        # ── 3. Merge with existing zones (don't lose state) ──
        self._merge_discovered_zones(discovered, now)

        # ── 4. Overlay OI confirmation ──
        self._overlay_oi(oi_support, oi_resistance)

        # ── 5. Update freshness decay ──
        self._decay_freshness(now)

        # ── 6. Detect interactions (state machine) ──
        new_events = self._detect_interactions(price, df, atr, now)
        for event in new_events:
            self._interactions.append(event)
            self._pending_forward.append({
                "event": event,
                "price_at_event": price,
                "ts": now,
            })

        # ── 7. Compute zone strength ──
        for zone in self._zones:
            zone.strength = self._compute_zone_strength(zone)
            zone.breakout_risk = self._compute_breakout_risk(zone)

        # ── 8. Classify zones by role relative to current price ──
        support_zones = []
        resistance_zones = []
        for zone in self._zones:
            if zone.state == "EXPIRED":
                continue
            if zone.mid < price:
                zone.role = "SUPPORT"
                support_zones.append(zone)
            elif zone.mid > price:
                zone.role = "RESISTANCE"
                resistance_zones.append(zone)
            # Zone containing price: role stays as-is (ambiguous)

        # Sort by proximity
        support_zones.sort(key=lambda z: abs(price - z.mid))
        resistance_zones.sort(key=lambda z: abs(price - z.mid))

        # Trim to max count
        support_zones = support_zones[:ZONE_MAX_COUNT]
        resistance_zones = resistance_zones[:ZONE_MAX_COUNT]

        # ── 9. Compute bias (SHADOW ONLY) ──
        sr_bias, sr_bias_score, trade_context = self._compute_sr_bias(
            price, support_zones, resistance_zones, new_events
        )

        # ── 10. Build state ──
        recent_events = [
            e for e in self._interactions
            if e.timestamp and (now - e.timestamp).total_seconds() < 900  # last 15 min
        ]

        latency_ms = (perf_counter() - t0) * 1000
        self._last_update_ts = now

        return SRState(
            support_zones=support_zones,
            resistance_zones=resistance_zones,
            nearest_support=support_zones[0] if support_zones else None,
            nearest_resistance=resistance_zones[0] if resistance_zones else None,
            latest_event=new_events[-1] if new_events else None,
            active_events=recent_events,
            sr_bias=sr_bias,
            sr_bias_score=sr_bias_score,
            trade_context=trade_context,
            total_zones=len(support_zones) + len(resistance_zones),
            engine_latency_ms=latency_ms,
            timestamp=now,
        )

    # ══════════════════════════════════════════════════════════════
    # ZONE DISCOVERY
    # ══════════════════════════════════════════════════════════════

    def _discover_zones(self, df: pd.DataFrame, atr: float) -> List[SRZone]:
        """
        Discover S/R zones from price action.

        Strategy:
          1. Find pivot highs/lows (existing indicator)
          2. Find swing points (existing indicator)
          3. Cluster nearby levels into zones using ATR-based tolerance
          4. Score each zone by pivot density
        """
        zones = []

        # ── Collect raw levels ──
        raw_levels: List[Tuple[float, str, float]] = []  # (price, source, volume)

        # Source 1: Pivot highs/lows
        sr = calculate_support_resistance(df, lookback=PIVOT_LOOKBACK, num_levels=10)
        for level in sr.get("resistance", []):
            raw_levels.append((level, "pivot_high", 0.0))
        for level in sr.get("support", []):
            raw_levels.append((level, "pivot_low", 0.0))

        # Source 2: Swing points
        swings = find_swing_points(df["close"], order=SWING_ORDER)
        for idx, val in swings.get("highs", []):
            vol = df["volume"].iloc[idx] if "volume" in df.columns and idx < len(df) else 0.0
            raw_levels.append((val, "swing_high", vol))
        for idx, val in swings.get("lows", []):
            vol = df["volume"].iloc[idx] if "volume" in df.columns and idx < len(df) else 0.0
            raw_levels.append((val, "swing_low", vol))

        if not raw_levels:
            return []

        # ── Cluster into zones ──
        zone_width = max(atr * ZONE_CLUSTER_ATR_MULT, ZONE_MIN_WIDTH)
        raw_levels.sort(key=lambda x: x[0])

        clusters: List[List[Tuple[float, str, float]]] = []
        current_cluster: List[Tuple[float, str, float]] = [raw_levels[0]]

        for level, source, vol in raw_levels[1:]:
            if level - current_cluster[-1][0] <= zone_width:
                current_cluster.append((level, source, vol))
            else:
                clusters.append(current_cluster)
                current_cluster = [(level, source, vol)]
        clusters.append(current_cluster)

        # ── Build SRZone from each cluster ──
        for cluster in clusters:
            prices = [c[0] for c in cluster]
            volumes = [c[2] for c in cluster]
            sources = [c[1] for c in cluster]

            zone_low = min(prices)
            zone_high = max(prices)

            # Widen thin zones to minimum width
            if zone_high - zone_low < ZONE_MIN_WIDTH:
                mid = (zone_low + zone_high) / 2
                zone_low = mid - ZONE_MIN_WIDTH / 2
                zone_high = mid + ZONE_MIN_WIDTH / 2

            # Price-action score: more pivots in the cluster = stronger
            pa_score = min(len(cluster) * 25.0, 100.0)

            # Volume score: average volume at pivots (normalized later)
            valid_vols = [v for v in volumes if v > 0]
            vol_score = 0.0
            if valid_vols:
                # Simple relative score — will be refined with volume profile
                vol_score = min(len(valid_vols) * 20.0, 80.0)

            zone = SRZone(
                zone_id=str(uuid.uuid4())[:8],
                price_low=round(zone_low, 1),
                price_high=round(zone_high, 1),
                price_action_score=pa_score,
                volume_score=vol_score,
                touch_count=len(cluster),
                first_seen_ts=datetime.now(),
                last_touch_ts=datetime.now(),
                freshness=1.0,
                role="SUPPORT",  # Will be set relative to price in update()
                state="ACTIVE",
            )
            zones.append(zone)

        return zones

    def _merge_discovered_zones(self, discovered: List[SRZone], now: datetime):
        """
        Merge newly discovered zones with existing stateful zones.

        Rules:
          - If a new zone overlaps an existing one, update the existing zone's
            scores (bump touch count, refresh timestamp) but keep its state.
          - If a new zone doesn't overlap anything, add it.
          - Existing zones that no longer appear in discovery keep decaying.
        """
        merged_ids = set()

        for new_zone in discovered:
            matched = False
            for existing in self._zones:
                if existing.state == "EXPIRED":
                    continue
                # Check overlap
                if (new_zone.price_low <= existing.price_high and
                        new_zone.price_high >= existing.price_low):
                    # Merge: update scores, keep state
                    existing.price_action_score = max(
                        existing.price_action_score,
                        new_zone.price_action_score
                    )
                    existing.volume_score = max(
                        existing.volume_score,
                        new_zone.volume_score
                    )
                    # Widen zone if discovery found a wider cluster
                    existing.price_low = min(existing.price_low, new_zone.price_low)
                    existing.price_high = max(existing.price_high, new_zone.price_high)
                    existing.mid = (existing.price_low + existing.price_high) / 2
                    existing.last_touch_ts = now
                    merged_ids.add(existing.zone_id)
                    matched = True
                    break

            if not matched:
                self._zones.append(new_zone)
                merged_ids.add(new_zone.zone_id)

        # Expire zones that are too old and haven't been refreshed
        for zone in self._zones:
            if zone.zone_id not in merged_ids and zone.freshness < 0.1:
                zone.state = "EXPIRED"

    # ══════════════════════════════════════════════════════════════
    # OI OVERLAY
    # ══════════════════════════════════════════════════════════════

    def _overlay_oi(
        self,
        oi_support: Optional[StrikeZone],
        oi_resistance: Optional[StrikeZone],
    ):
        """
        Overlay OI zone data onto price-action zones.

        If an OI StrikeZone overlaps with a price-action zone,
        boost that zone's oi_score. If no overlap, create a
        new zone from the OI data alone (lower base strength).
        """
        oi_zones = []
        if oi_support:
            oi_zones.append(("SUPPORT", oi_support))
        if oi_resistance:
            oi_zones.append(("RESISTANCE", oi_resistance))

        for role, oi_zone in oi_zones:
            oi_low = oi_zone.low
            oi_high = oi_zone.high
            oi_strength = oi_zone.strength

            matched = False
            for zone in self._zones:
                if zone.state == "EXPIRED":
                    continue
                # Check overlap
                if oi_low <= zone.price_high and oi_high >= zone.price_low:
                    # Confluence! OI confirms this price-action zone.
                    zone.oi_score = min(oi_strength, 100.0)
                    matched = True
                    break

            if not matched:
                # OI-only zone (no price-action confirmation — lower base score)
                zone = SRZone(
                    zone_id=f"oi_{str(uuid.uuid4())[:6]}",
                    price_low=oi_low,
                    price_high=oi_high,
                    oi_score=min(oi_strength, 100.0),
                    price_action_score=0.0,  # No PA confirmation
                    role=role,
                    state="ACTIVE",
                    first_seen_ts=datetime.now(),
                    last_touch_ts=datetime.now(),
                )
                self._zones.append(zone)

    # ══════════════════════════════════════════════════════════════
    # FRESHNESS DECAY
    # ══════════════════════════════════════════════════════════════

    def _decay_freshness(self, now: datetime):
        """
        Exponential decay on zone freshness.
        Half-life: FRESHNESS_HALF_LIFE_MIN minutes.
        """
        decay_rate = math.log(2) / (FRESHNESS_HALF_LIFE_MIN * 60.0)  # per second

        for zone in self._zones:
            if zone.state == "EXPIRED":
                continue
            if zone.last_touch_ts:
                age_sec = (now - zone.last_touch_ts).total_seconds()
                zone.freshness = max(0.01, math.exp(-decay_rate * age_sec))

    # ══════════════════════════════════════════════════════════════
    # INTERACTION STATE MACHINE
    # ══════════════════════════════════════════════════════════════

    def _detect_interactions(
        self,
        price: float,
        df: pd.DataFrame,
        atr: float,
        now: datetime,
    ) -> List[SRInteraction]:
        """
        Detect what price is doing relative to each active zone.

        State machine per zone:
          ACTIVE → TESTED → REJECTION (zone confirmed stronger)
                          → BREAKOUT → RETEST → FLIPPED (role reversal)
                                     → FAILED_BREAKOUT (trap)
        """
        events: List[SRInteraction] = []

        for zone in self._zones:
            if zone.state == "EXPIRED":
                continue

            dist = zone.distance_to(price)
            abs_dist = abs(dist)
            in_zone = zone.contains_price(price)
            vol = df["volume"].iloc[-1] if "volume" in df.columns else 0.0

            # ── Track consecutive candles in zone ──
            if in_zone:
                self._candles_at_zone[zone.zone_id] = (
                    self._candles_at_zone.get(zone.zone_id, 0) + 1
                )
            else:
                self._candles_at_zone[zone.zone_id] = 0

            candles_in = self._candles_at_zone.get(zone.zone_id, 0)

            # ── Check for BREAKOUT tracking state ──
            bt = self._breakout_tracking.get(zone.zone_id)

            if bt:
                # We're tracking a potential breakout
                bt["candles_since"] = bt.get("candles_since", 0) + 1

                if bt["direction"] == "UP":
                    # Breakout was upward (through resistance)
                    if price > zone.price_high + atr * BREAKOUT_MARGIN_ATR:
                        bt["confirm_candles"] = bt.get("confirm_candles", 0) + 1
                    else:
                        bt["confirm_candles"] = 0

                    if bt["confirm_candles"] >= BREAKOUT_CANDLES:
                        # CONFIRMED BREAKOUT
                        zone.state = "BROKEN"
                        zone.touch_count += 1
                        zone.last_touch_ts = now
                        zone.last_touch_price = price
                        events.append(SRInteraction(
                            zone_id=zone.zone_id,
                            event_type="BREAKOUT",
                            timestamp=now,
                            price_at_event=price,
                            volume_at_event=vol,
                            candles_in_zone=candles_in,
                            zone_role=zone.role,
                            zone_strength=zone.strength,
                            zone_mid=zone.mid,
                        ))
                        del self._breakout_tracking[zone.zone_id]
                        continue

                    # Check for FAILED BREAKOUT
                    if in_zone or price < zone.price_low:
                        zone.state = "ACTIVE"
                        zone.touch_count += 1
                        zone.last_touch_ts = now
                        zone.last_touch_price = price
                        # Strengthen zone — failed breakouts make zones stronger
                        zone.price_action_score = min(
                            zone.price_action_score + 15, 100
                        )
                        events.append(SRInteraction(
                            zone_id=zone.zone_id,
                            event_type="FAILED_BREAKOUT",
                            timestamp=now,
                            price_at_event=price,
                            volume_at_event=vol,
                            candles_in_zone=candles_in,
                            zone_role=zone.role,
                            zone_strength=zone.strength,
                            zone_mid=zone.mid,
                        ))
                        del self._breakout_tracking[zone.zone_id]
                        continue

                    if bt["candles_since"] > FAILED_BREAKOUT_CANDLES:
                        del self._breakout_tracking[zone.zone_id]

                elif bt["direction"] == "DOWN":
                    # Mirror logic for downward breakout
                    if price < zone.price_low - atr * BREAKOUT_MARGIN_ATR:
                        bt["confirm_candles"] = bt.get("confirm_candles", 0) + 1
                    else:
                        bt["confirm_candles"] = 0

                    if bt["confirm_candles"] >= BREAKOUT_CANDLES:
                        zone.state = "BROKEN"
                        zone.touch_count += 1
                        zone.last_touch_ts = now
                        zone.last_touch_price = price
                        events.append(SRInteraction(
                            zone_id=zone.zone_id,
                            event_type="BREAKOUT",
                            timestamp=now,
                            price_at_event=price,
                            volume_at_event=vol,
                            candles_in_zone=candles_in,
                            zone_role=zone.role,
                            zone_strength=zone.strength,
                            zone_mid=zone.mid,
                        ))
                        del self._breakout_tracking[zone.zone_id]
                        continue

                    if in_zone or price > zone.price_high:
                        zone.state = "ACTIVE"
                        zone.touch_count += 1
                        zone.last_touch_ts = now
                        zone.last_touch_price = price
                        zone.price_action_score = min(
                            zone.price_action_score + 15, 100
                        )
                        events.append(SRInteraction(
                            zone_id=zone.zone_id,
                            event_type="FAILED_BREAKOUT",
                            timestamp=now,
                            price_at_event=price,
                            volume_at_event=vol,
                            candles_in_zone=candles_in,
                            zone_role=zone.role,
                            zone_strength=zone.strength,
                            zone_mid=zone.mid,
                        ))
                        del self._breakout_tracking[zone.zone_id]
                        continue

                    if bt["candles_since"] > FAILED_BREAKOUT_CANDLES:
                        del self._breakout_tracking[zone.zone_id]

                continue  # Skip normal detection while tracking breakout

            # ── RETEST detection (zone was BROKEN, price returns) ──
            if zone.state == "BROKEN":
                if in_zone or abs_dist < atr * APPROACH_PROXIMITY_ATR:
                    # Price returned to the broken zone — potential retest
                    zone.touch_count += 1
                    zone.last_touch_ts = now
                    zone.last_touch_price = price

                    # Check if price is holding on the breakout side
                    # If zone was resistance (broken upward), price should stay above
                    if zone.role == "RESISTANCE" and price >= zone.mid:
                        zone.state = "FLIPPED"
                        zone.previous_role = zone.role
                        zone.role = "SUPPORT"
                        events.append(SRInteraction(
                            zone_id=zone.zone_id,
                            event_type="RETEST",
                            timestamp=now,
                            price_at_event=price,
                            volume_at_event=vol,
                            candles_in_zone=candles_in,
                            zone_role="FLIPPED_TO_SUPPORT",
                            zone_strength=zone.strength,
                            zone_mid=zone.mid,
                        ))
                    elif zone.role == "SUPPORT" and price <= zone.mid:
                        zone.state = "FLIPPED"
                        zone.previous_role = zone.role
                        zone.role = "RESISTANCE"
                        events.append(SRInteraction(
                            zone_id=zone.zone_id,
                            event_type="RETEST",
                            timestamp=now,
                            price_at_event=price,
                            volume_at_event=vol,
                            candles_in_zone=candles_in,
                            zone_role="FLIPPED_TO_RESISTANCE",
                            zone_strength=zone.strength,
                            zone_mid=zone.mid,
                        ))
                continue

            # ── Normal state machine (ACTIVE/TESTED zones) ──

            # APPROACH: price within proximity but not yet in zone
            if not in_zone and abs_dist < atr * APPROACH_PROXIMITY_ATR:
                events.append(SRInteraction(
                    zone_id=zone.zone_id,
                    event_type="APPROACH",
                    timestamp=now,
                    price_at_event=price,
                    volume_at_event=vol,
                    zone_role=zone.role,
                    zone_strength=zone.strength,
                    zone_mid=zone.mid,
                ))

            # TEST: price enters the zone
            elif in_zone:
                zone.state = "TESTED"
                zone.touch_count += 1
                zone.last_touch_ts = now
                zone.last_touch_price = price
                events.append(SRInteraction(
                    zone_id=zone.zone_id,
                    event_type="TEST",
                    timestamp=now,
                    price_at_event=price,
                    volume_at_event=vol,
                    candles_in_zone=candles_in,
                    zone_role=zone.role,
                    zone_strength=zone.strength,
                    zone_mid=zone.mid,
                ))

            # REJECTION: was TESTED, now moved away
            elif zone.state == "TESTED" and abs_dist > atr * REJECTION_DISTANCE_ATR:
                # Check direction of rejection
                if zone.role == "RESISTANCE" and price < zone.price_low:
                    zone.state = "ACTIVE"
                    zone.price_action_score = min(
                        zone.price_action_score + 10, 100
                    )
                    events.append(SRInteraction(
                        zone_id=zone.zone_id,
                        event_type="REJECTION",
                        timestamp=now,
                        price_at_event=price,
                        volume_at_event=vol,
                        candles_in_zone=candles_in,
                        zone_role=zone.role,
                        zone_strength=zone.strength,
                        zone_mid=zone.mid,
                    ))
                elif zone.role == "SUPPORT" and price > zone.price_high:
                    zone.state = "ACTIVE"
                    zone.price_action_score = min(
                        zone.price_action_score + 10, 100
                    )
                    events.append(SRInteraction(
                        zone_id=zone.zone_id,
                        event_type="REJECTION",
                        timestamp=now,
                        price_at_event=price,
                        volume_at_event=vol,
                        candles_in_zone=candles_in,
                        zone_role=zone.role,
                        zone_strength=zone.strength,
                        zone_mid=zone.mid,
                    ))
                else:
                    # Price moved through the zone — start breakout tracking
                    direction = "UP" if price > zone.price_high else "DOWN"
                    self._breakout_tracking[zone.zone_id] = {
                        "direction": direction,
                        "candles_since": 0,
                        "confirm_candles": 0,
                    }
                    zone.state = "TESTED"  # Keep as TESTED until confirmed

        return events

    # ══════════════════════════════════════════════════════════════
    # ZONE STRENGTH & BREAKOUT RISK
    # ══════════════════════════════════════════════════════════════

    def _compute_zone_strength(self, zone: SRZone) -> float:
        """
        Composite strength score (0-100).

        Formula:
          strength = (pa × 0.30 + oi × 0.25 + vol × 0.15 + touches × 0.15 + freshness × 0.15)

        Where touches is clamped and scaled, freshness is 0-100.
        """
        touch_score = min(zone.touch_count * 15, 100)
        freshness_score = zone.freshness * 100

        strength = (
            zone.price_action_score * 0.30
            + zone.oi_score * 0.25
            + zone.volume_score * 0.15
            + touch_score * 0.15
            + freshness_score * 0.15
        )
        return round(min(max(strength, 0), 100), 1)

    def _compute_breakout_risk(self, zone: SRZone) -> float:
        """
        Estimate probability that this zone will be broken.

        High breakout risk when:
          - Low touch count (untested)
          - Low OI confirmation
          - Low freshness (stale zone)
          - High touch count without rejection (weakening)

        Returns 0-1.
        """
        risk = 0.5  # Base risk

        # Fewer touches = more likely to break
        if zone.touch_count <= 1:
            risk += 0.15
        elif zone.touch_count >= 4:
            risk -= 0.15

        # No OI confirmation = higher risk
        if zone.oi_score < 20:
            risk += 0.10
        elif zone.oi_score > 70:
            risk -= 0.15

        # Stale zone = higher risk
        if zone.freshness < 0.3:
            risk += 0.10

        # Low PA score = higher risk
        if zone.price_action_score < 30:
            risk += 0.10
        elif zone.price_action_score > 70:
            risk -= 0.10

        return round(max(0.0, min(1.0, risk)), 3)

    # ══════════════════════════════════════════════════════════════
    # BIAS CALCULATION (SHADOW ONLY)
    # ══════════════════════════════════════════════════════════════

    def _compute_sr_bias(
        self,
        price: float,
        support_zones: List[SRZone],
        resistance_zones: List[SRZone],
        recent_events: List[SRInteraction],
    ) -> Tuple[str, float, str]:
        """
        Compute net S/R bias from zones + recent interactions.

        Returns (bias_direction, bias_score, trade_context).

        IMPORTANT: The bias_score is for SHADOW LOGGING ONLY.
        It is NOT used in trade decisions until empirically
        validated via forward return analysis.

        Positive score = bullish, Negative = bearish.
        """
        score = 0.0
        context_parts = []

        # ── Zone proximity bias ──
        if support_zones:
            ns = support_zones[0]
            dist_to_sup = price - ns.price_high
            if 0 < dist_to_sup < 30:  # Near support
                proximity_bonus = ns.strength * 0.1
                score += proximity_bonus
                context_parts.append(
                    f"Near support {ns.price_low:.0f}-{ns.price_high:.0f} "
                    f"(str={ns.strength:.0f})"
                )

        if resistance_zones:
            nr = resistance_zones[0]
            dist_to_res = nr.price_low - price
            if 0 < dist_to_res < 30:  # Near resistance
                proximity_penalty = nr.strength * 0.1
                score -= proximity_penalty
                context_parts.append(
                    f"Near resistance {nr.price_low:.0f}-{nr.price_high:.0f} "
                    f"(str={nr.strength:.0f})"
                )

        # ── Recent event bias ──
        for event in recent_events:
            # Log the raw event for forward return analysis
            # NO hardcoded weights — just directional hints for context string
            if event.event_type == "REJECTION":
                if event.zone_role == "RESISTANCE":
                    score -= event.zone_strength * 0.15
                    context_parts.append(f"Rejected at resistance {event.zone_mid:.0f}")
                elif event.zone_role == "SUPPORT":
                    score += event.zone_strength * 0.15
                    context_parts.append(f"Bounced from support {event.zone_mid:.0f}")

            elif event.event_type == "BREAKOUT":
                if event.zone_role == "RESISTANCE":
                    score += event.zone_strength * 0.20
                    context_parts.append(f"Broke above resistance {event.zone_mid:.0f}")
                elif event.zone_role == "SUPPORT":
                    score -= event.zone_strength * 0.20
                    context_parts.append(f"Broke below support {event.zone_mid:.0f}")

            elif event.event_type == "RETEST":
                if "SUPPORT" in (event.zone_role or ""):
                    score += event.zone_strength * 0.25
                    context_parts.append(f"Retest confirmed support {event.zone_mid:.0f}")
                elif "RESISTANCE" in (event.zone_role or ""):
                    score -= event.zone_strength * 0.25
                    context_parts.append(f"Retest confirmed resistance {event.zone_mid:.0f}")

            elif event.event_type == "FAILED_BREAKOUT":
                if event.zone_role == "RESISTANCE":
                    score -= event.zone_strength * 0.30
                    context_parts.append(f"FAILED breakout at resistance {event.zone_mid:.0f} (bull trap)")
                elif event.zone_role == "SUPPORT":
                    score += event.zone_strength * 0.30
                    context_parts.append(f"FAILED breakout at support {event.zone_mid:.0f} (bear trap)")

        # Clamp
        score = max(-100, min(100, score))

        if score > 5:
            bias = "BULLISH"
        elif score < -5:
            bias = "BEARISH"
        else:
            bias = "NEUTRAL"

        context = " | ".join(context_parts) if context_parts else "No significant S/R context"

        return bias, round(score, 2), context

    # ══════════════════════════════════════════════════════════════
    # FORWARD RETURN RESOLUTION
    # ══════════════════════════════════════════════════════════════

    def _resolve_forward_returns(self, current_price: float, now: datetime):
        """
        Fill in forward return fields for past events.

        This is the empirical validation mechanism — instead of
        assuming that "rejection = bearish", we measure what
        ACTUALLY happened after each event.
        """
        resolved = []
        for entry in self._pending_forward:
            event = entry["event"]
            event_price = entry["price_at_event"]
            event_ts = entry["ts"]
            elapsed_min = (now - event_ts).total_seconds() / 60.0

            if elapsed_min >= 5 and event.forward_5m is None:
                event.forward_5m = current_price - event_price

            if elapsed_min >= 10 and event.forward_10m is None:
                event.forward_10m = current_price - event_price

            if elapsed_min >= 15 and event.forward_15m is None:
                event.forward_15m = current_price - event_price

            if elapsed_min >= 30 and event.forward_30m is None:
                event.forward_30m = current_price - event_price
                resolved.append(entry)  # Fully resolved

        # Remove fully resolved entries
        for entry in resolved:
            if entry in self._pending_forward:
                self._pending_forward.remove(entry)

    # ══════════════════════════════════════════════════════════════
    # SESSION MANAGEMENT
    # ══════════════════════════════════════════════════════════════

    def _reset_session(self, today: str):
        """Reset zones and state for a new trading session."""
        logger.info(f"🔄 [SR ENGINE] New session detected ({today}). Resetting zones.")
        self._zones.clear()
        self._interactions.clear()
        self._pending_forward.clear()
        self._candles_at_zone.clear()
        self._breakout_tracking.clear()
        self._session_date = today
        self._last_update_ts = None
