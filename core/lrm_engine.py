"""
============================================
🧠 LIQUIDITY REACTION MODEL ENGINE

The compositor that orchestrates all five LRM
layers into a single shadow observation.

Architecture:
  1. LiquidityZoneScorer  → ranked zones
  2. Is price AT a zone?
     NO  → log minimal snapshot, return
     YES ↓
  3. ApproachClassifier   → approach profile
  4. LiquidityEventDetector → event
  5. OrderFlowAnalyzer    → flow state
  6. Structure snapshot   → structural state
  7. Additive LRM score   → shadow decision

Scoring is ADDITIVE, not multiplicative.
Each component normalized to 0-100, then
averaged over available components. Missing
data is excluded from the denominator.

The engine says:
  "I don't care where NIFTY goes. I'll wait
   until it reaches a statistically interesting
   location, then I'll determine whether the
   market is actually rejecting or accepting
   that area."

EVERY zone interaction is logged — not just
events — to provide a proper statistical
denominator.

⚠️ SHADOW MODE ONLY — never influences V2.
============================================
"""

import uuid
from datetime import datetime
from time import perf_counter
from typing import Optional, List, Dict, Any

import pandas as pd

from config.settings import Settings
from core.liquidity_zone_scorer import LiquidityZoneScorer
from core.approach_classifier import ApproachClassifier
from core.liquidity_event_detector import LiquidityEventDetector
from core.order_flow_analyzer import OrderFlowAnalyzer
from models.lrm_models import (
    LRMCycleSnapshot, LRMSignal, LiquidityZone,
    ForwardMetrics, StructuralState, LiquidityEventType,
)
from models.sr_zone import SRState
from models.oi_analysis import OIAnalysis
from models.amd_state import AMDState
from utils.logger import get_logger

import subprocess

logger = get_logger("lrm_engine")

# ── Decision Thresholds ──
# These are for the initial observation phase.
# They do NOT need to be optimal — the data will tell us
# what thresholds actually separate good from bad setups.
LRM_CANDIDATE_THRESHOLD = 55.0     # Composite score above this = candidate
PROXIMITY_ATR = 1.5                # "At zone" proximity threshold

def get_git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"]).decode("utf-8").strip()
    except Exception:
        return "unknown"


