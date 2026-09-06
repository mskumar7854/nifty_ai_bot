"""
============================================
RISK MANAGER
============================================
Position sizing, stop loss, trailing stop,
daily limits, and trade lifecycle management.
============================================
"""

import logging
from datetime import datetime
from typing import Optional, Dict, List
from dataclasses import dataclass, field

from .config import Config

logger = logging.getLogger("risk_manager")


# ══════════════════════════════════════════
# DATA CLASSES
# ══════════════════════════════════════════

@dataclass
class Trade:
    """Complete trade record."""
    symbol: str
    entry_price: float
    quantity: int
    option_type: str          # CE | PE
    strike: int
    expiry: str
    timestamp: datetime
    entry_reason: str = ""

    stop_loss: float = 0.0
    target: float = 0.0
    current_price: float = 0.0

    pnl: float = 0.0
    pnl_percent: float = 0.0
    status: str = "OPEN"      # OPEN | CLOSED
    exit_price: Optional[float] = None
    exit_timestamp: Optional[datetime] = None
    exit_reason: str = ""

    # Internal flag — set when partial exit done
    _partial_exited: bool = False

    def update_pnl(self):
        """Recalculate P&L from current_price."""
        if self.entry_price > 0:
            self.pnl_percent = (
                (self.current_price - self.entry_price) / self.entry_price * 100
            )
            self.pnl = (self.current_price - self.entry_price) * self.quantity


@dataclass
class DailyStats:
    """One row per trading day."""
    date: str
    trades_count: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_pnl: float = 0.0
    max_drawdown: float = 0.0
    trades: List[Trade] = field(default_factory=list)

    @property
    def win_rate(self) -> float:
        return (
            self.winning_trades / self.trades_count * 100
            if self.trades_count > 0 else 0.0
        )

    @property
    def is_loss_limit_hit(self) -> bool:
        return self.total_pnl <= -Config.MAX_DAILY_LOSS


# ══════════════════════════════════════════
# RISK MANAGER
# ══════════════════════════════════════════

