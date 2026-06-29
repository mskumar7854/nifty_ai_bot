"""
============================================
SETTINGS v3.2 — PRO MODE FINAL TUNING

These settings are the difference between
a demo and a money-making machine.

Every number here is calibrated for:
- Maximum signal quality
- Minimum false trades
- Controlled risk
- Sustainable profitability

DO NOT change these until you have
50+ trades of data to justify changes.

────────────────────────────────────────────
P2-D: CONFIGURATION PRECEDENCE CHAIN
────────────────────────────────────────────
Precedence (highest → lowest):
  1. Environment variables (set in .env or shell)
  2. This file (settings.py) — primary config
  3. Hardcoded defaults (in code)

Which file controls what:
  • Broker credentials:  ONLY in config/config.py (never here)
  • Agent weights:       ONLY in config/signal_weights.py
  • All other settings:  This file (settings.py) with ENV override

Pattern for every setting:
    SETTING_NAME: type = type(os.getenv("SETTING_NAME", "default"))

Dev override: copy settings.py to settings_local.py and import.
settings_local.py is git-ignored.
============================================
"""

import os
from dataclasses import dataclass, field
from typing import Dict, List
from dotenv import load_dotenv

load_dotenv()


# ══════════════════════════════════════════
# SYSTEM MODE
# ══════════════════════════════════════════

@dataclass
class SystemMode:
    """
    Controls system behavior globally.

    SIMULATION: Paper trading, no real money
    SMALL_CAPITAL: Real but tiny (₹5k-10k)
    SCALED: Full capital deployment
    """
    mode: str = "SIMULATION"           # SIMULATION | SMALL_CAPITAL | SCALED
    simulation_capital: float = 100000.0
    small_capital: float = 10000.0
    scaled_capital: float = 100000.0

    # ── P0 Fix: Orchestrator Decoupling ──
    # If the broker candle timestamp is frozen, how many seconds to wait
    # before forcing a decision engine cycle anyway?
    forced_decision_interval_sec: int = 30

    # Phase progression
    current_phase: int = 1              # 1=Sim, 2=Small, 3=Scaled
    phase_1_min_days: int = 3
    phase_1_min_trades: int = 15
    phase_1_min_win_rate: float = 55.0
    phase_1_max_drawdown: float = 10.0

    phase_2_min_days: int = 10
    phase_2_min_trades: int = 30
    phase_2_min_win_rate: float = 55.0
    phase_2_max_drawdown: float = 8.0

    # Logging
    log_every_signal: bool = True
    log_filter_kills: bool = True
    verbose_mode: bool = True


# ══════════════════════════════════════════
# PRO MODE TRADE FILTER (STRICT)
# ══════════════════════════════════════════

