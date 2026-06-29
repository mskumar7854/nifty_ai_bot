import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

class PerformanceLogger:
    """Logs all strategy signals, event streams, and the immutable ledger."""

    def __init__(self, log_dir: str = "logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        self.schema_version = 2

    def _append_event(self, filename: str, event_type: str, data: Dict[str, Any]):
        """Append an event to a .ndjson file."""
        today = datetime.now().strftime("%Y-%m-%d")
        file_path = self.log_dir / f"{filename}_{today}.ndjson"
        
        event_record = {
            "schema_version": self.schema_version,
            "event": event_type,
            "timestamp": datetime.now().isoformat(),
            **data
        }
        
        with open(file_path, 'a') as f:
            f.write(json.dumps(event_record) + "\n")

    def log_signal(self, data: Dict[str, Any]):
        """Log a single strategy signal to event stream."""
        self._append_event("signals", "SIGNAL", data)

    def log_rejection(self, data: Dict[str, Any]):
        """Log a trade rejection to event stream."""
        self._append_event("rejections", "REJECTION", data)

    def log_entry(self, data: Dict[str, Any]):
        """Log a trade entry to event stream."""
        self._append_event("entries", "ENTRY", data)

    def log_exit(self, trade_id: str, exit_price: float, pnl: float, reason: str):
        """Log a trade exit to event stream."""
        data = {
            "trade_id": trade_id,
            "exit_price": exit_price,
            "pnl": pnl,
            "exit_reason": reason
        }
        self._append_event("exits", "EXIT", data)

    def log_execution_quality(self, trade_id: str, signal_price: float, fill_price: float, slippage: float, spread: float, delay_ms: float):
        """Log execution quality to event stream."""
        data = {
            "trade_id": trade_id,
            "signal_price": signal_price,
            "fill_price": fill_price,
            "slippage": slippage,
            "spread": spread,
            "execution_delay_ms": delay_ms
        }
        self._append_event("entries", "EXECUTION_QUALITY", data)

    def mark_trade_executed(self, trade_id: str, status: str = "EXECUTED"):
        """Log trade execution status update to event stream."""
        data = {
            "trade_id": trade_id,
            "execution_status": status
        }
        self._append_event("entries", "TRADE_EXECUTED", data)

    def log_final_trade(self, ledger_record: dict):
        """
        Record a finalized, immutable execution ledger record.
        This contains the complete lifecycle of a trade in a structured format.
        """
        today = datetime.now().strftime("%Y-%m-%d")
        ledger_path = self.log_dir / f"ledger_{today}.json"
        
        with open(ledger_path, 'a') as f:
            f.write(json.dumps(ledger_record) + "\n")
