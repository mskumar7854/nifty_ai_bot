"""
============================================
⚡ LIQUIDITY EVENT DETECTOR — LRM Layer 3

Deterministic detection of sweep, rejection,
and absorption events at liquidity zones.

This is the core research layer. The key
hypothesis is:

  "Zone → Approach → Sweep/Reject → Reaction
   produces materially better forward R than
   random zone touches."

All events use ATR-calibrated thresholds
so they adapt to volatility conditions.

Cross-references AMD Engine state when
available — if AMD is in MANIPULATION at the
same zone, event confidence is boosted.
============================================
"""

import pandas as pd
from typing import Optional

from models.lrm_models import (
    LiquidityEvent, LiquidityEventType, LiquidityZone,
)
from models.amd_state import AMDState, AMDPhase
from utils.logger import get_logger

logger = get_logger("liquidity_event_detector")

# ── Configuration (ATR-calibrated) ──
SWEEP_BREACH_ATR = 0.15           # Breach beyond zone by at least this × ATR
SWEEP_WINDOW_CANDLES = 3          # Must close back inside within this many candles
REJECTION_DISTANCE_ATR = 0.25     # Move away from zone by this × ATR to confirm
REJECTION_WINDOW_CANDLES = 4      # Must reject within this many candles
REJECTION_WICK_RATIO = 0.40       # Wick ratio above this strengthens rejection
ABSORPTION_CANDLES = 6            # Sitting at zone for this many candles = absorption
VOLUME_SPIKE_MULTIPLIER = 1.5     # Volume above avg × this = spike


