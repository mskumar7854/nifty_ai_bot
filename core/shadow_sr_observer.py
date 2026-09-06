"""
============================================
STRUCTURE RESET SHADOW OBSERVER

A telemetry-only observer that tracks prospective
outcomes for Structure Reset re-entry candidates
under 25% and 50% position sizing.

ARCHITECTURAL SAFETY GUARANTEE:
  This module has NO import of, reference to, or
  dependency on any OMS, broker, or order-routing
  component. It is physically incapable of placing
  orders by construction — not by configuration flag.

  Signal → Decision → Risk Simulation → Telemetry
                            ✕
                           OMS

PIPELINE INTEGRATION:
  Called by ShadowVariantRunner.evaluate_variants()
  AFTER the V2 snapshot has been committed. The
  production decision is already final and immutable
  at this point.

VARIANTS TRACKED:
  - Shadow-B: 50% position sizing on SR rejections
  - Shadow-C: 25% position sizing on SR rejections
  Both track the same candidates; only the simulated
  position size differs for risk-adjusted comparison.
============================================
"""

import json
import os
import logging
from datetime import datetime, date
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger("shadow_sr_observer")

SHADOW_TELEMETRY_DIR = Path("data") / "telemetry" / "shadow_sr"


EXPERIMENT_METADATA = {
    "experiment_id": "SR-SHADOW-V1",
    "experiment_version": "1.0.0",
    "start_timestamp": "2026-09-03T21:00:00Z",
    "code_version": "v5.0.0",
    "variant_definitions": {
        "shadow_b": "50% simulated allocation on REJECTED_SAME_STRUCTURAL_TREND",
        "shadow_c": "25% simulated allocation on REJECTED_SAME_STRUCTURAL_TREND"
    },
    "risk_assumptions": {
        "target_rr": 2.0,
        "stop_rr": 1.0,
        "ambiguous_bar_rule": "WORST_CASE_STOP_FIRST",
        "time_exit": "15:15:00"
    },
    "friction_assumptions": {
        "slippage_points": 0.5,
        "transaction_cost_inr": 40.0
    }
}

class StructureResetShadowObserver:
    """
    Observes every REJECTED_SAME_STRUCTURAL_TREND signal and logs
    a prospective shadow record for later outcome evaluation.

    This class has ZERO awareness of order routing. It writes JSONL
    telemetry records only. It does not import OMS, Broker, or any
    execution-related module.
    """

    def __init__(self):
        SHADOW_TELEMETRY_DIR.mkdir(parents=True, exist_ok=True)
        self._today_file: Optional[str] = None
        self._today_date: Optional[date] = None

    def _get_log_file(self) -> str:
        today = date.today()
        if self._today_date != today:
            self._today_date = today
            self._today_file = str(
                SHADOW_TELEMETRY_DIR / f"sr_shadow_{today.strftime('%Y%m%d')}.jsonl"
            )
        return self._today_file

    def observe(
        self,
        snapshot_id: str,
        timestamp: str,
        signal_type: str,
        direction: str,
        spot: float,
        strike: Optional[int],
        confidence: float,
        regime: str,
        rejection_reason: str,
        entry_price: float,
        stop_loss: float,
        target_1: float,
        gate_results: Dict[str, Any],
        structure_details: Dict[str, Any],
    ):
        if "SAME_STRUCTURAL_TREND" not in (rejection_reason or ""):
            return

        risk_distance = abs(entry_price - stop_loss) if entry_price and stop_loss else 0.0
        reward_distance = abs(target_1 - entry_price) if entry_price and target_1 else 0.0

        record = {
            # Immutable Experiment Metadata
            "experiment": EXPERIMENT_METADATA,

            # Identity
            "snapshot_id": snapshot_id,
            "timestamp": timestamp,
            "date": timestamp[:10] if timestamp else "",

            # Signal characteristics (decision-time only)
            "signal_type": signal_type,
            "direction": direction,
            "spot": round(spot, 2),
            "strike": strike,
            "confidence": round(confidence, 2),
            "regime": regime,

            # Production action (always REJECT for these)
            "production_action": "REJECT",
            "rejection_reason": rejection_reason,

            # Shadow actions (telemetry-only, no order routing)
            "shadow_b_action": "ACCEPT_50_PCT",
            "shadow_b_size_multiplier": 0.50,
            "shadow_c_action": "ACCEPT_25_PCT",
            "shadow_c_size_multiplier": 0.25,

            # Trade specification (decision-time levels)
            "entry_price": round(entry_price, 2),
            "stop_loss": round(stop_loss, 2),
            "target_1": round(target_1, 2),
            "risk_distance_pts": round(risk_distance, 2),
            "reward_distance_pts": round(reward_distance, 2),
            "rr_ratio": round(reward_distance / risk_distance, 2) if risk_distance > 0 else 0.0,

            # Forward outcome fields (populated by post-session replay)
            "mfe_pts": None,
            "mae_pts": None,
            "outcome": None,  # TARGET_HIT / STOPPED_OUT / TIME_EXIT / PENDING

            # Production baseline counterfactual
            "production_counterfactual_r": 0.0,  # Always 0 (production rejected)

            # Decomposed Shadow Results (Strategy Alpha vs Economic Friction)
            "shadow_b_gross_r": None,
            "shadow_b_slippage_r": None,
            "shadow_b_fee_r": None,
            "shadow_b_net_r": None,

            "shadow_c_gross_r": None,
            "shadow_c_slippage_r": None,
            "shadow_c_fee_r": None,
            "shadow_c_net_r": None,

            # Structure context at decision time
            "structure_leg_id": structure_details.get("leg_id"),
            "structure_entries_in_leg": structure_details.get("entries_in_leg"),
            "structure_active_direction": structure_details.get("active_direction"),
            "structure_reset_event": structure_details.get("reset_event"),
            "structure_has_bos": structure_details.get("has_bos", False),
            "structure_has_choch": structure_details.get("has_choch", False),

            # Gate context (which other gates also failed, if any)
            "other_failed_gates": [
                g for g, d in (gate_results or {}).items()
                if not d.get("passed", True) and "Structure Reset" not in g
            ],
        }

        try:
            log_path = self._get_log_file()
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, default=str) + "\n")
            logger.info(
                f"[SHADOW-SR] Recorded: {snapshot_id} | "
                f"{signal_type} @ {spot:.2f} | "
                f"Conf={confidence:.1f}% | "
                f"Entry={entry_price:.2f} SL={stop_loss:.2f} TP={target_1:.2f}"
            )
        except Exception as e:
            # Shadow telemetry failures must never propagate
            logger.error(f"[SHADOW-SR] Failed to write telemetry: {e}")


