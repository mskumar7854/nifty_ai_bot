"""
============================================
CORE STRATEGY MODULE  (v2 — Safety Hardened)
============================================
Trend Detection + Momentum Confirmation +
Breakout Entry Logic + 3 Safety Filters

Signal flow  (7 gates):
  Gate 1 : No-trade zone (time)
  Gate 2 : Sideways market (EMA)
  Gate 3 : Momentum (RSI)
  Gate 4 : Breakout / Breakdown
  Gate 5 : 🛡️  Large-wick rejection
  Gate 6 : 🛡️  Distance-from-breakout cap
  Gate 7 : 🛡️  Trend–Breakout direction match

ALL gates must pass → signal emitted.
One fail → NO TRADE (with reason logged).
============================================
"""

import pandas as pd
from datetime import datetime, time
from typing import Optional, Tuple

from .config import Config
from indicators import (
    IndicatorEngine, calculate_ema, calculate_rsi,
    get_candle_strength, calculate_volume_profile,
)


# ══════════════════════════════════════════
# TREND DETECTION
# ══════════════════════════════════════════

class TrendDetector:
    """
    Detect market trend using EMA 20 / EMA 50.

    BULLISH  : close > EMA20 > EMA50
    BEARISH  : close < EMA20 < EMA50
    SIDEWAYS : everything else
    """

    @staticmethod
    def detect(df: pd.DataFrame) -> str:
        if len(df) < Config.EMA_LONG:
            return Config.SIDEWAYS

        df = df.copy()
        df['ema20'] = calculate_ema(df, Config.EMA_SHORT)
        df['ema50'] = calculate_ema(df, Config.EMA_LONG)

        last = df.iloc[-1]
        close, ema20, ema50 = last['close'], last['ema20'], last['ema50']

        if close > ema20 > ema50:
            return Config.BULLISH
        if close < ema20 < ema50:
            return Config.BEARISH
        return Config.SIDEWAYS

    @staticmethod
    def get_trend_strength(df: pd.DataFrame) -> dict:
        """Return trend + distance metrics for logging/UI."""
        df = df.copy()
        df['ema20'] = calculate_ema(df, Config.EMA_SHORT)
        df['ema50'] = calculate_ema(df, Config.EMA_LONG)
        last = df.iloc[-1]

        price_vs_ema20 = (last['close'] - last['ema20']) / last['ema20'] * 100
        ema20_vs_ema50 = (last['ema20'] - last['ema50']) / last['ema50'] * 100

        return {
            'trend': TrendDetector.detect(df),
            'price_vs_ema20_pct': round(price_vs_ema20, 3),
            'ema20_vs_ema50_pct': round(ema20_vs_ema50, 3),
            'ema20': round(last['ema20'], 2),
            'ema50': round(last['ema50'], 2),
            'close': round(last['close'], 2),
        }


# ══════════════════════════════════════════
# MOMENTUM CONFIRMATION
# ══════════════════════════════════════════

class MomentumChecker:
    """
    Confirm momentum via RSI.

    RSI > 60 → BULLISH
    RSI < 40 → BEARISH
    40-60    → WEAK (no trade)
    """

    @staticmethod
    def check(df: pd.DataFrame) -> str:
        if len(df) < Config.RSI_PERIOD:
            return Config.MOMENTUM_WEAK

        df = df.copy()
        df['rsi'] = calculate_rsi(df, Config.RSI_PERIOD)
        rsi = df.iloc[-1]['rsi']

        if rsi > Config.RSI_BULLISH_THRESHOLD:
            return Config.MOMENTUM_BULLISH
        if rsi < Config.RSI_BEARISH_THRESHOLD:
            return Config.MOMENTUM_BEARISH
        return Config.MOMENTUM_WEAK

    @staticmethod
    def get_rsi_details(df: pd.DataFrame) -> dict:
        df = df.copy()
        df['rsi'] = calculate_rsi(df, Config.RSI_PERIOD)
        rsi = df.iloc[-1]['rsi']

        return {
            'rsi': round(rsi, 2),
            'momentum': MomentumChecker.check(df),
            'rsi_position': round((rsi - 40) / 20 * 100, 1),
            'is_overbought': rsi > 70,
            'is_oversold': rsi < 30,
        }


# ══════════════════════════════════════════
# BREAKOUT DETECTOR
# ══════════════════════════════════════════

