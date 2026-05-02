"""
============================================
📝 TRADE LOGGER
Records all signals and outcomes for
performance analysis and self-improvement
============================================
"""

import json
import os
from datetime import datetime, date
from typing import List, Dict

from models.signals import Signal, SignalType
from utils.logger import get_logger
from utils.helpers import save_json, load_json


class TradeLogger:
    """
    Maintains complete trade journal.
    Used for:
    - Performance tracking
    - Pattern analysis
    - System improvement
    """

    def __init__(self, data_dir: str = "data"):
        self.logger = get_logger("trade_logger")
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)

        self.signals_file = os.path.join(data_dir, "signals.json")
        self.performance_file = os.path.join(data_dir, "performance.json")
        self.daily_file = os.path.join(
            data_dir, f"daily_{date.today().isoformat()}.json"
        )

        # In-memory storage
        self.today_signals: List[dict] = []
        self.session_stats = {
            "total_signals": 0,
            "buy_ce_signals": 0,
            "buy_pe_signals": 0,
            "no_trade_signals": 0,
            "avg_confidence": 0,
            "session_start": datetime.now().isoformat(),
        }

    def log_signal(self, signal: Signal):
        """Record a signal"""
        record = {
            "timestamp": signal.timestamp.isoformat(),
            "signal_type": signal.signal_type.value,
            "direction": signal.direction.value,
            "confidence": signal.confidence,
            "strength": signal.strength.value,
            "entry": signal.entry_price,
            "stop_loss": signal.stop_loss,
            "target_1": signal.target_1,
            "target_2": signal.target_2,
            "position_size": signal.position_size,
            "reasons": signal.reasons,
            "warnings": signal.warnings,
            "agent_votes": signal.agent_votes,
        }

        self.today_signals.append(record)
        self._update_stats(signal)

        # Save periodically (every 10 signals)
        if len(self.today_signals) % 10 == 0:
            self._save_daily()

    def _update_stats(self, signal: Signal):
        """Update session statistics"""
        self.session_stats["total_signals"] += 1

        if signal.signal_type == SignalType.BUY_CE:
            self.session_stats["buy_ce_signals"] += 1
        elif signal.signal_type == SignalType.BUY_PE:
            self.session_stats["buy_pe_signals"] += 1
        else:
            self.session_stats["no_trade_signals"] += 1

        # Running average confidence (only for trade signals)
        if signal.signal_type != SignalType.NO_TRADE:
            trade_count = (
                self.session_stats["buy_ce_signals"] +
                self.session_stats["buy_pe_signals"]
            )
            if trade_count > 0:
                prev_avg = self.session_stats["avg_confidence"]
                new_avg = prev_avg + (signal.confidence - prev_avg) / trade_count
                self.session_stats["avg_confidence"] = round(new_avg, 1)

    def _save_daily(self):
        """Save daily data to file"""
        data = {
            "date": date.today().isoformat(),
            "stats": self.session_stats,
            "signals": self.today_signals,
        }
        save_json(data, self.daily_file)

    def get_session_summary(self) -> dict:
        """Get current session summary"""
        return {
            **self.session_stats,
            "signals_today": len(self.today_signals),
        }

    def save_all(self):
        """Force save all data"""
        self._save_daily()
        self.logger.info(
            f"Saved {len(self.today_signals)} signals to {self.daily_file}"
        )
