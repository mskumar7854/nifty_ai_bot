"""
============================================
🕐 TIME & SESSION AGENT
Why: Market behaves DIFFERENTLY at different times.
     Opening = volatile, Lunch = dead, Power hour = trending.
     This prevents entering at wrong times.
============================================
"""

import pandas as pd
import pytz
from datetime import datetime, time, timedelta

from agents.base_agent import BaseAgent, AgentCategory
from models.signals import (
    AgentOutput, Direction, Strength, MarketSnapshot, SessionPhase
)
from config.settings import Settings


class TimeSessionAgent(BaseAgent):
    """
    KEY INSIGHT:
    - First 15 min: Wild swings, traps everywhere → avoid or reduce size
    - 9:30-12:00: Best trending moves → full size
    - 12:00-13:30: Low volume lunch → avoid
    - 14:00-15:00: Power hour, institutions act → great signals
    - Last 10 min: Expiry-related chaos → avoid

    This agent doesn't give direction — it gives PERMISSION.
    High confidence = "safe time to trade"
    Low confidence = "bad time, sit out"
    """

    def __init__(self, settings: Settings):
        super().__init__("time_session", settings, AgentCategory.FILTER)
        self.th = settings.thresholds

    def analyze(self, df: pd.DataFrame, snapshot: MarketSnapshot) -> AgentOutput:
        warnings = []
        details = {}

        ist = pytz.timezone('Asia/Kolkata')
        now = datetime.now(ist)
        print("Current Time:", now)
        current_time = now.time()
        weekday = now.strftime("%A")

        # ── 1. DETERMINE SESSION PHASE ──
        phase = self._get_session_phase(current_time)
        details["session_phase"] = phase.value
        details["weekday"] = weekday

        # ── 2. SCORE EACH PHASE ──
        phase_scores = {
            SessionPhase.PRE_MARKET: 0,
            SessionPhase.OPENING: 35,
            SessionPhase.MORNING: 85,
            SessionPhase.LUNCH: 25,
            SessionPhase.AFTERNOON: 75,
            SessionPhase.POWER_HOUR: 90,
            SessionPhase.CLOSING: 30,
            SessionPhase.AFTER_HOURS: 0,
        }

        base_score = phase_scores.get(phase, 50)

        # ── 3. SPECIFIC TIME DANGERS ──
        market_open = time(9, 15)
        market_close = time(15, 30)

        # First N minutes — avoid
        minutes_since_open = 0
        if current_time >= market_open:
            open_dt = now.replace(hour=9, minute=15, second=0)
            minutes_since_open = (now - open_dt).total_seconds() / 60

        if minutes_since_open < self.th.avoid_first_minutes:
            base_score = 10
            warnings.append(f"⏰ First {self.th.avoid_first_minutes} min — wild volatility, avoid")
            details["first_minutes"] = True

        # Last N minutes — avoid
        if current_time >= market_close:
            base_score = 0
        elif current_time >= time(15, 20):
            base_score = 15
            warnings.append("⏰ Last 10 minutes — avoid new entries")
            details["closing_minutes"] = True

        # ── 4. OPENING RANGE PERIOD ──
        if minutes_since_open <= self.th.opening_range_minutes:
            details["opening_range"] = True
            details["or_minutes_remaining"] = max(
                0, self.th.opening_range_minutes - minutes_since_open
            )
            if minutes_since_open > self.th.avoid_first_minutes:
                base_score = 60  # OK but reduced
                warnings.append("Opening range forming — be cautious")

        # ── 5. LUNCH ZONE ──
        lunch_start = time(12, 0)
        lunch_end = time(13, 30)
        if lunch_start <= current_time <= lunch_end:
            lunch_config = self.settings.session_strategy.sessions.get("lunch_dead", {})
            if not lunch_config.get("trade", False):
                base_score = 15  # Block it
                warnings.append("🍽️ Lunch session — low volume, avoid")
            else:
                base_score = 80  # Temporary testing
                warnings.append("🍽️ Lunch session — testing override enabled")
            details["lunch_zone"] = True

        # ── 6. EXPIRY DAY ADJUSTMENTS ──
        if snapshot.is_expiry_day:
            details["expiry_day"] = True
            if phase in (SessionPhase.AFTERNOON, SessionPhase.POWER_HOUR):
                base_score = min(base_score, 50)
                warnings.append("📅 Expiry day — gamma risk in afternoon")
            if minutes_since_open < 30:
                warnings.append("📅 Expiry open — extreme volatility possible")

        # ── 7. MONDAY/FRIDAY ADJUSTMENTS ──
        if weekday == "Monday":
            base_score *= 0.9
            details["monday_factor"] = True
            if minutes_since_open < 30:
                warnings.append("Monday morning — gap risk, wait for direction")

        if weekday == "Friday":
            if current_time >= time(14, 0):
                base_score *= 0.8
                warnings.append("Friday afternoon — weekend risk, reduce exposure")

        # ── 8. TIME QUALITY SCORE ──
        confidence = max(0, min(100, base_score))

        if confidence < 20:
            return self._blocker_output(f"Bad time to trade: {phase.value}")

        if confidence >= 70:
            strength = Strength.STRONG
            details["verdict"] = "✅ GOOD time to trade"
        elif confidence >= 40:
            strength = Strength.MODERATE
            details["verdict"] = "⚠️ OK but reduced confidence"
        else:
            strength = Strength.WEAK
            details["verdict"] = "❌ Poor time — consider skipping"

        return AgentOutput(
            agent_name=self.name,
            timestamp=now,
            direction=Direction.NEUTRAL,
            confidence=round(confidence, 1),
            strength=strength,
            details=details,
            warnings=warnings,
        )

    def _get_session_phase(self, t: time) -> SessionPhase:
        if t < time(9, 0):
            return SessionPhase.PRE_MARKET
        elif t < time(9, 30):
            return SessionPhase.OPENING
        elif t < time(12, 0):
            return SessionPhase.MORNING
        elif t < time(13, 30):
            return SessionPhase.LUNCH
        elif t < time(14, 0):
            return SessionPhase.AFTERNOON
        elif t < time(15, 15):
            return SessionPhase.POWER_HOUR
        elif t < time(15, 30):
            return SessionPhase.CLOSING
        else:
            return SessionPhase.AFTER_HOURS
