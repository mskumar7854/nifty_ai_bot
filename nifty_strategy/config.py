"""
============================================
NIFTY INTRADAY STRATEGY — CONFIG
============================================
All strategy knobs in one place.
Credentials come from ../.env via python-dotenv.
============================================
"""

import os
from dotenv import load_dotenv

# Load project-root .env (one level up from nifty_strategy/)
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))


class Config:
    # ─────────────── INDICATOR SETTINGS ─────────────────
    EMA_SHORT = 20
    EMA_LONG = 50
    RSI_PERIOD = 14
    RSI_BULLISH_THRESHOLD = 60
    RSI_BEARISH_THRESHOLD = 40

    # ─────────────── TREND / MOMENTUM ────────────────────
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    SIDEWAYS = "SIDEWAYS"

    MOMENTUM_BULLISH = "BULLISH"
    MOMENTUM_BEARISH = "BEARISH"
    MOMENTUM_WEAK = "WEAK"

    # ─────────────── BREAKOUT ─────────────────────────────
    BREAKOUT = "BREAKOUT"
    BREAKDOWN = "BREAKDOWN"
    NO_SIGNAL = "NO_SIGNAL"

    # ─────────────── CANDLE TIMEFRAMES ────────────────────
    TREND_TIMEFRAME = "5min"       # EMA trend detection
    MOMENTUM_TIMEFRAME = "1min"    # RSI momentum
    ENTRY_TIMEFRAME = "5min"       # Breakout confirmation

    # ─────────────── NO-TRADE ZONES ───────────────────────
    MARKET_OPEN_HOUR = 9
    MARKET_OPEN_MINUTE = 15
    MARKET_OPEN_END_MINUTE = 30    # First 15 min — no trades
    LUNCH_START_HOUR = 12
    LUNCH_END_HOUR = 13
    LUNCH_END_MINUTE = 30

    # ─────────────── RISK MANAGEMENT ──────────────────────
    MAX_DAILY_LOSS = 2000          # ₹2,000 daily stop
    MAX_TRADES_PER_DAY = 3
    STOP_LOSS_PERCENT = 20         # 20% of premium
    TARGET_REWARD_RATIO = 2        # Minimum 1:2 R:R

    # ─────────────── TRAILING STOP ────────────────────────
    TRAIL_TO_COST_PERCENT = 10     # Move SL to cost at +10%
    LOCK_PROFIT_PERCENT = 20       # Lock 50% profit at +20%
    PARTIAL_EXIT_PERCENT = 30      # Partial exit trigger
    PARTIAL_EXIT_QTY_PERCENT = 50  # Exit 50% of position

    # ─────────────── OPTION SETTINGS ──────────────────────
    UNDERLYING = "NIFTY"
    EXPIRY_DAYS = 4                # Weekly expiry distance
    STRIKE_STEP = 100              # Nifty strike step
    LOT_SIZE = 50
    DEFAULT_QTY = 50

    # ─────────────── TRADE SIGNALS ────────────────────────
    ALLOWED_SIGNALS = ["BUY_CE", "BUY_PE"]
    NO_TRADE = "NO_TRADE"

    # ─────────────── BREAKOUT VALIDATION ──────────────────
    MIN_CANDLE_BODY_PERCENT = 50   # Body must be ≥50% of range
    VOLUME_SPIKE_MULTIPLIER = 1.5  # Must be 1.5× average volume

    # ─────────────── LOGGING ──────────────────────────────
    LOG_FILE = "nifty_strategy/trades.log"
    LOG_LEVEL = "INFO"

    # ─────────────── TELEGRAM FILTERS (Refinement) ───────
    TELEGRAM_MODE = "STRICT"  # STRICT | TEST | OFF
    TELEGRAM_STRICT_THRESHOLD = 0.85
    TELEGRAM_TEST_THRESHOLD = 0.75
    # Dynamic scaling based on score
    TELEGRAM_SIZE_MAPPING = {
        0.90: 0.75,
        0.85: 0.50,
        0.00: 0.25
    }

    # ─────────────── DHAN CREDENTIALS (from .env) ─────────
    DHAN_CLIENT_ID: str = os.getenv("DHAN_CLIENT_ID", "")
    DHAN_ACCESS_TOKEN: str = os.getenv("DHAN_ACCESS_TOKEN", "")