class LRMEngine:
    """
    Liquidity Reaction Model — Shadow Research Engine.

    Called every decision cycle AFTER V2 has committed.
    Produces an LRMCycleSnapshot for logging.

    Zero V2 contamination. Zero side effects.
    """

    def __init__(self, settings: Settings):
        self.settings = settings

        # ── Sub-engines ──
        self.zone_scorer = LiquidityZoneScorer()
        self.approach_classifier = ApproachClassifier()
        self.event_detector = LiquidityEventDetector()
        self.flow_analyzer = OrderFlowAnalyzer()

        # ── Forward metrics tracking ──
        self._pending_forward: List[Dict] = []
        self._session_date: Optional[str] = None
        self._git_commit = get_git_commit()

    def reset_session(self):
        """Reset for a new trading session."""
        today = datetime.now().strftime("%Y-%m-%d")
        if self._session_date != today:
            logger.info(f"🔄 [LRM] New session detected ({today}). Resetting.")
            self.event_detector.reset_session(today)
            self.flow_analyzer.reset_session(today)
            self._pending_forward.clear()
            self._session_date = today

    def update(
        self,
        df: Optional[pd.DataFrame],
        snapshot,
        sr_state: Optional[SRState] = None,
        oi_analysis: Optional[OIAnalysis] = None,
        amd_state: Optional[AMDState] = None,
        structure_tracker_state: Optional[Dict[str, Any]] = None,
        v2_decision: str = "",
        v2_kill_reason: str = "",
    ) -> LRMCycleSnapshot:
        """
        Main entry point — called every cycle after V2 commit.

        Returns a complete LRMCycleSnapshot for logging.
        EVERY call is logged, not just events.
        """
        t0 = perf_counter()
        self.reset_session()

        # ── Basic validation ──
        if df is None or df.empty or len(df) < 5:
            return LRMCycleSnapshot(
                lrm_signal=LRMSignal.NO_TRADE,
                lrm_signal_reason="Insufficient data",
                v2_decision=v2_decision,
                v2_kill_reason=v2_kill_reason,
                engine_latency_ms=(perf_counter() - t0) * 1000,
            )

        price = snapshot.price if snapshot else df["close"].iloc[-1]
        atr = snapshot.atr if snapshot and snapshot.atr > 0 else 15.0
        vwap = snapshot.vwap if snapshot else 0.0
        regime = ""
        if snapshot and hasattr(snapshot, "regime_state"):
            regime = snapshot.regime_state.get("regime", "")

        # ── Resolve forward returns for pending interactions ──
        self._resolve_forward_metrics(price, datetime.now(), atr)

        # ── Layer 1: Location — Score zones ──
        zones = self.zone_scorer.score_zones(
            price=price,
            atr=atr,
            sr_state=sr_state,
            oi_analysis=oi_analysis,
            snapshot=snapshot,
        )

        # Find nearest zone
        nearest_zone = self.zone_scorer.find_nearest_zone(price, atr, zones)
        at_zone = nearest_zone is not None

        # ── Build base snapshot ──
        cycle_id = str(uuid.uuid4())[:12]
        snap = LRMCycleSnapshot(
            timestamp=datetime.now(),
            cycle_id=cycle_id,
            lrm_schema_version="v1.0",
            git_commit=self._git_commit,
            price=price,
            atr=atr,
            vwap=vwap,
            regime=regime,
            at_zone=at_zone,
            nearest_zone=nearest_zone,
            v2_decision=v2_decision,
            v2_kill_reason=v2_kill_reason,
            lrm_signal=LRMSignal.NO_TRADE,
        )

        if not at_zone:
            snap.lrm_signal_reason = "Not at liquidity zone"
            snap.engine_latency_ms = (perf_counter() - t0) * 1000
            return snap

        # ── We ARE at a zone — run all layers ──
        snap.location_score = nearest_zone.zone_measurement_score

        # ── Layer 2: Approach ──
        approach = self.approach_classifier.classify(
            df=df, zone=nearest_zone, price=price, atr=atr,
        )
        snap.approach = approach
        snap.approach_score = approach.approach_score

        # ── Layer 3: Liquidity Event ──
        sr_latest = None
        if sr_state and sr_state.latest_event:
            sr_latest = sr_state.latest_event.event_type

        oi_confirmed = False
        if nearest_zone and oi_analysis:
            oi_confirmed = nearest_zone.oi_measurement > 30

        event = self.event_detector.detect(
            df=df,
            zone=nearest_zone,
            price=price,
            atr=atr,
            sr_latest_event=sr_latest,
            amd_state=amd_state,
            oi_confirmed=oi_confirmed,
        )
        snap.event = event
        snap.event_score = event.event_score

        # ── Layer 4: Order Flow ──
        flow = self.flow_analyzer.analyze(snapshot)
        snap.flow = flow
        snap.flow_score = flow.flow_score

        # ── Layer 5: Structure ──
        struct_state = self._extract_structural_state(structure_tracker_state)
        snap.structure = struct_state
        snap.structure_score = struct_state.structure_score

        # ── Compute additive composite score ──
        components = []
        component_count = 0

        # Location is always available if we're at a zone
        components.append(snap.location_score)
        component_count += 1

        # Approach
        if approach.approach_type != approach.approach_type.INSUFFICIENT:
            components.append(snap.approach_score)
            component_count += 1

        # Event (only contributes if an event was detected)
        if event.event_type != LiquidityEventType.NONE:
            components.append(snap.event_score)
            component_count += 1

        # Flow (only if data available)
        if flow.data_available:
            components.append(snap.flow_score)
            component_count += 1

        # Structure (always available — reads from tracker)
        components.append(snap.structure_score)
        component_count += 1

        snap.components_available = component_count
        if component_count > 0:
            snap.lrm_composite_score = sum(components) / component_count
        else:
            snap.lrm_composite_score = 0.0

        # ── Shadow decision ──
        snap.lrm_signal, snap.lrm_signal_reason = self._make_shadow_decision(
            snap, nearest_zone, event, flow, struct_state,
        )

        # ── Register forward metrics tracking ──
        # Track ALL zone interactions, not just events
        direction = "LONG" if nearest_zone.role == "SUPPORT" else "SHORT"
        forward = ForwardMetrics(
            price_at_interaction=price,
            interaction_timestamp=datetime.now(),
            atr_at_interaction=atr,
            direction=direction,
        )
        snap.forward_metrics = forward
        self._pending_forward.append({
            "snapshot": snap,
            "forward": forward,
            "price_at_interaction": price,
            "ts": datetime.now(),
            "direction": direction,
            "atr": atr,
            "high_since": price,    # For MFE tracking
            "low_since": price,     # For MAE tracking
        })

        snap.engine_latency_ms = (perf_counter() - t0) * 1000
        return snap

    def _make_shadow_decision(
        self,
        snap: LRMCycleSnapshot,
        zone: LiquidityZone,
        event,
        flow,
        structure: StructuralState,
    ) -> tuple:
        """
        Make the shadow LRM decision.

        This is for logging/comparison only. It never routes orders.

        Decision logic:
          - Must have a liquidity event (sweep or rejection)
          - Composite score must exceed threshold
          - Direction comes from zone role + event type
        """
        # No event = no trade candidate
        if event.event_type in (LiquidityEventType.NONE, LiquidityEventType.ACCEPTANCE):
            reason = f"At zone {zone.mid:.0f} but no reaction event"
            if event.event_type == LiquidityEventType.ACCEPTANCE:
                reason = f"Zone {zone.mid:.0f} accepted (broken through)"
            return LRMSignal.NO_TRADE, reason

        # Composite threshold check
        if snap.lrm_composite_score < LRM_CANDIDATE_THRESHOLD:
            return (
                LRMSignal.NO_TRADE,
                f"Composite {snap.lrm_composite_score:.1f} < threshold {LRM_CANDIDATE_THRESHOLD}",
            )

        # Determine direction from zone role + event type
        if zone.role == "RESISTANCE":
            if event.event_type in (LiquidityEventType.SWEEP, LiquidityEventType.REJECTION):
                signal = LRMSignal.SHORT_CANDIDATE
                reason = (
                    f"Resistance {zone.mid:.0f} "
                    f"{event.event_type.value} "
                    f"(conf={event.confidence:.2f}, "
                    f"composite={snap.lrm_composite_score:.1f})"
                )
            else:
                return LRMSignal.NO_TRADE, f"Resistance absorption — ambiguous"
        elif zone.role == "SUPPORT":
            if event.event_type in (LiquidityEventType.SWEEP, LiquidityEventType.REJECTION):
                signal = LRMSignal.LONG_CANDIDATE
                reason = (
                    f"Support {zone.mid:.0f} "
                    f"{event.event_type.value} "
                    f"(conf={event.confidence:.2f}, "
                    f"composite={snap.lrm_composite_score:.1f})"
                )
            else:
                return LRMSignal.NO_TRADE, f"Support absorption — ambiguous"
        else:
            return LRMSignal.NO_TRADE, "Zone role ambiguous"

        # Check structural agreement (log but don't gate)
        if structure.agrees_with_lrm:
            reason += " | Structure AGREES"
        else:
            reason += " | Structure DISAGREES"

        return signal, reason

    def _extract_structural_state(
        self, tracker_state: Optional[Dict[str, Any]]
    ) -> StructuralState:
        """
        Extract structural state from TrendStructureTracker.

        Read-only — never modifies the tracker.
        """
        if not tracker_state:
            return StructuralState(structure_score=50.0)  # Neutral

        has_bos = tracker_state.get("has_bos", False)
        has_choch = tracker_state.get("has_choch", False)
        has_sweep = tracker_state.get("has_liquidity_sweep", False)
        has_vwap = tracker_state.get("has_vwap_reclaim", False)
        direction = tracker_state.get("active_direction", "")
        leg_id = tracker_state.get("leg_id", 0)
        entries = tracker_state.get("entries_in_leg", 0)

        # Structure score: 50 = neutral, higher = more structural confirmation
        score = 50.0
        if has_bos:
            score += 20
        if has_choch:
            score += 15
        if has_sweep:
            score += 10
        if has_vwap:
            score += 10
        if entries == 0:
            score += 5  # Fresh leg = more interesting

        score = min(100.0, score)

        return StructuralState(
            has_bos=has_bos,
            has_choch=has_choch,
            has_liquidity_sweep=has_sweep,
            has_vwap_reclaim=has_vwap,
            active_direction=direction,
            leg_id=leg_id,
            entries_in_leg=entries,
            structure_score=score,
        )

    def _resolve_forward_metrics(
        self, current_price: float, now: datetime, current_atr: float,
    ):
        """
        Fill forward returns + update MAE/MFE for pending interactions.

        MAE/MFE are updated every cycle until the 30m window closes.
        This is the mechanism that determines whether reactions
        actually provide tradable edge.
        """
        resolved = []

        for entry in self._pending_forward:
            fwd = entry["forward"]
            p0 = entry["price_at_interaction"]
            ts = entry["ts"]
            direction = entry["direction"]
            atr = entry["atr"]
            elapsed_min = (now - ts).total_seconds() / 60.0

            # ── Update MAE/MFE every cycle ──
            entry["high_since"] = max(entry["high_since"], current_price)
            entry["low_since"] = min(entry["low_since"], current_price)

            if direction == "LONG":
                # MAE = how far price went against us (below entry)
                fwd.mae_points = max(fwd.mae_points, p0 - entry["low_since"])
                # MFE = how far price went in our favor (above entry)
                fwd.mfe_points = max(fwd.mfe_points, entry["high_since"] - p0)
            else:  # SHORT
                fwd.mae_points = max(fwd.mae_points, entry["high_since"] - p0)
                fwd.mfe_points = max(fwd.mfe_points, p0 - entry["low_since"])

            if atr > 0:
                fwd.mae_atr = fwd.mae_points / atr
                fwd.mfe_atr = fwd.mfe_points / atr

            # ── Fill forward returns at milestones ──
            if elapsed_min >= 5 and fwd.forward_5m is None:
                fwd.forward_5m = current_price - p0

            if elapsed_min >= 10 and fwd.forward_10m is None:
                fwd.forward_10m = current_price - p0

            if elapsed_min >= 15 and fwd.forward_15m is None:
                fwd.forward_15m = current_price - p0

            if elapsed_min >= 30 and fwd.forward_30m is None:
                fwd.forward_30m = current_price - p0
                fwd.resolved = True
                resolved.append(entry)

        # Remove fully resolved
        for entry in resolved:
            if entry in self._pending_forward:
                self._pending_forward.remove(entry)

    def get_pending_forward_count(self) -> int:
        """Return count of interactions awaiting forward resolution."""
        return len(self._pending_forward)
