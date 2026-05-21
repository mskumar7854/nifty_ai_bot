"""
============================================
⚡ EXECUTION FIDELITY ENGINE — Phase A

Sits between Signal Generation and SimulationEngine.
Replaces idealized fills with realistic market friction.

Pipeline:
    Trade Signal
        ↓
    Latency Injection         (regime-aware ms delay)
        ↓
    Spread Modeling           (moneyness-aware bid/ask)
        ↓
    Slippage Model            (VIX + volatility)
        ↓
    Rejection Check           (regime + expiry probability)
        ↓
    Partial Fill Check        (OTM liquidity)
        ↓
    ExecutionResult
        ↓
    SimulatedTrade (or None if rejected)

Design Principles:
    - Deterministic: seeded RNG for reproducible simulations
    - Lightweight: probabilistic, not order-book level
    - Extensible: broker profiles, shock events can be added later
============================================
"""

import random
import math
from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Optional

from utils.logger import get_logger


# ─────────────────────────────────────────────
# MONEYNESS CATEGORIES
# ─────────────────────────────────────────────

MONEYNESS_DEEP_ITM  = "DEEP_ITM"
MONEYNESS_ATM       = "ATM"
MONEYNESS_SLIGHT_OTM = "SLIGHT_OTM"
MONEYNESS_FAR_OTM   = "FAR_OTM"

# Spread % of premium per moneyness tier
# (base values; VIX and expiry multipliers applied on top)
SPREAD_TABLE = {
    MONEYNESS_DEEP_ITM:   (0.10, 0.20),   # 0.10–0.20%
    MONEYNESS_ATM:        (0.15, 0.30),   # 0.15–0.30%
    MONEYNESS_SLIGHT_OTM: (0.40, 0.80),   # 0.40–0.80%
    MONEYNESS_FAR_OTM:    (1.00, 3.00),   # 1.00–3.00%
}

# Regime-dependent latency windows (ms)
LATENCY_TABLE = {
    "TRENDING":   (150, 250),
    "CHOPPY":     (200, 350),
    "RANGING":    (200, 350),
    "BREAKOUT":   (300, 600),
    "VOLATILE":   (400, 900),
    "UNKNOWN":    (200, 400),
}

# Rejection probability by regime
REJECTION_TABLE = {
    "TRENDING":   0.01,   # 1%
    "CHOPPY":     0.03,   # 3%
    "RANGING":    0.03,   # 3%
    "BREAKOUT":   0.04,   # 4%
    "VOLATILE":   0.05,   # 5%
    "UNKNOWN":    0.02,
}

# Base slippage as fraction of premium
BASE_SLIPPAGE_PCT = 0.0005   # 0.05%


# ─────────────────────────────────────────────
# RESULT DATACLASS
# ─────────────────────────────────────────────

@dataclass
class ExecutionResult:
    """
    Full execution telemetry returned by ExecutionFidelityEngine.

    If rejected=True, the caller should discard the trade.
    All point/percentage fields are relative to the option premium.
    """
    # Outcome
    rejected: bool = False
    rejection_reason: str = ""

    # Fill details
    fill_price: float = 0.0          # actual fill price after all friction
    signal_price: float = 0.0        # original signal ask price
    filled_qty: int = 0              # quantity actually filled
    fill_ratio: float = 1.0          # filled_qty / requested_qty

    # Friction breakdown (all in premium points)
    slippage_pts: float = 0.0        # market impact slippage
    spread_cost_pts: float = 0.0     # half-spread paid on entry
    total_friction_pts: float = 0.0  # slippage + spread

    # Context
    latency_ms: int = 0
    moneyness_category: str = ""
    vix_at_fill: float = 0.0
    regime_at_fill: str = ""

    # Numerical quality score (0–100)
    execution_quality_score: float = 0.0
    execution_quality: str = ""       # GOOD | FAIR | POOR

    # Timestamp
    fill_time: str = field(
        default_factory=lambda: datetime.now().isoformat()
    )

    def to_dict(self) -> dict:
        return {
            "rejected": self.rejected,
            "rejection_reason": self.rejection_reason,
            "fill_price": self.fill_price,
            "signal_price": self.signal_price,
            "filled_qty": self.filled_qty,
            "fill_ratio": round(self.fill_ratio, 3),
            "slippage_pts": round(self.slippage_pts, 3),
            "spread_cost_pts": round(self.spread_cost_pts, 3),
            "total_friction_pts": round(self.total_friction_pts, 3),
            "latency_ms": self.latency_ms,
            "moneyness": self.moneyness_category,
            "vix": self.vix_at_fill,
            "regime": self.regime_at_fill,
            "quality_score": round(self.execution_quality_score, 1),
            "quality": self.execution_quality,
            "fill_time": self.fill_time,
        }


