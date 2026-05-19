import logging
from typing import Optional
from dataclasses import replace
import pandas as pd

from core.regime_classifier import RegimeState, MarketRegime, RegimeClassifier

logger = logging.getLogger("regime_manager")

class RegimeStateManager:
    """
    Applies persistence and hysteresis to market regime classification.
    Prevents regime 'flickering' at the boundaries.
    
    If the raw classifier proposes a new regime, it must persist for N consecutive
    evaluations before becoming the new 'confirmed' regime.
    """
    def __init__(self, classifier: RegimeClassifier, confirm_threshold: int = 3):
        self.classifier = classifier
        self.confirm_threshold = confirm_threshold
        
        self.current_confirmed_state: Optional[RegimeState] = None
        
        # State tracking for hysteresis
        self._proposed_regime: Optional[MarketRegime] = None
        self._consecutive_count: int = 0
        
    def classify(self, df: pd.DataFrame, snapshot_vwap: float, snapshot_atr: float, prev_day_close: float = None) -> RegimeState:
        # 1. Get raw classification
        raw_state = self.classifier.classify(df, snapshot_vwap, snapshot_atr, prev_day_close)
        
        # Initialize if empty
        if self.current_confirmed_state is None:
            self.current_confirmed_state = raw_state
            self._proposed_regime = raw_state.regime
            self._consecutive_count = 1
            return raw_state
            
        # 2. Hysteresis check
        if raw_state.regime == self.current_confirmed_state.regime:
            # We are stable. Update the internal metrics (confidence, volatility) but keep regime.
            self._proposed_regime = raw_state.regime
            self._consecutive_count = 0
            
            # Smooth out confidence (EMA-style persistence)
            smoothed_conf = (self.current_confirmed_state.confidence * 0.7) + (raw_state.confidence * 0.3)
            self.current_confirmed_state = replace(raw_state, confidence=smoothed_conf)
            return self.current_confirmed_state
            
        # 3. Proposed regime differs from confirmed regime
        if raw_state.regime == self._proposed_regime:
            self._consecutive_count += 1
        else:
            self._proposed_regime = raw_state.regime
            self._consecutive_count = 1
            
        # 4. Check if threshold met to confirm switch
        if self._consecutive_count >= self.confirm_threshold:
            old_regime = self.current_confirmed_state.regime.value
            new_regime = raw_state.regime.value
            
            logger.info(
                f"🌍 [REGIME SHIFT] {old_regime} → {new_regime} "
                f"(Confirmed after {self.confirm_threshold} cycles)"
            )
            
            self.current_confirmed_state = raw_state
            self._consecutive_count = 0
            return self.current_confirmed_state
            
        # 5. Threshold not met, return the currently confirmed regime but with raw metrics
        # (meaning we don't switch the label yet to avoid flickering)
        smoothed_conf = (self.current_confirmed_state.confidence * 0.8) + (raw_state.confidence * 0.2)
        return replace(raw_state, regime=self.current_confirmed_state.regime, confidence=smoothed_conf)
