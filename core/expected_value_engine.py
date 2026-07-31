"""
============================================
EXPECTED VALUE (EV) ENGINE (v2.1)

Calculates mathematical Expected Value (EV) in R-multiples:
    EV = (P_win_calibrated * RR) - ((1 - P_win_calibrated) * 1.0) - Friction

Before any setup reaches OMS, it must demonstrate positive expected value (+0.50R baseline)
and a normalized EV score >= 60.
============================================
"""

from typing import Dict, Any, Tuple


class ExpectedValueEngine:
    def __init__(self, min_ev_r: float = 0.50, min_ev_score: float = 60.0, default_friction_r: float = 0.08):
        self.min_ev_r = min_ev_r
        self.min_ev_score = min_ev_score
        self.default_friction_r = default_friction_r

    def evaluate(
        self,
        calibrated_pwin: float,
        risk_reward_ratio: float,
        spread_pct: float = 0.0,
        slippage_r: float = 0.05
    ) -> Dict[str, Any]:
        """
        Evaluate Expected Value for a given trade signal.
        
        Args:
            calibrated_pwin: Probability derived from ConfidenceCalibrator (0.0 to 1.0)
            risk_reward_ratio: Target / Stop-Loss ratio (e.g. 2.0)
            spread_pct: Bid-Ask spread percentage (e.g. 0.8%)
            slippage_r: Expected slippage in R-multiples (e.g. 0.05R)
            
        Returns:
            Dict containing ev_r, normalized_score, passes_gate, and details breakdown.
        """
        rr = max(0.5, float(risk_reward_ratio))
        p_win = max(0.05, min(0.95, float(calibrated_pwin)))
        p_loss = 1.0 - p_win

        # Estimate friction in R units based on spread and slippage
        spread_friction_r = (spread_pct / 100.0) * 0.10 if spread_pct > 0 else 0.0
        total_friction_r = self.default_friction_r + spread_friction_r + max(0.0, slippage_r)

        # Raw EV in R-multiples: (Pwin * RR) - (Ploss * 1.0) - Friction
        raw_ev_r = (p_win * rr) - (p_loss * 1.0) - total_friction_r

        # Normalize EV to a 0-100 scale
        # EV = 0.0R -> Score = 40
        # EV = 0.50R -> Score = 65
        # EV = 1.50R+ -> Score = 100
        normalized_score = min(100.0, max(0.0, 40.0 + (raw_ev_r * 50.0)))

        passes_gate = (raw_ev_r >= self.min_ev_r) and (normalized_score >= self.min_ev_score)

        if passes_gate:
            reason = f"EV {raw_ev_r:.2f}R >= {self.min_ev_r}R threshold"
        else:
            reason = f"EV below threshold (EV: {raw_ev_r:.2f}R, Min: {self.min_ev_r}R)"

        return {
            "ev_r": round(raw_ev_r, 4),
            "normalized_score": round(normalized_score, 2),
            "passes_gate": passes_gate,
            "reason": reason,
            "details": {
                "calibrated_pwin": round(p_win, 4),
                "risk_reward_ratio": round(rr, 2),
                "p_loss": round(p_loss, 4),
                "total_friction_r": round(total_friction_r, 4),
                "min_ev_r_required": self.min_ev_r,
                "min_ev_score_required": self.min_ev_score
            }
        }
