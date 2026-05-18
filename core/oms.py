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
    
    DBManager uses:
      data/trading_v4_live.db  when SYSTEM_MODE != SIMULATION
      data/trading_v4_sim.db   otherwise
    """
    import os
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
        stop_loss_price: float
    ) -> bool:
        """Initialize a new execution intent from a signal."""
        try:
            with self._get_conn() as conn:
                # 1. Update orders table
                conn.execute("""
                    INSERT INTO orders (
                        signal_id, intent_id, symbol, side, qty, state, 
                        requested_price, stop_loss_price, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    signal_id, intent_id, symbol, side, qty, "ENTRY_SUBMITTED",
                    requested_price, stop_loss_price, 
                    datetime.now().isoformat(), datetime.now().isoformat()
                ))
                
                # 2. Insert into order_events
                event_payload = {"signal_id": signal_id, "qty": qty, "price": requested_price}
                event_payload["SYSTEM_VERSION"] = "v4.6.1"
                event_payload["STRATEGY_VERSION"] = "v3"

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
