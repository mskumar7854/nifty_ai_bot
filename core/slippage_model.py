"""
============================================
💰 SLIPPAGE & BROKERAGE MODEL

Models REAL trading costs:
- Brokerage (flat per order)
- STT (Securities Transaction Tax)
- Exchange charges
- GST
- SEBI charges
- Stamp duty
- Slippage (market impact)
- Spread cost

Without this, backtests are LIES.
A system with 55% win rate and 1:2 R:R
becomes UNPROFITABLE after costs if not modeled.
============================================
"""

import numpy as np
from datetime import datetime
from typing import Dict, Optional
from dataclasses import dataclass

from utils.logger import get_logger
from config.settings import BrokerageConfig


@dataclass
class CostBreakdown:
    """Detailed cost breakdown for a trade"""
    # Entry costs
    entry_brokerage: float = 0
    entry_stt: float = 0
    entry_stamp_duty: float = 0
    entry_slippage: float = 0
    entry_spread: float = 0

    # Exit costs
    exit_brokerage: float = 0
    exit_stt: float = 0
    exit_slippage: float = 0

    # Common costs
    exchange_charges: float = 0
    sebi_charges: float = 0
    gst: float = 0

    # Totals
    total_entry_cost: float = 0
    total_exit_cost: float = 0
    total_round_trip: float = 0

    # Impact
    entry_impact_points: float = 0
    exit_impact_points: float = 0
    total_impact_points: float = 0

    def to_dict(self) -> dict:
        return {
            "entry_costs": f"₹{self.total_entry_cost:,.2f}",
            "exit_costs": f"₹{self.total_exit_cost:,.2f}",
            "total_round_trip": f"₹{self.total_round_trip:,.2f}",
            "total_impact_pts": f"{self.total_impact_points:.2f}",
            "breakdown": {
                "brokerage": f"₹{self.entry_brokerage + self.exit_brokerage:,.2f}",
                "stt": f"₹{self.entry_stt + self.exit_stt:,.2f}",
                "slippage": f"₹{self.entry_slippage + self.exit_slippage:,.2f}",
                "spread": f"₹{self.entry_spread:,.2f}",
                "exchange": f"₹{self.exchange_charges:,.2f}",
                "gst": f"₹{self.gst:,.2f}",
                "stamp": f"₹{self.entry_stamp_duty:,.2f}",
                "sebi": f"₹{self.sebi_charges:,.2f}",
            },
        }


