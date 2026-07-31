"""
Trade Lifecycle Logger — Records the full lifecycle of every trade.

Writes to logs/trade_lifecycle.jsonl with events:
  TRADE_OPENED  — Entry with full context
  TRADE_UPDATE  — MFE/MAE changes, SL adjustments
  TRADE_CLOSED  — Exit with PnL, R-multiple, MFE, MAE, holding time
"""

import json
import logging
from datetime import datetime
from pathlib import Path

import json
import logging
from datetime import datetime
from pathlib import Path

from models.events import TradeStateChanged, MfeUpdated, MaeUpdated, TradeEvaluated

logger = logging.getLogger("trade_lifecycle")

class TradeLifecycleLogger:
    """Append-only JSONL logger for trade lifecycle events using publish/subscribe."""

    def __init__(self, event_manager, log_dir: str = "logs"):
        self._log_dir = Path(log_dir)
        self._log_dir.mkdir(parents=True, exist_ok=True)
        self._file_path = self._log_dir / "trade_lifecycle.jsonl"
        self.event_manager = event_manager
        self._subscribe()

    def _subscribe(self):
        if not self.event_manager:
            return
        self.event_manager.subscribe(TradeStateChanged, self._handle_state_changed)
        self.event_manager.subscribe(MfeUpdated, self._handle_mfe_updated)
        self.event_manager.subscribe(MaeUpdated, self._handle_mae_updated)
        self.event_manager.subscribe(TradeEvaluated, self._handle_trade_evaluated)

    def _write(self, record: dict):
        # Enforce schema version on all events
        record["schema_version"] = 1
        try:
            with open(self._file_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, default=str) + "\n")
        except Exception as e:
            logger.error(f"Failed to write trade lifecycle event: {e}")

    def _handle_state_changed(self, event: TradeStateChanged):
        self._write({
            "event": "TRADE_STATE_CHANGED",
            "ts": event.timestamp,
            "trade_id": event.correlation_id,
            "payload": event.payload
        })

    def _handle_mfe_updated(self, event: MfeUpdated):
        self._write({
            "event": "MFE_UPDATED",
            "ts": event.timestamp,
            "trade_id": event.correlation_id,
            "payload": event.payload
        })

    def _handle_mae_updated(self, event: MaeUpdated):
        self._write({
            "event": "MAE_UPDATED",
            "ts": event.timestamp,
            "trade_id": event.correlation_id,
            "payload": event.payload
        })

    def _handle_trade_evaluated(self, event: TradeEvaluated):
        self._write({
            "event": "TRADE_EVALUATED",
            "ts": event.timestamp,
            "trade_id": event.correlation_id,
            "payload": event.payload
        })