class BreakoutDetector:
    """
    Compare last closed candle vs previous candle range.

    BREAKOUT  : close > prev_high   (long trigger)
    BREAKDOWN : close < prev_low    (short trigger)
    """

    def __init__(
        self,
        min_body_pct: float = Config.MIN_CANDLE_BODY_PERCENT,
        require_volume: bool = True,
    ):
        self.min_body_pct = min_body_pct
        self.require_volume = require_volume

    def detect(
        self,
        df: pd.DataFrame,
        volume_df: Optional[pd.DataFrame] = None,
    ) -> Tuple[str, dict]:
        if len(df) < 2:
            return Config.NO_SIGNAL, {}

        prev = df.iloc[-2]
        last = df.iloc[-1]
        candle = get_candle_strength(df)

        # Volume gate
        volume_ok = True
        if self.require_volume:
            vol = calculate_volume_profile(volume_df if volume_df is not None else df)
            volume_ok = vol['is_spike']

        details = {
            'prev_high': round(prev['high'], 2),
            'prev_low': round(prev['low'], 2),
            'current_close': round(last['close'], 2),
            'candle_strong': candle['is_strong'],
            'body_percent': round(candle['body_percent'], 1),
            'volume_ok': volume_ok,
            'breakout_distance_pct': 0.0,
            'breakdown_distance_pct': 0.0,
        }

        if last['close'] > prev['high']:
            details['breakout_distance_pct'] = round(
                (last['close'] - prev['high']) / prev['high'] * 100, 3
            )
            return Config.BREAKOUT, details

        if last['close'] < prev['low']:
            details['breakdown_distance_pct'] = round(
                (prev['low'] - last['close']) / prev['low'] * 100, 3
            )
            return Config.BREAKDOWN, details

        return Config.NO_SIGNAL, details


# ══════════════════════════════════════════
# NO-TRADE ZONE CHECKER
# ══════════════════════════════════════════

class NoTradeZoneChecker:
    """Block entries during opening chaos, lunch, and post-close."""

    @staticmethod
    def is_no_trade_time(dt: Optional[datetime] = None) -> Tuple[bool, str]:
        if dt is None:
            dt = datetime.now()

        ct = dt.time()

        market_open  = time(Config.MARKET_OPEN_HOUR, Config.MARKET_OPEN_MINUTE)
        open_end     = time(Config.MARKET_OPEN_HOUR, Config.MARKET_OPEN_END_MINUTE)
        lunch_start  = time(Config.LUNCH_START_HOUR, 0)
        lunch_end    = time(Config.LUNCH_END_HOUR, Config.LUNCH_END_MINUTE)
        market_close = time(15, 30)

        if ct < market_open:
            return True, "Market not open yet"
        if market_open <= ct <= open_end:
            return True, "Opening 15 min — avoid noise"
        if lunch_start <= ct <= lunch_end:
            return True, "Lunch lull — no entries"
        if ct > market_close:
            return True, "Market closed"

        return False, ""

# ══════════════════════════════════════════
# 🛡️  SAFETY FILTER  (3 micro-gates)
# ══════════════════════════════════════════

