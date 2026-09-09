"""
============================================
⚡ ENTRY ENGINE — SMART ENTRY CONFIRMATION

Manages pending entries and confirmation logic.
Prevents chasing entries by requiring
confirmation candle or price action alignment.
============================================
"""

from enum import Enum
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Union, Any
from dataclasses import dataclass, field

from models import Signal, Direction
from utils.logger import get_logger
from config.settings import Settings


class PriceDomain(str, Enum):
    SPOT = "SPOT"
    OPTION_PREMIUM = "OPTION_PREMIUM"


PRICE_DOMAIN_SPOT = PriceDomain.SPOT
PRICE_DOMAIN_OPTION_PREMIUM = PriceDomain.OPTION_PREMIUM


@dataclass
class PendingEntry:
    """A signal waiting for entry confirmation with explicit price domain and contract lineage."""
    entry_id: str
    signal: Signal
    created_at: datetime
    adjusted_entry: Optional[float] = None
    confirmation_candles: int = 0
    status: str = "PENDING"  # PENDING | CONFIRMED | EXPIRED | CANCELLED
    price_domain: PriceDomain = PriceDomain.OPTION_PREMIUM
    expected_premium: Optional[float] = None
    spot_entry: Optional[float] = None
    underlying: str = "NIFTY"
    strike: Optional[float] = None
    option_type: Optional[str] = None
    expiry: Optional[str] = None
    snapshot_id: str = ""

    def __post_init__(self):
        if isinstance(self.price_domain, str):
            try:
                self.price_domain = PriceDomain(self.price_domain)
            except ValueError:
                raise ValueError(
                    f"Invalid price_domain '{self.price_domain}'. Must be one of {[d.value for d in PriceDomain]}"
                )


