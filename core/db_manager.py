"""
============================================
📦 DATABASE MANAGER
Asynchronous SQLite implementation to persist
system memory and trade history without
blocking the sub-50ms trading loop.
============================================
"""

import aiosqlite
import logging
from datetime import datetime

logger = logging.getLogger("db_manager")

class DBManager:
    def __init__(self, db_path=None):
        if db_path and db_path != "data/trading_v4.db":
            self.db_path = db_path
        else:
            import os
            mode = os.getenv("SYSTEM_MODE", "SIMULATION")
            self.db_path = "data/trading_v4_live.db" if mode != "SIMULATION" else "data/trading_v4_sim.db"

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
                
            await db.commit()
        logger.info("📦 SQLite Database connected and verified (v4.6.1 Hardened).")

    async def save_signal(self, signal):
        """Persists a new signal to disk for recovery."""
        import json
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
                    json.dumps(signal.metadata)
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
        import json
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
                    json.dumps(trade.get("agents", {})),
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