def compute_shadow_realized_r_breakdown(
    outcome: str,
    size_multiplier: float,
    base_risk_rupees: float = 1500.0,
    fee_rupees: float = 40.0,
    slippage_pts: float = 0.5,
    stop_distance_pts: float = 10.0
) -> Dict[str, float]:
    """
    Decomposes realized performance into Gross R, Slippage Drag, Fee Drag, and Net R:
        Gross R: Pure strategy edge (+2.0R target, -1.0R stop, 0.0R flat)
        Slippage R: Point slippage relative to stop distance
        Fee R: Fixed rupee transaction costs relative to allocated risk denominator
        Net R: Gross R - Slippage R - Fee R

    Enables diagnosing whether future performance issues are Strategy Failures (Gross R < 0)
    or Economics Failures (Gross R > 0, but Fee Drag consumes edge at small size).
    """
    allocated_risk = base_risk_rupees * size_multiplier
    if allocated_risk <= 0:
        return {"gross_r": 0.0, "slippage_r": 0.0, "fee_r": 0.0, "net_r": 0.0}

    slippage_drag_r = round((slippage_pts / stop_distance_pts), 4) if stop_distance_pts > 0 else 0.0
    fee_drag_r = round(fee_rupees / allocated_risk, 4)

    if "TARGET" in outcome.upper():
        gross_r = 2.0
    elif "STOP" in outcome.upper():
        gross_r = -1.0
    else:
        # Time exit / flat
        gross_r = 0.0

    net_r = round(gross_r - slippage_drag_r - fee_drag_r, 4)
    return {
        "gross_r": gross_r,
        "slippage_r": slippage_drag_r,
        "fee_r": fee_drag_r,
        "net_r": net_r
    }


def compute_shadow_realized_r(
    outcome: str,
    size_multiplier: float,
    base_risk_rupees: float = 1500.0,
    fee_rupees: float = 40.0,
    slippage_pts: float = 0.5,
    stop_distance_pts: float = 10.0
) -> float:
    """Convenience wrapper returning Net Realized R."""
    breakdown = compute_shadow_realized_r_breakdown(
        outcome=outcome,
        size_multiplier=size_multiplier,
        base_risk_rupees=base_risk_rupees,
        fee_rupees=fee_rupees,
        slippage_pts=slippage_pts,
        stop_distance_pts=stop_distance_pts,
    )
    return breakdown["net_r"]

