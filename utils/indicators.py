"""
============================================
TECHNICAL INDICATOR CALCULATIONS
Pure functions for all indicator math
============================================
"""

import numpy as np
import pandas as pd
from typing import Tuple, Optional


def calculate_vwap(df: pd.DataFrame) -> pd.Series:
    """
    Calculate VWAP (Volume Weighted Average Price)
    Requires: high, low, close, volume columns
    """
    typical_price = (df['high'] + df['low'] + df['close']) / 3
    cumulative_tp_vol = (typical_price * df['volume']).cumsum()
    cumulative_vol = df['volume'].cumsum()
    vwap = cumulative_tp_vol / cumulative_vol
    return vwap


def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Calculate RSI (Relative Strength Index)"""
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)

    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def calculate_ema(series: pd.Series, period: int) -> pd.Series:
    """Calculate Exponential Moving Average"""
    return series.ewm(span=period, adjust=False).mean()


def calculate_sma(series: pd.Series, period: int) -> pd.Series:
    """Calculate Simple Moving Average"""
    return series.rolling(window=period).mean()


def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Calculate Average True Range"""
    high = df['high']
    low = df['low']
    close = df['close']

    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low - close.shift(1))

    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = true_range.rolling(window=period).mean()
    return atr


def calculate_volume_sma(volume: pd.Series, period: int = 20) -> pd.Series:
    """Calculate volume moving average"""
    return volume.rolling(window=period).mean()


def candle_analysis(row: pd.Series) -> dict:
    """
    Analyze a single candle
    Returns: body_size, wick_upper, wick_lower, body_ratio, type
    """
    open_p = row['open']
    high_p = row['high']
    low_p = row['low']
    close_p = row['close']

    body_size = abs(close_p - open_p)
    total_range = high_p - low_p

    if total_range == 0:
        return {
            "body_size": 0,
            "wick_upper": 0,
            "wick_lower": 0,
            "body_ratio": 0,
            "type": "doji",
            "is_bullish": False,
        }

    is_bullish = close_p > open_p

    if is_bullish:
        wick_upper = high_p - close_p
        wick_lower = open_p - low_p
    else:
        wick_upper = high_p - open_p
        wick_lower = close_p - low_p

    body_ratio = body_size / total_range

    # Classify candle
    if body_ratio < 0.1:
        candle_type = "doji"
    elif body_ratio > 0.7:
        candle_type = "marubozu"
    elif wick_upper > body_size * 2:
        candle_type = "shooting_star" if not is_bullish else "inverted_hammer"
    elif wick_lower > body_size * 2:
        candle_type = "hammer" if is_bullish else "hanging_man"
    else:
        candle_type = "standard"

    return {
        "body_size": round(body_size, 2),
        "wick_upper": round(wick_upper, 2),
        "wick_lower": round(wick_lower, 2),
        "body_ratio": round(body_ratio, 4),
        "type": candle_type,
        "is_bullish": is_bullish,
    }


def detect_structure_break(
    highs: pd.Series, lows: pd.Series, lookback: int = 20
) -> dict:
    """
    Detect market structure breaks
    Returns: {'break_type': 'bullish'|'bearish'|'none', 'level': float}
    """
    if len(highs) < lookback:
        return {"break_type": "none", "level": 0}

    recent_highs = highs.tail(lookback)
    recent_lows = lows.tail(lookback)

    prev_high = recent_highs.iloc[:-1].max()
    prev_low = recent_lows.iloc[:-1].min()
    current_high = recent_highs.iloc[-1]
    current_low = recent_lows.iloc[-1]

    if current_high > prev_high:
        return {"break_type": "bullish", "level": prev_high}
    elif current_low < prev_low:
        return {"break_type": "bearish", "level": prev_low}

    return {"break_type": "none", "level": 0}


def calculate_support_resistance(
    df: pd.DataFrame, lookback: int = 50, num_levels: int = 3
) -> dict:
    """Calculate key support and resistance levels"""
    if len(df) < lookback:
        lookback = len(df)

    recent = df.tail(lookback)

    # Find pivot highs and lows
    pivot_highs = []
    pivot_lows = []

    for i in range(2, len(recent) - 2):
        if (recent['high'].iloc[i] > recent['high'].iloc[i-1] and
            recent['high'].iloc[i] > recent['high'].iloc[i-2] and
            recent['high'].iloc[i] > recent['high'].iloc[i+1] and
            recent['high'].iloc[i] > recent['high'].iloc[i+2]):
            pivot_highs.append(recent['high'].iloc[i])

        if (recent['low'].iloc[i] < recent['low'].iloc[i-1] and
            recent['low'].iloc[i] < recent['low'].iloc[i-2] and
            recent['low'].iloc[i] < recent['low'].iloc[i+1] and
            recent['low'].iloc[i] < recent['low'].iloc[i+2]):
            pivot_lows.append(recent['low'].iloc[i])

    # Sort and return top levels
    resistances = sorted(pivot_highs, reverse=True)[:num_levels]
    supports = sorted(pivot_lows)[:num_levels]

    return {
        "resistance": resistances,
        "support": supports,
    }


