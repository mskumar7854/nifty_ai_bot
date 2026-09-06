import logging
from typing import Optional, Dict, Any, Tuple
import pandas as pd
from datetime import datetime

from config.settings import AMDConfig
from models.amd_state import AMDState, AMDPhase

logger = logging.getLogger("amd_engine")


class AMDEngine:
    """
    Accumulation-Manipulation-Expansion (AMD) V1 State Engine.
    
    A strictly passive, read-only structural intelligence plugin.
    Consumes canonical price facts to identify liquidity sweeps and rejections.
    """
    
    def __init__(self, config: AMDConfig, symbol: str, timeframe_minutes: int):
        self.config = config
        self.symbol = symbol
        self.timeframe_minutes = timeframe_minutes
        self.state = AMDState()
        self._init_state()
        
    def _init_state(self):
        self.state.config_version = "AMD_V1_1"
        self.state.engine_version = "v1.0"
        self.state.timeframe_minutes = self.timeframe_minutes
        
    def reset(self):
        """Hard reset of the AMD state machine while retaining identity."""
        self.state = AMDState()
        self._init_state()
        
    def _calculate_wick_metrics(self, open_p: float, high_p: float, low_p: float, close_p: float) -> Tuple[float, float, float]:
        """
        Calculates direction-aware wick metrics.
        Returns: (lower_wick_ratio, upper_wick_ratio, close_location)
        """
        candle_range = high_p - low_p
        if candle_range <= 0.001:  # Protect against zero-range candles
            return 0.0, 0.0, 0.5
            
        lower_wick = min(open_p, close_p) - low_p
        upper_wick = high_p - max(open_p, close_p)
        
        lower_wick_ratio = lower_wick / candle_range
        upper_wick_ratio = upper_wick / candle_range
        close_location = (close_p - low_p) / candle_range
        
        return lower_wick_ratio, upper_wick_ratio, close_location

    def _evaluate_accumulation(self, candle: pd.Series, atr: float, structural_facts: Dict[str, Any], ts: datetime) -> bool:
        """
        Evaluates if we should transition from IDLE to ACCUMULATION.
        Requires canonical structural facts like range bounds.
        """
        range_high = structural_facts.get("consolidation_high")
        range_low = structural_facts.get("consolidation_low")
        duration_candles = structural_facts.get("consolidation_duration_candles", 0)
        start_ts = structural_facts.get("consolidation_start_time")
        
        # Fallback to calculate minutes if start time is missing
        duration_mins = (ts - start_ts).total_seconds() / 60.0 if start_ts else duration_candles * self.timeframe_minutes
        
        if range_high and range_low and duration_mins >= self.config.min_range_duration_minutes:
            range_size = range_high - range_low
            if range_size <= self.config.max_range_atr_multiple * atr:
                self.state.range_high = range_high
                self.state.range_low = range_low
                self.state.range_mid = (range_high + range_low) / 2.0
                self.state.range_start_timestamp = start_ts or (ts - timedelta(minutes=duration_mins))
                self.state.range_duration_candles = duration_candles
                self.state.range_duration_minutes = duration_mins
                return True
        return False

    def evaluate(self, candle: pd.Series, atr: float, structural_facts: Dict[str, Any], timestamp: datetime) -> AMDState:
        """
        Core tick evaluation loop for the state machine.
        Called strictly after the bar closes (closed-bar).
        """
        self.state.timestamp = timestamp
        
        # Unpack candle
        o, h, l, c = candle['open'], candle['high'], candle['low'], candle['close']
        candle_range = h - l
        
        if candle_range <= 0:
            return self.state  # Ignore 0-range invalid candles (unchanged state)
            
        lower_wick_ratio, upper_wick_ratio, close_location = self._calculate_wick_metrics(o, h, l, c)

        # ── STATE MACHINE TRANSITIONS ──
        
        # Evaluate ACCUMULATION Entry
        if self.state.phase == AMDPhase.IDLE:
            if self._evaluate_accumulation(candle, atr, structural_facts, timestamp):
                self.state.phase = AMDPhase.ACCUMULATION
                
        # Evaluate MANIPULATION Entry or INVALIDATION from ACCUMULATION
        if self.state.phase == AMDPhase.ACCUMULATION:
            # Check for range invalidation (clean breakout with no sweep)
            if c > self.state.range_high + (self.config.min_sweep_atr_multiple * atr):
                if close_location > 0.8:  # Clean bullish breakout
                    self.state.phase = AMDPhase.INVALIDATED
                    return self.state
            elif c < self.state.range_low - (self.config.min_sweep_atr_multiple * atr):
                if close_location < 0.2:  # Clean bearish breakout
                    self.state.phase = AMDPhase.INVALIDATED
                    return self.state

            # Check for BSL Sweep (Bearish setup potential)
            if h > self.state.range_high + (self.config.min_sweep_atr_multiple * atr):
                self.state.sweep_side = "BSL"
                self.state.sweep_extreme_price = h
                self.state.sweep_depth_pts = h - self.state.range_high
                self.state.phase = AMDPhase.MANIPULATION
                
            # Check for SSL Sweep (Bullish setup potential)
            elif l < self.state.range_low - (self.config.min_sweep_atr_multiple * atr):
                self.state.sweep_side = "SSL"
                self.state.sweep_extreme_price = l
                self.state.sweep_depth_pts = self.state.range_low - l
                self.state.phase = AMDPhase.MANIPULATION

        # Evaluate REJECTION or ACCEPTANCE in MANIPULATION
        if self.state.phase == AMDPhase.MANIPULATION:
            self.state.confirmation_candles += 1
            self.state.lower_wick_ratio = lower_wick_ratio
            self.state.upper_wick_ratio = upper_wick_ratio
            self.state.close_location = close_location
            
            # Evaluate Rejection on the sweep candle or immediate follow-up
            if not self.state.rejection_confirmed:
                if self.state.sweep_side == "SSL":
                    # Bullish rejection criteria
                    if lower_wick_ratio >= self.config.min_bullish_rejection_wick_ratio and close_location >= self.config.min_bullish_close_location:
                        if c >= self.state.range_low: # Close back inside
                            self.state.rejection_confirmed = True
                            self.state.inferred_bias = "BULLISH"
                elif self.state.sweep_side == "BSL":
                    # Bearish rejection criteria
                    if upper_wick_ratio >= self.config.min_bearish_rejection_wick_ratio and close_location <= self.config.max_bearish_close_location:
                        if c <= self.state.range_high: # Close back inside
                            self.state.rejection_confirmed = True
                            self.state.inferred_bias = "BEARISH"

            # Check for Timeout / Acceptance Outside Range (Failed Trap)
            if self.state.confirmation_candles > self.config.max_acceptance_candles and not self.state.rejection_confirmed:
                self.state.phase = AMDPhase.INVALIDATED
                return self.state
                
            if self.state.sweep_side == "SSL" and c < self.state.range_low:
                if self.state.confirmation_candles >= 2: # Clean acceptance outside
                    self.state.acceptance_confirmed = True
                    self.state.phase = AMDPhase.EXPANSION_BREAKOUT # Actually a breakdown, but breaking out of the AMD pattern
                    self.state.inferred_bias = "BEARISH"
                    return self.state
            elif self.state.sweep_side == "BSL" and c > self.state.range_high:
                if self.state.confirmation_candles >= 2:
                    self.state.acceptance_confirmed = True
                    self.state.phase = AMDPhase.EXPANSION_BREAKOUT
                    self.state.inferred_bias = "BULLISH"
                    return self.state

            # If rejected, look for MSB / Displacement to transition to EXPANSION
            if self.state.rejection_confirmed:
                msb_signal = structural_facts.get("msb_bullish") if self.state.sweep_side == "SSL" else structural_facts.get("msb_bearish")
                
                # Simple displacement proxy for now if no explicit MSB is provided
                displacement = False
                if self.state.sweep_side == "SSL":
                    displacement = c > self.state.range_mid and (c - o) > (self.config.min_displacement_atr_multiple * atr)
                else:
                    displacement = c < self.state.range_mid and (o - c) > (self.config.min_displacement_atr_multiple * atr)

                if msb_signal or displacement:
                    self.state.msb_confirmed = bool(msb_signal)
                    self.state.phase = AMDPhase.EXPANSION

        # Evaluate EXPANSION follow-through
        if self.state.phase == AMDPhase.EXPANSION:
            # Check for follow-through or failure
            if self.state.sweep_side == "SSL":
                if c > self.state.range_high:
                    self.state.phase = AMDPhase.EXPANSION_BREAKOUT
                elif c < self.state.range_low: # Structural failure (went all the way back down)
                    self.state.phase = AMDPhase.INVALIDATED
            else:
                if c < self.state.range_low:
                    self.state.phase = AMDPhase.EXPANSION_BREAKOUT
                elif c > self.state.range_high: # Structural failure
                    self.state.phase = AMDPhase.INVALIDATED
                    
        # Evaluate EXPANSION_BREAKOUT reversal
        if self.state.phase == AMDPhase.EXPANSION_BREAKOUT:
            if self.state.sweep_side == "SSL" and c < self.state.range_high:
                self.state.phase = AMDPhase.INVALIDATED
            elif self.state.sweep_side == "BSL" and c > self.state.range_low:
                self.state.phase = AMDPhase.INVALIDATED

        return self.state