class SlippageModel:
    """
    Realistic cost and slippage modeling.

    KEY INSIGHT:
    A trade that shows ₹1000 profit on paper
    might only be ₹600 profit after ALL costs.

    This model ensures your P&L is REAL.
    """

    def __init__(self, config: BrokerageConfig):
        self.config = config
        self.logger = get_logger("slippage_model")

        # Track actual vs expected fills
        self.fill_history = []

    def calculate_entry_price(
        self,
        signal_price: float,
        qty: int,
        lots: int,
        vix: float = 13.0,
        volume: int = 100000,
        is_market_order: bool = True,
    ) -> Dict:
        """
        Calculate realistic entry fill price
        including slippage and spread.
        """

        # ── Slippage calculation ──
        slippage = self._calculate_slippage(
            signal_price, qty, lots, vix, volume
        )

        # ── Spread cost ──
        spread = self._calculate_spread(vix)

        # For BUY: price goes UP (worse fill)
        fill_price = signal_price + slippage + (spread / 2)

        return {
            "signal_price": signal_price,
            "fill_price": round(fill_price, 2),
            "slippage_points": round(slippage, 2),
            "spread_points": round(spread, 2),
            "total_impact": round(slippage + spread / 2, 2),
        }

    def calculate_exit_price(
        self,
        signal_price: float,
        qty: int,
        lots: int,
        vix: float = 13.0,
        volume: int = 100000,
        is_stop_loss: bool = False,
    ) -> Dict:
        """
        Calculate realistic exit fill price.
        Stop losses tend to have WORSE slippage.
        """

        slippage = self._calculate_slippage(
            signal_price, qty, lots, vix, volume
        )

        # Stop losses get extra slippage
        if is_stop_loss:
            slippage *= 1.5

        # For SELL: price goes DOWN (worse fill)
        fill_price = signal_price - slippage

        return {
            "signal_price": signal_price,
            "fill_price": round(fill_price, 2),
            "slippage_points": round(slippage, 2),
            "is_stop_loss": is_stop_loss,
        }

    def calculate_full_costs(
        self,
        entry_price: float,
        exit_price: float,
        qty: int,
        lots: int,
        vix: float = 13.0,
    ) -> CostBreakdown:
        """
        Calculate COMPLETE round-trip costs.
        This is the truth your P&L must face.
        """

        cost = CostBreakdown()

        # Turnover
        entry_turnover = entry_price * qty
        exit_turnover = exit_price * qty
        total_turnover = entry_turnover + exit_turnover

        # ── Brokerage (flat per order, both sides) ──
        cost.entry_brokerage = min(
            self.config.brokerage_per_order,
            entry_turnover * 0.0003  # cap at 0.03%
        )
        cost.exit_brokerage = min(
            self.config.brokerage_per_order,
            exit_turnover * 0.0003
        )

        # ── STT (only on sell side for options) ──
        cost.exit_stt = exit_turnover * \
                        self.config.stt_sell_pct / 100

        # ── Exchange Transaction Charges ──
        cost.exchange_charges = total_turnover * \
                                self.config.transaction_charges_pct / 100

        # ── GST (on brokerage + exchange charges) ──
        gst_base = (cost.entry_brokerage +
                    cost.exit_brokerage +
                    cost.exchange_charges)
        cost.gst = gst_base * self.config.gst_pct / 100

        # ── SEBI Charges ──
        cost.sebi_charges = total_turnover / 10000000 * \
                            self.config.sebi_charges_per_crore

        # ── Stamp Duty (only on buy) ──
        cost.entry_stamp_duty = entry_turnover * \
                                self.config.stamp_duty_buy_pct / 100

        # ── Slippage ──
        slippage_points = self._calculate_slippage(
            entry_price, qty, lots, vix
        )
        cost.entry_slippage = slippage_points * qty
        cost.exit_slippage = slippage_points * qty * 0.8

        # ── Spread ──
        spread = self._calculate_spread(vix)
        cost.entry_spread = spread * qty

        # ── Totals ──
        cost.total_entry_cost = (
            cost.entry_brokerage +
            cost.entry_stamp_duty +
            cost.entry_slippage +
            cost.entry_spread
        )

        cost.total_exit_cost = (
            cost.exit_brokerage +
            cost.exit_stt +
            cost.exit_slippage
        )

        cost.total_round_trip = (
            cost.total_entry_cost +
            cost.total_exit_cost +
            cost.exchange_charges +
            cost.gst +
            cost.sebi_charges
        )

        # Impact in points
        cost.entry_impact_points = cost.total_entry_cost / qty \
            if qty > 0 else 0
        cost.exit_impact_points = cost.total_exit_cost / qty \
            if qty > 0 else 0
        cost.total_impact_points = cost.total_round_trip / qty \
            if qty > 0 else 0

        return cost

    def calculate_break_even(
        self,
        entry_price: float,
        qty: int,
        lots: int,
        direction: str = "BULLISH",
        vix: float = 13.0,
    ) -> Dict:
        """
        How much does price need to move JUST TO BREAK EVEN
        after all costs?
        """

        # Calculate total costs for a round trip
        # Assume exit at entry price (worst case)
        costs = self.calculate_full_costs(
            entry_price, entry_price, qty, lots, vix
        )

        # Points needed to cover costs
        break_even_points = costs.total_round_trip / qty \
            if qty > 0 else 0

        if direction == "BULLISH":
            break_even_price = entry_price + break_even_points
        else:
            break_even_price = entry_price - break_even_points

        return {
            "entry_price": entry_price,
            "break_even_price": round(break_even_price, 2),
            "points_to_break_even": round(break_even_points, 2),
            "total_costs": round(costs.total_round_trip, 2),
            "cost_as_pct_of_premium": round(
                costs.total_round_trip /
                (entry_price * qty) * 100
                if entry_price * qty > 0 else 0, 2
            ),
        }

    def _calculate_slippage(
        self,
        price: float,
        qty: int,
        lots: int,
        vix: float = 13.0,
        volume: int = 100000,
    ) -> float:
        """Calculate slippage based on model type"""

        if self.config.slippage_model == "fixed":
            return self.config.fixed_slippage_points

        elif self.config.slippage_model == "dynamic":
            # Base slippage
            base = self.config.dynamic_slippage_base

            # VIX adjustment (higher VIX = more slippage)
            vix_extra = max(0, (vix - 15)) * \
                        self.config.dynamic_slippage_vol_factor

            # Lot adjustment (more lots = more impact)
            lot_impact = self.config.impact_cost_per_lot * lots

            total = base + vix_extra + lot_impact

            # Random component (market microstructure noise)
            noise = np.random.uniform(0, 0.5)

            return min(
                total + noise,
                self.config.max_slippage_points
            )

        elif self.config.slippage_model == "volume":
            # Volume-based model
            participation_rate = (qty / max(volume, 1)) * 100

            if participation_rate > 5:
                return self.config.max_slippage_points
            elif participation_rate > 1:
                return self.config.fixed_slippage_points * 2
            else:
                return self.config.fixed_slippage_points

        return self.config.fixed_slippage_points

    def _calculate_spread(self, vix: float = 13.0) -> float:
        """Calculate bid-ask spread"""
        base_spread = self.config.typical_spread_points

        if vix >= self.config.wide_spread_threshold_vix:
            return base_spread * self.config.wide_spread_multiplier

        return base_spread

    def net_pnl(
        self,
        gross_pnl: float,
        entry_price: float,
        exit_price: float,
        qty: int,
        lots: int,
        vix: float = 13.0,
    ) -> Dict:
        """
        Calculate NET P&L after ALL costs.
        THIS is your real profit/loss.
        """
        costs = self.calculate_full_costs(
            entry_price, exit_price, qty, lots, vix
        )

        net = gross_pnl - costs.total_round_trip

        return {
            "gross_pnl": f"₹{gross_pnl:,.0f}",
            "total_costs": f"₹{costs.total_round_trip:,.0f}",
            "net_pnl": f"₹{net:,.0f}",
            "cost_pct_of_gross": f"{costs.total_round_trip / max(abs(gross_pnl), 1) * 100:.1f}%",
            "costs": costs.to_dict(),
        }
