"""
============================================
ENHANCED DATA MODELS v2
Supports 18 agents, confluence scoring,
signal quality grading
============================================
"""

import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Tuple
from enum import Enum


class Direction(Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"


class SignalType(Enum):
    BUY_CE = "BUY_CE"
    BUY_PE = "BUY_PE"
    NO_TRADE = "NO_TRADE"
    EXIT = "EXIT"


class Strength(Enum):
    STRONG = "STRONG"
    MODERATE = "MODERATE"
    WEAK = "WEAK"


class SignalGrade(Enum):
    A_PLUS = "A+"    # 90+ — elite setup, full alignment
    A = "A"          # 75-89 — very high quality
    B_PLUS = "B+"    # 60-74 — strong, tradeable
    B = "B"          # 45-59 — acceptable in trending regime
    C = "C"          # 30-44 — marginal, reduce size
    D = "D"          # below 30 — skip


class MarketRegime(Enum):
    TRENDING_UP = "TRENDING_UP"
    TRENDING_DOWN = "TRENDING_DOWN"
    RANGING = "RANGING"
    VOLATILE = "VOLATILE"
    SQUEEZE = "SQUEEZE"
    BREAKOUT = "BREAKOUT"
    UNKNOWN = "UNKNOWN"


class SessionPhase(Enum):
    PRE_MARKET = "PRE_MARKET"
    OPENING = "OPENING"
    MORNING = "MORNING"
    LUNCH = "LUNCH"
    AFTERNOON = "AFTERNOON"
    POWER_HOUR = "POWER_HOUR"
    CLOSING = "CLOSING"
    AFTER_HOURS = "AFTER_HOURS"


class TrapType(Enum):
    NONE = "NONE"
    FAKE_BREAKOUT_UP = "FAKE_BREAKOUT_UP"
    FAKE_BREAKOUT_DOWN = "FAKE_BREAKOUT_DOWN"
    LIQUIDITY_SWEEP = "LIQUIDITY_SWEEP"
    STOP_HUNT = "STOP_HUNT"


class DataSource(str, Enum):
    REAL = "real"
    SIMULATED = "simulated"
    UNKNOWN = "unknown"


class SignalStatus(str, Enum):
    """
    v4.8: Trade signal lifecycle states for Telegram notifications.
    Used by signal_formatter to display status and by future
    lifecycle notification handlers (target hits, trailing, close).
    """
    FRESH = "FRESH ✅"
    ACTIVE = "ACTIVE ✅"
    EXPIRING = "EXPIRING ⚠️"
    EXPIRED = "EXPIRED ⛔"
    T1_HIT = "T1 HIT 🎯"
    T2_HIT = "T2 HIT 🎯"
    T3_HIT = "T3 HIT 🎯"
    TRAILING = "TRAILING 🔄"
    BREAKEVEN = "BREAKEVEN 🛡️"
    CLOSED_WIN = "WIN 🏆"
    CLOSED_LOSS = "LOSS ❌"
    CLOSED_BREAKEVEN = "BREAKEVEN ⚪"


@dataclass
class AgentOutput:
    agent_name: str
    timestamp: datetime
    direction: Direction
    confidence: float
    strength: Strength
    details: Dict = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)

    # v2 additions
    is_blocker: bool = False       # if True, blocks all signals
    blocker_reason: str = ""
    sub_scores: Dict[str, float] = field(default_factory=dict)
    
    # v4 additions
    weight: float = 1.0            # dynamic weight applied by router

    def get_clamped_confidence(self) -> float:
        """Standardizes confidence to 0.1 - 0.95 scale."""
        val = self.confidence / 100.0 if self.confidence > 1 else self.confidence
        return max(0.1, min(val, 0.95))

    def to_dict(self) -> dict:
        return {
            "agent": self.agent_name,
            "time": self.timestamp.strftime("%H:%M:%S"),
            "direction": self.direction.value,
            "confidence": self.confidence,
            "strength": self.strength.value,
            "details": self.details,
            "warnings": self.warnings,
            "is_blocker": self.is_blocker,
            "weight": self.weight,
        }


@dataclass
class OptionQuote:
    """Live option premium and liquidity data"""
    security_id: str
    symbol: str
    ltp: float
    bid: float
    ask: float
    volume: int = 0
    oi: int = 0
    iv: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    is_stale: bool = False
    cache_age: float = 0.0
    cache_source: str = "api"

    @property
    def spread_pct(self) -> float:
        """Calculate the bid-ask spread as a percentage"""
        if self.ask > 0:
            return ((self.ask - self.bid) / self.ask) * 100
        return 0.0


