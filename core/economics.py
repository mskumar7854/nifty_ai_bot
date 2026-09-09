import sqlite3
import json
import logging
from typing import Dict, Any

logger = logging.getLogger("economics")

class CostEngine:
    """
    P0.5: Exact Trade Economics & Cost Engine for Indian Options (NSE F&O).
    Calculates net P&L after all real-world execution frictions.
    """
    
    # 2025/2026 typical rates for Indian Options
    BROKERAGE_PER_ORDER = 20.0
    STT_RATE = 0.001  # 0.1% on Sell Side Premium
    EXCHANGE_TXN_RATE = 0.000495  # ~0.0495% on Premium
    GST_RATE = 0.18  # 18% on (Brokerage + Exchange Txn)
    SEBI_RATE = 0.000001  # 10 per Crore
    STAMP_DUTY_RATE = 0.00003  # 0.003% on Buy Side Premium

    @classmethod
    def calculate_costs(
        cls, 
        entry_price: float, 
        exit_price: float, 
        qty: int, 
        direction: str = "BUY"
    ) -> Dict[str, float]:
        """Calculate complete execution costs for a round-trip options trade."""
        
        # Gross Turnover
        buy_value = entry_price * qty if direction == "BUY" else exit_price * qty
        sell_value = exit_price * qty if direction == "BUY" else entry_price * qty
        total_turnover = buy_value + sell_value
        
        # 1. Brokerage (Entry + Exit = 2 orders)
        brokerage = cls.BROKERAGE_PER_ORDER * 2
        
        # 2. Exchange Transaction Charges
        exchange_charges = total_turnover * cls.EXCHANGE_TXN_RATE
        
        # 3. GST (18% on Brokerage + Exchange Charges)
        gst = (brokerage + exchange_charges) * cls.GST_RATE
        
        # 4. STT (Only on SELL side for Options)
        stt = sell_value * cls.STT_RATE
        
        # 5. SEBI Charges
        sebi = total_turnover * cls.SEBI_RATE
        
        # 6. Stamp Duty (Only on BUY side for Options)
        stamp_duty = buy_value * cls.STAMP_DUTY_RATE
        
        total_costs = brokerage + exchange_charges + gst + stt + sebi + stamp_duty
        gross_pnl = (sell_value - buy_value)
        net_pnl = gross_pnl - total_costs
        
        return {
            "gross_pnl": round(gross_pnl, 2),
            "net_pnl": round(net_pnl, 2),
            "total_costs": round(total_costs, 2),
            "brokerage": round(brokerage, 2),
            "exchange_charges": round(exchange_charges, 2),
            "stt": round(stt, 2),
            "gst": round(gst, 2),
            "sebi_charges": round(sebi, 2),
            "stamp_duty": round(stamp_duty, 2)
        }

    @classmethod
    def save_trade_economics(
        cls, 
        db_path: str,
        intent_id: str,
        costs: Dict[str, float],
        execution_metrics: Dict[str, Any]
    ) -> bool:
        """Persist immutable trade economics snapshot to OMS DB."""
        try:
            conn = sqlite3.connect(db_path)
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=FULL;")
            
            with conn:
                conn.execute("""
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
                conn.execute("""
                    INSERT OR REPLACE INTO trade_economics (
                        intent_id, gross_pnl, net_pnl, spread_cost, slippage_cost,
                        brokerage, stt, gst, sebi_charges, stamp_duty,
                        holding_seconds, mfe, mae, realized_r_multiple,
                        entry_bid, entry_ask, entry_fill, exit_bid, exit_ask, exit_fill,
                        spread_pct_entry, spread_pct_exit, quote_age_ms,
                        slippage_entry, slippage_exit
                    ) VALUES (
                        ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?,
                        ?, ?, ?, ?,
                        ?, ?, ?, ?, ?, ?,
                        ?, ?, ?,
                        ?, ?
                    )
                """, (
                    intent_id,
                    costs["gross_pnl"],
                    costs["net_pnl"],
                    execution_metrics.get("spread_cost", 0.0),
                    execution_metrics.get("slippage_cost", 0.0),
                    
                    costs["brokerage"],
                    costs["stt"],
                    costs["gst"],
                    costs["sebi_charges"],
                    costs["stamp_duty"],
                    
                    execution_metrics.get("holding_seconds", 0.0),
                    execution_metrics.get("mfe", 0.0),
                    execution_metrics.get("mae", 0.0),
                    
                    execution_metrics.get("realized_r_multiple", 0.0),
                    
                    execution_metrics.get("entry_bid", 0.0),
                    execution_metrics.get("entry_ask", 0.0),
                    execution_metrics.get("entry_fill", 0.0),
                    execution_metrics.get("exit_bid", 0.0),
                    execution_metrics.get("exit_ask", 0.0),
                    execution_metrics.get("exit_fill", 0.0),
                    
                    execution_metrics.get("spread_pct_entry", 0.0),
                    execution_metrics.get("spread_pct_exit", 0.0),
                    execution_metrics.get("quote_age_ms", 0.0),
                    execution_metrics.get("slippage_entry", 0.0),
                    execution_metrics.get("slippage_exit", 0.0)
                ))
            return True
        except Exception as e:
            logger.error(f"Failed to save trade economics for {intent_id}: {e}")
            return False
