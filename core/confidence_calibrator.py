class ConfidenceCalibrator:
    """
    Shadow-mode calibration layer.
    Maps raw probability scores (which are inflated due to agent aggregation)
    down to empirically observed win rates derived from the 300-trade evidence run.
    """
    
    def __init__(self):
        # Empirical reliability lookup table (Raw Bucket -> Actual Win Rate)
        # Sourced from Sprint 4 Diagnostics
        self.reliability_table = {
            "TRENDING_UP": {"80-90": 0.85, "90-100": 0.85}, # Too few samples, left at 0.85
            "TRENDING": {"80-90": 0.59, "90-100": 0.60},
            "BREAKOUT": {"80-90": 0.74, "90-100": 0.74},
            "RANGE":    {"80-90": 0.46, "90-100": 0.47},
            "CHOPPY":   {"80-90": 0.33, "90-100": 0.33},
            "VOLATILE": {"80-90": 0.33, "90-100": 0.33}, # Map volatile to choppy
        }
        
    def _get_bucket(self, conf: float) -> str:
        """Map raw float confidence to the lookup table bucket string."""
        if conf < 0.90:
            return "80-90"
        return "90-100"

    def calibrate(self, raw_confidence: float, regime: str) -> float:
        """
        Takes the raw inflated confidence and the active regime,
        and returns the empirically calibrated confidence.
        """
        # Default fallback is the raw confidence if regime isn't in our table
        regime_upper = str(regime).upper()
        # Clean up enum strings like "MarketRegime.BREAKOUT"
        if "." in regime_upper:
            regime_upper = regime_upper.split(".")[1]
            
        # Also handle mapped values
        if regime_upper == "VOLATILE_CHOPPY":
            regime_upper = "CHOPPY"
            
        bucket = self._get_bucket(raw_confidence)
        
        if regime_upper in self.reliability_table:
            # Return the observed historical win rate for this bucket and regime
            return self.reliability_table[regime_upper].get(bucket, raw_confidence)
            
        # If we have no data, fallback to raw confidence
        return raw_confidence