@dataclass
class MarketSnapshot:
    timestamp: datetime
    price: float
    open: float
    high: float
    low: float
    close: float
    volume: int
    vwap: float
    rsi: float
    ema_fast: float
    ema_slow: float
    atr: float

    # Options
    total_ce_oi: float = 0
    total_pe_oi: float = 0
    pcr: float = 0
    max_pain: float = 0
    india_vix: float = 0

    # v2: Multi-timeframe
    rsi_5m: float = 50
    rsi_15m: float = 50
    ema_fast_5m: float = 0
    ema_slow_5m: float = 0
    ema_fast_15m: float = 0
    ema_slow_15m: float = 0
    vwap_5m: float = 0
    atr_5m: float = 0
    atr_15m: float = 0

    # v2: Correlation
    banknifty_price: float = 0
    banknifty_change_pct: float = 0
    sgx_nifty: float = 0
    dow_futures: float = 0

    # v2: Order flow
    bid_volume: float = 0
    ask_volume: float = 0
    large_buy_orders: int = 0
    large_sell_orders: int = 0

    # v2: Levels
    prev_day_high: float = 0
    prev_day_low: float = 0
    prev_day_close: float = 0
    day_open: float = 0
    pivot: float = 0
    r1: float = 0
    r2: float = 0
    r3: float = 0
    s1: float = 0
    s2: float = 0
    s3: float = 0
    cpr_top: float = 0
    cpr_bottom: float = 0

    # v2: Expiry
    days_to_expiry: int = 7
    is_expiry_day: bool = False
    is_monthly_expiry: bool = False

    # v2: Greeks
    net_delta: float = 0
    net_gamma: float = 0
    iv_atm: float = 0
    iv_skew: float = 0

    # v2: Institutional
    fii_net: float = 0
    dii_net: float = 0
    fii_index_futures_oi_change: float = 0

    # v2: Bollinger
    bb_upper: float = 0
    bb_lower: float = 0
    bb_middle: float = 0
    bb_width: float = 0

    # Expiry Day specific data
    # (Note: is_expiry_day and is_monthly_expiry are already defined above)
    expiry_type: str = "weekly"         # weekly | monthly
    time_to_expiry_hours: float = 0     # hours remaining
    minutes_to_close: int = 0

    # Straddle data
    atm_straddle_price: float = 0
    atm_straddle_open: float = 0        # straddle price at day open
    straddle_decay_pct: float = 0       # % decayed today

    # Premium tracking
    atm_ce_premium: float = 0
    atm_pe_premium: float = 0
    atm_ce_premium_open: float = 0
    atm_pe_premium_open: float = 0

    # Gamma data
    atm_gamma: float = 0
    gamma_exposure: float = 0           # net gamma * OI

    # OI concentration
    max_ce_oi_strike: float = 0         # highest CE OI strike
    max_pe_oi_strike: float = 0         # highest PE OI strike
    max_ce_oi_value: float = 0
    max_pe_oi_value: float = 0

    # IV surface
    atm_iv: float = 0
    iv_change_today: float = 0          # % change since open
    iv_percentile_30d: float = 50.0

    # ⚠️ P1.2: Data source flag for OI/Greeks fields
    # "real" = from broker API, "simulated" = generated locally
    # Agents MUST check this before making decisions on OI/Greeks/VIX data.
    oi_data_source: DataSource = DataSource.UNKNOWN
    
    # v4.6.1 Regime Context
    regime_state: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "time": self.timestamp.strftime("%H:%M:%S"),
            "price": self.price,
            "vwap": self.vwap,
            "rsi": round(self.rsi, 2),
            "atr": round(self.atr, 2),
            "pcr": round(self.pcr, 2),
            "vix": self.india_vix,
            "regime": self.regime_state.get("regime", ""),
            "session": "",
            "regime_state": self.regime_state
        }


