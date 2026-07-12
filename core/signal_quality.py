"""
============================================
SIGNAL QUALITY GRADER v3.1 (Probability-Gated)

Why: The old v3 grader was driven purely by
     confluence/dominance/alignment — it could
     produce A+ with probability=0.36, which is
     a grading calibration bug.

Fix: Probability score now acts as a HARD CEILING
     on the achievable grade.  No matter how good
     the confluence/alignment, a weak probability
     score caps the max grade:

       prob >= 0.48  → no cap (let score decide)
       prob >= 0.38  → max grade = B+
       prob >= 0.30  → max grade = B
       prob  < 0.30  → max grade = C

Grading factors:
  1. Confluence ratio       (max 25 pts)
  2. Risk/Reward ratio      (max 20 pts)
  3. Dominance percentage   (max 25 pts)
  4. Directional alignment  (max 15 pts)
  5. Regime alignment       (max 15 pts)
  - Penalty: excessive warnings, gap day w/o alignment
============================================
"""

from models import Signal, SignalGrade, Direction, MarketRegime
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

        # ── Raw Grade from score ──
        # A+: 90+ with alignment — elite
        # A:  75+ — strong setup
        # B+: 60+ — acceptable in trending regime
        # B:  45+ — marginal
        # C:  below 45 — too weak
        if score >= 90 and alignment:
            raw_grade = SignalGrade.A_PLUS
        elif score >= 75:
            raw_grade = SignalGrade.A
        elif score >= 60:
            raw_grade = SignalGrade.B_PLUS if hasattr(SignalGrade, "B_PLUS") else SignalGrade.A
        elif score >= 45:
            raw_grade = SignalGrade.B
        elif score >= 30:
            raw_grade = SignalGrade.C
        else:
            raw_grade = SignalGrade.D

        # ── Probability Gate: Hard ceiling on grade ──
        # Even if confluence/alignment is perfect, a weak probability score
        # means the EDGE is not there.  Cap the grade accordingly.
        #
        # The dominant probability is read from signal metadata so this grader
        # works with the full post-penalty, post-sigmoid probability score that
        # compute_weighted_score() already produced.
        #
        # CALIBRATION NOTE (2026-05-11): Thresholds lowered for live data.
        # Simulated data produced dominant_prob in 0.50-0.70 range.
        # Live post-penalty, post-sigmoid probs concentrate in 0.38-0.50.
        # Old thresholds capped every live signal at B, making B+ unreachable.
        dominant_prob = meta.get("dominant_prob", 1.0)  # 1.0 = no data → no cap

        # Grade ordering for cap comparison
        _GRADE_ORDER = {
            SignalGrade.A_PLUS: 5,
            SignalGrade.A: 4,
        }
        if hasattr(SignalGrade, "B_PLUS"):
            _GRADE_ORDER[SignalGrade.B_PLUS] = 3
        _GRADE_ORDER[SignalGrade.B] = 2
        _GRADE_ORDER[SignalGrade.C] = 1
        _GRADE_ORDER[SignalGrade.D] = 0

        def _apply_prob_cap(grade, cap_grade):
            """Return the lower of grade and cap_grade."""
            if _GRADE_ORDER.get(grade, 0) > _GRADE_ORDER.get(cap_grade, 0):
                return cap_grade
            return grade

        if dominant_prob < 0.30:
            # Probability too low — cap at C
            final_grade = _apply_prob_cap(raw_grade, SignalGrade.C)
        elif dominant_prob < 0.38:
            # Weak probability — cap at B
            final_grade = _apply_prob_cap(raw_grade, SignalGrade.B)
        elif dominant_prob < 0.48:
            # Below mid-strength — cap at B+
            cap = SignalGrade.B_PLUS if hasattr(SignalGrade, "B_PLUS") else SignalGrade.B
            final_grade = _apply_prob_cap(raw_grade, cap)
        else:
            # Probability strong enough — no cap
            final_grade = raw_grade

        return final_grade
