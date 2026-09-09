"""
============================================
📦 DATABASE MANAGER
Asynchronous SQLite implementation to persist
system memory and trade history without
blocking the sub-50ms trading loop.
============================================
"""

import json
import aiosqlite
import logging
from dataclasses import asdict, is_dataclass
from datetime import datetime, date
from enum import Enum

logger = logging.getLogger("db_manager")


class _SafeEncoder(json.JSONEncoder):
    """Handles numpy, dataclass, Enum, and datetime objects that appear in
    signal metadata and trade agent dicts.  Falls back to str() so
    json.dumps() *never* crashes — data integrity over prettiness."""

    def default(self, obj):
        # numpy scalar types (np.bool_, np.int64, np.float64, etc.)
        try:
            import numpy as np
            if isinstance(obj, np.bool_):
                return bool(obj)
            if isinstance(obj, np.integer):
                return int(obj)
            if isinstance(obj, np.floating):
                return float(obj)
            if isinstance(obj, np.ndarray):
                return obj.tolist()
        except ImportError:
            pass

        # dataclass instances (e.g. OptionQuote, ExecutionPolicy)
        if is_dataclass(obj) and not isinstance(obj, type):
            return asdict(obj)

        # Enum members
        if isinstance(obj, Enum):
            return obj.value

        # datetime / date
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()

        # Absolute last resort — never crash
        try:
            return super().default(obj)
        except TypeError:
            return str(obj)

def get_db_path(override_path: str = None) -> str:
    """Resolve the canonical SQLite database path."""
    import os
    if override_path and override_path != "data/trading_v4.db":
        return override_path
    env_override = os.getenv("NIFTY_DB_PATH")
    if env_override:
        return env_override
    mode = os.getenv("SYSTEM_MODE", "SIMULATION")
    return "data/trading_v4_live.db" if mode != "SIMULATION" else "data/trading_v4_sim.db"


