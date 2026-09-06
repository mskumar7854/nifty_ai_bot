"""
============================================
⏳ TIME & PRICE DECAY AGENT — THETA PROTECTOR

Focuses exclusively on Options Premium Decay.
Answers:
- Is Theta burning too fast to hold?
- Did IV just crush, wiping out premium?
- Is there enough intrinsic value buffer?
- Should I take profits before weekend decay?
============================================
"""

from datetime import datetime, time, timedelta
import pandas as pd
from typing import Dict, List

from agents.base_agent import BaseAgent
from models import (
    AgentOutput, Direction, Strength, MarketSnapshot,
)
from utils.logger import get_logger
from config.settings import Settings


class DecayAgent(BaseAgent):
    """
    Evaluates option premium erosion.
    Acts primarily as a BLOCKER or EXIT TRIGGER.
    """

    def __init__(self, settings: Settings):
        super().__init__("decay", settings)
        self.th = settings.thresholds
        self.decay_log = get_logger("decay_agent")
        
        # State tracking
        self.last_iv = 0.0
        self.peak_iv_today = 0.0

    def analyze(
        self, df: pd.DataFrame, snapshot: MarketSnapshot
    ) -> AgentOutput:
        """
        Analyze time decay, IV crush, and premium erosion.
        """
        warnings = []
        details = {}
        now = datetime.now()

        # ⚠️ P1.2 Guard: Don't trade on fictional data
        from models import DataSource
        if snapshot.oi_data_source != DataSource.REAL and self.settings.system_mode.mode == "LIVE":
            return self._format_output(
                Direction.NEUTRAL, 0, Strength.WEAK,
                {"abstained": True, "reason": "no_real_oi_data"}, 
                ["Simulated OI data — agent abstaining"], "Abstained"
            )
        current_time = now.time()

        if snapshot.days_to_expiry > 5:
            # Theta decay is less of a concern far from expiry
            return self._format_output(
                Direction.NEUTRAL, 50, Strength.WEAK,
                {"status": "Far from expiry", "dte": snapshot.days_to_expiry}, 
                warnings, "DTE > 5"
            )

        # Update IV tracking
        if snapshot.atm_iv > self.peak_iv_today:
            self.peak_iv_today = snapshot.atm_iv
        
        # ── 1. IV CRUSH DETECTION ──
        iv_crush_score, iv_details, iv_warn = self._detect_iv_crush(snapshot)
        details.update(iv_details)
        warnings.extend(iv_warn)

        if iv_crush_score > 75:
            return self._format_output(
                Direction.NEUTRAL, min(30, 100 - iv_crush_score), Strength.MODERATE,
                details, warnings, "Blocked: IV Crush detected"
            )

        # ── 2. THETA BURN RATE ──
        theta_score, theta_details, theta_warn = self._analyze_theta_burn(snapshot, now)
        details.update(theta_details)
        warnings.extend(theta_warn)

        if theta_score > 80:
             return self._format_output(
                Direction.NEUTRAL, 20, Strength.STRONG,
                details, warnings, "Blocked: Massive Theta Burn"
            )

        # ── 3. WEEKEND DECAY RISK ──
        weekend_score, w_details, w_warn = self._check_weekend_decay(snapshot, now)
        details.update(w_details)
        warnings.extend(w_warn)

        if weekend_score > 85:
            return self._format_output(
                Direction.NEUTRAL, 15, Strength.STRONG,
                details, warnings, "Blocked: Weekend Theta Risk"
            )

        # Combine scores for general "decay risk"
        max_risk = max(iv_crush_score, theta_score, weekend_score)
        
        # If risk is low, we don't block. Decay agent doesn't give directional signals (mostly).
        confidence = 100 - max_risk  # Higher confidence = lower risk = safe to trade
        strength = Strength.STRONG if confidence > 80 else \
                   Strength.MODERATE if confidence > 50 else \
                   Strength.WEAK
                   
        verdict = f"Decay Risk: {max_risk}%"

        return self._format_output(
            Direction.NEUTRAL, confidence, strength,
            details, warnings, verdict
        )

    def _detect_iv_crush(
        self, snapshot: MarketSnapshot
    ) -> tuple[float, dict, list]:
        """
        Detects sudden drop in Implied Volatility (usually post-event/open).
        """
        details = {}
        warnings = []
        score = 0
        
        if self.peak_iv_today > 0 and snapshot.atm_iv > 0:
            iv_drop_pct = ((self.peak_iv_today - snapshot.atm_iv) / self.peak_iv_today) * 100
            
            details["iv_drop_pct"] = iv_drop_pct
            details["peak_iv"] = self.peak_iv_today
            details["current_iv"] = snapshot.atm_iv

            if iv_drop_pct > self.th.decay_iv_crush_threshold:
                score = 85
                warnings.append(f"💥 IV CRUSH: Volatility dropped by {iv_drop_pct:.1f}%")
            elif iv_drop_pct > (self.th.decay_iv_crush_threshold / 2):
                score = 50
                warnings.append(f"⚠️ IV dropping ({iv_drop_pct:.1f}%) — Options losing value")
                
        return score, details, warnings

    def _analyze_theta_burn(
        self, snapshot: MarketSnapshot, now: datetime
    ) -> tuple[float, dict, list]:
        """
        Analyzes how fast time value is decaying based on DTE and time of day.
        """
        details = {}
        warnings = []
        score = 0
        
        # Closer to expiry = faster burn
        # Afternoon = faster burn than morning usually (unless IV is propping it up)
        
        dte = snapshot.days_to_expiry
        details["dte"] = dte

        if dte <= self.th.decay_critical_dte:
            # 0 or 1 DTE
            score += 40
            
            # Accelerates in the afternoon
            if now.time() >= time(14, 0):
                score += 30
                warnings.append("⏱️ Critical Theta Burn (Late 0/1 DTE)")
        elif dte <= self.th.decay_acceleration_dte:
            # 2-3 DTE
            score += 20
        
        # Straddle decay gives a hint of the actual burn
        if snapshot.straddle_decay_pct > 20:
             score += (snapshot.straddle_decay_pct / 2) # max 50 points
             warnings.append(f"🕯️ Straddle decayed {snapshot.straddle_decay_pct:.1f}% today")

        details["theta_risk_score"] = min(100, score)
        return min(100, score), details, warnings

    def _check_weekend_decay(
        self, snapshot: MarketSnapshot, now: datetime
    ) -> tuple[float, dict, list]:
        """
        Friday afternoons carry outsized theta risk for holding overnight.
        """
        details = {}
        warnings = []
        score = 0

        # Friday is weekday 4
        if now.weekday() == 4 and now.time() >= time(14, 30):
            score = 90
            warnings.append("🛑 WEEKEND RISK: Holding options over the weekend guarantees theta loss.")
            details["weekend_hold_risk"] = "EXTREME"
            
        return score, details, warnings

    def _format_output(
        self, direction: Direction, conf: float, strength: Strength,
        details: dict, warnings: list, verdict: str
    ) -> AgentOutput:
        details["verdict"] = verdict
        return AgentOutput(
            agent_name=self.name,
            timestamp=datetime.now(),
            direction=direction,
            confidence=round(conf, 1),
            strength=strength,
            details=details,
            warnings=warnings,
        )
