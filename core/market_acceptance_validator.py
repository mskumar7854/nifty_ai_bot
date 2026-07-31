import logging
from enum import Enum
from typing import Dict, Optional, Tuple, Any
from datetime import datetime
import pandas as pd


class AcceptanceState(Enum):
    IDLE = "IDLE"
    CANDIDATE = "CANDIDATE"
    STRUCTURAL_BREAK = "STRUCTURAL_BREAK"
    WAITING_ACCEPTANCE = "WAITING_ACCEPTANCE"
    ACCEPTED = "ACCEPTED"
    FALSE_BREAKOUT = "FALSE_BREAKOUT"
    TIMEOUT = "TIMEOUT"


class MarketAcceptanceValidator:
    """
    Market Acceptance Validator (MAV)
    Validates structural breakouts based on completed 1-minute candles.
    Prevents false breakouts (liquidity sweeps) by requiring confirmation.
    """

    def __init__(self, timeout_candles: int = 5):
        self.logger = logging.getLogger("MAV")
        self.state = AcceptanceState.IDLE
        self.timeout_candles = timeout_candles
        
        # State tracking
        self.candidate_id: Optional[str] = None
        self.direction = None
        self.structural_level: float = 0.0
        self.start_candle_time: Optional[datetime] = None
        self.candles_elapsed: int = 0
        self.break_candle: Optional[pd.Series] = None
        
        self.acceptance_score: float = 0.0
        self.failure_reason: str = ""

    def reset(self):
        """Reset the validator back to IDLE state."""
        self.state = AcceptanceState.IDLE
        self.candidate_id = None
        self.direction = None
        self.structural_level = 0.0
        self.start_candle_time = None
        self.candles_elapsed = 0
        self.break_candle = None
        self.acceptance_score = 0.0
        self.failure_reason = ""

    def track_candidate(self, candidate_id: str, direction: str, structural_level: float, current_time: datetime):
        """Register a new breakout candidate."""
        if self.state != AcceptanceState.IDLE:
            self.logger.warning(f"MAV: Overwriting existing candidate {self.candidate_id} with {candidate_id}")
            
        self.reset()
        self.state = AcceptanceState.CANDIDATE
        self.candidate_id = candidate_id
        self.direction = direction.upper()
        self.structural_level = structural_level
        self.start_candle_time = current_time
        
        self.logger.info(f"MAV: Tracking {self.direction} Candidate {self.candidate_id} against structure {self.structural_level:.2f}")

    def evaluate_1m_candle(self, df_1m: pd.DataFrame, ema_50: float = None) -> AcceptanceState:
        """
        Evaluate completed 1-minute candles.
        df_1m should contain at least ['open', 'high', 'low', 'close'] and be indexed by timestamp.
        """
        if self.state in [AcceptanceState.IDLE, AcceptanceState.ACCEPTED, AcceptanceState.FALSE_BREAKOUT, AcceptanceState.TIMEOUT]:
            return self.state

        if df_1m.empty or len(df_1m) < 2:
            return self.state

        current_candle_ts = df_1m.index[-1]
        
        # We only evaluate when a new candle starts, meaning the previous one is COMPLETE.
        # Track the last evaluated completed candle timestamp to prevent double-counting.
        if not hasattr(self, 'last_eval_ts'):
            self.last_eval_ts = None
            
        completed_candle_ts = df_1m.index[-2]
        
        if self.start_candle_time and completed_candle_ts < self.start_candle_time:
            return self.state  # The completed candle is from before we started tracking
            
        if self.last_eval_ts == completed_candle_ts:
            return self.state  # Already evaluated this completed candle
            
        self.last_eval_ts = completed_candle_ts
        completed_candle = df_1m.iloc[-2]
        
        self.candles_elapsed += 1
        c_open = completed_candle['open']
        c_high = completed_candle['high']
        c_low = completed_candle['low']
        c_close = completed_candle['close']

        # Check Timeout
        if self.candles_elapsed > self.timeout_candles:
            self.failure_reason = f"Timeout after {self.timeout_candles} candles without acceptance"
            self.state = AcceptanceState.TIMEOUT
            self.logger.info(f"MAV: {self.candidate_id} {self.state.value} - {self.failure_reason}")
            return self.state

        if self.state == AcceptanceState.CANDIDATE:
            # We are waiting for a STRUCTURAL CLOSE (Body close beyond structure)
            is_break = False
            if self.direction == "BEARISH" and c_close < self.structural_level:
                is_break = True
            elif self.direction == "BULLISH" and c_close > self.structural_level:
                is_break = True
                
            if is_break:
                self.state = AcceptanceState.STRUCTURAL_BREAK
                self.break_candle = completed_candle
                self.acceptance_score += 35.0  # Structural Close achieved
                self.logger.info(f"MAV: {self.candidate_id} STRUCTURAL_BREAK at {c_close} (Level: {self.structural_level})")
                # Immediately move to waiting acceptance for the NEXT candle
                self.state = AcceptanceState.WAITING_ACCEPTANCE
            else:
                # If it wicked beyond but closed inside, it's an immediate false breakout trap.
                wicked_beyond = (self.direction == "BEARISH" and c_low < self.structural_level) or \
                                (self.direction == "BULLISH" and c_high > self.structural_level)
                if wicked_beyond:
                    self.failure_reason = f"Wick rejected at {self.structural_level}, close at {c_close}"
                    self.state = AcceptanceState.FALSE_BREAKOUT
                    self.logger.info(f"MAV: {self.candidate_id} FALSE_BREAKOUT - {self.failure_reason}")
            return self.state

        elif self.state == AcceptanceState.WAITING_ACCEPTANCE:
            # We need the next candle to STAY beyond the structure.
            held_acceptance = False
            if self.direction == "BEARISH" and c_close < self.structural_level:
                held_acceptance = True
            elif self.direction == "BULLISH" and c_close > self.structural_level:
                held_acceptance = True
                
            if not held_acceptance:
                self.failure_reason = f"Acceptance candle failed to hold {self.structural_level}, closed at {c_close}"
                self.state = AcceptanceState.FALSE_BREAKOUT
                self.logger.info(f"MAV: {self.candidate_id} FALSE_BREAKOUT - {self.failure_reason}")
                return self.state
            
            self.acceptance_score += 35.0  # Acceptance Candle achieved

            # EMA Context check (if provided)
            if ema_50 is not None:
                if self.direction == "BEARISH" and c_close < ema_50:
                    self.acceptance_score += 15.0
                elif self.direction == "BULLISH" and c_close > ema_50:
                    self.acceptance_score += 15.0

            # Momentum persistence check
            if self.break_candle is not None:
                b_body = abs(self.break_candle['close'] - self.break_candle['open'])
                c_body = abs(c_close - c_open)
                # If follow through body is at least 30% of breakout body
                if b_body > 0 and (c_body / b_body) > 0.3:
                    self.acceptance_score += 10.0

            if self.acceptance_score >= 70.0:
                self.state = AcceptanceState.ACCEPTED
                self.logger.info(f"MAV: {self.candidate_id} ACCEPTED with score {self.acceptance_score}")
            else:
                self.failure_reason = f"Low acceptance score ({self.acceptance_score})"
                self.state = AcceptanceState.FALSE_BREAKOUT
                self.logger.info(f"MAV: {self.candidate_id} FALSE_BREAKOUT - {self.failure_reason}")

            return self.state

        return self.state
