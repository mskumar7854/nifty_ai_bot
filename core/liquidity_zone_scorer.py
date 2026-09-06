"""
============================================
📍 LIQUIDITY ZONE SCORER — LRM Layer 1

Fuses all location sources into LiquidityZone
objects with a zone_measurement_score.

The measurement score answers:
  "How many independent liquidity references
   cluster at this price region?"

It is NOT a quality judgment. We don't yet
know that OI deserves the same weight as a
previous swing high. The data will tell us.

Sources fused:
  1. SR Engine zones (pivot/swing-based)
  2. OI StrikeZones (option OI concentration)
  3. MarketSnapshot structural levels:
     - Previous day high/low
     - VWAP
     - Pivot points (R1/R2/R3/S1/S2/S3)
     - Opening range (day_open)
  4. OI change direction (from OIAnalysis)

Design decisions:
  - ATR-based zone clustering (reuses SR
    Engine's approach)
  - Equal initial component weights
  - Multi-session: prev-day levels persist
============================================
"""

import uuid
from typing import List, Optional

from models.lrm_models import (
    LiquidityZone, ZoneSourceContribution,
)
from models.sr_zone import SRState, SRZone
from models.oi_analysis import OIAnalysis, StrikeZone
from utils.logger import get_logger

logger = get_logger("liquidity_zone_scorer")

# ── Configuration ──
ZONE_CLUSTER_WIDTH_ATR = 0.4    # Cluster raw levels within this ATR multiple
ZONE_MIN_WIDTH = 10.0           # Minimum zone width in points
PROXIMITY_THRESHOLD_ATR = 1.5   # "At zone" if within this ATR distance
MAX_ZONES = 10                  # Max zones to track per side


