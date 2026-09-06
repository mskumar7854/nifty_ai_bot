"""
============================================
📦 OPTIONS INTELLIGENCE AGENT (v3)
Tracks: Multi-Strike OI, Walls, Migration, 
        Absorption, Traps, and Expiry phases
============================================
"""

import pandas as pd
from datetime import datetime, timedelta
import numpy as np
from typing import Optional

from agents.base_agent import BaseAgent
from models import AgentOutput, Direction, Strength, MarketSnapshot, DataSource
from models.oi_analysis import (
    OIAnalysis, StrikeZone, MarketStructureAnalysis
)
from config.settings import Settings


class OIAgent(BaseAgent):
    """
    Market Structure Intelligence Layer.
    Analyzes multi-strike Option Chain data to detect institutional
    positioning, wall migration, OI traps, and pressure gradients.
    """

    def __init__(self, settings: Settings):
        super().__init__("oi", settings)
        self.th = settings.thresholds
        
        # State memory for migration analysis (list of MarketSnapshot dicts + our analysis)
        self._history = []
        
        # We need a stable identifier to know if we are processing a new snapshot
        self._last_processed_timestamp = None

    def analyze(self, df: pd.DataFrame, snapshot: MarketSnapshot) -> AgentOutput:
        """Core analysis pipeline."""
        warnings = []
        details = {}
        explanation = []

        # ── 1. GUARDS ──
        if snapshot.oi_data_source != DataSource.REAL and self.settings.system_mode.mode == "LIVE":
            return AgentOutput(
                agent_name=self.name, timestamp=datetime.now(),
                direction=Direction.NEUTRAL, confidence=0, strength=Strength.WEAK,
                warnings=["Simulated OI data — agent abstaining"],
                details={"abstained": True, "reason": "no_real_oi_data"}
            )

        chain = snapshot.oi_chain_data
        if not chain:
            return AgentOutput(
                agent_name=self.name, timestamp=datetime.now(),
                direction=Direction.NEUTRAL, confidence=0, strength=Strength.WEAK,
                warnings=["Empty option chain"],
                details={"abstained": True, "reason": "empty_chain"}
            )

        # Ensure we don't process the same snapshot twice if the orchestrator loops fast
        if self._last_processed_timestamp == snapshot.timestamp:
            # We already processed this. Return neutral or cached? 
            # The engine expects fresh scores. We will re-evaluate but maybe use cache in a real HFT.
            pass
        self._last_processed_timestamp = snapshot.timestamp

        # ── 2. CONTEXT ──
        spot = snapshot.oi_spot_price if snapshot.oi_spot_price > 0 else snapshot.price
        vix = snapshot.india_vix
        regime = snapshot.regime_state.get("regime", "RANGING")
        
        atm_strike = self._get_atm_strike(chain, spot)
        radius = self._get_strike_radius(vix)
        nearby_chain = self._filter_chain(chain, atm_strike, radius)

        # Freshness
        data_age_sec = (datetime.now().timestamp() - snapshot.timestamp.timestamp())
        if hasattr(snapshot, "age_sec"): # if data_manager injected it
            data_age_sec = getattr(snapshot, "age_sec", data_age_sec)
            
        freshness_mult = self._freshness_multiplier(data_age_sec)
        
        # Expiry Phase
        expiry_phase, expiry_mult = self._detect_expiry_phase(
            snapshot.days_to_expiry, snapshot.is_expiry_day, snapshot.minutes_to_close
        )

        # ── 3. PER-STRIKE ANALYSIS & ZONES ──
        # Detect Resistance and Support zones
        res_zone = self._detect_zone(nearby_chain, "CE", self.th.oi_wall_zone_threshold_pct, self.th.oi_wall_zone_adjacent_ratio)
        sup_zone = self._detect_zone(nearby_chain, "PE", self.th.oi_wall_zone_threshold_pct, self.th.oi_wall_zone_adjacent_ratio)

        # Compute Pressure Gradient
        pressure_above, pressure_below = self._compute_pressure_gradient(nearby_chain, spot)
        pressure_ratio = pressure_above / max(pressure_below, 1)

        # Near-ATM PCR
        near_atm_chain = self._filter_chain(chain, atm_strike, 5)
        near_pcr = self._compute_pcr(near_atm_chain)

        # ── 4. TACTICAL (MIGRATION & TRAPS) ──
        migration_dir, migration_vel = self._analyze_migration(res_zone, sup_zone)
        
        wall_absorption = False
        wall_break = False
        wall_break_dir = "NONE"
        if res_zone and sup_zone:
            wall_absorption, wall_break, wall_break_dir = self._analyze_walls(
                spot, res_zone, sup_zone, nearby_chain
            )

        trap_detected, trap_type = self._detect_oi_trap(spot, nearby_chain)
        
        flip_detected, flip_side = self._detect_flip(nearby_chain)

        # Update History
        self._update_history(snapshot, nearby_chain, res_zone, sup_zone, near_pcr)

        # ── 5. SCORING ENGINE ──
        # Structural Score (0-100 Bullish or Bearish)
        struct_score, struct_dir = self._compute_structural_score(
            res_zone, sup_zone, spot, pressure_ratio
        )
        
        # Tactical Score (0-100 Bullish or Bearish)
        tact_score, tact_dir = self._compute_tactical_score(
            migration_dir, migration_vel, flip_detected, flip_side,
            wall_absorption, wall_break, wall_break_dir, trap_detected, trap_type, near_pcr
        )

        # Blend using regime weights
        struct_wt, tact_wt = self._get_regime_weights(regime)
        
        # Convert to signed pressure (-100 to +100)
        s_sign = 1 if struct_dir == Direction.BULLISH else (-1 if struct_dir == Direction.BEARISH else 0)
        t_sign = 1 if tact_dir == Direction.BULLISH else (-1 if tact_dir == Direction.BEARISH else 0)
        
        raw_pressure = (struct_score * s_sign * struct_wt) + (tact_score * t_sign * tact_wt)
        pressure_score = raw_pressure * expiry_mult * freshness_mult

        # Reliability & Conviction
        data_qual = "LIVE" if freshness_mult > 0.8 else "STALE"
        if snapshot.oi_data_source == DataSource.SIMULATED:
            data_qual = "SIMULATED"

        reliability = self._compute_reliability(
            freshness_mult, expiry_mult, len(self._history), data_qual
        )
        
        conviction = self._compute_conviction(
            struct_dir, tact_dir, migration_dir, wall_break_dir, trap_type
        )

        # ── 6. EXPLAINABILITY & ATTRIBUTION ──
        explanation = self._build_explanation(
            res_zone, sup_zone, migration_dir, migration_vel,
            wall_break, wall_break_dir, wall_absorption, trap_detected, trap_type,
            flip_detected, flip_side, freshness_mult, data_age_sec, expiry_mult, expiry_phase
        )
        
        feature_attribution = {
            "Structure": round(struct_score * s_sign * struct_wt * freshness_mult * expiry_mult, 1),
            "Tactical": round(tact_score * t_sign * tact_wt * freshness_mult * expiry_mult, 1),
            "Freshness_Penalty": round(raw_pressure * expiry_mult * (freshness_mult - 1.0), 1) if freshness_mult < 1.0 else 0.0,
            "Expiry_Penalty": round(raw_pressure * (expiry_mult - 1.0), 1) if expiry_mult < 1.0 else 0.0,
        }

        # ── 7. OUTPUT GENERATION ──
        final_dir = Direction.BULLISH if pressure_score > 0 else (Direction.BEARISH if pressure_score < 0 else Direction.NEUTRAL)
        
        # Effective confidence incorporates reliability and conviction
        effective_confidence = abs(pressure_score) * (reliability / 100.0) * (conviction / 100.0)
        
        if effective_confidence >= self.th.oi_pressure_strong:
            strength = Strength.STRONG
        elif effective_confidence >= self.th.oi_pressure_moderate:
            strength = Strength.MODERATE
        else:
            strength = Strength.WEAK

        # Build OIAnalysis
        oi_analysis = OIAnalysis(
            pressure_score=round(pressure_score, 1),
            reliability_score=round(reliability, 1),
            conviction=round(conviction, 1),
            support_zone=sup_zone,
            resistance_zone=res_zone,
            migration_direction=migration_dir,
            migration_velocity=round(migration_vel, 2),
            flip_detected=flip_detected,
            flip_side=flip_side,
            wall_absorption=wall_absorption,
            wall_break=wall_break,
            wall_break_direction=wall_break_dir,
            trap_detected=trap_detected,
            trap_type=trap_type,
            pressure_above=pressure_above,
            pressure_below=pressure_below,
            pressure_ratio=round(pressure_ratio, 2),
            near_atm_pcr=round(near_pcr, 2),
            pcr_trend="STABLE", # simplified for now
            structural_score=round(struct_score, 1),
            tactical_score=round(tact_score, 1),
            expiry_phase=expiry_phase,
            expiry_confidence_multiplier=expiry_mult,
            data_age_seconds=data_age_sec,
            freshness_multiplier=freshness_mult,
            market_state=regime,
            data_quality=data_qual,
            timestamp=snapshot.timestamp,
            explanation=explanation,
            feature_attribution=feature_attribution
        )
        
        msa = MarketStructureAnalysis(oi=oi_analysis, timestamp=snapshot.timestamp)
        details["market_structure"] = msa.to_dict()

        return AgentOutput(
            agent_name=self.name,
            timestamp=datetime.now(),
            direction=final_dir,
            confidence=round(effective_confidence, 1),
            strength=strength,
            details=details,
            warnings=warnings,
        )

    # ── HELPER METHODS ──

    def _get_atm_strike(self, chain: list, spot: float) -> float:
        if not chain: return spot
        strikes = [r["strike"] for r in chain]
        return min(strikes, key=lambda x: abs(x - spot))

    def _get_strike_radius(self, vix: float) -> int:
        if vix < self.th.oi_strike_radius_low_vix: return self.th.oi_strike_radius_low_vix
        if vix < self.th.oi_strike_radius_normal: return self.th.oi_strike_radius_normal
        if vix < self.th.oi_strike_radius_high_vix: return self.th.oi_strike_radius_high_vix
        return self.th.oi_strike_radius_extreme

    def _filter_chain(self, chain: list, atm: float, radius: int) -> list:
        if len(chain) < 2: return chain
        strike_diff = abs(chain[1]["strike"] - chain[0]["strike"])
        if strike_diff == 0: strike_diff = 50
        lo = atm - (radius * strike_diff)
        hi = atm + (radius * strike_diff)
        return [r for r in chain if lo <= r["strike"] <= hi]

    def _freshness_multiplier(self, age_sec: float) -> float:
        if age_sec <= self.th.oi_freshness_live_sec: return 1.00
        if age_sec <= self.th.oi_freshness_ok_sec: return 0.90
        if age_sec <= self.th.oi_freshness_stale_sec: return 0.75
        return self.th.oi_freshness_min_multiplier

    def _detect_expiry_phase(self, dte: int, is_expiry: bool, mins_to_close: int) -> tuple[str, float]:
        if is_expiry:
            if mins_to_close <= self.th.oi_expiry_afternoon_minutes:
                return "EXPIRY_AFTERNOON", self.th.oi_expiry_afternoon_multiplier
            return "EXPIRY_DAY", self.th.oi_expiry_day_multiplier
        if dte <= 1:
            return "MID", 0.85
        return "EARLY", self.th.oi_early_multiplier

    def _get_regime_weights(self, regime: str) -> tuple[float, float]:
        weights = {
            "STRONG_TREND_UP":   (0.60, 0.40),
            "STRONG_TREND_DOWN": (0.60, 0.40),
            "WEAK_TREND_UP":     (0.65, 0.35),
            "WEAK_TREND_DOWN":   (0.65, 0.35),
            "RANGING":           (0.80, 0.20),
            "BREAKOUT":          (0.55, 0.45),
            "VOLATILE_CHOPPY":   (0.50, 0.50),
        }
        return weights.get(regime, (self.th.oi_structural_weight_default, self.th.oi_tactical_weight_default))

    def _detect_zone(self, chain: list, opt_type: str, threshold_pct: float, adjacent_ratio: float) -> Optional[StrikeZone]:
        if not chain: return None
        
        total_oi = sum(r[opt_type.lower()].get("oi", 0) for r in chain)
        if total_oi == 0: return None
        
        # Sort by OI desc
        sorted_chain = sorted(chain, key=lambda x: x[opt_type.lower()].get("oi", 0), reverse=True)
        peak_row = sorted_chain[0]
        peak_oi = peak_row[opt_type.lower()].get("oi", 0)
        peak_strike = peak_row["strike"]
        
        if peak_oi / total_oi * 100 < threshold_pct:
            return None # No distinct wall
            
        # Cluster adjacent strikes
        zone_strikes = [peak_strike]
        zone_oi = peak_oi
        
        strike_diff = abs(chain[1]["strike"] - chain[0]["strike"]) if len(chain)>1 else 50
        
        for row in sorted_chain[1:]:
            oi = row[opt_type.lower()].get("oi", 0)
            if oi >= peak_oi * adjacent_ratio:
                # Is it adjacent to any existing zone strike?
                if any(abs(row["strike"] - zs) <= strike_diff for zs in zone_strikes):
                    zone_strikes.append(row["strike"])
                    zone_oi += oi
                    
        strength = min((zone_oi / total_oi) * 100 * 1.5, 100) # scale up a bit
        
        return StrikeZone(
            low=min(zone_strikes),
            high=max(zone_strikes),
            strength=strength,
            total_oi=zone_oi,
            peak_strike=peak_strike,
            num_strikes=len(zone_strikes)
        )

    def _compute_pressure_gradient(self, chain: list, spot: float) -> tuple[float, float]:
        ce_above = sum(r["ce"].get("oi", 0) for r in chain if r["strike"] > spot)
        pe_below = sum(r["pe"].get("oi", 0) for r in chain if r["strike"] < spot)
        return ce_above, pe_below
        
    def _compute_pcr(self, chain: list) -> float:
        ce_tot = sum(r["ce"].get("oi", 0) for r in chain)
        pe_tot = sum(r["pe"].get("oi", 0) for r in chain)
        return pe_tot / max(ce_tot, 1)

    def _analyze_migration(self, res_zone: Optional[StrikeZone], sup_zone: Optional[StrikeZone]) -> tuple[str, float]:
        if len(self._history) < 2: return "STABLE", 0.0
        
        # Simplified recency-weighted migration
        migration_dir = "STABLE"
        velocity = 0.0
        
        past_res = self._history[-2].get("res_zone")
        past_sup = self._history[-2].get("sup_zone")
        
        if res_zone and past_res:
            if res_zone.peak_strike > past_res.peak_strike: migration_dir = "UP"
            elif res_zone.peak_strike < past_res.peak_strike: migration_dir = "DOWN"
            
        if sup_zone and past_sup:
            if sup_zone.peak_strike > past_sup.peak_strike and migration_dir != "DOWN": migration_dir = "UP"
            elif sup_zone.peak_strike < past_sup.peak_strike and migration_dir != "UP": migration_dir = "DOWN"
            
        if migration_dir != "STABLE":
            velocity = 0.5 # Simplified velocity
            
        return migration_dir, velocity

    def _analyze_walls(self, spot: float, res_zone: StrikeZone, sup_zone: StrikeZone, chain: list) -> tuple[bool, bool, str]:
        # Absorption
        # Price near res_zone high, and res_zone strong
        absorption = False
        break_det = False
        break_dir = "NONE"
        
        dist_to_res = (res_zone.low - spot) / spot
        if 0 < dist_to_res < (self.th.oi_wall_absorption_proximity_pct / 100) and res_zone.strength > 50:
            absorption = True
            
        dist_to_sup = (spot - sup_zone.high) / spot
        if 0 < dist_to_sup < (self.th.oi_wall_absorption_proximity_pct / 100) and sup_zone.strength > 50:
            absorption = True
            
        # Break (needs history)
        if len(self._history) >= 2:
            past_res = self._history[-2].get("res_zone")
            if past_res and spot > past_res.high:
                current_ce_oi = sum(r["ce"].get("oi",0) for r in chain if past_res.low <= r["strike"] <= past_res.high)
                if current_ce_oi < past_res.total_oi * (1 - self.th.oi_wall_break_collapse_pct/100):
                    break_det = True
                    break_dir = "BULLISH"
                    
            past_sup = self._history[-2].get("sup_zone")
            if past_sup and spot < past_sup.low:
                current_pe_oi = sum(r["pe"].get("oi",0) for r in chain if past_sup.low <= r["strike"] <= past_sup.high)
                if current_pe_oi < past_sup.total_oi * (1 - self.th.oi_wall_break_collapse_pct/100):
                    break_det = True
                    break_dir = "BEARISH"
                    
        return absorption, break_det, break_dir

    def _detect_oi_trap(self, spot: float, chain: list) -> tuple[bool, str]:
        if len(self._history) < 2: return False, "NONE"
        
        past_res = self._history[-2].get("res_zone")
        if past_res and past_res.strength >= self.th.oi_trap_wall_strength_min:
            current_ce_oi = sum(r["ce"].get("oi",0) for r in chain if past_res.low <= r["strike"] <= past_res.high)
            if current_ce_oi < past_res.total_oi * self.th.oi_trap_collapse_ratio and spot > past_res.high:
                return True, "CALL_TRAP"
                
        past_sup = self._history[-2].get("sup_zone")
        if past_sup and past_sup.strength >= self.th.oi_trap_wall_strength_min:
            current_pe_oi = sum(r["pe"].get("oi",0) for r in chain if past_sup.low <= r["strike"] <= past_sup.high)
            if current_pe_oi < past_sup.total_oi * self.th.oi_trap_collapse_ratio and spot < past_sup.low:
                return True, "PUT_TRAP"
                
        return False, "NONE"

    def _detect_flip(self, chain: list) -> tuple[bool, str]:
        # Simplified flip detection
        return False, "NONE"

    def _update_history(self, snapshot, chain, res_zone, sup_zone, pcr):
        self._history.append({
            "timestamp": snapshot.timestamp,
            "chain": chain,
            "res_zone": res_zone,
            "sup_zone": sup_zone,
            "pcr": pcr
        })
        if len(self._history) > self.th.oi_migration_lookback:
            self._history.pop(0)

    def _compute_structural_score(self, res_zone, sup_zone, spot, pressure_ratio) -> tuple[float, Direction]:
        score = 0.0
        direction = Direction.NEUTRAL
        
        # simplified structural scoring
        bull_pts = 0
        bear_pts = 0
        
        if sup_zone: bull_pts += sup_zone.strength
        if res_zone: bear_pts += res_zone.strength
        
        if pressure_ratio > 1.2: bear_pts += 30
        elif pressure_ratio < 0.8: bull_pts += 30
        
        if bull_pts > bear_pts:
            direction = Direction.BULLISH
            score = min(100, bull_pts - bear_pts)
        elif bear_pts > bull_pts:
            direction = Direction.BEARISH
            score = min(100, bear_pts - bull_pts)
            
        return score, direction

    def _compute_tactical_score(self, mig_dir, mig_vel, flip_det, flip_side,
                                absorption, w_break, break_dir, trap_det, trap_type, pcr) -> tuple[float, Direction]:
        bull_pts = 0
        bear_pts = 0
        
        if mig_dir == "UP": bull_pts += 40 * mig_vel
        elif mig_dir == "DOWN": bear_pts += 40 * mig_vel
        
        if w_break:
            if break_dir == "BULLISH": bull_pts += 50
            elif break_dir == "BEARISH": bear_pts += 50
            
        if trap_det:
            if trap_type == "CALL_TRAP": bull_pts += 60 # Shorts forced to cover
            elif trap_type == "PUT_TRAP": bear_pts += 60
            
        if pcr > 1.2: bull_pts += 20
        elif pcr < 0.8: bear_pts += 20
        
        direction = Direction.NEUTRAL
        score = 0.0
        if bull_pts > bear_pts:
            direction = Direction.BULLISH
            score = min(100, bull_pts - bear_pts)
        elif bear_pts > bull_pts:
            direction = Direction.BEARISH
            score = min(100, bear_pts - bull_pts)
            
        return score, direction

    def _compute_reliability(self, freshness_mult, expiry_mult, history_depth, data_quality) -> float:
        base = 50.0
        base += (freshness_mult - 0.4) / 0.6 * 25
        base += (expiry_mult - 0.4) / 0.6 * 20
        base += min(history_depth / 12, 1.0) * 15
        
        if data_quality == "STALE": base -= 15
        if data_quality == "SIMULATED": base = 10
        
        return max(0, min(100, base))
        
    def _compute_conviction(self, struct_dir, tact_dir, mig_dir, break_dir, trap_type) -> float:
        factors = [struct_dir, tact_dir]
        if mig_dir == "UP": factors.append(Direction.BULLISH)
        elif mig_dir == "DOWN": factors.append(Direction.BEARISH)
        if break_dir == "BULLISH": factors.append(Direction.BULLISH)
        elif break_dir == "BEARISH": factors.append(Direction.BEARISH)
        if trap_type == "CALL_TRAP": factors.append(Direction.BULLISH)
        elif trap_type == "PUT_TRAP": factors.append(Direction.BEARISH)
        
        bull_c = sum(1 for f in factors if f == Direction.BULLISH)
        bear_c = sum(1 for f in factors if f == Direction.BEARISH)
        return max(bull_c, bear_c) / len(factors) * 100 if factors else 0

    def _build_explanation(self, res_zone, sup_zone, mig_dir, mig_vel,
                           w_break, break_dir, absorption, trap_det, trap_type,
                           flip_det, flip_side, f_mult, age, e_mult, e_phase) -> list:
        reasons = []
        if sup_zone and sup_zone.strength > 50:
            reasons.append(f"✓ Put support zone {sup_zone.low}-{sup_zone.high} (strength {sup_zone.strength:.0f})")
        if res_zone and res_zone.strength > 50:
            reasons.append(f"✓ Call resistance zone {res_zone.low}-{res_zone.high} (strength {res_zone.strength:.0f})")
            
        if mig_dir == "UP": reasons.append(f"✓ Resistance migrating UP (vel {mig_vel:.2f})")
        elif mig_dir == "DOWN": reasons.append(f"✓ Support migrating DOWN (vel {mig_vel:.2f})")
        
        if w_break: reasons.append(f"✓ Wall BREAK detected — {break_dir}")
        if absorption: reasons.append("✗ Wall absorption — institutions defending")
        if trap_det: reasons.append(f"⚠ OI TRAP detected — {trap_type}")
        if flip_det: reasons.append(f"✓ OI flip — {flip_side}")
        
        if f_mult < 0.8: reasons.append(f"✗ Freshness reduced (age {age:.0f}s)")
        if e_mult < 0.8: reasons.append(f"✗ Expiry confidence reduced ({e_phase})")
        
        return reasons