@dataclass
class TradeFilterConfig:
    """
    🔥 PRO MODE SETTINGS

    These are STRICT on purpose.
    Better to miss a trade than take a bad one.

    A missed trade costs you ₹0.
    A bad trade costs you ₹2000+.
    """

    # ── CONFIDENCE GATE (RAISED) ──
    min_signal_confidence: float = 80.0         # was 75 → now 80
    min_confluence_score: float = 70.0          # was 65 → now 70
    min_agent_agreement_pct: float = 55.0       # was 50 → now 55

    # ── REGIME GATE ──
    allowed_regimes_for_momentum: List[str] = field(
        default_factory=lambda: [
            "STRONG_TREND_UP",
            "STRONG_TREND_DOWN",
            "WEAK_TREND_UP",
            "WEAK_TREND_DOWN",
            "BREAKOUT",
        ]
    )
    allowed_regimes_for_mean_reversion: List[str] = field(
        default_factory=lambda: [
            "RANGING",
        ]
    )
    blocked_regimes: List[str] = field(
        default_factory=lambda: [
            "VOLATILE_CHOPPY",
        ]
    )

    # ── STRUCTURE GATE ──
    require_structure_alignment: bool = True
    blocked_structures: List[str] = field(
        default_factory=lambda: [
            "UNDEFINED",
            "EXPANDING",
        ]
    )

    # ── COST GATE ──
    min_expected_move_vs_breakeven: float = 2.0
    min_risk_reward_ratio: float = 1.5
    max_cost_pct_of_target: float = 15.0

    # ── TRADE LIMITS (SNIPER MODE) ──
    max_trades_per_day: int = 3                 # was 4 → now 3
    max_trades_per_session: Dict[str, int] = field(
        default_factory=lambda: {
            "morning": 2,
            "midday": 0,
            "power_hour": 1,
            "closing": 0,
        }
    )

    # ── LEARNING GATE (TIGHTENED) ──
    require_learning_approval: bool = True
    learning_min_confidence: float = 50.0       # was 40 → now 50
    learning_block_on_streak: int = -3

    # ── DECAY GATE ──
    max_theta_pct_per_hour: float = 3.0
    min_premium_time_value_pct: float = 20.0
    block_if_iv_crushing: bool = True

    # ── QUALITY GRADE (RAISED) ──
    grade_thresholds: Dict[str, float] = field(
        default_factory=lambda: {
            "A+": 92.0,
            "A": 82.0,
            "B+": 72.0,
            "B": 62.0,
            "C": 50.0,
        }
    )
    min_grade_to_trade: str = "B"               # was B+ → B for SIMULATION burn-in (2026-05-11)
                                                 # B+ rejected all live signals (prob cap at 0.41-0.44).
                                                 # B allows trades to accumulate for tuner calibration.
                                                 # Raise to B+ after 15+ trades confirm edge.

    # ── ADDITIONAL PRO FILTERS ──
    require_multi_tf_alignment: bool = True
    require_volume_above_average: bool = True
    block_first_5_minutes: bool = True
    block_last_10_minutes: bool = True
    block_around_news_events: bool = True
    min_atr_for_trade: float = 2.0             # lower for testing
    max_spread_pct: float = 1.0                 # max bid-ask spread

    # ── ADVANCED PRO SAFEGUARDS ──
    execution_buffer_points: float = 0.5        # Latency buffer (Base)
    min_candles_warmup: int = 50                # Indicator warmup
    market_open_safe_time: str = "09:20"        # Avoid opening volatility
    gap_threshold_points: float = 30.0          # Market open gap limit


# ══════════════════════════════════════════
# PRO MODE POSITION CONFIG
# ══════════════════════════════════════════

