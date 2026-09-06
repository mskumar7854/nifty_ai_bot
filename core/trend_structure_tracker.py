import time
import logging
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger("trend_structure_tracker")


class TrendStructureTracker:
    def __init__(self, max_reentry_per_trend: int = 2):
        self.max_reentry_per_trend = max_reentry_per_trend
        
        # Session State
        self.active_direction: Optional[str] = None  # "BULLISH", "BEARISH", or None
        self.leg_id: int = 1
        
        # Leg State
        self.entries_in_leg: int = 0
        self.reset_event: Optional[str] = None
        self.reset_timestamp: float = 0.0
        self.last_trade_timestamp: float = 0.0
        self.last_entry_price: float = 0.0
        
        # Reset flags
        self.bos_flag: bool = False
        self.choch_flag: bool = False
        self.liquidity_sweep_flag: bool = False
        self.vwap_reclaim_flag: bool = False

    def reset_session(self):
        """Resets the tracker for a new trading session."""
        self.active_direction = None
        self.leg_id = 1
        self.entries_in_leg = 0
        self.reset_event = None
        self.reset_timestamp = 0.0
        self.last_trade_timestamp = 0.0
        self.last_entry_price = 0.0
        self.clear_reset_flags()
        logger.info("TrendStructureTracker session reset completed. Starting clean.")

    def record_trade_execution(self, direction: str, entry_price: float, timestamp: Optional[float] = None, reset_event: Optional[str] = None):
        """Record that a trade has been executed in a specific direction."""
        now = timestamp if timestamp else time.time()
        dir_clean = str(direction).upper()
        if "." in dir_clean:
            dir_clean = dir_clean.split(".")[1]

        if self.active_direction is None:
            # First trade of the session
            self.active_direction = dir_clean
            self.leg_id = 1
            self.entries_in_leg = 1
            self.reset_event = None
            self.reset_timestamp = now
            logger.info(f"Recorded first trade of session in {dir_clean} direction (Leg #1, Entry #1) @ {entry_price}")
        elif self.active_direction != dir_clean:
            # OPPOSITE DIRECTION + EXECUTION -> New Leg
            self.active_direction = dir_clean
            self.leg_id += 1
            self.entries_in_leg = 1
            self.reset_event = None
            self.reset_timestamp = now
            logger.info(f"Recorded trade in NEW {dir_clean} direction (Leg #{self.leg_id}, Entry #1) @ {entry_price}")
        else:
            if reset_event:
                # SAME DIRECTION + STRUCTURAL RESET + EXECUTION -> New Leg Generation
                self.leg_id += 1
                self.entries_in_leg = 1
                self.reset_event = reset_event
                self.reset_timestamp = now
                logger.info(f"Recorded trade with {reset_event} reset -> {dir_clean} Leg #{self.leg_id} (Entry #1) @ {entry_price}")
            else:
                # SAME DIRECTION + NO RESET -> Increment Entry
                self.entries_in_leg += 1
                logger.info(f"Recorded trade in {dir_clean} Leg #{self.leg_id} (Entry #{self.entries_in_leg}) @ {entry_price}")

        self.last_trade_timestamp = now
        self.last_entry_price = float(entry_price)
        
        # Clear reset flags after entry
        self.clear_reset_flags()

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
            "leg_id": self.leg_id,
            "entries_in_leg": self.entries_in_leg,
            "reset_event": self.reset_event,
            "has_bos": self.bos_flag or has_inline_bos,
            "has_choch": self.choch_flag or has_inline_choch,
            "has_vwap_reclaim": self.vwap_reclaim_flag or has_inline_vwap,
            "pending_reset_event": None
        }

        # First trade in a direction is always allowed structurally
        if self.active_direction is None or self.active_direction != dir_clean:
            return True, "NEW_DIRECTION", details

        # Determine if there's an active reset event
        reset_ev = None
        if details["has_bos"]: reset_ev = "BOS"
        elif details["has_choch"]: reset_ev = "CHoCH"
        elif self.liquidity_sweep_flag: reset_ev = "LIQUIDITY_SWEEP"
        elif details["has_vwap_reclaim"]: reset_ev = "VWAP_RECLAIM"

        if reset_ev:
            details["pending_reset_event"] = reset_ev
            return True, f"STRUCTURAL_RESET_CONFIRMED ({reset_ev})", details

        # If re-entry count exceeds limit without structural reset, block
        if self.entries_in_leg >= self.max_reentry_per_trend:
            return False, f"REJECTED_SAME_STRUCTURAL_TREND: Already entered {self.entries_in_leg} times in {dir_clean} trend without structural reset (BOS/CHoCH)", details

        # Allow secondary re-entry if count is under limit
        return True, f"TREND_REENTRY_WITHIN_LIMIT (Leg {self.leg_id}: {self.entries_in_leg}/{self.max_reentry_per_trend})", details
