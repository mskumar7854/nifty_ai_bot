"""
============================================
🏦 POSITION MANAGEMENT ENGINE

The MOST CRITICAL production component.
Without this, everything else is academic.

This manages:
- How much to risk per trade
- How many lots to trade
- When to STOP trading (circuit breakers)
- Open position tracking
- Trailing stops
- Partial profit booking
- Portfolio heat monitoring
- Drawdown protection

RULE: This engine can OVERRIDE any signal.
If risk limits are breached → NO TRADE.

⚠️ AI WARNING: core/position_manager.py
This file controls REAL MONEY position sizing and stop losses.
DO NOT modify calculate_position_size() or open_position() without:
  1. 50+ trade backtest on simulation data
  2. Manual review of risk calculations
  3. Verifying SL is ALWAYS set before order placement
============================================
"""

import os
import time
import uuid
import logging
import asyncio
from enum import Enum
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from collections import deque

from models import (
    Signal, SignalType, Direction, Strength
)
from models.trade_record import TradeRecord
from utils.trade_logger import TradeLogger
from utils.logger import get_logger
from core.oms import OrderManagementSystem
from core.shadow_execution import ShadowExecutionEngine
from utils.helpers import save_json, load_json, safe_divide
from config.settings import Settings, PositionConfig
from config.signal_weights import MIN_CONFIDENCE, MIN_DIRECTION_GAP

from analytics.analytics_bus import analytics_bus


# ── P0-E: SL Guarantee Config ──
SL_MAX_RETRIES = 3
SL_RETRY_DELAY_SECONDS = 1.0
SL_PLACEMENT_TIMEOUT_SECONDS = 10.0
VALID_SL_STATUSES = {"PENDING", "TRIGGER_PENDING", "OPEN"}

@dataclass
class EntryResult:
    filled: bool
    order_id: str | None = None
    fill_price: float = 0.0
    fill_qty: int = 0
    symbol: str = ""
    security_id: str = ""
    exchange_segment: str = ""


@dataclass
class OpenPosition:
    """Represents a currently open position"""
    position_id: str
    entry_time: datetime
    signal_type: SignalType
    direction: Direction
    entry_price: float
    
    symbol: str = "NIFTY"
    security_id: str = ""
    intent_id: str = ""
    strike: Optional[float] = None
    option_type: str = ""
    expiry: Optional[str] = None
    
    # Execution Metrics (P0.5)
    entry_bid: float = 0.0
    entry_ask: float = 0.0
    quote_age_ms: float = 0.0
    spread_pct_entry: float = 0.0
    slippage_entry: float = 0.0

    # Prices
    current_price: float = 0
    stop_loss: float = 0
    original_stop_loss: float = 0
    target_1: float = 0
    target_2: float = 0
    trailing_stop: float = 0

    # Size
    lots: int = 1
    qty: int = 50
    entry_premium: float = 0          # option premium at entry

    # Status
    is_active: bool = True
    partial_booked: bool = False
    sl_moved_to_cost: bool = False

    # P&L
    unrealized_pnl: float = 0
    realized_pnl: float = 0
    max_favorable: float = 0          # max profit seen
    max_adverse: float = 0            # max loss seen

    # Context & Intelligence (Learning Layer)
    confidence_at_entry: float = 0
    regime_at_entry: str = ""
    weighted_score: float = 0
    calibrated_confidence: float = 0
    buy_score: float = 0
    sell_score: float = 0
    agent_breakdown: Dict = field(default_factory=dict)
    
    # Market Context
    volatility_at_entry: float = 0
    entry_type: str = "AI"  # AI, TELEGRAM, MANUAL
    
    # API Throttling
    last_sl_price: float = 0
    last_sl_update_time: float = 0

    # ── Hybrid TSL State ──
    tsl_active: bool = False
    tsl_breakeven_hit: bool = False
    tsl_current_trail_pct: float = 0.0
    tsl_highest_premium: float = 0.0           # Peak premium seen — the ratchet value
    tsl_highest_premium_time: datetime = field(default_factory=datetime.now)  # For idle tightening
    tsl_phase: str = "INITIAL"                 # INITIAL|BREAKEVEN|ACTIVE|TIGHTEN_1|TIGHTEN_2|IDLE_TIGHTEN
    tsl_grade: str = "B"                       # Signal grade at entry (additive adjustment)
    tsl_regime: str = "UNKNOWN"                # Regime at entry (additive adjustment)
    
    # ── Trade Health & Exits ──
    health_score: float = 100.0
    health_state: str = "HEALTHY"
    iv_at_entry: float = 0.0
    underlying_price_at_entry: float = 0.0
    consecutive_iv_drops: int = 0
    consecutive_critical_cycles: int = 0
    is_reconstructed: bool = False

    def update_pnl(self, current_price: float):
        """Update unrealized P&L"""
        self.current_price = current_price

        if self.direction == Direction.BULLISH:
            points = current_price - self.entry_price
        else:
            points = self.entry_price - current_price

        self.unrealized_pnl = points * self.qty
        self.max_favorable = max(
            self.max_favorable, self.unrealized_pnl
        )
        self.max_adverse = min(
            self.max_adverse, self.unrealized_pnl
        )

    def to_dict(self) -> dict:
        sig_type_str = self.signal_type.value if hasattr(self.signal_type, "value") else str(self.signal_type)
        dir_str = self.direction.value if hasattr(self.direction, "value") else str(self.direction)
        contract_str = self.symbol if self.symbol and self.symbol != "NIFTY" else (f"{self.symbol}_{int(self.strike)}_{sig_type_str}" if self.strike else sig_type_str)
        return {
            "id": self.position_id,
            "trade_id": self.position_id,
            "intent_id": self.intent_id,
            "snapshot_id": self.position_id,
            "signal_type": sig_type_str,
            "type": sig_type_str,
            "direction": dir_str,
            "symbol": self.symbol,
            "contract": contract_str,
            "strike": self.strike,
            "option_type": self.option_type,
            "expiry": self.expiry,
            "entry_price": self.entry_price,
            "entry": self.entry_price,
            "current_price": self.current_price,
            "current": self.current_price,
            "stop_loss": self.stop_loss,
            "sl": self.stop_loss,
            "target_1": self.target_1,
            "target1": self.target_1,
            "lots": self.lots,
            "qty": self.qty,
            "unrealized_pnl": f"₹{self.unrealized_pnl:,.0f}",
            "net_pnl": self.unrealized_pnl,
            "max_profit_seen": f"₹{self.max_favorable:,.0f}",
            "max_loss_seen": f"₹{self.max_adverse:,.0f}",
            "active": self.is_active,
            "partial_booked": self.partial_booked,
            "is_reconstructed": self.is_reconstructed,
            "opened_at": self.entry_time.isoformat() if hasattr(self.entry_time, "isoformat") else str(self.entry_time),
            # ── TSL telemetry ──
            "tsl_phase": self.tsl_phase,
            "tsl_active": self.tsl_active,
            "tsl_trail_pct": f"{self.tsl_current_trail_pct:.1f}%",
            "tsl_peak_premium": f"₹{self.tsl_highest_premium:,.1f}",
            "tsl_breakeven_hit": self.tsl_breakeven_hit,
            "confidence": getattr(self, "confidence_at_entry", 0.0) or getattr(self, "calibrated_confidence", self.weighted_score),
            "grade": getattr(self, "tsl_grade", "—"),
            "weighted_score": self.weighted_score,
            "calibrated_confidence": getattr(self, "calibrated_confidence", self.weighted_score),
            "regime_at_entry": self.regime_at_entry,
            # ── Health ──
            "health_score": f"{self.health_score:.1f}",
            "health_state": self.health_state,
        }


@dataclass
class DailyStats:
    """Daily trading statistics"""
    date: date = field(default_factory=date.today)
    trades_taken: int = 0
    wins: int = 0
    losses: int = 0
    break_evens: int = 0
    total_pnl: float = 0
    gross_profit: float = 0
    gross_loss: float = 0
    max_win: float = 0
    max_loss: float = 0
    total_brokerage: float = 0
    total_slippage: float = 0
    capital_start: float = 0
    capital_current: float = 0
    peak_capital: float = 0
    max_drawdown: float = 0
    is_halted: bool = False
    halt_reason: str = ""
    exit_reasons: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "date": self.date.isoformat(),
            "trades": self.trades_taken,
            "wins": self.wins,
            "losses": self.losses,
            "win_rate": f"{self.win_rate:.1f}%",
            "pnl": f"₹{self.total_pnl:,.0f}",
            "net_pnl": f"₹{self.net_pnl:,.0f}",
            "max_win": f"₹{self.max_win:,.0f}",
            "max_loss": f"₹{self.max_loss:,.0f}",
            "brokerage": f"₹{self.total_brokerage:,.0f}",
            "slippage": f"₹{self.total_slippage:,.0f}",
            "drawdown": f"{self.max_drawdown:.2f}%",
            "halted": self.is_halted,
            "exit_reasons": self.exit_reasons,
        }

    @property
    def win_rate(self) -> float:
        total = self.wins + self.losses
        return (self.wins / total * 100) if total > 0 else 0

    @property
    def net_pnl(self) -> float:
        return self.total_pnl - self.total_brokerage - \
               self.total_slippage


