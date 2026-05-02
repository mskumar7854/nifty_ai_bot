"""
============================================
🧪 SIMULATION ENGINE — PAPER TRADING

This is YOUR PROVING GROUND.

Before risking real money, prove the system
works by running it in simulation mode.

What it does:
- Tracks every signal as if it were a real trade
- Records hypothetical P&L
- Measures all performance metrics
- Scores your readiness for live trading
- Generates go-live qualification report

RULE: You MUST pass Phase 1 (simulation)
before moving to Phase 2 (small capital).

No exceptions. No shortcuts.
============================================
"""

import os
import json
import uuid
import numpy as np
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from collections import defaultdict

from models.signals import (
    Signal, SignalType, Direction, Strength,
    MarketSnapshot,
)
from utils.logger import get_logger
from utils.helpers import save_json, load_json, safe_divide
from config.settings import Settings


@dataclass
class SimulatedTrade:
    """A paper trade for simulation"""
    trade_id: str
    timestamp: datetime
    signal_type: SignalType
    direction: Direction
    confidence: float
    grade: str

    # Prices
    entry_price: float
    stop_loss: float
    target_1: float
    target_2: float
    simulated_exit_price: float = 0

    # Size
    lots: int = 1
    qty: int = 50

    # Result (filled when closed)
    gross_pnl: float = 0
    costs: float = 0
    net_pnl: float = 0
    result: str = "OPEN"              # WIN | LOSS | BREAK_EVEN
    exit_reason: str = ""
    hold_minutes: float = 0

    # Context
    regime: str = ""
    session: str = ""
    rsi: float = 0
    vwap_position: str = ""
    vix: float = 0
    confluence: float = 0
    agreement_pct: float = 0

    # Filter info
    filter_score: float = 0
    gates_passed: int = 0
    gates_total: int = 0

    def to_dict(self) -> dict:
        return {
            "id": self.trade_id,
            "time": self.timestamp.isoformat(),
            "signal": self.signal_type.value,
            "direction": self.direction.value,
            "confidence": self.confidence,
            "grade": self.grade,
            "entry": self.entry_price,
            "sl": self.stop_loss,
            "target1": self.target_1,
            "exit": self.simulated_exit_price,
            "gross_pnl": self.gross_pnl,
            "costs": self.costs,
            "net_pnl": self.net_pnl,
            "result": self.result,
            "exit_reason": self.exit_reason,
            "hold_min": self.hold_minutes,
            "regime": self.regime,
            "session": self.session,
            "filter_score": self.filter_score,
        }


@dataclass
class DailySimReport:
    """Daily simulation performance"""
    date: str
    trades: int = 0
    wins: int = 0
    losses: int = 0
    gross_pnl: float = 0
    total_costs: float = 0
    net_pnl: float = 0
    win_rate: float = 0
    best_trade: float = 0
    worst_trade: float = 0
    signals_received: int = 0
    signals_killed: int = 0
    filter_kill_rate: float = 0
    avg_confidence: float = 0
    avg_rr: float = 0


