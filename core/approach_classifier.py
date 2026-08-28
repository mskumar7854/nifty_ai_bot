"""
============================================
🏃 APPROACH CLASSIFIER — LRM Layer 2

Characterizes HOW price is approaching a
liquidity zone. This is the layer that
distinguishes meaningful zone tests from
random price wandering.

Key question:
  "Is price arriving impulsively (high sweep
   probability), grinding slowly (high
   rejection probability), or exhausted
   (ambiguous)?"

All raw metrics are preserved alongside the
classification so we can validate whether
the classifier has predictive value.
============================================
"""

import numpy as np
import pandas as pd
from typing import Optional

from models.lrm_models import ApproachProfile, ApproachType, LiquidityZone
from utils.logger import get_logger

logger = get_logger("approach_classifier")

# ── Configuration ──
MIN_CANDLES_FOR_CLASSIFICATION = 3   # Minimum candles needed
DEFAULT_LOOKBACK = 8                 # Candles to analyze on approach
VELOCITY_IMPULSIVE_THRESHOLD = 0.5   # ATR-normalized velocity above this = impulsive
VELOCITY_GRINDING_THRESHOLD = 0.15   # Below this = grinding
VOLUME_EXPANDING_THRESHOLD = 0.3     # Positive slope above this = expanding
MOMENTUM_STRONG_THRESHOLD = 0.3      # RSI slope above this = strong


class ApproachClassifier:
    """
    Classifies how price is approaching a liquidity zone.

    Stateless — each call analyzes the recent candle
    history independently.
    """

    def __init__(self):
        pass

    def classify(
        self,
        df: pd.DataFrame,
        zone: LiquidityZone,
        price: float,
        atr: float,
        lookback: int = DEFAULT_LOOKBACK,
    ) -> ApproachProfile:
        """
        Classify the approach to a liquidity zone.

        Args:
            df: OHLCV DataFrame with at least `lookback` rows
            zone: The liquidity zone being approached
            price: Current price
            atr: Current ATR

        Returns:
            ApproachProfile with raw metrics and classification.
        """
        if df is None or len(df) < MIN_CANDLES_FOR_CLASSIFICATION:
            return ApproachProfile(approach_type=ApproachType.INSUFFICIENT)

        if atr <= 0:
            atr = 15.0

        # Use the last `lookback` candles
        n = min(lookback, len(df))
        recent = df.tail(n)

        closes = recent["close"].values
        if len(closes) < MIN_CANDLES_FOR_CLASSIFICATION:
            return ApproachProfile(approach_type=ApproachType.INSUFFICIENT)

        # ── 1. Velocity: rate of price change toward zone ──
        # Positive = moving toward zone, normalized by ATR
        zone_mid = zone.mid
        distances = np.array([abs(c - zone_mid) for c in closes])

        # Velocity = average reduction in distance per candle
        if len(distances) >= 2:
            distance_changes = np.diff(distances)
            # Negative change = getting closer to zone
            velocity_raw = -np.mean(distance_changes)  # Positive = approaching
            velocity = velocity_raw / atr  # ATR-normalized
        else:
            velocity = 0.0

        # ── 2. Acceleration: is velocity increasing or decreasing? ──
        acceleration = 0.0
        if len(distances) >= 3:
            dist_changes = np.diff(distances)
            if len(dist_changes) >= 2:
                accel_raw = np.diff(dist_changes)
                acceleration = -np.mean(accel_raw) / atr  # Positive = accelerating toward zone

        # ── 3. Volume trend: expanding or contracting? ──
        volume_trend = 0.0
        if "volume" in recent.columns:
            volumes = recent["volume"].values
            valid_vols = volumes[volumes > 0]
            if len(valid_vols) >= MIN_CANDLES_FOR_CLASSIFICATION:
                # Linear regression slope of volume, normalized
                x = np.arange(len(valid_vols), dtype=float)
                if np.std(x) > 0 and np.std(valid_vols) > 0:
                    correlation = np.corrcoef(x, valid_vols)[0, 1]
                    volume_trend = float(correlation) if not np.isnan(correlation) else 0.0

        # ── 4. Momentum: RSI slope on approach candles ──
        momentum = 0.0
        if len(closes) >= 4:
            # Simple momentum proxy: slope of close prices, ATR-normalized
            x = np.arange(len(closes), dtype=float)
            if np.std(x) > 0 and np.std(closes) > 0:
                slope = np.polyfit(x, closes, 1)[0]
                momentum = slope / atr  # Positive = prices rising

                # Adjust sign based on zone role
                # For resistance (above), approaching = prices rising = positive momentum
                # For support (below), approaching = prices falling = negative momentum
                # We want momentum to reflect "approach strength" regardless of direction
                if zone.role == "SUPPORT":
                    momentum = -momentum  # Falling toward support = positive approach momentum

        # ── 5. Classify approach type ──
        abs_velocity = abs(velocity)

        if abs_velocity >= VELOCITY_IMPULSIVE_THRESHOLD:
            if volume_trend >= VOLUME_EXPANDING_THRESHOLD:
                approach_type = ApproachType.IMPULSIVE
            elif volume_trend < -VOLUME_EXPANDING_THRESHOLD:
                approach_type = ApproachType.EXHAUSTION
            else:
                approach_type = ApproachType.IMPULSIVE
        elif abs_velocity <= VELOCITY_GRINDING_THRESHOLD:
            approach_type = ApproachType.GRINDING
        else:
            # Medium velocity — use volume and acceleration to disambiguate
            if acceleration < -0.05 and volume_trend < 0:
                approach_type = ApproachType.EXHAUSTION
            elif acceleration > 0.05 and volume_trend > 0:
                approach_type = ApproachType.IMPULSIVE
            else:
                approach_type = ApproachType.GRINDING

        # ── 6. Compute approach score (0-100) ──
        # Higher score = more decisive approach (either impulsive or strongly grinding)
        # This is a measurement of approach "clarity", not a quality judgment
        score_components = []

        # Velocity component (0-40): higher velocity = more decisive
        vel_score = min(abs_velocity / VELOCITY_IMPULSIVE_THRESHOLD, 1.0) * 40
        score_components.append(vel_score)

        # Volume trend component (0-30): expanding volume = more decisive
        vol_score = (volume_trend + 1.0) / 2.0 * 30  # Normalize -1..+1 to 0..30
        score_components.append(vol_score)

        # Momentum component (0-30): stronger momentum = more decisive
        mom_score = min(abs(momentum) / MOMENTUM_STRONG_THRESHOLD, 1.0) * 30
        score_components.append(mom_score)

        approach_score = sum(score_components)

        return ApproachProfile(
            velocity=float(velocity),
            acceleration=float(acceleration),
            volume_trend=float(volume_trend),
            momentum=float(momentum),
            candles_measured=n,
            approach_type=approach_type,
            approach_score=round(approach_score, 2),
        )
