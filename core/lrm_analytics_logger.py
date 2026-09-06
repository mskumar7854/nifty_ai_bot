"""
============================================
📝 LRM ANALYTICS LOGGER — Shadow Mode CSV

Logs every LRM cycle to CSV for research.

Two output files:
  1. lrm_decisions.csv — ALL zone interactions
     (event + no-event) for proper denominator
  2. lrm_events.csv — Only rows with detected
     liquidity events, with full detail

The key research comparison:
  - Liquidity event vs no liquidity event
  - High-LZS zone vs low-LZS zone
  - Sweep + structure confirm vs sweep alone
  - V2 decision vs LRM decision agreement

Forward metrics (5m/10m/15m/30m + MAE/MFE)
are written on a second pass when resolved.
============================================
"""

import csv
import os
from datetime import datetime
from typing import Optional

from models.lrm_models import LRMCycleSnapshot, LiquidityEventType
from utils.logger import get_logger

logger = get_logger("lrm_analytics")

# ── CSV paths ──
LRM_DECISIONS_CSV = os.path.join("data", "lrm_decisions.csv")
LRM_EVENTS_CSV = os.path.join("data", "lrm_events.csv")

# ── Column definitions ──
DECISION_COLUMNS = [
    # Identity
    "Timestamp", "Cycle_ID", "LRM_Schema_Version", "Git_Commit", "Price", "ATR", "VWAP", "Regime",
    # Location
    "At_Zone", "Zone_Mid", "Zone_Low", "Zone_High", "Zone_Role",
    "Zone_Source_Count", "Zone_Measurement_Score", "Zone_Components_Available",
    "OI_Measurement", "PriceStructure_Measurement", "Volume_Measurement",
    "VWAP_Measurement", "SweepPotential_Measurement", "Imbalance_Measurement",
    "Zone_Distance_Points", "Zone_Distance_ATR",
    # Approach
    "Approach_Type", "Approach_Score",
    "Approach_Velocity", "Approach_Acceleration",
    "Approach_Volume_Trend", "Approach_Momentum",
    # Event
    "Event_Type", "Event_Score", "Event_Confidence",
    "Breach_Distance", "Breach_Distance_ATR",
    "Wick_Ratio", "Volume_Spike", "OI_Confirmed", "AMD_Aligned",
    "Confirming_Factor_Count",
    # Order Flow
    "Flow_Available", "Flow_Direction", "Flow_Score",
    "Flow_Delta", "Flow_Cumulative_Delta", "Flow_Imbalance_Ratio",
    "Large_Order_Imbalance",
    # Structure
    "Structure_Score", "Has_BOS", "Has_CHoCH",
    "Has_Liquidity_Sweep", "Has_VWAP_Reclaim",
    "Active_Direction", "Leg_ID", "Entries_In_Leg",
    "Structure_Agrees",
    # Composite
    "Components_Available", "LRM_Composite_Score",
    "LRM_Signal", "LRM_Signal_Reason",
    # V2 Comparison
    "V2_Decision", "V2_Kill_Reason",
    # Forward Metrics (filled later)
    "Forward_5m", "Forward_10m", "Forward_15m", "Forward_30m",
    "MAE_Points", "MFE_Points", "MAE_ATR", "MFE_ATR",
    "Forward_Direction", "Forward_Resolved",
    # Telemetry
    "Engine_Latency_ms",
]