class RiskManager:
    """
    Guards on:
      • Daily loss limit (₹2,000 default)
      • Max trades per day (3 default)
      • No duplicate direction
      • Stop-loss / target calculation
      • Trailing stop progression
    """

    def __init__(
        self,
        max_daily_loss: float = Config.MAX_DAILY_LOSS,
        max_trades_per_day: int = Config.MAX_TRADES_PER_DAY,
    ):
        self.max_daily_loss = max_daily_loss
        self.max_trades_per_day = max_trades_per_day
        self.daily_stats: Dict[str, DailyStats] = {}
        self.active_trades: List[Trade] = []
        self._today_key = self._get_today_key()

    # ── Helpers ───────────────────────────────────────────
    def _get_today_key(self) -> str:
        return datetime.now().strftime("%Y-%m-%d")

    def _today(self) -> DailyStats:
        key = self._get_today_key()
        if key not in self.daily_stats:
            self.daily_stats[key] = DailyStats(date=key)
        return self.daily_stats[key]

    # ── Trade eligibility ──────────────────────────────────
    def can_take_trade(self, signal: str) -> tuple[bool, str]:
        """Return (allowed, reason)."""
        if signal not in Config.ALLOWED_SIGNALS:
            return False, f"Signal '{signal}' not allowed"

        stats = self._today()

        if stats.is_loss_limit_hit:
            return False, f"Daily loss limit ₹{self.max_daily_loss:,.0f} hit"

        if stats.trades_count >= self.max_trades_per_day:
            return False, f"Max {self.max_trades_per_day} trades/day reached"

        otype = "CE" if signal == "BUY_CE" else "PE"
        if any(t.status == "OPEN" and t.option_type == otype for t in stats.trades):
            return False, f"Open {otype} trade already exists"

        return True, "OK"

    # ── Position sizing ────────────────────────────────────
    def calculate_position_size(
        self,
        entry_price: float,
        stop_loss: float,
        capital: float = 100_000,
        entry_type: str = "AI",
        score: float = 0.0
    ) -> dict:
        """
        Risk 1% of capital per trade.
        Dynamic scaling applied for Telegram signals (Refinement 3).
        """
        # 1. Base quantity 
        risk_budget = capital * 0.01
        risk_per_unit = abs(entry_price - stop_loss) or entry_price * 0.02
        raw_qty = int(risk_budget / risk_per_unit)

        # 2. Dynamic Scaling (Refinement 3)
        multiplier = 1.0
        if entry_type == "TELEGRAM":
            # Normalize score to 0.0-1.0 if it's on the 0-140 scale
            norm_score = score / 140.0 if score > 1 else score
            
            if norm_score >= 0.90:
                multiplier = 0.75
            elif norm_score >= 0.85:
                multiplier = 0.50
            else:
                multiplier = 0.25
            
            logger.info(f"📊 Scaling Telegram trade (Score:{norm_score:.2f} | Multiplier:{multiplier}x)")

        quantity = max(
            Config.LOT_SIZE,
            (int(raw_qty * multiplier) // Config.LOT_SIZE) * Config.LOT_SIZE,
        )

        actual_risk = risk_per_unit * quantity
        return {
            'quantity': quantity,
            'lots': quantity // Config.LOT_SIZE,
            'risk_amount': round(actual_risk, 2),
            'risk_percent': round(actual_risk / capital * 100, 2),
            'multiplier': multiplier
        }

    # ── Stop-loss & target ─────────────────────────────────
    def calculate_stop_loss(
        self,
        entry_price: float,
        option_type: str,
        atr: Optional[float] = None,
    ) -> float:
        """
        ATR-based if available, else 20% of premium.
        SL is always below entry for bought options.
        """
        sl_dist = atr * 1.5 if atr and atr > 0 else entry_price * (Config.STOP_LOSS_PERCENT / 100)
        sl = entry_price - sl_dist
        # Hard floor: minimum 20% of entry
        return max(sl, entry_price * 0.20)

    def calculate_target(
        self,
        entry_price: float,
        stop_loss: float,
        risk_reward: float = Config.TARGET_REWARD_RATIO,
    ) -> float:
        risk = abs(entry_price - stop_loss)
        return round(entry_price + risk * risk_reward, 2)

    # ── Trailing stop ──────────────────────────────────────
    def trail_stop_loss(
        self,
        trade: Trade,
        current_price: float,
    ) -> float:
        """
        Phase 1 (+10%): Move SL to entry (cost)
        Phase 2 (+20%): Lock 50% of profit
        Returns the new SL (unchanged if not triggered yet).
        """
        pnl_pct = (current_price - trade.entry_price) / trade.entry_price * 100

        if pnl_pct >= Config.LOCK_PROFIT_PERCENT:
            profit = current_price - trade.entry_price
            locked_sl = trade.entry_price + profit * 0.50
            return max(trade.stop_loss, locked_sl)

        if pnl_pct >= Config.TRAIL_TO_COST_PERCENT:
            return max(trade.stop_loss, trade.entry_price)

        return trade.stop_loss

    # ── Trade lifecycle ────────────────────────────────────
    def record_trade(self, trade: Trade):
        stats = self._today()
        stats.trades.append(trade)
        stats.trades_count += 1
        if trade.status == "OPEN":
            self.active_trades.append(trade)
        logger.info(f"Trade recorded: {trade.symbol} @ ₹{trade.entry_price:.2f}")

    def close_trade(self, trade: Trade, exit_price: float, reason: str):
        trade.exit_price = exit_price
        trade.exit_timestamp = datetime.now()
        trade.exit_reason = reason
        trade.current_price = exit_price
        trade.update_pnl()
        trade.status = "CLOSED"

        stats = self._today()
        stats.total_pnl += trade.pnl

        if trade.pnl > 0:
            stats.winning_trades += 1
        else:
            stats.losing_trades += 1

        stats.max_drawdown = min(stats.max_drawdown, stats.total_pnl)

        if trade in self.active_trades:
            self.active_trades.remove(trade)

        logger.info(
            f"Trade closed: {trade.symbol} | "
            f"Exit ₹{exit_price:.2f} | "
            f"P&L ₹{trade.pnl:+.2f} ({trade.pnl_percent:+.1f}%) | "
            f"Reason: {reason}"
        )

    # ── Session queries ────────────────────────────────────
    def get_daily_summary(self) -> dict:
        stats = self._today()
        return {
            'date': stats.date,
            'total_trades': stats.trades_count,
            'winning_trades': stats.winning_trades,
            'losing_trades': stats.losing_trades,
            'win_rate': round(stats.win_rate, 1),
            'total_pnl': round(stats.total_pnl, 2),
            'max_drawdown': round(stats.max_drawdown, 2),
            'trades_remaining': self.max_trades_per_day - stats.trades_count,
            'can_trade': (
                not stats.is_loss_limit_hit
                and stats.trades_count < self.max_trades_per_day
            ),
        }

    def should_stop_trading(self) -> tuple[bool, str]:
        """Check end-of-day / loss-limit shutdown triggers."""
        s = self.get_daily_summary()

        if s['total_pnl'] <= -self.max_daily_loss:
            return True, f"Daily loss limit hit: ₹{abs(s['total_pnl']):.2f}"

        # Stop after 2 consecutive losses
        stats = self._today()
        recent = [t for t in stats.trades if t.status == "CLOSED"][-2:]
        if len(recent) == 2 and all(t.pnl < 0 for t in recent):
            return True, "2 consecutive losses — stopping for discipline"

        return False, ""


# ══════════════════════════════════════════
# TRADE LOGGER
# ══════════════════════════════════════════

class TradeLogger:
    """Append-only file log for every signal and trade event."""

    def __init__(self, log_file: str = Config.LOG_FILE):
        self.log_file = log_file

    def log_signal(self, analysis: dict):
        ts = analysis['timestamp'].strftime("%Y-%m-%d %H:%M:%S")
        self._write(
            f"[{ts}] SIGNAL | {analysis['signal']} | "
            f"Trend:{analysis['trend']} | "
            f"Momentum:{analysis['momentum']} | "
            f"Breakout:{analysis['breakout']}"
        )

    def log_trade_entry(self, trade: Trade):
        ts = trade.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        self._write(
            f"[{ts}] ENTRY | {trade.symbol} | "
            f"Qty:{trade.quantity} | "
            f"Entry:₹{trade.entry_price:.2f} | "
            f"SL:₹{trade.stop_loss:.2f} | "
            f"Target:₹{trade.target:.2f} | "
            f"{trade.entry_reason}"
        )

    def log_trade_exit(self, trade: Trade):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sign = "+" if trade.pnl >= 0 else ""
        self._write(
            f"[{ts}] EXIT | {trade.symbol} | "
            f"Exit:₹{trade.exit_price:.2f} | "
            f"P&L:{sign}₹{trade.pnl:.2f} ({sign}{trade.pnl_percent:.1f}%) | "
            f"{trade.exit_reason}"
        )

    def log_sl_trail(self, trade: Trade, old_sl: float, new_sl: float):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._write(
            f"[{ts}] SL_TRAIL | {trade.symbol} | "
            f"₹{old_sl:.2f} → ₹{new_sl:.2f}"
        )

    def log_error(self, message: str):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._write(f"[{ts}] ERROR | {message}")
        logger.error(message)

    def _write(self, message: str):
        try:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(message + '\n')
        except Exception as e:
            print(f"[TradeLogger] write failed: {e}")
