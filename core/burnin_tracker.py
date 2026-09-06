"""
============================================
📊 BURN-IN METRICS TRACKER — Phase B

Persistent, append-only longitudinal metrics store.

Separates concerns:
    SimulationEngine  → trade lifecycle (open/close)
    MetricsEngine     → in-memory rolling stats
    BurninTracker     → daily snapshots + lifetime evidence

Four metric categories:
    1. Trading Quality   — edge validation
    2. Execution Quality — fill realism (requires Phase A)
    3. Operational Stability — system health
    4. Regime Intelligence — adaptability proof

Persists to: data/burnin_metrics.json
============================================
"""

import json
import os
from datetime import datetime, date
from collections import defaultdict
from typing import Dict, List, Optional

from utils.logger import get_logger
from core.execution_fidelity import ExecutionResult


class BurninTracker:
    """
    Longitudinal burn-in evidence accumulator.

    Records metrics across sessions so readiness scoring
    is based on statistically meaningful history, not
    a single session's in-memory stats.
    """

    PERSIST_PATH = "data/burnin_metrics.json"

    def __init__(self):
        self.logger = get_logger("burnin_tracker")

        # ── Session start ──
        self.session_start = datetime.now()
        self.session_date = date.today().isoformat()

        # ── Trading Quality (lifetime) ──
        self.lifetime_trades = 0
        self.lifetime_wins = 0
        self.lifetime_losses = 0
        self.lifetime_gross_profit = 0.0
        self.lifetime_gross_loss = 0.0
        self.lifetime_net_pnl = 0.0
        self.lifetime_rr_ratios: List[float] = []
        self.lifetime_max_consecutive_losses = 0
        self._current_loss_streak = 0

        # ── Execution Quality (lifetime, populated by Phase A) ──
        self.lifetime_exec_attempts = 0
        self.lifetime_rejected = 0
        self.lifetime_partial_fills = 0
        self.lifetime_slippage_sum = 0.0
        self.lifetime_spread_sum = 0.0
        self.lifetime_latency_sum = 0
        self.exec_quality_scores: List[float] = []

        # ── Operational Stability ──
        self.session_api_failures = 0
        self.lifetime_api_failures = 0
        self.session_circuit_trips = 0
        self.lifetime_circuit_trips = 0
        self.session_seconds_up = 0   # updated on snapshot

        # ── Regime Intelligence ──
        self.regime_stats: Dict[str, Dict] = defaultdict(
            lambda: {"wins": 0, "losses": 0, "pnl": 0.0, "signals_killed": 0, "signals_total": 0}
        )

        # ── Daily snapshots (last 30 days) ──
        self.daily_snapshots: List[Dict] = []

        # ── Load previous state ──
        self._load()
        self.logger.info(
            f"📊 BurninTracker initialized | "
            f"Lifetime trades: {self.lifetime_trades} | "
            f"Net P&L: ₹{self.lifetime_net_pnl:,.0f}"
        )

    # ─────────────────────────────────────────
    # PUBLIC: EVENT HOOKS
    # ─────────────────────────────────────────

    def record_trade_closed(
        self,
        result: str,          # 'WIN' | 'LOSS' | 'BREAK_EVEN'
        net_pnl: float,
        gross_profit: float,
        gross_loss: float,
        rr_ratio: float,
        regime: str = "",
    ):
        """Called by SimulationEngine._close_trade() for each completed trade."""
        self.lifetime_trades += 1
        self.lifetime_net_pnl += net_pnl

        if result == "WIN":
            self.lifetime_wins += 1
            self.lifetime_gross_profit += gross_profit
            self._current_loss_streak = 0
        elif result == "LOSS":
            self.lifetime_losses += 1
            self.lifetime_gross_loss += gross_loss
            self._current_loss_streak += 1
            self.lifetime_max_consecutive_losses = max(
                self.lifetime_max_consecutive_losses,
                self._current_loss_streak,
            )
        else:
            self._current_loss_streak = 0

        if rr_ratio != 0:
            self.lifetime_rr_ratios.append(rr_ratio)

        if regime:
            self.regime_stats[regime]["pnl"] += net_pnl
            if result == "WIN":
                self.regime_stats[regime]["wins"] += 1
            elif result == "LOSS":
                self.regime_stats[regime]["losses"] += 1

    def record_execution(self, exec_result: ExecutionResult, regime: str = ""):
        """Called after each simulated entry by SimulationEngine."""
        self.lifetime_exec_attempts += 1

        if exec_result.rejected:
            self.lifetime_rejected += 1
            return

        if exec_result.fill_ratio < 1.0:
            self.lifetime_partial_fills += 1

        self.lifetime_slippage_sum += exec_result.slippage_pts
        self.lifetime_spread_sum += exec_result.spread_cost_pts
        self.lifetime_latency_sum += exec_result.latency_ms
        self.exec_quality_scores.append(exec_result.execution_quality_score)

    def record_signal_filtered(self, regime: str = "", was_killed: bool = True):
        """Called by SimulationEngine.record_signal()."""
        if regime:
            self.regime_stats[regime]["signals_total"] += 1
            if was_killed:
                self.regime_stats[regime]["signals_killed"] += 1

    def record_api_failure(self):
        """Called by DataManager on API errors."""
        self.session_api_failures += 1
        self.lifetime_api_failures += 1

    def record_circuit_breaker_trip(self):
        """Called by DataManager when circuit breaker trips."""
        self.session_circuit_trips += 1
        self.lifetime_circuit_trips += 1
        self.logger.warning(
            f"⚡ Circuit breaker trip recorded | "
            f"Session trips: {self.session_circuit_trips}"
        )

    # ─────────────────────────────────────────
    # PUBLIC: STATS
    # ─────────────────────────────────────────

    def get_lifetime_stats(self) -> Dict:
        """Complete lifetime statistics for ReadinessScorer and dashboard."""
        trades = max(self.lifetime_trades, 1)
        attempted = max(self.lifetime_exec_attempts, 1)
        wins_losses = max(self.lifetime_wins + self.lifetime_losses, 1)

        win_rate = self.lifetime_wins / wins_losses * 100
        profit_factor = (
            self.lifetime_gross_profit / self.lifetime_gross_loss
            if self.lifetime_gross_loss > 0 else
            (10.0 if self.lifetime_gross_profit > 0 else 0.0)
        )
        avg_rr = (
            sum(self.lifetime_rr_ratios) / len(self.lifetime_rr_ratios)
            if self.lifetime_rr_ratios else 0.0
        )
        expectancy = self.lifetime_net_pnl / wins_losses

        avg_slippage = self.lifetime_slippage_sum / attempted
        avg_spread = self.lifetime_spread_sum / attempted
        avg_latency = self.lifetime_latency_sum / attempted
        rejection_rate = self.lifetime_rejected / attempted * 100
        partial_fill_rate = self.lifetime_partial_fills / attempted * 100
        fill_success_rate = (1.0 - self.lifetime_rejected / attempted) * 100

        avg_exec_quality = (
            sum(self.exec_quality_scores) / len(self.exec_quality_scores)
            if self.exec_quality_scores else 0.0
        )

        # Regime breakdown
        regime_breakdown = {}
        for regime, stats in self.regime_stats.items():
            total = stats["wins"] + stats["losses"]
            regime_breakdown[regime] = {
                "win_rate": round(stats["wins"] / max(total, 1) * 100, 1),
                "pnl": round(stats["pnl"], 0),
                "trades": total,
                "signal_kill_rate": round(
                    stats["signals_killed"] / max(stats["signals_total"], 1) * 100, 1
                ),
            }

        # Uptime estimate
        session_elapsed = (datetime.now() - self.session_start).total_seconds()
        uptime_pct = min(100, (session_elapsed - self.session_api_failures * 30) / max(session_elapsed, 1) * 100)

        return {
            "trading": {
                "lifetime_trades": self.lifetime_trades,
                "wins": self.lifetime_wins,
                "losses": self.lifetime_losses,
                "win_rate": round(win_rate, 1),
                "profit_factor": round(profit_factor, 2),
                "expectancy": round(expectancy, 0),
                "avg_rr": round(avg_rr, 2),
                "max_consecutive_losses": self.lifetime_max_consecutive_losses,
                "net_pnl": round(self.lifetime_net_pnl, 0),
            },
            "execution": {
                "attempts": self.lifetime_exec_attempts,
                "rejected": self.lifetime_rejected,
                "rejection_rate_pct": round(rejection_rate, 2),
                "fill_success_rate_pct": round(fill_success_rate, 2),
                "partial_fills": self.lifetime_partial_fills,
                "partial_fill_rate_pct": round(partial_fill_rate, 2),
                "avg_slippage_pts": round(avg_slippage, 3),
                "avg_spread_pts": round(avg_spread, 3),
                "avg_latency_ms": round(avg_latency, 0),
                "avg_quality_score": round(avg_exec_quality, 1),
            },
            "operational": {
                "session_api_failures": self.session_api_failures,
                "lifetime_api_failures": self.lifetime_api_failures,
                "session_circuit_trips": self.session_circuit_trips,
                "lifetime_circuit_trips": self.lifetime_circuit_trips,
                "uptime_pct": round(uptime_pct, 1),
                "api_failures_per_day": round(self.lifetime_api_failures / max(len(self.daily_snapshots) + 1, 1), 1),
            },
            "regime": regime_breakdown,
            "daily_snapshots": self.daily_snapshots[-30:],
        }

    def get_daily_snapshot(self) -> Dict:
        """Generate and persist today's snapshot."""
        snap = {
            "date": self.session_date,
            "trades": self.lifetime_trades,
            "wins": self.lifetime_wins,
            "losses": self.lifetime_losses,
            "net_pnl": round(self.lifetime_net_pnl, 0),
            "api_failures": self.session_api_failures,
            "circuit_trips": self.session_circuit_trips,
            "exec_attempts": self.lifetime_exec_attempts,
            "rejected": self.lifetime_rejected,
            "avg_slippage": round(
                self.lifetime_slippage_sum / max(self.lifetime_exec_attempts, 1), 3
            ),
        }
        # Merge or append today's snapshot
        existing = [s for s in self.daily_snapshots if s.get("date") != self.session_date]
        self.daily_snapshots = existing + [snap]
        self._save()
        return snap

    # ─────────────────────────────────────────
    # PERSISTENCE
    # ─────────────────────────────────────────

    def _save(self):
        state = {
            "last_saved": datetime.now().isoformat(),
            # Trading
            "lifetime_trades": self.lifetime_trades,
            "lifetime_wins": self.lifetime_wins,
            "lifetime_losses": self.lifetime_losses,
            "lifetime_gross_profit": self.lifetime_gross_profit,
            "lifetime_gross_loss": self.lifetime_gross_loss,
            "lifetime_net_pnl": self.lifetime_net_pnl,
            "lifetime_rr_ratios": self.lifetime_rr_ratios[-200:],
            "lifetime_max_consecutive_losses": self.lifetime_max_consecutive_losses,
            # Execution
            "lifetime_exec_attempts": self.lifetime_exec_attempts,
            "lifetime_rejected": self.lifetime_rejected,
            "lifetime_partial_fills": self.lifetime_partial_fills,
            "lifetime_slippage_sum": self.lifetime_slippage_sum,
            "lifetime_spread_sum": self.lifetime_spread_sum,
            "lifetime_latency_sum": self.lifetime_latency_sum,
            "exec_quality_scores": self.exec_quality_scores[-200:],
            # Operational
            "lifetime_api_failures": self.lifetime_api_failures,
            "lifetime_circuit_trips": self.lifetime_circuit_trips,
            # Regime
            "regime_stats": {k: dict(v) for k, v in self.regime_stats.items()},
            # Snapshots
            "daily_snapshots": self.daily_snapshots[-30:],
        }
        os.makedirs("data", exist_ok=True)
        try:
            with open(self.PERSIST_PATH, "w") as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            self.logger.error(f"BurninTracker save failed: {e}")

    def _load(self):
        if not os.path.exists(self.PERSIST_PATH):
            return
        try:
            with open(self.PERSIST_PATH) as f:
                state = json.load(f)

            self.lifetime_trades = state.get("lifetime_trades", 0)
            self.lifetime_wins = state.get("lifetime_wins", 0)
            self.lifetime_losses = state.get("lifetime_losses", 0)
            self.lifetime_gross_profit = state.get("lifetime_gross_profit", 0.0)
            self.lifetime_gross_loss = state.get("lifetime_gross_loss", 0.0)
            self.lifetime_net_pnl = state.get("lifetime_net_pnl", 0.0)
            self.lifetime_rr_ratios = state.get("lifetime_rr_ratios", [])
            self.lifetime_max_consecutive_losses = state.get("lifetime_max_consecutive_losses", 0)

            self.lifetime_exec_attempts = state.get("lifetime_exec_attempts", 0)
            self.lifetime_rejected = state.get("lifetime_rejected", 0)
            self.lifetime_partial_fills = state.get("lifetime_partial_fills", 0)
            self.lifetime_slippage_sum = state.get("lifetime_slippage_sum", 0.0)
            self.lifetime_spread_sum = state.get("lifetime_spread_sum", 0.0)
            self.lifetime_latency_sum = state.get("lifetime_latency_sum", 0)
            self.exec_quality_scores = state.get("exec_quality_scores", [])

            self.lifetime_api_failures = state.get("lifetime_api_failures", 0)
            self.lifetime_circuit_trips = state.get("lifetime_circuit_trips", 0)

            for regime, stats in state.get("regime_stats", {}).items():
                self.regime_stats[regime].update(stats)

            self.daily_snapshots = state.get("daily_snapshots", [])

            self.logger.info(
                f"📂 BurninTracker loaded | "
                f"Trades: {self.lifetime_trades} | "
                f"Snapshots: {len(self.daily_snapshots)} days"
            )
        except Exception as e:
            self.logger.error(f"BurninTracker load failed: {e}")
