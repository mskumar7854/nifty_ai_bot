"""
============================================
📋 ORDER TRACKER (P2-B)
Tracks order lifecycle and partial fills.

Provides actionable context when reconciliation
detects orphan positions — symbol, qty, cause,
and estimated P&L exposure.
============================================
"""

from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
from typing import Optional
import logging

logger = logging.getLogger("order_tracker")


class OrderStatus(Enum):
    PENDING = "PENDING"
    FILLED = "FILLED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    SL_PENDING = "SL_PENDING"
    SL_PLACED = "SL_PLACED"
    SL_FAILED = "SL_FAILED"


@dataclass
class OrderState:
    """Tracks the full lifecycle of a single order."""
    order_id: str
    symbol: str
    requested_qty: int
    filled_qty: int = 0
    remaining_qty: int = 0
    status: OrderStatus = OrderStatus.PENDING
    fill_price: float = 0.0
    error: str | None = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    # SL tracking
    sl_order_id: str | None = None
    sl_status: OrderStatus = OrderStatus.PENDING
    sl_trigger_price: float = 0.0
    sl_attempts: int = 0

    def is_partial(self) -> bool:
        """Returns True if order was partially filled."""
        return self.filled_qty > 0 and self.remaining_qty > 0

    def update_fill(self, filled_qty: int, fill_price: float) -> None:
        """Update with broker fill information."""
        self.filled_qty = filled_qty
        self.remaining_qty = self.requested_qty - filled_qty
        self.fill_price = fill_price
        self.updated_at = datetime.now()

        if self.filled_qty >= self.requested_qty:
            self.status = OrderStatus.FILLED
        elif self.filled_qty > 0:
            self.status = OrderStatus.PARTIAL
            logger.warning(
                "Partial fill detected: %s filled %d/%d @ %.2f",
                self.symbol, self.filled_qty, self.requested_qty, fill_price
            )

    def record_sl_attempt(self, success: bool, sl_order_id: str = "") -> None:
        """Record an SL placement attempt."""
        self.sl_attempts += 1
        self.updated_at = datetime.now()
        if success:
            self.sl_status = OrderStatus.SL_PLACED
            self.sl_order_id = sl_order_id
        else:
            self.sl_status = OrderStatus.SL_FAILED

    def to_alert_string(self) -> str:
        """Build a human-readable alert for reconciliation/admin notification."""
        estimated_pnl = "unknown"
        if self.fill_price > 0 and self.filled_qty > 0:
            estimated_pnl = f"₹{self.fill_price * self.filled_qty * 0.01:,.0f} at risk"

        return (
            f"⚠️ ORDER STATE ALERT\n"
            f"Symbol: {self.symbol}\n"
            f"Status: {self.status.value}\n"
            f"Qty: {self.filled_qty}/{self.requested_qty} (remaining: {self.remaining_qty})\n"
            f"Fill Price: ₹{self.fill_price:,.2f}\n"
            f"SL Status: {self.sl_status.value} (attempts: {self.sl_attempts})\n"
            f"Estimated exposure: {estimated_pnl}\n"
        )


def build_reconciliation_alert(orphan_position: dict) -> str:
    """Build an actionable reconciliation alert with full context."""
    symbol = orphan_position.get("tradingSymbol", "UNKNOWN")
    qty = orphan_position.get("netQty", 0)
    avg_price = orphan_position.get("averagePrice", 0)
    realized_pnl = orphan_position.get("realizedProfit", 0)

    return (
        f"⚠️ ORPHAN POSITION DETECTED\n"
        f"Symbol: {symbol}\n"
        f"Qty: {qty} lots\n"
        f"Avg Price: ₹{avg_price:,.2f}\n"
        f"Realized P&L: ₹{realized_pnl:,.0f}\n"
        f"Suggested action: Square off manually or use /kill\n"
        f"Trading halted pending manual resolution."
    )
