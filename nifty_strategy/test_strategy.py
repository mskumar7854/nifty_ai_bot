"""
============================================
TEST SUITE — run without Dhan API
============================================
Tests all modules in isolation using synthetic data.

Usage (from nifty_strategy/ or project root):
    python nifty_strategy/test_strategy.py
============================================
"""

import sys
import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Allow import from both nifty_strategy/ and project root
sys.path.insert(0, os.path.dirname(__file__))

from config import Config
from indicators import (
    calculate_ema, calculate_rsi, calculate_atr,
    calculate_volume_profile, get_candle_strength,
    IndicatorEngine,
)
from strategy import Strategy, TrendDetector, MomentumChecker, BreakoutDetector
from risk_manager import RiskManager, TradeLogger, Trade
from options_selector import (
    OptionStrikeSelector, StrikeLadderBuilder,
    OptionContractBuilder,
)
from data_provider import DhanDataProvider


SEP = "=" * 55


def gen_candles(
    periods: int = 120,
    base: float = 22_800,
    seed: int = 42,
    bullish: bool = True,
) -> pd.DataFrame:
    """Synthetic OHLCV candles with optional trend direction."""
    np.random.seed(seed)
    drift = 0.6 if bullish else -0.6
    prices = base + np.cumsum(np.random.randn(periods) * 18 + drift)

    opens  = prices + np.random.randn(periods) * 8
    highs  = np.maximum(opens, prices) + np.abs(np.random.randn(periods) * 14)
    lows   = np.minimum(opens, prices) - np.abs(np.random.randn(periods) * 14)
    closes = prices + np.random.randn(periods) * 8

    dates = [datetime.now() - timedelta(minutes=5 * (periods - i)) for i in range(periods)]

    return pd.DataFrame({
        'open':   np.round(opens,  2),
        'high':   np.round(highs,  2),
        'low':    np.round(lows,   2),
        'close':  np.round(closes, 2),
        'volume': np.random.randint(80_000, 450_000, periods).astype(float),
    }, index=pd.DatetimeIndex(dates, name='timestamp'))


# ──────────────────────────────────────────
# TEST 1: Indicators
# ──────────────────────────────────────────
def test_indicators():
    print(f"\n{SEP}")
    print("  TEST 1 — INDICATORS")
    print(SEP)

    df = gen_candles(120)
    engine = IndicatorEngine()
    enriched = engine.calculate_all(df)

    vals = engine.get_latest_values(enriched)

    print(f"  Close    : ₹{vals['close']:.2f}")
    print(f"  EMA20    : ₹{vals['ema20']:.2f}")
    print(f"  EMA50    : ₹{vals['ema50']:.2f}")
    print(f"  RSI      : {vals['rsi']:.1f}")
    print(f"  ATR      : {vals['atr']:.2f}")
    print(f"  Vol spike: {vals['volume_spike']}")
    print(f"  Candle ✓ : {vals['candle_strong']}")

    assert 0 < vals['rsi'] < 100, "RSI out of range"
    assert vals['ema20'] > 0,     "EMA20 is zero"
    print("  ✅ Indicators OK")


# ──────────────────────────────────────────
# TEST 2: Trend / Momentum / Breakout
# ──────────────────────────────────────────
def test_strategy_components():
    print(f"\n{SEP}")
    print("  TEST 2 — STRATEGY COMPONENTS")
    print(SEP)

    bull_df = gen_candles(120, bullish=True, seed=10)
    bear_df = gen_candles(120, bullish=False, seed=20)

    trend = TrendDetector.detect(bull_df)
    print(f"  Trend (bull data): {trend}")

    mom = MomentumChecker.check(bull_df)
    rsi_d = MomentumChecker.get_rsi_details(bull_df)
    print(f"  Momentum          : {mom}  (RSI {rsi_d['rsi']:.1f})")

    detector = BreakoutDetector(require_volume=False)
    signal, details = detector.detect(bull_df)
    print(f"  Breakout signal   : {signal}")
    print(f"  Breakout details  : {details}")

    print("  ✅ Strategy components OK")


# ──────────────────────────────────────────
# TEST 3: Full strategy analysis
# ──────────────────────────────────────────
def test_full_strategy():
    print(f"\n{SEP}")
    print("  TEST 3 — FULL STRATEGY ANALYSIS")
    print(SEP)

    df = gen_candles(120, bullish=True, seed=7)
    strategy = Strategy()

    # Force lunch-hour time to test no-trade gate
    lunch_time = datetime.now().replace(hour=12, minute=30)
    result = strategy.analyze(df, df, df, dt=lunch_time)
    assert not result['can_trade'], "Should block during lunch"
    print(f"  Lunch gate OK: {result['no_trade_reason']}")

    # Normal trading hour
    trade_time = datetime.now().replace(hour=10, minute=30)
    result = strategy.analyze(df, df, df, dt=trade_time)
    print(f"  Signal: {result['signal']}  | Can trade: {result['can_trade']}")
    print(f"  Trend : {result['trend']}   | Momentum: {result['momentum']}")
    print(f"  {strategy.get_signal_summary(result)}")

    print("  ✅ Full strategy OK")


