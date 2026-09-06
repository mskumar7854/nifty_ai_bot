"""
============================================
⚡ ENTRY ENGINE — SMART ENTRY CONFIRMATION

Manages pending entries and confirmation logic.
Prevents chasing entries by requiring
confirmation candle or price action alignment.
============================================
"""

import uuid
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field

from models import Signal, Direction
from utils.logger import get_logger
from config.settings import Settings


@dataclass
class PendingEntry:
    """A signal waiting for entry confirmation"""
    entry_id: str
    signal: Signal
    created_at: datetime
    adjusted_entry: Optional[float] = None
    confirmation_candles: int = 0
    status: str = "PENDING"  # PENDING | CONFIRMED | EXPIRED | CANCELLED


class EntryEngine:
    """
    Manages entry confirmations before executing trades.

    Prevents:
    - Chasing entries
    - FOMO trades
    - Bad fills
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self.logger = get_logger("entry_engine")
        self.pending_entries: Dict[str, PendingEntry] = {}
        self.confirmed_count = 0
        self.expired_count = 0
        self.cancelled_count = 0

        # Max wait time before entry expires (in minutes)
        self.max_wait_minutes = 3

    def create_pending_entry(
        self,
        signal: Signal,
        snapshot,
        df,
    ) -> PendingEntry:
        """Create a pending entry waiting for confirmation"""

        entry_id = f"ENT-{uuid.uuid4().hex[:6].upper()}"

        pending = PendingEntry(
            entry_id=entry_id,
            signal=signal,
            created_at=datetime.now(),
            adjusted_entry=signal.entry_price,
            confirmation_candles=0,
            status="PENDING",
        )

        self.pending_entries[entry_id] = pending

        self.logger.info(
            f"⏳ Pending entry created: {entry_id} | "
            f"{signal.signal_type.value} @ ₹{signal.entry_price:,.1f}"
        )

        return pending

    def check_confirmations(
        self,
        snapshot,
        df,
    ) -> List[Tuple[str, PendingEntry]]:
        """
        Check all pending entries for confirmation.
        Returns list of (entry_id, pending_entry) confirmed.
        """

        confirmed = []
        current_price = snapshot.price if snapshot else 0

        for eid, pending in list(self.pending_entries.items()):
            if pending.status != "PENDING":
                continue

            # Check expiry
            wait_minutes = (
                datetime.now() - pending.created_at
            ).total_seconds() / 60

            if wait_minutes > self.max_wait_minutes:
                pending.status = "EXPIRED"
                self.expired_count += 1
                del self.pending_entries[eid]
                self.logger.debug(
                    f"⏰ Entry expired: {eid} after "
                    f"{wait_minutes:.1f}min"
                )
                continue

            # Simple confirmation: price within 0.5% of entry
            if current_price > 0 and pending.signal.entry_price > 0:
                price_diff_pct = abs(
                    current_price - pending.signal.entry_price
                ) / pending.signal.entry_price * 100

                if price_diff_pct <= 0.5:
                    pending.status = "CONFIRMED"
                    pending.adjusted_entry = current_price
                    self.confirmed_count += 1
                    confirmed.append((eid, pending))
                    self.logger.info(
                        f"✅ Entry confirmed: {eid} @ "
                        f"₹{current_price:,.1f}"
                    )

        return confirmed

    def cancel_pending(self, entry_id: str):
        """Cancel a specific pending entry"""
        if entry_id in self.pending_entries:
            self.pending_entries[entry_id].status = "CANCELLED"
            self.cancelled_count += 1
            del self.pending_entries[entry_id]

    def cancel_all_pending(self):
        """Cancel all pending entries on shutdown"""
        count = len(self.pending_entries)
        self.pending_entries.clear()
        if count > 0:
            self.logger.info(f"Cancelled {count} pending entries")

    def get_stats(self) -> Dict:
        return {
            "pending": len(self.pending_entries),
            "confirmed": self.confirmed_count,
            "expired": self.expired_count,
            "cancelled": self.cancelled_count,
        }
