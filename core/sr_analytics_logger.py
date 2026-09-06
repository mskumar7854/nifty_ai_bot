"""
============================================
📊 S/R ANALYTICS LOGGER (Shadow Mode)

Logs every cycle's S/R state to a CSV file
for empirical validation. This follows the
same pattern as OIAnalyticsLogger.

Output: data/sr_analytics.csv

Key columns for validation:
  - Forward returns after each interaction
    (5m, 10m, 15m, 30m)
  - Zone strength at time of interaction
  - OI confirmation status
  - Engine decision (what the bot actually did)

This data is used in Gate 2 (Validation) to
determine whether S/R events have genuine
predictive value before promoting them to
active scoring in Gate 3.
============================================
"""

import csv
import os
from datetime import datetime
from typing import Optional

from models.sr_zone import SRState, SRInteraction
from utils.logger import get_logger


logger = get_logger("sr_analytics")

# CSV paths
SR_STATE_CSV = os.path.join("data", "sr_analytics.csv")
SR_EVENTS_CSV = os.path.join("data", "sr_events.csv")


class SRAnalyticsLogger:
    """
    Shadow-mode CSV logger for S/R Engine output.

    Two files:
      1. sr_analytics.csv — per-cycle state snapshot (zones, bias, context)
      2. sr_events.csv    — per-interaction event log with forward returns

    The events file is the critical one for validation. After 5+ trading
    sessions, you can analyze:
      - Do REJECTION events predict reversal? (check forward returns)
      - Do BREAKOUT events predict continuation?
      - Do FAILED_BREAKOUT events predict traps?
      - Is OI confirmation correlated with stronger events?
    """

    def __init__(self):
        os.makedirs("data", exist_ok=True)
        self._ensure_state_csv()
        self._ensure_events_csv()
        self._event_buffer = []  # Buffer interactions for batch forward-return updates

    def _ensure_state_csv(self):
        """Create state CSV with headers if it doesn't exist."""
        if not os.path.exists(SR_STATE_CSV):
            with open(SR_STATE_CSV, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "Timestamp", "Price",
                    "Nearest_Support_Low", "Nearest_Support_High", "Support_Strength",
                    "Nearest_Resistance_Low", "Nearest_Resistance_High", "Resistance_Strength",
                    "Support_OI_Score", "Resistance_OI_Score",
                    "Support_Touches", "Resistance_Touches",
                    "Support_Freshness", "Resistance_Freshness",
                    "SR_Bias", "SR_Bias_Score",
                    "Total_Zones", "Latest_Event", "Trade_Context",
                    "Engine_Decision", "Engine_Latency_ms",
                ])

    def _ensure_events_csv(self):
        """Create events CSV with headers if it doesn't exist."""
        if not os.path.exists(SR_EVENTS_CSV):
            with open(SR_EVENTS_CSV, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "Timestamp", "Zone_ID", "Event_Type",
                    "Price", "Volume",
                    "Zone_Role", "Zone_Mid", "Zone_Strength",
                    "OI_Confirmed", "Candles_In_Zone",
                    "Forward_5m", "Forward_10m", "Forward_15m", "Forward_30m",
                ])

    def log_state(
        self,
        sr_state: SRState,
        snapshot,  # MarketSnapshot
        engine_decision: str = "",
    ):
        """
        Log a per-cycle S/R state snapshot.

        Called from decision_engine._process_impl() every cycle.
        """
        try:
            ns = sr_state.nearest_support
            nr = sr_state.nearest_resistance

            row = [
                datetime.now().isoformat(),
                round(snapshot.price, 1),
                # Support
                round(ns.price_low, 1) if ns else "",
                round(ns.price_high, 1) if ns else "",
                round(ns.strength, 1) if ns else "",
                # Resistance
                round(nr.price_low, 1) if nr else "",
                round(nr.price_high, 1) if nr else "",
                round(nr.strength, 1) if nr else "",
                # OI scores
                round(ns.oi_score, 1) if ns else "",
                round(nr.oi_score, 1) if nr else "",
                # Touches
                ns.touch_count if ns else "",
                nr.touch_count if nr else "",
                # Freshness
                round(ns.freshness, 3) if ns else "",
                round(nr.freshness, 3) if nr else "",
                # Bias
                sr_state.sr_bias,
                round(sr_state.sr_bias_score, 2),
                # Meta
                sr_state.total_zones,
                sr_state.latest_event.event_type if sr_state.latest_event else "",
                sr_state.trade_context[:200],  # Truncate long context
                engine_decision,
                round(sr_state.engine_latency_ms, 1),
            ]

            with open(SR_STATE_CSV, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(row)

        except Exception as e:
            logger.error(f"Failed to log S/R state: {e}")

    def log_interaction(self, event: SRInteraction):
        """
        Log an individual interaction event.

        Initially logged WITHOUT forward returns (they're None).
        Later, update_forward_returns() fills them in.
        """
        try:
            row = [
                event.timestamp.isoformat() if event.timestamp else "",
                event.zone_id,
                event.event_type,
                round(event.price_at_event, 1),
                round(event.volume_at_event, 0),
                event.zone_role,
                round(event.zone_mid, 1),
                round(event.zone_strength, 1),
                event.oi_confirmed,
                event.candles_in_zone,
                # Forward returns — will be None initially
                round(event.forward_5m, 2) if event.forward_5m is not None else "",
                round(event.forward_10m, 2) if event.forward_10m is not None else "",
                round(event.forward_15m, 2) if event.forward_15m is not None else "",
                round(event.forward_30m, 2) if event.forward_30m is not None else "",
            ]

            with open(SR_EVENTS_CSV, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(row)

            self._event_buffer.append(event)

        except Exception as e:
            logger.error(f"Failed to log S/R interaction: {e}")

    def flush_resolved_events(self):
        """
        Re-log events that now have forward returns filled in.

        Called periodically to update the events CSV with
        the actual forward returns measured by SREngine.
        """
        resolved = [
            e for e in self._event_buffer
            if e.forward_30m is not None  # Fully resolved
        ]

        if not resolved:
            return

        for event in resolved:
            self.log_interaction(event)
            self._event_buffer.remove(event)

        if resolved:
            logger.info(
                f"📊 [SR ANALYTICS] Flushed {len(resolved)} resolved events "
                f"with forward returns"
            )