@dataclass
class PositionConfig:
    """Conservative position management"""

    total_capital: float = 100000.0
    max_capital_per_trade: float = 0.25         # 25% max
    max_capital_deployed: float = 0.50          # 50% max
    reserve_capital_pct: float = 0.25           # 25% reserve

    risk_per_trade_pct: float = 1.5             # was 2% → now 1.5%
    max_risk_per_trade_pct: float = 2.0
    min_risk_per_trade: float = 300.0
    max_risk_per_trade: float = 3000.0

    min_lot_size: int = 1
    max_lot_size: int = 3                       # was 5 → now 3
    lot_qty: int = 50

    confidence_lot_mapping: Dict = field(
        default_factory=lambda: {
            "90-100": 2,                        # was 3 → now 2
            "80-90": 1,                         # was 2 → now 1
            "70-80": 1,
            "below_70": 0,
        }
    )

    max_daily_loss: float = 3000.0              # was 5000 → now 3000
    max_daily_loss_pct: float = 3.0             # was 5% → now 3%
    max_weekly_loss: float = 8000.0
    max_weekly_loss_pct: float = 8.0
    max_drawdown_pct: float = 15.0
    drawdown_reduce_size_pct: float = 8.0
    drawdown_halt_pct: float = 12.0

    max_daily_trades: int = 3
    max_open_positions: int = 1                 # was 2 → now 1
    max_same_direction: int = 1
    min_time_between_trades: int = 300          # was 180 → now 300 (5 min)

    partial_profit_1_pct: float = 50.0
    partial_profit_2_pct: float = 30.0
    trail_remaining: bool = True
    trail_stop_atr_multiplier: float = 1.0  # legacy — superseded by Hybrid TSL below

    sl_type: str = "atr"
    sl_atr_multiplier: float = 1.5
    sl_fixed_points: float = 30.0
    sl_percentage: float = 2.0
    sl_move_to_cost_after_r1: bool = True

    # ══════════════════════════════════════════
    # HYBRID TSL CONFIG (Indian Weekly Options Tuned)
    # ══════════════════════════════════════════
    # Uses ADDITIVE (not multiplicative) grade + regime adjustments.
    # Multiplicative stacking (e.g. 1.4 × 1.3) can produce 18%+ trails
    # which give back huge profits on Nifty weekly options.
    # Additive approach: base=10% + A+(+2%) + Trend(+2%) = 14% max.
    # Hard clamps enforce floor and ceiling regardless of all adjustments.
    # ══════════════════════════════════════════

    tsl_enabled: bool = True

    # ── Profit milestones (% of entry premium) ──
    # Calibrated for Nifty weekly options noise level.
    tsl_breakeven_trigger_pct: float = 12.0    # At +12%: SL → entry (capital protected)
    tsl_activate_trigger_pct: float = 22.0     # At +22%: active trailing begins
    tsl_tighten_1_trigger_pct: float = 35.0    # At +35%: trail tightens
    tsl_tighten_2_trigger_pct: float = 50.0    # At +50%: tightest trail (lock max profits)

    # ── Base trail widths (% of peak premium) ──
    tsl_trail_pct_normal: float = 10.0         # Active phase default
    tsl_trail_pct_tighten_1: float = 8.0       # After +35%
    tsl_trail_pct_tighten_2: float = 5.5       # After +50%

    # ── Grade-based ADDITIVE adjustments ──
    # Positive = wider trail (let winner breathe)
    # Negative = tighter trail (exit marginal signals quickly)
    tsl_grade_adjustments: Dict = field(
        default_factory=lambda: {
            "A+": 2.0,   # +2% — elite setup, give it room
            "A":  1.0,   # +1%
            "B+": 0.0,   # Standard — no change
            "B":  -1.0,  # -1% tighter
            "C":  -2.0,  # -2% — exit quickly, marginal signal
        }
    )

    # ── Regime-based ADDITIVE adjustments ──
    tsl_regime_adjustments: Dict = field(
        default_factory=lambda: {
            "STRONG_TREND_UP":   2.0,   # +2% — trend days reward patience
            "STRONG_TREND_DOWN": 2.0,
            "BREAKOUT":          1.5,   # +1.5% — runners extend in breakouts
            "WEAK_TREND_UP":     0.5,
            "WEAK_TREND_DOWN":   0.5,
            "RANGING":          -1.5,   # -1.5% — chop kills options fast
            "VOLATILE_CHOPPY":  -2.0,   # -2% — reversals are violent
        }
    )

    # ── Hard clamps (override all adjustments) ──
    tsl_max_trail_pct: float = 15.0   # NEVER trail wider than 15% (prevents runaway)
    tsl_min_trail_pct: float = 5.0    # NEVER trail tighter than 5% (prevents noise stops)

    # ── Time-based idle tightening ──
    # If premium makes no new high for N minutes: theta is eating the position.
    # Tighten trail proactively to lock remaining value before decay.
    tsl_idle_tighten_enabled: bool = True
    tsl_idle_minutes_threshold: float = 15.0   # Stagnant for 15 min → tighten
    tsl_idle_tighten_by_pct: float = 2.0       # Reduce trail by 2% (e.g. 10% → 8%)


# ══════════════════════════════════════════
# PRO MODE EXIT CONFIG
# ══════════════════════════════════════════

@dataclass
class ExitConfig:
    """Intelligent exit settings"""

    max_hold_time_minutes: int = 45             # was 60 → now 45
    time_exit_if_flat_minutes: int = 15         # was 20 → now 15
    time_exit_if_flat_threshold_pct: float = 0.3

    exit_on_opposite_signal: bool = True
    exit_on_vwap_cross: bool = True
    exit_on_regime_change: bool = True
    exit_on_structure_break: bool = True

    move_sl_to_cost_at_rr: float = 1.0
    trail_after_rr: float = 1.5
    trail_step_pct: float = 30.0

    exit_if_theta_exceeding_pnl: bool = True
    max_hold_on_expiry_day_minutes: int = 20    # was 30 → now 20
    force_exit_before_close_minutes: int = 10

    daily_target_amount: float = 3000.0
    daily_target_pct: float = 3.0
    stop_after_daily_target: bool = True

    stop_after_consecutive_losses: int = 3
    reduce_size_after_loss: bool = True
    loss_size_reduction_pct: float = 50.0