def calculate_adx(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """
    Calculate ADX (Average Directional Index)
    Returns: DataFrame with adx, plus_di, minus_di
    """
    df = df.copy()
    high = df['high']
    low = df['low']
    close = df['close']

    # 1. Calculate TR (True Range)
    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low - close.shift(1))
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    # 2. Calculate DM (+ and -)
    up_move = high - high.shift(1)
    down_move = low.shift(1) - low

    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

    # 3. Smooth with Wilder's method
    tr_smoothed = tr.ewm(alpha=1/period, adjust=False).mean()
    plus_dm_smoothed = pd.Series(plus_dm).ewm(alpha=1/period, adjust=False).mean()
    minus_dm_smoothed = pd.Series(minus_dm).ewm(alpha=1/period, adjust=False).mean()

    # 4. Calculate DI+ and DI-
    plus_di = 100 * (plus_dm_smoothed / tr_smoothed)
    minus_di = 100 * (minus_dm_smoothed / tr_smoothed)

    # 5. Calculate DX and ADX
    dx = 100 * (abs(plus_di - minus_di) / (plus_di + minus_di))
    adx = dx.ewm(alpha=1/period, adjust=False).mean()

    return pd.DataFrame({
        'adx': adx,
        'plus_di': plus_di,
        'minus_di': minus_di
    }, index=df.index)


def calculate_bollinger_bands(
    series: pd.Series, period: int = 20, std_dev: float = 2.0
) -> pd.DataFrame:
    """
    Calculate Bollinger Bands
    Returns: DataFrame with upper, middle, lower, width
    """
    sma = series.rolling(window=period).mean()
    std = series.rolling(window=period).std()

    upper = sma + (std * std_dev)
    lower = sma - (std * std_dev)
    width = (upper - lower) / sma

    return pd.DataFrame({
        'upper': upper,
        'middle': sma,
        'lower': lower,
        'width': width
    }, index=series.index)


def calculate_supertrend(
    df: pd.DataFrame, period: int = 10, multiplier: float = 3.0
) -> pd.DataFrame:
    """
    Calculate Supertrend
    Returns: DataFrame with supertrend, direction
    """
    high = df['high']
    low = df['low']
    close = df['close']

    atr = calculate_atr(df, period)

    # HL2 + (multiplier * ATR)
    hl2 = (high + low) / 2
    upper_band = hl2 + (multiplier * atr)
    lower_band = hl2 - (multiplier * atr)

    # Final bands adjustment logic
    final_upper_band = pd.Series(0.0, index=df.index)
    final_lower_band = pd.Series(0.0, index=df.index)
    supertrend = pd.Series(0.0, index=df.index)
    direction = pd.Series(1, index=df.index)  # 1 for bull, -1 for bear

    for i in range(1, len(df)):
        # Final Upper Band
        if (upper_band.iloc[i] < final_upper_band.iloc[i-1]) or \
           (close.iloc[i-1] > final_upper_band.iloc[i-1]):
            final_upper_band.iloc[i] = upper_band.iloc[i]
        else:
            final_upper_band.iloc[i] = final_upper_band.iloc[i-1]

        # Final Lower Band
        if (lower_band.iloc[i] > final_lower_band.iloc[i-1]) or \
           (close.iloc[i-1] < final_lower_band.iloc[i-1]):
            final_lower_band.iloc[i] = lower_band.iloc[i]
        else:
            final_lower_band.iloc[i] = final_lower_band.iloc[i-1]

        # Supertrend and Direction
        if supertrend.iloc[i-1] == final_upper_band.iloc[i-1]:
            if close.iloc[i] > final_upper_band.iloc[i]:
                direction.iloc[i] = 1
                supertrend.iloc[i] = final_lower_band.iloc[i]
            else:
                direction.iloc[i] = -1
                supertrend.iloc[i] = final_upper_band.iloc[i]
        else:
            if close.iloc[i] < final_lower_band.iloc[i]:
                direction.iloc[i] = -1
                supertrend.iloc[i] = final_upper_band.iloc[i]
            else:
                direction.iloc[i] = 1
                supertrend.iloc[i] = final_lower_band.iloc[i]

    return pd.DataFrame({
        'supertrend': supertrend,
        'direction': direction
    }, index=df.index)


def find_swing_points(
    series: pd.Series, order: int = 5
) -> dict:
    """
    Detect local peaks and troughs
    Returns: {'highs': [(idx, val), ...], 'lows': [(idx, val), ...]}
    """
    highs = []
    lows = []

    for i in range(order, len(series) - order):
        # Local peak
        window = series.iloc[i - order : i + order + 1]
        if series.iloc[i] == window.max():
            highs.append((i, series.iloc[i]))

        # Local trough
        if series.iloc[i] == window.min():
            lows.append((i, series.iloc[i]))

    return {
        "highs": highs,
        "lows": lows,
    }
