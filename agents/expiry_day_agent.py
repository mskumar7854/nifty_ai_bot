"""
============================================
🎯 EXPIRY DAY AGENT — ZERO-DTE SPECIALIST

Takes over decision-making on expiry days.
Focuses on:
- Gamma explosions (1:30 PM - 3:00 PM)
- Pin risk (Max Pain gravity)
- Straddle premium crush
- OI concentration levels
- First/last 15 min traps
============================================
"""

from datetime import datetime, time
import numpy as np
import pandas as pd
from typing import Dict, List, Optional

from agents.base_agent import BaseAgent
from models import (
    AgentOutput, Direction, Strength, MarketSnapshot,
)
from utils.logger import get_logger
from config.settings import Settings


class ExpiryDayAgent(BaseAgent):
    """
    Specialized agent that overrides normal logic on Expiry Days.
    On non-expiry days, it remains neutral.
    """

    def __init__(self, settings: Settings):
        super().__init__("expiry_day", settings)
        self.th = settings.thresholds
        self.expiry_log = get_logger("expiry_agent")
        
        # State tracking for the day
        self.morning_high = 0.0
        self.morning_low = float('inf')
        self.straddle_peak = 0.0
        
        # Determine last hour start time
        hour, minute = map(int, self.th.expiry_last_hour_start.split(':'))
        self.last_hour_start = time(hour, minute)

    def analyze(
        self, df: pd.DataFrame, snapshot: MarketSnapshot
    ) -> AgentOutput:
        """
        Analyze specific zero-DTE mechanics.
        """
        warnings = []
        details = {}
        now = datetime.now()
        current_time = now.time()

        # ⚠️ P1.2 Guard: Don't trade on fictional data
        from models import DataSource
        if snapshot.oi_data_source != DataSource.REAL and self.settings.system_mode.mode == "LIVE":
            return self._format_output(
                Direction.NEUTRAL, 0, Strength.WEAK,
                {"abstained": True, "reason": "no_real_oi_data"}, 
                ["Simulated OI data — agent abstaining"], "Abstained"
            )

        # ── 1. EXPIRY DAY CHECK ──
        if not snapshot.is_expiry_day:
            return AgentOutput(
                agent_name=self.name,
                timestamp=now,
                direction=Direction.NEUTRAL,
                confidence=50,
                strength=Strength.WEAK,
                details={"status": "Not an expiry day"},
            )

        details["expiry_type"] = snapshot.expiry_type

        # ── 2. TIME-BASED TRAPS (BLOCKERS) ──
        # Avoid first 15 mins (wild swings)
        market_open = time(9, 15)
        open_dt = datetime.combine(now.date(), market_open)
        mins_from_open = (now - open_dt).total_seconds() / 60

        if mins_from_open < self.th.expiry_avoid_first_minutes:
            warnings.append("🚫 Expiry Trap: First 15 min volatility")
            return self._format_output(
                Direction.NEUTRAL, 10, Strength.WEAK,
                details, warnings, "Blocked: Opening volatility"
            )

        # Avoid last 5 mins (auto-square off traps)
        market_close = time(15, 40)
        close_dt = datetime.combine(now.date(), market_close)
        mins_to_close = (close_dt - now).total_seconds() / 60
        snapshot.minutes_to_close = max(0, int(mins_to_close))

        if mins_to_close < self.th.expiry_avoid_last_minutes:
            warnings.append("🚫 Expiry Trap: Auto-square off zone")
            return self._format_output(
                Direction.NEUTRAL, 10, Strength.WEAK,
                details, warnings, "Blocked: Closing volatility"
            )

        # ── Update tracking ──
        self.morning_high = max(self.morning_high, snapshot.price)
        self.morning_low = min(self.morning_low, snapshot.price)
        if snapshot.atm_straddle_price > self.straddle_peak:
            self.straddle_peak = snapshot.atm_straddle_price

        # ── 3. GAMMA BLAST ZONE (1:30 PM+) ──
        in_gamma_window = current_time >= self.last_hour_start
        details["in_gamma_window"] = in_gamma_window

        if in_gamma_window:
            gamma_score, gamma_dir, g_details, g_warn = \
                self._analyze_gamma_blast(snapshot, mins_to_close)
            
            details.update(g_details)
            warnings.extend(g_warn)
            
            if gamma_score > 70:
                # Gamma overrides everything else
                return self._format_output(
                    gamma_dir, gamma_score, Strength.STRONG,
                    details, warnings, f"🚀 GAMMA BLAST: {gamma_dir.value}"
                )

        # ── 4. PREMIUM CRUSH (THETA DECAY) ──
        # Between 10:30 and 1:30, it's usually premium decay
        crush_score, c_details, c_warn = self._analyze_premium_crush(
            snapshot, current_time
        )
        details.update(c_details)
        warnings.extend(c_warn)

        if crush_score > 75:
            # Dangerous to buy options right now
            warnings.append("⚠️ SEVERE PREMIUM CRUSH ZONE — AVOID BUYING")
            return self._format_output(
                Direction.NEUTRAL, min(30, 100 - crush_score), Strength.WEAK,
                details, warnings, "Blocked: Premium Crush"
            )

        # ── 5. PIN RISK (MAX PAIN / HIGHEST OI) ──
        pin_score, pin_dir, p_details = self._analyze_pin_risk(snapshot)
        details.update(p_details)

        # ── FINAL COMBINATION ──
        # If we reach here, it's a normal expiry day trade
        # but influenced by pin risk
        
        direction = pin_dir
        confidence = pin_score
        
        strength = Strength.STRONG if confidence >= 70 \
            else Strength.MODERATE if confidence >= 50 \
            else Strength.WEAK
            
        verdict = f"Pin Risk tracking {direction.value}" if confidence > 50 else "Neutral expiry chop"

        return self._format_output(
            direction, confidence, strength, details, warnings, verdict
        )

    def _analyze_gamma_blast(
        self, snapshot: MarketSnapshot, mins_to_close: float
    ) -> tuple[float, Direction, dict, list]:
        """
        Looks for late-day breakouts that trigger short covering
        (Gamma Explosion).
        """
        details = {}
        warnings = []
        score = 50
        direction = Direction.NEUTRAL

        # Need high momentum and breaking of morning ranges
        range_break_up = snapshot.price > self.morning_high
        range_break_down = snapshot.price < self.morning_low
        
        # Require VWAP alignment
        price_above_vwap = snapshot.price > snapshot.vwap
        
        # Check OI thresholds
        ce_trapped = snapshot.price > snapshot.max_ce_oi_strike and snapshot.max_ce_oi_strike > 0
        pe_trapped = snapshot.price < snapshot.max_pe_oi_strike and snapshot.max_pe_oi_strike > 0

        details["gamma_conditions"] = {
            "range_break_up": range_break_up,
            "range_break_down": range_break_down,
            "ce_writers_trapped": ce_trapped,
            "pe_writers_trapped": pe_trapped,
        }

        if range_break_up and price_above_vwap and ce_trapped:
            score = 85
            direction = Direction.BULLISH
            warnings.append("💥 SHORT COVERING: Call writers trapped!")
            
        elif range_break_down and not price_above_vwap and pe_trapped:
            score = 85
            direction = Direction.BEARISH
            warnings.append("💥 LONG UNWINDING: Put writers trapped!")
        
        # Adjust for time left (closer to 3:00 PM = stronger gamma)
        if mins_to_close < 30 and score > 50:
            score = min(95, score + 10)
            details["time_multiplier"] = "Extreme Gamma"
            
        return score, direction, details, warnings

    def _analyze_premium_crush(
        self, snapshot: MarketSnapshot, current_time: time
    ) -> tuple[float, dict, list]:
        """
        Detects if option premiums are melting rapidly without index movement.
        """
        details = {}
        warnings = []
        crush_score = 0

        # Typically happens mid-day
        if time(10, 30) <= current_time <= time(13, 30):
            # Calculate straddle decay
            if self.straddle_peak > 0:
                decay_from_peak = ((self.straddle_peak - snapshot.atm_straddle_price) / self.straddle_peak) * 100
                details["straddle_decay_from_peak"] = f"{decay_from_peak:.1f}%"
                
                if decay_from_peak > self.th.expiry_premium_crush_threshold:
                    crush_score = 80
                    warnings.append(f"📉 Option premiums crushed {decay_from_peak:.1f}%")

            # Check ATR / volatility
            if snapshot.atr < 20: # Arbitrary threshold, should be dynamic or config
                crush_score += 10
                warnings.append("📉 Low ATR: Pure theta decay regime")

        details["premium_crush_score"] = crush_score
        return crush_score, details, warnings

    def _analyze_pin_risk(
        self, snapshot: MarketSnapshot
    ) -> tuple[float, Direction, dict]:
        """
        Analyzes the "gravity" of high OI strikes pulling the price toward them.
        """
        details = {}
        score = 50
        direction = Direction.NEUTRAL

        if snapshot.max_ce_oi_strike == 0 or snapshot.max_pe_oi_strike == 0:
            return score, direction, {"pin_risk": "No OI data"}

        # Find nearest major OI strike (Max Pain proxy)
        dist_to_ce = abs(snapshot.price - snapshot.max_ce_oi_strike)
        dist_to_pe = abs(snapshot.price - snapshot.max_pe_oi_strike)

        nearest_strike = 0
        dist_to_nearest = float('inf')
        
        if dist_to_ce < dist_to_pe:
            nearest_strike = snapshot.max_ce_oi_strike
            dist_to_nearest = dist_to_ce
        else:
            nearest_strike = snapshot.max_pe_oi_strike
            dist_to_nearest = dist_to_pe

        details["nearest_heavy_oi_strike"] = nearest_strike
        details["dist_to_strike"] = dist_to_nearest

        # If price is drifting within the "gravity radius" of a major strike
        if dist_to_nearest < self.th.expiry_max_pain_gravity_radius:
            score = 65 + (self.th.expiry_max_pain_gravity_radius - dist_to_nearest) / self.th.expiry_max_pain_gravity_radius * 15
            
            if snapshot.price < nearest_strike:
                direction = Direction.BULLISH # Pinning UP to strike
                details["pin_action"] = "Pulling UP to nearest strike"
            else:
                direction = Direction.BEARISH # Pinning DOWN to strike
                details["pin_action"] = "Pulling DOWN to nearest strike"

        return score, direction, details

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
