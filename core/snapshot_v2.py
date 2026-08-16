import sqlite3
import json
import logging
from typing import Optional
from models.snapshot_v2 import DecisionSnapshotV2

logger = logging.getLogger("snapshot_v2")

def _resolve_db_path() -> str:
    import os
    mode = os.getenv("SYSTEM_MODE", "SIMULATION")
    return "data/trading_v4_live.db" if mode != "SIMULATION" else "data/trading_v4_sim.db"

_DB_PATH = _resolve_db_path()

def persist_snapshot_v2(snap: DecisionSnapshotV2, db_path: Optional[str] = None) -> bool:
    """Write the V2 snapshot to SQLite. Non-blocking, non-fatal."""
    db_path = db_path or _DB_PATH
    try:
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        with conn:
            try:
                conn.execute("ALTER TABLE decision_snapshots_v2 ADD COLUMN amd_json TEXT DEFAULT '{}'")
            except Exception:
                pass
            conn.execute(
                """
                INSERT OR IGNORE INTO decision_snapshots_v2 (
                    snapshot_id, timestamp, symbol, expiry, mode, 
                    schema_version, pipeline_version, strategy_version, git_commit, snapshot_hash,
                    parent_snapshot_id, trade_id, shadow_trade_id, experiment_id, replay_run_id,
                    market_json, agents_json, confidence_json, confluence_json, expected_value_json, 
                    structure_json, risk_json, amd_json, gate_results_json, decision_json, execution_json, 
                    event_timeline_json, replay_status_json, outcome_json
                ) VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
                """,
                (
                    snap.metadata.snapshot_id, snap.metadata.timestamp, snap.metadata.symbol, snap.metadata.expiry, snap.metadata.mode,
                    snap.metadata.schema_version, snap.metadata.pipeline_version, snap.metadata.strategy_version, snap.metadata.git_commit, snap.snapshot_hash,
                    snap.metadata.parent_snapshot_id, snap.metadata.trade_id, snap.metadata.shadow_trade_id, snap.metadata.experiment_id, snap.metadata.replay_run_id,
                    json.dumps(snap.market, default=str),
                    json.dumps({k: {"signal": v.signal, "confidence": v.confidence, "details": v.details} for k, v in snap.agents.items()}, default=str),
                    json.dumps(snap.confidence, default=str),
                    json.dumps(snap.confluence, default=str),
                    json.dumps(snap.expected_value, default=str),
                    json.dumps(snap.structure, default=str),
                    json.dumps(snap.risk, default=str),
                    json.dumps(snap.amd, default=str),
                    json.dumps({k: {"passed": v.passed, "actual": v.actual, "required": v.required, "detail": v.detail} for k, v in snap.gate_results.items()}, default=str),
                    json.dumps(snap.decision, default=str),
                    json.dumps(snap.execution, default=str),
                    json.dumps(snap.event_timeline, default=str),
                    json.dumps({"deterministic": snap.replay.deterministic, "missing_fields": snap.replay.missing_fields, "fallback_values": snap.replay.fallback_values}, default=str),
                    json.dumps(snap.outcome.__dict__ if snap.outcome else None, default=str),
                ),
            )
        conn.close()
        return True
    except Exception as e:
        logger.error(f"[SNAPSHOT_V2] Failed to persist {snap.metadata.snapshot_id}: {e}")
        return False
