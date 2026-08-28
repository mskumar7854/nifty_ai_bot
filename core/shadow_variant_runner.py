"""
============================================
🔬 SHADOW VARIANT RUNNER — Post-Decision Observer

A purely observational layer that replays V2's
already-captured gate results under alternative
policy configurations (variants).

Architecture:
  V2 decision
     ↓
  persist V2 snapshot
     ↓
  COMMIT (V2 is immutable at this point)
     ↓
  shadow variant observer  ← THIS MODULE
     ↓
  variant_decisions table

Rules:
  1. NEVER mutate V2 decisions, signals, or state
  2. NEVER rerun agents — uses already-computed gate data
  3. Failure in this module cannot prevent, modify,
     rollback, or delay the V2 snapshot
  4. Purely post-commit telemetry

CODE FREEZE: V2 control remains immutable.
============================================
"""

import sqlite3
import json
import logging
import os
from datetime import datetime
from typing import Dict, List, Optional, Any

logger = logging.getLogger("shadow_variant")

# ═══════════════════════════════════════════════════════════
# VARIANT CONFIGURATIONS
# ═══════════════════════════════════════════════════════════
#
# Each variant defines which gates to skip when replaying
# the V2 gate results. Variants can only REMOVE gates,
# never add new ones or change thresholds.
#
# EV and Unknown-Regime protection are preserved in ALL
# variants until evidence justifies their removal.
# ═══════════════════════════════════════════════════════════

VARIANTS = {
    "V2-Control": {
        "skip_gates": [],
        "skip_pre_gate_blocks": False,
        "description": "Immutable control — identical to frozen V2",
    },
    "V2.1-NoStructReset": {
        "skip_gates": ["Structure Reset"],
        "skip_pre_gate_blocks": False,
        "description": "Primary hypothesis — remove dominant over-filter",
    },
    "V2.2-NoStructReset-NoStruct": {
        "skip_gates": ["Structure Reset", "Structure"],
        "skip_pre_gate_blocks": False,
        "description": "Test structural over-filtering",
    },
    "V2.3-NoStructReset-NoRegimeGrade": {
        "skip_gates": ["Structure Reset", "Regime-Aware Grade"],
        "skip_pre_gate_blocks": False,
        "description": "Test interaction with regime grading",
    },
    "V2.4-SweetSpot": {
        "skip_gates": ["Structure Reset", "Structure", "Regime-Aware Grade"],
        "skip_pre_gate_blocks": False,
        "description": "Broader relaxation — ablation sweet spot",
    },
    "V2.5-NoStructReset-NoChop": {
        "skip_gates": ["Structure Reset", "Chop Zone"],
        "skip_pre_gate_blocks": False,
        "description": "Test whether Chop compounds the over-filter",
    },
    "V2.6-NoStructReset-NoPEV": {
        "skip_gates": ["Structure Reset", "Cost/Breakeven (PEV)"],
        "skip_pre_gate_blocks": False,
        "description": "Confirm PEV redundancy hypothesis",
    },
}


