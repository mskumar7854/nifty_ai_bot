"""
============================================
PAPER TRADING TRACKER
============================================
Explicit paper-trading mode with:
  • Simulated fills (no real orders)
  • Per-trade journal
  • Daily scorecard vs go-live targets
  • Readiness report (3-5 day assessment)

Run this BEFORE touching real capital.

Qualification targets:
  Win rate   ≥ 55%
  RR ratio   ≥ 1.5 (average)
  Max DD/day ≤ ₹2,000
  Trades/day ≤ 3
  Min sample 15 trades over 3+ days
============================================
"""

import json
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime, date
from typing import List, Optional, Dict
import logging

logger = logging.getLogger("paper_trader")


# ══════════════════════════════════════════
# QUALIFICATION TARGETS
# ══════════════════════════════════════════

TARGETS = {
    'min_win_rate_pct':  55.0,
    'min_avg_rr':         1.5,
    'max_daily_loss':  2000.0,
    'max_trades_day':      3,
    'min_trades_total':   15,
    'min_days':            3,
}


# ══════════════════════════════════════════
# DATA CLASSES
# ══════════════════════════════════════════

@dataclass
class PaperTrade:
    """One simulated trade — fully tracked."""
    id: int
    signal: str                # BUY_CE | BUY_PE
    symbol: str
    option_type: str           # CE | PE
    strike: int
    expiry: str
    entry_price: float
    stop_loss: float
    target: float
    quantity: int
    entry_time: str            # ISO string
    source: str = "STRATEGY"  # STRATEGY | COMBINED | AI_ONLY

    # Filled on close
    exit_price: Optional[float] = None
    exit_time:  Optional[str]   = None
    exit_reason: str = ""
    pnl: float = 0.0
    pnl_pct: float = 0.0
    rr_achieved: float = 0.0
    status: str = "OPEN"       # OPEN | CLOSED


@dataclass
class DailyScore:
    """Scorecard for one trading day."""
    date: str
    trades: int = 0
    wins: int = 0
    losses: int = 0
    gross_pnl: float = 0.0
    max_loss: float = 0.0       # worst single loss
    total_rr: float = 0.0       # sum of RR achieved

    @property
    def win_rate(self) -> float:
        return self.wins / self.trades * 100 if self.trades else 0.0

    @property
    def avg_rr(self) -> float:
        return self.total_rr / self.trades if self.trades else 0.0

    @property
    def target_met(self) -> dict:
        return {
            'win_rate':  self.win_rate >= TARGETS['min_win_rate_pct'],
            'avg_rr':    self.avg_rr   >= TARGETS['min_avg_rr'],
            'max_loss':  self.gross_pnl >= -TARGETS['max_daily_loss'],
            'trade_cnt': self.trades   <= TARGETS['max_trades_day'],
        }


# ══════════════════════════════════════════
# PAPER TRADER
# ══════════════════════════════════════════