class LiquidityZoneScorer:
    """
    Fuses multiple independent liquidity sources into
    ranked LiquidityZone objects.

    Called every cycle. Stateless — zones are rebuilt
    each cycle from the current SR state + snapshot.
    """

    def __init__(self):
        pass

    def score_zones(
        self,
        price: float,
        atr: float,
        sr_state: Optional[SRState],
        oi_analysis: Optional[OIAnalysis],
        snapshot,
    ) -> List[LiquidityZone]:
        """
        Build and score liquidity zones from all sources.

        Args:
            price: Current NIFTY price
            atr: Current ATR
            sr_state: Latest SRState from SREngine (may be None)
            oi_analysis: Latest OIAnalysis (may be None)
            snapshot: MarketSnapshot with structural levels

        Returns:
            List of LiquidityZone sorted by proximity to price.
        """
        if atr <= 0:
            atr = 15.0  # Fallback

        # ── 1. Collect raw levels from all sources ──
        raw_levels: List[ZoneSourceContribution] = []

        # Source: SR Engine zones
        if sr_state:
            for z in (sr_state.support_zones or []):
                raw_levels.append(ZoneSourceContribution(
                    source="SWING_SUPPORT",
                    level=z.mid,
                    strength=z.strength,
                ))
            for z in (sr_state.resistance_zones or []):
                raw_levels.append(ZoneSourceContribution(
                    source="SWING_RESISTANCE",
                    level=z.mid,
                    strength=z.strength,
                ))

        # Source: OI StrikeZones
        if oi_analysis:
            if oi_analysis.support_zone:
                sz = oi_analysis.support_zone
                raw_levels.append(ZoneSourceContribution(
                    source="OI_SUPPORT",
                    level=sz.peak_strike,
                    strength=sz.strength,
                ))
            if oi_analysis.resistance_zone:
                rz = oi_analysis.resistance_zone
                raw_levels.append(ZoneSourceContribution(
                    source="OI_RESISTANCE",
                    level=rz.peak_strike,
                    strength=rz.strength,
                ))

        # Source: MarketSnapshot structural levels
        if snapshot:
            pdh = getattr(snapshot, "prev_day_high", 0.0) or 0.0
            pdl = getattr(snapshot, "prev_day_low", 0.0) or 0.0
            vwap = getattr(snapshot, "vwap", 0.0) or 0.0
            day_open = getattr(snapshot, "day_open", 0.0) or 0.0
            pivot = getattr(snapshot, "pivot", 0.0) or 0.0

            if pdh > 0:
                raw_levels.append(ZoneSourceContribution(
                    source="PREV_DAY_HIGH", level=pdh, strength=70.0,
                ))
            if pdl > 0:
                raw_levels.append(ZoneSourceContribution(
                    source="PREV_DAY_LOW", level=pdl, strength=70.0,
                ))
            if vwap > 0:
                raw_levels.append(ZoneSourceContribution(
                    source="VWAP", level=vwap, strength=60.0,
                ))
            if day_open > 0:
                raw_levels.append(ZoneSourceContribution(
                    source="OPENING_RANGE", level=day_open, strength=50.0,
                ))
            if pivot > 0:
                raw_levels.append(ZoneSourceContribution(
                    source="PIVOT", level=pivot, strength=50.0,
                ))

            # Pivot R/S levels
            for attr, src in [
                ("r1", "R1"), ("r2", "R2"), ("r3", "R3"),
                ("s1", "S1"), ("s2", "S2"), ("s3", "S3"),
            ]:
                val = getattr(snapshot, attr, 0.0) or 0.0
                if val > 0:
                    raw_levels.append(ZoneSourceContribution(
                        source=src, level=val, strength=40.0,
                    ))

        if not raw_levels:
            return []

        # ── 2. Cluster into zones ──
        cluster_width = max(atr * ZONE_CLUSTER_WIDTH_ATR, ZONE_MIN_WIDTH)
        raw_levels.sort(key=lambda x: x.level)

        clusters: List[List[ZoneSourceContribution]] = []
        current_cluster: List[ZoneSourceContribution] = [raw_levels[0]]

        for contrib in raw_levels[1:]:
            if contrib.level - current_cluster[-1].level <= cluster_width:
                current_cluster.append(contrib)
            else:
                clusters.append(current_cluster)
                current_cluster = [contrib]
        clusters.append(current_cluster)

        # ── 3. Build LiquidityZone from each cluster ──
        zones: List[LiquidityZone] = []

        for cluster in clusters:
            levels = [c.level for c in cluster]
            zone_low = min(levels)
            zone_high = max(levels)

            # Ensure minimum width
            if zone_high - zone_low < ZONE_MIN_WIDTH:
                mid = (zone_low + zone_high) / 2
                zone_low = mid - ZONE_MIN_WIDTH / 2
                zone_high = mid + ZONE_MIN_WIDTH / 2

            zone = LiquidityZone(
                zone_id=str(uuid.uuid4())[:8],
                price_low=round(zone_low, 1),
                price_high=round(zone_high, 1),
                sources=list(cluster),
                source_count=len(cluster),
            )

            # ── Score each component ──
            components_available = 0

            # OI measurement: any OI source in this cluster?
            oi_sources = [c for c in cluster if "OI" in c.source]
            if oi_sources:
                zone.oi_measurement = max(c.strength for c in oi_sources)
                components_available += 1

            # Price structure measurement: swing/pivot sources
            pa_sources = [c for c in cluster if c.source in (
                "SWING_SUPPORT", "SWING_RESISTANCE", "PIVOT",
            )]
            if pa_sources:
                zone.price_structure_measurement = min(
                    len(pa_sources) * 25.0, 100.0
                )
                components_available += 1

            # Volume measurement: from SR zone volume scores if available
            if sr_state:
                matching_sr = self._find_overlapping_sr_zone(
                    zone_low, zone_high, sr_state
                )
                if matching_sr and matching_sr.volume_score > 0:
                    zone.volume_measurement = matching_sr.volume_score
                    components_available += 1

            # VWAP measurement: proximity to VWAP
            vwap_val = getattr(snapshot, "vwap", 0.0) or 0.0
            if vwap_val > 0:
                vwap_dist = abs(zone.mid - vwap_val)
                # Closer to VWAP = higher measurement
                vwap_score = max(0, 100 - (vwap_dist / atr) * 30)
                zone.vwap_measurement = vwap_score
                components_available += 1

            # Sweep potential measurement: obvious highs/lows
            sweep_sources = [c for c in cluster if c.source in (
                "PREV_DAY_HIGH", "PREV_DAY_LOW", "SWING_SUPPORT",
                "SWING_RESISTANCE",
            )]
            if sweep_sources:
                zone.sweep_potential_measurement = min(
                    len(sweep_sources) * 30.0, 100.0
                )
                components_available += 1

            # Imbalance measurement: OI pressure near zone
            if oi_analysis and oi_analysis.reliability_score > 30:
                zone.imbalance_measurement = abs(
                    oi_analysis.pressure_score
                )  # 0-100
                components_available += 1

            # ── Compute composite measurement score ──
            zone.components_available = components_available
            if components_available > 0:
                total = (
                    zone.oi_measurement
                    + zone.price_structure_measurement
                    + zone.volume_measurement
                    + zone.vwap_measurement
                    + zone.sweep_potential_measurement
                    + zone.imbalance_measurement
                )
                zone.zone_measurement_score = total / components_available
            else:
                zone.zone_measurement_score = 0.0

            # ── Set role relative to current price ──
            if zone.mid < price:
                zone.role = "SUPPORT"
            elif zone.mid > price:
                zone.role = "RESISTANCE"

            # ── Set distance ──
            zone.distance_to_price = abs(price - zone.mid)
            zone.distance_atr = zone.distance_to_price / atr if atr > 0 else 0.0

            # ── Set touch count from SR zone if available ──
            if sr_state:
                matching_sr = self._find_overlapping_sr_zone(
                    zone_low, zone_high, sr_state
                )
                if matching_sr:
                    zone.touch_count = matching_sr.touch_count
                    zone.freshness = matching_sr.freshness

            zones.append(zone)

        # ── 4. Sort by proximity and trim ──
        zones.sort(key=lambda z: z.distance_to_price)
        return zones[:MAX_ZONES * 2]

    def find_nearest_zone(
        self,
        price: float,
        atr: float,
        zones: List[LiquidityZone],
    ) -> Optional[LiquidityZone]:
        """
        Find the nearest zone within the proximity threshold.

        Returns None if no zone is within PROXIMITY_THRESHOLD_ATR.
        """
        threshold = atr * PROXIMITY_THRESHOLD_ATR
        for zone in zones:
            if zone.distance_to_price <= threshold:
                return zone
        return None

    def is_at_zone(
        self,
        price: float,
        atr: float,
        zones: List[LiquidityZone],
    ) -> bool:
        """Check if price is within proximity of any liquidity zone."""
        return self.find_nearest_zone(price, atr, zones) is not None

    @staticmethod
    def _find_overlapping_sr_zone(
        zone_low: float,
        zone_high: float,
        sr_state: SRState,
    ) -> Optional[SRZone]:
        """Find an SR zone that overlaps with the given bounds."""
        all_sr = (sr_state.support_zones or []) + (sr_state.resistance_zones or [])
        for sr in all_sr:
            if sr.price_low <= zone_high and sr.price_high >= zone_low:
                return sr
        return None
