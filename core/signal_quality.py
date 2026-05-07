"""
============================================
SIGNAL QUALITY GRADER v3 (Dominance-Aware)

Why: The old v2 grader used raw confidence
     thresholds (85%, 75%) that are IMPOSSIBLE
     to reach after regime scaling (~0.70x).
     This version grades on relative edge
     quality, not absolute probability.

Grading factors:
  1. Confluence ratio       (max 25 pts)
  2. Risk/Reward ratio      (max 20 pts)
  3. Dominance percentage   (max 25 pts)  ← NEW
  4. Directional alignment  (max 15 pts)  ← NEW
  5. Regime alignment       (max 15 pts)
  - Penalty: excessive warnings
============================================
"""

from models.signals import Signal, SignalGrade, Direction, MarketRegime
from config.settings import Settings


class SignalQualityGrader:
    """
    Grades a signal from A+ down to D based on:
    - Confluence ratio  (how many agents agree)
    - Risk/Reward       (is the math favorable)
    - Dominance         (how decisive is the edge)
    - Alignment         (do directional agents agree)
    - Regime            (is the market helping or hurting)
    """

    def __init__(self, settings: Settings):
        self.settings = settings

    def grade(self, signal: Signal) -> SignalGrade:
        score = 0

        # ── 1. Confluence Ratio (max 25) ──
        # How many agents are voting in the same direction?
        conf_ratio = signal.confluence.confluence_ratio if signal.confluence else 0
        if conf_ratio >= 0.85:
            score += 25
        elif conf_ratio >= 0.70:
            score += 20
        elif conf_ratio >= 0.55:
            score += 12
        elif conf_ratio >= 0.40:
            score += 6

        # ── 2. Risk/Reward (max 20) ──
        rr = signal.risk_reward_ratio
        if rr >= 3.0:
            score += 20
        elif rr >= 2.0:
            score += 15
        elif rr >= 1.5:
            score += 10
        elif rr >= 1.0:
            score += 5

        # ── 3. Dominance Percentage (max 25) ── NEW
        # How decisive is the dominant direction?
        # Dominance = |buy - sell| / (buy + sell) * 100
        # 100% = one-sided (very strong), 0% = split (garbage)
        meta = getattr(signal, "metadata", {}) or {}
        dominance_pct = meta.get("dominance_pct", 0)
        if dominance_pct >= 30:
            score += 25
        elif dominance_pct >= 20:
            score += 20
        elif dominance_pct >= 12:
            score += 12
        elif dominance_pct >= 6:
            score += 6

        # ── 4. Directional Alignment (max 15) ── NEW
        # Are the directional agents cleanly aligned?
        alignment = meta.get("directional_alignment", False)
        if alignment:
            score += 15
        else:
            # Partial credit if gap is strong enough
            gap = meta.get("dominance_gap", 0)
            if gap >= 0.08:
                score += 8
            elif gap >= 0.05:
                score += 4

        # ── 5. Regime Alignment (max 15) ──
        if signal.regime in [MarketRegime.TRENDING_UP, MarketRegime.TRENDING_DOWN, MarketRegime.BREAKOUT]:
            score += 15
        elif signal.regime == MarketRegime.SQUEEZE:
            score += 8  # squeeze can break either way — partial credit
        # RANGING/VOLATILE = 0 points (headwind, not aligned)

        # ── Penalties ──
        # Excessive warnings reduce quality
        if len(signal.warnings) > 3:
            score -= (len(signal.warnings) - 3) * 5

        # Gap day with no confirmation is risky
        if meta.get("gap_detected", False) and not alignment:
            score -= 5

        # Clamp to 0
        score = max(0, score)

        # ── Assign Grade ──
        # A+: 90+ with alignment — elite
        # A:  75+ — strong setup
        # B+: 60+ — acceptable in trending regime
        # B:  45+ — marginal
        # C:  below 45 — too weak
        if score >= 90 and alignment:
            return SignalGrade.A_PLUS
        elif score >= 75:
            return SignalGrade.A
        elif score >= 60:
            return SignalGrade.B_PLUS if hasattr(SignalGrade, "B_PLUS") else SignalGrade.A
        elif score >= 45:
            return SignalGrade.B
        elif score >= 30:
            return SignalGrade.C
        else:
            return SignalGrade.D