@dataclass
class TradeOutcome:
    """Complete record of a trade for learning"""
    trade_id: str
    timestamp_entry: datetime
    timestamp_exit: Optional[datetime] = None
    signal_type: SignalType = SignalType.NO_TRADE
    direction: Direction = Direction.NEUTRAL

    # Prices
    entry_price: float = 0
    exit_price: float = 0
    stop_loss: float = 0
    target_1: float = 0
    option_entry_premium: float = 0
    option_exit_premium: float = 0

    # Result
    pnl: float = 0
    pnl_pct: float = 0
    result: str = "OPEN"              # WIN | LOSS | BREAK_EVEN

    # Context at entry
    confidence_at_entry: float = 0
    confluence_at_entry: float = 0
    agent_agreement_at_entry: float = 0
    regime_at_entry: str = ""
    session_phase_at_entry: str = ""
    rsi_at_entry: float = 0
    vwap_position_at_entry: str = ""
    atr_at_entry: float = 0
    vix_at_entry: float = 0
    dte_at_entry: int = 0
    is_expiry_day_trade: bool = False
    pcr_at_entry: float = 0

    # Agent votes at entry
    agent_votes_at_entry: Dict = field(default_factory=dict)

    # Timing
    hold_duration_minutes: float = 0
    entry_hour: int = 0
    entry_minute: int = 0
    day_of_week: int = 0              # 0=Monday

    # Categories (for pattern matching)
    market_condition: str = ""         # trending | ranging | volatile
    entry_quality: str = ""           # at_level | mid_range | chasing
    exit_reason: str = ""             # target | stoploss | manual | time

    def to_dict(self) -> dict:
        return {
            "id": self.trade_id,
            "entry_time": self.timestamp_entry.isoformat()
                if self.timestamp_entry else "",
            "exit_time": self.timestamp_exit.isoformat()
                if self.timestamp_exit else "",
            "signal": self.signal_type.value,
            "direction": self.direction.value,
            "entry": self.entry_price,
            "exit": self.exit_price,
            "pnl": self.pnl,
            "result": self.result,
            "confidence": self.confidence_at_entry,
            "confluence": self.confluence_at_entry,
            "regime": self.regime_at_entry,
            "session": self.session_phase_at_entry,
            "hold_minutes": self.hold_duration_minutes,
            "dte": self.dte_at_entry,
            "is_expiry": self.is_expiry_day_trade,
            "agents": self.agent_votes_at_entry,
        }


@dataclass
class ConfluenceResult:
    """Result of confluence analysis across all agents"""
    total_agents: int = 0
    bullish_agents: int = 0
    bearish_agents: int = 0
    neutral_agents: int = 0
    blocker_agents: int = 0
    
    weighted_bull_score: float = 0
    weighted_bear_score: float = 0
    
    confluence_ratio: float = 0      # 0 to 1 (1 = perfect agreement)
    dominant_direction: Direction = Direction.NEUTRAL
    
    agreeing_agents: List[str] = field(default_factory=list)
    disagreeing_agents: List[str] = field(default_factory=list)
    blocker_reasons: List[str] = field(default_factory=list)


@dataclass
class ExecutionPolicy:
    """Regime-specific overrides for a generated signal, preserving original intent."""
    suppressed: bool = False
    reason: str = ""
    
    # Delta tracking
    original_sl: float = 0
    adapted_sl: float = 0
    original_qty: int = 0
    adapted_qty: int = 0
    
    # Policies applied
    sl_multiplier: float = 1.0
    tp2_multiplier: float = 1.0
    position_scale: float = 1.0

    def to_dict(self) -> dict:
        return {
            "suppressed": self.suppressed,
            "reason": self.reason,
            "original_sl": self.original_sl,
            "adapted_sl": self.adapted_sl,
            "original_qty": self.original_qty,
            "adapted_qty": self.adapted_qty,
            "sl_multiplier": self.sl_multiplier,
            "tp2_multiplier": self.tp2_multiplier,
            "position_scale": self.position_scale,
        }