class LRMAnalyticsLogger:
    """
    Shadow-mode CSV logger for LRM research data.

    Logs ALL zone interactions (not just events) to
    provide proper denominators for statistical comparison.
    """

    def __init__(self):
        os.makedirs("data", exist_ok=True)
        self._ensure_csv(LRM_DECISIONS_CSV, DECISION_COLUMNS)
        self._ensure_csv(LRM_EVENTS_CSV, DECISION_COLUMNS)

    def _ensure_csv(self, path: str, columns: list):
        """Create CSV with headers if it doesn't exist."""
        if not os.path.exists(path):
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(columns)

    def log_cycle(self, snap: LRMCycleSnapshot):
        """
        Log a complete LRM cycle snapshot.

        Writes to lrm_decisions.csv for ALL zone interactions.
        Additionally writes to lrm_events.csv when a liquidity
        event is detected.
        """
        try:
            row = self._snapshot_to_row(snap)

            # Always log to decisions (full denominator)
            if snap.at_zone:
                self._append_row(LRM_DECISIONS_CSV, row)

            # Log to events only when an event was detected
            if (snap.event and
                    snap.event.event_type not in (
                        LiquidityEventType.NONE, LiquidityEventType.ACCEPTANCE,
                    )):
                self._append_row(LRM_EVENTS_CSV, row)

        except Exception as e:
            logger.error(f"LRM log error: {e}", exc_info=True)

    def update_forward_metrics(self, snap: LRMCycleSnapshot):
        """
        Update forward metrics for a previously logged interaction.

        Called when forward returns are resolved (after 30m window).
        This appends a new row with the forward metrics filled in.

        Note: In a production system we'd update in-place, but for
        research CSV logging, appending resolved rows is simpler and
        the analysis script can deduplicate by cycle_id.
        """
        if snap.forward_metrics and snap.forward_metrics.resolved:
            try:
                row = self._snapshot_to_row(snap)
                self._append_row(LRM_DECISIONS_CSV, row)
            except Exception as e:
                logger.error(f"LRM forward update error: {e}", exc_info=True)

    def _snapshot_to_row(self, snap: LRMCycleSnapshot) -> list:
        """Convert LRMCycleSnapshot to a CSV row."""
        zone = snap.nearest_zone
        approach = snap.approach
        event = snap.event
        flow = snap.flow
        structure = snap.structure
        fwd = snap.forward_metrics

        return [
            # Identity
            snap.timestamp.isoformat() if snap.timestamp else "",
            snap.cycle_id,
            snap.lrm_schema_version,
            snap.git_commit,
            round(snap.price, 1),
            round(snap.atr, 2),
            round(snap.vwap, 1),
            snap.regime,
            # Location
            snap.at_zone,
            round(zone.mid, 1) if zone else "",
            round(zone.price_low, 1) if zone else "",
            round(zone.price_high, 1) if zone else "",
            zone.role if zone else "",
            zone.source_count if zone else 0,
            round(zone.zone_measurement_score, 2) if zone else 0,
            zone.components_available if zone else 0,
            round(zone.oi_measurement, 2) if zone else 0,
            round(zone.price_structure_measurement, 2) if zone else 0,
            round(zone.volume_measurement, 2) if zone else 0,
            round(zone.vwap_measurement, 2) if zone else 0,
            round(zone.sweep_potential_measurement, 2) if zone else 0,
            round(zone.imbalance_measurement, 2) if zone else 0,
            round(zone.distance_to_price, 1) if zone else "",
            round(zone.distance_atr, 3) if zone else "",
            # Approach
            approach.approach_type.value if approach else "",
            round(approach.approach_score, 2) if approach else 0,
            round(approach.velocity, 4) if approach else 0,
            round(approach.acceleration, 4) if approach else 0,
            round(approach.volume_trend, 4) if approach else 0,
            round(approach.momentum, 4) if approach else 0,
            # Event
            event.event_type.value if event else "NONE",
            round(event.event_score, 2) if event else 0,
            round(event.confidence, 3) if event else 0,
            round(event.breach_distance, 2) if event else 0,
            round(event.breach_distance_atr, 3) if event else 0,
            round(event.wick_ratio, 3) if event else 0,
            event.volume_spike if event else False,
            event.oi_confirmed if event else False,
            event.amd_aligned if event else False,
            event.confirming_factor_count if event else 0,
            # Order Flow
            flow.data_available if flow else False,
            flow.flow_direction.value if flow else "UNAVAILABLE",
            round(flow.flow_score, 2) if flow else 50,
            round(flow.delta, 1) if flow else 0,
            round(flow.cumulative_delta, 1) if flow else 0,
            round(flow.imbalance_ratio, 4) if flow else 0,
            flow.large_order_imbalance if flow else 0,
            # Structure
            round(structure.structure_score, 2) if structure else 50,
            structure.has_bos if structure else False,
            structure.has_choch if structure else False,
            structure.has_liquidity_sweep if structure else False,
            structure.has_vwap_reclaim if structure else False,
            structure.active_direction if structure else "",
            structure.leg_id if structure else 0,
            structure.entries_in_leg if structure else 0,
            structure.agrees_with_lrm if structure else False,
            # Composite
            snap.components_available,
            round(snap.lrm_composite_score, 2),
            snap.lrm_signal.value,
            snap.lrm_signal_reason,
            # V2 Comparison
            snap.v2_decision,
            snap.v2_kill_reason,
            # Forward Metrics
            round(fwd.forward_5m, 2) if fwd and fwd.forward_5m is not None else "",
            round(fwd.forward_10m, 2) if fwd and fwd.forward_10m is not None else "",
            round(fwd.forward_15m, 2) if fwd and fwd.forward_15m is not None else "",
            round(fwd.forward_30m, 2) if fwd and fwd.forward_30m is not None else "",
            round(fwd.mae_points, 2) if fwd else "",
            round(fwd.mfe_points, 2) if fwd else "",
            round(fwd.mae_atr, 3) if fwd else "",
            round(fwd.mfe_atr, 3) if fwd else "",
            fwd.direction if fwd else "",
            fwd.resolved if fwd else False,
            # Telemetry
            round(snap.engine_latency_ms, 2),
        ]

    @staticmethod
    def _append_row(path: str, row: list):
        """Append a single row to CSV."""
        with open(path, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(row)
