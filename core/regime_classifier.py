import pandas as pd
import numpy as np
from enum import Enum
from dataclasses import dataclass
from typing import Dict, Any

class MarketRegime(Enum):
    TREND_UP = "TREND_UP"
    TREND_DOWN = "TREND_DOWN"
    RANGE = "RANGE"
    VOLATILE = "VOLATILE"
    LOW_VOL = "LOW_VOL"

@dataclass
class RegimeState:
    regime: MarketRegime
    confidence: float
    volatility_state: str
    trend_strength: float
    tradability: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "regime": self.regime.value,
            "confidence": round(self.confidence, 2),
            "volatility_state": self.volatility_state,
            "trend_strength": round(self.trend_strength, 2),
            "tradability": round(self.tradability, 2)
        }

class RegimeClassifier:
    """
    Descriptive, context-adaptive regime classifier.
    Answers ONLY: 'What kind of market are we in right now?'
    
    Inputs are market-pure:
    - ATR expansion
    - Opening gap %
    - VWAP distance
    - Trend slope
    - Volume expansion
    - Candle overlap efficiency
    """
    
    def __init__(self, lookback: int = 20):
        self.lookback = lookback
        
    def classify(self, df: pd.DataFrame, snapshot_vwap: float, snapshot_atr: float, prev_day_close: float = None) -> RegimeState:
        if df is None or len(df) < self.lookback:
            return RegimeState(MarketRegime.RANGE, 0.0, "NORMAL", 0.0, 0.5)
            
        recent = df.tail(self.lookback)
        closes = recent['close'].values
        opens = recent['open'].values
        highs = recent['high'].values
        lows = recent['low'].values
        volumes = recent['volume'].values
        
        last_close = closes[-1]
        
        # 1. Trend Slope (Linear regression of closes)
        x = np.arange(len(closes))
        slope, _ = np.polyfit(x, closes, 1)
        # Normalized slope: points per candle
        
        # 2. VWAP Distance
        vwap_dist_pct = ((last_close - snapshot_vwap) / snapshot_vwap) * 100 if snapshot_vwap > 0 else 0
        
        # 3. Volatility / ATR Expansion
        # ATR as a % of price
        atr_pct = (snapshot_atr / last_close) * 100 if last_close > 0 else 0
        
        # 4. Volume Expansion
        avg_vol = np.mean(volumes[:-1]) if len(volumes) > 1 else 1.0
        last_vol = volumes[-1]
        vol_expansion = last_vol / avg_vol if avg_vol > 0 else 1.0
        
        # 5. Candle Overlap Efficiency (Directional Efficiency)
        # net move / sum of absolute body moves
        bodies = np.abs(closes - opens)
        total_body = np.sum(bodies)
        net_move = np.abs(closes[-1] - closes[0])
        efficiency = net_move / total_body if total_body > 0 else 0.0
        
        # 6. Opening Gap %
        gap_pct = 0.0
        if prev_day_close is not None and prev_day_close > 0:
            today_open = opens[-1] # Simplification, assuming intraday data
            gap_pct = abs((today_open - prev_day_close) / prev_day_close) * 100
            
        # --- Classification Logic ---
        
        # Volatility State Mapping for Nifty (approximate points/pct)
        # Nifty at 22000: 0.1% = 22 pts, 0.2% = 44 pts per candle
        if atr_pct > 0.15:
            vol_state = "HIGH"
        elif atr_pct < 0.05:
            vol_state = "LOW"
        else:
            vol_state = "NORMAL"
            
        trend_strength = min(1.0, efficiency * 1.5) # Normalize 0-1
        
        # Base classification variables
        is_high_vol = vol_state == "HIGH"
        is_low_vol = vol_state == "LOW"
        is_trending_up = slope > 1.5 and vwap_dist_pct > 0.03 and efficiency > 0.4
        is_trending_down = slope < -1.5 and vwap_dist_pct < -0.03 and efficiency > 0.4
        is_choppy = efficiency < 0.35
        
        # Rule Evaluation
        if is_high_vol and is_choppy:
            regime = MarketRegime.VOLATILE
            conf = 0.8
            tradability = 0.3
        elif is_low_vol and is_choppy:
            regime = MarketRegime.LOW_VOL
            conf = 0.85
            tradability = 0.2
        elif is_trending_up:
            regime = MarketRegime.TREND_UP
            conf = min(0.95, efficiency + 0.1)
            tradability = 0.9 if vol_expansion > 0.8 else 0.7
        elif is_trending_down:
            regime = MarketRegime.TREND_DOWN
            conf = min(0.95, efficiency + 0.1)
            tradability = 0.9 if vol_expansion > 0.8 else 0.7
        else:
            regime = MarketRegime.RANGE
            conf = 1.0 - efficiency
            tradability = 0.5
            
        # Apply opening gap suppression (Gaps initially suppress tradability and confidence)
        if gap_pct > 0.3: # > ~60 pts on Nifty 22k
            tradability *= 0.8
            conf *= 0.9
            
        return RegimeState(
            regime=regime,
            confidence=max(0.1, min(1.0, conf)),
            volatility_state=vol_state,
            trend_strength=max(0.0, min(1.0, trend_strength)),
            tradability=max(0.0, min(1.0, tradability))
        )
