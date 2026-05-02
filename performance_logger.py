import json
import csv
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

class PerformanceLogger:
    """Logs all strategy signals and trade outcomes for later analysis."""

    def __init__(self, log_dir: str = "logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)

        today = datetime.now().strftime("%Y-%m-%d")
        self.json_path = self.log_dir / f"trades_{today}.json"
        self.csv_path = self.log_dir / f"trades_{today}.csv"

        if not self.csv_path.exists():
            with open(self.csv_path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    "timestamp", "signal", "price_action_passed",
                    "options_available", "options_sentiment", "options_score",
                    "max_pain_distance", "filter_passed", "trade_executed",
                    "entry_price", "exit_price", "pnl", "would_have_taken_without_filter",
                    "exit_reason", "risk_reason", "ai_reason", "trade_id"
                ])

    def log_signal(self, data: Dict[str, Any]):
        """Log a single strategy signal (before trade execution decision)."""
        with open(self.json_path, 'a') as f:
            f.write(json.dumps(data) + "\n")

        with open(self.csv_path, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                data.get("timestamp"),
                data.get("signal"),
                data.get("price_action_passed"),
                data.get("options_available"),
                data.get("options_sentiment"),
                data.get("options_score"),
                data.get("max_pain_distance"),
                data.get("filter_passed"),
                data.get("trade_executed"),
                data.get("entry_price"),
                data.get("exit_price"),
                data.get("pnl"),
                data.get("would_have_taken_without_filter"),
                data.get("exit_reason"),
                data.get("risk_reason"),
                data.get("ai_reason"),
                data.get("trade_id")
            ])

    def log_exit(self, trade_id: str, exit_price: float, pnl: float, reason: str):
        """
        Update an existing trade log with exit details.
        """
        exit_data = {
            "timestamp": datetime.now().isoformat(),
            "trade_id": trade_id,
            "exit_price": exit_price,
            "pnl": pnl,
            "exit_reason": reason
        }
        exit_log_path = self.log_dir / f"exits_{datetime.now().strftime('%Y-%m-%d')}.json"
        with open(exit_log_path, 'a') as f:
            f.write(json.dumps(exit_data) + "\n")