class PaperTrader:
    """
    Drop-in replacement for TradeExecutor during simulation.

    Usage:
        paper = PaperTrader()
        trade = paper.open_trade(signal, analysis, entry_price, sl, target, qty)
        paper.close_trade(trade.id, exit_price, "SL hit")
        report = paper.get_readiness_report()
    """

    STATE_FILE = "nifty_strategy/paper_trades.json"

    def __init__(self):
        self.trades: List[PaperTrade] = []
        self._next_id = 1
        self.daily: Dict[str, DailyScore] = {}
        self._load_state()

    # ── Trade lifecycle ────────────────────────────────────
    def open_trade(
        self,
        signal: str,
        symbol: str,
        option_type: str,
        strike: int,
        expiry: str,
        entry_price: float,
        stop_loss: float,
        target: float,
        quantity: int,
        source: str = "STRATEGY",
    ) -> PaperTrade:
        """Simulate order fill at entry_price (no slippage in paper mode)."""
        trade = PaperTrade(
            id=self._next_id,
            signal=signal,
            symbol=symbol,
            option_type=option_type,
            strike=strike,
            expiry=expiry,
            entry_price=entry_price,
            stop_loss=stop_loss,
            target=target,
            quantity=quantity,
            entry_time=datetime.now().isoformat(),
            source=source,
        )
        self._next_id += 1
        self.trades.append(trade)

        logger.info(
            f"📝 PAPER OPEN #{trade.id} | {symbol} | "
            f"Entry ₹{entry_price:.2f} | "
            f"SL ₹{stop_loss:.2f} | T ₹{target:.2f}"
        )
        self._save_state()
        return trade

    def close_trade(
        self,
        trade_id: int,
        exit_price: float,
        reason: str,
    ) -> Optional[PaperTrade]:
        """Close a paper trade and update scorecards."""
        trade = self._get_trade(trade_id)
        if trade is None or trade.status != "OPEN":
            return None

        trade.exit_price  = exit_price
        trade.exit_time   = datetime.now().isoformat()
        trade.exit_reason = reason
        trade.status      = "CLOSED"

        # P&L
        trade.pnl     = (exit_price - trade.entry_price) * trade.quantity
        trade.pnl_pct = (exit_price - trade.entry_price) / trade.entry_price * 100

        # R:R achieved
        risk = abs(trade.entry_price - trade.stop_loss)
        if risk > 0:
            trade.rr_achieved = (exit_price - trade.entry_price) / risk

        won = trade.pnl > 0
        sign = "✅ WIN" if won else "❌ LOSS"
        logger.info(
            f"📝 PAPER CLOSE #{trade.id} | {sign} | "
            f"Exit ₹{exit_price:.2f} | "
            f"P&L ₹{trade.pnl:+.2f} | "
            f"RR {trade.rr_achieved:.2f} | {reason}"
        )

        self._update_daily(trade)
        self._save_state()
        return trade

    def update_sl(self, trade_id: int, new_sl: float) -> Optional[PaperTrade]:
        """Trail stop loss on a paper trade."""
        trade = self._get_trade(trade_id)
        if trade and trade.status == "OPEN":
            old = trade.stop_loss
            trade.stop_loss = new_sl
            logger.info(f"📝 PAPER SL trail #{trade_id}: ₹{old:.2f} → ₹{new_sl:.2f}")
            self._save_state()
        return trade

    def check_exits(self, current_prices: Dict[int, float]) -> List[PaperTrade]:
        """
        Auto-close trades that hit SL or target.
        Pass {trade_id: current_price} dict.
        """
        closed = []
        for trade in self.open_trades:
            price = current_prices.get(trade.id)
            if price is None:
                continue
            if price <= trade.stop_loss:
                self.close_trade(trade.id, price, "SL hit")
                closed.append(trade)
            elif price >= trade.target:
                self.close_trade(trade.id, price, "Target hit")
                closed.append(trade)
        return closed

    # ── Queries ────────────────────────────────────────────
    @property
    def open_trades(self) -> List[PaperTrade]:
        return [t for t in self.trades if t.status == "OPEN"]

    @property
    def closed_trades(self) -> List[PaperTrade]:
        return [t for t in self.trades if t.status == "CLOSED"]

    def get_daily_score(self, day: Optional[str] = None) -> DailyScore:
        day = day or date.today().isoformat()
        return self.daily.get(day, DailyScore(date=day))

    # ── Readiness Report ───────────────────────────────────
    def get_readiness_report(self) -> dict:
        """
        The critical go/no-go assessment.
        Must pass ALL targets before going live.
        """
        closed = self.closed_trades
        total = len(closed)
        days  = len(self.daily)

        wins   = sum(1 for t in closed if t.pnl > 0)
        losses = total - wins

        win_rate = wins / total * 100 if total else 0.0
        avg_rr   = (
            sum(t.rr_achieved for t in closed) / total if total else 0.0
        )
        total_pnl = sum(t.pnl for t in closed)
        worst_day = min(
            (s.gross_pnl for s in self.daily.values()), default=0.0
        )

        # 12-point checklist
        checks = [
            {
                'name':   'Min 15 trades',
                'pass':   total >= TARGETS['min_trades_total'],
                'value':  str(total),
                'target': str(TARGETS['min_trades_total']),
            },
            {
                'name':   'Min 3 days',
                'pass':   days >= TARGETS['min_days'],
                'value':  str(days),
                'target': str(TARGETS['min_days']),
            },
            {
                'name':   'Win rate ≥ 55%',
                'pass':   win_rate >= TARGETS['min_win_rate_pct'],
                'value':  f"{win_rate:.1f}%",
                'target': f"{TARGETS['min_win_rate_pct']}%",
            },
            {
                'name':   'Avg RR ≥ 1.5',
                'pass':   avg_rr >= TARGETS['min_avg_rr'],
                'value':  f"{avg_rr:.2f}",
                'target': str(TARGETS['min_avg_rr']),
            },
            {
                'name':   'No day > ₹2,000 loss',
                'pass':   worst_day >= -TARGETS['max_daily_loss'],
                'value':  f"₹{worst_day:+,.0f}",
                'target': f"≥ -₹{TARGETS['max_daily_loss']:,.0f}",
            },
            {
                'name':   '≤ 3 trades/day avg',
                'pass':   (total / max(days, 1)) <= TARGETS['max_trades_day'],
                'value':  f"{total/max(days,1):.1f}",
                'target': str(TARGETS['max_trades_day']),
            },
            {
                'name':   'Positive total P&L',
                'pass':   total_pnl > 0,
                'value':  f"₹{total_pnl:+,.0f}",
                'target': "> ₹0",
            },
            {
                'name':   'No 3 consecutive losses',
                'pass':   not self._has_3_consec_losses(closed),
                'value':  "Yes" if self._has_3_consec_losses(closed) else "No",
                'target': "No",
            },
            {
                'name':   'Win rate in last 5 trades',
                'pass':   self._recent_win_rate(closed, 5) >= 40.0,
                'value':  f"{self._recent_win_rate(closed, 5):.0f}%",
                'target': "≥ 40%",
            },
            {
                'name':   'Signals not overtrading',
                'pass':   self._max_day_trades() <= TARGETS['max_trades_day'],
                'value':  str(self._max_day_trades()),
                'target': f"≤ {TARGETS['max_trades_day']}",
            },
        ]

        passed_count = sum(1 for c in checks if c['pass'])
        score = passed_count / len(checks) * 100

        if score >= 90 and total >= TARGETS['min_trades_total']:
            readiness = "🟢 READY — Go live with small capital"
        elif score >= 70:
            readiness = "🟡 ALMOST — Continue paper trading"
        else:
            readiness = "🔴 NOT READY — Review and fix failing checks"

        return {
            'readiness':    readiness,
            'score':        round(score, 1),
            'total_trades': total,
            'days_tracked': days,
            'win_rate':     f"{win_rate:.1f}%",
            'avg_rr':       f"{avg_rr:.2f}",
            'total_pnl':    f"₹{total_pnl:+,.0f}",
            'worst_day':    f"₹{worst_day:+,.0f}",
            'checks':       checks,
            'next_step': (
                "Update SYSTEM_MODE=SMALL_CAPITAL in .env and deploy ₹5,000-₹10,000"
                if score >= 90 else
                "Keep paper trading. Focus on failing checks above."
            ),
        }

    def print_report(self):
        """Pretty-print the readiness report to console."""
        r = self.get_readiness_report()
        sep = "═" * 52
        print(f"\n{sep}")
        print(f"  📋 PAPER TRADING READINESS REPORT")
        print(sep)
        print(f"  Status  : {r['readiness']}")
        print(f"  Score   : {r['score']}/100")
        print(f"  Trades  : {r['total_trades']} over {r['days_tracked']} days")
        print(f"  Win Rate: {r['win_rate']}   Avg RR: {r['avg_rr']}")
        print(f"  Total P&L: {r['total_pnl']}   Worst Day: {r['worst_day']}")
        print(f"\n  {'CHECK':<32} {'PASS':<6} VALUE / TARGET")
        print(f"  {'─'*48}")
        for c in r['checks']:
            icon = "✅" if c['pass'] else "❌"
            print(f"  {icon} {c['name']:<30} {c['value']} / {c['target']}")
        print(f"\n  ▶  {r['next_step']}")
        print(f"{sep}\n")

    # ── Persistence ────────────────────────────────────────
    def _save_state(self):
        try:
            state = {
                'next_id': self._next_id,
                'trades':  [asdict(t) for t in self.trades],
                'daily':   {k: asdict(v) for k, v in self.daily.items()},
            }
            with open(self.STATE_FILE, 'w', encoding='utf-8') as f:
                json.dump(state, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"save_state: {e}")

    def _load_state(self):
        if not os.path.exists(self.STATE_FILE):
            return
        try:
            with open(self.STATE_FILE, 'r', encoding='utf-8') as f:
                state = json.load(f)
            self._next_id = state.get('next_id', 1)
            self.trades   = [PaperTrade(**t) for t in state.get('trades', [])]
            self.daily    = {
                k: DailyScore(**v) for k, v in state.get('daily', {}).items()
            }
            logger.info(
                f"Paper state loaded: {len(self.trades)} trades, "
                f"{len(self.daily)} days"
            )
        except Exception as e:
            logger.warning(f"load_state: {e} — starting fresh")

    # ── Internals ──────────────────────────────────────────
    def _get_trade(self, trade_id: int) -> Optional[PaperTrade]:
        return next((t for t in self.trades if t.id == trade_id), None)

    def _update_daily(self, trade: PaperTrade):
        day = date.today().isoformat()
        if day not in self.daily:
            self.daily[day] = DailyScore(date=day)
        s = self.daily[day]
        s.trades += 1
        s.gross_pnl += trade.pnl
        s.total_rr  += max(0, trade.rr_achieved)
        if trade.pnl > 0:
            s.wins += 1
        else:
            s.losses += 1
            s.max_loss = min(s.max_loss, trade.pnl)

    def _has_3_consec_losses(self, closed: list) -> bool:
        streak = 0
        for t in closed:
            if t.pnl < 0:
                streak += 1
                if streak >= 3:
                    return True
            else:
                streak = 0
        return False

    def _recent_win_rate(self, closed: list, n: int) -> float:
        recent = closed[-n:] if len(closed) >= n else closed
        if not recent:
            return 0.0
        return sum(1 for t in recent if t.pnl > 0) / len(recent) * 100

    def _max_day_trades(self) -> int:
        return max((s.trades for s in self.daily.values()), default=0)