# ══════════════════════════════════════════
# PRO MODE SESSION STRATEGY
# ══════════════════════════════════════════

@dataclass
class SessionStrategyConfig:
    """Time-based trading rules"""

    sessions: Dict[str, Dict] = field(
        default_factory=lambda: {
            "pre_open": {
                "start": "09:00", "end": "09:15",
                "trade": False,
                "reason": "Pre-market",
            },
            "opening_chaos": {
                "start": "09:15", "end": "09:25",
                "trade": False,
                "reason": "Opening volatility — traps everywhere",
            },
            "morning_prime": {
                "start": "09:25", "end": "10:30",
                "trade": True,
                "max_trades": 2,
                "strategy": "breakout_momentum",
                "min_confidence": 78,
                "reason": "BEST window — breakout + momentum",
            },
            "mid_morning": {
                "start": "10:30", "end": "12:00",
                "trade": True,
                "max_trades": 1,
                "strategy": "trend_continuation",
                "min_confidence": 85,
                "reason": "Only A+ continuation setups",
            },
            "lunch_dead": {
                "start": "12:00", "end": "13:30",
                "trade": True,  # Temporarily enabled for testing
                "max_trades": 1,
                "strategy": "lunch_scalp",
                "min_confidence": 75,
                "reason": "Lunch lull — theta burns, choppy moves",
            },
            "afternoon_setup": {
                "start": "13:30", "end": "14:15",
                "trade": True,  # Temporarily enabled for testing
                "max_trades": 1,
                "strategy": "scan_only",
                "min_confidence": 75,
                "reason": "Scanning for power hour setup",
            },
            "power_hour": {
                "start": "14:15", "end": "15:10",
                "trade": True,
                "max_trades": 1,
                "strategy": "directional_momentum",
                "min_confidence": 78,
                "reason": "Institutional activity — 1 quality trade",
            },
            "closing_zone": {
                "start": "15:10", "end": "15:30",
                "trade": False,
                "reason": "EXIT ONLY — close all positions",
            },
        }
    )


# ══════════════════════════════════════════
# LEGACY DATACLASSES (backward compat)
# ══════════════════════════════════════════

@dataclass
class TradingConfig:
    instrument: str = "NIFTY"
    capital: float = 100000.0
    max_risk_per_trade: float = 2.0
    max_daily_trades: int = 3
    max_daily_loss: float = 3000.0
    default_qty: int = 50
    slippage_buffer: float = 0.5
    auto_shutdown_after_market: bool = False


@dataclass
class AgentIntervals:
    market: int = 5
    momentum: int = 5
    oi: int = 10
    trap: int = 5
    sentiment: int = 60
    risk: int = 30
    time_session: int = 60
    multi_timeframe: int = 15
    price_action: int = 5
    volatility: int = 10
    correlation: int = 30
    expiry: int = 60
    order_flow: int = 5
    level: int = 30
    delta_gamma: int = 15
    institutional: int = 300
    gap: int = 60
    consolidation: int = 10
    learning: int = 120
    expiry_day: int = 5
    decay: int = 10


