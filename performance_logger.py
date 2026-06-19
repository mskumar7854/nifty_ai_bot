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
                    "max_pain_distance", "filter_passed", "trade_executed", "execution_status",
                    "entry_price", "exit_price", "pnl", "would_have_taken_without_filter",
                    "exit_reason", "risk_reason", "ai_reason", "trade_id",
                    "signal_price", "fill_price", "slippage", "spread", "execution_delay_ms",
                    "raw_confidence", "confidence_suppression", "suppression_reason"
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
                data.get("execution_status"),
                data.get("entry_price"),
                data.get("exit_price"),
                data.get("pnl"),
                data.get("would_have_taken_without_filter"),
                data.get("exit_reason"),
                data.get("ai_reason"),
                data.get("trade_id"),
                data.get("signal_price"),
                data.get("fill_price"),
                data.get("slippage"),
                data.get("spread"),
                data.get("execution_delay_ms"),
                data.get("raw_confidence"),
                data.get("confidence_suppression"),
                data.get("suppression_reason")
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

    def log_execution_quality(self, trade_id: str, signal_price: float, fill_price: float, slippage: float, spread: float, delay_ms: float):
        """Update an existing trade log with execution quality details."""
        exec_data = {
            "timestamp": datetime.now().isoformat(),
            "trade_id": trade_id,
            "signal_price": signal_price,
            "fill_price": fill_price,
            "slippage": slippage,
            "spread": spread,
            "execution_delay_ms": delay_ms
        }
        exec_log_path = self.log_dir / f"executions_{datetime.now().strftime('%Y-%m-%d')}.json"
        with open(exec_log_path, 'a') as f:
            f.write(json.dumps(exec_data) + "\n")

    def mark_trade_executed(self, trade_id: str, status: str = "EXECUTED"):
        """Safely updates trade_executed=True and execution_status=status for a trade."""
        # Update JSON
        if self.json_path.exists():
            temp_json = self.json_path.with_suffix('.tmp')
            with open(self.json_path, 'r') as f_in, open(temp_json, 'w') as f_out:
                for line in f_in:
                    if not line.strip():
                        continue
                    try:
                        data = json.loads(line)
                        if data.get("trade_id") == trade_id:
                            data["trade_executed"] = True
                            data["execution_status"] = status
                        f_out.write(json.dumps(data) + "\n")
                    except json.JSONDecodeError:
                        f_out.write(line)
            os.replace(temp_json, self.json_path)
            
        # Update CSV
        if self.csv_path.exists():
            temp_csv = self.csv_path.with_suffix('.tmp')
            with open(self.csv_path, 'r', newline='') as f_in, open(temp_csv, 'w', newline='') as f_out:
                reader = csv.reader(f_in)
                writer = csv.writer(f_out)
                header = next(reader, None)
                if header:
                    writer.writerow(header)
                    try:
                        trade_id_idx = header.index("trade_id")
                        trade_executed_idx = header.index("trade_executed")
                        exec_status_idx = header.index("execution_status")
                    except ValueError:
                        trade_id_idx = -1
                    
                    for row in reader:
                        if trade_id_idx != -1 and len(row) > trade_id_idx and row[trade_id_idx] == trade_id:
                            if len(row) > trade_executed_idx:
                                row[trade_executed_idx] = "True"
                            if len(row) > exec_status_idx:
                                row[exec_status_idx] = status
                        writer.writerow(row)
            os.replace(temp_csv, self.csv_path)