@dataclass
class Signal:
    id: str                                  # Added for Telegram callback tracking
    timestamp: datetime
    signal_type: SignalType
    direction: Direction
    confidence: float
    strength: Strength
    
    status: str = "new"                      # Added for lifecycle tracking
    execution_status: str = "pending"        # NEW: pending/executing/executed/failed
    created_at: float = field(default_factory=time.time) # Added for queue-level expiry
    updated_at: Optional[float] = None       # NEW: For auditing transition speeds
    queue_position: Optional[int] = None     # NEW: For ordered recovery
    metadata: Dict = field(default_factory=dict) # NEW: For any extra context

    entry_price: float = 0
    stop_loss: float = 0
    target_1: float = 0
    target_2: float = 0
    target_3: float = 0
    position_size: int = 0

    # v2: Weighted Intelligence (2026-04-09)
    weighted_score: float = 0
    buy_score: float = 0
    sell_score: float = 0
    uncertainty_multiplier: float = 1.0
    agent_breakdown: Dict = field(default_factory=dict)

    # v2 additions
    grade: SignalGrade = SignalGrade.D
    confluence: Optional[ConfluenceResult] = None
    regime: MarketRegime = MarketRegime.RANGING
    session_phase: SessionPhase = SessionPhase.MORNING
    risk_reward_ratio: float = 0
    expected_value: float = 0

    agent_votes: Dict = field(default_factory=dict)
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    # v2: Scoring breakdown
    primary_score: float = 0       # from core signal agents
    confirmation_score: float = 0  # from confirmation agents
    filter_score: float = 0        # from filter agents
    
    # v2: Context
    key_levels_nearby: List[float] = field(default_factory=list)
    suggested_adjustment: str = ""  # "tighten SL", "trail", etc.

    # Priority 2: Regime Execution Policy (overrides)
    execution_policy: Optional[ExecutionPolicy] = None

    def to_dict(self) -> dict:
        return {
            "time": self.timestamp.strftime("%H:%M:%S"),
            "signal": self.signal_type.value,
            "direction": self.direction.value,
            "confidence": f"{self.confidence:.1f}%",
            "execution_status": self.execution_status,
            "rejection_reason": self.metadata.get("rejection_reason", ""),
            "grade": self.grade.value,
            "strength": self.strength.value,
            "entry": self.entry_price,
            "sl": self.stop_loss,
            "target1": self.target_1,
            "target2": self.target_2,
            "target3": self.target_3,
            "qty": self.position_size,
            "rr_ratio": f"{self.risk_reward_ratio:.1f}",
            "regime": self.regime.value,
            "session": self.session_phase.value,
            "confluence": {
                "bullish": self.confluence.bullish_agents if self.confluence else 0,
                "bearish": self.confluence.bearish_agents if self.confluence else 0,
                "ratio": f"{self.confluence.confluence_ratio:.0%}" if self.confluence else "0%",
            },
            "reasons": self.reasons,
            "warnings": self.warnings,
            "premium_levels": self.metadata.get("premium_levels", {}),
            "symbol": getattr(self, "symbol", ""),
            "execution_policy": self.execution_policy.to_dict() if self.execution_policy else None,
            "execution_status": self.execution_status,
            "rejection_status": self.metadata.get("rejection_status", ""),
            "rejection_reason": self.metadata.get("rejection_reason", "")
        }

    def __str__(self) -> str:
        icon = "🟢" if self.signal_type == SignalType.BUY_CE else \
               "🔴" if self.signal_type == SignalType.BUY_PE else "⚪"

        conf = self.confluence
        conf_str = ""
        if conf:
            active_agents = conf.bullish_agents + conf.bearish_agents
            total_evaluated = conf.total_agents if conf.total_agents > 0 else 11
            conf_str = (
                f"   Directional Confluence: {conf.bullish_agents} bullish / {conf.bearish_agents} bearish\n"
                f"   Active Participation: {active_agents} of {total_evaluated} agents\n"
                f"   Agreeing          : {', '.join(conf.agreeing_agents[:5])}\n"
            )

        # Premium Levels mapping
        if "premium_levels" in self.metadata:
            pl = self.metadata["premium_levels"]
            levels_str = (
                f"   Premium Entry : ₹{pl.get('premium_entry', 0):,.1f}\n"
                f"   Premium SL    : ₹{pl.get('premium_sl', 0):,.1f}\n"
                f"   Premium T1    : ₹{pl.get('premium_t1', 0):,.1f}\n"
                f"   Premium T2    : ₹{pl.get('premium_t2', 0):,.1f}\n"
                f"   Spot Trigger  : ₹{self.entry_price:,.1f}\n"
                f"   Decay Risk    : {pl.get('decay_risk', 'Moderate')}\n"
                f"   Qty           : {self.position_size}\n"
                f"{'─'*60}\n"
            )
        else:
            levels_str = (
                f"   Entry      : ₹{self.entry_price:,.1f}\n"
                f"   Stop Loss  : ₹{self.stop_loss:,.1f}\n"
                f"   Target 1   : ₹{self.target_1:,.1f}\n"
                f"   Target 2   : ₹{self.target_2:,.1f}\n"
                f"   Target 3   : ₹{self.target_3:,.1f}\n"
                f"   Qty        : {self.position_size}\n"
                f"{'─'*60}\n"
            )

        return (
            f"\n{'='*60}\n"
            f"{icon} SIGNAL: {self.signal_type.value}  |  "
            f"GRADE: {self.grade.value}  |  "
            f"REGIME: {self.regime.value}\n"
            f"{'─'*60}\n"
            f"   Direction  : {self.direction.value}\n"
            f"   Confidence : {self.confidence:.1f}%\n"
            f"   Strength   : {self.strength.value}\n"
            f"   R:R Ratio  : {self.risk_reward_ratio:.1f}\n"
            f"{'─'*60}\n"
            f"{levels_str}"
            f"{conf_str}"
            f"   Scores     : Primary={self.primary_score:.0f} "
            f"Confirm={self.confirmation_score:.0f} "
            f"Filter={self.filter_score:.0f}\n"
            f"{'─'*60}\n"
            f"   Reasons    : {', '.join(self.reasons[:4])}\n"
            f"   Warnings   : {', '.join(self.warnings[:3]) if self.warnings else 'None'}\n"
            f"{'='*60}"
        )
