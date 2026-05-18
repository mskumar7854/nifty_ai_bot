"""
P0.6: Deterministic Decision Snapshot Engine.

Captures the COMPLETE market + decision state BEFORE any execution occurs.
This is the foundation for:
  - Deterministic replay
  - Regression testing
  - Version drift detection
  - ML training data (future)

CRITICAL DESIGN RULE:
  Snapshot must be written BEFORE OMS intent creation.
  Ordering: market_state → decision_snapshot → OMS intent → execution

All snapshots are self-contained. Replay must NEVER depend on:
  - current market data
  - current config
  - current thresholds
  - any live state
"""

import json
import hashlib
import sqlite3
import logging
from datetime import datetime
from typing import Any, Dict, Optional

logger = logging.getLogger("snapshot")

SYSTEM_VERSION = "v4.6.1"
STRATEGY_VERSION = "v3"

DB_PATH = "data/trading_v4.db"


def _normalize_for_hash(d: dict) -> str:
    """Produce a stable, canonical JSON string for SHA-256 fingerprinting."""
    return json.dumps(d, sort_keys=True, separators=(",", ":"), default=str)


def compute_snapshot_hash(snapshot_body: dict) -> str:
    """SHA-256 fingerprint of the normalized snapshot body."""
    raw = _normalize_for_hash(snapshot_body)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def build_snapshot(
    signal,
    snapshot,
    filter_result,
    agent_outputs: dict,
    gate_results: dict,
    final_decision: str,
    rejection_reason: str = "",
    intent_id: str = "",
    quote=None,
    instrument: dict = None,
    options_context: dict = None,
) -> dict:
    """
    Construct a self-contained, immutable decision snapshot.
    This function must be called with the state AT THE MOMENT OF DECISION.
    """
    ts = datetime.now().isoformat()
    snapshot_id = f"SNAP_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')[:20]}"

    quote_bid = getattr(quote, "bid", 0.0) if quote else 0.0
    quote_ask = getattr(quote, "ask", 0.0) if quote else 0.0
    spread_pct = getattr(quote, "spread_pct", 0.0) if quote else 0.0
    quote_age_ms = (
        (datetime.now() - getattr(quote, "timestamp", datetime.now())).total_seconds() * 1000
        if quote else 0.0
    )

    # ── Threshold freeze: capture all live thresholds at this exact moment ──
    # If future tuning changes thresholds, replay uses the frozen values, not new ones.
    threshold_snapshot = {
        "confidence_min": getattr(filter_result, "confidence_min", None),
        "grade": getattr(filter_result, "grade", "UNKNOWN"),
        "final_score": getattr(filter_result, "final_score", 0),
        "filters_passed": getattr(filter_result, "filters_passed", 0),
        "filters_total": getattr(filter_result, "filters_total", 0),
        "rejection_reason": getattr(filter_result, "rejection_reason", "") if hasattr(filter_result, "rejection_reason") else "",
    }

    market_context = {
        "spot_price": getattr(snapshot, "price", 0.0),
        "vix": getattr(snapshot, "vix", None),
        "atr": getattr(snapshot, "atr", None),
        "oi_bias": getattr(snapshot, "oi_bias", None),
        "options_context": options_context or {},
    }

    body = {
        "timestamp": ts,
        "signal_id": str(getattr(signal, "id", "")),
        "intent_id": intent_id,
        "regime": signal.regime.value if hasattr(signal.regime, "value") else str(getattr(signal, "regime", "")),
        "market_phase": str(getattr(signal, "market_phase", "")),
        "spot_price": getattr(snapshot, "price", 0.0),
        "vix": getattr(snapshot, "vix", None),
        "selected_option": instrument.get("symbol", "") if instrument else "",
        "bid": quote_bid,
        "ask": quote_ask,
        "spread_pct": spread_pct,
        "quote_age_ms": quote_age_ms,
        "weighted_score": getattr(signal, "weighted_score", 0.0),
        "buy_score": getattr(signal, "buy_score", 0.0),
        "sell_score": getattr(signal, "sell_score", 0.0),
        "confidence": getattr(signal, "confidence", 0.0),
        "grade": signal.grade.value if hasattr(signal.grade, "value") else str(getattr(signal, "grade", "")),
        "threshold_snapshot_json": threshold_snapshot,
        "agent_outputs_json": agent_outputs,
        "gate_results_json": gate_results,
        "filter_stats_json": {
            "passed": getattr(filter_result, "passed", False),
            "grade": getattr(filter_result, "grade", "UNKNOWN"),
            "score": getattr(filter_result, "final_score", 0),
        },
        "market_context_json": market_context,
        "final_decision": final_decision,
        "rejection_reason": rejection_reason,
        "system_version": SYSTEM_VERSION,
        "strategy_version": STRATEGY_VERSION,
    }

    snapshot_hash = compute_snapshot_hash(body)

    return {
        "snapshot_id": snapshot_id,
        "snapshot_hash": snapshot_hash,
        **body,
    }


def persist_snapshot(snap: dict, db_path: str = DB_PATH) -> bool:
    """Write the snapshot to SQLite. Non-blocking, non-fatal."""
    try:
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")  # Performance: snapshots can afford async durability
        with conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO decision_snapshots (
                    snapshot_id, snapshot_hash, timestamp,
                    signal_id, intent_id,
                    regime, market_phase, spot_price, vix,
                    selected_option, bid, ask, spread_pct, quote_age_ms,
                    weighted_score, buy_score, sell_score, confidence, grade,
                    threshold_snapshot_json, agent_outputs_json, gate_results_json,
                    filter_stats_json, market_context_json,
                    final_decision, rejection_reason,
                    system_version, strategy_version
                ) VALUES (
                    ?, ?, ?,
                    ?, ?,
                    ?, ?, ?, ?,
                    ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?,
                    ?, ?, ?,
                    ?, ?,
                    ?, ?,
                    ?, ?
                )
                """,
                (
                    snap["snapshot_id"], snap["snapshot_hash"], snap["timestamp"],
                    snap["signal_id"], snap["intent_id"],
                    snap["regime"], snap["market_phase"], snap["spot_price"], snap["vix"],
                    snap["selected_option"], snap["bid"], snap["ask"],
                    snap["spread_pct"], snap["quote_age_ms"],
                    snap["weighted_score"], snap["buy_score"], snap["sell_score"],
                    snap["confidence"], snap["grade"],
                    json.dumps(snap["threshold_snapshot_json"], default=str),
                    json.dumps(snap["agent_outputs_json"], default=str),
                    json.dumps(snap["gate_results_json"], default=str),
                    json.dumps(snap["filter_stats_json"], default=str),
                    json.dumps(snap["market_context_json"], default=str),
                    snap["final_decision"], snap["rejection_reason"],
                    snap["system_version"], snap["strategy_version"],
                ),
            )
        conn.close()
        return True
    except Exception as e:
        logger.error(f"[SNAPSHOT] Failed to persist {snap.get('snapshot_id', '?')}: {e}")
        return False
