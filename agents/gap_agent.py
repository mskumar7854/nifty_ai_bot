"""
============================================================
🫧 GAP AGENT  (v2 — ATR-Normalised)

Why: "Gaps are meant to be filled."
     Runaway gaps vs Exhaustion gaps.

v2 Changes (Priority 4 Fix):
  OLD: fixed gap_significant_points = 30pts hardcoded.
       A 60pt gap at ATR=280 treated same as ATR=90.
       That is wrong — severity must be context-relative.

  NEW: gap_strength = abs(gap) / ATR
       Calibrated thresholds:
         gap_strength < 0.15 → insignificant (SKIP)
         gap_strength 0.15–0.40 → normal (low signal weight)
         gap_strength 0.40–0.70 → notable
         gap_strength > 0.70 → strong gap event

  Context table:
    Gap  ATR   gap_strength  Category
    ─────────────────────────────────
    60   280   0.21          Minor
    60   90    0.67          Significant
    120  280   0.43          Notable
    200  280   0.71          Major
============================================================
"""

import pandas as pd
from datetime import datetime

from agents.base_agent import BaseAgent, AgentCategory
from models import AgentOutput, Direction, Strength, MarketSnapshot
from config.settings import Settings


# Minimum normalised gap strength to consider a gap significant
_MIN_GAP_STRENGTH = 0.15


class GapAgent(BaseAgent):
    """
    Identifies morning gaps using ATR-normalised severity.

    Signals:
      - Gap Up + fading  → BEARISH (targeting fill)
      - Gap Up + holding → BULLISH (gap and go)
      - Gap Down + recovering → BULLISH (targeting fill)
      - Gap Down + holding  → BEARISH (gap and go)
      - Gap filled          → NEUTRAL
    """

    def __init__(self, settings: Settings):
        super().__init__("gap", settings, AgentCategory.FILTER)
        self.th = settings.thresholds

    def analyze(self, df: pd.DataFrame, snapshot: MarketSnapshot) -> AgentOutput:
        warnings = []
        details = {}

        if len(df) < 5:
            return self._neutral_output()

        price = snapshot.price
        prev_close = snapshot.prev_day_close

        if prev_close == 0:
            prev_close = df['close'].iloc[-2]  # fallback

        day_open = snapshot.day_open if snapshot.day_open > 0 else df['open'].iloc[-1]
        atr = snapshot.atr if snapshot.atr > 0 else 100.0

        gap = day_open - prev_close
        abs_gap = abs(gap)

        # ── ATR-normalised severity ──
        gap_strength = abs_gap / atr
        details["gap_pts"] = f"{gap:+.1f}"
        details["atr"] = f"{atr:.1f}"
        details["gap_strength"] = round(gap_strength, 3)

        if gap_strength < _MIN_GAP_STRENGTH:
            details["gap_verdict"] = "Insignificant (gap_strength < 0.15)"
            return self._neutral_output("No significant gap relative to ATR")

        # Severity label (informational — penalty is handled by GapPenaltyManager)
        if gap_strength < 0.40:
            severity = "MINOR"
        elif gap_strength < 0.70:
            severity = "NOTABLE"
        else:
            severity = "MAJOR"
        details["gap_severity"] = severity

        # ── Gap direction analysis ──
        direction = Direction.NEUTRAL
        score = 50

        if gap > 0:
            details["gap_type"] = "Gap Up"
            if price < day_open:  # fading the gap
                direction = Direction.BEARISH
                score = 65 + int(gap_strength * 20)  # scale with severity
                details["action"] = "Fading Gap Up (Targeting Fill)"
            else:
                direction = Direction.BULLISH
                score = 60 + int(gap_strength * 15)
                details["action"] = "Gap and Go (Strength)"

        elif gap < 0:
            details["gap_type"] = "Gap Down"
            if price > day_open:  # recovering
                direction = Direction.BULLISH
                score = 65 + int(gap_strength * 20)
                details["action"] = "Fading Gap Down (Targeting Fill)"
            else:
                direction = Direction.BEARISH
                score = 60 + int(gap_strength * 15)
                details["action"] = "Gap and Go (Weakness)"

        # Cap score at 90
        score = min(score, 90)

        # ── Gap fill check ──
        if (gap > 0 and price <= prev_close) or (gap < 0 and price >= prev_close):
            details["gap_status"] = "FILLED"
            direction = Direction.NEUTRAL
            score = 30
            warnings.append("Gap has been filled. Look for bounce/rejection structure.")
        else:
            fill_pct = (abs(price - day_open) / abs_gap * 100) if abs_gap > 0 else 0
            details["gap_status"] = f"UNFILLED ({fill_pct:.0f}% closed)"

        strength = Strength.STRONG if score >= 75 else (
            Strength.MODERATE if score >= 55 else Strength.WEAK
        )

        return AgentOutput(
            agent_name=self.name,
            timestamp=datetime.now(),
            direction=direction,
            confidence=score,
            strength=strength,
            details=details,
            warnings=warnings,
        )
