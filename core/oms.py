import sqlite3
import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any

logger = logging.getLogger("oms")


def _resolve_db_path() -> str:
    """
    Resolve the canonical DB path matching DBManager's mode-aware routing.
    OMS MUST use the same file as DBManager — they share the same schema.
    """
    import os
    env_override = os.getenv("NIFTY_DB_PATH")
    if env_override:
        return env_override
    mode = os.getenv("SYSTEM_MODE", "SIMULATION")
    return "data/trading_v4_live.db" if mode != "SIMULATION" else "data/trading_v4_sim.db"


class OrderManagementSystem:
    """
    Persistent Order State Machine (OMS).
    Manages the lifecycle of an order to prevent in-memory state loss.
    """
    def __init__(self, db_path: str = None):
        # If caller provides a path, use it. Otherwise resolve from SYSTEM_MODE env.
        # This ensures OMS always targets the SAME file as DBManager.
        self.db_path = db_path or _resolve_db_path()
        self._verify_schema()
        
    def _verify_schema(self):
        """Startup schema verification. Ensures all required contract tables and columns exist."""
        required_cols = [
            ("target_price", "REAL"),
            ("strike", "REAL"),
            ("expiry", "TEXT"),
            ("option_type", "TEXT")
        ]
        try:
            with self._get_conn() as conn:
                conn.execute("""
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
                conn.execute("""
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
                cursor = conn.execute("PRAGMA table_info(orders)")
                existing_cols = {row["name"] for row in cursor.fetchall()}
                for col_name, col_type in required_cols:
                    if col_name not in existing_cols:
                        conn.execute(f"ALTER TABLE orders ADD COLUMN {col_name} {col_type}")
                        logger.info(f"OMS verified & migrated column '{col_name}' on startup.")
        except Exception as e:
            logger.error(f"OMS startup schema verification failed: {e}")

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        # P0.3: Enterprise-grade durability
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=FULL;")
        return conn

    def create_intent(
        self, 
        signal_id: str, 
        intent_id: str, 
        symbol: str, 
        side: str, 
        qty: int, 
        requested_price: float,
        stop_loss_price: Optional[float] = None,
        target_price: Optional[float] = None,
        strike: Optional[float] = None,
        expiry: Optional[str] = None,
        option_type: Optional[str] = None
    ) -> bool:
        """Initialize a new execution intent carrying the complete execution contract."""
        try:
            with self._get_conn() as conn:
                # 1. Insert into orders table with complete contract parameters
                conn.execute("""
                    INSERT INTO orders (
                        signal_id, intent_id, symbol, side, qty, state, 
                        requested_price, stop_loss_price, target_price, strike, expiry, option_type,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    signal_id, intent_id, symbol, side, qty, "ENTRY_SUBMITTED",
                    requested_price, stop_loss_price, target_price, strike, expiry, option_type,
                    datetime.now().isoformat(), datetime.now().isoformat()
                ))
                
                # 2. Insert into order_events with full contract payload
                event_payload = {
                    "signal_id": signal_id,
                    "symbol": symbol,
                    "side": side,
                    "qty": qty,
                    "price": requested_price,
                    "stop_loss": stop_loss_price,
                    "target_price": target_price,
                    "strike": strike,
                    "expiry": expiry,
                    "option_type": option_type,
                    "SYSTEM_VERSION": "v4.6.1",
                    "STRATEGY_VERSION": "v3"
                }

                conn.execute("""
                    INSERT INTO order_events (
                        intent_id, event_type, old_state, new_state, payload_json, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    intent_id, "INTENT_CREATED", None, "ENTRY_SUBMITTED",
                    json.dumps(event_payload),
                    datetime.now().isoformat()
                ))
            return True
        except Exception as e:
            logger.error(f"Failed to create intent {intent_id}: {e}")
            return False

    def update_order_state(
        self, 
        intent_id: str, 
        new_state: str, 
        event_type: str,
        broker_order_id: Optional[str] = None,
        broker_sl_order_id: Optional[str] = None,
        avg_fill_price: Optional[float] = None,
        filled_qty: Optional[int] = None,
        payload: Dict[str, Any] = None
    ) -> bool:
        """Atomic state transition."""
        try:
            with self._get_conn() as conn:
                # Get old state
                cursor = conn.execute("SELECT state FROM orders WHERE intent_id = ?", (intent_id,))
                row = cursor.fetchone()
                old_state = row["state"] if row else "UNKNOWN"
                
                # Build update query
                update_fields = ["state = ?", "updated_at = ?"]
                params = [new_state, datetime.now().isoformat()]
                
                if broker_order_id is not None:
                    update_fields.append("broker_order_id = ?")
                    params.append(broker_order_id)
                if broker_sl_order_id is not None:
                    update_fields.append("broker_sl_order_id = ?")
                    params.append(broker_sl_order_id)
                if avg_fill_price is not None:
                    update_fields.append("avg_fill_price = ?")
                    params.append(avg_fill_price)
                if filled_qty is not None:
                    update_fields.append("filled_qty = ?")
                    params.append(filled_qty)
                    
                params.append(intent_id)
                
                conn.execute(
                    f"UPDATE orders SET {', '.join(update_fields)} WHERE intent_id = ?", 
                    tuple(params)
                )
                
                # Inject versions into payload
                event_payload = payload or {}
                event_payload["SYSTEM_VERSION"] = "v4.6.1"
                event_payload["STRATEGY_VERSION"] = "v3"

                # Insert event
                conn.execute("""
                    INSERT INTO order_events (
                        intent_id, event_type, old_state, new_state, payload_json, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    intent_id, event_type, old_state, new_state, 
                    json.dumps(event_payload),
                    datetime.now().isoformat()
                ))
            
            logger.info(f"OMS [{intent_id}] {old_state} -> {new_state} ({event_type})")
            return True
        except Exception as e:
            logger.error(f"Failed to update order state {intent_id} -> {new_state}: {e}")
            return False

    def get_order(self, intent_id: str) -> Optional[Dict]:
        """Fetch order by intent."""
        try:
            with self._get_conn() as conn:
                cursor = conn.execute("SELECT * FROM orders WHERE intent_id = ?", (intent_id,))
                row = cursor.fetchone()
                return dict(row) if row else None
        except Exception as e:
            logger.error(f"Failed to fetch order {intent_id}: {e}")
            return None

    def get_open_orders(self) -> list:
        """Fetch all non-terminal orders."""
        terminal_states = ("POSITION_CLOSED", "FAILED", "HALTED")
        try:
            with self._get_conn() as conn:
                cursor = conn.execute(
                    f"SELECT * FROM orders WHERE state NOT IN {terminal_states}"
                )
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Failed to fetch open orders: {e}")
            return []

    def get_execution_stats_today(self) -> Dict[str, int]:
        """Returns execution reconciliation metrics for today."""
        today_str = datetime.now().date().isoformat()
        stats = {
            "orders_routed": 0,
            "orders_filled": 0,
            "failed": 0,
            "cancelled": 0
        }
        try:
            with self._get_conn() as conn:
                cursor = conn.execute(
                    "SELECT state FROM orders WHERE created_at LIKE ?",
                    (f"{today_str}%",)
                )
                rows = cursor.fetchall()
                for row in rows:
                    state = row["state"]
                    stats["orders_routed"] += 1
                    if state in ("ENTRY_FILLED", "POSITION_CLOSED"):
                        stats["orders_filled"] += 1
                    elif state == "FAILED":
                        stats["failed"] += 1
                    elif state == "CANCELLED":
                        stats["cancelled"] += 1
        except Exception as e:
            logger.error(f"Failed to fetch execution stats: {e}")
        return stats

    def get_filled_orders_today(self) -> list:
        """Fetch all orders filled today with complete contract attributes."""
        today_str = datetime.now().date().isoformat()
        try:
            with self._get_conn() as conn:
                cursor = conn.execute(
                    "SELECT * FROM orders WHERE created_at LIKE ? AND state IN ('ENTRY_FILLED', 'POSITION_CLOSED')",
                    (f"{today_str}%",)
                )
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Failed to fetch filled orders today: {e}")
            return []