@dataclass
class ThresholdConfig:
    vwap_buffer: float = 5.0
    trend_ema_fast: int = 9
    trend_ema_slow: int = 21
    structure_lookback: int = 20
    rsi_overbought: float = 70.0
    rsi_oversold: float = 30.0
    rsi_bull_zone: float = 60.0
    rsi_bear_zone: float = 40.0
    volume_spike_multiplier: float = 1.5
    candle_body_ratio: float = 0.6
    oi_change_threshold: float = 100000
    pcr_bullish: float = 1.2
    pcr_bearish: float = 0.8
    trap_wick_ratio: float = 0.65
    trap_volume_drop: float = 0.7
    fake_breakout_candles: int = 3
    vix_high: float = 18.0
    vix_low: float = 12.0
    vix_spike: float = 10.0
    opening_range_minutes: int = 15
    power_hour_start: str = "14:00"
    lunch_start: str = "12:00"
    lunch_end: str = "13:30"
    avoid_first_minutes: int = 5
    avoid_last_minutes: int = 10
    expiry_day_caution: bool = True
    mtf_timeframes: list = field(default_factory=lambda: [1, 5, 15])
    mtf_alignment_threshold: int = 2
    engulfing_min_ratio: float = 1.5
    pin_bar_wick_ratio: float = 2.5
    inside_bar_lookback: int = 3
    double_top_tolerance: float = 0.1
    bb_period: int = 20
    bb_std: float = 2.0
    squeeze_threshold: float = 0.5
    expansion_multiplier: float = 1.5
    atr_fast: int = 7
    atr_slow: int = 21
    correlation_window: int = 50
    correlation_strong: float = 0.7
    correlation_weak: float = 0.3
    banknifty_weight: float = 0.6
    expiry_day: str = "Thursday"
    gamma_exposure_threshold: float = 50
    theta_decay_acceleration_dte: int = 3
    pin_risk_range: float = 0.5
    bid_ask_imbalance_threshold: float = 1.5
    large_order_threshold: float = 500000
    absorption_candles: int = 5
    round_number_interval: int = 100
    pivot_type: str = "standard"
    level_proximity_points: float = 10.0
    delta_neutral_range: tuple = field(default_factory=lambda: (-0.1, 0.1))
    gamma_wall_threshold: float = 200000
    iv_skew_threshold: float = 5.0
    fii_bullish_threshold: float = 500
    fii_bearish_threshold: float = -500
    dii_confirmation: bool = True
    gap_significant_points: float = 30.0
    gap_fill_probability_threshold: float = 0.7
    consolidation_min_candles: int = 10
    consolidation_range_atr_ratio: float = 0.5
    breakout_volume_multiplier: float = 1.8
    breakout_confirmation_candles: int = 2
    min_trades_for_learning: int = 10
    learning_lookback_days: int = 30
    win_rate_good: float = 60.0
    win_rate_bad: float = 40.0
    pattern_min_occurrences: int = 3
    confidence_calibration_enabled: bool = True
    optimal_confidence_min: float = 65.0
    optimal_confidence_max: float = 90.0
    streak_alert_threshold: int = 3
    learning_weight_adaptation_rate: float = 0.1
    condition_correlation_min_samples: int = 5
    expiry_gamma_zone_points: float = 50.0
    expiry_pin_proximity: float = 25.0
    expiry_last_hour_start: str = "14:30"
    expiry_premium_crush_threshold: float = 30.0
    expiry_straddle_decay_rate_high: float = 5.0
    expiry_avoid_first_minutes: int = 15
    expiry_avoid_last_minutes: int = 5
    expiry_oi_concentration_threshold: float = 0.3
    expiry_gamma_scalp_window: int = 30
    expiry_weekly_vs_monthly_vol_diff: float = 1.3
    expiry_max_pain_gravity_radius: float = 75.0
    expiry_pin_level_oi_ratio: float = 0.25
    decay_measurement_interval: int = 5
    decay_acceleration_dte: int = 3
    decay_critical_dte: int = 1
    decay_iv_crush_threshold: float = 15.0
    decay_theta_burn_rate_high: float = 3.0
    decay_optimal_hold_minutes_trend: int = 45
    decay_optimal_hold_minutes_scalp: int = 15
    decay_weekend_premium_factor: float = 1.2
    decay_overnight_gap_risk: float = 2.0
    decay_itm_vs_otm_break_even: float = 0.6
    decay_time_value_min_pct: float = 10.0
    decay_intrinsic_safety_margin: float = 20.0
    min_confidence: float = 30.0
    min_confluence_agents: int = 3  # was 5 — dynamic routing selects 2-4 agents per cycle; requiring 5 is impossible
    signal_quality_min: str = "B"
    agent_weights: Dict[str, float] = field(default_factory=lambda: {
        "market": 0.10,
        "momentum": 0.10,
        "oi": 0.10,
        "multi_tf": 0.08,
        "price_action": 0.07,
        "trend_strength": 0.06,
        "divergence": 0.05,
        "level_zone": 0.05,
        "institutional": 0.04,
        "correlation": 0.03,
        "greeks": 0.03,
        "mean_reversion": 0.03,
        "learning": 0.06,
        "expiry_day": 0.04,
        "decay": 0.04,
        "trap": 0.04,
        "sentiment": 0.02,
        "session": 0.02,
        "expiry": 0.01,
        "volatility": 0.01,
    })
    blocker_agents: Dict[str, float] = field(default_factory=lambda: {
        "risk": 30.0,
        "trap": 70.0,
        "session": 20.0,
        "sentiment": 20.0,
        "expiry_day": 15.0,
        "decay": 20.0,
        "learning": 25.0,
    })
    base_stop_loss_pct: float = 10.0
    trailing_sl_activation_pct: float = 15.0
    trailing_sl_distance_pct: float = 5.0
    structure_bos_confirmation: int = 2
    structure_swing_order: int = 5
    structure_ob_lookback: int = 20
    structure_fvg_min_gap_pct: float = 0.1
    regime_adx_trending: float = 25.0
    regime_adx_strong_trend: float = 40.0
    regime_adx_ranging: float = 20.0
    regime_lookback: int = 50
    learning_rolling_window: int = 1000
    learning_overfit_threshold: float = 0.85
    learning_staleness_days: int = 14
    learning_weight_decay: float = 0.98