class SimulationEngine:
    """
    Paper trading engine.

    Tracks everything as if trading for real,
    but no actual orders are placed.

    Purpose:
    1. Validate system performance
    2. Build confidence in the system
    3. Qualify for live trading
    4. Identify weaknesses before losing real money
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self.logger = get_logger("simulation")

        # ── Capital Tracking ──
        self.initial_capital = settings.get_capital()
        self.current_capital = self.initial_capital
        self.peak_capital = self.initial_capital

        # ── Trade History ──
        self.all_trades: List[SimulatedTrade] = []
        self.open_trades: Dict[str, SimulatedTrade] = {}
        self.daily_reports: List[DailySimReport] = []

        # ── Running Stats ──
        self.total_signals = 0
        self.total_filtered = 0
        self.total_trades = 0
        self.wins = 0
        self.losses = 0
        self.gross_profit = 0.0
        self.gross_loss = 0.0
        self.total_costs = 0.0
        self.net_pnl = 0.0

        # ── Streaks ──
        self.current_streak = 0
        self.max_win_streak = 0
        self.max_loss_streak = 0

        # ── Drawdown ──
        self.max_drawdown_pct = 0.0
        self.current_drawdown_pct = 0.0

        # ── R:R Tracking ──
        self.rr_ratios: List[float] = []

        # ── Daily ──
        self.today_trades = 0
        self.today_pnl = 0.0
        self.today_date = date.today()

        # ── Equity Curve ──
        self.equity_points: List[Dict] = [{
            "time": datetime.now().isoformat(),
            "equity": self.initial_capital,
        }]

        # ── Per-regime tracking ──
        self.regime_stats: Dict[str, Dict] = defaultdict(
            lambda: {"wins": 0, "losses": 0, "pnl": 0}
        )

        # ── Per-session tracking ──
        self.session_stats: Dict[str, Dict] = defaultdict(
            lambda: {"wins": 0, "losses": 0, "pnl": 0}
        )

        # ── Per-hour tracking ──
        self.hourly_stats: Dict[int, Dict] = {
            h: {"wins": 0, "losses": 0, "pnl": 0}
            for h in range(9, 16)
        }

        # Load previous state
        self._load_state()

        self.logger.info(
            f"🧪 Simulation Engine initialized | "
            f"Capital: ₹{self.initial_capital:,.0f} | "
            f"History: {len(self.all_trades)} trades"
        )

    def record_signal(self, passed: bool):
        """Record that a signal was generated"""
        self.total_signals += 1
        if not passed:
            self.total_filtered += 1

    def open_simulated_trade(
        self,
        signal: Signal,
        snapshot: MarketSnapshot,
        filter_score: float,
        filter_grade: str,
        gates_passed: int,
        gates_total: int,
        costs_estimate: float,
    ) -> SimulatedTrade:
        """Open a paper trade"""

        self._check_daily_reset()

        trade_id = f"SIM-{uuid.uuid4().hex[:6].upper()}"

        # Extract confluence score safely
        confluence_score = 0.0
        if signal.confluence:
            confluence_score = signal.confluence.confluence_ratio * 100

        # Extract regime safely
        regime_str = ""
        if hasattr(signal, 'regime') and signal.regime:
            regime_str = signal.regime.value

        # Extract session safely
        session_str = ""
        if hasattr(signal, 'session_phase') and signal.session_phase:
            session_str = signal.session_phase.value

        # ── 🎲 REALISTIC SLIPPAGE SIMULATION ──
        # Real markets never fill at the signal price.
        # ±0.3% simulates: spread widening, latency, partial fills.
        # This will expose strategies that only work on perfect fills.
        slippage_factor = 1 + np.random.uniform(-0.003, 0.003)
        realistic_entry = round(signal.entry_price * slippage_factor, 2)
        slippage_pts = round(realistic_entry - signal.entry_price, 2)
        
        # ── P0-F: Adjust SL and Targets relative to Fill Price ──
        # If SL is based on signal price instead of fill price, the risk model is off.
        sl_dist = abs(signal.entry_price - signal.stop_loss)
        t1_dist = abs(signal.target_1 - signal.entry_price)
        t2_dist = abs(signal.target_2 - signal.entry_price)
        
        if signal.direction == Direction.BULLISH:
            adjusted_sl = round(realistic_entry - sl_dist, 2)
            adjusted_t1 = round(realistic_entry + t1_dist, 2)
            adjusted_t2 = round(realistic_entry + t2_dist, 2)
        else:
            adjusted_sl = round(realistic_entry + sl_dist, 2)
            adjusted_t1 = round(realistic_entry - t1_dist, 2)
            adjusted_t2 = round(realistic_entry - t2_dist, 2)

        trade = SimulatedTrade(
            trade_id=trade_id,
            timestamp=datetime.now(),
            signal_type=signal.signal_type,
            direction=signal.direction,
            confidence=signal.confidence,
            grade=filter_grade,
            entry_price=realistic_entry,   # ✅ Slippage-adjusted
            stop_loss=adjusted_sl,         # ✅ Slippage-adjusted
            target_1=adjusted_t1,          # ✅ Slippage-adjusted
            target_2=adjusted_t2,          # ✅ Slippage-adjusted
            lots=max(1, signal.position_size // 50),
            qty=signal.position_size if signal.position_size > 0 else 50,
            regime=regime_str,
            session=session_str,
            rsi=snapshot.rsi,
            vwap_position=(
                "above" if snapshot.price > snapshot.vwap
                else "below"
            ),
            vix=snapshot.india_vix,
            confluence=confluence_score,
            agreement_pct=0.0,
            filter_score=filter_score,
            gates_passed=gates_passed,
            gates_total=gates_total,
            costs=costs_estimate,
        )

        self.open_trades[trade_id] = trade
        self.total_trades += 1
        self.today_trades += 1

        self.logger.info(
            f"📝 SIM TRADE OPENED: {trade_id} | "
            f"{signal.signal_type.value} | "
            f"Signal: ₹{signal.entry_price:,.1f} | "
            f"Filled: ₹{realistic_entry:,.1f} (slip: {slippage_pts:+.1f}pts) | "
            f"Grade: {filter_grade} | "
            f"Conf: {signal.confidence:.0f}%"
        )

        return trade

    def update_open_trades(
        self, current_price: float, snapshot: MarketSnapshot
    ) -> List[Dict]:
        """
        Check all open sim trades for SL/TP hits.
        Returns list of closed trade results.
        """

        closed = []

        for tid, trade in list(self.open_trades.items()):
            if trade.result != "OPEN":
                continue

            if trade.direction == Direction.BULLISH:
                if current_price <= trade.stop_loss:
                    self._close_trade(tid, current_price, "STOP_LOSS")
                    closed.append(self.all_trades[-1].to_dict()
                                  if self.all_trades else {})
                elif trade.target_1 > 0 and current_price >= trade.target_1:
                    self._close_trade(tid, trade.target_1, "TARGET_1")
                    closed.append(self.all_trades[-1].to_dict()
                                  if self.all_trades else {})
            else:
                if current_price >= trade.stop_loss:
                    self._close_trade(tid, current_price, "STOP_LOSS")
                    closed.append(self.all_trades[-1].to_dict()
                                  if self.all_trades else {})
                elif trade.target_1 > 0 and current_price <= trade.target_1:
                    self._close_trade(tid, trade.target_1, "TARGET_1")
                    closed.append(self.all_trades[-1].to_dict()
                                  if self.all_trades else {})

            # Time-based exit check (only for still-open trades)
            if tid in self.open_trades:
                hold_time = (
                    datetime.now() - trade.timestamp
                ).total_seconds() / 60

                if hold_time > self.settings.exit.max_hold_time_minutes:
                    self._close_trade(tid, current_price, "TIME_EXIT")
                    closed.append(self.all_trades[-1].to_dict()
                                  if self.all_trades else {})

        return closed

    def _close_trade(
        self, trade_id: str, exit_price: float, reason: str
    ):
        """Close a simulated trade and record results"""

        if trade_id not in self.open_trades:
            return

        trade = self.open_trades[trade_id]
        trade.simulated_exit_price = exit_price
        trade.exit_reason = reason
        trade.hold_minutes = (
            datetime.now() - trade.timestamp
        ).total_seconds() / 60

        # Calculate P&L
        if trade.direction == Direction.BULLISH:
            trade.gross_pnl = (
                exit_price - trade.entry_price
            ) * trade.qty
        else:
            trade.gross_pnl = (
                trade.entry_price - exit_price
            ) * trade.qty

        trade.net_pnl = trade.gross_pnl - trade.costs

        # Determine result
        if trade.net_pnl > 0:
            trade.result = "WIN"
            self.wins += 1
            self.gross_profit += trade.net_pnl

            if self.current_streak >= 0:
                self.current_streak += 1
            else:
                self.current_streak = 1
            self.max_win_streak = max(
                self.max_win_streak, self.current_streak
            )
        elif trade.net_pnl < 0:
            trade.result = "LOSS"
            self.losses += 1
            self.gross_loss += abs(trade.net_pnl)

            if self.current_streak <= 0:
                self.current_streak -= 1
            else:
                self.current_streak = -1
            self.max_loss_streak = max(
                self.max_loss_streak, abs(self.current_streak)
            )
        else:
            trade.result = "BREAK_EVEN"

        # Update capital
        self.total_costs += trade.costs
        self.net_pnl += trade.net_pnl
        self.current_capital += trade.net_pnl
        self.today_pnl += trade.net_pnl

        # Update peak and drawdown
        self.peak_capital = max(
            self.peak_capital, self.current_capital
        )
        if self.peak_capital > 0:
            self.current_drawdown_pct = (
                (self.peak_capital - self.current_capital) /
                self.peak_capital * 100
            )
            self.max_drawdown_pct = max(
                self.max_drawdown_pct,
                self.current_drawdown_pct,
            )

        # R:R
        risk = abs(trade.entry_price - trade.stop_loss) * trade.qty
        if risk > 0:
            rr = trade.net_pnl / risk
            self.rr_ratios.append(rr)

        # Equity curve
        self.equity_points.append({
            "time": datetime.now().isoformat(),
            "equity": self.current_capital,
            "trade_pnl": trade.net_pnl,
        })

        # Regime stats
        if trade.regime:
            if trade.result == "WIN":
                self.regime_stats[trade.regime]["wins"] += 1
            elif trade.result == "LOSS":
                self.regime_stats[trade.regime]["losses"] += 1
            self.regime_stats[trade.regime]["pnl"] += trade.net_pnl

        # Session stats
        if trade.session:
            if trade.result == "WIN":
                self.session_stats[trade.session]["wins"] += 1
            elif trade.result == "LOSS":
                self.session_stats[trade.session]["losses"] += 1
            self.session_stats[trade.session]["pnl"] += trade.net_pnl

        # Hourly stats
        hour = trade.timestamp.hour
        if hour in self.hourly_stats:
            if trade.result == "WIN":
                self.hourly_stats[hour]["wins"] += 1
            elif trade.result == "LOSS":
                self.hourly_stats[hour]["losses"] += 1
            self.hourly_stats[hour]["pnl"] += trade.net_pnl

        # Move to all trades
        self.all_trades.append(trade)

        # Remove from open
        del self.open_trades[trade_id]

        # Save periodically
        if len(self.all_trades) % 5 == 0:
            self._save_state()

        self.logger.info(
            f"{'🟢' if trade.result == 'WIN' else '🔴'} "
            f"SIM TRADE CLOSED: {trade_id} | "
            f"{trade.result} | "
            f"Gross: ₹{trade.gross_pnl:,.0f} | "
            f"Costs: ₹{trade.costs:,.0f} | "
            f"Net: ₹{trade.net_pnl:,.0f} | "
            f"Reason: {reason} | "
            f"Hold: {trade.hold_minutes:.0f}min"
        )

    def _check_daily_reset(self):
        today = date.today()
        if self.today_date != today:
            self._generate_daily_report()
            self.today_date = today
            self.today_trades = 0
            self.today_pnl = 0.0

    def _generate_daily_report(self):
        """Generate end-of-day report"""

        today_trades = [
            t for t in self.all_trades
            if t.timestamp.date() == self.today_date
        ]

        if not today_trades:
            return

        wins = sum(1 for t in today_trades if t.result == "WIN")
        losses = sum(
            1 for t in today_trades if t.result == "LOSS"
        )
        total = wins + losses

        report = DailySimReport(
            date=self.today_date.isoformat(),
            trades=len(today_trades),
            wins=wins,
            losses=losses,
            gross_pnl=sum(t.gross_pnl for t in today_trades),
            total_costs=sum(t.costs for t in today_trades),
            net_pnl=sum(t.net_pnl for t in today_trades),
            win_rate=safe_divide(wins * 100, total),
            best_trade=max(
                (t.net_pnl for t in today_trades), default=0
            ),
            worst_trade=min(
                (t.net_pnl for t in today_trades), default=0
            ),
            signals_received=self.total_signals,
            signals_killed=self.total_filtered,
            filter_kill_rate=safe_divide(
                self.total_filtered * 100, self.total_signals
            ),
            avg_confidence=np.mean(
                [t.confidence for t in today_trades]
            ) if today_trades else 0,
            avg_rr=np.mean(self.rr_ratios[-len(today_trades):]
            ) if self.rr_ratios else 0,
        )

        self.daily_reports.append(report)

    # ══════════════════════════════════════
    # READINESS ASSESSMENT
    # ══════════════════════════════════════

    def get_readiness_score(self) -> Dict:
        """
        The GO-LIVE QUALIFICATION TEST.

        12-point checklist that determines
        if you're ready for real money.
        """

        checks = []
        total_score = 0
        total_weight = 0

        completed = [
            t for t in self.all_trades
            if t.result in ("WIN", "LOSS")
        ]
        total_trades = len(completed)
        trading_days = len(set(
            t.timestamp.date() for t in self.all_trades
        ))

        # ── CHECK 1: Minimum Trades ──
        min_trades = self.settings.system_mode.phase_1_min_trades
        c1_pass = total_trades >= min_trades
        c1_score = min(100, safe_divide(total_trades, min_trades) * 100)
        checks.append({
            "name": "Minimum Trades",
            "pass": c1_pass,
            "score": c1_score,
            "detail": f"{total_trades}/{min_trades} trades",
            "weight": 10,
        })
        total_score += c1_score * 10
        total_weight += 10

        # ── CHECK 2: Minimum Days ──
        min_days = self.settings.system_mode.phase_1_min_days
        c2_pass = trading_days >= min_days
        c2_score = min(100, safe_divide(trading_days, min_days) * 100)
        checks.append({
            "name": "Minimum Days",
            "pass": c2_pass,
            "score": c2_score,
            "detail": f"{trading_days}/{min_days} days",
            "weight": 5,
        })
        total_score += c2_score * 5
        total_weight += 5

        # ── CHECK 3: Win Rate ──
        min_wr = self.settings.system_mode.phase_1_min_win_rate
        actual_wr = safe_divide(self.wins * 100, total_trades)
        c3_pass = actual_wr >= min_wr
        c3_score = min(100, safe_divide(actual_wr, min_wr) * 100) if min_wr > 0 else 50
        checks.append({
            "name": "Win Rate",
            "pass": c3_pass,
            "score": c3_score,
            "detail": f"{actual_wr:.1f}% (need {min_wr}%)",
            "weight": 20,
        })
        total_score += c3_score * 20
        total_weight += 20

        # ── CHECK 4: Max Drawdown ──
        max_dd = self.settings.system_mode.phase_1_max_drawdown
        c4_pass = self.max_drawdown_pct <= max_dd
        c4_score = max(0, 100 - safe_divide(
            self.max_drawdown_pct, max_dd) * 100) if max_dd > 0 else 50
        checks.append({
            "name": "Max Drawdown",
            "pass": c4_pass,
            "score": c4_score,
            "detail": f"{self.max_drawdown_pct:.1f}% (max {max_dd}%)",
            "weight": 15,
        })
        total_score += c4_score * 15
        total_weight += 15

        # ── CHECK 5: Positive Net P&L ──
        c5_pass = self.net_pnl > 0
        c5_score = 100 if c5_pass else 0
        checks.append({
            "name": "Net Profitable",
            "pass": c5_pass,
            "score": c5_score,
            "detail": f"₹{self.net_pnl:,.0f}",
            "weight": 15,
        })
        total_score += c5_score * 15
        total_weight += 15

        # ── CHECK 6: Profit Factor > 1.5 ──
        pf = safe_divide(self.gross_profit, self.gross_loss)
        c6_pass = pf >= 1.5
        c6_score = min(100, safe_divide(pf, 1.5) * 100) if pf > 0 else 0
        checks.append({
            "name": "Profit Factor",
            "pass": c6_pass,
            "score": c6_score,
            "detail": f"{pf:.2f} (need 1.5+)",
            "weight": 10,
        })
        total_score += c6_score * 10
        total_weight += 10

        # ── CHECK 7: Average R:R > 1.0 ──
        avg_rr = np.mean(self.rr_ratios) if self.rr_ratios else 0
        c7_pass = avg_rr >= 1.0
        c7_score = min(100, avg_rr * 100) if avg_rr > 0 else 0
        checks.append({
            "name": "Average R:R",
            "pass": c7_pass,
            "score": c7_score,
            "detail": f"{avg_rr:.2f} (need 1.0+)",
            "weight": 10,
        })
        total_score += c7_score * 10
        total_weight += 10

        # ── CHECK 8: No Catastrophic Losses ──
        max_single_loss = min(
            (t.net_pnl for t in completed), default=0
        )
        capital = self.initial_capital
        max_loss_pct = safe_divide(abs(max_single_loss), capital) * 100
        c8_pass = max_loss_pct <= 5.0
        c8_score = max(0, 100 - max_loss_pct * 10)
        checks.append({
            "name": "No Catastrophic Loss",
            "pass": c8_pass,
            "score": c8_score,
            "detail": f"Max loss: {max_loss_pct:.1f}% (max 5%)",
            "weight": 5,
        })
        total_score += c8_score * 5
        total_weight += 5

        # ── CHECK 9: Filter Working ──
        filter_rate = safe_divide(
            self.total_filtered * 100, self.total_signals
        )
        c9_pass = 50 <= filter_rate <= 85
        c9_score = 100 if c9_pass else 50
        checks.append({
            "name": "Filter Effectiveness",
            "pass": c9_pass,
            "score": c9_score,
            "detail": f"{filter_rate:.0f}% killed (need 50-85%)",
            "weight": 5,
        })
        total_score += c9_score * 5
        total_weight += 5

        # ── CHECK 10: Trades Per Day ──
        avg_trades = safe_divide(total_trades, max(trading_days, 1))
        c10_pass = 1 <= avg_trades <= 4
        c10_score = 100 if c10_pass else 50
        checks.append({
            "name": "Trade Frequency",
            "pass": c10_pass,
            "score": c10_score,
            "detail": f"{avg_trades:.1f}/day (need 1-4)",
            "weight": 3,
        })
        total_score += c10_score * 3
        total_weight += 3

        # ── CHECK 11: No Max Loss Streak > 4 ──
        c11_pass = self.max_loss_streak <= 4
        c11_score = 100 if c11_pass else 30
        checks.append({
            "name": "Max Loss Streak",
            "pass": c11_pass,
            "score": c11_score,
            "detail": f"{self.max_loss_streak} (max 4)",
            "weight": 2,
        })
        total_score += c11_score * 2
        total_weight += 2

        # ── CHECK 12: Costs Under Control ──
        total_volume = self.gross_profit + self.gross_loss
        cost_pct = safe_divide(self.total_costs * 100, total_volume)
        c12_pass = cost_pct < 20
        c12_score = max(0, 100 - cost_pct * 3)
        checks.append({
            "name": "Cost Management",
            "pass": c12_pass,
            "score": c12_score,
            "detail": f"Costs = {cost_pct:.1f}% of turnover",
            "weight": 0,  # bonus
        })

        # ── FINAL SCORE ──
        final_score = safe_divide(total_score, max(total_weight, 1))
        all_critical_passed = all(
            c["pass"] for c in checks
            if c["weight"] >= 10
        )

        # Determine readiness
        if final_score >= 80 and all_critical_passed:
            readiness = "READY"
            recommendation = (
                "✅ System QUALIFIED for Phase 2 "
                "(Small Capital Trading)"
            )
        elif final_score >= 60:
            readiness = "ALMOST"
            recommendation = (
                "⚠️ Close but not ready — "
                "continue simulation for more data"
            )
        else:
            readiness = "NOT_READY"
            recommendation = (
                "🚫 System needs improvement — "
                "review strategy and continue simulation"
            )

        return {
            "readiness": readiness,
            "final_score": round(final_score, 1),
            "recommendation": recommendation,
            "checks": checks,
            "all_critical_passed": all_critical_passed,
            "summary": {
                "trades": total_trades,
                "days": trading_days,
                "win_rate": f"{actual_wr:.1f}%",
                "net_pnl": f"₹{self.net_pnl:,.0f}",
                "profit_factor": f"{pf:.2f}",
                "max_drawdown": f"{self.max_drawdown_pct:.1f}%",
                "avg_rr": f"{avg_rr:.2f}",
                "current_capital": f"₹{self.current_capital:,.0f}",
            },
        }

    def get_full_report(self) -> Dict:
        """Complete simulation report"""

        completed = [
            t for t in self.all_trades
            if t.result in ("WIN", "LOSS")
        ]
        total = len(completed)

        return {
            "overview": {
                "mode": "SIMULATION",
                "start_capital": f"₹{self.initial_capital:,.0f}",
                "current_capital": f"₹{self.current_capital:,.0f}",
                "net_pnl": f"₹{self.net_pnl:,.0f}",
                "return_pct": f"{safe_divide(self.net_pnl, self.initial_capital) * 100:.2f}%",
                "total_trades": total,
                "win_rate": f"{safe_divide(self.wins * 100, total):.1f}%",
                "profit_factor": f"{safe_divide(self.gross_profit, self.gross_loss):.2f}",
                "max_drawdown": f"{self.max_drawdown_pct:.1f}%",
            },
            "filter_performance": {
                "total_signals": self.total_signals,
                "filtered_out": self.total_filtered,
                "filter_rate": f"{safe_divide(self.total_filtered * 100, self.total_signals):.0f}%",
                "trades_taken": total,
            },
            "regime_breakdown": {
                regime: {
                    "win_rate": f"{safe_divide(s['wins'] * 100, s['wins'] + s['losses']):.0f}%",
                    "pnl": f"₹{s['pnl']:,.0f}",
                    "trades": s["wins"] + s["losses"],
                }
                for regime, s in self.regime_stats.items()
                if s["wins"] + s["losses"] > 0
            },
            "session_breakdown": {
                session: {
                    "win_rate": f"{safe_divide(s['wins'] * 100, s['wins'] + s['losses']):.0f}%",
                    "pnl": f"₹{s['pnl']:,.0f}",
                    "trades": s["wins"] + s["losses"],
                }
                for session, s in self.session_stats.items()
                if s["wins"] + s["losses"] > 0
            },
            "hourly_heatmap": {
                f"{h}:00": {
                    "win_rate": f"{safe_divide(s['wins'] * 100, s['wins'] + s['losses']):.0f}%",
                    "pnl": f"₹{s['pnl']:,.0f}",
                }
                for h, s in self.hourly_stats.items()
                if s["wins"] + s["losses"] > 0
            },
            "equity_curve": self.equity_points[-200:],
            "readiness": self.get_readiness_score(),
            "recent_trades": [
                t.to_dict() for t in self.all_trades[-20:]
            ],
        }

    # ══════════════════════════════════════
    # PERSISTENCE
    # ══════════════════════════════════════

    def _save_state(self):
        state = {
            "current_capital": self.current_capital,
            "peak_capital": self.peak_capital,
            "net_pnl": self.net_pnl,
            "wins": self.wins,
            "losses": self.losses,
            "gross_profit": self.gross_profit,
            "gross_loss": self.gross_loss,
            "total_costs": self.total_costs,
            "max_drawdown_pct": self.max_drawdown_pct,
            "total_signals": self.total_signals,
            "total_filtered": self.total_filtered,
            "rr_ratios": self.rr_ratios[-100:],
            "trades": [t.to_dict() for t in self.all_trades[-200:]],
            "last_saved": datetime.now().isoformat(),
        }
        save_json(state, "data/simulation_state.json")

    def _load_state(self):
        state = load_json("data/simulation_state.json")
        if state:
            self.current_capital = state.get(
                "current_capital", self.initial_capital
            )
            self.peak_capital = state.get(
                "peak_capital", self.initial_capital
            )
            self.net_pnl = state.get("net_pnl", 0)
            self.wins = state.get("wins", 0)
            self.losses = state.get("losses", 0)
            self.gross_profit = state.get("gross_profit", 0)
            self.gross_loss = state.get("gross_loss", 0)
            self.total_costs = state.get("total_costs", 0)
            self.max_drawdown_pct = state.get("max_drawdown_pct", 0)
            self.total_signals = state.get("total_signals", 0)
            self.total_filtered = state.get("total_filtered", 0)
            self.rr_ratios = state.get("rr_ratios", [])

            self.logger.info(
                f"Loaded simulation state | "
                f"Capital: ₹{self.current_capital:,.0f} | "
                f"P&L: ₹{self.net_pnl:,.0f} | "
                f"Trades: {self.wins + self.losses}"
            )
