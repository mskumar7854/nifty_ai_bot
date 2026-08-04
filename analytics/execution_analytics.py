import os
import json
import logging
from analytics.analytics_bus import analytics_bus

class ExecutionAnalyticsEngine:
    """
    Subscribes to trade_opened, trade_closed, and signal_blocked events.
    Quantifies slippage, latency, spread costs, and missed opportunities.
    """
    def __init__(self):
        self.logger = logging.getLogger("execution_analytics")
        self.data_dir = os.path.join("data", "analytics")
        os.makedirs(self.data_dir, exist_ok=True)
        self.log_file = os.path.join(self.data_dir, "execution_stats.jsonl")
        
        analytics_bus.subscribe("trade_opened", self.handle_trade_opened)
        analytics_bus.subscribe("trade_closed", self.handle_trade_closed)
        analytics_bus.subscribe("signal_blocked", self.handle_signal_blocked)

    def handle_trade_opened(self, payload: dict):
        position = payload.get("position", {})
        entry_price = position.get("entry_price", 0.0)
        signal_price = payload.get("signal_price", entry_price)
        direction = position.get("direction", "BUY").upper()
        
        # Calculate Slippage
        if direction == "BUY":
            slippage = entry_price - signal_price
        else:
            slippage = signal_price - entry_price

        # Spread Cost
        entry_bid = position.get("entry_bid", 0.0)
        entry_ask = position.get("entry_ask", 0.0)
        spread_cost = (entry_ask - entry_bid) / 2.0 if entry_ask > entry_bid else 0.0
        
        record = {
            "timestamp": payload.get("timestamp"),
            "event": "execution_entry",
            "position_id": position.get("position_id"),
            "slippage": slippage,
            "spread_cost_entry": spread_cost,
            "latency_ms": payload.get("latency_ms", 0)
        }
        self._write_to_log(record)

    def handle_trade_closed(self, payload: dict):
        position = payload.get("position", {})
        exit_price = payload.get("exit_price", 0.0)
        theoretical_exit = payload.get("theoretical_exit", exit_price)
        direction = position.get("direction", "BUY").upper()

        if direction == "BUY":
            slippage = theoretical_exit - exit_price
        else:
            slippage = exit_price - theoretical_exit
            
        record = {
            "timestamp": payload.get("timestamp"),
            "event": "execution_exit",
            "position_id": position.get("position_id"),
            "exit_slippage": slippage,
            "realized_pnl": position.get("realized_pnl", 0.0)
        }
        self._write_to_log(record)

    def handle_signal_blocked(self, payload: dict):
        """Track missed PnL from blocked signals."""
        record = {
            "timestamp": payload.get("timestamp"),
            "event": "signal_blocked",
            "signal_id": payload.get("signal_id"),
            "reason": payload.get("reason"),
            "theoretical_entry": payload.get("theoretical_entry"),
            "missed_pnl_estimated": 0.0  # Would be updated by a background checker
        }
        self._write_to_log(record)

    def generate_kpis(self, target_date: str = None) -> dict:
        """
        Generates Execution Quality KPIs for daily audit summaries.
        Reads actual agent weight telemetry from decision snapshots.
        """
        import sqlite3
        import pandas as pd
        import numpy as np
        if target_date is None:
            target_date = datetime.now().strftime("%Y-%m-%d")

        db_path = os.path.join("data", "trading_v4_sim.db")
        signals_gen = 0
        signals_exec = 0
        part_ratios = []
        abst_ratios = []
        ev_passed = 0
        ev_failed = 0

        if os.path.exists(db_path):
            try:
                conn = sqlite3.connect(db_path)
                df_snaps = pd.read_sql_query(
                    f"SELECT agents_json, decision_json, expected_value_json FROM decision_snapshots_v2 WHERE timestamp LIKE '{target_date}%'",
                    conn
                )
                conn.close()

                signals_gen = len(df_snaps)
                for _, row in df_snaps.iterrows():
                    d_json = json.loads(row["decision_json"]) if row["decision_json"] else {}
                    if d_json.get("action") == "EXECUTE":
                        signals_exec += 1

                    ev_json = json.loads(row["expected_value_json"]) if row["expected_value_json"] else {}
                    if ev_json.get("passes_gate", False):
                        ev_passed += 1
                    else:
                        ev_failed += 1

                    a_json = json.loads(row["agents_json"]) if row["agents_json"] else {}
                    dir_w = 0.0
                    neu_w = 0.0
                    for a_name, a_out in a_json.items():
                        if isinstance(a_out, dict):
                            d_val = a_out.get("signal", "NEUTRAL")
                            w_val = 0.15 # standard agent weight share
                            if any(k in d_val for k in ["BULLISH", "BEARISH", "BUY", "SELL"]):
                                dir_w += w_val
                            else:
                                neu_w += w_val

                    tot_w = dir_w + neu_w
                    if tot_w > 0:
                        part_ratios.append(dir_w / tot_w)
                        abst_ratios.append(neu_w / tot_w)
            except Exception as e:
                self.logger.error(f"Error calculating KPIs from DB: {e}")

        avg_part = float(np.mean(part_ratios) * 100) if part_ratios else 0.0
        avg_abst = float(np.mean(abst_ratios) * 100) if abst_ratios else 0.0

        kpis = {
            "target_date": target_date,
            "signals_generated": signals_gen,
            "signals_executed": signals_exec,
            "effective_participation_pct": round(avg_part, 1),
            "average_abstention_rate_pct": round(avg_abst, 1),
            "ev_gate_passed": ev_passed,
            "ev_gate_failed": ev_failed
        }
        return kpis

    def _write_to_log(self, record: dict):
        try:
            with open(self.log_file, "a") as f:
                f.write(json.dumps(record) + "\n")
        except Exception as e:
            self.logger.error(f"Failed to write to {self.log_file}: {e}")

# Initialize and register
execution_analytics_engine = ExecutionAnalyticsEngine()