@dataclass
class AlertConfig:
    console_enabled: bool = True
    telegram_enabled: bool = False
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    sound_enabled: bool = True
    cooldown_seconds: int = 120
    
    # v4.5 Interactive Bot Config
    trading_mode: str = "AUTO"  # AUTO | SEMI_AUTO | MANUAL
    telegram_signal_expiry_seconds: int = 30
    max_slippage_pct_on_confirm: float = 0.2

    # v4.7 Spread Explosion Filter
    # Reject order if bid-ask spread exceeds this absolute value (₹)
    # NIFTY ATM options: normal spread ~₹1-3; blowout = ₹8+
    max_spread_abs: float = 8.0             # ₹ hard limit
    max_spread_pct: float = 6.0             # % of ask — alternative gate

    # v4.7 Broker Health Monitor
    # Halt new trades if broker API latency exceeds this sustained threshold
    broker_latency_halt_ms: float = 3000.0  # 3s single-call timeout = degraded
    broker_latency_warn_ms: float = 1500.0  # 1.5s warn threshold


@dataclass
class DashboardConfig:
    enabled: bool = True
    host: str = "0.0.0.0"
    port: int = 5000
    telemetry_emit_interval_seconds: float = 2.0



@dataclass
class InstrumentConfig:
    """
    🛡️ Risk #5 Fix: Centralised security ID registry.
    Previously hardcoded in data_manager._discover_nifty_id().
    Update these if Dhan changes their instrument master.
    Override via environment: NIFTY_SECURITY_ID, BANKNIFTY_SECURITY_ID.
    """
    # Dhan IDX_I security IDs (as of 2026)
    security_id_map: Dict[str, str] = field(
        default_factory=lambda: {
            "NIFTY": os.getenv("NIFTY_SECURITY_ID", "13"),
            "BANKNIFTY": os.getenv("BANKNIFTY_SECURITY_ID", "25"),
        }
    )

    def get_security_id(self, instrument: str) -> str:
        """Returns the Dhan security ID for the given instrument name."""
        sid = self.security_id_map.get(instrument.upper())
        if sid is None:
            raise RuntimeError(
                f"INSTRUMENT '{instrument}' NOT FOUND IN MASTER LIST. "
                f"Add it to InstrumentConfig.security_id_map or set env var {instrument.upper()}_SECURITY_ID."
            )
        return sid