class EntryEngine:
    """
    Manages entry confirmations before executing trades.

    Prevents:
    - Chasing entries
    - FOMO trades
    - Bad fills
    """

    def __init__(self, settings: Settings, data_manager=None):
        self.settings = settings
        self.data_manager = data_manager
        self.logger = get_logger("entry_engine")
        self.pending_entries: Dict[str, PendingEntry] = {}
        self.confirmed_count = 0
        self.expired_count = 0
        self.cancelled_count = 0

        # Max wait time before entry expires (in minutes)
        self.max_wait_minutes = getattr(settings, "entry_max_wait_minutes", 3)
        self.tolerance_pct = getattr(settings, "entry_confirmation_tolerance_pct", 0.5)

    def create_pending_entry(
        self,
        signal: Signal,
        snapshot,
        df,
        price_domain: Optional[Union[str, PriceDomain]] = None,
    ) -> PendingEntry:
        """Create a pending entry waiting for confirmation with explicit domain validation."""

        entry_id = f"ENT-{uuid.uuid4().hex[:6].upper()}"

        inst_meta = signal.metadata.get("instrument", {}) if hasattr(signal, "metadata") and isinstance(signal.metadata, dict) else {}
        strike = getattr(signal, "strike", None) if getattr(signal, "strike", None) is not None else inst_meta.get("strike")
        option_type = getattr(signal, "option_type", None) or inst_meta.get("type")
        expiry = getattr(signal, "expiry", None) or inst_meta.get("expiry")
        underlying = getattr(signal, "symbol", None) or inst_meta.get("symbol") or "NIFTY"
        snap_id = getattr(signal, "id", "") or (getattr(snapshot, "snapshot_id", "") if snapshot else "") or ""

        has_complete_option = (strike is not None and option_type is not None and expiry is not None)
        has_partial_option = (strike is not None or option_type is not None or expiry is not None or ("instrument" in getattr(signal, "metadata", {}) if hasattr(signal, "metadata") and isinstance(signal.metadata, dict) else False))

        if price_domain is None:
            if has_complete_option:
                domain = PriceDomain.OPTION_PREMIUM
            elif has_partial_option:
                raise ValueError(
                    f"Incomplete option contract specification for pending entry: "
                    f"strike={strike}, option_type={option_type}, expiry={expiry}"
                )
            else:
                domain = PriceDomain.SPOT
        else:
            domain = PriceDomain(price_domain) if isinstance(price_domain, str) else price_domain

        expected_prem = None
        spot_p = None

        if domain == PriceDomain.OPTION_PREMIUM:
            if not has_complete_option:
                raise ValueError(
                    f"Cannot create OPTION_PREMIUM pending entry without complete contract: "
                    f"strike={strike}, option_type={option_type}, expiry={expiry}"
                )
            expected_prem = float(getattr(signal, "entry_price", 0.0) or (signal.metadata.get("premium_entry", 0.0) if hasattr(signal, "metadata") and isinstance(signal.metadata, dict) else 0.0))
            spot_p = float(getattr(signal, "spot_entry", 0.0) or (snapshot.price if snapshot else 0.0))
        else:
            spot_p = float(getattr(signal, "spot_entry", 0.0) or getattr(signal, "entry_price", 0.0) or (snapshot.price if snapshot else 0.0))

        pending = PendingEntry(
            entry_id=entry_id,
            signal=signal,
            created_at=datetime.now(),
            adjusted_entry=expected_prem if domain == PriceDomain.OPTION_PREMIUM else spot_p,
            confirmation_candles=0,
            status="PENDING",
            price_domain=domain,
            expected_premium=expected_prem,
            spot_entry=spot_p,
            underlying=str(underlying),
            strike=float(strike) if strike is not None else None,
            option_type=str(option_type) if option_type is not None else None,
            expiry=str(expiry) if expiry is not None else None,
            snapshot_id=str(snap_id),
        )

        self.pending_entries[entry_id] = pending

        if hasattr(signal, "metadata") and isinstance(signal.metadata, dict):
            signal.metadata["pending_entry_id"] = entry_id

        if domain == PriceDomain.OPTION_PREMIUM:
            self.logger.info(
                f"⏳ Pending entry created: {entry_id} | "
                f"{underlying} {strike} {option_type} @ ₹{expected_prem:,.1f} (Domain: {domain.value}, Snapshot: {snap_id})"
            )
        else:
            sig_type = signal.signal_type.value if hasattr(signal, "signal_type") and hasattr(signal.signal_type, "value") else str(getattr(signal, "signal_type", "SPOT"))
            self.logger.info(
                f"⏳ Pending entry created: {entry_id} | "
                f"{sig_type} @ ₹{spot_p:,.1f} (Domain: {domain.value})"
            )

        return pending

    def check_confirmations(
        self,
        snapshot,
        df,
        data_manager=None,
        quotes: Optional[Dict[str, Any]] = None,
    ) -> List[Tuple[str, PendingEntry]]:
        """
        Check all pending entries for confirmation with strict price-domain fidelity.
        Returns list of (entry_id, pending_entry) confirmed.
        """

        confirmed = []
        dm = data_manager or self.data_manager

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

            if pending.price_domain == PriceDomain.OPTION_PREMIUM:
                # ── DOMAIN: OPTION_PREMIUM ──
                # Must compare current option quote against expected option premium.
                # NEVER compare index spot price against option premium!
                current_quote = None
                if quotes:
                    key = f"{int(pending.strike)}_{pending.option_type}_{pending.expiry}"
                    sec_key = getattr(pending.signal, "security_id", None)
                    current_quote = quotes.get(key) or (quotes.get(sec_key) if sec_key else None)
                
                if current_quote is None and dm and hasattr(dm, "fetch_option_quote"):
                    try:
                        current_quote = dm.fetch_option_quote(
                            int(pending.strike),
                            pending.option_type,
                            pending.expiry
                        )
                    except Exception as qe:
                        self.logger.warning(f"⚠️ Failed to fetch confirmation quote for {eid}: {qe}")
                        current_quote = None

                if current_quote is None:
                    # Quote unavailable this tick; wait for next cycle or expiry
                    continue

                # For BUY orders, ask is the price to pay; fallback to ltp
                current_premium = getattr(current_quote, "ask", 0.0) if getattr(current_quote, "ask", 0.0) > 0 else getattr(current_quote, "ltp", 0.0)
                expected_prem = pending.expected_premium or pending.signal.entry_price

                if current_premium > 0 and expected_prem > 0:
                    price_diff_pct = abs(current_premium - expected_prem) / expected_prem * 100.0

                    if price_diff_pct <= self.tolerance_pct:
                        pending.status = "CONFIRMED"
                        pending.adjusted_entry = current_premium
                        if hasattr(pending.signal, "metadata") and isinstance(pending.signal.metadata, dict):
                            pending.signal.metadata["confirmed_quote"] = current_quote
                            pending.signal.metadata["confirmed_premium"] = current_premium
                        self.confirmed_count += 1
                        confirmed.append((eid, pending))
                        del self.pending_entries[eid]
                        self.logger.info(
                            f"✅ Entry confirmed: {eid} | {pending.underlying} {pending.strike} {pending.option_type} "
                            f"@ ₹{current_premium:,.2f} (expected: ₹{expected_prem:,.2f}, diff: {price_diff_pct:.2f}%)"
                        )
                    else:
                        self.logger.debug(
                            f"⏸️ Entry {eid} pending confirmation: premium drifted {price_diff_pct:.2f}% "
                            f"(current: ₹{current_premium:.2f} vs expected: ₹{expected_prem:.2f}, max allowed: {self.tolerance_pct}%)"
                        )

            elif pending.price_domain == PriceDomain.SPOT:
                # ── DOMAIN: SPOT ──
                current_price = snapshot.price if snapshot else 0
                expected_spot = pending.spot_entry or getattr(pending.signal, "spot_entry", 0.0) or pending.signal.entry_price

                if current_price > 0 and expected_spot > 0:
                    price_diff_pct = abs(current_price - expected_spot) / expected_spot * 100.0

                    if price_diff_pct <= self.tolerance_pct:
                        pending.status = "CONFIRMED"
                        pending.adjusted_entry = current_price
                        self.confirmed_count += 1
                        confirmed.append((eid, pending))
                        del self.pending_entries[eid]
                        self.logger.info(
                            f"✅ Entry confirmed (SPOT): {eid} @ "
                            f"₹{current_price:,.1f} (expected: ₹{expected_spot:,.1f}, diff: {price_diff_pct:.2f}%)"
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
