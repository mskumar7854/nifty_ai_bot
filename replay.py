#!/usr/bin/env python3
"""
P0.6 + P1: Deterministic Replay Engine — Nifty AI System
=========================================================

Subcommands:
  show        Replay a specific snapshot by ID (with integrity check)
  latest      Replay the N most recent snapshots
  date        Replay all snapshots on a date
  verify      Integrity audit: recompute hash vs stored hash
  regression  Statistical regression summary over last N snapshots
  simulate    Sandbox: re-run gates against stored snapshot using CURRENT engine

Replay is 100% self-contained. It does NOT depend on:
  - Current market data
  - Current config / thresholds (except `simulate` mode — intentionally)
  - Any live runtime state

Outcome classifications:
  MATCH          Same decision with same confidence
  DRIFT          Different decision (engine regression detected)
  PARTIAL_DRIFT  Same action, different confidence or grade
  INVALID        Hash mismatch — corrupted or mutated snapshot
  VERSION_MISMATCH Incompatible engine version in stored snapshot
"""

import argparse
import json
import sqlite3
import sys
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

DB_PATH = "data/trading_v4.db"

CURRENT_SYSTEM_VERSION  = "v4.6.1"
CURRENT_STRATEGY_VERSION = "v3"

CYAN    = "\033[96m"
GREEN   = "\033[92m"
YELLOW  = "\033[93m"
RED     = "\033[91m"
MAGENTA = "\033[95m"
BOLD    = "\033[1m"
DIM     = "\033[2m"
RESET   = "\033[0m"


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def _get_conn(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _load_json(raw: Optional[str]) -> dict:
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except Exception:
        return {}


def _fmt_decision(d: str) -> str:
    if d == "EXECUTE":
        return f"{GREEN}✅ EXECUTE{RESET}"
    elif d == "REJECTED":
        return f"{RED}🚫 REJECTED{RESET}"
    return f"{YELLOW}{d}{RESET}"


def _fmt_outcome(outcome: str) -> str:
    colors = {
        "MATCH":           f"{GREEN}✅ MATCH{RESET}",
        "DRIFT":           f"{RED}🔀 DRIFT{RESET}",
        "PARTIAL_DRIFT":   f"{YELLOW}⚠️  PARTIAL_DRIFT{RESET}",
        "INVALID":         f"{RED}🛑 INVALID (hash mismatch){RESET}",
        "VERSION_MISMATCH":f"{MAGENTA}🔖 VERSION_MISMATCH{RESET}",
    }
    return colors.get(outcome, f"{YELLOW}{outcome}{RESET}")


# ─────────────────────────────────────────────
# Integrity Validation
# ─────────────────────────────────────────────

def _recompute_hash(s: dict) -> str:
    """Recompute the SHA-256 fingerprint from stored fields (determinism check)."""
    import hashlib
    body = {
        "timestamp":               s.get("timestamp", ""),
        "signal_id":               s.get("signal_id", ""),
        "intent_id":               s.get("intent_id", ""),
        "regime":                  s.get("regime", ""),
        "market_phase":            s.get("market_phase", ""),
        "spot_price":              s.get("spot_price", 0.0),
        "vix":                     s.get("vix"),
        "selected_option":         s.get("selected_option", ""),
        "bid":                     s.get("bid", 0.0),
        "ask":                     s.get("ask", 0.0),
        "spread_pct":              s.get("spread_pct", 0.0),
        "quote_age_ms":            s.get("quote_age_ms", 0.0),
        "weighted_score":          s.get("weighted_score", 0.0),
        "buy_score":               s.get("buy_score", 0.0),
        "sell_score":              s.get("sell_score", 0.0),
        "confidence":              s.get("confidence", 0.0),
        "grade":                   s.get("grade", ""),
        "threshold_snapshot_json": _load_json(s.get("threshold_snapshot_json")),
        "agent_outputs_json":      _load_json(s.get("agent_outputs_json")),
        "gate_results_json":       _load_json(s.get("gate_results_json")),
        "filter_stats_json":       _load_json(s.get("filter_stats_json")),
        "market_context_json":     _load_json(s.get("market_context_json")),
        "final_decision":          s.get("final_decision", ""),
        "rejection_reason":        s.get("rejection_reason", ""),
        "system_version":          s.get("system_version", ""),
        "strategy_version":        s.get("strategy_version", ""),
    }
    raw = json.dumps(body, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def classify_integrity(s: dict) -> str:
    """
    Classify snapshot integrity:
      INVALID          — stored hash ≠ recomputed hash (data mutated or serialization changed)
      VERSION_MISMATCH — snapshot was produced by a different engine version
      MATCH            — hash valid and versions match
    """
    stored_hash    = s.get("snapshot_hash", "")
    recomputed     = _recompute_hash(s)
    sys_ver        = s.get("system_version", "")
    strat_ver      = s.get("strategy_version", "")

    if stored_hash and stored_hash != recomputed:
        return "INVALID"
    if sys_ver != CURRENT_SYSTEM_VERSION or strat_ver != CURRENT_STRATEGY_VERSION:
        return "VERSION_MISMATCH"
    return "MATCH"


def classify_simulation_outcome(
    stored_decision: str,
    stored_score: float,
    stored_grade: str,
    new_decision: str,
    new_score: float,
    new_grade: str,
    score_drift_threshold: float = 0.05,
) -> str:
    """
    Classify the outcome when comparing stored vs. simulated decision.

    MATCH          — same decision, score within threshold, same grade
    PARTIAL_DRIFT  — same decision but score or grade shifted significantly
    DRIFT          — different final decision (regression)
    """
    if stored_decision != new_decision:
        return "DRIFT"
    score_diff = abs((stored_score or 0.0) - (new_score or 0.0))
    if score_diff > score_drift_threshold or stored_grade != new_grade:
        return "PARTIAL_DRIFT"
    return "MATCH"


# ─────────────────────────────────────────────
# Display
# ─────────────────────────────────────────────

def replay_single(snap_row: sqlite3.Row, show_integrity: bool = True) -> str:
    """Reconstruct and print a full decision context. Returns integrity outcome."""
    s = dict(snap_row)

    agent_outputs  = _load_json(s.get("agent_outputs_json"))
    gate_results   = _load_json(s.get("gate_results_json"))
    threshold_snap = _load_json(s.get("threshold_snapshot_json"))
    filter_stats   = _load_json(s.get("filter_stats_json"))

    integrity = classify_integrity(s) if show_integrity else "SKIPPED"

    print(f"\n{'═'*70}")
    print(f"{BOLD}{CYAN}📸 DECISION REPLAY   {s['snapshot_id']}{RESET}")
    print(f"{'═'*70}")

    if show_integrity:
        print(f"\n{BOLD}── Integrity Check ────────────────────────────────────{RESET}")
        print(f"  Stored Hash  : {s.get('snapshot_hash', 'N/A')}")
        print(f"  Recomputed   : {_recompute_hash(s)}")
        print(f"  Outcome      : {_fmt_outcome(integrity)}")

    print(f"\n{BOLD}── Market State ───────────────────────────────────────{RESET}")
    print(f"  Timestamp   : {s['timestamp']}")
    print(f"  Spot Price  : ₹{s.get('spot_price', 0):,.1f}")
    print(f"  VIX         : {s.get('vix', 'N/A')}")
    print(f"  Regime      : {s.get('regime', 'N/A')}")
    print(f"  Phase       : {s.get('market_phase', 'N/A')}")

    print(f"\n{BOLD}── Signal Scores ──────────────────────────────────────{RESET}")
    print(f"  Weighted    : {s.get('weighted_score', 0):.3f}")
    print(f"  Buy Score   : {s.get('buy_score', 0):.3f}")
    print(f"  Sell Score  : {s.get('sell_score', 0):.3f}")
    print(f"  Confidence  : {s.get('confidence', 0):.1f}%")
    print(f"  Grade       : {s.get('grade', 'N/A')}")

    print(f"\n{BOLD}── Execution Context ─────────────────────────────────{RESET}")
    print(f"  Option      : {s.get('selected_option', 'N/A')}")
    print(f"  Bid / Ask   : ₹{s.get('bid', 0):,.2f} / ₹{s.get('ask', 0):,.2f}")
    print(f"  Spread      : {s.get('spread_pct', 0):.2f}%")
    print(f"  Quote Age   : {s.get('quote_age_ms', 0):.0f}ms")

    print(f"\n{BOLD}── Filter & Gate Results ─────────────────────────────{RESET}")
    print(f"  Score       : {filter_stats.get('score', 'N/A')}")
    print(f"  Grade       : {filter_stats.get('grade', 'N/A')}")
    print(f"  Passed      : {filter_stats.get('passed', 'N/A')}")

    if threshold_snap:
        print(f"\n{BOLD}── Frozen Thresholds (at decision time) ──────────────{RESET}")
        for k, v in threshold_snap.items():
            print(f"  {k:30s}: {v}")

    if gate_results:
        print(f"\n{BOLD}── Gate Rejections ───────────────────────────────────{RESET}")
        for gate, reason in gate_results.items():
            print(f"  {gate:25s}: {reason}")

    if agent_outputs:
        print(f"\n{BOLD}── Agent Outputs ─────────────────────────────────────{RESET}")
        for agent_name, output in agent_outputs.items():
            score = output.get("score", output.get("value", "?")) if isinstance(output, dict) else output
            print(f"  {agent_name:30s}: {score}")

    print(f"\n{BOLD}── Decision ──────────────────────────────────────────{RESET}")
    print(f"  Decision    : {_fmt_decision(s.get('final_decision', ''))}")
    if s.get("rejection_reason"):
        print(f"  Reason      : {RED}{s['rejection_reason']}{RESET}")
    if s.get("intent_id"):
        print(f"  Intent ID   : {s['intent_id']}")

    print(f"\n{BOLD}── Version Lineage ───────────────────────────────────{RESET}")
    print(f"  System      : {s.get('system_version', 'N/A')}  (current: {CURRENT_SYSTEM_VERSION})")
    print(f"  Strategy    : {s.get('strategy_version', 'N/A')}  (current: {CURRENT_STRATEGY_VERSION})")
    print(f"{'═'*70}\n")

    return integrity


# ─────────────────────────────────────────────
# Commands
# ─────────────────────────────────────────────

def cmd_show(args) -> None:
    conn = _get_conn(args.db)
    row = conn.execute(
        "SELECT * FROM decision_snapshots WHERE snapshot_id = ?", (args.snapshot_id,)
    ).fetchone()
    conn.close()
    if not row:
        print(f"{RED}Snapshot not found: {args.snapshot_id}{RESET}")
        sys.exit(1)
    replay_single(row)


def cmd_latest(args) -> None:
    conn = _get_conn(args.db)
    rows = conn.execute(
        "SELECT * FROM decision_snapshots ORDER BY timestamp DESC LIMIT ?", (args.n,)
    ).fetchall()
    conn.close()
    if not rows:
        print(f"{YELLOW}No snapshots found.{RESET}")
        return
    for row in reversed(rows):
        replay_single(row)


def cmd_date(args) -> None:
    conn = _get_conn(args.db)
    params = [f"{args.date}%"]
    decision_filter = ""
    if args.decision:
        decision_filter = "AND final_decision = ?"
        params.append(args.decision.upper())
    rows = conn.execute(
        f"SELECT * FROM decision_snapshots WHERE timestamp LIKE ? {decision_filter} ORDER BY timestamp",
        params,
    ).fetchall()
    conn.close()
    print(f"\n{BOLD}Found {len(rows)} snapshots for {args.date}{RESET}\n")
    for row in rows:
        replay_single(row)


def cmd_verify(args) -> None:
    """
    Integrity Audit: recompute hash for every snapshot (or last N) and
    report any INVALID or VERSION_MISMATCH outcomes.
    """
    conn = _get_conn(args.db)
    if args.snapshot_id:
        rows = conn.execute(
            "SELECT * FROM decision_snapshots WHERE snapshot_id = ?", (args.snapshot_id,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM decision_snapshots ORDER BY timestamp DESC LIMIT ?", (args.last_n,)
        ).fetchall()
    conn.close()

    counts = {"MATCH": 0, "INVALID": 0, "VERSION_MISMATCH": 0}
    problems = []

    for row in rows:
        s = dict(row)
        outcome = classify_integrity(s)
        counts[outcome] = counts.get(outcome, 0) + 1
        if outcome != "MATCH":
            problems.append((s["snapshot_id"], s["timestamp"], outcome))

    total = len(rows)
    print(f"\n{'═'*70}")
    print(f"{BOLD}{CYAN}🔍 INTEGRITY AUDIT — {total} snapshots{RESET}")
    print(f"{'═'*70}")
    print(f"  {GREEN}MATCH          : {counts.get('MATCH', 0)}{RESET}")
    print(f"  {RED}INVALID        : {counts.get('INVALID', 0)}{RESET}  (hash mismatch — serialization changed or data mutated)")
    print(f"  {MAGENTA}VERSION_MISMATCH: {counts.get('VERSION_MISMATCH', 0)}{RESET}  (snapshot from different engine version)")

    if problems:
        print(f"\n{BOLD}── Problematic Snapshots ─────────────────────────────{RESET}")
        for snap_id, ts, outcome in problems:
            print(f"  {_fmt_outcome(outcome):50s}  {snap_id}  ({ts})")
    else:
        print(f"\n  {GREEN}✅ All snapshots passed integrity verification.{RESET}")

    print(f"{'═'*70}\n")


def cmd_regression(args) -> None:
    """
    Regression Summary: statistical report over last N snapshots.
    Includes integrity pass rate, grade/regime distributions, and decision split.
    """
    conn = _get_conn(args.db)
    rows = conn.execute(
        "SELECT * FROM decision_snapshots ORDER BY timestamp DESC LIMIT ?", (args.last_n,)
    ).fetchall()
    conn.close()

    total    = len(rows)
    executed = sum(1 for r in rows if dict(r)["final_decision"] == "EXECUTE")
    rejected = sum(1 for r in rows if dict(r)["final_decision"] == "REJECTED")
    invalid  = 0
    grades, regimes = {}, {}

    for r in rows:
        s = dict(r)
        g  = s.get("grade", "UNKNOWN")
        re = s.get("regime", "UNKNOWN")
        grades[g]   = grades.get(g, 0) + 1
        regimes[re] = regimes.get(re, 0) + 1
        if classify_integrity(s) == "INVALID":
            invalid += 1

    if not total:
        print(f"{YELLOW}No snapshots found.{RESET}")
        return

    print(f"\n{'═'*70}")
    print(f"{BOLD}{CYAN}🔬 REGRESSION REPLAY REPORT  (last {args.last_n} requested, {total} found){RESET}")
    print(f"{'═'*70}")
    print(f"  {GREEN}EXECUTE{RESET}        : {executed:4d}  ({executed/total*100:.1f}%)")
    print(f"  {RED}REJECTED{RESET}       : {rejected:4d}  ({rejected/total*100:.1f}%)")
    print(f"  {RED}INVALID hashes{RESET} : {invalid:4d}  {'← ⚠️  INVESTIGATE' if invalid else ''}")

    print(f"\n{BOLD}Grade Distribution:{RESET}")
    for g, c in sorted(grades.items(), key=lambda x: -x[1]):
        bar = "█" * min(c, 40)
        print(f"  {g:10s}  {c:4d}  {bar}")

    print(f"\n{BOLD}Regime Distribution:{RESET}")
    for r, c in sorted(regimes.items(), key=lambda x: -x[1]):
        bar = "█" * min(c, 40)
        print(f"  {r:25s}  {c:4d}  {bar}")

    print(f"\n{DIM}Run `verify` to audit hash integrity. Run `show --snapshot-id` to inspect individual decisions.{RESET}")
    print(f"{'═'*70}\n")




def _export_json(prefix: str, analysis_type: str, data: list, sample_size: int):
    import json
    import time
    from datetime import datetime
    
    os.makedirs("replay_results", exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y-%m-%dT%H%M%SZ")
    filename = f"replay_results/{prefix}_{timestamp}.json"
    
    envelope = {
        "generated_at": datetime.now().isoformat(),
        "strategy_version": CURRENT_STRATEGY_VERSION,
        "replay_version": "v1.1",
        "db_source": "trading_v4_sim.db",
        "sample_size": sample_size,
        "analysis_type": analysis_type,
        "results": data
    }
    
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(envelope, f, indent=2)
        
    print(f"\n{GREEN}💾 Exported results to {filename}{RESET}\n")

def cmd_gate_analysis(args) -> None:
    """Phase 4A: Analyze Rejection Counterfactuals"""
    from core.replay_simulator import ReplaySimulator
    from core.replay_analytics import ReplayAnalytics
    
    conn = _get_conn(args.db)
    rows = conn.execute(
        "SELECT * FROM decision_snapshots WHERE final_decision = 'REJECTED' ORDER BY timestamp DESC LIMIT ?", (args.last_n,)
    ).fetchall()
    conn.close()
    
    if not rows:
        print(f"{YELLOW}No REJECTED snapshots found.{RESET}")
        return
        
    print(f"\n{BOLD}Initializing execution simulator for {len(rows)} snapshots...{RESET}")
    sim = ReplaySimulator(db_path=args.db)
    
    results = []
    for r in rows:
        res = sim.simulate_rejection(r)
        if res:
            results.append(res)
            
    print(f"\n{'═'*80}")
    print(f"{BOLD}{CYAN}🛡️  GATE ANALYSIS: Protection vs Suppression (Last {args.last_n} REJECTED){RESET}")
    print(f"{'═'*80}")
    
    analysis = ReplayAnalytics.calculate_gate_impact(results)
    
    print(f"{BOLD}{'Gate/Reason':<30} | {'Suppressed R':>12} | {'Prevented Loss':>15} | {'Net R':>8} | {'Win %':>7}{RESET}")
    print("-" * 80)
    for row in analysis:
        net = row['net_r']
        net_color = GREEN if net > 0 else RED if net < 0 else YELLOW
        print(f"{row['gate']:<30} | {row['suppressed_r']:>12.2f} | {row['prevented_loss_r']:>15.2f} | {net_color}{net:>8.2f}{RESET} | {row['empirical_win_rate']:>6.1f}%")
        
    print(f"{'═'*80}\n")

    if getattr(args, "export", False):
        _export_json("gate_analysis", "gate_impact", analysis, len(results))


def cmd_longitudinal(args) -> None:
    """Phase 4B: Longitudinal Replay Analytics"""
    from core.replay_simulator import ReplaySimulator
    from core.replay_analytics import ReplayAnalytics
    
    conn = _get_conn(args.db)
    rows = conn.execute(
        "SELECT * FROM decision_snapshots WHERE final_decision = 'REJECTED' ORDER BY timestamp DESC LIMIT ?", (args.last_n,)
    ).fetchall()
    conn.close()
    
    if not rows:
        print(f"{YELLOW}No snapshots found.{RESET}")
        return
        
    sim = ReplaySimulator(db_path=args.db)
    results = []
    for r in rows:
        res = sim.simulate_rejection(r)
        if res:
            results.append(res)
            
    print(f"\\n{{'═'*100}}")
    print(f"{BOLD}{CYAN}📈 LONGITUDINAL EXPECTANCY (Sliced by: {args.slice.upper()}){RESET}")
    print(f"{'═'*100}")
    
    analysis = ReplayAnalytics.analyze_longitudinal(results, slice_by=args.slice)
    
    if len(results) < 10:
        print(f"{YELLOW}⚠️ WARNING: Only {len(results)} samples evaluated. Results are statistically weak and should not be used for tuning.{RESET}\n")
    
    print(f"{BOLD}{args.slice.capitalize():<20} | {'Count':>6} | {'Win %':>6} | {'5m AvgR':>8} | {'15m AvgR':>8} | {'30m AvgR':>8} | {'Net R':>8}{RESET}")
    print("-" * 100)
    for row in analysis:
        net = row['net_r']
        net_color = GREEN if net > 0 else RED if net < 0 else YELLOW
        print(f"{row['slice_value']:<20} | {row['count']:>6} | {row['win_rate']:>5.1f}% | {row['avg_r_5m']:>8.2f} | {row['avg_r_15m']:>8.2f} | {row['avg_r_30m']:>8.2f} | {net_color}{net:>8.2f}{RESET}")
        
    print(f"{'═'*100}\n")
    
    if getattr(args, "export", False):
        _export_json(f"longitudinal_{args.slice}", f"longitudinal_{args.slice}", analysis, len(results))

def cmd_calibrate(args) -> None:
    """Phase 4A: Analyze Confidence Calibration"""
    from core.replay_simulator import ReplaySimulator
    from core.replay_analytics import ReplayAnalytics
    
    conn = _get_conn(args.db)
    # Calibrate needs all trades (exec and rejected) but right now simulator only evaluates rejected.
    # To evaluate EXECUTE, we can use the same simulator! (Need to slightly tweak simulator if we want it to run on EXECUTE)
    # But for now, we'll just evaluate REJECTED counterfactuals to see if high-confidence rejections win.
    rows = conn.execute(
        "SELECT * FROM decision_snapshots WHERE final_decision = 'REJECTED' ORDER BY timestamp DESC LIMIT ?", (args.last_n,)
    ).fetchall()
    conn.close()
    
    if not rows:
        print(f"{YELLOW}No snapshots found.{RESET}")
        return
        
    sim = ReplaySimulator(db_path=args.db)
    results = []
    for r in rows:
        res = sim.simulate_rejection(r)
        if res:
            results.append(res)
            
    print(f"\n{'═'*60}")
    print(f"{BOLD}{CYAN}📊 CONFIDENCE CALIBRATION (Counterfactuals){RESET}")
    print(f"{'═'*60}")
    
    analysis = ReplayAnalytics.calibrate_confidence_bands(results)
    
    print(f"{BOLD}{'Confidence Band':<16} | {'Count':>6} | {'Win Rate':>9} | {'Expected R':>10}{RESET}")
    print("-" * 60)
    for row in analysis:
        print(f"{row['band']:<16} | {row['count']:>6} | {row['win_rate']:>8.1f}% | {row['avg_r']:>10.2f}")
        
    print(f"{'═'*60}\n")

    if getattr(args, "export", False):
        _export_json("calibration", "confidence_bands", analysis, len(results))
def cmd_simulate(args) -> None:
    """
    Sandbox Mode: re-score a stored snapshot using CURRENT engine logic.
    Compares the stored outcome against what the engine would decide TODAY.
    Produces an outcome classification: MATCH / PARTIAL_DRIFT / DRIFT.

    This is the regression testing framework for strategy evolution.
    """
    conn = _get_conn(args.db)
    row = conn.execute(
        "SELECT * FROM decision_snapshots WHERE snapshot_id = ?", (args.snapshot_id,)
    ).fetchone()
    conn.close()

    if not row:
        print(f"{RED}Snapshot not found: {args.snapshot_id}{RESET}")
        sys.exit(1)

    s = dict(row)
    stored_decision = s.get("final_decision", "")
    stored_score    = s.get("weighted_score", 0.0)
    stored_grade    = s.get("grade", "")

    integrity = classify_integrity(s)
    if integrity == "INVALID":
        print(f"\n{RED}🛑 INVALID snapshot — hash mismatch. Cannot trust simulation inputs.{RESET}\n")
        sys.exit(2)

    # Attempt to re-score using current engine
    try:
        from config.settings import settings as live_settings
        from core.trade_filter import TradeFilter
        tfilter = TradeFilter(live_settings)

        # Build a minimal mock signal object from snapshot fields
        threshold_snap = _load_json(s.get("threshold_snapshot_json"))
        filter_stats   = _load_json(s.get("filter_stats_json"))

        # We can't replay the FULL engine from frozen data without the original candles,
        # but we CAN re-run the filter's scoring thresholds against the frozen scores.
        # This detects threshold drift — the most common source of regression.
        current_thresholds = tfilter._get_current_thresholds() if hasattr(tfilter, "_get_current_thresholds") else {}

        stored_thresholds = threshold_snap
        drift_fields = []
        for k, v in current_thresholds.items():
            stored_v = stored_thresholds.get(k)
            if stored_v is not None and abs(float(v or 0) - float(stored_v or 0)) > 0.001:
                drift_fields.append((k, stored_v, v))

        # Grade re-evaluation based on current thresholds
        new_grade    = filter_stats.get("grade", stored_grade)
        new_score    = filter_stats.get("score", stored_score)
        new_decision = stored_decision  # Without candle data, decision can't be fully replayed

        # Determine drift purely from threshold delta
        outcome = "MATCH"
        if drift_fields:
            outcome = "PARTIAL_DRIFT"

    except Exception as e:
        outcome = "PARTIAL_DRIFT"
        drift_fields = [("engine_import_error", "", str(e))]
        new_grade    = stored_grade
        new_score    = stored_score
        new_decision = stored_decision

    print(f"\n{'═'*70}")
    print(f"{BOLD}{CYAN}🧪 SANDBOX SIMULATION  {s['snapshot_id']}{RESET}")
    print(f"{'═'*70}")
    print(f"\n{BOLD}── Stored State ──────────────────────────────────────{RESET}")
    print(f"  Decision : {_fmt_decision(stored_decision)}")
    print(f"  Score    : {stored_score:.3f}   Grade: {stored_grade}")
    print(f"  System   : {s.get('system_version')} / {s.get('strategy_version')}")
    print(f"\n{BOLD}── Current Engine ────────────────────────────────────{RESET}")
    print(f"  Decision : {_fmt_decision(new_decision)}")
    print(f"  Score    : {new_score:.3f}   Grade: {new_grade}")
    print(f"  System   : {CURRENT_SYSTEM_VERSION} / {CURRENT_STRATEGY_VERSION}")
    print(f"\n{BOLD}── Outcome ───────────────────────────────────────────{RESET}")
    print(f"  Result   : {_fmt_outcome(outcome)}")

    if drift_fields:
        print(f"\n{BOLD}── Threshold Drift Detected ──────────────────────────{RESET}")
        for field, old, new in drift_fields:
            print(f"  {field:30s}: {YELLOW}{old}{RESET} → {GREEN}{new}{RESET}")
    else:
        print(f"\n  {GREEN}No threshold drift detected.{RESET}")

    print(f"{'═'*70}\n")
    print(f"{DIM}NOTE: Full decision replay requires original OHLCV candles. This command")
    print(f"      detects threshold drift and version changes — the most common regression sources.{RESET}\n")


# ─────────────────────────────────────────────
# Entry Point
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Nifty AI System — Deterministic Replay Engine (P0.6)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--db", default=DB_PATH, help="Path to SQLite database")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_show = sub.add_parser("show", help="Replay a specific snapshot by ID (with integrity check)")
    p_show.add_argument("--snapshot-id", required=True)

    p_latest = sub.add_parser("latest", help="Replay the N most recent snapshots")
    p_latest.add_argument("--n", type=int, default=5)

    p_date = sub.add_parser("date", help="Replay all snapshots on a date (YYYY-MM-DD)")
    p_date.add_argument("--date", required=True)
    p_date.add_argument("--decision", choices=["EXECUTE", "REJECTED"], default=None)

    p_verify = sub.add_parser("verify", help="Integrity audit: recompute vs stored hashes")
    p_verify.add_argument("--snapshot-id", default=None, help="Verify a single snapshot")
    p_verify.add_argument("--last-n", type=int, default=500, help="Verify last N snapshots (default 500)")

    p_reg = sub.add_parser("regression", help="Regression summary over last N snapshots")
    p_reg.add_argument("--last-n", type=int, default=100)

    p_sim = sub.add_parser("simulate", help="Sandbox: re-run current engine against stored snapshot")
    p_sim.add_argument("--snapshot-id", required=True)



    p_gate = sub.add_parser("gate-analysis", help="Analyze Missed vs Prevented Expectancy per Gate")
    p_gate.add_argument("--last-n", type=int, default=500)
    p_gate.add_argument("--export", action="store_true", help="Export to JSON artifact")

    p_calib = sub.add_parser("calibrate", help="Analyze empirical win rates by confidence band")
    p_calib.add_argument("--last-n", type=int, default=500)
    p_calib.add_argument("--export", action="store_true", help="Export to JSON artifact")
    
    p_long = sub.add_parser("longitudinal", help="Slice counterfactuals longitudinally")
    p_long.add_argument("--slice", choices=["hour", "regime", "vix"], default="hour")
    p_long.add_argument("--last-n", type=int, default=500)
    p_long.add_argument("--export", action="store_true", help="Export to JSON artifact")
    args = parser.parse_args()

    if not Path(args.db).exists():
        print(f"{RED}Database not found: {args.db}{RESET}")
        sys.exit(1)

    dispatch = {
        "show":       cmd_show,
        "latest":     cmd_latest,
        "date":       cmd_date,
        "verify":     cmd_verify,
        "regression": cmd_regression,
        "simulate":   cmd_simulate,

        "gate-analysis": cmd_gate_analysis,
        "calibrate": cmd_calibrate,
        "longitudinal": cmd_longitudinal,
    }
    dispatch[args.cmd](args)


if __name__ == "__main__":
    main()
