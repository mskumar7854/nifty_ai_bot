"""
============================================
🕐 SESSION STRATEGY — TIME-BASED RULES

Controls WHEN to trade.
Markets have rhythm — trade with it.

Sessions:
  09:25-10:30  Morning Prime (BEST)
  10:30-12:00  Mid Morning (A+ only)
  12:00-13:30  LUNCH — NO TRADING
  13:30-14:15  Afternoon — Scan Only
  14:15-15:10  Power Hour (1 trade max)
  15:10-15:30  Closing — EXIT ONLY
============================================
"""

from datetime import datetime, time
from typing import Dict, Tuple

import pytz

from models.signals import Signal
from utils.logger import get_logger
from config.settings import Settings


IST = pytz.timezone("Asia/Kolkata")


def _now_ist() -> datetime:
    return datetime.now(IST)


def _time_in_range(start_str: str, end_str: str) -> bool:
    """Check if current IST time is within a range"""
    now = _now_ist().time()
    h, m = map(int, start_str.split(":"))
    start = time(h, m)
    h, m = map(int, end_str.split(":"))
    end = time(h, m)
    return start <= now <= end


def _get_current_session_name(sessions: Dict) -> str:
    """Identify which session we're currently in"""
    for name, cfg in sessions.items():
        if "start" in cfg and "end" in cfg:
            if _time_in_range(cfg["start"], cfg["end"]):
                return name
    return "outside_market"


class SessionStrategy:
    """
    Time-based trading rules.

    Knows when to trade, when to watch,
    and when to stay completely flat.
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self.sessions = settings.session_strategy.sessions
        self.logger = get_logger("session_strategy")

    def get_current_rules(self) -> Dict:
        """Get current session rules"""

        # 1. Global SessionGuard check first
        from core.session_guard import SessionGuard
        guard_ok, guard_reason = SessionGuard.can_trade(self.settings)
        if not guard_ok:
            return {
                "session": "market_open_protection",
                "can_trade": False,
                "reason": guard_reason,
                "max_trades": 0,
                "min_confidence": 100,
                "strategy": "blocked",
                "current_time": _now_ist().strftime("%H:%M:%S"),
            }

        # 2. Specific session check
        session_name = _get_current_session_name(self.sessions)
        session = self.sessions.get(session_name, {})

        can_trade = session.get("trade", False)
        reason = session.get("reason", "Outside session")
        max_trades = session.get("max_trades", 0)
        min_confidence = session.get("min_confidence", 80)
        strategy = session.get("strategy", "none")

        return {
            "session": session_name,
            "can_trade": can_trade,
            "reason": reason,
            "max_trades": max_trades,
            "min_confidence": min_confidence,
            "strategy": strategy,
            "current_time": _now_ist().strftime("%H:%M:%S"),
        }

    def validate_signal(
        self, signal: Signal
    ) -> Tuple[bool, str, Dict]:
        """
        Validate a signal against current session rules.
        Returns (ok, reason, session_info).
        """

        rules = self.get_current_rules()

        if not rules["can_trade"]:
            return (
                False,
                f"Session '{rules['session']}': {rules['reason']}",
                rules,
            )

        if signal.confidence < rules["min_confidence"]:
            return (
                False,
                (
                    f"Signal confidence {signal.confidence:.0f}% "
                    f"below session minimum {rules['min_confidence']}%"
                ),
                rules,
            )

        return True, "Session OK", rules

    def is_exit_only(self) -> bool:
        """True when in closing zone — exit only, no new trades"""
        rules = self.get_current_rules()
        return rules["session"] == "closing_zone"

    def is_market_hours(self) -> bool:
        """True if within any market session"""
        now = _now_ist().time()
        return time(9, 15) <= now <= time(15, 30)
