"""
============================================
TECHNICAL INDICATORS
============================================
EMA, RSI, ATR, Volume Profile, Candle Strength
============================================
"""

import pandas as pd
import numpy as np
from .config import Config


# ══════════════════════════════════════════
# RAW CALCULATION FUNCTIONS
# ══════════════════════════════════════════

def calculate_ema(df: pd.DataFrame, period: int, column: str = 'close') -> pd.Series:
    """Exponential Moving Average."""
    if column not in df.columns:
        raise ValueError(f"Column '{column}' not found in DataFrame")
    return df[column].ewm(span=period, adjust=False).mean()


def calculate_sma(df: pd.DataFrame, period: int, column: str = 'close') -> pd.Series:
    """Simple Moving Average."""
    return df[column].rolling(window=period).mean()


def calculate_rsi(df: pd.DataFrame, period: int = 14, column: str = 'close') -> pd.Series:
    """
    RSI using Wilder's EMA smoothing.
    Returns a Series in the range [0, 100].
    """
    if column not in df.columns:
        raise ValueError(f"Column '{column}' not found in DataFrame")

    delta = df[column].diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)

    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50)          # neutral on first tick


def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Average True Range — useful for SL placement."""
    high = df['high']
    low = df['low']
    prev_close = df['close'].shift()

    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)

    return tr.rolling(window=period).mean()


def calculate_volume_profile(df: pd.DataFrame, lookback: int = 20) -> dict:
    """Volume statistics for breakout validation."""
    recent = df['volume'].tail(lookback)
    avg = recent.mean()
    current = df['volume'].iloc[-1]

    return {
        'current': current,
        'average': avg,
        'max': recent.max(),
        'min': recent.min(),
        'ratio': current / avg if avg > 0 else 1.0,
        'is_spike': current > avg * Config.VOLUME_SPIKE_MULTIPLIER,
    }


def get_candle_strength(df: pd.DataFrame) -> dict:
    """
    Analyse the *last* candle's body strength.
    Returns metrics useful for breakout confirmation.
    """
    last = df.iloc[-1]

    body = abs(last['close'] - last['open'])
    rng = last['high'] - last['low']
    rng = rng if rng > 0 else np.nan

    body_pct = (body / rng * 100) if rng else 0.0

    return {
        'body': body,
        'body_percent': body_pct,
        'is_strong': body_pct >= Config.MIN_CANDLE_BODY_PERCENT,
        'is_bullish': last['close'] > last['open'],
        'is_bearish': last['close'] < last['open'],
        'upper_wick': last['high'] - max(last['close'], last['open']),
        'lower_wick': min(last['close'], last['open']) - last['low'],
    }


# ══════════════════════════════════════════
# INDICATOR ENGINE — ALL IN ONE
# ══════════════════════════════════════════

class IndicatorEngine:
    """Centralised indicator calculation engine."""

    def __init__(self, config: type = Config):
        self.config = config

    def calculate_all(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add all indicator columns to a copy of the DataFrame."""
        result = df.copy()

        result['ema20'] = calculate_ema(df, self.config.EMA_SHORT)
        result['ema50'] = calculate_ema(df, self.config.EMA_LONG)
        result['rsi'] = calculate_rsi(df, self.config.RSI_PERIOD)
        result['atr'] = calculate_atr(df)

        vol = calculate_volume_profile(df)
        result['volume_spike'] = vol['is_spike']
        result['volume_ratio'] = vol['ratio']

        candle = get_candle_strength(df)
        result['candle_strong'] = candle['is_strong']

        return result

    def get_latest_values(self, df: pd.DataFrame) -> dict:
        """Return latest indicator snapshot as a plain dict."""
        enriched = self.calculate_all(df)
        last = enriched.iloc[-1]

        return {
            'close': last['close'],
            'ema20': last['ema20'],
            'ema50': last['ema50'],
            'rsi': last['rsi'],
            'atr': last['atr'],
            'volume_spike': bool(last.get('volume_spike', False)),
            'volume_ratio': float(last.get('volume_ratio', 1.0)),
            'candle_strong': bool(last.get('candle_strong', False)),
        }
