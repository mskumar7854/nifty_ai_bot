"""
============================================
TREND STRUCTURE TRACKER (v2.1)

Tracks market structure reset states for trend re-entry gating.
Prevents rapid re-entries into the same trend move (e.g. 5-minute repeated trades)
unless a structural reset event has occurred:
  - BOS (Break of Structure)
  - CHoCH (Change of Character)
  - Liquidity Sweep
  - VWAP Reclaim / Re-extension
============================================
"""

import time
import logging
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger("trend_structure_tracker")


class TrendStructureTracker:
    def __init__(self, max_reentry_per_trend: int = 2):
        self.max_reentry_per_trend = max_reentry_per_trend
        
        # State tracking
        self.active_direction: Optional[str] = None  # "BULLISH", "BEARISH", or None
        self.entries_in_current_trend: int = 0
        self.last_trade_timestamp: float = 0.0
        self.last_entry_price: float = 0.0
        
        # Reset flags
        self.bos_flag: bool = False
        self.choch_flag: bool = False
        self.liquidity_sweep_flag: bool = False
        self.vwap_reclaim_flag: bool = False

    def record_trade_execution(self, direction: str, entry_price: float, timestamp: Optional[float] = None):
        """Record that a trade has been executed in a specific direction."""
        now = timestamp if timestamp else time.time()
        dir_clean = str(direction).upper()
        if "." in dir_clean:
            dir_clean = dir_clean.split(".")[1]

        if self.active_direction == dir_clean:
            self.entries_in_current_trend += 1
        else:
            self.active_direction = dir_clean
            self.entries_in_current_trend = 1

        self.last_trade_timestamp = now
        self.last_entry_price = float(entry_price)
        
        # Clear reset flags after entry
        self.clear_reset_flags()
        logger.info(f"Recorded trade in {dir_clean} trend (Entry #{self.entries_in_current_trend}) @ {entry_price}")

    def register_structural_event(self, event_type: str, details: Optional[Dict[str, Any]] = None):
        """Register a market structure reset event (BOS, CHoCH, Liquidity Sweep, VWAP Reclaim)."""
        ev = str(event_type).upper()
        if "BOS" in ev or "BREAK_OF_STRUCTURE" in ev:
            self.bos_flag = True
        elif "CHOCH" in ev or "CHANGE_OF_CHARACTER" in ev:
            self.choch_flag = True
        elif "SWEEP" in ev or "LIQUIDITY" in ev:
            self.liquidity_sweep_flag = True
        elif "VWAP" in ev:
            self.vwap_reclaim_flag = True

        logger.info(f"Registered structural reset event: {ev}")

    def clear_reset_flags(self):
        """Clear structural reset flags."""
        self.bos_flag = False
        self.choch_flag = False
        self.liquidity_sweep_flag = False
        self.vwap_reclaim_flag = False

    def check_reentry_allowed(self, direction: str, signal_metadata: Optional[Dict[str, Any]] = None) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Check if a trade in the given direction is allowed or blocked by structural state memory.
        
        Returns:
            (is_allowed: bool, reason: str, details: Dict[str, Any])
        """
        dir_clean = str(direction).upper()
        if "." in dir_clean:
            dir_clean = dir_clean.split(".")[1]

        meta = signal_metadata or {}
        has_inline_bos = meta.get("bos_detected", False) or meta.get("bos", False)
        has_inline_choch = meta.get("choch_detected", False) or meta.get("choch", False)
        has_inline_vwap = meta.get("vwap_reclaim", False)

        details = {
            "active_direction": self.active_direction,
            "entries_in_current_trend": self.entries_in_current_trend,
            "has_bos": self.bos_flag or has_inline_bos,
            "has_choch": self.choch_flag or has_inline_choch,
            "has_vwap_reclaim": self.vwap_reclaim_flag or has_inline_vwap
        }

        # First trade in a direction is always allowed structurally
        if self.active_direction is None or self.active_direction != dir_clean:
            return True, "NEW_DIRECTION", details

        has_structural_reset = details["has_bos"] or details["has_choch"] or self.liquidity_sweep_flag or details["has_vwap_reclaim"]

        if has_structural_reset:
            return True, "STRUCTURAL_RESET_CONFIRMED", details

        # If re-entry count exceeds limit without structural reset, block
        if self.entries_in_current_trend >= self.max_reentry_per_trend:
            return False, f"REJECTED_SAME_STRUCTURAL_TREND: Already entered {self.entries_in_current_trend} times in {dir_clean} trend without structural reset (BOS/CHoCH)", details

        # Allow secondary re-entry if count is under limit
        return True, f"TREND_REENTRY_WITHIN_LIMIT ({self.entries_in_current_trend}/{self.max_reentry_per_trend})", details
