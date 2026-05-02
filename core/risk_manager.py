"""
============================================
🛡️ RISK MANAGER (v4.6.1 Hardened + P0-B Persistence)
Global safety guardrails for the Nifty AI Agent.
Handles Daily Loss Kill Switch and Weekend Buffers.

P0-B additions:
  • Atomic disk persistence of daily P&L state
  • Survives process crashes, OOM kills, deploys
  • Auto-resets on new calendar day
  • Writes to data/risk_state.json after EVERY update
============================================
"""

import json
import time
import logging
from datetime import datetime, date, time as dt_time
from pathlib import Path
from typing import Tuple

logger = logging.getLogger("risk_manager")

# ── P0-B: State file path ──
STATE_FILE = Path("data/risk_state.json")


class RiskManager:
    def __init__(self, settings, db_manager):
        self.settings = settings
        self.db = db_manager
        self.trading_enabled = True  # Global NEW trade gate
        self.daily_pnl = 0.0
        self.trades_today = 0
        self.max_daily_loss = getattr(settings.position, 'max_daily_loss', 3000.0)

        # ── P0-B: Load persisted state on init ──
        self._load_state()

    async def update_daily_pnl(self):
        """
        Recalculate total P&L for today from the database.
        This ensures persistence across bot restarts.
        """
        # Note: 'trades' table is used for realized PnL
        result = await self.db.fetch_one("""
            SELECT COALESCE(SUM(pnl), 0) as total_pnl
            FROM trades
            WHERE date(timestamp) = date('now')
        """)
        
        self.daily_pnl = result[0] if result else 0.0

        # ── P0-B: Persist to disk after every update ──
        self._persist_state_atomic()
        
        # Check Breach
        # (Using negative max_daily_loss if it's stored as a positive limit)
        limit = -abs(self.max_daily_loss)
        if self.daily_pnl <= limit:
            if self.trading_enabled:
                self.trading_enabled = False
                self._persist_state_atomic()
                logger.critical(f"🛑 RISK BREACH: Daily loss limit hit (₹{self.daily_pnl:,.0f}). NEW trades blocked.")
                # We do NOT square off here, only block new trades as per strategy.

    def update_daily_pnl_manual(self, amount: float) -> None:
        """
        P0-B: Manual P&L update (for use outside DB reconciliation).
        Adds `amount` to the running daily P&L total and persists to disk.
        """
        self.daily_pnl += amount
        self.trades_today += 1
        self._persist_state_atomic()

        limit = -abs(self.max_daily_loss)
        if self.daily_pnl <= limit:
            if self.trading_enabled:
                self.trading_enabled = False
                self._persist_state_atomic()
                logger.critical(
                    "🛑 Daily loss limit hit (₹%.2f). Trading halted.",
                    self.daily_pnl
                )
        
    def is_within_trading_hours(self) -> Tuple[bool, str]:
        """
        Check if we are in a safe trading window.
        Includes the 'Weekend Buffer' for Fridays.
        """
        # ── v4.6 Dynamic Cutoffs ──
        def parse_time(t_str):
            h, m = map(int, t_str.split(':'))
            return dt_time(h, m)

        friday_cutoff = parse_time(self.settings.friday_cutoff)
        daily_cutoff = parse_time(self.settings.daily_cutoff)

        # Fix: define current_time and weekday before using them
        now = datetime.now()
        current_time = now.time()
        weekday = now.weekday()   # 0=Mon … 4=Fri … 6=Sun

        # 1. Weekend Buffer (Friday 3:10 PM IST)
        if weekday == 4:  # Friday
            if current_time >= friday_cutoff:
                return False, f"Weekend Buffer: No new trades after {self.settings.friday_cutoff} on Friday."

        # 2. Daily Closing Buffer (3:20 PM IST)
        if current_time >= daily_cutoff:
            return False, f"Market Closing: No new trades after {self.settings.daily_cutoff}."

        return True, "OK"

    def can_take_new_trade(self, signal) -> Tuple[bool, str]:
        """
        The final 'Go/No-Go' check before a signal is processed.
        """
        # 1. Check Global Kill Switch (Daily Loss)
        if not self.trading_enabled:
            return False, f"Risk Halted: Daily loss limit (₹{self.max_daily_loss:,.0f}) has been breached."
            
        # 2. Check Timing (Weekend/Closing Gap)
        time_ok, time_msg = self.is_within_trading_hours()
        if not time_ok:
            return False, time_msg
            
        return True, "OK"
    
    def get_status_report(self) -> dict:
        """Helper for the /status command."""
        return {
            "trading_enabled": self.trading_enabled,
            "daily_pnl": self.daily_pnl,
            "trades_today": self.trades_today,
            "max_daily_loss": self.max_daily_loss,
            "is_weekend_buffer": datetime.now().weekday() == 4 and datetime.now().time() >= dt_time(15, 10)
        }

    # ══════════════════════════════════════════════════════════════
    # P0-B: ATOMIC DISK PERSISTENCE
    # ══════════════════════════════════════════════════════════════

    def _persist_state_atomic(self) -> None:
        """
        Atomic write — never leaves a partial/corrupt state file.
        
        Write to .tmp first, then rename (atomic on POSIX, near-atomic on Windows).
        This guarantees that even if the process is killed mid-write, the
        previous valid state file remains intact.
        """
        state = {
            "date": date.today().isoformat(),
            "daily_pnl": self.daily_pnl,
            "trades_today": self.trades_today,
            "trading_enabled": self.trading_enabled,
            "max_daily_loss": self.max_daily_loss,
            "last_updated": datetime.now().isoformat(),
        }
        try:
            STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            tmp = STATE_FILE.with_suffix(".tmp")
            tmp.write_text(json.dumps(state, indent=2))
            tmp.replace(STATE_FILE)  # Atomic on POSIX — near-atomic on Windows
        except Exception as e:
            logger.error("Failed to persist risk state to disk: %s", e)

    def _load_state(self) -> None:
        """
        Load state from disk. If date mismatch, reset cleanly.
        
        This runs on every init (including after a crash restart).
        If the stored date doesn't match today, we start fresh.
        """
        try:
            state = json.loads(STATE_FILE.read_text())
            if state.get("date") != date.today().isoformat():
                logger.info("New trading day — resetting P&L state.")
                self.daily_pnl = 0.0
                self.trades_today = 0
                self.trading_enabled = True
            else:
                self.daily_pnl = state.get("daily_pnl", 0.0)
                self.trades_today = state.get("trades_today", 0)
                self.trading_enabled = state.get("trading_enabled", True)
                logger.info(
                    "Loaded P&L state: pnl=%.2f trades=%d enabled=%s",
                    self.daily_pnl, self.trades_today, self.trading_enabled
                )
        except FileNotFoundError:
            logger.info("No risk state file found — starting fresh.")
        except (KeyError, json.JSONDecodeError) as e:
            logger.warning("Corrupt risk state file — starting fresh: %s", e)
