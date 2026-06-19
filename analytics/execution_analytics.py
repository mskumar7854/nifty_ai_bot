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

    def _write_to_log(self, record: dict):
        try:
            with open(self.log_file, "a") as f:
                f.write(json.dumps(record) + "\n")
        except Exception as e:
            self.logger.error(f"Failed to write to {self.log_file}: {e}")

# Initialize and register
execution_analytics_engine = ExecutionAnalyticsEngine()
