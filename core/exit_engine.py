"""
============================================
🚪 EXIT ENGINE — INTELLIGENT EXIT MANAGEMENT

Knows when to get out before the market
punishes you for staying too long.

Handles:
- Daily target locking
- Consecutive loss stopping
- Position sizing reduction
- Time-based exits
============================================
"""

from datetime import datetime, date
from typing import Dict, Tuple

from utils.logger import get_logger
from config.settings import Settings


class ExitEngine:
    """
    Exit intelligence layer.

    Protects profits, limits losses,
    enforces daily rules.
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self.cfg = settings.exit
        self.logger = get_logger("exit_engine")

        # ── Daily State ──
        self.today_date = date.today()
        self.today_pnl = 0.0
        self.today_trades = 0
        self.daily_target_hit = False
        self.daily_loss_hit = False

        # ── Consecutive Loss Tracking ──
        self.consecutive_losses = 0
        self.consecutive_wins = 0
        self.last_trade_result = ""

        # ── Size Reduction State ──
        self.size_reduction_active = False
        self.size_reduction_factor = 1.0

        # ── Last Trade Time ──
        self.last_trade_time: datetime = None

    def record_trade_result(self, pnl: float):
        """Record a trade result and update exit state"""

        self._check_daily_reset()

        self.today_pnl += pnl
        self.today_trades += 1
        self.last_trade_time = datetime.now()

        if pnl > 0:
            self.consecutive_losses = 0
            self.consecutive_wins += 1
            self.last_trade_result = "WIN"
            # Reset size reduction on win
            if self.size_reduction_active:
                self.size_reduction_active = False
                self.size_reduction_factor = 1.0
                self.logger.info("📈 Size reduction cleared after win")
        else:
            self.consecutive_wins = 0
            self.consecutive_losses += 1
            self.last_trade_result = "LOSS"

            # Activate size reduction after loss
            if (
                self.cfg.reduce_size_after_loss
                and self.consecutive_losses >= 1
            ):
                self.size_reduction_active = True
                self.size_reduction_factor = (
                    1.0 - self.cfg.loss_size_reduction_pct / 100
                )
                self.logger.warning(
                    f"📉 Size reduced to "
                    f"{self.size_reduction_factor*100:.0f}% "
                    f"after {self.consecutive_losses} loss(es)"
                )

        # Check daily target
        if (
            self.today_pnl >= self.cfg.daily_target_amount
            and self.cfg.stop_after_daily_target
        ):
            self.daily_target_hit = True
            self.logger.info(
                f"🎯 DAILY TARGET HIT! "
                f"P&L: ₹{self.today_pnl:,.0f} — "
                f"stopping for the day"
            )

        # Check consecutive loss limit
        if self.consecutive_losses >= self.cfg.stop_after_consecutive_losses:
            self.logger.warning(
                f"⛔ {self.consecutive_losses} consecutive losses — "
                f"stopping new trades"
            )

    def should_reduce_size(self) -> Tuple[bool, float]:
        """Returns (should_reduce, reduction_factor)"""
        return self.size_reduction_active, self.size_reduction_factor

    def can_take_new_trade(self) -> Tuple[bool, str]:
        """Check if a new trade can be taken"""

        self._check_daily_reset()

        if self.daily_target_hit:
            return False, "Daily target already hit"

        if self.daily_loss_hit:
            return False, "Daily loss limit hit"

        if self.consecutive_losses >= self.cfg.stop_after_consecutive_losses:
            return False, (
                f"Stopped after {self.consecutive_losses} "
                f"consecutive losses"
            )

        return True, "OK"

    def _check_daily_reset(self):
        today = date.today()
        if self.today_date != today:
            self.today_date = today
            self.today_pnl = 0.0
            self.today_trades = 0
            self.daily_target_hit = False
            self.daily_loss_hit = False
            self.consecutive_losses = 0
            self.consecutive_wins = 0
            self.size_reduction_active = False
            self.size_reduction_factor = 1.0
            self.logger.info("🔄 New trading day — exit engine reset")

    def get_status(self) -> Dict:
        return {
            "today_pnl": f"₹{self.today_pnl:,.0f}",
            "today_trades": self.today_trades,
            "daily_target_hit": self.daily_target_hit,
            "consecutive_losses": self.consecutive_losses,
            "consecutive_wins": self.consecutive_wins,
            "size_reduction_active": self.size_reduction_active,
            "size_reduction_factor": self.size_reduction_factor,
            "last_result": self.last_trade_result,
        }