@dataclass
class BrokerageConfig:
    """Pro-grade brokerage and slippage modeling"""
    brokerage_per_order: float = 20.0
    stt_sell_pct: float = 0.0625            # STT on sell side
    transaction_charges_pct: float = 0.05   # Exchange txn charges
    gst_pct: float = 18.0                  # GST on brokerage/txn
    sebi_charges_per_crore: float = 10.0
    stamp_duty_buy_pct: float = 0.003

    # Slippage Model Settings
    slippage_model: str = "dynamic"         # fixed | dynamic | volume
    fixed_slippage_points: float = 0.5
    dynamic_slippage_base: float = 0.3
    dynamic_slippage_vol_factor: float = 0.05
    impact_cost_per_lot: float = 0.1
    max_slippage_points: float = 2.0

    # Spread Settings
    typical_spread_points: float = 0.2
    wide_spread_threshold_vix: float = 18.0
    wide_spread_multiplier: float = 2.5


@dataclass
class LegacyPositionConfig:
    max_portfolio_heat: float = 5.0
    max_open_positions: int = 3
    scaling_enabled: bool = True
    partial_profit_pct: float = 50.0
    circuit_breaker_drawdown: float = 10.0

    # ══════════════════════════════════════════
# V3 ENGINE PIPELINE (HIERARCHICAL ROUTING)
# ══════════════════════════════════════════

@dataclass
class EnginePipelineConfig:
    """
    Defines the execution order of agent phases.
    If a phase fails (e.g., choppy regime, no structure),
    the engine halts and saves compute power.

    ── active_agents ──────────────────────────────────────────
    Graphify analysis (2026-04-09) identified 9 agents that
    directly influence trade decisions and 14 that do not.

    Only agents in active_agents are instantiated + run.
    This cuts compute by ~40% and removes signal noise.

    To re-enable an unused agent add its name here, then wire
    it into the appropriate phase list below.
    ───────────────────────────────────────────────────────────
    """

    # ── 9 agents confirmed to influence decisions (Graphify) ──
    # ── Core Directional Stack (Phase 1) ──
    active_agents: List[str] = field(
        default_factory=lambda: [
            # Phase 1 gatekeepers
            "time_session",
            "regime",
            # Phase 2 core
            "structure",
            "price_action",
            "momentum",
            # Phase 4 risk & meta
            "risk",
        ]
        # Temporarily Disabled (Phase 1 Edge Validation):
        # "oi", "trap", "order_flow", "level", "institutional", 
        # "multi_timeframe", "volatility", "decay", "expiry_day", 
        # "learning", "market", "sentiment"
    )

    # Phase 1: The Gatekeepers (Fast & Cheap)
    # Goal: Is the market even tradable right now?
    phase_1_gatekeepers: List[str] = field(
        default_factory=lambda: [
            "time_session",
            "regime"
        ]
    )

    # Phase 2: Core Direction (The Strategists)
    # Goal: Do we have a baseline setup/trend?
    phase_2_core: List[str] = field(
        default_factory=lambda: [
            "structure",
            "price_action",
            "momentum"
        ]
    )

    # Phase 3: Deep Confirmation (The Heavy Lifters)
    # Temporarily disabled for Phase 1 edge validation
    phase_3_confirmation: List[str] = field(
        default_factory=lambda: []
    )

    # Phase 4: Risk & Meta-Analysis (The Final Check)
    # Goal: Does the risk/reward make sense?
    phase_4_risk: List[str] = field(
        default_factory=lambda: [
            "risk",
        ]
    )


# ══════════════════════════════════════════
# MASTER SETTINGS CLASS
# ══════════════════════════════════════════

