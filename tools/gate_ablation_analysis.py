"""
============================================================
🔬 ZERO-TRADE GATE-ABLATION DIAGNOSTIC ANALYSIS

Read-only forensic analysis of the V2 candidate policy.
Simulates removing each strategy gate individually and in
combination to identify which gates are over-restrictive
vs. genuinely protective.

CODE FREEZE: ACTIVE — No production code is modified.

Usage:
    python tools/gate_ablation_analysis.py
============================================================
"""

import sqlite3
import json
import os
import sys
import itertools
from datetime import datetime
from pathlib import Path
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional

import pandas as pd
import numpy as np

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

WORKSPACE = Path(r"c:\Users\Selva\Downloads\nifty-ai-system")
sys.path.insert(0, str(WORKSPACE))
DB_PATH = WORKSPACE / "data" / "trading_v4_sim.db"
REPORT_DIR = WORKSPACE / "reports"

# Gates tracked in gate_results_json
PREDICTIVE_GATES = [
    "Structure",
    "Structure Reset",
    "Cost/Breakeven (PEV)",
    "Expected Value (EV)",
    "Regime-Aware Grade",
    "Chop Zone",
    "Confidence",
    "Confluence",
    "Agent Agreement",
    "Regime",
    "Daily Limit",
    "Decay/Theta",
    "Learning Gate",
]

# Pre-gate blockers (rejected before gate pipeline runs)
PRE_GATE_BLOCKER = "Strike Policy: Unknown Regime"

# Short names for readability in tables
GATE_SHORT = {
    "Structure": "Structure",
    "Structure Reset": "StructReset",
    "Cost/Breakeven (PEV)": "PEV",
    "Expected Value (EV)": "EV",
    "Regime-Aware Grade": "RegimeGrade",
    "Chop Zone": "Chop",
    "Confidence": "Confidence",
    "Confluence": "Confluence",
    "Agent Agreement": "AgentAgree",
    "Regime": "Regime",
    "Daily Limit": "DailyLimit",
    "Decay/Theta": "Decay",
    "Learning Gate": "Learning",
    PRE_GATE_BLOCKER: "UnknownRegime",
}


# ═══════════════════════════════════════════════════════════
# DATA STRUCTURES
# ═══════════════════════════════════════════════════════════

@dataclass
class CandidateRecord:
    snapshot_id: str
    timestamp: str
    date: str
    signal: str
    spot: float
    raw_conf: float
    sl_pts: float
    mfe_pts: float
    mfe_r: float
    mae_pts: float
    mae_r: float
    outcome: str
    realized_r: float
    is_profitable: bool
    decision_action: str  # EXECUTE or REJECTED
    primary_reason: str
    failed_gates: List[str]    # gates that actually failed
    passed_gates: List[str]    # gates that passed
    is_pre_gate_block: bool    # blocked before gate pipeline
    has_levels: bool


@dataclass
class AblationResult:
    """Result of simulating a policy variant."""
    policy_name: str
    gates_removed: List[str]
    # Policy qualification (would candidate pass gates?)
    qualified_count: int = 0
    qualified_profitable: int = 0
    qualified_unprofitable: int = 0
    qualified_net_r: float = 0.0
    qualified_gross_pos_r: float = 0.0
    qualified_gross_neg_r: float = 0.0
    qualified_avg_r: float = 0.0
    qualified_median_r: float = 0.0
    qualified_win_rate: float = 0.0
    qualified_profit_factor: float = 0.0
    qualified_max_ae: float = 0.0
    qualified_max_consec_losses: int = 0
    qualified_r_values: List[float] = field(default_factory=list)
    # OMS-constrained sequential execution
    executed_count: int = 0
    executed_profitable: int = 0
    executed_unprofitable: int = 0
    executed_net_r: float = 0.0
    executed_gross_pos_r: float = 0.0
    executed_gross_neg_r: float = 0.0
    executed_avg_r: float = 0.0
    executed_median_r: float = 0.0
    executed_win_rate: float = 0.0
    executed_profit_factor: float = 0.0
    executed_max_ae: float = 0.0
    executed_max_consec_losses: int = 0
    executed_r_values: List[float] = field(default_factory=list)


# ═══════════════════════════════════════════════════════════
# DATA LOADING
# ═══════════════════════════════════════════════════════════

