import os
import json
import hashlib
import threading
import queue
from datetime import datetime
from pathlib import Path
from utils.logger import get_logger

logger = get_logger("raw_capture")

class RawDecisionLogger:
    """
    Immutable, non-blocking observability layer that captures 
    raw decision inputs before any mutating gate blocks the signal.
    """
    def __init__(self, data_dir: str = "data/raw"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.queue = queue.Queue()
        self.sequence_counter = 0
        self.current_date = None
        self._stop_event = threading.Event()
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()
        
        import atexit
        atexit.register(self.stop)

    def _worker_loop(self):
        while not self._stop_event.is_set():
            try:
                record = self.queue.get(timeout=1.0)
                if record is None:
                    break
                try:
                    self._write_record(record)
                finally:
                    self.queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Raw capture worker failed: {e}")
                
    def _get_file_path(self, date_str: str) -> Path:
        return self.data_dir / f"v2_raw_inputs_{date_str}.jsonl"
                
    def _write_record(self, record: dict):
        try:
            date_str = record.get("timestamp", "")[:10]
            if not date_str:
                date_str = datetime.now().strftime("%Y-%m-%d")
                
            # Reset sequence if day changed
            if self.current_date != date_str:
                self.current_date = date_str
                self.sequence_counter = 0
            
            self.sequence_counter += 1
            record["capture_sequence"] = self.sequence_counter
            
            # Serialize for hashing
            # Remove record_hash if it exists just to be safe
            record.pop("record_hash", None)
            canonical_json = json.dumps(record, sort_keys=True, separators=(',', ':'))
            record_hash = hashlib.sha256(canonical_json.encode('utf-8')).hexdigest()
            record["record_hash"] = record_hash
            
            final_json = json.dumps(record)
            
            file_path = self._get_file_path(date_str)
            with open(file_path, "a", encoding="utf-8") as f:
                f.write(final_json + "\n")
                
        except Exception as e:
            logger.error(f"Failed to write raw decision record: {e}")

    def capture(self, raw_record: dict):
        """
        Submits a raw record to the non-blocking queue.
        Failure to capture will never crash the caller.
        """
        try:
            self.queue.put_nowait(raw_record)
        except Exception as e:
            logger.error(f"Failed to enqueue raw decision record: {e}")

    def stop(self):
        """Clean shutdown of the worker thread."""
        try:
            # Wait for all pending items to be processed
            self.queue.join()
        except Exception:
            pass
            
        self._stop_event.set()
        # Wake up the thread if it's waiting on queue.get
        try:
            self.queue.put_nowait(None)
        except Exception:
            pass
            
        if self.worker_thread.is_alive():
            self.worker_thread.join(timeout=2.0)