class SafetyFilter:
    """
    Three lightweight guards that sit AFTER breakout
    detection and kill the most common loss patterns:

    Gate A — Large-Wick Rejection
        A candle whose wick is much longer than its body
        signals indecision / rejection. We don't enter.
        Threshold: wick-to-body ratio > MAX_WICK_BODY_RATIO

    Gate B — Stale Breakout Distance Cap
        If price has already run far beyond the breakout
        level we are chasing price. We don't enter.
        Threshold: close-to-breakout-level > MAX_BREAKOUT_CHASE_PCT

    Gate C — Trend ↔ Breakout Direction Match
        Bullish trend must confirm with bullish breakout,
        bearish trend must confirm with bearish breakdown.
        Mismatches are filtered as noise.
    """

    # ── Tuneable thresholds ────────────────────────────
    MAX_WICK_BODY_RATIO: float = 2.0          # wick ≤ 2× body
    MAX_BREAKOUT_CHASE_PCT: float = 0.30      # max 0.30% away from level

    # ── Gate A ─────────────────────────────────────────
    @classmethod
    def check_wick(cls, df: pd.DataFrame) -> Tuple[bool, str]:
        """
        Reject if the breakout candle has a large upper/lower
        wick relative to its body (rejection signal).
        """
        last = df.iloc[-1]
        body = abs(last['close'] - last['open'])

        if body == 0:
            return False, "Doji candle — body=0, skip"

        upper_wick = last['high'] - max(last['close'], last['open'])
        lower_wick = min(last['close'], last['open']) - last['low']
        dominant_wick = max(upper_wick, lower_wick)

        ratio = dominant_wick / body
        if ratio > cls.MAX_WICK_BODY_RATIO:
            return False, (
                f"Large wick rejection: wick/body={ratio:.1f}× "
                f"(max {cls.MAX_WICK_BODY_RATIO}×)"
            )
        return True, f"Wick OK ({ratio:.1f}×)"

    # ── Gate B ─────────────────────────────────────────
    @classmethod
    def check_breakout_distance(
        cls,
        df: pd.DataFrame,
        breakout_signal: str,
        breakout_details: dict,
    ) -> Tuple[bool, str]:
        """
        Reject if price has moved too far past the breakout
        level — we would be chasing a stale move.
        """
        last_close = df.iloc[-1]['close']

        if breakout_signal == Config.BREAKOUT:
            level = breakout_details.get('prev_high', last_close)
            if level <= 0:
                return True, "No level"
            distance_pct = (last_close - level) / level * 100

        elif breakout_signal == Config.BREAKDOWN:
            level = breakout_details.get('prev_low', last_close)
            if level <= 0:
                return True, "No level"
            distance_pct = (level - last_close) / level * 100

        else:
            return True, "No breakout — skip distance check"

        if distance_pct > cls.MAX_BREAKOUT_CHASE_PCT:
            return False, (
                f"Chasing breakout: {distance_pct:.3f}% past level "
                f"(max {cls.MAX_BREAKOUT_CHASE_PCT}%)"
            )
        return True, f"Distance OK ({distance_pct:.3f}%)"

    # ── Gate C ─────────────────────────────────────────
    @classmethod
    def check_direction_match(
        cls,
        trend: str,
        breakout_signal: str,
    ) -> Tuple[bool, str]:
        """
        Bullish trend → only accept BREAKOUT.
        Bearish trend → only accept BREAKDOWN.
        """
        ok = (
            (trend == Config.BULLISH and breakout_signal == Config.BREAKOUT)
            or (trend == Config.BEARISH and breakout_signal == Config.BREAKDOWN)
        )
        if not ok:
            return False, (
                f"Direction mismatch: trend={trend}, "
                f"breakout={breakout_signal}"
            )
        return True, f"Direction aligned ({trend} ↔ {breakout_signal})"

    # ── Run all three ──────────────────────────────────
    @classmethod
    def run_all(
        cls,
        df: pd.DataFrame,
        trend: str,
        breakout_signal: str,
        breakout_details: dict,
    ) -> Tuple[bool, str, dict]:
        """
        Returns (all_pass, first_fail_reason, details_dict).
        """
        details = {}

        wick_ok, wick_msg = cls.check_wick(df)
        details['wick_check'] = wick_msg
        if not wick_ok:
            return False, wick_msg, details

        dist_ok, dist_msg = cls.check_breakout_distance(
            df, breakout_signal, breakout_details
        )
        details['distance_check'] = dist_msg
        if not dist_ok:
            return False, dist_msg, details

        dir_ok, dir_msg = cls.check_direction_match(trend, breakout_signal)
        details['direction_check'] = dir_msg
        if not dir_ok:
            return False, dir_msg, details

        return True, "All safety filters passed", details


# ══════════════════════════════════════════
# MASTER STRATEGY
# ══════════════════════════════════════════

