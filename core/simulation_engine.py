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
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from collections import defaultdict

from models import (
    Signal, SignalType, Direction, Strength,
    MarketSnapshot, TradeHealth
)
from utils.logger import get_logger
from utils.helpers import save_json, load_json, safe_divide
from config.settings import Settings
from core.execution_fidelity import ExecutionFidelityEngine, ExecutionResult
from core.burnin_tracker import BurninTracker
from core.trade_lifecycle_logger import TradeLifecycleLogger
from models.lifecycle import TradeLifecycle, TradeState


@dataclass
class SimulatedTrade(TradeLifecycle):
    """A paper trade for simulation"""
    trade_id: str = ""
    timestamp: Optional[datetime] = None
    signal_type: SignalType = SignalType.NO_TRADE
    direction: Direction = Direction.NEUTRAL
    confidence: float = 0.0
    grade: str = ""

    # Prices
    entry_price: float = 0.0
    stop_loss: float = 0.0
    target_1: float = 0.0
    target_2: float = 0.0
    spot_entry: float = 0.0
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
    mfe: float = 0.0
    mae: float = 0.0

    # Context
    regime: str = ""
    session: str = ""
    rsi: float = 0
    vwap_position: str = ""
    vix: float = 0
    confluence: float = 0
    agreement_pct: float = 0
    atr: float = 0.0
    adx: float = 0.0
    grade_reason: str = ""

    # Filter info
    filter_score: float = 0
    gates_passed: int = 0
    gates_total: int = 0

    instrument: dict = field(default_factory=dict)

    # ── Phase A: Execution Fidelity Telemetry ──
    fill_ratio: float = 1.0
    slippage_pts: float = 0.0
    spread_cost_pts: float = 0.0
    total_friction_pts: float = 0.0
    latency_ms: int = 0
    moneyness_category: str = ""
    execution_quality_score: float = 0.0
    execution_quality: str = ""
    exit_slippage_pts: float = 0.0   # slippage incurred at exit

    # ── Priority 2: Execution Policy Deltas ──
    adaptation_reason: str = ""
    original_sl: float = 0.0
    original_tp1: float = 0.0
    original_tp2: float = 0.0
    adapted_sl: float = 0.0
    original_qty: int = 0
    adapted_qty: int = 0
    failure_type: str = ""

    # ── Phase C: Counterfactual Outcomes ──
    original_sl_hit: bool = False
    original_tp1_hit: bool = False
    original_tp2_hit: bool = False
    baseline_outcome: dict = field(default_factory=dict)  # { "exit_reason": "...", "pnl": 0.0 }
    adapted_outcome: dict = field(default_factory=dict)   # { "exit_reason": "...", "pnl": 0.0 }
    adaptation_outcome: str = ""                          # LOSS_MITIGATED, WIN_ENHANCED, etc.
    adaptation_pnl_delta: float = 0.0

    # ── Duck Typing for PositionPipeline ──
    current_price: float = 0.0
    unrealized_pnl: float = 0.0
    max_favorable: float = 0.0
    max_adverse: float = 0.0
    confidence_at_entry: float = 0.0
    entry_premium: float = 0.0
    tsl_highest_premium: float = 0.0
    tsl_highest_premium_time: Optional[datetime] = None
    tsl_phase: str = ""
    tsl_active: bool = False
    health_score: float = 100.0
    health_state: TradeHealth = TradeHealth.HEALTHY

    @property
    def position_id(self) -> str:
        """Alias for trade_id to fulfill the PositionLike interface contract."""
        return self.trade_id

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
            # Execution telemetry
            "fill_ratio": round(self.fill_ratio, 3),
            "slippage_pts": round(self.slippage_pts, 3),
            "spread_cost_pts": round(self.spread_cost_pts, 3),
            "total_friction_pts": round(self.total_friction_pts, 3),
            "latency_ms": self.latency_ms,
            "moneyness": self.moneyness_category,
            "exec_quality": self.execution_quality,
            "exec_quality_score": round(self.execution_quality_score, 1),
            "exit_slippage_pts": round(self.exit_slippage_pts, 3),
            # Priority 2
            "adaptation_reason": self.adaptation_reason,
            "original_sl": self.original_sl,
            "adapted_sl": self.adapted_sl,
            "original_qty": self.original_qty,
            "adapted_qty": self.adapted_qty,
            "failure_type": self.failure_type,
            # Phase C: Counterfactual
            "baseline_outcome": self.baseline_outcome,
            "adapted_outcome": self.adapted_outcome,
            "adaptation_outcome": self.adaptation_outcome,
            "adaptation_pnl_delta": round(self.adaptation_pnl_delta, 2),
        }

    def to_ledger_record(self) -> dict:
        risk_rupees = abs(self.entry_price - self.stop_loss) * self.qty
        return {
            "trade_id": self.trade_id,
            "schema_version": 2,
            "status": "CLOSED",
            "outcome": self.exit_reason,
            "trade": {
                "session": {
                    "trading_day": self.timestamp.strftime("%Y-%m-%d"),
                    "market": "NSE",
                    "session": self.session,
                    "weekday": self.timestamp.strftime("%A").upper(),
                    "expiry_week": False
                },
                "environment": {
                    "python": "3.12.5",
                    "git_commit": "unknown",
                    "hostname": os.environ.get("COMPUTERNAME", "UNKNOWN"),
                    "build": "v5.0"
                },
                "instrument": {
                    "symbol": self.instrument.get("symbol", "NIFTY"),
                    "option_type": self.instrument.get("type", "CE"),
                    "strike": self.instrument.get("strike", 0),
                    "expiry": self.instrument.get("expiry", ""),
                    "exchange": "NFO",
                    "tradingsymbol": self.instrument.get("tradingsymbol", "")
                },
                "strategy": {
                    "engine_version": "5.0",
                    "strategy": "MasterDecisionEngine",
                    "mode": "SIMULATION",
                    "capital_mode": "SIM",
                    "config_hash": "SIM_CONF"
                },
                "signal": {
                    "direction": self.direction.value,
                    "strength": self.confidence,
                    "generated_by": "MasterDecisionEngine"
                },
                "market": {
                    "spot_entry": self.spot_entry,
                    "regime": self.regime,
                    "adx": self.adx,
                    "atr": self.atr,
                    "vix": self.vix,
                    "oi_bias": self.instrument.get("oi_bias", "UNKNOWN")
                },
                "decision": {
                    "grade": self.grade,
                    "confidence": self.confidence,
                    "agent_agreement": self.agreement_pct,
                    "filter_score": self.filter_score,
                    "signal_quality": self.filter_score,
                    "approved_by": "MasterDecisionEngine",
                    "gate_version": "v4",
                    "passed_filters": []
                },
                "execution": {
                    "broker": "SIMULATION",
                    "entries": [
                        {
                            "price": self.entry_price,
                            "qty": self.qty,
                            "order_type": "MARKET",
                            "fill_type": "FULL",
                            "slippage": self.slippage_pts
                        }
                    ],
                    "exits": [
                        {
                            "price": self.simulated_exit_price,
                            "qty": self.qty,
                            "reason": self.exit_reason,
                            "order_type": "LIMIT",
                            "fill_type": "FULL",
                            "slippage": self.exit_slippage_pts
                        }
                    ]
                },
                "risk": {
                    "initial_sl": self.stop_loss,
                    "current_sl": self.stop_loss,
                    "target1": self.target_1,
                    "target2": self.target_2,
                    "risk_rupees": round(risk_rupees, 2),
                    "risk_percent": 0.0
                },
                "latency": {
                    "signal_to_authorization_ms": 0,
                    "authorization_to_entry_ms": 0,
                    "entry_to_fill_ms": self.latency_ms,
                    "cycle_ms": self.latency_ms
                },
                "artifacts": {
                    "snapshot": f"snapshot_{self.trade_id}.json",
                    "market_state": f"market_state_{self.trade_id}.json",
                    "decision_trace": f"trace_{self.trade_id}.json"
                },
                "timestamps": {
                    "signal": self.timestamp.isoformat(),
                    "authorized": self.timestamp.isoformat(),
                    "entry": self.timestamp.isoformat(),
                    "target1": None,
                    "target2": None,
                    "exit": datetime.now().isoformat(),
                    "closed": datetime.now().isoformat()
                }
            },
            "analytics": {
                "financial": {
                    "gross_pnl": round(self.gross_pnl, 2),
                    "costs": round(self.costs, 2),
                    "net_pnl": round(self.net_pnl, 2)
                },
                "derived": {
                    "r_multiple": round(self.net_pnl / risk_rupees, 2) if risk_rupees > 0 else 0.0,
                    "mae": 0.0,
                    "mfe": 0.0,
                    "expectancy_bucket": self.grade,
                    "holding_minutes": round(self.hold_minutes, 1)
                }
            }
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

    def __init__(self, settings: Settings, burnin_tracker: Optional[BurninTracker] = None, event_manager: Optional[Any] = None):
        self.settings = settings
        self.logger = get_logger("simulation")
        self.event_manager = event_manager

        # ── Phase A: Execution Fidelity Engine ──
        self.exec_engine = ExecutionFidelityEngine()

        # ── Phase B: Burn-In Tracker (optional, injected from main) ──
        self.burnin_tracker: Optional[BurninTracker] = burnin_tracker

        # ── Phase C: Trade Lifecycle Logger ──
        self.lifecycle_logger = TradeLifecycleLogger(event_manager=self.event_manager)

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
        self.reset_month = self.today_date.month

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

    def record_signal(self, passed: bool, regime: str = ""):
        """Record that a signal was generated"""
        self.total_signals += 1
        if not passed:
            self.total_filtered += 1
        if self.burnin_tracker:
            self.burnin_tracker.record_signal_filtered(regime=regime, was_killed=not passed)

    def open_simulated_trade(
        self,
        signal: Signal,
        snapshot: MarketSnapshot,
        filter_score: float,
        filter_grade: str,
        gates_passed: int,
        gates_total: int,
        costs_estimate: float,
        data_manager=None,
    ) -> SimulatedTrade:
        """Open a paper trade"""

        self._check_daily_reset()

        from utils.id_generator import TradeIdGenerator
        trade_id = getattr(signal, 'id', None) or TradeIdGenerator.generate()

        # Extract confluence score safely
        confluence_score = 0.0
        agreement_pct = 0.0
        if signal.confluence:
            confluence_score = signal.confluence.confluence_ratio * 100
            total_agents = signal.confluence.total_agents
            bullish = signal.confluence.bullish_agents
            bearish = signal.confluence.bearish_agents
            direction_agents = (
                bullish if signal.direction == Direction.BULLISH
                else bearish
            )
            agreement_pct = safe_divide(direction_agents * 100, total_agents)

        # Extract regime safely
        regime_str = ""
        if hasattr(signal, 'regime') and signal.regime:
            regime_str = getattr(signal.regime, 'value', str(signal.regime))

        # Extract session safely
        session_str = ""
        if hasattr(signal, 'session_phase') and signal.session_phase:
            session_str = getattr(signal.session_phase, 'value', str(signal.session_phase))

        # ── ⚡ EXECUTION FIDELITY ENGINE (Phase A) ──
        quote = signal.metadata.get("quote")
        instrument = signal.metadata.get("instrument", {})

        # If quote is missing or invalid, attempt to fetch live from data_manager
        if not (quote and hasattr(quote, 'ask') and quote.ask > 0) and data_manager and instrument:
            live_quote = data_manager.fetch_option_quote(
                instrument.get("strike"),
                instrument.get("type"),
                instrument.get("expiry")
            )
            if live_quote and hasattr(live_quote, 'ask') and live_quote.ask > 0:
                quote = live_quote

        # Determine base signal price
        base_price = quote.ask if (quote and hasattr(quote, 'ask') and quote.ask > 0) else signal.entry_price
        if not (quote and hasattr(quote, 'ask') and quote.ask > 0):
            self.logger.warning("Simulation fallback to Spot due to missing OptionQuote")

        # Classify instrument for moneyness calc
        strike = instrument.get("strike", base_price)
        option_type = instrument.get("type", "CE")
        expiry_str = instrument.get("expiry", None)
        expiry_date = None
        if expiry_str:
            try:
                expiry_date = date.fromisoformat(expiry_str)
            except Exception:
                pass

        # ── Priority 2: Execution Policy Overrides ──
        target_qty = signal.position_size if signal.position_size > 0 else 75
        sl_multiplier = 1.0
        tp2_multiplier = 1.0
        policy_reason = ""
        orig_sl = signal.stop_loss
        orig_tp1 = signal.target_1
        orig_tp2 = signal.target_2
        adapted_sl = signal.stop_loss
        orig_qty = target_qty
        adapted_qty = target_qty

        if getattr(signal, 'execution_policy', None):
            target_qty = signal.execution_policy.adapted_qty
            sl_multiplier = signal.execution_policy.sl_multiplier
            tp2_multiplier = signal.execution_policy.tp2_multiplier
            policy_reason = signal.execution_policy.reason
            orig_sl = signal.execution_policy.original_sl
            adapted_sl = signal.execution_policy.adapted_sl
            orig_qty = signal.execution_policy.original_qty
            adapted_qty = signal.execution_policy.adapted_qty

        # Run the fidelity pipeline
        exec_result: ExecutionResult = self.exec_engine.simulate_entry(
            signal_price=base_price,
            spot_price=snapshot.price,
            strike=strike,
            option_type=option_type,
            qty=target_qty,
            regime=regime_str or "UNKNOWN",
            vix=snapshot.india_vix,
            expiry_date=expiry_date,
        )

        sig_type_str = getattr(signal.signal_type, 'value', str(signal.signal_type))

        # ── Handle Rejection ──
        if exec_result.rejected:
            self.logger.warning(
                f"🚫 Trade REJECTED by fidelity engine | "
                f"Reason: {exec_result.rejection_reason} | "
                f"Signal: {sig_type_str}"
            )
            return None   # Caller must handle None (skip OMS/Telegram)

        realistic_entry = exec_result.fill_price
        filled_qty = exec_result.filled_qty

        # ── Adjust SL/TP relative to actual fill price + Execution Policy ──
        premium_levels = getattr(signal, "metadata", {}).get("premium_levels", {})
        
        if premium_levels and "premium_sl" in premium_levels:
            # We are trading an option. Use the translated premium distances.
            expected_entry = premium_levels.get("premium_entry", realistic_entry)
            expected_sl = premium_levels.get("premium_sl", expected_entry - 5.0)
            
            # SL distance in premium space
            base_sl_dist = abs(expected_entry - expected_sl)
            sl_dist = base_sl_dist * sl_multiplier
            
            # Target distances in premium space
            expected_t1 = premium_levels.get("premium_t1", expected_entry + base_sl_dist * 1.5)
            t1_dist = abs(expected_t1 - expected_entry)
            
            expected_t2 = premium_levels.get("premium_t2", expected_entry + base_sl_dist * 2.5)
            t2_dist = abs(expected_t2 - expected_entry) * tp2_multiplier
            
            orig_sl_dist = base_sl_dist
            orig_t1_dist = t1_dist
            orig_t2_dist = abs(expected_t2 - expected_entry)
        else:
            # Fallback for Spot simulation
            sl_dist = abs(signal.entry_price - signal.stop_loss) * sl_multiplier
            t1_dist = abs(signal.target_1 - signal.entry_price)
            t2_dist = abs(signal.target_2 - signal.entry_price) * tp2_multiplier
            
            orig_sl_dist = abs(signal.entry_price - signal.stop_loss)
            orig_t1_dist = abs(signal.target_1 - signal.entry_price)
            orig_t2_dist = abs(signal.target_2 - signal.entry_price)

        adjusted_sl = round(realistic_entry - sl_dist, 2)
        adjusted_t1 = round(realistic_entry + t1_dist, 2)
        adjusted_t2 = round(realistic_entry + t2_dist, 2)
        
        baseline_sl = round(realistic_entry - orig_sl_dist, 2)
        baseline_t1 = round(realistic_entry + orig_t1_dist, 2)
        baseline_t2 = round(realistic_entry + orig_t2_dist, 2)

        trade = SimulatedTrade(
            trade_id=trade_id,
            timestamp=datetime.now(),
            signal_type=signal.signal_type,
            direction=signal.direction,
            confidence=signal.confidence,
            grade=filter_grade,
            entry_price=realistic_entry,
            stop_loss=adjusted_sl,
            target_1=adjusted_t1,
            target_2=adjusted_t2,
            lots=max(1, filled_qty // 75),
            qty=filled_qty,
            regime=regime_str,
            session=session_str,
            rsi=snapshot.rsi,
            vwap_position=(
                "above" if snapshot.price > snapshot.vwap
                else "below"
            ),
            vix=snapshot.india_vix,
            confluence=confluence_score,
            agreement_pct=agreement_pct,
            filter_score=filter_score,
            gates_passed=gates_passed,
            gates_total=gates_total,
            instrument=instrument,
            costs=costs_estimate,
            spot_entry=snapshot.price,
            atr=snapshot.atr,
            adx=getattr(snapshot, 'adx', 0.0),
            grade_reason=signal.reasons[0] if signal.reasons else "",
            # ── Execution telemetry ──
            fill_ratio=exec_result.fill_ratio,
            slippage_pts=exec_result.slippage_pts,
            spread_cost_pts=exec_result.spread_cost_pts,
            total_friction_pts=exec_result.total_friction_pts,
            latency_ms=exec_result.latency_ms,
            moneyness_category=exec_result.moneyness_category,
            execution_quality_score=exec_result.execution_quality_score,
            execution_quality=exec_result.execution_quality,
            # Priority 2 Deltas
            adaptation_reason=policy_reason,
            original_sl=baseline_sl,
            original_tp1=baseline_t1,
            original_tp2=baseline_t2,
            adapted_sl=adjusted_sl,
            original_qty=orig_qty,
            adapted_qty=filled_qty,
        )

        self.open_trades[trade_id] = trade
        self.total_trades += 1
        self.today_trades += 1

        trade.transition_to(TradeState.SIGNAL_APPROVED, self.event_manager)
        trade.transition_to(TradeState.ORDER_PENDING, self.event_manager)
        trade.transition_to(TradeState.ORDER_FILLED, self.event_manager)
        trade.transition_to(TradeState.POSITION_OPEN, self.event_manager, payload=trade.to_dict())

        # ── Phase B: Record execution into BurninTracker ──
        if self.burnin_tracker:
            self.burnin_tracker.record_execution(exec_result, regime=regime_str)

        self.logger.info(
            f"📝 SIM TRADE OPENED: {trade_id} | "
            f"{sig_type_str} | "
            f"Signal: ₹{base_price:,.1f} → Fill: ₹{realistic_entry:,.1f} | "
            f"Friction: {exec_result.total_friction_pts:+.2f}pts | "
            f"Latency: {exec_result.latency_ms}ms | "
            f"Fill: {exec_result.fill_ratio*100:.0f}% | "
            f"Moneyness: {exec_result.moneyness_category} | "
            f"Quality: {exec_result.execution_quality} ({exec_result.execution_quality_score:.0f}) | "
            f"Grade: {filter_grade} | Conf: {signal.confidence:.0f}%"
        )

        return trade

    def _resolve_exit_premium(
        self, trade: SimulatedTrade, current_spot: float,
        snapshot: MarketSnapshot, data_manager=None
    ) -> float:
        """
        P0 Fix: Resolve the current option premium for exit pricing.

        Uses a 3-tier fallback:
          Tier 1: Actual contract premium via data_manager.fetch_option_quote()
          Tier 2: ATM premium proxy from snapshot (atm_ce_premium / atm_pe_premium)
          Tier 3: Delta approximation from spot movement relative to entry

        NEVER returns raw spot price — that would cause astronomical PnL errors
        when compared against the option premium stored in trade.entry_price.
        """
        # ── Tier 1: Actual contract premium (best accuracy) ──
        if data_manager and trade.instrument:
            quote = data_manager.fetch_option_quote(
                trade.instrument.get("strike"),
                trade.instrument.get("type"),
                trade.instrument.get("expiry")
            )
            if quote and quote.bid > 0:
                return quote.bid

        # ── Tier 2: ATM premium proxy from snapshot ──
        if snapshot:
            is_ce = trade.signal_type == SignalType.BUY_CE
            atm_premium = snapshot.atm_ce_premium if is_ce else snapshot.atm_pe_premium
            if atm_premium and atm_premium > 0:
                self.logger.debug(
                    f"⚠️ Premium Tier 2 (ATM proxy): {trade.trade_id} | "
                    f"Using {'CE' if is_ce else 'PE'} ATM premium ₹{atm_premium:.2f}"
                )
                return atm_premium

        # ── Tier 3: Delta approximation (emergency fallback) ──
        # Estimate premium change from spot movement.
        # Use a conservative delta of 0.5 for ATM options.
        spot_move = current_spot - (snapshot.price if snapshot else current_spot)
        is_ce = trade.signal_type == SignalType.BUY_CE
        delta = 0.5 if is_ce else -0.5
        estimated_premium = trade.entry_price + (spot_move * delta)
        # Floor at 0.05 — option premium cannot go negative
        estimated_premium = max(0.05, estimated_premium)

        self.logger.warning(
            f"⚠️ Premium Tier 3 (delta approx): {trade.trade_id} | "
            f"Entry premium: ₹{trade.entry_price:.2f} | "
            f"Spot move: {spot_move:+.2f} | "
            f"Estimated exit premium: ₹{estimated_premium:.2f}"
        )
        return round(estimated_premium, 2)

    def update_open_trades(
        self, current_price: float, snapshot: MarketSnapshot, data_manager=None
    ) -> List[Dict]:
        """
        Check all open sim trades for SL/TP hits.
        Returns list of closed trade results.

        P0 Fix: All exit paths now use resolved option premium
        instead of raw spot price for PnL calculation.
        """

        closed = []

        for tid, trade in list(self.open_trades.items()):
            if trade.result != "OPEN":
                continue

            # ── P0 Fix: Resolve current option premium (never raw spot) ──
            eval_price = self._resolve_exit_premium(
                trade, current_price, snapshot, data_manager
            )

            # ── Update MFE / MAE ──
            unrealized = eval_price - trade.entry_price
            trade.update_mfe_mae(unrealized, self.event_manager)

            # ── Phase C: Counterfactual Intrabar Hit Tracking ──
            # Deterministic intrabar assumptions: SL hits before TP if both breached, but we'll mark them as we see them.
            if trade.original_sl > 0 and eval_price <= trade.original_sl and not trade.original_sl_hit:
                trade.original_sl_hit = True
                trade.baseline_outcome = {
                    "exit_reason": "STOP_LOSS",
                    "pnl": (trade.original_sl - trade.entry_price) * trade.original_qty
                }
            if trade.original_tp1 > 0 and eval_price >= trade.original_tp1 and not trade.original_tp1_hit:
                trade.original_tp1_hit = True
                # If SL wasn't hit, TP1 would be the exit
                if not trade.baseline_outcome:
                    trade.baseline_outcome = {
                        "exit_reason": "TARGET_1",
                        "pnl": (trade.original_tp1 - trade.entry_price) * trade.original_qty
                    }
            if trade.original_tp2 > 0 and eval_price >= trade.original_tp2 and not trade.original_tp2_hit:
                trade.original_tp2_hit = True

            if eval_price <= trade.stop_loss:
                self._close_trade(tid, eval_price, "STOP_LOSS")
                if self.all_trades:
                    t_dict = self.all_trades[-1].to_dict()
                    t_dict["ledger_record"] = self.all_trades[-1].to_ledger_record()
                    closed.append(t_dict)
            elif trade.target_1 > 0 and eval_price >= trade.target_1:
                self._close_trade(tid, eval_price, "TARGET_1")
                if self.all_trades:
                    t_dict = self.all_trades[-1].to_dict()
                    t_dict["ledger_record"] = self.all_trades[-1].to_ledger_record()
                    closed.append(t_dict)

            # Time-based exit check (only for still-open trades)
            # P0 Fix: Use eval_price (resolved premium), NOT current_price (spot)
            if tid in self.open_trades:
                hold_time = (
                    datetime.now() - trade.timestamp
                ).total_seconds() / 60

                max_hold = self.settings.exit.max_hold_time_minutes
                if getattr(snapshot, 'is_expiry_day', False):
                    max_hold = min(max_hold, self.settings.exit.max_hold_on_expiry_day_minutes)

                if hold_time > max_hold:
                    self._close_trade(tid, eval_price, "TIME_EXIT" if max_hold == self.settings.exit.max_hold_time_minutes else "EXPIRY_TIME_EXIT")
                    if self.all_trades:
                        t_dict = self.all_trades[-1].to_dict()
                        t_dict["ledger_record"] = self.all_trades[-1].to_ledger_record()
                        closed.append(t_dict)

        return closed

    def _close_trade(
        self, trade_id: str, exit_price: float, reason: str
    ):
        """Close a simulated trade and record results"""

        if trade_id not in self.open_trades:
            return

        trade = self.open_trades[trade_id]

        # ── P0.5 Safety Assertion: Catch spot-vs-premium confusion ──
        # A Nifty option premium realistically cannot move more than ~500 pts
        # from entry in a single session. If it does, the exit_price is almost
        # certainly a raw spot value that leaked through.
        premium_move = abs(exit_price - trade.entry_price)
        if premium_move > 500:
            self.logger.critical(
                f"🚨 SUSPICIOUS PREMIUM MOVE: {trade_id} | "
                f"Entry: ₹{trade.entry_price:.2f} → Exit: ₹{exit_price:.2f} | "
                f"Delta: {premium_move:.2f} pts | Reason: {reason} | "
                f"This looks like spot price leaked into premium PnL. "
                f"Clamping exit to entry (PnL=0) to prevent data corruption."
            )
            # Clamp to entry price so PnL = 0 rather than ±billions
            exit_price = trade.entry_price

        # ── Phase A: Exit Slippage ──
        exit_result = self.exec_engine.simulate_exit(
            trigger_price=exit_price,
            exit_reason=reason,
            vix=trade.vix,
            regime=trade.regime or "UNKNOWN",
        )
        realistic_exit = exit_result.exit_price
        trade.exit_slippage_pts = exit_result.slippage_pts

        trade.simulated_exit_price = realistic_exit
        trade.exit_reason = reason
        trade.hold_minutes = (
            datetime.now() - trade.timestamp
        ).total_seconds() / 60

        # Calculate P&L (Both BUY_CE and BUY_PE are LONG premium positions)
        trade.gross_pnl = (exit_price - trade.entry_price) * trade.qty

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
            
            # ── Priority 2: Structured Post-Mortem ──
            if "target" not in reason.lower():
                if "breakout" in trade.regime.lower() or trade.adaptation_reason and "breakout" in trade.adaptation_reason.lower():
                    trade.failure_type = "FALSE_BREAKOUT"
                elif trade.total_friction_pts + trade.exit_slippage_pts > (trade.entry_price * 0.015):
                    trade.failure_type = "SLIPPAGE_LOSS"
                elif trade.spread_cost_pts > (trade.entry_price * 0.01):
                    trade.failure_type = "SPREAD_DEGRADATION"
                elif "time" in reason.lower() or "manual" in reason.lower():
                    trade.failure_type = "EARLY_EXIT"
                else:
                    trade.failure_type = "GOOD_LOSS"
        else:
            trade.result = "BREAK_EVEN"
            
        # ── Phase C: Counterfactual Resolution ──
        trade.adapted_outcome = {
            "exit_reason": reason,
            "pnl": trade.net_pnl
        }
        
        # If no baseline outcome was logged (e.g. time exit before any targets hit), fallback to adapted outcome logic.
        if not trade.baseline_outcome:
            # Baseline PNL is what the PNL would have been with the original size
            hypothetical_pnl = trade.net_pnl * (trade.original_qty / trade.qty) if trade.qty > 0 else trade.net_pnl
            trade.baseline_outcome = {
                "exit_reason": reason,
                "pnl": hypothetical_pnl
            }
            
        base_pnl = trade.baseline_outcome.get("pnl", 0)
        adpt_pnl = trade.adapted_outcome.get("pnl", 0)
        trade.adaptation_pnl_delta = adpt_pnl - base_pnl
        
        if trade.adaptation_reason:
            if trade.original_sl_hit and trade.result == "WIN":
                trade.adaptation_outcome = "REVERSAL_CAPTURED"
            elif trade.original_tp1_hit and trade.result == "LOSS":
                trade.adaptation_outcome = "PROFIT_SUPPRESSED"
            elif base_pnl < 0 and adpt_pnl > base_pnl:
                trade.adaptation_outcome = "LOSS_MITIGATED"
            elif base_pnl < 0 and adpt_pnl > 0:
                trade.adaptation_outcome = "LOSS_AVOIDED"
            elif adpt_pnl > base_pnl and base_pnl > 0:
                trade.adaptation_outcome = "WIN_ENHANCED"
            elif trade.exit_reason == "TARGET_2" and not trade.original_tp2_hit:
                trade.adaptation_outcome = "RUNNER_CAPTURED"
            elif adpt_pnl < base_pnl:
                trade.adaptation_outcome = "PROFIT_SUPPRESSED"
            else:
                trade.adaptation_outcome = "NEUTRAL"
        
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

        trade.transition_to(TradeState.EXIT_TRIGGERED, self.event_manager, payload={"reason": reason, "exit_price": exit_price})
        trade.transition_to(TradeState.POSITION_CLOSED, self.event_manager, payload=trade.to_dict())
        
        # ── TRADE_EVALUATED ──
        # Calculate EV vs Realized
        expected_r = (trade.confidence - 0.5) * 2  # simple mock mapping
        risk = abs(trade.entry_price - trade.stop_loss) * trade.qty if trade.stop_loss > 0 else 0
        actual_r = (trade.net_pnl / risk) if risk > 0 else 0.0
        prediction_error = actual_r - expected_r
        
        trade.transition_to(TradeState.TRADE_EVALUATED, self.event_manager, payload={
            "actual_r": round(actual_r, 3),
            "expected_r": round(expected_r, 3),
            "prediction_error": round(prediction_error, 3),
            "decision_quality": "Correct Decision" if actual_r > 0 else "Poor Decision",
            "confidence": trade.confidence,
            "grade": trade.grade,
            "regime": trade.regime,
        })
        trade.transition_to(TradeState.TRADE_ARCHIVED, self.event_manager)

        # ── Phase B: Record trade into BurninTracker ──
        if self.burnin_tracker:
            risk = abs(trade.entry_price - trade.stop_loss) * trade.qty
            rr = (trade.net_pnl / risk) if risk > 0 else 0
            self.burnin_tracker.record_trade_closed(
                result=trade.result,
                net_pnl=trade.net_pnl,
                gross_profit=max(trade.net_pnl, 0),
                gross_loss=abs(min(trade.net_pnl, 0)),
                rr_ratio=rr,
                regime=trade.regime,
            )

        # Save periodically
        if len(self.all_trades) % 5 == 0:
            self._save_state()
            if self.burnin_tracker:
                self.burnin_tracker._save()

        self.logger.info(
            f"{'🟢' if trade.result == 'WIN' else '🔴'} "
            f"SIM TRADE CLOSED: {trade_id} | "
            f"{trade.result} | "
            f"Gross: ₹{trade.gross_pnl:,.0f} | "
            f"Costs: ₹{trade.costs:,.0f} | "
            f"Net: ₹{trade.net_pnl:,.0f} | "
            f"Exit slip: {trade.exit_slippage_pts:.2f}pts | "
            f"Reason: {reason} | Hold: {trade.hold_minutes:.0f}min"
        )

    def _check_daily_reset(self):
        today = date.today()
        
        # ── Capital Reset Logic ──
        # Reset if new month
        if hasattr(self, 'reset_month') and today.month != self.reset_month:
            self.logger.info(f"🔄 Monthly Rollover Detected (Old: {self.reset_month}, New: {today.month}). Resetting Simulation Capital to ₹{self.initial_capital:,.0f}.")
            self.current_capital = self.initial_capital
            self.peak_capital = self.initial_capital
            self.reset_month = today.month
            
        # Reset if ruin
        if self.current_capital <= 0:
            self.logger.warning(f"💥 CAPITAL DEPLETED! Resetting Simulation Capital to ₹{self.initial_capital:,.0f}.")
            self.current_capital = self.initial_capital
            self.peak_capital = self.initial_capital
            self.reset_month = today.month

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

        # ── Phase B: Persist daily burnin snapshot ──
        if self.burnin_tracker:
            self.burnin_tracker.get_daily_snapshot()

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
            "reset_month": getattr(self, 'reset_month', date.today().month),
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
            saved_month = state.get("reset_month", date.today().month)
            if saved_month != date.today().month or abs(state.get("net_pnl", 0)) > 50_000_000:
                self.logger.info("Simulation state reset triggered (month rollover or invalid state). Starting fresh.")
                return

            self.current_capital = state.get(
                "current_capital", self.initial_capital
            )
            self.peak_capital = state.get(
                "peak_capital", self.initial_capital
            )
            self.reset_month = saved_month
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