class ShadowVariantRunner:
    """
    Post-decision observer that replays gate results under
    alternative policy configurations.

    Called AFTER the V2 snapshot has been committed to the database.
    Cannot affect V2 decisions in any way.
    """

    def __init__(self, db_path: str = None):
        if db_path is None:
            mode = os.getenv("SYSTEM_MODE", "SIMULATION")
            self.db_path = "data/trading_v4_live.db" if mode != "SIMULATION" else "data/trading_v4_sim.db"
        else:
            self.db_path = db_path
        self.variants = VARIANTS
        self._ensure_table()

    def _ensure_table(self):
        """Create variant_decisions table if it doesn't exist."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS variant_decisions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    snapshot_id TEXT NOT NULL,
                    variant_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    v2_decision TEXT NOT NULL,
                    v2_reason TEXT,
                    variant_decision TEXT NOT NULL,
                    variant_gates_skipped TEXT,
                    variant_failed_gates TEXT,
                    variant_primary_blocker TEXT,
                    UNIQUE(snapshot_id, variant_id)
                )
            """)
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"[VARIANT] Failed to create table: {e}")

    def evaluate_variants(
        self,
        snapshot_id: str,
        gate_results: Dict[str, Any],
        v2_decision: str,
        v2_reason: str,
        timestamp: str,
    ):
        """
        Evaluate all registered variants for a given V2 snapshot.

        Called AFTER V2 snapshot is committed. This is post-commit telemetry.

        Args:
            snapshot_id: The unique V2 snapshot identifier (signal.id)
            gate_results: Dict of gate name → {passed, actual, required, detail}
                         This is the gate_results dict BEFORE JSON serialization.
            v2_decision: "EXECUTE" or "REJECTED"
            v2_reason: The V2 rejection reason (empty if approved)
            timestamp: ISO timestamp of the decision
        """
        try:
            # Determine if this was a pre-gate block
            is_pre_gate = self._is_pre_gate_block(v2_reason, gate_results)

            # Find which gates actually failed in V2
            failed_gates = []
            if gate_results:
                for gate_name, gate_data in gate_results.items():
                    passed = gate_data.get("passed", False)
                    if passed in (True, "True", "true"):
                        continue
                    failed_gates.append(gate_name)

            conn = sqlite3.connect(self.db_path)
            conn.execute("PRAGMA journal_mode=WAL;")

            for variant_id, config in self.variants.items():
                try:
                    variant_decision, remaining_failed, primary_blocker = self._evaluate_single(
                        v2_decision=v2_decision,
                        v2_reason=v2_reason,
                        failed_gates=failed_gates,
                        is_pre_gate=is_pre_gate,
                        config=config,
                    )

                    conn.execute(
                        """
                        INSERT OR IGNORE INTO variant_decisions
                        (snapshot_id, variant_id, timestamp, v2_decision, v2_reason,
                         variant_decision, variant_gates_skipped, variant_failed_gates,
                         variant_primary_blocker)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            snapshot_id,
                            variant_id,
                            timestamp,
                            v2_decision,
                            v2_reason or "",
                            variant_decision,
                            json.dumps(config["skip_gates"]),
                            json.dumps(remaining_failed),
                            primary_blocker,
                        ),
                    )
                except Exception as e:
                    logger.error(f"[VARIANT] Error evaluating {variant_id} for {snapshot_id}: {e}")

            conn.commit()
            conn.close()
        except Exception as e:
            # This must NEVER propagate up to affect V2
            logger.error(f"[VARIANT] evaluate_variants failed for {snapshot_id}: {e}")

    def _evaluate_single(
        self,
        v2_decision: str,
        v2_reason: str,
        failed_gates: List[str],
        is_pre_gate: bool,
        config: Dict,
    ) -> tuple:
        """
        Evaluate a single variant.

        Returns: (variant_decision, remaining_failed_gates, primary_blocker)
        """
        skip_gates = config["skip_gates"]
        skip_pre_gate = config.get("skip_pre_gate_blocks", False)

        # If V2 approved it, all variants also approve (can't add gates)
        if v2_decision == "EXECUTE":
            return ("WOULD_PASS", [], "")

        # Pre-gate blocks (Strike Policy, Premium Fetch, Weekend Buffer, etc.)
        if is_pre_gate:
            if skip_pre_gate:
                # Pre-gate lifted — check remaining gate failures
                remaining = [g for g in failed_gates if g not in skip_gates]
                if remaining:
                    return ("WOULD_FAIL", remaining, remaining[0])
                return ("WOULD_PASS", [], "")
            else:
                return ("WOULD_FAIL", ["PRE_GATE_BLOCK"], v2_reason or "PRE_GATE_BLOCK")

        # Standard gate failures
        remaining = [g for g in failed_gates if g not in skip_gates]

        if remaining:
            return ("WOULD_FAIL", remaining, remaining[0])
        return ("WOULD_PASS", [], "")

    def _is_pre_gate_block(self, reason: str, gate_results: Dict) -> bool:
        """
        Detect pre-gate blocks: candidates rejected before or despite
        the gate pipeline (Strike Policy, Premium Fetch, Weekend Buffer).
        """
        if not reason:
            return False

        pre_gate_keywords = [
            "Strike Policy",
            "Unknown market regime",
            "Premium Fetch",
            "Weekend Buffer",
        ]

        for keyword in pre_gate_keywords:
            if keyword in reason:
                return True

        # Also: if all gates passed but decision is REJECTED, it's a pre-gate block
        if gate_results:
            failed = [
                g for g, d in gate_results.items()
                if d.get("passed") not in (True, "True", "true")
            ]
            if len(failed) == 0:
                return True

        return False

    def backfill_from_db(self):
        """
        Backfill variant_decisions for all existing V2 snapshots.
        Uses gate_results_json and decision_json from decision_snapshots_v2.

        Returns: (total_processed, total_inserted)
        """
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL;")

        cursor = conn.execute("""
            SELECT snapshot_id, timestamp, gate_results_json, decision_json
            FROM decision_snapshots_v2
            ORDER BY timestamp
        """)

        total_processed = 0
        total_inserted = 0

        for row in cursor.fetchall():
            snapshot_id, timestamp, g_raw, d_raw = row
            total_processed += 1

            gate_results = json.loads(g_raw) if g_raw else {}
            decision = json.loads(d_raw) if d_raw else {}

            v2_decision = decision.get("action", "REJECTED")
            v2_reason = decision.get("reason", "")

            is_pre_gate = self._is_pre_gate_block(v2_reason, gate_results)

            failed_gates = []
            if gate_results:
                for gate_name, gate_data in gate_results.items():
                    passed = gate_data.get("passed", False)
                    if passed in (True, "True", "true"):
                        continue
                    failed_gates.append(gate_name)

            for variant_id, config in self.variants.items():
                try:
                    variant_decision, remaining_failed, primary_blocker = self._evaluate_single(
                        v2_decision=v2_decision,
                        v2_reason=v2_reason,
                        failed_gates=failed_gates,
                        is_pre_gate=is_pre_gate,
                        config=config,
                    )

                    conn.execute(
                        """
                        INSERT OR IGNORE INTO variant_decisions
                        (snapshot_id, variant_id, timestamp, v2_decision, v2_reason,
                         variant_decision, variant_gates_skipped, variant_failed_gates,
                         variant_primary_blocker)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            snapshot_id,
                            variant_id,
                            timestamp,
                            v2_decision,
                            v2_reason or "",
                            variant_decision,
                            json.dumps(config["skip_gates"]),
                            json.dumps(remaining_failed),
                            primary_blocker,
                        ),
                    )
                    total_inserted += 1
                except Exception as e:
                    logger.error(f"[VARIANT] Backfill error {variant_id}/{snapshot_id}: {e}")

        conn.commit()
        conn.close()

        return total_processed, total_inserted
