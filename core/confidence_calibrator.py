import math

class ConfidenceCalibrator:
    """
    Shadow & Live Calibration Layer (v2.1).
    Maps raw probability scores (which can be inflated due to agent aggregation)
    down to empirically observed win rates derived from historical session runs.
    Supports continuous Platt-scaling as well as regime-specific empirical tables.
    """
    
    def __init__(self, platt_a: float = 3.5, platt_b: float = -1.8):
        self.platt_a = platt_a
        self.platt_b = platt_b
        
        # Empirical reliability lookup table (Raw Bucket -> Actual Win Rate)
        self.reliability_table = {
            "TRENDING_UP":   {"<70": 0.52, "70-80": 0.68, "80-90": 0.78, "90-100": 0.85},
            "TRENDING_DOWN": {"<70": 0.52, "70-80": 0.68, "80-90": 0.78, "90-100": 0.85},
            "TRENDING":      {"<70": 0.50, "70-80": 0.59, "80-90": 0.68, "90-100": 0.74},
            "BREAKOUT":      {"<70": 0.55, "70-80": 0.64, "80-90": 0.74, "90-100": 0.81},
            "RANGE":         {"<70": 0.38, "70-80": 0.44, "80-90": 0.49, "90-100": 0.52},
            "CHOPPY":        {"<70": 0.25, "70-80": 0.30, "80-90": 0.33, "90-100": 0.35},
            "VOLATILE":      {"<70": 0.25, "70-80": 0.30, "80-90": 0.33, "90-100": 0.35},
        }

    def _get_bucket(self, conf_pct: float) -> str:
        """Map percentage confidence (0-100) to bucket string."""
        if conf_pct < 70.0:
            return "<70"
        elif conf_pct < 80.0:
            return "70-80"
        elif conf_pct < 90.0:
            return "80-90"
        return "90-100"

    def calibrate(self, raw_confidence: float, regime: str = "TRENDING") -> tuple[float, dict]:
        """
        Takes raw confidence (float 0.0-1.0 or 0-100) and regime string,
        and returns (calibrated win probability, telemetry dict).
        """
        # Normalize fractional inputs (e.g., 0.85) to percentage scale (85.0)
        conf_pct = raw_confidence * 100.0 if raw_confidence <= 1.0 else raw_confidence
        conf_frac = conf_pct / 100.0

        regime_upper = str(regime).upper()
        if "." in regime_upper:
            regime_upper = regime_upper.split(".")[1]
            
        if regime_upper in ["VOLATILE_CHOPPY", "SQUEEZE", "REVERSAL"]:
            if regime_upper == "VOLATILE_CHOPPY":
                regime_upper = "CHOPPY"
            elif regime_upper == "REVERSAL":
                regime_upper = "BREAKOUT"

        bucket = self._get_bucket(conf_pct)

        calibrated_val = 0.0
        method_used = "UNKNOWN"

        if regime_upper in self.reliability_table and bucket in self.reliability_table[regime_upper]:
            calibrated_val = self.reliability_table[regime_upper][bucket]
            method_used = "EMPIRICAL"
        else:
            # Platt scaling continuous fallback: 1 / (1 + exp(-(A * conf + B)))
            try:
                val = 1.0 / (1.0 + math.exp(-(self.platt_a * conf_frac + self.platt_b)))
                calibrated_val = round(max(0.10, min(0.95, val)), 4)
            except Exception:
                calibrated_val = round(max(0.10, min(0.95, conf_frac * 0.85)), 4)
            method_used = "PLATT_SCALING"

        telemetry = {
            "raw_confidence": round(conf_pct, 2),
            "calibrated_pwin": calibrated_val,
            "regime": regime_upper,
            "method": method_used
        }
        
        return calibrated_val, telemetry