def load_all_candidates() -> List[CandidateRecord]:
    """Load all decision snapshots with gate results and counterfactual outcomes."""
    if not DB_PATH.exists():
        print(f"Database not found: {DB_PATH}")
        return []

    conn = sqlite3.connect(str(DB_PATH))
    query = """
        SELECT snapshot_id, timestamp, market_json, decision_json, 
               confidence_json, gate_results_json, execution_json
        FROM decision_snapshots_v2
        ORDER BY timestamp
    """
    df = pd.read_sql_query(query, conn)
    conn.close()

    if df.empty:
        return []

    df["dt"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values("dt").reset_index(drop=True)

    candidates = []

    for idx, row in df.iterrows():
        dt_snap = row["dt"]

        m_json = json.loads(row["market_json"]) if row["market_json"] else {}
        d_json = json.loads(row["decision_json"]) if row["decision_json"] else {}
        c_json = json.loads(row["confidence_json"]) if row["confidence_json"] else {}
        e_json = json.loads(row["execution_json"]) if row.get("execution_json") else {}
        g_json = json.loads(row["gate_results_json"]) if row["gate_results_json"] else {}

        spot = m_json.get("spot_price", 0.0)
        atr = m_json.get("atr", 12.0) or 12.0

        entry_p = float(e_json.get("entry_price", 0.0))
        sl_p = float(e_json.get("stop_loss", 0.0))
        tp_p = float(e_json.get("target_1", 0.0))
        sig_dir = str(e_json.get("direction", ""))

        has_levels = bool(entry_p > 0 and sl_p > 0 and tp_p > 0)

        if has_levels:
            sig_type = "BUY_CE" if sig_dir == "LONG" else "BUY_PE" if sig_dir == "SHORT" else "BUY_CE"
            spot_entry = entry_p
            sl_dist = abs(entry_p - sl_p)
            tp_dist = abs(tp_p - entry_p)
        else:
            sig_type = "BUY_PE" if dt_snap.hour >= 10 and dt_snap.hour <= 14 and dt_snap.minute > 20 else "BUY_CE"
            spot_entry = spot
            sl_dist = max(atr * 1.5, 10.0)
            tp_dist = sl_dist * 2.0

        # Simulate counterfactual outcome
        future_snaps = df[df["dt"] >= dt_snap]
        mfe_pts = 0.0
        mae_pts = 0.0
        outcome = "TIME_EXIT"
        realized_r = 0.0
        exit_dt = dt_snap + pd.Timedelta(minutes=45)

        if len(future_snaps) > 1:
            for _, f_row in future_snaps.iterrows():
                f_dt = f_row["dt"]
                f_m = json.loads(f_row["market_json"]) if f_row["market_json"] else {}
                p = f_m.get("spot_price")
                if not p:
                    continue

                fav = (spot_entry - p) if sig_type == "BUY_PE" else (p - spot_entry)
                adv = (p - spot_entry) if sig_type == "BUY_PE" else (spot_entry - p)

                if fav > mfe_pts:
                    mfe_pts = fav
                if adv > mae_pts:
                    mae_pts = adv

                if adv >= sl_dist and outcome == "TIME_EXIT":
                    outcome = "STOPPED_OUT (-1.0R)"
                    realized_r = -1.0
                    exit_dt = f_dt
                    break
                elif fav >= tp_dist and outcome == "TIME_EXIT":
                    outcome = "TARGET_HIT (+2.0R)"
                    realized_r = round(tp_dist / sl_dist, 2) if sl_dist > 0 else 2.0
                    exit_dt = f_dt
                    break

            if outcome == "TIME_EXIT":
                last_snap = future_snaps.iloc[-1]
                f_m = json.loads(last_snap["market_json"]) if last_snap["market_json"] else {}
                end_p = f_m.get("spot_price", spot_entry)
                pnl_pts = (spot_entry - end_p) if sig_type == "BUY_PE" else (end_p - spot_entry)
                realized_r = round(pnl_pts / sl_dist, 2) if sl_dist > 0 else 0.0
                exit_dt = last_snap["dt"]

        # Parse gate results
        failed_gates = []
        passed_gates = []
        for gname, gdata in g_json.items():
            p = gdata.get("passed")
            if p is True or p == "True" or p == "true":
                passed_gates.append(gname)
            else:
                failed_gates.append(gname)

        decision_action = d_json.get("action", "REJECTED")
        primary_reason = d_json.get("reason", "")

        # Detect pre-gate blocks (Strike Policy, Unknown Regime, Premium Fetch, Weekend Buffer)
        # These are rejected BEFORE the gate pipeline runs (or gates run but decision is overridden)
        is_pre_gate_block = (
            "Strike Policy" in primary_reason 
            or "Unknown market regime" in primary_reason
            or "Premium Fetch" in primary_reason
            or "Weekend Buffer" in primary_reason
            # Also: if all gates passed but decision is REJECTED, it's a pre-gate/execution block
            or (decision_action == "REJECTED" and len(failed_gates) == 0)
        )

        candidates.append(CandidateRecord(
            snapshot_id=row["snapshot_id"],
            timestamp=row["timestamp"],
            date=dt_snap.strftime("%Y-%m-%d"),
            signal=sig_type,
            spot=spot_entry,
            raw_conf=c_json.get("raw", 0.0),
            sl_pts=round(sl_dist, 1) if has_levels else round(sl_dist, 1),
            mfe_pts=round(mfe_pts, 1),
            mfe_r=round(mfe_pts / sl_dist, 2) if sl_dist > 0 else 0.0,
            mae_pts=round(mae_pts, 1),
            mae_r=round(mae_pts / sl_dist, 2) if sl_dist > 0 else 0.0,
            outcome=outcome,
            realized_r=realized_r,
            is_profitable=(realized_r > 0),
            decision_action=decision_action,
            primary_reason=primary_reason,
            failed_gates=failed_gates,
            passed_gates=passed_gates,
            is_pre_gate_block=is_pre_gate_block,
            has_levels=has_levels,
        ))

    return candidates


# ═══════════════════════════════════════════════════════════
# METRICS CALCULATION
# ═══════════════════════════════════════════════════════════

def compute_r_metrics(r_values: List[float]) -> dict:
    """Compute comprehensive R-based metrics."""
    if not r_values:
        return {
            "count": 0, "winners": 0, "losers": 0,
            "net_r": 0.0, "gross_pos_r": 0.0, "gross_neg_r": 0.0,
            "avg_r": 0.0, "median_r": 0.0, "win_rate": 0.0,
            "profit_factor": 0.0, "max_ae": 0.0, "max_consec_losses": 0,
        }

    arr = np.array(r_values)
    winners = int(np.sum(arr > 0))
    losers = int(np.sum(arr <= 0))
    gross_pos = float(arr[arr > 0].sum()) if winners > 0 else 0.0
    gross_neg = float(arr[arr <= 0].sum()) if losers > 0 else 0.0

    # Profit factor
    pf = abs(gross_pos / gross_neg) if gross_neg < 0 else float("inf") if gross_pos > 0 else 0.0

    # Max consecutive losses
    max_consec = 0
    current_consec = 0
    for r in r_values:
        if r <= 0:
            current_consec += 1
            max_consec = max(max_consec, current_consec)
        else:
            current_consec = 0

    # Max adverse excursion (max mae_r not available here — use max drawdown in R)
    max_ae = float(arr.min()) if len(arr) > 0 else 0.0

    return {
        "count": len(r_values),
        "winners": winners,
        "losers": losers,
        "net_r": float(arr.sum()),
        "gross_pos_r": gross_pos,
        "gross_neg_r": gross_neg,
        "avg_r": float(arr.mean()),
        "median_r": float(np.median(arr)),
        "win_rate": winners / len(r_values) * 100.0 if r_values else 0.0,
        "profit_factor": min(pf, 999.0),
        "max_ae": max_ae,
        "max_consec_losses": max_consec,
    }


def simulate_oms_sequential(candidates: List[CandidateRecord], qualifies_fn) -> List[CandidateRecord]:
    """
    Simulate OMS sequential execution (max_active_positions=1).
    Returns the list of candidates that would actually execute.
    """
    executed = []
    active_until = None

    # Sort by timestamp
    sorted_cands = sorted(candidates, key=lambda c: c.timestamp)

    for c in sorted_cands:
        if not qualifies_fn(c):
            continue

        dt_snap = pd.to_datetime(c.timestamp)

        if active_until is not None and dt_snap < active_until:
            continue  # OMS blocked

        # This candidate executes
        executed.append(c)

        # Calculate exit time
        sl_dist = c.sl_pts
        tp_dist = sl_dist * 2.0
        exit_minutes = 45  # default hold
        if "TARGET_HIT" in c.outcome:
            exit_minutes = 15  # approximate
        elif "STOPPED_OUT" in c.outcome:
            exit_minutes = 10  # approximate
        active_until = dt_snap + pd.Timedelta(minutes=exit_minutes)

    return executed


# ═══════════════════════════════════════════════════════════
# ABLATION ENGINE
# ═══════════════════════════════════════════════════════════

def would_qualify(candidate: CandidateRecord, gates_to_remove: List[str],
                  remove_pre_gate_block: bool = False) -> bool:
    """
    Determine if a candidate would qualify under a policy with
    the specified gates removed.
    
    Separates:
    - Policy qualification: Would the candidate pass predictive gates?
    - Execution availability: Was it blocked by HALT/strike-policy/etc?
    """
    # Handle pre-gate blocks (Strike Policy, Premium Fetch, Weekend Buffer, etc.)
    if candidate.is_pre_gate_block:
        if remove_pre_gate_block:
            # Pre-gate block lifted. Check if any predictive gates would still block.
            # For candidates where gates ran (all passed), they qualify.
            # For candidates where gates never ran (no gate_results), assume qualify.
            remaining_failed = [g for g in candidate.failed_gates if g not in gates_to_remove]
            return len(remaining_failed) == 0
        else:
            return False

    # Check if the candidate was already approved
    if candidate.decision_action == "EXECUTE":
        return True

    # For rejected candidates: check if all remaining gates pass
    remaining_failed = [g for g in candidate.failed_gates if g not in gates_to_remove]
    return len(remaining_failed) == 0


def run_single_ablation(candidates: List[CandidateRecord],
                         gates_to_remove: List[str],
                         policy_name: str,
                         remove_pre_gate_block: bool = False) -> AblationResult:
    """Run a single ablation scenario."""
    result = AblationResult(
        policy_name=policy_name,
        gates_removed=gates_to_remove,
    )

    def qualifies(c):
        return would_qualify(c, gates_to_remove, remove_pre_gate_block)

    # A. Policy qualification (unconstrained)
    qualified = [c for c in candidates if qualifies(c)]
    q_r_values = [c.realized_r for c in qualified]
    q_metrics = compute_r_metrics(q_r_values)

    result.qualified_count = q_metrics["count"]
    result.qualified_profitable = q_metrics["winners"]
    result.qualified_unprofitable = q_metrics["losers"]
    result.qualified_net_r = q_metrics["net_r"]
    result.qualified_gross_pos_r = q_metrics["gross_pos_r"]
    result.qualified_gross_neg_r = q_metrics["gross_neg_r"]
    result.qualified_avg_r = q_metrics["avg_r"]
    result.qualified_median_r = q_metrics["median_r"]
    result.qualified_win_rate = q_metrics["win_rate"]
    result.qualified_profit_factor = q_metrics["profit_factor"]
    result.qualified_max_ae = q_metrics["max_ae"]
    result.qualified_max_consec_losses = q_metrics["max_consec_losses"]
    result.qualified_r_values = q_r_values

    # B. OMS-constrained sequential execution
    executed = simulate_oms_sequential(candidates, qualifies)
    e_r_values = [c.realized_r for c in executed]
    e_metrics = compute_r_metrics(e_r_values)

    result.executed_count = e_metrics["count"]
    result.executed_profitable = e_metrics["winners"]
    result.executed_unprofitable = e_metrics["losers"]
    result.executed_net_r = e_metrics["net_r"]
    result.executed_gross_pos_r = e_metrics["gross_pos_r"]
    result.executed_gross_neg_r = e_metrics["gross_neg_r"]
    result.executed_avg_r = e_metrics["avg_r"]
    result.executed_median_r = e_metrics["median_r"]
    result.executed_win_rate = e_metrics["win_rate"]
    result.executed_profit_factor = e_metrics["profit_factor"]
    result.executed_max_ae = e_metrics["max_ae"]
    result.executed_max_consec_losses = e_metrics["max_consec_losses"]
    result.executed_r_values = e_r_values

    return result


# ═══════════════════════════════════════════════════════════
# ANALYSIS FUNCTIONS
# ═══════════════════════════════════════════════════════════

def analyze_gate_frequencies(candidates: List[CandidateRecord]) -> dict:
    """Count how often each gate fails across all candidates."""
    gate_fail_counts = Counter()
    gate_sole_blocker_counts = Counter()  # primary blocker (only failing gate)
    gate_contributing_counts = Counter()  # part of multi-gate failure

    for c in candidates:
        if c.is_pre_gate_block:
            gate_fail_counts[PRE_GATE_BLOCKER] += 1
            gate_sole_blocker_counts[PRE_GATE_BLOCKER] += 1
            continue

        if c.decision_action == "EXECUTE":
            continue

        for g in c.failed_gates:
            gate_fail_counts[g] += 1

        if len(c.failed_gates) == 1:
            gate_sole_blocker_counts[c.failed_gates[0]] += 1
        else:
            for g in c.failed_gates:
                gate_contributing_counts[g] += 1

    return {
        "fail_counts": gate_fail_counts,
        "sole_blocker": gate_sole_blocker_counts,
        "contributing": gate_contributing_counts,
    }


def analyze_multi_gate_overlap(candidates: List[CandidateRecord]) -> pd.DataFrame:
    """Build a gate-pair co-failure matrix."""
    active_gates = set()
    for c in candidates:
        active_gates.update(c.failed_gates)
    active_gates = sorted(active_gates)

    matrix = pd.DataFrame(0, index=active_gates, columns=active_gates)

    for c in candidates:
        if len(c.failed_gates) > 1:
            for g1, g2 in itertools.combinations(c.failed_gates, 2):
                matrix.loc[g1, g2] += 1
                matrix.loc[g2, g1] += 1

    # Diagonal = total fail count for that gate
    for c in candidates:
        for g in c.failed_gates:
            matrix.loc[g, g] += 1

    return matrix


def analyze_profitable_fn_deep_dive(candidates: List[CandidateRecord]) -> List[dict]:
    """Deep dive on profitable rejected candidates (False Negatives)."""
    fns = []
    for c in candidates:
        if c.realized_r > 0 and c.decision_action != "EXECUTE":
            blocking_combo = tuple(sorted(c.failed_gates)) if not c.is_pre_gate_block else (PRE_GATE_BLOCKER,)
            fns.append({
                "snapshot_id": c.snapshot_id,
                "date": c.date,
                "time": c.timestamp[11:16],
                "signal": c.signal,
                "realized_r": c.realized_r,
                "confidence": c.raw_conf,
                "outcome": c.outcome,
                "primary_reason": c.primary_reason,
                "blocking_gates": list(blocking_combo),
                "blocking_combo_key": " + ".join(blocking_combo) if blocking_combo else "NONE",
                "n_gates_failed": len(c.failed_gates),
                "mae_r": c.mae_r,
                "mfe_r": c.mfe_r,
            })
    return fns


def run_cumulative_relaxation(candidates: List[CandidateRecord],
                               single_results: List[AblationResult]) -> List[AblationResult]:
    """
    Progressive cumulative relaxation.
    Rank gates by single-ablation net R impact (best first),
    then cumulatively remove them.
    """
    # Rank gates by qualified_net_r improvement (highest first)
    ranked = []
    for r in single_results:
        if r.gates_removed and r.gates_removed[0] != PRE_GATE_BLOCKER:
            ranked.append((r.gates_removed[0], r.qualified_net_r, r.qualified_count))

    # Sort by net R descending (best single-gate ablation first)
    ranked.sort(key=lambda x: x[1], reverse=True)

    cumulative_results = []
    cumulative_gates = []

    for gate_name, _, _ in ranked:
        cumulative_gates.append(gate_name)
        short_names = [GATE_SHORT.get(g, g) for g in cumulative_gates]
        policy_name = f"V2 − {' − '.join(short_names)}"

        result = run_single_ablation(
            candidates, list(cumulative_gates), policy_name,
            remove_pre_gate_block=False
        )
        cumulative_results.append(result)

    # Final: remove everything including pre-gate block
    all_gates = [g for g, _, _ in ranked]
    result = run_single_ablation(
        candidates, all_gates,
        "V2 − ALL gates − UnknownRegime",
        remove_pre_gate_block=True
    )
    cumulative_results.append(result)

    return cumulative_results


# ═══════════════════════════════════════════════════════════
# REPORT GENERATION
# ═══════════════════════════════════════════════════════════

def generate_report(candidates: List[CandidateRecord],
                    gate_freq: dict,
                    single_results: List[AblationResult],
                    cumulative_results: List[AblationResult],
                    overlap_matrix: pd.DataFrame,
                    fn_deep_dive: List[dict]) -> str:
    """Generate the full diagnostic markdown report."""

    lines = []
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Header
    lines.append("> **⚠️ PRELIMINARY DIAGNOSTIC — Based on 6 valid sessions (292 snapshots)**")
    lines.append(">")
    lines.append("> All ablation conclusions are preliminary. Even if an apparently excellent variant is discovered,")
    lines.append("> it requires prospective validation before deployment.")
    lines.append("")
    lines.append("# Zero-Trade Gate-Ablation Diagnostic")
    lines.append("")
    lines.append(f"**Generated**: {now}  ")
    lines.append("**Campaign**: 2026-08-SHADOW-V2  ")
    lines.append("**Code Freeze**: ACTIVE — No production changes  ")
    lines.append(f"**Dataset**: {len(candidates)} candidates across {len(set(c.date for c in candidates))} sessions  ")
    lines.append("")

    # ─── Executive Summary ───────────────────────────────────
    total = len(candidates)
    rejected = sum(1 for c in candidates if c.decision_action != "EXECUTE")
    approved = total - rejected
    profitable = sum(1 for c in candidates if c.realized_r > 0 and c.decision_action != "EXECUTE")
    unprofitable = rejected - profitable
    total_missed_r = sum(c.realized_r for c in candidates if c.realized_r > 0 and c.decision_action != "EXECUTE")
    pre_gate_blocked = sum(1 for c in candidates if c.is_pre_gate_block)
    multi_gate = sum(1 for c in candidates if len(c.failed_gates) > 1 and not c.is_pre_gate_block)

    lines.append("---")
    lines.append("")
    lines.append("## 1. Executive Summary")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("| :--- | ---: |")
    lines.append(f"| Total Candidates | {total} |")
    lines.append(f"| Strategy-Approved | {approved} |")
    lines.append(f"| Rejected | {rejected} |")
    lines.append(f"| Rejection Rate | {rejected/total*100:.1f}% |")
    lines.append(f"| Pre-Gate Blocked (Unknown Regime) | {pre_gate_blocked} |")
    lines.append(f"| Multi-Gate Failures | {multi_gate} ({multi_gate/rejected*100:.0f}% of rejections) |")
    lines.append(f"| Profitable Candidates Missed (FN) | {profitable} |")
    lines.append(f"| Unprofitable Candidates Blocked (TN) | {unprofitable} |")
    lines.append(f"| Total Missed Profit | +{total_missed_r:.2f}R |")
    lines.append(f"| OMS Trades Executed | 0 |")
    lines.append("")

    # Per-session summary
    lines.append("### Per-Session Breakdown")
    lines.append("")
    lines.append("| Date | Candidates | Rejected | FN (Profitable Missed) | TN (Blocked Bad) | Approved |")
    lines.append("| :--- | ---: | ---: | ---: | ---: | ---: |")
    for dt in sorted(set(c.date for c in candidates)):
        dc = [c for c in candidates if c.date == dt]
        dr = [c for c in dc if c.decision_action != "EXECUTE"]
        dfn = [c for c in dr if c.realized_r > 0]
        dtn = [c for c in dr if c.realized_r <= 0]
        dap = [c for c in dc if c.decision_action == "EXECUTE"]
        lines.append(f"| {dt} | {len(dc)} | {len(dr)} | {len(dfn)} | {len(dtn)} | {len(dap)} |")
    lines.append("")

    # ─── Gate Frequency Table ────────────────────────────────
    lines.append("---")
    lines.append("")
    lines.append("## 2. Gate Failure Frequency (All Sessions)")
    lines.append("")
    lines.append("| Gate | Total Fails | Primary Blocker | Contributing Blocker | Fail % |")
    lines.append("| :--- | ---: | ---: | ---: | ---: |")

    fail_counts = gate_freq["fail_counts"]
    sole_counts = gate_freq["sole_blocker"]
    contrib_counts = gate_freq["contributing"]

    for gate in sorted(fail_counts.keys(), key=lambda g: fail_counts[g], reverse=True):
        total_f = fail_counts[gate]
        sole = sole_counts.get(gate, 0)
        contrib = contrib_counts.get(gate, 0)
        pct = total_f / rejected * 100 if rejected > 0 else 0
        lines.append(f"| {gate} | {total_f} | {sole} | {contrib} | {pct:.1f}% |")
    lines.append("")
    lines.append("**Primary Blocker**: The only failing gate (removing it alone would unlock the candidate)  ")
    lines.append("**Contributing Blocker**: One of multiple failing gates (removing it alone would NOT unlock the candidate)  ")
    lines.append("")

    # ─── Single-Gate Ablation ────────────────────────────────
    lines.append("---")
    lines.append("")
    lines.append("## 3. Single-Gate Ablation Analysis")
    lines.append("")
    lines.append("*What would happen if each gate were individually removed from V2?*")
    lines.append("")

    lines.append("### A. Policy Qualification (Unconstrained)")
    lines.append("")
    lines.append("| Policy Variant | Qualified | W | L | Net R | Avg R | Median R | Win% | PF | Max Consec L |")
    lines.append("| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")

    for r in single_results:
        pf_str = f"{r.qualified_profit_factor:.2f}" if r.qualified_profit_factor < 999 else "∞"
        net_str = f"{r.qualified_net_r:+.2f}R" if r.qualified_count > 0 else "—"
        avg_str = f"{r.qualified_avg_r:+.2f}R" if r.qualified_count > 0 else "—"
        med_str = f"{r.qualified_median_r:+.2f}R" if r.qualified_count > 0 else "—"
        win_str = f"{r.qualified_win_rate:.1f}%" if r.qualified_count > 0 else "—"
        lines.append(
            f"| {r.policy_name} | {r.qualified_count} | {r.qualified_profitable} | "
            f"{r.qualified_unprofitable} | {net_str} | {avg_str} | {med_str} | "
            f"{win_str} | {pf_str} | {r.qualified_max_consec_losses} |"
        )
    lines.append("")

    lines.append("### B. OMS-Constrained Sequential Execution")
    lines.append("")
    lines.append("*With max_active_positions = 1 (production constraint)*")
    lines.append("")
    lines.append("| Policy Variant | Executed | W | L | Net R | Avg R | Median R | Win% | PF | Max Consec L |")
    lines.append("| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")

    for r in single_results:
        pf_str = f"{r.executed_profit_factor:.2f}" if r.executed_profit_factor < 999 else "∞"
        net_str = f"{r.executed_net_r:+.2f}R" if r.executed_count > 0 else "—"
        avg_str = f"{r.executed_avg_r:+.2f}R" if r.executed_count > 0 else "—"
        med_str = f"{r.executed_median_r:+.2f}R" if r.executed_count > 0 else "—"
        win_str = f"{r.executed_win_rate:.1f}%" if r.executed_count > 0 else "—"
        lines.append(
            f"| {r.policy_name} | {r.executed_count} | {r.executed_profitable} | "
            f"{r.executed_unprofitable} | {net_str} | {avg_str} | {med_str} | "
            f"{win_str} | {pf_str} | {r.executed_max_consec_losses} |"
        )
    lines.append("")

    # ─── Cumulative Relaxation ───────────────────────────────
    lines.append("---")
    lines.append("")
    lines.append("## 4. Cumulative Relaxation (Progressive Gate Removal)")
    lines.append("")
    lines.append("*Gates removed in order of best single-gate Net R impact (descending).*")
    lines.append("")

    lines.append("### A. Policy Qualification (Unconstrained)")
    lines.append("")
    lines.append("| Policy Variant | Qualified | W | L | Net R | Avg R | Win% | PF | Gross +R | Gross −R |")
    lines.append("| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")

    # Add baseline row
    lines.append("| **Current V2 (frozen)** | 0 | 0 | 0 | — | — | — | — | — | — |")

    for r in cumulative_results:
        pf_str = f"{r.qualified_profit_factor:.2f}" if r.qualified_profit_factor < 999 else "∞"
        net_str = f"{r.qualified_net_r:+.2f}R" if r.qualified_count > 0 else "—"
        avg_str = f"{r.qualified_avg_r:+.2f}R" if r.qualified_count > 0 else "—"
        win_str = f"{r.qualified_win_rate:.1f}%" if r.qualified_count > 0 else "—"
        gpos_str = f"+{r.qualified_gross_pos_r:.2f}R" if r.qualified_count > 0 else "—"
        gneg_str = f"{r.qualified_gross_neg_r:.2f}R" if r.qualified_count > 0 else "—"
        lines.append(
            f"| {r.policy_name} | {r.qualified_count} | {r.qualified_profitable} | "
            f"{r.qualified_unprofitable} | {net_str} | {avg_str} | "
            f"{win_str} | {pf_str} | {gpos_str} | {gneg_str} |"
        )
    lines.append("")

    lines.append("### B. OMS-Constrained Sequential Execution")
    lines.append("")
    lines.append("| Policy Variant | Executed | W | L | Net R | Avg R | Win% | PF | Gross +R | Gross −R |")
    lines.append("| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
    lines.append("| **Current V2 (frozen)** | 0 | 0 | 0 | — | — | — | — | — | — |")

    for r in cumulative_results:
        pf_str = f"{r.executed_profit_factor:.2f}" if r.executed_profit_factor < 999 else "∞"
        net_str = f"{r.executed_net_r:+.2f}R" if r.executed_count > 0 else "—"
        avg_str = f"{r.executed_avg_r:+.2f}R" if r.executed_count > 0 else "—"
        win_str = f"{r.executed_win_rate:.1f}%" if r.executed_count > 0 else "—"
        gpos_str = f"+{r.executed_gross_pos_r:.2f}R" if r.executed_count > 0 else "—"
        gneg_str = f"{r.executed_gross_neg_r:.2f}R" if r.executed_count > 0 else "—"
        lines.append(
            f"| {r.policy_name} | {r.executed_count} | {r.executed_profitable} | "
            f"{r.executed_unprofitable} | {net_str} | {avg_str} | "
            f"{win_str} | {pf_str} | {gpos_str} | {gneg_str} |"
        )
    lines.append("")

    # ─── Profitable FN Deep Dive ─────────────────────────────
    lines.append("---")
    lines.append("")
    lines.append("## 5. Profitable Missed Candidates (False Negatives) — Deep Dive")
    lines.append("")
    total_fn = len(fn_deep_dive)
    total_fn_r = sum(f["realized_r"] for f in fn_deep_dive)
    lines.append(f"**{total_fn} profitable candidates were rejected**, representing **+{total_fn_r:.2f}R** in missed opportunity.")
    lines.append("")

    # Gate-combo aggregation
    combo_counter = Counter()
    combo_r = defaultdict(float)
    combo_count = defaultdict(int)
    for f in fn_deep_dive:
        key = f["blocking_combo_key"]
        combo_counter[key] += 1
        combo_r[key] += f["realized_r"]
        combo_count[key] += 1

    lines.append("### Blocking Gate Combinations (Profitable Candidates Only)")
    lines.append("")
    lines.append("| Gate Combination | Count | Total Missed R | Avg Missed R |")
    lines.append("| :--- | ---: | ---: | ---: |")
    for combo, count in combo_counter.most_common():
        avg_r = combo_r[combo] / count
        lines.append(f"| {combo} | {count} | +{combo_r[combo]:.2f}R | +{avg_r:.2f}R |")
    lines.append("")

    # Individual FN table
    lines.append("### Individual False Negative Candidates")
    lines.append("")
    lines.append("| Date | Time | Signal | R | Conf% | MFE R | MAE R | Blocking Gates | Primary Reason |")
    lines.append("| :--- | :--- | :--- | ---: | ---: | ---: | ---: | :--- | :--- |")
    for f in sorted(fn_deep_dive, key=lambda x: x["realized_r"], reverse=True):
        gates_str = ", ".join(f["blocking_gates"]) if f["blocking_gates"] else "PRE-GATE"
        lines.append(
            f"| {f['date']} | {f['time']} | {f['signal']} | +{f['realized_r']:.2f}R | "
            f"{f['confidence']:.1f} | {f['mfe_r']:.2f} | {f['mae_r']:.2f} | "
            f"{gates_str} | {f['primary_reason'][:50]} |"
        )
    lines.append("")

    # ─── Multi-Gate Overlap Matrix ───────────────────────────
    lines.append("---")
    lines.append("")
    lines.append("## 6. Multi-Gate Overlap Matrix")
    lines.append("")
    lines.append("*Cell (i,j) = number of candidates where both gate i and gate j failed.*  ")
    lines.append("*Diagonal = total failures for that gate.*")
    lines.append("")

    # Only show gates that actually failed
    active_gates = [g for g in overlap_matrix.columns if overlap_matrix.loc[g, g] > 0]
    if active_gates:
        short_headers = [GATE_SHORT.get(g, g[:8]) for g in active_gates]
        header = "| Gate | " + " | ".join(short_headers) + " |"
        sep = "| :--- | " + " | ".join(["---:" for _ in active_gates]) + " |"
        lines.append(header)
        lines.append(sep)
        for g in active_gates:
            row_vals = [str(int(overlap_matrix.loc[g, g2])) for g2 in active_gates]
            lines.append(f"| {GATE_SHORT.get(g, g[:12])} | " + " | ".join(row_vals) + " |")
    lines.append("")

    # ─── Diagnostic Assessment ───────────────────────────────
    lines.append("---")
    lines.append("")
    lines.append("## 7. Diagnostic Assessment")
    lines.append("")

    # Find best single-gate ablation
    best_single = max(single_results, key=lambda r: r.qualified_net_r)
    # Find best cumulative
    best_cumul = max(cumulative_results, key=lambda r: r.executed_net_r) if cumulative_results else None

    lines.append("### Best Single-Gate Ablation")
    lines.append("")
    if best_single.qualified_count > 0:
        lines.append(f"**{best_single.policy_name}**  ")
        lines.append(f"- Unlocks {best_single.qualified_count} candidates  ")
        lines.append(f"- Net R: {best_single.qualified_net_r:+.2f}R  ")
        lines.append(f"- Win Rate: {best_single.qualified_win_rate:.1f}%  ")
        lines.append(f"- Profit Factor: {best_single.qualified_profit_factor:.2f}  ")
    else:
        lines.append("No single-gate removal produces qualifying trades.")
    lines.append("")

    if best_cumul and best_cumul.executed_count > 0:
        lines.append("### Best Cumulative Relaxation (OMS-Constrained)")
        lines.append("")
        lines.append(f"**{best_cumul.policy_name}**  ")
        lines.append(f"- Executable trades: {best_cumul.executed_count}  ")
        lines.append(f"- Net R: {best_cumul.executed_net_r:+.2f}R  ")
        lines.append(f"- Win Rate: {best_cumul.executed_win_rate:.1f}%  ")
        lines.append(f"- Profit Factor: {best_cumul.executed_profit_factor:.2f}  ")
        lines.append("")

    # Classification
    lines.append("### Preliminary Classification")
    lines.append("")

    if best_cumul and best_cumul.executed_net_r > 0 and best_cumul.executed_count >= 5:
        lines.append("> 🟢 **V2 appears too restrictive.** A targeted relaxation produces positive expectancy")
        lines.append("> with meaningful trade frequency. Candidate for V2.1 revision after prospective validation.")
    elif best_cumul and best_cumul.executed_net_r > -2.0 and best_cumul.executed_count >= 3:
        lines.append("> 🟡 **V2 is borderline.** Relaxation increases trades but expectancy is near zero.")
        lines.append("> More sessions needed before concluding. Do not deploy.")
    else:
        lines.append("> 🔴 **V2 may be fundamentally misaligned.** Progressive relaxation produces more trades")
        lines.append("> but increasingly negative expectancy. The signal/selection hypothesis may lack edge.")
    lines.append("")

    lines.append("---")
    lines.append("")

    # ─── Sanity Checks ───────────────────────────────────────
    lines.append("## 8. Sanity Checks")
    lines.append("")

    baseline = single_results[0] if single_results else None
    all_pass = True

    lines.append("| Check | Status |")
    lines.append("| :--- | :--- |")

    # Check 1: Baseline should have 0 qualifying (or match the original approved count)
    if baseline:
        approved_count = sum(1 for c in candidates if c.decision_action == "EXECUTE")
        if baseline.qualified_count == approved_count:
            lines.append(f"| Baseline matches known state ({approved_count} approved) | ✅ PASS |")
        else:
            lines.append(f"| Baseline matches known state (expected {approved_count}, got {baseline.qualified_count}) | ❌ FAIL |")
            all_pass = False

    # Check 2: Monotonicity — ablating a gate should never reduce trades
    for r in single_results[1:]:
        if baseline and r.qualified_count < baseline.qualified_count:
            lines.append(f"| Monotonicity: {r.policy_name} | ❌ FAIL (reduced trades from {baseline.qualified_count} to {r.qualified_count}) |")
            all_pass = False

    if all_pass:
        lines.append("| All monotonicity checks | ✅ PASS |")
    lines.append("")

    lines.append("---")
    lines.append(f"*Report generated at {now} by `tools/gate_ablation_analysis.py`*  ")
    lines.append("*CODE FREEZE: ACTIVE — This is a read-only diagnostic. No production code was modified.*")
    lines.append("")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════

def main():
    print("=" * 60)
    print("🔬 ZERO-TRADE GATE-ABLATION DIAGNOSTIC")
    print("=" * 60)
    print()

    # 1. Load all candidates
    print("Loading candidates from database...")
    candidates = load_all_candidates()
    if not candidates:
        print("No candidates found. Exiting.")
        return

    dates = sorted(set(c.date for c in candidates))
    print(f"Loaded {len(candidates)} candidates across {len(dates)} sessions: {dates}")
    print()

    # 2. Gate frequency analysis
    print("Analyzing gate failure frequencies...")
    gate_freq = analyze_gate_frequencies(candidates)
    print(f"  Active gates with failures: {len(gate_freq['fail_counts'])}")
    for g, count in gate_freq["fail_counts"].most_common(5):
        print(f"    {g}: {count} failures")
    print()

    # 3. Single-gate ablation
    print("Running single-gate ablation analysis...")

    # Baseline (Current V2 — no gates removed)
    baseline = run_single_ablation(candidates, [], "Current V2 (frozen)")
    single_results = [baseline]

    # Ablate each gate that actually failed at least once
    active_failing_gates = [g for g in PREDICTIVE_GATES if g in gate_freq["fail_counts"]]
    for gate in active_failing_gates:
        short = GATE_SHORT.get(gate, gate)
        result = run_single_ablation(candidates, [gate], f"V2 − {short}")
        single_results.append(result)

    # Also test removing the pre-gate block
    result = run_single_ablation(candidates, [], f"V2 − {GATE_SHORT[PRE_GATE_BLOCKER]}",
                                  remove_pre_gate_block=True)
    single_results.append(result)

    for r in single_results:
        print(f"  {r.policy_name}: {r.qualified_count} qualified, {r.executed_count} executed, "
              f"net {r.qualified_net_r:+.2f}R")
    print()

    # Sanity checks
    print("Running sanity checks...")
    for r in single_results[1:]:
        if r.qualified_count < baseline.qualified_count:
            print(f"  ❌ MONOTONICITY VIOLATION: {r.policy_name} has fewer trades than baseline!")
        else:
            print(f"  ✅ {r.policy_name}: {r.qualified_count} >= {baseline.qualified_count} (baseline)")
    print()

    # 4. Cumulative relaxation
    print("Running cumulative relaxation analysis...")
    cumulative_results = run_cumulative_relaxation(candidates, single_results[1:])
    for r in cumulative_results:
        print(f"  {r.policy_name}: {r.qualified_count} qualified, {r.executed_count} executed, "
              f"net {r.qualified_net_r:+.2f}R (qual) / {r.executed_net_r:+.2f}R (exec)")
    print()

    # 5. Multi-gate overlap matrix
    print("Building multi-gate overlap matrix...")
    overlap_matrix = analyze_multi_gate_overlap(candidates)
    print()

    # 6. Profitable FN deep dive
    print("Analyzing profitable missed candidates (False Negatives)...")
    fn_deep_dive = analyze_profitable_fn_deep_dive(candidates)
    print(f"  Found {len(fn_deep_dive)} profitable rejected candidates")
    total_fn_r = sum(f["realized_r"] for f in fn_deep_dive)
    print(f"  Total missed profit: +{total_fn_r:.2f}R")
    print()

    # 7. Generate report
    print("Generating diagnostic report...")
    report = generate_report(
        candidates, gate_freq, single_results,
        cumulative_results, overlap_matrix, fn_deep_dive
    )

    report_path = REPORT_DIR / "gate_ablation_diagnostic.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"\n✅ Report written to: {report_path}")
    print(f"   {len(report.splitlines())} lines, {len(report)} bytes")
    print()

    # Summary
    best_single = max(single_results[1:], key=lambda r: r.qualified_net_r) if len(single_results) > 1 else None
    if best_single:
        print(f"📊 Best single-gate ablation: {best_single.policy_name}")
        print(f"   → {best_single.qualified_count} qualified, Net R: {best_single.qualified_net_r:+.2f}R")

    if cumulative_results:
        best_cumul = max(cumulative_results, key=lambda r: r.executed_net_r)
        print(f"📊 Best cumulative (OMS-constrained): {best_cumul.policy_name}")
        print(f"   → {best_cumul.executed_count} executed, Net R: {best_cumul.executed_net_r:+.2f}R")

    print("\n🔒 CODE FREEZE: ACTIVE — No production code modified.")


if __name__ == "__main__":
    main()