class LiquidityEventDetector:
    """
    Detects liquidity events at zone boundaries.

    Stateful: tracks recent candle history at each zone
    to detect multi-candle patterns (sweep-and-return,
    absorption).

    Session-scoped: call reset_session() at market open.
    """

    def __init__(self):
        # zone_id -> tracking state
        self._zone_tracking: dict = {}
        self._session_date: str = ""

    def reset_session(self, date_str: str):
        """Reset tracking for a new session."""
        if date_str != self._session_date:
            self._zone_tracking.clear()
            self._session_date = date_str

    def detect(
        self,
        df: pd.DataFrame,
        zone: LiquidityZone,
        price: float,
        atr: float,
        sr_latest_event: Optional[str] = None,
        amd_state: Optional[AMDState] = None,
        oi_confirmed: bool = False,
    ) -> LiquidityEvent:
        """
        Detect a liquidity event at the given zone.

        Args:
            df: OHLCV DataFrame (recent candles)
            zone: The liquidity zone being tested
            price: Current price (latest close)
            atr: Current ATR
            sr_latest_event: Latest SREngine event type if any
            amd_state: Current AMDState if available
            oi_confirmed: Whether OI data confirms this zone

        Returns:
            LiquidityEvent with type, confidence, and details.
        """
        if df is None or len(df) < 2 or atr <= 0:
            return LiquidityEvent(event_type=LiquidityEventType.NONE)

        zid = zone.zone_id
        if zid not in self._zone_tracking:
            self._zone_tracking[zid] = {
                "candles_in_zone": 0,
                "breached": False,
                "breach_side": None,
                "breach_candle_idx": 0,
                "breach_extreme": 0.0,
                "total_candles_tracked": 0,
            }

        tracking = self._zone_tracking[zid]
        tracking["total_candles_tracked"] += 1

        # Current candle data
        current = df.iloc[-1]
        high = current.get("high", price)
        low = current.get("low", price)
        close = price
        open_p = current.get("open", price)

        # Volume analysis
        vol = current.get("volume", 0) if "volume" in df.columns else 0
        avg_vol = df["volume"].tail(20).mean() if "volume" in df.columns and len(df) >= 5 else 0
        volume_spike = vol > avg_vol * VOLUME_SPIKE_MULTIPLIER if avg_vol > 0 else False

        # Wick analysis
        candle_range = high - low
        if candle_range > 0:
            upper_wick = high - max(open_p, close)
            lower_wick = min(open_p, close) - low
            wick_ratio = max(upper_wick, lower_wick) / candle_range
        else:
            wick_ratio = 0.0

        # Is price inside the zone?
        in_zone = zone.contains_price(price)
        breach_threshold = atr * SWEEP_BREACH_ATR

        # ── Detect SWEEP ──
        # Price breaches beyond zone boundary, then closes back inside
        if zone.role == "RESISTANCE":
            # Sweep above resistance
            if high > zone.price_high + breach_threshold:
                if not tracking["breached"]:
                    tracking["breached"] = True
                    tracking["breach_side"] = "ABOVE"
                    tracking["breach_candle_idx"] = tracking["total_candles_tracked"]
                    tracking["breach_extreme"] = high

            if tracking["breached"] and tracking["breach_side"] == "ABOVE":
                tracking["breach_extreme"] = max(tracking["breach_extreme"], high)
                candles_since_breach = (
                    tracking["total_candles_tracked"] - tracking["breach_candle_idx"]
                )

                if close <= zone.price_high and candles_since_breach <= SWEEP_WINDOW_CANDLES:
                    # SWEEP confirmed: breached above, closed back inside/below
                    breach_dist = tracking["breach_extreme"] - zone.price_high
                    return self._build_sweep_event(
                        breach_dist, atr, candles_since_breach,
                        wick_ratio, vol, avg_vol, volume_spike,
                        oi_confirmed, amd_state, sr_latest_event,
                    )

                if candles_since_breach > SWEEP_WINDOW_CANDLES:
                    # Too many candles — this is ACCEPTANCE, not sweep
                    tracking["breached"] = False
                    return self._build_acceptance_event()

        elif zone.role == "SUPPORT":
            # Sweep below support
            if low < zone.price_low - breach_threshold:
                if not tracking["breached"]:
                    tracking["breached"] = True
                    tracking["breach_side"] = "BELOW"
                    tracking["breach_candle_idx"] = tracking["total_candles_tracked"]
                    tracking["breach_extreme"] = low

            if tracking["breached"] and tracking["breach_side"] == "BELOW":
                tracking["breach_extreme"] = min(tracking["breach_extreme"], low)
                candles_since_breach = (
                    tracking["total_candles_tracked"] - tracking["breach_candle_idx"]
                )

                if close >= zone.price_low and candles_since_breach <= SWEEP_WINDOW_CANDLES:
                    # SWEEP confirmed: breached below, closed back inside/above
                    breach_dist = zone.price_low - tracking["breach_extreme"]
                    return self._build_sweep_event(
                        breach_dist, atr, candles_since_breach,
                        wick_ratio, vol, avg_vol, volume_spike,
                        oi_confirmed, amd_state, sr_latest_event,
                    )

                if candles_since_breach > SWEEP_WINDOW_CANDLES:
                    tracking["breached"] = False
                    return self._build_acceptance_event()

        # ── Detect REJECTION ──
        # Price tested zone (in_zone or touched), then moved away
        if in_zone:
            tracking["candles_in_zone"] += 1
        else:
            if tracking["candles_in_zone"] > 0 and not tracking["breached"]:
                # Was in zone, now moved away — check if it's a rejection
                rejection_dist = atr * REJECTION_DISTANCE_ATR

                if zone.role == "RESISTANCE" and price < zone.price_low - rejection_dist:
                    # Rejected from resistance — bearish
                    event = self._build_rejection_event(
                        wick_ratio, vol, avg_vol, volume_spike,
                        oi_confirmed, amd_state, sr_latest_event,
                    )
                    tracking["candles_in_zone"] = 0
                    return event

                elif zone.role == "SUPPORT" and price > zone.price_high + rejection_dist:
                    # Rejected from support — bullish
                    event = self._build_rejection_event(
                        wick_ratio, vol, avg_vol, volume_spike,
                        oi_confirmed, amd_state, sr_latest_event,
                    )
                    tracking["candles_in_zone"] = 0
                    return event

            tracking["candles_in_zone"] = 0

        # ── Detect ABSORPTION ──
        if tracking["candles_in_zone"] >= ABSORPTION_CANDLES and not tracking["breached"]:
            return self._build_absorption_event(
                tracking["candles_in_zone"], volume_spike,
                oi_confirmed, amd_state,
            )

        # ── No event ──
        return LiquidityEvent(event_type=LiquidityEventType.NONE)

    def _build_sweep_event(
        self, breach_dist, atr, candles_beyond,
        wick_ratio, vol, avg_vol, volume_spike,
        oi_confirmed, amd_state, sr_latest_event,
    ) -> LiquidityEvent:
        """Build a SWEEP event with confirming factors."""
        confirming = 0
        if wick_ratio >= REJECTION_WICK_RATIO:
            confirming += 1
        if volume_spike:
            confirming += 1
        if oi_confirmed:
            confirming += 1

        amd_aligned = False
        if amd_state and amd_state.phase == AMDPhase.MANIPULATION:
            confirming += 1
            amd_aligned = True

        if sr_latest_event in ("FAILED_BREAKOUT",):
            confirming += 1

        # Confidence = base + confirming factor bonus
        confidence = min(0.40 + confirming * 0.12, 1.0)

        # Event score (0-100)
        event_score = confidence * 100

        # Reset tracking
        zids_to_reset = [
            zid for zid, t in self._zone_tracking.items()
            if t.get("breached")
        ]
        for zid in zids_to_reset:
            self._zone_tracking[zid]["breached"] = False
            self._zone_tracking[zid]["candles_in_zone"] = 0

        vol_ratio = vol / avg_vol if avg_vol > 0 else 0.0

        return LiquidityEvent(
            event_type=LiquidityEventType.SWEEP,
            confidence=confidence,
            breach_distance=breach_dist,
            breach_distance_atr=breach_dist / atr if atr > 0 else 0,
            candles_beyond=candles_beyond,
            closed_back_inside=True,
            wick_ratio=wick_ratio,
            rejection_volume_ratio=vol_ratio,
            oi_confirmed=oi_confirmed,
            volume_spike=volume_spike,
            amd_aligned=amd_aligned,
            confirming_factor_count=confirming,
            event_score=event_score,
        )

    def _build_rejection_event(
        self, wick_ratio, vol, avg_vol, volume_spike,
        oi_confirmed, amd_state, sr_latest_event,
    ) -> LiquidityEvent:
        """Build a REJECTION event."""
        confirming = 0
        if wick_ratio >= REJECTION_WICK_RATIO:
            confirming += 1
        if volume_spike:
            confirming += 1
        if oi_confirmed:
            confirming += 1

        amd_aligned = False
        if amd_state and amd_state.phase in (
            AMDPhase.MANIPULATION, AMDPhase.EXPANSION,
        ):
            confirming += 1
            amd_aligned = True

        if sr_latest_event in ("REJECTION",):
            confirming += 1

        confidence = min(0.30 + confirming * 0.14, 1.0)
        vol_ratio = vol / avg_vol if avg_vol > 0 else 0.0

        return LiquidityEvent(
            event_type=LiquidityEventType.REJECTION,
            confidence=confidence,
            wick_ratio=wick_ratio,
            rejection_volume_ratio=vol_ratio,
            oi_confirmed=oi_confirmed,
            volume_spike=volume_spike,
            amd_aligned=amd_aligned,
            confirming_factor_count=confirming,
            event_score=confidence * 100,
        )

    def _build_absorption_event(
        self, candles_in_zone, volume_spike, oi_confirmed, amd_state,
    ) -> LiquidityEvent:
        """Build an ABSORPTION event."""
        confirming = 0
        if volume_spike:
            confirming += 1
        if oi_confirmed:
            confirming += 1
        if candles_in_zone >= ABSORPTION_CANDLES * 2:
            confirming += 1  # Extended absorption

        amd_aligned = False
        if amd_state and amd_state.phase == AMDPhase.ACCUMULATION:
            confirming += 1
            amd_aligned = True

        confidence = min(0.25 + confirming * 0.15, 1.0)

        return LiquidityEvent(
            event_type=LiquidityEventType.ABSORPTION,
            confidence=confidence,
            candles_beyond=candles_in_zone,
            oi_confirmed=oi_confirmed,
            volume_spike=volume_spike,
            amd_aligned=amd_aligned,
            confirming_factor_count=confirming,
            event_score=confidence * 100,
        )

    @staticmethod
    def _build_acceptance_event() -> LiquidityEvent:
        """Build an ACCEPTANCE event (clean breakout, zone invalidated)."""
        return LiquidityEvent(
            event_type=LiquidityEventType.ACCEPTANCE,
            confidence=0.5,
            event_score=0.0,  # Acceptance = zone failed, not interesting for reaction trades
        )