@dataclass
class ExitExecutionResult:
    """Exit-side slippage when closing a simulated trade."""
    exit_price: float = 0.0           # actual exit fill price
    trigger_price: float = 0.0        # original SL or TP trigger price
    slippage_pts: float = 0.0         # points lost to slippage at exit
    exit_reason: str = ""
    quality: str = ""


# ─────────────────────────────────────────────
# ENGINE
# ─────────────────────────────────────────────

class ExecutionFidelityEngine:
    """
    Realistic execution simulator for NIFTY options paper trading.

    Supports seeded randomness for reproducible simulations.
    Call with seed=42 for regression testing / before-after comparisons.

    Usage:
        engine = ExecutionFidelityEngine()
        result = engine.simulate_entry(
            signal_price=118.40,
            spot_price=24500,
            strike=24500,
            option_type='CE',
            qty=75,
            regime='TRENDING',
            vix=14.5,
            expiry_date=date(2026, 5, 28),
        )
        if result.rejected:
            return  # skip this trade
        trade.entry_price = result.fill_price
    """

    def __init__(self, seed: Optional[int] = None):
        self.logger = get_logger("exec_fidelity")
        self._rng = random.Random(seed)    # seeded for reproducibility
        self._seed = seed

        # Lifetime telemetry
        self.total_entries_attempted = 0
        self.total_rejected = 0
        self.total_partial_fills = 0
        self.cumulative_slippage_pts = 0.0
        self.cumulative_spread_pts = 0.0

        self.logger.info(
            f"⚡ ExecutionFidelityEngine initialized | "
            f"Seed: {'random' if seed is None else seed}"
        )

    def reseed(self, seed: int):
        """Reseed for a new reproducible run (e.g. regression tests)."""
        self._rng = random.Random(seed)
        self._seed = seed

    # ─────────────────────────────────────────
    # PUBLIC: ENTRY SIMULATION
    # ─────────────────────────────────────────

    def simulate_entry(
        self,
        signal_price: float,
        spot_price: float,
        strike: float,
        option_type: str,        # 'CE' | 'PE'
        qty: int,
        regime: str = "UNKNOWN",
        vix: float = 14.0,
        expiry_date: Optional[date] = None,
    ) -> ExecutionResult:
        """
        Run the full 6-stage execution pipeline.
        Returns ExecutionResult. Caller must check result.rejected.
        """
        self.total_entries_attempted += 1

        # ── Stage 1: Latency ──
        latency_ms = self._simulate_latency(regime)

        # ── Stage 2: Moneyness classification ──
        moneyness = self._classify_moneyness(spot_price, strike, option_type)

        # ── Stage 3: Expiry proximity ──
        days_to_expiry = self._days_to_expiry(expiry_date)
        expiry_multiplier = self._expiry_multiplier(days_to_expiry)

        # ── Stage 4: Rejection check ──
        rejection_result = self._check_rejection(regime, days_to_expiry)
        if rejection_result:
            self.total_rejected += 1
            self.logger.warning(
                f"🚫 Order REJECTED | Regime: {regime} | "
                f"Reason: {rejection_result} | "
                f"DTE: {days_to_expiry}"
            )
            return ExecutionResult(
                rejected=True,
                rejection_reason=rejection_result,
                signal_price=signal_price,
                regime_at_fill=regime,
                vix_at_fill=vix,
                moneyness_category=moneyness,
                latency_ms=latency_ms,
            )

        # ── Stage 5: Spread calculation ──
        spread_pts = self._calculate_spread(
            premium=signal_price,
            moneyness=moneyness,
            vix=vix,
            expiry_multiplier=expiry_multiplier,
        )

        # ── Stage 6: Slippage calculation ──
        slippage_pts = self._calculate_slippage(
            premium=signal_price,
            vix=vix,
            regime=regime,
        )

        total_friction = spread_pts + slippage_pts
        fill_price = round(signal_price + total_friction, 2)

        # ── Partial fill check ──
        filled_qty, fill_ratio = self._simulate_partial_fill(
            qty, moneyness, days_to_expiry
        )
        if fill_ratio < 1.0:
            self.total_partial_fills += 1

        # ── Execution quality score ──
        quality_score = self._compute_quality_score(
            slippage_pts=slippage_pts,
            spread_pts=spread_pts,
            fill_ratio=fill_ratio,
            latency_ms=latency_ms,
        )
        quality_label = self._quality_label(quality_score)

        # ── Telemetry accumulation ──
        self.cumulative_slippage_pts += slippage_pts
        self.cumulative_spread_pts += spread_pts

        result = ExecutionResult(
            rejected=False,
            fill_price=fill_price,
            signal_price=signal_price,
            filled_qty=filled_qty,
            fill_ratio=fill_ratio,
            slippage_pts=slippage_pts,
            spread_cost_pts=spread_pts,
            total_friction_pts=total_friction,
            latency_ms=latency_ms,
            moneyness_category=moneyness,
            vix_at_fill=vix,
            regime_at_fill=regime,
            execution_quality_score=quality_score,
            execution_quality=quality_label,
        )

        self.logger.info(
            f"✅ FILL | Price: ₹{signal_price:.1f} → ₹{fill_price:.1f} | "
            f"Slip: +{slippage_pts:.2f}pts | Spread: +{spread_pts:.2f}pts | "
            f"Latency: {latency_ms}ms | Fill: {fill_ratio*100:.0f}% | "
            f"Moneyness: {moneyness} | Quality: {quality_label} ({quality_score:.0f})"
        )

        return result

    # ─────────────────────────────────────────
    # PUBLIC: EXIT SIMULATION
    # ─────────────────────────────────────────

    def simulate_exit(
        self,
        trigger_price: float,
        exit_reason: str,       # 'STOP_LOSS' | 'TARGET_1' | 'TIME_EXIT'
        vix: float = 14.0,
        regime: str = "UNKNOWN",
    ) -> ExitExecutionResult:
        """
        Simulate realistic exit fill. SL exits get worse slippage (gap-through).
        """
        is_sl = exit_reason == "STOP_LOSS"

        # SL: 1.5× slippage (gap-through effect during fast moves)
        slippage_mult = 1.5 if is_sl else 0.5

        # Base slippage at exit (smaller than entry — no spread cost on close)
        base = trigger_price * BASE_SLIPPAGE_PCT
        vix_adj = max(0, (vix - 15) * 0.02) * trigger_price
        regime_mult = 1.5 if regime in ("VOLATILE", "BREAKOUT") else 1.0

        slippage_pts = round(
            (base + vix_adj) * regime_mult * slippage_mult, 2
        )

        # On exit: we SELL, so fill is BELOW trigger (we get less)
        exit_price = round(max(0.05, trigger_price - slippage_pts), 2)

        quality = "GOOD" if slippage_pts <= 0.3 else ("FAIR" if slippage_pts <= 0.8 else "POOR")

        return ExitExecutionResult(
            exit_price=exit_price,
            trigger_price=trigger_price,
            slippage_pts=slippage_pts,
            exit_reason=exit_reason,
            quality=quality,
        )

    # ─────────────────────────────────────────
    # TELEMETRY
    # ─────────────────────────────────────────

    def get_lifetime_stats(self) -> dict:
        """Summary statistics across all simulated executions."""
        attempted = max(self.total_entries_attempted, 1)
        return {
            "entries_attempted": self.total_entries_attempted,
            "rejected": self.total_rejected,
            "rejection_rate_pct": round(self.total_rejected / attempted * 100, 2),
            "partial_fills": self.total_partial_fills,
            "partial_fill_rate_pct": round(self.total_partial_fills / attempted * 100, 2),
            "avg_slippage_pts": round(
                self.cumulative_slippage_pts / attempted, 3
            ),
            "avg_spread_pts": round(
                self.cumulative_spread_pts / attempted, 3
            ),
        }

    # ─────────────────────────────────────────
    # PRIVATE: STAGES
    # ─────────────────────────────────────────

    def _simulate_latency(self, regime: str) -> int:
        """Regime-dependent latency in milliseconds (not a real sleep)."""
        lo, hi = LATENCY_TABLE.get(regime.upper(), (200, 400))
        return self._rng.randint(lo, hi)

    def _classify_moneyness(
        self, spot: float, strike: float, option_type: str
    ) -> str:
        """
        Classify option moneyness by distance from spot.
        For CE: strike > spot → OTM; for PE: strike < spot → OTM.
        """
        if spot <= 0:
            return MONEYNESS_ATM

        if option_type.upper() == "CE":
            distance_pct = (strike - spot) / spot * 100
        else:
            distance_pct = (spot - strike) / spot * 100

        # distance_pct > 0 = OTM, < 0 = ITM
        if distance_pct < -1.0:
            return MONEYNESS_DEEP_ITM
        elif distance_pct <= 1.0:
            return MONEYNESS_ATM
        elif distance_pct <= 3.0:
            return MONEYNESS_SLIGHT_OTM
        else:
            return MONEYNESS_FAR_OTM

    def _days_to_expiry(self, expiry_date: Optional[date]) -> int:
        if expiry_date is None:
            return 7  # assume mid-week if unknown
        delta = (expiry_date - date.today()).days
        return max(0, delta)

    def _expiry_multiplier(self, days_to_expiry: int) -> float:
        """
        Spread multiplier as expiry approaches.
        Last 2 days → significantly wider spreads (gamma risk, illiquidity).
        """
        if days_to_expiry == 0:
            return 2.0   # expiry day — very wide
        elif days_to_expiry == 1:
            return 1.75
        elif days_to_expiry == 2:
            return 1.5
        return 1.0

    def _check_rejection(self, regime: str, days_to_expiry: int) -> Optional[str]:
        """
        Probabilistic order rejection.
        Returns rejection reason string, or None if order proceeds.
        """
        prob = REJECTION_TABLE.get(regime.upper(), 0.02)

        # Add 3% on expiry day (liquidity constraints, wide spreads)
        if days_to_expiry == 0:
            prob += 0.03

        if self._rng.random() < prob:
            reason = "EXPIRY_LIQUIDITY" if days_to_expiry == 0 else f"REGIME_{regime.upper()}_REJECTION"
            return reason
        return None

    def _calculate_spread(
        self,
        premium: float,
        moneyness: str,
        vix: float,
        expiry_multiplier: float,
    ) -> float:
        """
        Moneyness-aware half-spread paid on entry (we BUY at ASK).
        Returns spread in option premium points.
        """
        lo_pct, hi_pct = SPREAD_TABLE.get(moneyness, (0.15, 0.30))
        # Pick a random spread within the tier
        spread_pct = self._rng.uniform(lo_pct, hi_pct) / 100.0

        # VIX widens spreads above 15
        vix_factor = 1.0 + max(0, (vix - 15) * 0.04)

        raw_spread_pts = premium * spread_pct * vix_factor * expiry_multiplier

        # Half-spread (we pay half on entry; the other half on exit)
        return round(raw_spread_pts / 2.0, 3)

    def _calculate_slippage(
        self,
        premium: float,
        vix: float,
        regime: str,
    ) -> float:
        """
        Market-impact slippage.
        Base 0.05% of premium, scaled by VIX and regime volatility.
        """
        base = premium * BASE_SLIPPAGE_PCT

        vix_mult = 1.0 + max(0, (vix - 15) * 0.05)

        regime_mult = {
            "TRENDING":   1.0,
            "CHOPPY":     1.2,
            "RANGING":    1.2,
            "BREAKOUT":   1.4,
            "VOLATILE":   1.8,
        }.get(regime.upper(), 1.0)

        # Add a small random noise component
        noise = self._rng.uniform(0.0, premium * 0.0002)

        return round(base * vix_mult * regime_mult + noise, 3)

    def _simulate_partial_fill(
        self, qty: int, moneyness: str, days_to_expiry: int
    ) -> tuple:
        """
        Returns (filled_qty, fill_ratio).
        Full fills for ATM/liquid contracts; probabilistic for OTM/expiry.
        """
        is_illiquid = (
            moneyness == MONEYNESS_FAR_OTM
            or days_to_expiry == 0
        )

        if is_illiquid and self._rng.random() < 0.25:  # 25% chance of partial on illiquid
            fill_ratio = self._rng.uniform(0.6, 0.95)
            # Round to nearest lot (NIFTY = 75 qty)
            lot_size = 75
            lots = max(1, round(qty * fill_ratio / lot_size))
            filled_qty = lots * lot_size
            fill_ratio = filled_qty / qty
            return filled_qty, fill_ratio

        return qty, 1.0

    def _compute_quality_score(
        self,
        slippage_pts: float,
        spread_pts: float,
        fill_ratio: float,
        latency_ms: int,
    ) -> float:
        """
        Numerical execution quality score 0–100.

        Component weights:
            Fill ratio     30 pts  (partial fills penalized)
            Slippage       30 pts  (lower = better)
            Spread         20 pts  (tighter = better)
            Latency        20 pts  (lower = better)
        """
        # Fill ratio score (30 pts max)
        fill_score = fill_ratio * 30.0

        # Slippage score (30 pts max) — benchmark: 0.10 pts = full score
        slippage_score = max(0.0, 30.0 * (1.0 - slippage_pts / 0.50))

        # Spread score (20 pts max) — benchmark: 0.20 pts = full score
        spread_score = max(0.0, 20.0 * (1.0 - spread_pts / 1.00))

        # Latency score (20 pts max) — benchmark: 250ms = full score
        latency_score = max(0.0, 20.0 * (1.0 - (latency_ms - 150) / 750.0))

        total = fill_score + slippage_score + spread_score + latency_score
        return round(min(100.0, max(0.0, total)), 1)

    def _quality_label(self, score: float) -> str:
        if score >= 80:
            return "GOOD"
        elif score >= 60:
            return "FAIR"
        return "POOR"