class DBManager:
    def __init__(self, db_path=None):
        self.db_path = get_db_path(db_path)

    async def initialize(self):
        """Creates tables if they don't exist. Run on startup."""
        async with aiosqlite.connect(self.db_path) as db:
            # 1. Trade history (memory context)
            await db.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                result TEXT,
                pnl REAL,
                regime TEXT,
                confidence REAL,
                signal_type TEXT,
                agents TEXT,
                pev REAL,
                slippage REAL
            )
            """)
            
            # 2. Interactive signal queue (v4.6.1 Hardened)
            await db.execute("""
            CREATE TABLE IF NOT EXISTS signals (
                id TEXT PRIMARY KEY,
                symbol TEXT,
                signal_type TEXT,
                direction TEXT,
                entry_price REAL,
                stop_loss REAL,
                target_1 REAL,
                confidence REAL,
                status TEXT,
                execution_status TEXT DEFAULT 'pending',
                created_at REAL NOT NULL,
                updated_at REAL,
                queue_position INTEGER,
                metadata TEXT
            )
            """)
            
            # 3. OMS Orders Table (P0.3)
            await db.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                signal_id TEXT NOT NULL,
                intent_id TEXT NOT NULL UNIQUE,
                broker_order_id TEXT,
                broker_sl_order_id TEXT,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                qty INTEGER NOT NULL,
                state TEXT NOT NULL,
                requested_price REAL,
                avg_fill_price REAL,
                stop_loss_price REAL,
                target_price REAL,
                strike REAL,
                expiry TEXT,
                option_type TEXT,
                filled_qty INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """)

            # Startup Schema Verification: Ensure contract execution columns exist
            for col, col_type in [("strike", "REAL"), ("expiry", "TEXT"), ("option_type", "TEXT"), ("target_price", "REAL")]:
                try:
                    await db.execute(f"ALTER TABLE orders ADD COLUMN {col} {col_type}")
                except Exception:
                    pass

            # 4. OMS Order Events (P0.3) - Append-only audit log
            await db.execute("""
            CREATE TABLE IF NOT EXISTS order_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                intent_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                old_state TEXT,
                new_state TEXT,
                payload_json TEXT,
                created_at TEXT NOT NULL
            )
            """)

            # 5. OMS Position Snapshots (P0.3)
            await db.execute("""
            CREATE TABLE IF NOT EXISTS position_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                signal_id TEXT,
                symbol TEXT,
                qty INTEGER,
                unrealized_pnl REAL,
                realized_pnl REAL,
                stop_loss REAL,
                snapshot_time TEXT NOT NULL
            )
            """)
            # 6. Trade Economics (P0.5) - Exact costs and execution drift
            await db.execute("""
            CREATE TABLE IF NOT EXISTS trade_economics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                intent_id TEXT NOT NULL UNIQUE,
                gross_pnl REAL,
                net_pnl REAL,
                
                spread_cost REAL,
                slippage_cost REAL,
                
                brokerage REAL,
                stt REAL,
                gst REAL,
                sebi_charges REAL,
                stamp_duty REAL,
                
                holding_seconds REAL,
                mfe REAL,
                mae REAL,
                
                realized_r_multiple REAL,
                
                entry_bid REAL,
                entry_ask REAL,
                entry_fill REAL,
                exit_bid REAL,
                exit_ask REAL,
                exit_fill REAL,
                
                spread_pct_entry REAL,
                spread_pct_exit REAL,
                quote_age_ms REAL,
                slippage_entry REAL,
                slippage_exit REAL
            )
            """)
            
            # Dynamic schema migration for existing DBs
            columns = [
                ("execution_status", "TEXT DEFAULT 'pending'"),
                ("updated_at", "REAL"),
                ("queue_position", "INTEGER"),
                ("metadata", "TEXT")
            ]
            for col_name, col_type in columns:
                try:
                    await db.execute(f"ALTER TABLE signals ADD COLUMN {col_name} {col_type}")
                    logger.info(f"Migration: Added column {col_name} to signals table.")
                except Exception:
                    pass # Column already exists
            
            try:
                await db.execute("ALTER TABLE trades ADD COLUMN pev REAL")
                await db.execute("ALTER TABLE trades ADD COLUMN slippage REAL")
                logger.info("Migration: Added pev and slippage to trades table.")
            except Exception:
                pass
                
            # 7. Decision Snapshots (P0.6) - Full cycle truth archive for deterministic replay
            await db.execute("""
            CREATE TABLE IF NOT EXISTS decision_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                snapshot_id TEXT NOT NULL UNIQUE,
                snapshot_hash TEXT NOT NULL,
                timestamp TEXT NOT NULL,

                signal_id TEXT,
                intent_id TEXT,

                regime TEXT,
                market_phase TEXT,
                spot_price REAL,
                vix REAL,

                selected_option TEXT,
                bid REAL,
                ask REAL,
                spread_pct REAL,
                quote_age_ms REAL,

                weighted_score REAL,
                buy_score REAL,
                sell_score REAL,
                confidence REAL,
                grade TEXT,

                threshold_snapshot_json TEXT,
                agent_outputs_json TEXT,
                gate_results_json TEXT,
                filter_stats_json TEXT,
                market_context_json TEXT,

                final_decision TEXT,
                rejection_reason TEXT,

                system_version TEXT DEFAULT 'v4.6.1',
                strategy_version TEXT DEFAULT 'v3'
            )
            """)

            # 8. Decision Snapshots V2 (P2.0) - Deterministic Replay Foundation
            await db.execute("""
            CREATE TABLE IF NOT EXISTS decision_snapshots_v2 (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                snapshot_id TEXT NOT NULL UNIQUE,
                timestamp TEXT NOT NULL,
                symbol TEXT,
                expiry TEXT,
                mode TEXT,
                schema_version TEXT,
                pipeline_version TEXT,
                strategy_version TEXT,
                git_commit TEXT,
                parent_snapshot_id TEXT,
                trade_id TEXT,
                shadow_trade_id TEXT,
                experiment_id TEXT,
                replay_run_id TEXT,
                market_json TEXT,
                snapshot_hash TEXT NOT NULL,
                
                agents_json TEXT,
                confidence_json TEXT,
                confluence_json TEXT,
                expected_value_json TEXT,
                structure_json TEXT,
                risk_json TEXT,
                gate_results_json TEXT,
                decision_json TEXT,
                execution_json TEXT,
                event_timeline_json TEXT,
                replay_status_json TEXT,
                outcome_json TEXT
            )
            """)

            # 9. Persistent Trade Outcomes (P0)
            await db.execute("""
            CREATE TABLE IF NOT EXISTS trade_outcomes (
                trade_id TEXT PRIMARY KEY,
                signal_timestamp TEXT,
                opened_at TEXT,
                closed_at TEXT,
                contract TEXT,
                strike REAL,
                option_type TEXT,
                qty INTEGER,
                entry REAL,
                sl REAL,
                target REAL,
                exit_price REAL,
                net_pnl REAL,
                r_multiple REAL,
                result TEXT,
                confidence REAL,
                grade TEXT,
                source TEXT
            )
            """)

            await db.commit()
        logger.info("📦 SQLite Database connected and verified (v4.6.1 Hardened).")

    async def save_signal(self, signal):
        """Persists a new signal to disk for recovery."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    INSERT OR REPLACE INTO signals 
                    (id, symbol, signal_type, direction, entry_price, stop_loss, target_1, 
                     confidence, status, execution_status, created_at, updated_at, 
                     queue_position, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    str(signal.id),
                    getattr(signal, "symbol", "NIFTY"),
                    signal.signal_type.value,
                    signal.direction.value,
                    signal.entry_price,
                    signal.stop_loss,
                    signal.target_1,
                    signal.confidence,
                    signal.status,
                    signal.execution_status,
                    signal.created_at,
                    signal.updated_at,
                    signal.queue_position,
                    json.dumps(signal.metadata, cls=_SafeEncoder)
                ))
                await db.commit()
        except Exception as e:
            logger.error(f"Failed to save signal to DB: {e}")

    async def update_signal_status(
        self, 
        signal_id: str, 
        status: str, 
        execution_status: str = None,
        expected_current_status: str = None
    ) -> bool:
        """
        Conditionally update signal status with optimistic locking.
        
        Returns:
            bool: True if update succeeded, False if status already changed
        """
        import time
        current_time = time.time()
        
        params = [status]
        set_clause = "status = ?"
        
        if execution_status:
            set_clause += ", execution_status = ?"
            params.append(execution_status)
            
        set_clause += ", updated_at = ?"
        params.extend([current_time, signal_id])
        
        query = f"UPDATE signals SET {set_clause} WHERE id = ?"
        
        if expected_current_status:
            query += " AND status = ?"
            params.append(expected_current_status)
            
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute(query, params)
                await db.commit()
                rows_affected = cursor.rowcount
            
            if rows_affected == 0:
                logger.warning(
                    f"Signal {signal_id} status update failed. "
                    f"Expected: {expected_current_status}, Attempted: {status}"
                )
                return False
            
            logger.info(f"Signal {signal_id}: {expected_current_status} → {status} (Success)")
            return True
        except Exception as e:
            logger.error(f"Failed to update signal {signal_id}: {e}")
            return False

    async def load_unprocessed_signals(self) -> list:
        """Loads signals that didn't reach a final state (for recovery)."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute("""
                    SELECT id, symbol, signal_type, direction, entry_price, stop_loss, target_1, 
                           confidence, status, execution_status, created_at, queue_position, metadata
                    FROM signals
                    WHERE status IN ('queued', 'pending', 'confirmed')
                    AND (execution_status != 'executed' OR execution_status IS NULL)
                    ORDER BY queue_position ASC, created_at ASC
                """) as cursor:
                    return await cursor.fetchall()
        except Exception as e:
            logger.error(f"Failed to load unprocessed signals: {e}")
            return []

    async def save_trade(self, trade: dict):
        """Fire-and-forget async save to disk."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    INSERT INTO trades (timestamp, result, pnl, regime, confidence, signal_type, agents, pev, slippage)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    str(trade["time"]),
                    trade["result"],
                    trade["pnl"],
                    trade["regime"],
                    trade.get("confidence", 0.0),
                    trade.get("signal_type", "UNKNOWN"),
                    json.dumps(trade.get("agents", {}), cls=_SafeEncoder),
                    trade.get("pev", 0.0),
                    trade.get("slippage", 0.0)
                ))
                await db.commit()
        except Exception as e:
            logger.error(f"Failed to save trade to DB: {e}")

    async def load_recent_trades(self, limit: int = 20) -> list:
        """Loads historical context on system boot."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute("""
                    SELECT timestamp, result, pnl, regime
                    FROM trades
                    ORDER BY id DESC
                    LIMIT ?
                """, (limit,)) as cursor:
                    return await cursor.fetchall()
        except Exception as e:
            logger.error(f"Failed to load trades from DB: {e}")
            return []
    async def execute(self, query: str, params: tuple = ()):
        """Generic execute for bulk updates or deletions."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(query, params)
                await db.commit()
        except Exception as e:
            logger.error(f"DB Execute Error: {e}")

    async def fetch_one(self, query: str, params: tuple = ()):
        """Generic fetch one for aggregations."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute(query, params) as cursor:
                    return await cursor.fetchone()
        except Exception as e:
            logger.error(f"DB FetchOne Error: {e}")
            return None