class Strategy:
    """
    Orchestrates: Trend → Momentum → Breakout.

    ALL three must align for a signal to fire.
    One weak link = NO TRADE.
    """

    def __init__(self):
        self.trend_detector     = TrendDetector()
        self.momentum_checker   = MomentumChecker()
        self.breakout_detector  = BreakoutDetector()
        self.no_trade_checker   = NoTradeZoneChecker()
        self.safety_filter      = SafetyFilter()
        self.indicator_engine   = IndicatorEngine()

    def analyze(
        self,
        trend_df: pd.DataFrame,
        momentum_df: pd.DataFrame,
        entry_df: pd.DataFrame,
        volume_df: Optional[pd.DataFrame] = None,
        dt: Optional[datetime] = None,
    ) -> dict:
        """
        Run complete strategy analysis.

        Returns a fully-populated analysis dict:
          signal        : BUY_CE | BUY_PE | NO_TRADE
          can_trade     : bool
          no_trade_reason: str | None
          trend/momentum/breakout + details
        """
        now = dt or datetime.now()

        result = {
            'timestamp': now,
            'can_trade': True,
            'no_trade_reason': None,
            'signal': Config.NO_TRADE,
            'trade_direction': None,
            'trend': None,
            'momentum': None,
            'breakout': None,
            'details': {},
        }

        # ── GATE 1: No-trade zone ─────────────────────────
        blocked, reason = self.no_trade_checker.is_no_trade_time(now)
        if blocked:
            result.update(can_trade=False, no_trade_reason=reason)
            return result

        # Flag expiry day as warning (not a hard block here)
        # Expiry is now dynamic and handled at the gate level via MarketSnapshot.

        # ── GATE 2: Trend ─────────────────────────────────
        trend = self.trend_detector.detect(trend_df)
        result['trend'] = trend
        result['details']['trend_strength'] = self.trend_detector.get_trend_strength(trend_df)

        if trend == Config.SIDEWAYS:
            result.update(can_trade=False, no_trade_reason="Sideways market — EMAs not aligned")
            return result

        # ── GATE 3: Momentum ──────────────────────────────
        momentum = self.momentum_checker.check(momentum_df)
        result['momentum'] = momentum
        result['details']['rsi_details'] = self.momentum_checker.get_rsi_details(momentum_df)

        if momentum == Config.MOMENTUM_WEAK:
            result.update(can_trade=False, no_trade_reason="RSI in neutral zone (40–60)")
            return result

        # ── GATE 4: Breakout / Breakdown ──────────────────
        breakout, breakout_details = self.breakout_detector.detect(entry_df, volume_df)
        result['breakout'] = breakout
        result['details']['breakout_details'] = breakout_details

        if breakout == Config.NO_SIGNAL:
            result.update(
                can_trade=False,
                no_trade_reason="No breakout/breakdown — waiting for trigger",
            )
            return result

        # ── GATES 5–7: Safety Filters ─────────────────────
        #   Gate 5 — Large wick rejection
        #   Gate 6 — Don't chase stale breakouts
        #   Gate 7 — Trend/breakout direction must match
        safe, safety_reason, safety_details = SafetyFilter.run_all(
            df=entry_df,
            trend=trend,
            breakout_signal=breakout,
            breakout_details=breakout_details,
        )
        result['details']['safety_filters'] = safety_details

        if not safe:
            result.update(can_trade=False, no_trade_reason=f"🛡️ Safety: {safety_reason}")
            return result

        # ── SIGNAL GENERATION ─────────────────────────────
        if (trend == Config.BULLISH
                and momentum == Config.MOMENTUM_BULLISH
                and breakout == Config.BREAKOUT):
            result.update(signal="BUY_CE", trade_direction="CE", can_trade=True)

        elif (trend == Config.BEARISH
              and momentum == Config.MOMENTUM_BEARISH
              and breakout == Config.BREAKDOWN):
            result.update(signal="BUY_PE", trade_direction="PE", can_trade=True)

        else:
            result.update(
                can_trade=False,
                no_trade_reason=(
                    f"Mismatch: Trend={trend}, "
                    f"Momentum={momentum}, "
                    f"Breakout={breakout}"
                ),
            )

        return result

    # ── Convenience ───────────────────────────────────────

    def get_signal_summary(self, analysis: dict) -> str:
        """Human-readable one-liner."""
        if not analysis['can_trade']:
            return f"⛔ NO TRADE — {analysis.get('no_trade_reason', 'Unknown')}"

        sig = analysis['signal']
        if sig in Config.ALLOWED_SIGNALS:
            icon = "🟢 BUY CE 📈" if sig == "BUY_CE" else "🔴 BUY PE 📉"
            rsi = analysis['details'].get('rsi_details', {}).get('rsi', '')
            return (
                f"{icon} | "
                f"Trend: {analysis['trend']} | "
                f"RSI: {rsi:.1f} | "
                f"Breakout: {analysis['breakout']}"
            )

        return f"⛔ NO TRADE — {analysis.get('no_trade_reason', '')}"