# ──────────────────────────────────────────
# TEST 4: Risk Manager
# ──────────────────────────────────────────
def test_risk_manager():
    print(f"\n{SEP}")
    print("  TEST 4 — RISK MANAGER")
    print(SEP)

    rm = RiskManager()

    entry  = 150.0
    sl     = rm.calculate_stop_loss(entry, "CE")
    target = rm.calculate_target(entry, sl)
    pos    = rm.calculate_position_size(entry, sl)

    print(f"  Entry     : ₹{entry:.2f}")
    print(f"  Stop Loss : ₹{sl:.2f}  ({(entry-sl)/entry*100:.1f}%)")
    print(f"  Target    : ₹{target:.2f}")
    print(f"  Qty       : {pos['quantity']} ({pos['lots']} lots)")
    print(f"  Risk ₹    : {pos['risk_amount']:.2f}")
    print(f"  Risk %    : {pos['risk_percent']:.2f}%")

    can, msg = rm.can_take_trade("BUY_CE")
    print(f"\n  Can take trade: {can} — {msg}")

    can_bad, msg_bad = rm.can_take_trade("INVALID_SIGNAL")
    assert not can_bad, "Should reject invalid signal"
    print(f"  Invalid signal blocked: {msg_bad}")

    # Simulate daily loss limit
    for i in range(3):
        t = Trade(
            symbol=f"FAKE{i}CE", entry_price=100, quantity=50,
            option_type="CE", strike=22800, expiry="03APR",
            timestamp=datetime.now(), stop_loss=80, target=140,
            current_price=75,
        )
        rm.record_trade(t)
        rm.close_trade(t, exit_price=75, reason="SL hit")

    stop, reason = rm.should_stop_trading()
    print(f"\n  Should stop: {stop} — {reason}")

    summary = rm.get_daily_summary()
    print(f"  Daily P&L : ₹{summary['total_pnl']:.2f}")
    print(f"  Win Rate  : {summary['win_rate']:.1f}%")
    print("  ✅ Risk Manager OK")


# ──────────────────────────────────────────
# TEST 5: Option Selector
# ──────────────────────────────────────────
def test_option_selector():
    print(f"\n{SEP}")
    print("  TEST 5 — OPTION SELECTOR")
    print(SEP)

    spot = 22_847.5
    print(f"  Spot     : ₹{spot:.1f}")
    print(f"  ATM      : {OptionStrikeSelector.get_atm_strike(spot)}")
    print(f"  CE ATM   : {OptionStrikeSelector.select_strike(spot, 'CE', 'ATM')}")
    print(f"  CE ITM   : {OptionStrikeSelector.select_strike(spot, 'CE', 'ITM')}")
    print(f"  CE OTM   : {OptionStrikeSelector.select_strike(spot, 'CE', 'OTM')}")
    print(f"  PE ATM   : {OptionStrikeSelector.select_strike(spot, 'PE', 'ATM')}")
    print(f"  PE ITM   : {OptionStrikeSelector.select_strike(spot, 'PE', 'ITM')}")
    print(f"  PE OTM   : {OptionStrikeSelector.select_strike(spot, 'PE', 'OTM')}")

    symbol = OptionContractBuilder.get_trading_symbol("NIFTY", 22800, "03APR", "CE")
    print(f"\n  Symbol   : {symbol}")

    print("\n  Strike Ladder:")
    for row in StrikeLadderBuilder.build_ladder(spot, strikes=3):
        print(f"    {row['strike']:>6}  {row['label']:<6}  {row['distance_pct']:+.2f}%")

    assert OptionStrikeSelector.get_atm_strike(22_847) == 22_800
    print("  ✅ Option Selector OK")


# ──────────────────────────────────────────
# TEST 6: Data Provider (offline mode)
# ──────────────────────────────────────────
def test_data_provider():
    print(f"\n{SEP}")
    print("  TEST 6 — DATA PROVIDER (synthetic)")
    print(SEP)

    provider = DhanDataProvider()
    now = datetime.now()
    df = provider.get_candles("NIFTY", "5min", now - timedelta(hours=3), now)

    print(f"  Candles returned: {len(df)}")
    print(f"  Columns         : {list(df.columns)}")
    print(f"  Last close      : ₹{df['close'].iloc[-1]:.2f}")

    assert len(df) > 10, "Too few candles returned"
    assert {'open', 'high', 'low', 'close', 'volume'}.issubset(df.columns)
    print("  ✅ Data Provider OK")


# ──────────────────────────────────────────
# RUN ALL
# ──────────────────────────────────────────
if __name__ == "__main__":
    print(f"\n{SEP}")
    print("  🧪 NIFTY STRATEGY — TEST SUITE")
    print(SEP)

    test_indicators()
    test_strategy_components()
    test_full_strategy()
    test_risk_manager()
    test_option_selector()
    test_data_provider()

    print(f"\n{SEP}")
    print("  🎉 ALL TESTS PASSED")
    print(SEP)
