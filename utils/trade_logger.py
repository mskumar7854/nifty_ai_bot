import json
import os
import threading
from typing import Union
from models.trade_record import TradeRecord, RejectionRecord

class TradeLogger:
    """
    THREAD-SAFE NDJSON LOGGER (Refinement 1)
    Writes trade results and rejections to separated .ndjson files.
    """
    def __init__(self, trades_path="logs/trades.ndjson", rejections_path="logs/rejections.ndjson"):
        self.trades_path = trades_path
        self.rejections_path = rejections_path
        self.lock = threading.Lock()
        
        # Ensure directories exist
        os.makedirs(os.path.dirname(trades_path), exist_ok=True)
        os.makedirs(os.path.dirname(rejections_path), exist_ok=True)

    def log_trade(self, record: TradeRecord):
        """Thread-safe append of a closed trade (NDJSON)"""
        with self.lock:
            self._write_to_ndjson(self.trades_path, record.to_dict())

    def log_rejection(self, record: RejectionRecord):
        """Thread-safe append of a rejected signal (NDJSON)"""
        with self.lock:
            self._write_to_ndjson(self.rejections_path, record.to_dict())

    def _write_to_ndjson(self, file_path: str, record_dict: dict):
        """
        Appends a single JSON object as a new line.
        Robust against corruption and highly scalable.
        """
        try:
            with open(file_path, "a", encoding='utf-8') as f:
                f.write(json.dumps(record_dict) + "\n")
        except Exception as e:
            # Fallback to console if file system fails
            print(f"CRITICAL: Failed to write log to {file_path}: {e}")
