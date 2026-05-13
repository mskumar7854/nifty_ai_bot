"""
============================================================
🕳️  GAP PENALTY MANAGER  (Priority 4 Fix)

Replaces the binary session_gap_detected flag with a
physics-based penalty model:

  1. gap_strength  = abs(gap) / ATR        ← normalized severity
  2. gap_penalty() = base × exp(-k × mins) ← time-decaying impact

Why this is better than the old fixed-point system:
  - A 60pt gap on ATR=280 is MINOR (gap_strength ≈ 0.21)
  - A 60pt gap on ATR=90  is MAJOR (gap_strength ≈ 0.67)
  - Penalty melts away after open — no all-day suppression

Decay schedule (accelerated params, 2026-05-11):
  Time after open   Remaining penalty
  ─────────────────────────────────
  9:15 (open)       100%
  9:25 (10m)        ~67%
  9:35 (20m)        ~45%
  9:45 (30m)        ~30%
  10:15 (60m)       ~9%   ← effectively zero
  10:45 (90m)       ~3%
  11:15 (120m)      negligible

Integration with DecisionEngineV3:
  - Replace the session_gap_detected bool with this manager.
  - Call manager.update(snapshot, minutes_since_open) each cycle.
  - Use manager.get_penalty() in compute_weighted_score() ONCE
    instead of compounding it via multiple layers.
============================================================
"""

import math
from datetime import datetime, date
from typing import Optional

from utils.logger import AgentLogger


# ── Decay constant: chosen so penalty reaches ~5% after 75 minutes ──
# k = -ln(0.05) / 75  ≈ 0.040
# (Increased from 0.025 → 0.040 on 2026-05-11 to shrink opening dead zone
# from ~35min to ~20min. Old value caused 30+ min suppression on 200pt gaps.)
_DEFAULT_DECAY_K = 0.040

# ── Severity tiers (gap_strength = gap / ATR) ──
# These translate normalised gap size into a max initial penalty.
# minor:       ≤0.25  → soft penalty cap at 0.08 (8%  weight reduction)
# moderate:    ≤0.50  → 0.15 cap
# significant: ≤0.80  → 0.22 cap
# major:       ≤0.95  → 0.30 cap
# critical:    >0.95  → 0.40 cap  (gap > ~1 ATR — extreme open distortion)
_GAP_SEVERITY_THRESHOLDS = [
    (0.25, 0.08, "MINOR"),
    (0.50, 0.15, "MODERATE"),
    (0.80, 0.22, "SIGNIFICANT"),
    (0.95, 0.30, "MAJOR"),
    (float("inf"), 0.40, "CRITICAL"),
]

# ── Absolute gap hard floor ──
# When a gap is large in absolute terms (> ABSOLUTE_GAP_FLOOR_PTS), we enforce
# a MINIMUM penalty regardless of ATR normalization.
# This prevents a large ATR from washing out the danger of a 100pt+ gap open.
#
# ATR=280, gap=103 → gap_strength=0.37 → MODERATE tier → ~11% penalty → mult=0.89
# But 103pts IS dangerous at open.  Hard floor: mult >= 0.65 prevented.
#   mult_floor = 0.65 means at minimum a 35% weight reduction on a big gap day.
ABSOLUTE_GAP_FLOOR_PTS = 80.0        # any gap > 80 pts triggers the floor
ABSOLUTE_GAP_MULT_FLOOR = 0.65       # multiplier can be no higher than this


