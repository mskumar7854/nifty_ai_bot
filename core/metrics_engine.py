"""
============================================
📊 LIVE METRICS ENGINE

Real-time performance tracking:
- Win rate (rolling)
- Average R:R
- Profit factor
- Drawdown curve
- Agent contribution analysis
- Equity curve
- Daily P&L
- Regime performance overlay
- Time-of-day heatmap
============================================
"""

import numpy as np
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional
from collections import defaultdict, deque

from utils.logger import get_logger
from utils.helpers import safe_divide


class MetricsEngine:
    """Real-time performance analytics"""

    def __init__(self, capital: float = 100000):
        self.logger = get_logger("metrics")
        self.initial_capital = capital

        # ── Trade Records ──
        self.all_trades: List[Dict] = []

        # ── Running Metrics ──
        self.total_trades = 0
        self.wins = 0
        self.losses = 0
        self.break_evens = 0

        self.gross_profit = 0.0
        self.gross_loss = 0.0
        self.net_pnl = 0.0

        # ── Equity Curve ──
        self.equity_curve: deque = deque(maxlen=5000)
        self.equity_curve.append({
            "time": datetime.now().isoformat(),
            "equity": capital,
        })

        # ── Drawdown Tracking ──
        self.peak_equity = capital
        self.current_drawdown = 0.0
        self.max_drawdown = 0.0
        self.drawdown_history: deque = deque(maxlen=5000)

        # ── Daily P&L ──
        self.daily_pnl: Dict[str, float] = {}

        # ── Agent Contribution ──
        self.agent_contributions: Dict[str, Dict] = defaultdict(
            lambda: {
                "times_agreed_with_win": 0,
                "times_agreed_with_loss": 0,
                "total_signals": 0,
                "contribution_score": 50.0,
            }
        )

        # ── Hourly Performance ──
        self.hourly_performance: Dict[int, Dict] = {
            h: {"wins": 0, "losses": 0, "pnl": 0}
            for h in range(9, 16)
        }

        # ── Regime Performance ──
        self.regime_performance: Dict[str, Dict] = defaultdict(
            lambda: {"wins": 0, "losses": 0, "pnl": 0}
        )

        # ── Streak Tracking ──
        self.current_streak = 0
        self.max_win_streak = 0
        self.max_loss_streak = 0

        # ── R:R Tracking ──
        self.rr_ratios: List[float] = []

    def record_trade(
        self,
        entry_price: float,
        exit_price: float,
        direction: str,
        pnl: float,
        result: str,
        confidence: float,
        agent_votes: Dict,
        regime: str = "",
        entry_hour: int = 10,
        costs: float = 0,
        risk_amount: float = 0,
    ):
        """Record a completed trade"""

        self.total_trades += 1
        net_pnl = pnl - costs

        trade = {
            "id": self.total_trades,
            "time": datetime.now().isoformat(),
            "entry": entry_price,
            "exit": exit_price,
            "direction": direction,
            "gross_pnl": pnl,
            "costs": costs,
            "net_pnl": net_pnl,
            "result": result,
            "confidence": confidence,
            "regime": regime,
            "hour": entry_hour,
        }
        self.all_trades.append(trade)

        # ── Win/Loss ──
        if result == "WIN":
            self.wins += 1
            self.gross_profit += net_pnl

            if self.current_streak >= 0:
                self.current_streak += 1
            else:
                self.current_streak = 1
            self.max_win_streak = max(
                self.max_win_streak, self.current_streak
            )
        elif result == "LOSS":
            self.losses += 1
            self.gross_loss += abs(net_pnl)

            if self.current_streak <= 0:
                self.current_streak -= 1
            else:
                self.current_streak = -1
            self.max_loss_streak = max(
                self.max_loss_streak, abs(self.current_streak)
            )
        else:
            self.break_evens += 1

        self.net_pnl += net_pnl

        # ── R:R ──
        if risk_amount > 0 and net_pnl != 0:
            rr = abs(net_pnl) / risk_amount
            if result == "LOSS":
                rr = -rr
            self.rr_ratios.append(rr)

        # ── Equity ──
        current_equity = self.initial_capital + self.net_pnl
        self.equity_curve.append({
            "time": datetime.now().isoformat(),
            "equity": current_equity,
        })

        # ── Drawdown ──
        self.peak_equity = max(self.peak_equity, current_equity)
        self.current_drawdown = (
            (self.peak_equity - current_equity) /
            self.peak_equity * 100
        ) if self.peak_equity > 0 else 0
        self.max_drawdown = max(
            self.max_drawdown, self.current_drawdown
        )
        self.drawdown_history.append({
            "time": datetime.now().isoformat(),
            "drawdown": self.current_drawdown,
        })

        # ── Daily ──
        today = date.today().isoformat()
        self.daily_pnl[today] = self.daily_pnl.get(
            today, 0
        ) + net_pnl

        # ── Hourly ──
        if entry_hour in self.hourly_performance:
            if result == "WIN":
                self.hourly_performance[entry_hour]["wins"] += 1
            elif result == "LOSS":
                self.hourly_performance[entry_hour]["losses"] += 1
            self.hourly_performance[entry_hour]["pnl"] += net_pnl

        # ── Regime ──
        if regime:
            if result == "WIN":
                self.regime_performance[regime]["wins"] += 1
            elif result == "LOSS":
                self.regime_performance[regime]["losses"] += 1
            self.regime_performance[regime]["pnl"] += net_pnl

        # ── Agent Contributions ──
        for agent_name, vote in agent_votes.items():
            agent_dir = vote.get("dir", "NEUTRAL")
            self.agent_contributions[agent_name][
                "total_signals"
            ] += 1

            if agent_dir == direction and result == "WIN":
                self.agent_contributions[agent_name][
                    "times_agreed_with_win"
                ] += 1
            elif agent_dir == direction and result == "LOSS":
                self.agent_contributions[agent_name][
                    "times_agreed_with_loss"
                ] += 1

            # Update contribution score
            total = self.agent_contributions[agent_name][
                "total_signals"
            ]
            correct = self.agent_contributions[agent_name][
                "times_agreed_with_win"
            ]
            if total >= 5:
                self.agent_contributions[agent_name][
                    "contribution_score"
                ] = round(correct / total * 100, 1)

    def get_full_metrics(self) -> Dict:
        """Complete metrics dashboard data"""

        current_equity = self.initial_capital + self.net_pnl
        total = self.wins + self.losses

        return {
            "summary": {
                "total_trades": self.total_trades,
                "wins": self.wins,
                "losses": self.losses,
                "break_evens": self.break_evens,
                "win_rate": f"{safe_divide(self.wins * 100, total):.1f}%",
                "gross_profit": f"₹{self.gross_profit:,.0f}",
                "gross_loss": f"₹{self.gross_loss:,.0f}",
                "net_pnl": f"₹{self.net_pnl:,.0f}",
                "profit_factor": f"{safe_divide(self.gross_profit, self.gross_loss):.2f}",
                "avg_win": f"₹{safe_divide(self.gross_profit, self.wins):,.0f}",
                "avg_loss": f"₹{safe_divide(self.gross_loss, self.losses):,.0f}",
                "avg_rr": f"{np.mean(self.rr_ratios):.2f}" if self.rr_ratios else "N/A",
                "expectancy": f"₹{safe_divide(self.net_pnl, total):,.0f}",
            },
            "capital": {
                "initial": f"₹{self.initial_capital:,.0f}",
                "current": f"₹{current_equity:,.0f}",
                "peak": f"₹{self.peak_equity:,.0f}",
                "return_pct": f"{(current_equity - self.initial_capital) / self.initial_capital * 100:.2f}%",
            },
            "risk": {
                "current_drawdown": f"{self.current_drawdown:.2f}%",
                "max_drawdown": f"{self.max_drawdown:.2f}%",
                "current_streak": self.current_streak,
                "max_win_streak": self.max_win_streak,
                "max_loss_streak": self.max_loss_streak,
            },
            "equity_curve": list(self.equity_curve)[-100:],
            "drawdown_curve": list(self.drawdown_history)[-100:],
            "daily_pnl": dict(
                list(self.daily_pnl.items())[-30:]
            ),
            "hourly_heatmap": {
                str(h): {
                    "win_rate": f"{safe_divide(v['wins'] * 100, v['wins'] + v['losses']):.0f}%",
                    "pnl": f"₹{v['pnl']:,.0f}",
                    "trades": v['wins'] + v['losses'],
                }
                for h, v in self.hourly_performance.items()
                if v['wins'] + v['losses'] > 0
            },
            "regime_performance": {
                regime: {
                    "win_rate": f"{safe_divide(v['wins'] * 100, v['wins'] + v['losses']):.0f}%",
                    "pnl": f"₹{v['pnl']:,.0f}",
                    "trades": v['wins'] + v['losses'],
                }
                for regime, v in self.regime_performance.items()
                if v['wins'] + v['losses'] > 0
            },
            "agent_contributions": {
                agent: {
                    "score": f"{data['contribution_score']:.0f}%",
                    "signals": data['total_signals'],
                    "correct": data['times_agreed_with_win'],
                }
                for agent, data in sorted(
                    self.agent_contributions.items(),
                    key=lambda x: x[1]['contribution_score'],
                    reverse=True,
                )
                if data['total_signals'] >= 3
            },
        }