class PositionManager:
    """
    MASTER POSITION AND RISK CONTROLLER

    Hierarchy of safety:
    1. Capital preservation (ALWAYS first)
    2. Risk management (per trade, per day, drawdown)
    3. Position sizing (confidence-based)
    4. Trade execution (with slippage model)
    5. Position monitoring (trailing, partial)
    """

    def __init__(self, settings: Settings, broker=None):
        self.settings = settings
        self.config = settings.position
        self.logger = get_logger("position_manager")
        self.broker = broker

        # ── Capital State ──
        self.total_capital = self.config.total_capital
        self.available_capital = self.total_capital
        self.deployed_capital = 0.0
        self.peak_capital = self.total_capital
        self.current_drawdown_pct = 0.0

        # ── Learning Engine ──
        self.trade_logger = TradeLogger()

        # ── Self-learning Threshold Tuner ──
        # Injected lazily by the system runner after construction,
        # so both the engine and the manager share THE SAME instance.
        # Fallback: if not set, import is safe (no crash).
        self.tuner = None

        # ── Open Positions ──
        self.open_positions: Dict[str, OpenPosition] = {}
        self.closed_positions_today: List[dict] = []

        # ── Daily Stats ──
        self.today_stats = DailyStats(
            capital_start=self.total_capital,
            capital_current=self.total_capital,
            peak_capital=self.total_capital,
        )

        # ── Historical Stats ──
        self.daily_history: List[DailyStats] = []
        self.equity_curve: deque = deque(maxlen=5000)
        self.recent_pnls: deque = deque(maxlen=50) # Added for PF50 tracking
        self.equity_curve.append({
            "time": datetime.now(),
            "equity": self.total_capital,
        })

        # ── Master Capital Scaling State ──
        self.master_high_water_mark = self.total_capital
        self.approved_capital_baseline = self.total_capital

        # ── Trade Timing ──
        self.last_trade_time: Optional[datetime] = None

        # ── Weekly tracking ──
        self.weekly_pnl = 0.0
        self.week_start = self._get_week_start()

        # ── Circuit Breaker State ──
        self.is_halted = False
        self.halt_reason = ""
        self.last_loss_time: Optional[datetime] = None
        self._acknowledged_orphans: set[str] = set()

        # ── P0-C: Deadman watchdog heartbeat ──
        self._last_heartbeat_time: float = time.time()
        
        # ── Execution Lock ──
        self._trade_lock = asyncio.Lock()

        # Load previous state
        self._load_state()



        # ── OMS Integration ──
        self.oms = OrderManagementSystem()
        
        # ── P0: Shadow Execution Engine ──
        self.shadow_engine = ShadowExecutionEngine()

        
        self.logger.info(
            f"PositionManager initialized | "
            f"Capital: ₹{self.total_capital:,.0f} | "
            f"Max Risk/Trade: {self.config.risk_per_trade_pct}%"
        )
        
        # ── P3: Restart Position Hydration ──
        self._recover_live_state()


    # ══════════════════════════════════════
    # P0-C: DEADMAN HEARTBEAT
    # ══════════════════════════════════════

    def record_heartbeat(self) -> None:
        """Called by main loop every cycle to prove liveness."""
        self._last_heartbeat_time = time.time()
        # Write for independent watchdog process
        try:
            import json, os
            os.makedirs("data", exist_ok=True)
            with open("data/heartbeat.json", "w") as f:
                json.dump({"last_heartbeat": self._last_heartbeat_time}, f)
        except Exception as e:
            self.logger.error(f"Failed to write heartbeat file: {e}")


    def _recover_live_state(self):
        """
        P3: Hydrate open and closed positions from OMS to survive mid-day crashes.
        """
        try:
            open_orders = self.oms.get_open_orders()
            count = 0
            for order in open_orders:
                state = order.get("state")
                if state in ("ENTRY_FILLED", "FILLED_ACTIVE", "PARTIAL_FILLED"):
                    pos_id = order.get("signal_id") or order.get("intent_id")
                    if pos_id and pos_id not in self.open_positions:
                        symbol = order.get("symbol", "NIFTY")
                        side = (order.get("side") or "BUY").upper()
                        is_pe = "PE" in symbol.upper()
                        sig_type = SignalType.BUY_PE if is_pe else SignalType.BUY_CE
                        direction = Direction.BEARISH if is_pe else Direction.BULLISH
                        fill_p = order.get("avg_fill_price") or order.get("requested_price") or 0.0
                        sl_p = order.get("stop_loss_price") or 0.0
                        qty_val = order.get("filled_qty") or order.get("qty") or 50

                        created_str = order.get("created_at")
                        try:
                            entry_dt = datetime.fromisoformat(created_str) if created_str else datetime.now()
                        except Exception:
                            entry_dt = datetime.now()

                        recovered_pos = OpenPosition(
                            position_id=pos_id,
                            intent_id=order.get("intent_id", ""),
                            entry_time=entry_dt,
                            signal_type=sig_type,
                            direction=direction,
                            symbol=symbol,
                            security_id="",
                            entry_price=fill_p,
                            entry_bid=fill_p,
                            entry_ask=fill_p,
                            current_price=fill_p,
                            stop_loss=sl_p,
                            original_stop_loss=sl_p,
                            target_1=fill_p + (abs(fill_p - sl_p) * 1.5) if sl_p > 0 else 0.0,
                            target_2=fill_p + (abs(fill_p - sl_p) * 2.5) if sl_p > 0 else 0.0,
                            trailing_stop=sl_p,
                            lots=max(1, qty_val // 50),
                            qty=qty_val,
                            entry_premium=fill_p,
                            is_reconstructed=True
                        )
                        self.open_positions[pos_id] = recovered_pos
                        count += 1
                elif state == "ENTRY_SUBMITTED":
                    self.logger.warning(f"⚠️ Recovered in-flight pending order (unfilled): {order.get('intent_id')}")
            if count > 0:
                self.logger.warning(f"🔄 Reconstructed {count} active positions from OMS.")

            # P3.1: Recover closed positions for today from persistent trade_outcomes
            import os as _os
            import sqlite3 as _sqlite3
            from datetime import date as _date
            _today_s = _date.today().isoformat()
            _mode = _os.getenv("SYSTEM_MODE", "SIMULATION")
            _db_p = _os.getenv("NIFTY_DB_PATH") or ("data/trading_v4_live.db" if _mode != "SIMULATION" else "data/trading_v4_sim.db")
            if _os.path.exists(_db_p):
                with _sqlite3.connect(_db_p) as _conn:
                    _conn.row_factory = _sqlite3.Row
                    _cur = _conn.execute("PRAGMA table_info(trade_outcomes)")
                    if _cur.fetchall():
                        _c_rows = _conn.execute(
                            "SELECT * FROM trade_outcomes WHERE signal_timestamp LIKE ? AND result IN ('WIN', 'LOSS', 'BREAKEVEN')",
                            (f"{_today_s}%",)
                        ).fetchall()
                        _existing = {str(c.get("trade_id")) for c in self.closed_positions_today}
                        for _cr in _c_rows:
                            _cd = dict(_cr)
                            _cid = str(_cd.get("trade_id") or "")
                            if _cid and _cid not in _existing:
                                self.closed_positions_today.append(_cd)
                                _existing.add(_cid)
        except Exception as e:
            self.logger.error(f"Failed to recover live state from OMS: {e}")

    # ══════════════════════════════════════
    # CORE: CAN WE TRADE?
    # ══════════════════════════════════════

    def can_trade(self) -> Tuple[bool, str]:
        """
        THE GATEKEEPER.
        Returns (allowed, reason).
        Called BEFORE any signal processing.
        """

        # Phase 5: Loss Cooldown Check (30-minute freeze after stop-out)
        if self.last_loss_time:
            elapsed = (datetime.now() - self.last_loss_time).total_seconds()
            if elapsed < 1800:
                return False, f"Loss Cooldown active: {int((1800 - elapsed) / 60)}m remaining"

        # Reset daily if new day
        self._check_daily_reset()

        # Check halt
        if self.is_halted:
            if hasattr(self, 'halt_auto_resume_ts') and self.halt_auto_resume_ts:
                import time
                if time.time() > self.halt_auto_resume_ts:
                    self.is_halted = False
                    self.halt_reason = ""
                    self.halt_auto_resume_ts = 0
                    self.logger.info("✅ Auto-resume timeout reached. System un-halted.")
                else:
                    return False, f"HALTED: {self.halt_reason}"
            else:
                return False, f"HALTED: {self.halt_reason}"

        # Check daily trade limit
        if self.today_stats.trades_taken >= \
           self.config.max_daily_trades:
            return False, (
                f"Max daily trades reached "
                f"({self.today_stats.trades_taken}/"
                f"{self.config.max_daily_trades})"
            )

        # Check daily loss limit
        if self.today_stats.total_pnl <= \
           -self.config.max_daily_loss:
            self._halt_trading(
                f"Daily loss limit ₹{self.config.max_daily_loss:,.0f}"
            )
            return False, self.halt_reason

        daily_loss_pct = abs(self.today_stats.total_pnl) / \
                         self.total_capital * 100
        if self.today_stats.total_pnl < 0 and \
           daily_loss_pct >= self.config.max_daily_loss_pct:
            self._halt_trading(
                f"Daily loss {daily_loss_pct:.1f}% >= "
                f"{self.config.max_daily_loss_pct}%"
            )
            return False, self.halt_reason

        # Check weekly loss limit
        if self.weekly_pnl <= -self.config.max_weekly_loss:
            self._halt_trading(
                f"Weekly loss limit ₹{self.config.max_weekly_loss:,.0f}"
            )
            return False, self.halt_reason

        # Check drawdown
        if self.current_drawdown_pct >= \
           self.config.drawdown_halt_pct:
            self._halt_trading(
                f"Drawdown {self.current_drawdown_pct:.1f}% >= "
                f"halt threshold {self.config.drawdown_halt_pct}%"
            )
            return False, self.halt_reason

        # Check max open positions
        active = sum(
            1 for p in self.open_positions.values()
            if p.is_active
        )
        if active >= self.config.max_open_positions:
            return False, (
                f"Max open positions "
                f"({active}/{self.config.max_open_positions})"
            )

        # Check max capital deployed
        deployed_pct = self.deployed_capital / \
                       self.total_capital * 100
        if deployed_pct >= self.config.max_capital_deployed * 100:
            return False, (
                f"Max capital deployed "
                f"({deployed_pct:.0f}%)"
            )

        # Check cooldown between trades
        if self.last_trade_time:
            elapsed = (
                datetime.now() - self.last_trade_time
            ).total_seconds()
            if elapsed < self.config.min_time_between_trades:
                remaining = int(
                    self.config.min_time_between_trades - elapsed
                )
                return False, (
                    f"Trade cooldown: {remaining}s remaining"
                )

        return True, "OK"

    # ══════════════════════════════════════
    # POSITION SIZING
    # ══════════════════════════════════════

    def calculate_position_size(
        self,
        signal: Signal,
        current_price: float,
        atr: float,
    ) -> Dict:
        """
        Calculate exact position size based on:
        1. Risk per trade (% of capital)
        2. Signal confidence
        3. Drawdown adjustment
        4. ATR-based stop distance

        Returns: {lots, qty, risk_amount, sl_distance, ...}
        """

        # ── Base risk amount ──
        risk_pct = self.config.risk_per_trade_pct / 100
        base_risk = self.approved_capital_baseline * risk_pct

        # ── Phase 2 Gap Sizing Limit ──
        if signal.metadata.get("gap_detected", False):
            base_risk *= 0.5
            self.logger.warning(
                f"🛡️ GAP DETECTED: Slashing base risk by 50% for session to ₹{base_risk:,.0f}"
            )

        # ── Drawdown adjustment ──
        peak_drop_pct = ((self.master_high_water_mark - self.total_capital) / self.master_high_water_mark * 100) if self.master_high_water_mark > 0 else 0
        
        if peak_drop_pct >= 5.0:  # 5% from peak cuts risk by 50%
            drawdown_factor = 0.5
            base_risk *= drawdown_factor
            self.logger.warning(
                f"🛡️ DRAWDOWN BRAKE: 5% drop from peak. Base risk halved to ₹{base_risk:,.0f}"
            )
        elif self.current_drawdown_pct >= \
           self.config.drawdown_reduce_size_pct:
            drawdown_factor = max(0.3, 1 - (
                self.current_drawdown_pct -
                self.config.drawdown_reduce_size_pct
            ) / 20)
            base_risk *= drawdown_factor
            self.logger.warning(
                f"Drawdown adjustment: size reduced to "
                f"{drawdown_factor:.0%}"
            )
        else:
            drawdown_factor = 1.0

        # ── Dynamic Confidence/Quality-based lot sizing ──
        # Fix: Raw confidence is lowered heavily by regime penalty.
        # Instead of raw confidence > 70, we look at the exact Entry Quality
        # via the metadata (dominance and alignment).
        meta = signal.metadata if hasattr(signal, "metadata") and signal.metadata else {}
        
        quality = meta.get("quality", "UNKNOWN")
        gap = meta.get("dominance_gap", 0)
        directional_alignment = meta.get("directional_alignment", False)

        if gap >= 0.08 or quality == "STRONG":
            if directional_alignment:
                confidence_lots = self.config.max_lot_size  # Usually 3
            else:
                confidence_lots = max(1, self.config.max_lot_size - 1)
        elif gap >= 0.05 or quality == "MODERATE":
            confidence_lots = max(1, self.config.max_lot_size - 1)
        elif gap >= 0.04:
            confidence_lots = 1
        else:
            # Fallback for old tests / missing metadata
            confidence = signal.confidence
            lot_mapping = self.config.confidence_lot_mapping
            if confidence >= 90:
                confidence_lots = lot_mapping.get("90-100", 3)
            elif confidence >= 80:
                confidence_lots = lot_mapping.get("80-90", 2)
            elif confidence >= 70:
                confidence_lots = lot_mapping.get("70-80", 1)
            else:
                confidence_lots = lot_mapping.get("below_70", 0)

        # Apply alignment penalty
        if not directional_alignment and confidence_lots > 1 and gap < 0.08:
            # If gap >= 0.08 and misaligned, it was already penalized above
            confidence_lots -= 1  # Reduce size if agents are mixed
            self.logger.info("Reduced lot size by 1 due to lack of directional alignment.")

        if confidence_lots == 0:
            return {
                "lots": 0,
                "qty": 0,
                "risk_amount": 0,
                "reason": f"Entry Quality insufficient for minimum size (Gap: {gap:.3f}, Quality: {quality})",
                "allowed": False,
            }

        # ── P1-C: ATR Warm-Up Guard ──
        # ATR at 9:15–9:20 is computed from 1–2 candles. It's either abnormally
        # high (gap day) or abnormally low (noise). Reject if insufficient data.
        ATR_MIN_CANDLES = 10  # Do not trade if fewer candles are available
        ATR_MAX_SL_POINTS = 30  # Hard cap: SL can never exceed this
        ATR_MIN_SL_POINTS = 5   # Floor: prevent SL too tight

        candle_count = signal.metadata.get("candle_count", 999) if hasattr(signal, 'metadata') else 999
        if candle_count < ATR_MIN_CANDLES:
            self.logger.info(
                "Skipping trade: only %d candles (min %d required for ATR)",
                candle_count, ATR_MIN_CANDLES
            )
            return {
                "lots": 0,
                "qty": 0,
                "risk_amount": 0,
                "reason": f"ATR warm-up: only {candle_count} candles (min {ATR_MIN_CANDLES})",
                "allowed": False,
            }


        # ── P2: Quote Freshness Firewall ──
        quote = getattr(signal, "metadata", {}).get("quote")
        if quote and hasattr(quote, 'timestamp'):
            quote_age_ms = (datetime.now() - quote.timestamp).total_seconds() * 1000
            
            # 1. Age check (1500ms hard cutoff)
            if quote_age_ms > 1500:
                self.logger.warning(f"🚫 [STALE QUOTE] Quote age {quote_age_ms:.0f}ms > 1500ms threshold. Rejecting.")
                return {
                    "lots": 0, "qty": 0, "risk_amount": 0,
                    "reason": f"Stale Quote ({quote_age_ms:.0f}ms > 1500ms)",
                    "allowed": False
                }
                
            # 2. Frozen check (LTP unchanged while time advances artificially, or inverted spread)
            # This requires access to historical quote tracking, but we can do a basic spread check
            if quote.ask <= quote.bid:
                self.logger.warning(f"🚫 [FROZEN QUOTE] Ask (₹{quote.ask}) <= Bid (₹{quote.bid}). Inverted spread. Rejecting.")
                return {
                    "lots": 0, "qty": 0, "risk_amount": 0,
                    "reason": "Frozen/Inverted Quote (Ask <= Bid)",
                    "allowed": False
                }

        # ── PHASE A: Premium-based risk calculation ──
        quote = signal.metadata.get("quote")
        if quote and quote.ask > 0:
            premium_price = quote.ask
            # Sl is 20-25% of premium, with a hard floor to avoid gamma shakeouts
            sl_distance = max(premium_price * 0.25, 5.0) 
        else:
            # Fallback if no quote
            premium_price = current_price * 0.01 * 50
            sl_distance = max(premium_price * 0.25, 5.0)

        # ── Risk-based lot calculation ──
        risk_per_lot = sl_distance * self.config.lot_qty
        risk_based_lots = int(base_risk / risk_per_lot) \
            if risk_per_lot > 0 else 1

        # ── Final lot count (minimum of all constraints) ──
        final_lots = min(
            confidence_lots,
            risk_based_lots,
            self.config.max_lot_size,
        )
        final_lots = max(final_lots, self.config.min_lot_size)

        # ── INITIAL DEPLOYMENT HARD CAP ──
        # Not configurable. Hard-coded safety.
        MAX_LOTS_CAP = 1
        final_lots = min(final_lots, MAX_LOTS_CAP)

        # ── Capital check ──
        estimated_premium = premium_price
        capital_needed = estimated_premium * final_lots
        max_capital = self.total_capital * \
                      self.config.max_capital_per_trade

        if capital_needed > max_capital:
            final_lots = max(1, int(
                max_capital / estimated_premium
            ))

        # ── Final calculations ──
        qty = final_lots * self.config.lot_qty
        actual_risk = sl_distance * qty
        actual_risk = min(
            actual_risk, self.config.max_risk_per_trade
        )

        # Exit expectations based on entry quality
        if quality == "STRONG":
            t1_mult, t2_mult = 2.0, 3.0
        elif quality == "MODERATE":
            t1_mult, t2_mult = 1.5, 2.0
        else:
            t1_mult, t2_mult = 1.0, 1.5

        # Option premium ALWAYS goes UP when profitable (since we BUY CE or BUY PE)
        # We do not short options in this phase.
        sl_price = premium_price - sl_distance
        target_1 = premium_price + sl_distance * t1_mult
        target_2 = premium_price + sl_distance * t2_mult

        # ── Execution Buffer (Dynamic) ──
        # Adapts to volatility: Low vol -> small buffer, High vol -> large buffer
        execution_buffer = max(
            self.settings.trade_filter.execution_buffer_points,
            atr * 0.1
        )

        return {
            "lots": final_lots,
            "qty": qty,
            "risk_amount": round(actual_risk, 0),
            "risk_pct": round(actual_risk / self.total_capital * 100, 2),
            "sl_distance": round(sl_distance, 1),
            "sl_price": round(sl_price, 1),
            "target_1": round(target_1, 1),
            "target_2": round(target_2, 1),
            "execution_buffer": round(execution_buffer, 2),
            "drawdown_factor": drawdown_factor,
            "confidence_lots": confidence_lots,
            "risk_lots": risk_based_lots,
            "allowed": True,
            "reason": "OK",
        }

    # ══════════════════════════════════════
    # POSITION LIFECYCLE
    # ══════════════════════════════════════

    @property
    def dhan(self):
        """Lazy load Dhan client or use injected broker (e.g. for simulation)."""
        if self.broker:
            return self.broker
        from dhan_client import get_dhan_client
        return get_dhan_client()

    async def _place_order_async(self, **kwargs):
        """Async wrapper around Dhan API to prevent blocking the event loop."""
        return await asyncio.wait_for(
            asyncio.to_thread(self.dhan.place_order, **kwargs),
            timeout=5.0
        )

    def open_position(
        self,
        signal: Signal,
        size_params: Dict,
        fill_price: float,
        premium: float = 0,
    ) -> Optional[OpenPosition]:
        """Open a new position"""

        if self.is_halted:
            self.logger.warning(f"Position entry blocked: SYSTEM HALTED ({self.halt_reason})")
            return None

        if not size_params.get("allowed", False):
            self.logger.warning(
                f"Position blocked: {size_params.get('reason')}"
            )
            return None

        position_id = getattr(signal, "id", None)
        if not position_id:
            position_id = str(uuid.uuid4())[:8]
            
        quote = getattr(signal, "metadata", {}).get("quote")
        entry_bid = quote.bid if quote else 0.0
        entry_ask = quote.ask if quote else 0.0
        quote_age_ms = (datetime.now() - getattr(quote, 'timestamp', datetime.now())).total_seconds() * 1000 if quote else 0.0
        spread_pct_entry = quote.spread_pct if quote else 0.0
        slippage_entry = fill_price - entry_ask if entry_ask > 0 and signal.direction.value.upper() == "BUY" else entry_bid - fill_price

        strike_val = getattr(signal, "strike", None)
        opt_type_val = getattr(signal, "option_type", "")
        expiry_val = getattr(signal, "expiry", None)
        sym_val = getattr(signal, "symbol", "NIFTY")
        if (strike_val is None or not opt_type_val or not expiry_val) and sym_val and sym_val != "NIFTY":
            import re
            m = re.search(r"NIFTY(\d{2}[A-Z]{3})?(\d{4,5})(CE|PE)", str(sym_val).upper())
            if m:
                if not expiry_val and m.group(1):
                    expiry_val = m.group(1)
                if strike_val is None and m.group(2):
                    try:
                        strike_val = float(m.group(2))
                    except Exception:
                        pass
                if not opt_type_val and m.group(3):
                    opt_type_val = m.group(3)

        position = OpenPosition(
            position_id=position_id,
            intent_id=getattr(signal, "intent_id", ""),
            entry_time=datetime.now(),
            signal_type=signal.signal_type,
            direction=signal.direction,
            symbol=sym_val,
            security_id=getattr(signal, "security_id", "") or "",
            strike=strike_val,
            option_type=opt_type_val,
            expiry=expiry_val,
            entry_price=fill_price,
            entry_bid=entry_bid,
            entry_ask=entry_ask,
            quote_age_ms=quote_age_ms,
            spread_pct_entry=spread_pct_entry,
            slippage_entry=slippage_entry,
            current_price=fill_price,
            stop_loss=size_params["sl_price"],
            original_stop_loss=size_params["sl_price"],
            target_1=size_params["target_1"],
            target_2=size_params["target_2"],
            trailing_stop=size_params["sl_price"],
            lots=size_params["lots"],
            qty=size_params["qty"],
            entry_premium=premium,
            confidence_at_entry=signal.confidence,
            regime_at_entry=signal.regime.value if hasattr(signal.regime, "value") else str(signal.regime),
            weighted_score=signal.weighted_score,
            calibrated_confidence=signal.metadata.get("calibrated_confidence", signal.weighted_score),
            buy_score=signal.buy_score,
            sell_score=signal.sell_score,
            agent_breakdown=signal.agent_breakdown,
            volatility_at_entry=size_params.get("volatility", 0),
            entry_type=signal.metadata.get("context", {}).get("entry_type", "AI"),
            last_sl_price=size_params["sl_price"],
            last_sl_update_time=time.time(),
            # ── TSL initial state ──
            tsl_highest_premium=premium if premium > 0 else fill_price,
            tsl_highest_premium_time=datetime.now(),
            tsl_grade=signal.grade.value if hasattr(signal.grade, "value") else "B",
            tsl_regime=signal.regime.value if hasattr(signal.regime, "value") else "UNKNOWN",
            iv_at_entry=signal.metadata.get("snapshot_summary", {}).get("atm_iv", 0.0) if hasattr(signal, "metadata") else 0.0,
            underlying_price_at_entry=signal.metadata.get("snapshot_summary", {}).get("spot", fill_price) if hasattr(signal, "metadata") else fill_price,
        )

        self.open_positions[position_id] = position
        self.deployed_capital += premium * size_params["qty"] \
            if premium > 0 else \
            fill_price * 0.01 * size_params["qty"]

        self.last_trade_time = datetime.now()
        self.today_stats.trades_taken += 1

        # ── Persist to trade_outcomes in OPEN state ──
        try:
            import os as _os
            import sqlite3 as _sqlite3
            _mode = _os.getenv("SYSTEM_MODE", "SIMULATION")
            _db_p = _os.getenv("NIFTY_DB_PATH") or ("data/trading_v4_live.db" if _mode != "SIMULATION" else "data/trading_v4_sim.db")
            _dir = _os.path.dirname(_db_p)
            if not _dir or _os.path.exists(_dir):
                with _sqlite3.connect(_db_p) as _conn:
                    _conn.execute("""
                    CREATE TABLE IF NOT EXISTS trade_outcomes (
                        trade_id TEXT PRIMARY KEY,
                        signal_timestamp TEXT,
                        opened_at TEXT,
                        closed_at TEXT,
                        contract TEXT,
                        strike REAL,
                        option_type TEXT,
                        qty INTEGER,
                        entry REAL,
                        sl REAL,
                        target REAL,
                        exit_price REAL,
                        net_pnl REAL,
                        r_multiple REAL,
                        result TEXT,
                        confidence REAL,
                        grade TEXT,
                        source TEXT,
                        campaign_id TEXT,
                        session_id TEXT
                    )
                    """)
                    _sig_type = signal.signal_type.value if hasattr(signal.signal_type, 'value') else str(signal.signal_type)
                    _contract_name = position.symbol if position.symbol and position.symbol != "NIFTY" else (f"{position.symbol}_{int(position.strike)}_{_sig_type}" if position.strike else _sig_type)
                    _conn.execute("""
                        INSERT OR REPLACE INTO trade_outcomes (
                            trade_id, signal_timestamp, opened_at, closed_at, contract, strike, option_type,
                            qty, entry, sl, target, exit_price, net_pnl, r_multiple, result, confidence, grade, source
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        position.position_id,
                        position.entry_time.isoformat(),
                        position.entry_time.isoformat(),
                        None,
                        _contract_name,
                        position.strike,
                        position.option_type or ("CE" if "CE" in _sig_type else "PE"),
                        position.qty,
                        position.entry_price,
                        position.stop_loss,
                        position.target_1,
                        None,
                        0.0,
                        0.0,
                        "OPEN",
                        position.confidence_at_entry or position.calibrated_confidence,
                        position.tsl_grade,
                        "position_manager"
                    ))
                    _conn.commit()
        except Exception as _pe_db:
            self.logger.warning(f"Failed to record opened position in trade_outcomes: {_pe_db}")

        self.logger.info(
            f"OPENED: {position_id} | "
            f"{signal.signal_type.value} | "
            f"Entry: ₹{fill_price:,.1f} | "
            f"SL: ₹{size_params['sl_price']:,.1f} | "
            f"Lots: {size_params['lots']} | "
            f"Risk: ₹{size_params['risk_amount']:,.0f}"
        )

        try:
            analytics_bus.publish("trade_opened", {
                "position": position.to_dict(),
                "signal_price": getattr(signal.metadata.get("quote", None), "ask", fill_price) if getattr(signal, "metadata", None) else fill_price,
            })
        except Exception as e:
            self.logger.error(f"Analytics trade_opened publish failed: {e}")

        return position

    async def open_position_with_sl_guarantee(
        self,
        signal: Signal,
        size_params: Dict,
        fill_price: float,
        premium: float = 0,
    ) -> Optional[OpenPosition]:
        """
        P0-E: Atomic-as-possible entry + SL placement.
        Returns OpenPosition if both entry AND SL are successfully placed.
        Returns None and halts trading if SL cannot be placed after retries.
        """
        async with self._trade_lock:
            # ── Double Check `can_trade` under lock ──
            allowed, reason = self.can_trade()
            if not allowed:
                self.logger.warning(f"Position blocked under lock: {reason}")
                return None

            if not size_params.get("allowed", False):
                self.logger.warning(f"Position blocked: {size_params.get('reason')}")
                return None

            # ── Spread Explosion Filter ──
            # Reject if bid-ask spread has blown out — signal may be technically
            # valid but execution would destroy expected edge.
            quote = getattr(signal, "metadata", {}).get("quote")
            if quote and hasattr(quote, "ask") and hasattr(quote, "bid") and quote.ask > 0:
                spread_abs = quote.ask - quote.bid
                spread_pct = (spread_abs / quote.ask) * 100

                max_spread_abs = getattr(
                    getattr(self.settings, "alerts", None), "max_spread_abs", 8.0
                )
                max_spread_pct = getattr(
                    getattr(self.settings, "alerts", None), "max_spread_pct", 6.0
                )

                if spread_abs > max_spread_abs or spread_pct > max_spread_pct:
                    self.logger.warning(
                        "🚫 [SPREAD EXPLOSION] Spread ₹%.2f (%.1f%%) exceeds limits "
                        "(abs=₹%.1f, pct=%.1f%%). Trade blocked.",
                        spread_abs, spread_pct, max_spread_abs, max_spread_pct
                    )
                    return None


            # ── P1: Idempotent Intent Locking ──
            intent_id = getattr(signal, "intent_id", None)
            existing_order = None
            if intent_id:
                existing_order = self.oms.get_order(intent_id)
                # ALLOW adoption of "PENDING" or "ENTRY_SUBMITTED" orders created by the execution pipeline
                if existing_order and existing_order.get("state") not in ("PENDING", "ENTRY_SUBMITTED", "FAILED", "HALTED", "UNKNOWN"):
                    self.logger.warning(f"🚫 [IDEMPOTENCY GUARD] Duplicate execution attempt blocked for intent: {intent_id}")
                    return None
            else:
                intent_id = str(uuid.uuid4())
                signal.intent_id = intent_id
                
            # Prevent sqlite UNIQUE constraint failures by only creating intent if it doesn't already exist
            if not existing_order:
                self.oms.create_intent(
                    signal_id=getattr(signal, "id", "UNKNOWN"),
                    intent_id=intent_id,
                    symbol=getattr(signal, "symbol", "NIFTY"),
                    side="BUY",
                    qty=size_params["qty"],
                    requested_price=fill_price,
                    stop_loss_price=size_params["sl_price"],
                    target_price=size_params.get("target_1"),
                    strike=getattr(signal, "strike", None),
                    expiry=getattr(signal, "expiry", None),
                    option_type=getattr(signal, "option_type", None)
                )
            
            # ── P4: Shadow Execution Telemetry (Fire & Forget) ──
            try:
                # Capture t2_submit exactly at intent creation
                t0_sig = getattr(signal, "created_at", datetime.now())
                if isinstance(t0_sig, str):
                    t0_sig = datetime.fromisoformat(t0_sig)
                t1_quote = getattr(signal, "metadata", {}).get("quote", None)
                t1_quote_dt = t1_quote.timestamp if t1_quote else datetime.now()
                t2_sub = datetime.now()
                
                asyncio.create_task(
                    self.shadow_engine.process_signal(
                        signal=signal,
                        size_params=size_params,
                        t0_signal=t0_sig,
                        t1_quote=t1_quote_dt,
                        t2_submit=t2_sub
                    )
                )
            except Exception as e:
                self.logger.error(f"Shadow Engine integration error: {e}", exc_info=True)


            # ── Step 1: Place Entry Order ──
            qty = size_params["qty"]
            stop_loss_price = size_params["sl_price"]
            transaction_type = "BUY" if signal.direction.value.upper() == "BUY" else "SELL"
            sl_transaction_type = "SELL" if transaction_type == "BUY" else "BUY"
        
        self.logger.info(
            "Placing entry: %s %d qty | SL target: %.2f",
            getattr(signal, "symbol", "NIFTY"), qty, stop_loss_price
        )

        start_time = time.time()
        try:
            entry_response = await self._place_order_async(
                security_id=getattr(signal, "security_id", None),
                exchange_segment="NSE_FNO",
                transaction_type=transaction_type,
                quantity=qty,
                order_type="MARKET",
                product_type="INTRADAY"
            )
        except Exception as e:
            self.logger.error("Entry order failed — no position opened: %s", e)
            self.oms.update_order_state(intent_id, "FAILED", "BROKER_REJECTION")
            return None


        # Extract order ID from response (fallback to uuid if missing)
        order_id = entry_response.get("data", {}).get("orderId", str(uuid.uuid4())[:8])
        execution_delay_ms = int((time.time() - start_time) * 1000)

        # ── 🔒 RUNTIME BROKER ACK BREAKER CHECK (Phase 1.2) ──
        from core.system_state import get_state_manager
        state_mgr = get_state_manager()
        
        # Check ACK delay
        ack_delay_sec = execution_delay_ms / 1000.0
        if ack_delay_sec > 5.0:
            self.logger.warning(
                f"⚠️ LATE BROKER ACK DETECTED ({ack_delay_sec:.1f}s > 5.0s limit). "
                f"Halting system to verify fill status for {order_id}..."
            )
            state_mgr.trigger_structural_halt(
                f"Late broker ACK for order {order_id} ({ack_delay_sec:.1f}s > 5.0s limit). Polling broker for fill verification..."
            )
            
            # Aggressively poll order status for up to 15 seconds to resolve split-brain risk
            fill_found = False
            poll_start = time.time()
            while time.time() - poll_start < 15.0:
                try:
                    order_status_resp = self.dhan.get_order_status(order_id)
                    if order_status_resp and order_status_resp.get("status") == "success":
                        order_data = order_status_resp.get("data", {})
                        order_status = order_data.get("orderStatus", "")
                        if order_status == "TRADED":
                            self.logger.info(f"✅ Recovery: Late fill verified on broker for order {order_id}!")
                            fill_found = True
                            fill_price = order_data.get("price", fill_price)
                            break
                        elif order_status in ["CANCELLED", "REJECTED"]:
                            self.logger.info(f"🚫 Recovery: Order {order_id} confirmed as {order_status} on broker.")
                            break
                except Exception as pe:
                    self.logger.warning(f"Error polling recovery status: {pe}")
                await asyncio.sleep(1.0)
                
            if fill_found:
                # Registered locally to prevent split-brain before structural halt is executed
                position = self.open_position(signal, size_params, fill_price, premium)
                reason = f"Broker ACK high latency ({ack_delay_sec:.1f}s), but late fill successfully resolved."
                state_mgr.trigger_structural_halt(reason)
                self._halt_trading(reason)
                # Still try to place stop-loss since we are filled
                await self._place_sl_with_retry(
                    EntryResult(
                        filled=True,
                        order_id=order_id,
                        fill_price=fill_price,
                        fill_qty=qty,
                        symbol=getattr(signal, "symbol", "NIFTY"),
                        security_id=getattr(signal, "security_id", "") or "",
                        exchange_segment="NSE_FNO"
                    ),
                    stop_loss_price,
                    sl_transaction_type
                )
                return position
            else:
                reason = f"Critical Broker ACK timeout: order {order_id} status unverified after 15s polling."
                state_mgr.trigger_structural_halt(reason)
                self._halt_trading(reason)
                return None

        fill = EntryResult(
            filled=True,
            order_id=order_id,
            fill_price=fill_price,
            fill_qty=qty,
            symbol=getattr(signal, "symbol", "NIFTY"),
            security_id=getattr(signal, "security_id", "") or "",
            exchange_segment="NSE_FNO"
        )

        self.logger.info(
            "Entry filled: %s @ %.2f (%d qty) | order_id=%s | delay=%dms",
            fill.symbol, fill.fill_price, fill.fill_qty, fill.order_id, execution_delay_ms
        )

        # Log Execution Quality
        try:
            from performance_logger import PerformanceLogger
            perf = PerformanceLogger()
            spread = 0.0 # Will need level 2 data for real spread
            slippage = fill.fill_price - signal.entry_price
            perf.log_execution_quality(
                trade_id=getattr(signal, "id", order_id),
                signal_price=signal.entry_price,
                fill_price=fill.fill_price,
                slippage=slippage,
                spread=spread,
                delay_ms=execution_delay_ms
            )
        except Exception as e:
            self.logger.error(f"Failed to log execution quality: {e}")

        # ── Step 2: Record position locally IMMEDIATELY ──
        # Track position even if SL fails, so deadman/reconciliation catches it.
        position = self.open_position(signal, size_params, fill_price, premium)
        if not position:
            return None

        self.oms.update_order_state(intent_id, "ENTRY_FILLED", "ORDER_FILL")

        # ── Step 3: Place SL with retry loop & verification ──
        sl_placed = await self._place_sl_with_retry(fill, stop_loss_price, sl_transaction_type)

        if sl_placed:
            self.logger.info("SL confirmed placed for %s @ %.2f", fill.symbol, stop_loss_price)
            return position

        # ── Step 4: SL failed after all retries — emergency halt ──
        self.logger.critical(
            "SL_PLACEMENT_FATAL_FAILURE",
            extra={
                "symbol": fill.symbol,
                "qty": fill.fill_qty,
                "price": fill.fill_price,
                "action": "HALTING_TRADING"
            }
        )

        self._halt_trading("SL PLACEMENT FAILED: Broker API Unresponsive")

        # Attempt immediate market close as last resort
        await self._emergency_close_position(fill, sl_transaction_type)

        return None

    async def _place_sl_with_retry(
        self, fill: EntryResult, stop_loss_price: float, sl_transaction_type: str
    ) -> bool:
        """Retry SL placement up to SL_MAX_RETRIES times with hard total deadline."""
        deadline = time.monotonic() + SL_PLACEMENT_TIMEOUT_SECONDS
        client_id = f"SL_{fill.order_id}"

        for attempt in range(1, SL_MAX_RETRIES + 1):
            if time.monotonic() >= deadline:
                self.logger.error(
                    "SL_PLACEMENT_DEADLINE_EXCEEDED",
                    extra={"symbol": fill.symbol, "timeout_sec": SL_PLACEMENT_TIMEOUT_SECONDS}
                )
                break

            # ── Duplicate Guard: Check if SL already exists ──
            if await self._verify_sl_order(fill.symbol, stop_loss_price, client_id):
                self.logger.info("SL already exists — skipping placement (attempt %d)", attempt)
                return True

            try:
                self.logger.info(
                    "SL_PLACEMENT_ATTEMPT",
                    extra={
                        "symbol": fill.symbol,
                        "attempt": attempt,
                        "max_attempts": SL_MAX_RETRIES,
                        "price": stop_loss_price,
                        "client_id": client_id
                    }
                )

                remaining = max(0.1, deadline - time.monotonic())
                await self._place_order_async(
                    security_id=fill.security_id,
                    exchange_segment=fill.exchange_segment,
                    transaction_type=sl_transaction_type,
                    quantity=fill.fill_qty,
                    order_type="SL-M",
                    product_type="INTRADAY",
                    trigger_price=stop_loss_price,
                    correlation_id=client_id,  # Map to clientId / correlationId
                    correlationId=client_id
                )
            except asyncio.TimeoutError:
                self.logger.warning("SL_PLACEMENT_TIMEOUT", extra={"attempt": attempt})
            except Exception as e:
                self.logger.error("SL_PLACEMENT_ERROR", extra={"attempt": attempt, "error": str(e)})

            # ── VERIFY (CRITICAL AFTER TIMEOUT OR FAILURE) ──
            if await self._verify_sl_order(fill.symbol, stop_loss_price, client_id):
                self.logger.info("SL_VERIFIED_ON_BROKER", extra={"attempt": attempt})
                return True

            if attempt < SL_MAX_RETRIES:
                await asyncio.sleep(SL_RETRY_DELAY_SECONDS)

        return False

    async def _verify_sl_order(self, symbol: str, expected_trigger: float, client_id: str) -> bool:
        """Confirm broker actually has the SL order registered, preferably using correlation ID."""
        try:
            response = await asyncio.to_thread(self.dhan.get_order_list)
        except Exception as e:
            self.logger.error("ORDER_LIST_FETCH_FAILED", extra={"error": str(e)})
            return False

        if not response or response.get("status") != "success":
            return False

        orders = response.get("data", [])
        for order in orders:
            try:
                order_cid = order.get("correlationId") or order.get("clientId")
                
                # Match by Correlation ID if provided
                if order_cid == client_id:
                    return True
                
                # Fallback: strict symbol, type, status, and price match
                if (
                    order.get("tradingSymbol") == symbol
                    and order.get("orderType") in ("SL", "SL-M")
                    and order.get("orderStatus") in VALID_SL_STATUSES
                    and abs(float(order.get("triggerPrice", 0)) - expected_trigger) < 0.5
                ):
                    return True
            except Exception:
                continue

        return False

    async def _emergency_close_position(self, fill: EntryResult, sl_transaction_type: str) -> None:
        """Last resort: if SL can't be placed, exit immediately at market with retries."""
        self.logger.critical(
            "EMERGENCY_CLOSE_ATTEMPT",
            extra={"symbol": fill.symbol, "qty": fill.fill_qty}
        )
        
        for attempt in range(1, 4):
            try:
                await self._place_order_async(
                    security_id=fill.security_id,
                    exchange_segment=fill.exchange_segment,
                    transaction_type=sl_transaction_type,
                    quantity=fill.fill_qty,
                    order_type="MARKET",
                    product_type="INTRADAY",
                )
                self.logger.critical("EMERGENCY_CLOSE_SUCCESS", extra={"symbol": fill.symbol, "attempt": attempt})
                return
            except Exception as e:
                self.logger.error("EMERGENCY_CLOSE_ERROR", extra={"attempt": attempt, "error": str(e)})
                await asyncio.sleep(1)

        self.logger.critical(
            "EMERGENCY_CLOSE_FATAL_FAILURE",
            extra={"symbol": fill.symbol, "action": "MANUAL_INTERVENTION_REQUIRED"}
        )
        
        # Send Telegram alert
        try:
            from utils.tasks import fire_and_log
            if hasattr(self, 'telegram_bot') and self.telegram_bot:
                fire_and_log(
                    self.telegram_bot._send_admin_msg(
                        f"🚨 <b>EMERGENCY EXIT FAILED</b> 🚨\n\n"
                        f"Position: {fill.symbol} ({fill.fill_qty} qty)\n"
                        f"SL failed AND emergency market close failed after 3 attempts.\n"
                        f"<b>Immediate manual intervention required!</b>"
                    ),
                    label="emergency_exit_fatal"
                )
        except Exception:
            pass

    def update_positions(self, current_price: float, snapshot=None, current_signal=None) -> List[Dict]:
        """
        Monitor and update all open positions.
        Now delegates to PositionPipeline for trade health, trailing stop logic, and exit decisions.
        """
        actions_taken = []
        
        # In the new architecture, PositionPipeline runs in Orchestrator/Main,
        # but for now we'll hook it here to avoid breaking everything before Orchestrator is ready.
        if not hasattr(self, "_position_pipeline"):
            from core.pipelines.position_pipeline import PositionPipeline
            from core.context import RuntimeContext
            ctx = RuntimeContext(
                settings=self.settings,
                mode=self.mode,
                is_simulation=self.mode == "SIMULATION",
                telegram_enabled=False,
                db_manager=None,
                data_manager=None,
                burnin_tracker=None,
                readiness_scorer=None,
                simulation=None
            )
            self._position_pipeline = PositionPipeline(ctx)
            
        for pos_id, pos in list(self.open_positions.items()):
            # 1. Evaluate position via Pipeline
            from models.position import PositionState, PositionAction
            
            # Since PositionManager already uses OpenPosition dataclass (which is similar to PositionState),
            # we can pass it directly. But wait, PositionPipeline expects PositionState!
            # Since OpenPosition and PositionState share 99% of fields, let's just pass `pos` as duck-typed PositionState.
            # In Python, this works seamlessly if attributes match.
            
            # The pipeline handles PnL update, trade health, and generates actions.
            pipeline_actions = self._position_pipeline.evaluate(pos, snapshot, None, current_signal)
            
            for action in pipeline_actions:
                if action.action_type == "FULL_EXIT":
                    reason = action.reason
                    exit_p = pos.current_price if hasattr(pos, "current_price") and pos.current_price > 0 else (pos.entry_price if hasattr(pos, "entry_price") else current_price)
                    pnl = self.close_position(pos_id, exit_p, reason)
                    if pnl is not None:
                        actions_taken.append({
                            "position_id": pos_id,
                            "type": "exit",
                            "reason": reason,
                            "pnl": pnl
                        })
                elif action.action_type == "PARTIAL_EXIT":
                    pass # TODO: implement partial exit handling
                elif action.action_type == "UPDATE_SL":
                    new_sl = action.target_price
                    pos.stop_loss = new_sl
                    # If live, update OMS and broker
                    if self.mode != "SIMULATION":
                        if pos.intent_id and hasattr(self, "oms") and self.oms:
                            try:
                                self.dhan.modify_order(...)
                                # In real system, ExecutionPipeline should handle this. 
                                # For now, we update state.
                                pass
                            except Exception as e:
                                self.logger.error(f"Failed to update live SL: {e}")
                                
                    actions_taken.append({
                        "position_id": pos_id,
                        "type": "sl_update",
                        "new_sl": new_sl,
                        "reason": action.reason
                    })
                    self.logger.info(f"🛡️ [TSL] {pos.symbol} Stop Loss Trailed to ₹{new_sl:,.1f} | Phase: {pos.tsl_phase} | Reason: {action.reason}")
        
        return actions_taken

    def close_position(
        self,
        position_id: str,
        exit_price: float,
        reason: str,
        partial_qty: int = 0,
    ) -> Optional[Dict]:
        """Close or partially close a position"""

        if position_id not in self.open_positions:
            return None

        pos = self.open_positions[position_id]

        if partial_qty > 0 and partial_qty < pos.qty:
            # Partial close
            if pos.direction == Direction.BULLISH:
                pnl = (exit_price - pos.entry_price) * partial_qty
            else:
                pnl = (pos.entry_price - exit_price) * partial_qty

            pos.qty -= partial_qty
            pos.realized_pnl += pnl

            self.logger.info(
                f"PARTIAL CLOSE: {position_id} | "
                f"Qty: {partial_qty} | "
                f"PnL: ₹{pnl:,.0f} | "
                f"Remaining: {pos.qty}"
            )

            try:
                analytics_bus.publish("trade_closed", {
                    "position": pos.to_dict(),
                    "exit_price": exit_price,
                    "theoretical_exit": exit_price,
                    "partial": True
                })
            except Exception as e:
                self.logger.error(f"Analytics trade_closed publish failed: {e}")

            return {
                "type": "partial",
                "pnl": pnl,
                "remaining_qty": pos.qty,
            }
        else:
            # Full close
            pos.update_pnl(exit_price)
            total_pnl = pos.unrealized_pnl + pos.realized_pnl
            pos.is_active = False

            # Update stats
            self._record_trade_result(total_pnl, reason)

            # Release capital
            self.deployed_capital = max(
                0, self.deployed_capital -
                (pos.entry_premium * pos.qty
                 if pos.entry_premium > 0
                 else pos.entry_price * 0.01 * pos.qty)
            )

            hold_duration = (
                datetime.now() - pos.entry_time
            ).total_seconds() / 60

            self.logger.info(
                f"CLOSED: {position_id} | "
                f"Reason: {reason} | "
                f"PnL: ₹{total_pnl:,.0f} | "
                f"Hold: {hold_duration:.1f}min"
            )

            # ── P0.5: Exact Net P&L Calculation ──
            try:
                from core.economics import CostEngine
                costs = CostEngine.calculate_costs(
                    entry_price=pos.entry_price,
                    exit_price=exit_price,
                    qty=pos.qty,
                    direction="BUY"
                )
                
                exec_metrics = {
                    "holding_seconds": hold_duration * 60,
                    "mfe": pos.max_favorable,
                    "mae": pos.max_adverse,
                    "realized_r_multiple": (costs["net_pnl"] / (abs(pos.entry_price - pos.original_stop_loss) * pos.qty)) if abs(pos.entry_price - pos.original_stop_loss) > 0 else 0,
                    "entry_bid": pos.entry_bid,
                    "entry_ask": pos.entry_ask,
                    "entry_fill": pos.entry_price,
                    "exit_fill": exit_price,
                    "spread_pct_entry": pos.spread_pct_entry,
                    "quote_age_ms": pos.quote_age_ms,
                    "slippage_entry": pos.slippage_entry,
                    "exit_bid": 0.0, "exit_ask": 0.0, "spread_pct_exit": 0.0, "slippage_exit": 0.0
                }
                
                if getattr(pos, "intent_id", ""):
                    import os as _os
                    _mode = _os.getenv("SYSTEM_MODE", "SIMULATION")
                    _econ_db = _os.getenv("NIFTY_DB_PATH") or ("data/trading_v4_live.db" if _mode != "SIMULATION" else "data/trading_v4_sim.db")
                    CostEngine.save_trade_economics(
                        db_path=_econ_db,
                        intent_id=pos.intent_id,
                        costs=costs,
                        execution_metrics=exec_metrics
                    )
                
                net_pnl = costs["net_pnl"]
                total_pnl = net_pnl  # Override legacy PnL with Net PnL!
            except Exception as e:
                self.logger.error(f"CostEngine failure: {e}")
                net_pnl = total_pnl

            result = {
                "type": "full",
                "pnl": total_pnl,
                "net_pnl": net_pnl,
                "reason": reason,
                "hold_minutes": hold_duration,
                "entry": pos.entry_price,
                "exit": exit_price,
                "max_favorable": pos.max_favorable,
                "max_adverse": pos.max_adverse,
            }

            # ── Log to Learning Layer ──
            try:
                trade_id_val = pos.position_id or (f"TRD_{pos.intent_id[4:]}" if getattr(pos, "intent_id", "").startswith("INT_") else (pos.intent_id or "UNKNOWN"))
                contract_val = pos.symbol if pos.symbol and pos.symbol != "NIFTY" else (f"{pos.symbol}_{int(pos.strike)}_{pos.signal_type.value}" if pos.strike else pos.signal_type.value)
                record = TradeRecord(
                    trade_id=trade_id_val,
                    timestamp=datetime.now().isoformat(),
                    signal=pos.signal_type.value,
                    contract=contract_val,
                    strike=pos.strike,
                    expiry=pos.expiry,
                    entry_price=pos.entry_price,
                    exit_price=exit_price,
                    stop_loss=pos.original_stop_loss or pos.stop_loss,
                    target_1=pos.target_1,
                    quantity=pos.qty,
                    confidence=pos.confidence_at_entry or pos.calibrated_confidence,
                    grade=pos.tsl_grade,
                    weighted_score=pos.weighted_score,
                    buy_score=pos.buy_score,
                    sell_score=pos.sell_score,
                    gap=abs(pos.buy_score - pos.sell_score),
                    agent_breakdown=pos.agent_breakdown,
                    market_regime=pos.regime_at_entry,
                    volatility=pos.volatility_at_entry,
                    time_of_day=datetime.now().strftime("%H:%M"),
                    entry_type=pos.entry_type,
                    pnl=total_pnl,
                    outcome="WIN" if total_pnl > 0 else ("LOSS" if total_pnl < 0 else "BREAKEVEN"),
                    max_favorable=pos.max_favorable,
                    max_adverse=pos.max_adverse,
                    time_in_trade=hold_duration
                )
                self.trade_logger.log_trade(record)
                self.closed_positions_today.append(record.to_dict())
            except Exception as e:
                self.logger.error(f"Failed to log trade to learning layer: {e}")

            # ── Feed ThresholdTuner with trade outcome ──
            try:
                if self.tuner is not None:
                    sl_dist = abs(pos.entry_price - pos.stop_loss)
                    meta    = pos.agent_breakdown.get("_meta", {})
                    self.tuner.record_trade(
                        pnl=total_pnl,
                        stop_distance=sl_dist,
                        gap=meta.get("dominance_gap", abs(pos.buy_score - pos.sell_score)),
                        confidence=pos.weighted_score,
                        quality=meta.get("quality", "UNKNOWN"),
                    )
            except Exception as te:
                self.logger.warning(f"Tuner record failed (non-fatal): {te}")

            # Remove from active
            del self.open_positions[position_id]

            # ── Update OMS order state to POSITION_CLOSED ──
            try:
                if self.oms and getattr(pos, "intent_id", None):
                    self.oms.update_order_state(
                        intent_id=pos.intent_id,
                        new_state="POSITION_CLOSED",
                        event_type="POSITION_CLOSED",
                        avg_fill_price=exit_price,
                        payload={"reason": reason, "net_pnl": total_pnl}
                    )
            except Exception as oe:
                self.logger.error(f"Failed to update OMS state on position close: {oe}")

            # ── Update SQLite trade_outcomes table ──
            try:
                import os as _os
                import sqlite3 as _sqlite3
                _mode = _os.getenv("SYSTEM_MODE", "SIMULATION")
                _db_p = _os.getenv("NIFTY_DB_PATH") or ("data/trading_v4_live.db" if _mode != "SIMULATION" else "data/trading_v4_sim.db")
                _dir = _os.path.dirname(_db_p)
                if not _dir or _os.path.exists(_dir):
                    with _sqlite3.connect(_db_p) as _conn:
                        _conn.execute("""
                        CREATE TABLE IF NOT EXISTS trade_outcomes (
                            trade_id TEXT PRIMARY KEY,
                            signal_timestamp TEXT,
                            opened_at TEXT,
                            closed_at TEXT,
                            contract TEXT,
                            strike REAL,
                            option_type TEXT,
                            qty INTEGER,
                            entry REAL,
                            sl REAL,
                            target REAL,
                            exit_price REAL,
                            net_pnl REAL,
                            r_multiple REAL,
                            result TEXT,
                            confidence REAL,
                            grade TEXT,
                            source TEXT,
                            campaign_id TEXT,
                            session_id TEXT
                        )
                        """)
                        _res_str = "WIN" if total_pnl > 0 else ("LOSS" if total_pnl < 0 else "BREAKEVEN")
                        _r_mult = (total_pnl / (abs(pos.entry_price - pos.original_stop_loss) * pos.qty)) if abs(pos.entry_price - pos.original_stop_loss) > 0 and pos.qty > 0 else 0.0
                        _intent_suffix = pos.intent_id.replace("INT_", "") if getattr(pos, "intent_id", None) else ""
                        _contract_name = pos.symbol if pos.symbol and pos.symbol != "NIFTY" else (f"{pos.symbol}_{int(pos.strike)}_{pos.signal_type.value}" if pos.strike else pos.signal_type.value)
                        _cur = _conn.execute("""
                            UPDATE trade_outcomes
                            SET exit_price = ?, net_pnl = ?, result = ?, closed_at = ?, r_multiple = ?,
                                contract = COALESCE(NULLIF(contract, 'NIFTY'), ?),
                                strike = COALESCE(strike, ?),
                                sl = COALESCE(NULLIF(sl, 0), ?),
                                target = COALESCE(NULLIF(target, 0), ?)
                            WHERE trade_id = ? OR trade_id LIKE ? OR (trade_id LIKE ? AND ? != '')
                        """, (
                            exit_price, total_pnl, _res_str, datetime.now().isoformat(), _r_mult,
                            _contract_name,
                            pos.strike,
                            pos.original_stop_loss or pos.stop_loss,
                            pos.target_1,
                            pos.position_id,
                            f"%{pos.position_id.split('-')[-1]}",
                            f"%{_intent_suffix}",
                            _intent_suffix
                        ))
                        if _cur.rowcount == 0:
                            _conn.execute("""
                                INSERT OR REPLACE INTO trade_outcomes (
                                    trade_id, signal_timestamp, opened_at, closed_at, contract, strike, option_type,
                                    qty, entry, sl, target, exit_price, net_pnl, r_multiple, result, confidence, grade, source
                                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, (
                                pos.position_id,
                                pos.entry_time.isoformat() if hasattr(pos.entry_time, "isoformat") else str(pos.entry_time),
                                pos.entry_time.isoformat() if hasattr(pos.entry_time, "isoformat") else str(pos.entry_time),
                                datetime.now().isoformat(),
                                _contract_name,
                                pos.strike,
                                pos.option_type or ("CE" if "CE" in pos.signal_type.value else "PE"),
                                pos.qty,
                                pos.entry_price,
                                pos.original_stop_loss or pos.stop_loss,
                                pos.target_1,
                                exit_price,
                                total_pnl,
                                _r_mult,
                                _res_str,
                                pos.confidence_at_entry or pos.calibrated_confidence,
                                pos.tsl_grade,
                                "position_manager"
                            ))
                        _conn.commit()
            except Exception as te_db:
                self.logger.error(f"Failed to update trade_outcomes in DB on close: {te_db}")

            try:
                analytics_bus.publish("trade_closed", {
                    "position": pos.to_dict(),
                    "exit_price": exit_price,
                    "theoretical_exit": exit_price,
                })
            except Exception as e:
                self.logger.error(f"Analytics trade_closed publish failed: {e}")

            return result

    # ══════════════════════════════════════
    # INTERNAL TRACKING
    # ══════════════════════════════════════

    def _record_trade_result(self, pnl: float, reason: str):
        """Record trade result to daily stats"""

        self.today_stats.total_pnl += pnl
        self.total_capital += pnl
        self.weekly_pnl += pnl
        self.recent_pnls.append(pnl)
        
        # Track exit reason analytics
        self.today_stats.exit_reasons[reason] = self.today_stats.exit_reasons.get(reason, 0) + 1

        if pnl > 0:
            self.today_stats.wins += 1
            self.today_stats.gross_profit += pnl
            self.today_stats.max_win = max(
                self.today_stats.max_win, pnl
            )
        elif pnl < 0:
            self.today_stats.losses += 1
            self.today_stats.gross_loss += abs(pnl)
            self.today_stats.max_loss = min(
                self.today_stats.max_loss, pnl
            )
            self.last_loss_time = datetime.now()
        else:
            self.today_stats.break_evens += 1

        # Update capital tracking
        self.today_stats.capital_current = self.total_capital
        self.peak_capital = max(self.peak_capital, self.total_capital)
        self.master_high_water_mark = max(self.master_high_water_mark, self.total_capital)
        self.today_stats.peak_capital = self.peak_capital

        # Master Drawdown brake
        raw_halt_pct = getattr(self.config, "drawdown_halt_pct", 10.0)
        master_halt_pct = float(raw_halt_pct) if isinstance(raw_halt_pct, (int, float)) and raw_halt_pct > 0 else 10.0
        if self.master_high_water_mark > 0:
            peak_drop_pct = ((self.master_high_water_mark - self.total_capital) / self.master_high_water_mark) * 100
            if peak_drop_pct >= master_halt_pct:
                reason = f"CRITICAL: {master_halt_pct:.1f}% Drawdown from Master Target hit ({peak_drop_pct:.1f}%)"
                self._halt_trading(reason)
                from core.system_state import get_state_manager
                get_state_manager().trigger_structural_halt(reason)

        # The Stability Gate for scaling
        if self.total_capital >= self.approved_capital_baseline * 1.10: # 10% gain
            pf_50 = self._calculate_pf50()
            if pf_50 > 1.3:
                self.approved_capital_baseline = self.total_capital
                self.logger.info(f"🟢 STABILITY GATE PASSED (PF50: {pf_50:.2f}). Scaling risk base to ₹{self.approved_capital_baseline:,.0f}")
            else:
                self.logger.warning(f"🛡️ STABILITY GATE BLOCKED. 10% gain reached but PF50={pf_50:.2f} <= 1.3")

        # Drawdown calculation
        if self.peak_capital > 0:
            self.current_drawdown_pct = (
                (self.peak_capital - self.total_capital) /
                self.peak_capital * 100
            )
            self.today_stats.max_drawdown = max(
                self.today_stats.max_drawdown,
                self.current_drawdown_pct,
            )

        # Equity curve
        self.equity_curve.append({
            "time": datetime.now(),
            "equity": self.total_capital,
            "pnl": pnl,
        })

        # Check post-trade circuit breakers
        self._check_circuit_breakers()

    def _calculate_pf50(self) -> float:
        gross_profit = sum(p for p in self.recent_pnls if p > 0)
        gross_loss = abs(sum(p for p in self.recent_pnls if p < 0))
        if gross_loss == 0:
            return 999.0 if gross_profit > 0 else 0.0
        return gross_profit / gross_loss

    def _check_circuit_breakers(self):
        """Check if any circuit breaker conditions are met"""
        from core.system_state import get_state_manager
        state_mgr = get_state_manager()

        # Daily loss
        if self.today_stats.total_pnl <= -self.config.max_daily_loss:
            reason = f"Daily loss ₹{abs(self.today_stats.total_pnl):,.0f} >= limit ₹{self.config.max_daily_loss:,.0f}"
            self._halt_trading(reason)
            state_mgr.trigger_financial_pause(reason)

        # Drawdown checks (dynamic based on total capital & config)
        drawdown_rupees = self.peak_capital - self.total_capital
        drawdown_pct = (drawdown_rupees / self.peak_capital * 100) if self.peak_capital > 0 else 0.0
        
        raw_halt_pct = getattr(self.config, "drawdown_halt_pct", 12.0)
        halt_pct = float(raw_halt_pct) if isinstance(raw_halt_pct, (int, float)) and raw_halt_pct > 0 else 12.0

        raw_reduce_pct = getattr(self.config, "drawdown_reduce_size_pct", 8.0)
        reduce_pct = float(raw_reduce_pct) if isinstance(raw_reduce_pct, (int, float)) and raw_reduce_pct > 0 else 8.0

        halt_rupees = self.peak_capital * (halt_pct / 100.0) if self.peak_capital > 0 else 12000.0
        reduce_rupees = self.peak_capital * (reduce_pct / 100.0) if self.peak_capital > 0 else 8000.0

        # Persistent halt
        if drawdown_pct >= halt_pct or drawdown_rupees >= halt_rupees:
            reason = f"Critical financial drawdown exceeded: {drawdown_pct:.1f}% (₹{drawdown_rupees:.0f} >= ₹{halt_rupees:,.0f})"
            self._halt_trading(reason)
            state_mgr.trigger_structural_halt(reason)
        # Temporary pause
        elif drawdown_pct >= reduce_pct or drawdown_rupees >= reduce_rupees:
            reason = f"Financial drawdown threshold reached: {drawdown_pct:.1f}% (₹{drawdown_rupees:.0f} >= ₹{reduce_rupees:,.0f})"
            self._halt_trading(reason)
            state_mgr.trigger_financial_pause(reason)

        # Weekly loss
        if self.weekly_pnl <= -self.config.max_weekly_loss:
            reason = f"Weekly loss ₹{abs(self.weekly_pnl):,.0f} >= limit ₹{self.config.max_weekly_loss:,.0f}"
            self._halt_trading(reason)
            state_mgr.trigger_financial_pause(reason)

    def _halt_trading(self, reason: str):
        """Halt all trading"""
        self.is_halted = True
        self.halt_reason = reason
        self.today_stats.is_halted = True
        self.today_stats.halt_reason = reason
        self.logger.error(f"🚨 TRADING HALTED: {reason}")

    def _check_daily_reset(self):
        """Reset daily stats if new trading day"""
        today = date.today()
        if self.today_stats.date != today:
            # Save yesterday's stats
            self.daily_history.append(self.today_stats)

            # Check weekly reset
            if today.weekday() == 0:  # Monday
                self.weekly_pnl = 0
                self.week_start = today

            # Create new day
            self.today_stats = DailyStats(
                date=today,
                capital_start=self.total_capital,
                capital_current=self.total_capital,
                peak_capital=self.peak_capital,
            )
            self.closed_positions_today.clear()
            self.is_halted = False
            self.halt_reason = ""

            self.logger.info(
                f"New trading day | Capital: "
                f"₹{self.total_capital:,.0f}"
            )

    def _get_week_start(self) -> date:
        today = date.today()
        return today - timedelta(days=today.weekday())

    def close_all_positions(self, reason: str = "Emergency Telegram Override") -> bool:
        """
        Force-closes all open positions immediately via market orders on Dhan.
        Triggered primarily by the remote command layer.
        """
        self.logger.warning(f"🚨 TRIGGERING GLOBAL CLOSE: {reason}")
        
        if not self.open_positions:
            self.logger.info("No open positions to close.")
            return True
            
        success_count = 0
        total_positions = len(self.open_positions)
        
        # ── Step 1: Connect to Broker ──
        if not self.dhan:
            self.logger.error("FATAL: Could not connect to broker for square-off (no dhan client available)")
            return False
        # ── Step 2: Iterate and Sell ──
        for position_id, position in list(self.open_positions.items()):
            try:
                self.logger.critical(f"Nuclear Sell: {position.symbol} (Qty: {position.qty})")
                
                # Place Market Sell Order
                response = self.dhan.place_order(
                    security_id=position.security_id or "0", # Should be set
                    exchange_segment="NSE_FNO",
                    transaction_type="SELL",
                    quantity=position.qty,
                    order_type="MARKET",
                    product_type="INTRADAY"
                )
                
                if response.get("status") == "success":
                    self.logger.info(f"✅ Square-off Success: {position_id}")
                    # Update local state
                    self.close_position(position_id, position.current_price, "EMERGENCY_OVERRIDE")
                    success_count += 1
                else:
                    self.logger.error(f"❌ Square-off Failed: {position_id} | {response.get('remarks')}")
                    
            except Exception as e:
                self.logger.error(f"Exception during square-off for {position_id}: {str(e)}")
                
        self.logger.info(f"Successfully closed {success_count}/{total_positions} positions.")
        return success_count == total_positions

    # ══════════════════════════════════════
    # QUERIES
    # ══════════════════════════════════════

    def get_portfolio_heat(self) -> Dict:
        """How much risk is currently deployed"""
        total_unrealized = sum(
            p.unrealized_pnl for p in self.open_positions.values()
            if p.is_active
        )
        total_risk = sum(
            abs(p.entry_price - p.stop_loss) * p.qty
            for p in self.open_positions.values()
            if p.is_active
        )

        return {
            "open_positions": sum(
                1 for p in self.open_positions.values()
                if p.is_active
            ),
            "total_unrealized_pnl": f"₹{total_unrealized:,.0f}",
            "total_risk_deployed": f"₹{total_risk:,.0f}",
            "capital_deployed_pct": f"{self.deployed_capital / self.total_capital * 100:.1f}%",
            "drawdown": f"{self.current_drawdown_pct:.2f}%",
            "daily_pnl": f"₹{self.today_stats.total_pnl:,.0f}",
            "is_halted": self.is_halted,
        }

    def get_full_status(self) -> Dict:
        """Complete position manager status"""
        return {
            "capital": {
                "total": f"₹{self.total_capital:,.0f}",
                "available": f"₹{self.available_capital:,.0f}",
                "deployed": f"₹{self.deployed_capital:,.0f}",
                "peak": f"₹{self.peak_capital:,.0f}",
                "drawdown": f"{self.current_drawdown_pct:.2f}%",
            },
            "today": self.today_stats.to_dict(),
            "portfolio_heat": self.get_portfolio_heat(),
            "open_positions": {
                pid: pos.to_dict()
                for pid, pos in self.open_positions.items()
                if pos.is_active
            },
            "halted": self.is_halted,
            "halt_reason": self.halt_reason,
        }

    # ══════════════════════════════════════
    # PERSISTENCE
    # ══════════════════════════════════════

    @property
    def state_file(self):
        import os
        mode = os.getenv("SYSTEM_MODE", "SIMULATION")
        return "data/position_state_live.json" if mode != "SIMULATION" else "data/position_state_sim.json"

    def _load_state(self):
        data = load_json(self.state_file)
        if data:
            self.total_capital = data.get(
                "total_capital", self.config.total_capital
            )
            self.peak_capital = data.get(
                "peak_capital", self.total_capital
            )
            self.master_high_water_mark = data.get(
                "master_high_water_mark", self.total_capital
            )
            self.approved_capital_baseline = data.get(
                "approved_capital_baseline", self.total_capital
            )
            self.weekly_pnl = data.get("weekly_pnl", 0)

    def save_state(self):
        save_json({
            "total_capital": self.total_capital,
            "peak_capital": self.peak_capital,
            "master_high_water_mark": self.master_high_water_mark,
            "approved_capital_baseline": self.approved_capital_baseline,
            "weekly_pnl": self.weekly_pnl,
            "last_saved": datetime.now().isoformat(),
        }, self.state_file)
