"""
============================================
📊 ORDER FLOW ANALYZER — LRM Layer 4

Converts raw MarketSnapshot order flow fields
into actionable imbalance measurements.

Graceful degradation: when broker data is
unavailable, returns data_available=False.
The LRM excludes this component from its
denominator — it never treats missing data
as zero.

This is a stateless utility — no session
memory. Each call returns a fresh snapshot.
============================================
"""

from models.lrm_models import OrderFlowState, FlowDirection
from utils.logger import get_logger

logger = get_logger("order_flow_analyzer")

# ── Thresholds ──
IMBALANCE_THRESHOLD = 0.15      # Ratio above this = directional
LARGE_ORDER_THRESHOLD = 2       # Net large orders above this = significant
MIN_TOTAL_VOLUME = 100          # Minimum bid+ask volume to consider data valid


class OrderFlowAnalyzer:
    """
    Converts raw bid/ask volume and large order counts
    into an OrderFlowState measurement.

    Stateless — each call is independent.
    """

    def __init__(self):
        self._cumulative_delta: float = 0.0
        self._session_date: str = ""

    def reset_session(self, date_str: str):
        """Reset cumulative delta for new session."""
        if date_str != self._session_date:
            self._cumulative_delta = 0.0
            self._session_date = date_str

    def analyze(self, snapshot) -> OrderFlowState:
        """
        Analyze order flow from a MarketSnapshot.

        Args:
            snapshot: MarketSnapshot with bid_volume, ask_volume,
                      large_buy_orders, large_sell_orders

        Returns:
            OrderFlowState with availability flag and measurements.
        """
        bid_vol = getattr(snapshot, "bid_volume", 0.0) or 0.0
        ask_vol = getattr(snapshot, "ask_volume", 0.0) or 0.0
        large_buys = getattr(snapshot, "large_buy_orders", 0) or 0
        large_sells = getattr(snapshot, "large_sell_orders", 0) or 0

        total_vol = bid_vol + ask_vol

        # ── Check data availability ──
        if total_vol < MIN_TOTAL_VOLUME:
            return OrderFlowState(
                data_available=False,
                flow_direction=FlowDirection.UNAVAILABLE,
                flow_score=50.0,  # Neutral, NOT zero
            )

        # ── Compute delta ──
        delta = bid_vol - ask_vol
        self._cumulative_delta += delta

        # ── Compute imbalance ratio ──
        imbalance_ratio = abs(delta) / total_vol if total_vol > 0 else 0.0

        # ── Large order imbalance ──
        large_order_imbalance = large_buys - large_sells

        # ── Classify direction ──
        if imbalance_ratio >= IMBALANCE_THRESHOLD:
            if delta > 0:
                direction = FlowDirection.BUYING
            else:
                direction = FlowDirection.SELLING
        else:
            direction = FlowDirection.BALANCED

        # ── Compute flow score (0-100) ──
        # Neutral = 50. Buying pressure pushes toward 100, selling toward 0.
        # This is a measurement, not a judgment.
        raw_score = 50.0

        # Delta contribution: normalize by total volume
        delta_normalized = delta / total_vol if total_vol > 0 else 0.0
        raw_score += delta_normalized * 30.0  # ±30 points max from delta

        # Large order contribution
        if abs(large_order_imbalance) >= LARGE_ORDER_THRESHOLD:
            large_contrib = min(abs(large_order_imbalance), 10) * 2.0
            if large_order_imbalance > 0:
                raw_score += large_contrib
            else:
                raw_score -= large_contrib

        # Clamp to 0-100
        flow_score = max(0.0, min(100.0, raw_score))

        return OrderFlowState(
            data_available=True,
            delta=delta,
            cumulative_delta=self._cumulative_delta,
            imbalance_ratio=imbalance_ratio,
            large_order_imbalance=large_order_imbalance,
            flow_direction=direction,
            flow_score=flow_score,
        )
