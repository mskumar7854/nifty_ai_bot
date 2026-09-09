"""
Recovery script for 2026-09-08 historical execution records.

Idempotently recovers the two confirmed simulated trades from September 8:
1. 09:44:10 — BUY PE 23650 @ ₹32.65 (Snapshot: 20260908-094410-954-319A)
2. 09:59:01 — BUY PE 23650 @ ₹32.85 (Snapshot: 20260908-095901-1821-02CC)

Preserves Phase 3 architecture lineage:
- Appends to immutable ExecutedTrade reality ledger (data/immutable_executions.jsonl)
- Indexes into SQLite (orders and trade_outcomes in data/trading_v4_sim.db)
- Guaranteed idempotent: running multiple times never duplicates records.
"""

import os
import sys
import json
import sqlite3
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.execution import ExecutedTrade
from core.telemetry.execution_logger import ExecutionLedgerWriter, EXECUTIONS_LOG


RECORDS = [
    {
        "trade_id": "TRD_20260908_094410_319A",
        "snapshot_id": "20260908-094410-954-319A",
        "intent_id": "INT_20260908_094410_319A",
        "timestamp": "2026-09-08T09:44:10.385499",
        "fill_timestamp": "2026-09-08T09:44:10.461841",
        "symbol": "NIFTY26SEP23650PE",
        "security_id": "SEC_NIFTY_23650_PE",
        "expiry": "2026-09-24",
        "strike": 23650.0,
        "option_type": "PE",
        "side": "BUY",
        "qty": 50,
        "entry_price": 32.65,
        "sl_price": 24.49,
        "target_price": 49.0,
        "confidence": 59.6,
        "grade": "B+",
        "broker_order_id": "SIM_ORD_20260908_094410",
        "broker_sl_order_id": "SIM_SL_20260908_094410",
    },
    {
        "trade_id": "TRD_20260908_095901_02CC",
        "snapshot_id": "20260908-095901-1821-02CC",
        "intent_id": "INT_20260908_095901_02CC",
        "timestamp": "2026-09-08T09:59:01.593177",
        "fill_timestamp": "2026-09-08T09:59:01.661021",
        "symbol": "NIFTY26SEP23650PE",
        "security_id": "SEC_NIFTY_23650_PE",
        "expiry": "2026-09-24",
        "strike": 23650.0,
        "option_type": "PE",
        "side": "BUY",
        "qty": 50,
        "entry_price": 32.85,
        "sl_price": 24.64,
        "target_price": 49.3,
        "confidence": 71.5,
        "grade": "A",
        "broker_order_id": "SIM_ORD_20260908_095901",
        "broker_sl_order_id": "SIM_SL_20260908_095901",
    }
]


def recover_immutable_ledger():
    """Appends to immutable_executions.jsonl if not already present."""
    existing_trade_ids = set()
    if os.path.exists(EXECUTIONS_LOG):
        with open(EXECUTIONS_LOG, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    data = json.loads(line.strip())
                    t_id = data.get("trade_id")
                    if t_id:
                        existing_trade_ids.add(t_id)
                except Exception:
                    pass

    added = 0
    for rec in RECORDS:
        if rec["trade_id"] in existing_trade_ids:
            print(f"[Immutable Ledger] Trade {rec['trade_id']} already exists. Skipping.")
            continue

        executed_trade = ExecutedTrade(
            schema_version=1,
            execution_version=1,
            trade_id=rec["trade_id"],
            decision_snapshot_id=rec["snapshot_id"],
            execution_context="SIMULATION",
            timestamp=rec["timestamp"],
            security_id=rec["security_id"],
            trading_symbol=rec["symbol"],
            expiry=rec["expiry"],
            strike=rec["strike"],
            option_type=rec["option_type"],
            quantity=rec["qty"],
            side=rec["side"],
            entry_price=rec["entry_price"],
            exit_price=0.0,
            fill_timestamp=rec["fill_timestamp"],
            broker_order_id=rec["broker_order_id"],
            initial_sl=rec["sl_price"],
            final_sl=rec["sl_price"],
            target_price=rec["target_price"],
            pnl=0.0,
            realized_r=0.0
        )
        ExecutionLedgerWriter.append_executed_trade(executed_trade)
        print(f"[Immutable Ledger] Appended {rec['trade_id']} to {EXECUTIONS_LOG}")
        added += 1

    print(f"[Immutable Ledger] Done. Added {added} new execution records.")


def recover_sqlite(db_path: str):
    """Idempotently indexes the records into SQLite orders and trade_outcomes."""
    if not os.path.exists(db_path):
        print(f"[SQLite] {db_path} does not exist. Skipping.")
        return

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    for rec in RECORDS:
        # 1. Upsert into orders table (keyed on intent_id UNIQUE)
        cur.execute("""
            INSERT INTO orders (
                signal_id, intent_id, broker_order_id, broker_sl_order_id,
                symbol, side, qty, state, requested_price, avg_fill_price,
                stop_loss_price, filled_qty, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(intent_id) DO UPDATE SET
                state=excluded.state,
                avg_fill_price=excluded.avg_fill_price,
                stop_loss_price=excluded.stop_loss_price,
                filled_qty=excluded.filled_qty,
                updated_at=excluded.updated_at
        """, (
            rec["snapshot_id"],
            rec["intent_id"],
            rec["broker_order_id"],
            rec["broker_sl_order_id"],
            rec["symbol"],
            rec["side"],
            rec["qty"],
            "ENTRY_FILLED",
            rec["entry_price"],
            rec["entry_price"],
            rec["sl_price"],
            rec["qty"],
            rec["fill_timestamp"],
            rec["fill_timestamp"]
        ))

        # 2. Upsert into trade_outcomes table (keyed on trade_id PRIMARY KEY)
        cur.execute("""
            INSERT INTO trade_outcomes (
                trade_id, signal_timestamp, opened_at, closed_at,
                contract, strike, option_type, qty, entry, sl, target,
                exit_price, net_pnl, r_multiple, result, confidence, grade, source
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(trade_id) DO UPDATE SET
                entry=excluded.entry,
                sl=excluded.sl,
                target=excluded.target,
                confidence=excluded.confidence,
                grade=excluded.grade,
                source=excluded.source
        """, (
            rec["trade_id"],
            rec["timestamp"],
            rec["fill_timestamp"],
            None,  # closed_at
            rec["symbol"],
            rec["strike"],
            rec["option_type"],
            rec["qty"],
            rec["entry_price"],
            rec["sl_price"],
            rec["target_price"],
            0.0,   # exit_price
            0.0,   # net_pnl
            0.0,   # r_multiple
            "OPEN", # result
            rec["confidence"],
            rec["grade"],
            "historical_recovery"
        ))

        # 3. Link trade_id into decision_snapshots_v2
        cur.execute("""
            UPDATE decision_snapshots_v2
            SET trade_id = ?
            WHERE snapshot_id = ?
        """, (rec["trade_id"], rec["snapshot_id"]))

    conn.commit()
    conn.close()
    print(f"[SQLite] Successfully indexed records into {db_path}.")


def main():
    print("=== Starting Idempotent Execution Ledger Recovery ===")
    recover_immutable_ledger()
    recover_sqlite("data/trading_v4_sim.db")
    if os.path.exists("data/trading_v4_live.db"):
        recover_sqlite("data/trading_v4_live.db")
    print("=== Recovery Complete ===")


if __name__ == "__main__":
    main()