class Settings:
    """Master settings — PRO MODE v3.2"""

    def __init__(self):
        self.mode = os.getenv("SYSTEM_MODE", "SIMULATION")
        self.log_level = os.getenv("LOG_LEVEL", "INFO")
        self.data_source = os.getenv("DATA_SOURCE", "simulated")

        # ── v3.2 NEW CONFIGS ──
        self.system_mode = SystemMode(
            mode=self.mode,
        )
        
        # ── V3 PIPELINE ──
        self.pipeline = EnginePipelineConfig()

        # Capital based on mode
        if self.mode == "SIMULATION":
            capital = self.system_mode.simulation_capital
        elif self.mode == "SMALL_CAPITAL":
            capital = self.system_mode.small_capital
        else:
            capital = self.system_mode.scaled_capital

        # Timeframes
        self.entry_timeframe = os.getenv("ENTRY_TIMEFRAME", "1min")
        self.trend_timeframe = os.getenv("TREND_TIMEFRAME", "5min")

        # ── ⚓ PRODUCTION PROTOCOL SYNC (v4.6.1) ──
        self.symbol = os.getenv("SYMBOL", "NIFTY")
        self.friday_cutoff = os.getenv("FRIDAY_CUTOFF_TIME", "15:10")
        self.daily_cutoff = os.getenv("DAILY_CUTOFF_TIME", "15:20")
        
        # ── Risk Override ──
        max_daily_loss = float(os.getenv("MAX_DAILY_LOSS", -2000))
        max_trade_loss = float(os.getenv("MAX_LOSS_PER_TRADE", 500))
        max_pos_size = float(os.getenv("POSITION_SIZE_INR", 50000))

        self.position = PositionConfig(
            total_capital=capital,
            max_daily_loss=max_daily_loss,
            max_risk_per_trade=max_trade_loss,
            max_capital_per_trade=(max_pos_size / capital) if capital > 0 else 0.25,
            max_open_positions=int(os.getenv("MAX_OPEN_POSITIONS", 1)),
        )
        self.trade_filter = TradeFilterConfig()
        self.exit = ExitConfig()
        self.session_strategy = SessionStrategyConfig()
        
        # Apply Cutoff overrides to SessionStrategy
        if self.friday_cutoff in self.session_strategy.sessions["power_hour"]["end"]:
            # Logic handled in session_strategy or risk_manager
            pass

        # ── LEGACY CONFIGS (backward compat) ──
        self.trading = TradingConfig(
            instrument=self.symbol,
            capital=capital,
            max_risk_per_trade=max_trade_loss,
            max_daily_trades=int(os.getenv("MAX_DAILY_TRADES", 3)),
            max_daily_loss=max_daily_loss,
            auto_shutdown_after_market=os.getenv("AUTO_SHUTDOWN", "false").lower() == "true",
        )
        self.intervals = AgentIntervals(
            market=int(os.getenv("MARKET_AGENT_INTERVAL", 5)),
        )
        self.thresholds = ThresholdConfig()
        self.alerts = AlertConfig(
            console_enabled=os.getenv("ENABLE_CONSOLE_ALERTS", "true").lower() == "true",
            telegram_enabled=os.getenv("ENABLE_TELEGRAM_ALERTS", "false").lower() == "true",
            telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
            telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID", ""),
            trading_mode=os.getenv("TRADING_MODE", "AUTO").upper(),
            telegram_signal_expiry_seconds=int(os.getenv("TELEGRAM_SIGNAL_EXPIRY_SECONDS", 30)),
            max_slippage_pct_on_confirm=float(os.getenv("MAX_SLIPPAGE_PCT_ON_CONFIRM", 0.2)),
        )
        self.dashboard = DashboardConfig(
            enabled=os.getenv("DASHBOARD_ENABLED", "true").lower() == "true",
            port=int(os.getenv("DASHBOARD_PORT", 5000)),
            telemetry_emit_interval_seconds=float(os.getenv("TELEMETRY_EMIT_INTERVAL_SECONDS", 2.0)),
        )
        self.brokerage = BrokerageConfig()
        self.legacy_position = LegacyPositionConfig()
        self.instruments = InstrumentConfig()  # 🛡️ Risk #5 Fix: centralised security ID registry

    def get_capital(self) -> float:
        if self.system_mode.mode == "SIMULATION":
            return self.system_mode.simulation_capital
        elif self.system_mode.mode == "SMALL_CAPITAL":
            return self.system_mode.small_capital
        return self.system_mode.scaled_capital

    def __repr__(self):
        return (
            f"Settings(mode={self.mode}, "
            f"capital=₹{self.get_capital():,.0f}, "
            f"max_trades={self.trade_filter.max_trades_per_day}, "
            f"min_confidence={self.trade_filter.min_signal_confidence}%, "
            f"min_grade={self.trade_filter.min_grade_to_trade})"
        )