class GapPenaltyManager:
    """
    Session-scoped gap penalty that decays exponentially after the open.

    Usage:
        manager = GapPenaltyManager()
        manager.new_session(gap_pts, atr)         # called once at session start
        penalty = manager.get_penalty(minutes)    # called each cycle
        # penalty is 0.0–0.30, representing additive weight reduction
    """

    def __init__(self, decay_k: float = _DEFAULT_DECAY_K):
        self.decay_k = decay_k
        self.logger = AgentLogger("gap_penalty")

        # State reset each trading day
        self._session_date: Optional[date] = None
        self._gap_strength: float = 0.0
        self._initial_penalty: float = 0.0
        self._severity_label: str = "NONE"
        self._gap_points: float = 0.0
        self._atr_at_open: float = 0.0
        self._session_open_minutes: Optional[datetime] = None

    # ─── Public API ────────────────────────────────────────────────────

    def new_session(self, gap_pts: float, atr: float) -> None:
        """
        Call once at the start of each trading day.

        Args:
            gap_pts: abs(day_open - prev_close) in index points
            atr:     current ATR at session open (same units as gap_pts)
        """
        self._session_date = datetime.now().date()
        self._session_open_minutes = datetime.now()
        self._gap_points = gap_pts
        self._atr_at_open = max(atr, 1.0)  # guard against zero ATR

        # Normalize severity against ATR
        self._gap_strength = gap_pts / self._atr_at_open

        # Look up penalty tier
        for threshold, max_penalty, label in _GAP_SEVERITY_THRESHOLDS:
            if self._gap_strength <= threshold:
                # Scale within the tier for smoother curve
                self._initial_penalty = max_penalty * min(
                    self._gap_strength / threshold, 1.0
                )
                self._severity_label = label
                break

        self.logger.info(
            f"📊 Gap Session Init | Gap: {gap_pts:.1f}pts | ATR: {atr:.1f} | "
            f"Strength: {self._gap_strength:.2f} | Severity: {self._severity_label} | "
            f"Initial penalty: {self._initial_penalty:.3f} ({self._initial_penalty*100:.1f}%)"
        )

        # ── Absolute gap hard floor warning ──
        if gap_pts > ABSOLUTE_GAP_FLOOR_PTS:
            effective_mult = round(1.0 - self._initial_penalty, 4)
            if effective_mult > ABSOLUTE_GAP_MULT_FLOOR:
                self.logger.warning(
                    f"⚠️ ABSOLUTE GAP HARD FLOOR ACTIVE: {gap_pts:.1f}pts > {ABSOLUTE_GAP_FLOOR_PTS}pts. "
                    f"ATR-normalised mult={effective_mult:.3f} would be too lenient. "
                    f"Enforcing floor: multiplier ≤ {ABSOLUTE_GAP_MULT_FLOOR}"
                )

    def get_penalty(self, minutes_since_open: Optional[float] = None) -> float:
        """
        Returns a 0.0–0.30 additive penalty value.

        A return of 0.0 means no suppression.
        A return of 0.15 means weight scores are reduced by 15%.

        Args:
            minutes_since_open: If None, auto-computes from session start time.
        """
        if self._initial_penalty == 0.0:
            return 0.0

        if minutes_since_open is None:
            if self._session_open_minutes is None:
                return 0.0
            elapsed = (datetime.now() - self._session_open_minutes).total_seconds() / 60.0
            minutes_since_open = max(0.0, elapsed)

        decayed = self._initial_penalty * math.exp(
            -self.decay_k * minutes_since_open
        )
        return round(max(0.0, decayed), 4)

    def get_unified_penalty_multiplier(
        self, minutes_since_open: Optional[float] = None
    ) -> float:
        """
        Returns a 0.60–1.00 MULTIPLIER (not additive) for score scaling.
        This is the format consumed by compute_weighted_score().

        e.g. penalty=0.15 → multiplier=0.85

        Hard floor: if raw gap > ABSOLUTE_GAP_FLOOR_PTS, the multiplier
        is capped at ABSOLUTE_GAP_MULT_FLOOR (0.65) so that a large ATR
        cannot make a 100pt+ gap appear negligible.
        """
        base_mult = round(1.0 - self.get_penalty(minutes_since_open), 4)

        # Apply absolute gap hard floor if applicable
        if self._gap_points > ABSOLUTE_GAP_FLOOR_PTS:
            # The floor is also time-decayed: after 120 minutes, the floor itself
            # melts away (multiplied by the same decay factor as the penalty).
            if minutes_since_open is None:
                if self._session_open_minutes is None:
                    return base_mult
                elapsed = (datetime.now() - self._session_open_minutes).total_seconds() / 60.0
                minutes_since_open = max(0.0, elapsed)
            decay_factor = math.exp(-self.decay_k * minutes_since_open)
            effective_floor = ABSOLUTE_GAP_MULT_FLOOR + (1.0 - ABSOLUTE_GAP_MULT_FLOOR) * (1.0 - decay_factor)
            effective_floor = round(min(effective_floor, 1.0), 4)
            base_mult = min(base_mult, effective_floor)

        return base_mult

    def is_active(self) -> bool:
        """Returns True if gap penalty has any meaningful effect (>1%)."""
        return self.get_penalty() > 0.01

    def is_new_session_needed(self) -> bool:
        """Returns True if today has not been initialised yet."""
        return self._session_date != datetime.now().date()

    def get_status(self) -> dict:
        """Diagnostic dump for logging."""
        mins = 0.0
        if self._session_open_minutes:
            mins = (datetime.now() - self._session_open_minutes).total_seconds() / 60.0
        current_penalty = self.get_penalty(mins)
        return {
            "session_date": str(self._session_date),
            "gap_points": round(self._gap_points, 1),
            "atr_at_open": round(self._atr_at_open, 1),
            "gap_strength": round(self._gap_strength, 3),
            "severity": self._severity_label,
            "initial_penalty_pct": round(self._initial_penalty * 100, 1),
            "current_penalty_pct": round(current_penalty * 100, 1),
            "multiplier": self.get_unified_penalty_multiplier(mins),
            "minutes_since_open": round(mins, 1),
        }
