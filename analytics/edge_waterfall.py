import os
import json
import logging
from analytics.analytics_bus import analytics_bus

class EdgeWaterfall:
    """
    Event-sourced tracker for the edge waterfall.
    Instead of maintaining state in memory and dumping at the end,
    it writes individual edge events (raw_signal_edge, execution_slippage, etc.)
    per trade_id as they happen.
    """
    def __init__(self):
        self.logger = logging.getLogger("edge_waterfall")
        self.data_dir = os.path.join("data", "analytics")
        os.makedirs(self.data_dir, exist_ok=True)
        self.log_file = os.path.join(self.data_dir, "edge_waterfall.jsonl")
        
        analytics_bus.subscribe("trade_opened", self.handle_trade_opened)
        analytics_bus.subscribe("trade_closed", self.handle_trade_closed)
        analytics_bus.subscribe("signal_generated", self.handle_signal_generated)

    def handle_signal_generated(self, payload: dict):
        # We don't have a trade_id yet, but we log the initial expected edge
        record = {
            "timestamp": payload.get("timestamp"),
            "event": "raw_signal_edge",
            "signal_id": payload.get("signal_id"),
            "value": payload.get("expected_edge_pts", 0.0)
        }
        self._write_to_log(record)

    def handle_trade_opened(self, payload: dict):
        position = payload.get("position", {})
        
        # Log execution slippage event
        direction = position.get("direction", "BUY").upper()
        entry_price = position.get("entry_price", 0.0)
        signal_price = payload.get("signal_price", entry_price)
        
        slippage = (entry_price - signal_price) if direction == "BUY" else (signal_price - entry_price)
        
        self._write_to_log({
            "timestamp": payload.get("timestamp"),
            "event": "execution_slippage_entry",
            "position_id": position.get("position_id"),
            "value": -slippage  # Slippage destroys edge
        })
        
        # Log spread cost event
        entry_bid = position.get("entry_bid", 0.0)
        entry_ask = position.get("entry_ask", 0.0)
        spread_cost = (entry_ask - entry_bid) / 2.0 if entry_ask > entry_bid else 0.0
        
        self._write_to_log({
            "timestamp": payload.get("timestamp"),
            "event": "spread_cost_entry",
            "position_id": position.get("position_id"),
            "value": -spread_cost
        })

    def handle_trade_closed(self, payload: dict):
        position = payload.get("position", {})
        self._write_to_log({
            "timestamp": payload.get("timestamp"),
            "event": "realized_edge",
            "position_id": position.get("position_id"),
            "value": position.get("realized_pnl", 0.0)
        })

    def _write_to_log(self, record: dict):
        try:
            with open(self.log_file, "a") as f:
                f.write(json.dumps(record) + "\n")
        except Exception as e:
            self.logger.error(f"Failed to write to {self.log_file}: {e}")

# Initialize and register
edge_waterfall = EdgeWaterfall()
