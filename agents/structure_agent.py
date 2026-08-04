"""
============================================
🏗️ MARKET STRUCTURE AGENT

Institutional-grade structure analysis:

1. Swing Highs / Swing Lows (HH, HL, LH, LL)
2. Break of Structure (BOS)
3. Change of Character (CHoCH)
4. Order Blocks (Institutional zones)
5. Fair Value Gaps (FVG / Imbalance)
6. Liquidity Zones (stop clusters)
7. VWAP Structure

This is how SMART MONEY reads the market.
Not indicators. STRUCTURE.
============================================
"""

import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from collections import deque

from agents.base_agent import BaseAgent
from models import (
    AgentOutput, Direction, Strength, MarketSnapshot
)
from utils.indicators import (
    find_swing_points, calculate_vwap,
    calculate_support_resistance,
)
from config.settings import Settings


class StructureAgent(BaseAgent):
    """
    Reads market structure like institutional traders.

    Structure tells you:
    - Is the trend intact or breaking?
    - Where will institutions buy/sell?
    - Where are the stop loss clusters?
    - Is this a continuation or reversal?
    """

    def __init__(self, settings: Settings):
        super().__init__("structure", settings)
        self.th = settings.thresholds

        # Structure state tracking
        self.swing_highs: deque = deque(maxlen=50)
        self.swing_lows: deque = deque(maxlen=50)
        self.structure_type = "UNDEFINED"  # BULLISH | BEARISH | UNDEFINED
        self.last_bos: Optional[Dict] = None
        self.last_choch: Optional[Dict] = None
        self.order_blocks: List[Dict] = []
        self.fair_value_gaps: List[Dict] = []
        self.liquidity_zones: List[Dict] = []

    def analyze(
        self, df: pd.DataFrame, snapshot: MarketSnapshot
    ) -> AgentOutput:

        warnings = []
        details = {}

        if len(df) < 30:
            return self._neutral_output("Insufficient data")

        df = df.tail(500).copy()

        price = snapshot.price

        # ── 1. SWING POINT DETECTION ──
        swings = find_swing_points(
            df['close'],
            order=self.th.structure_swing_order,
        )

        highs = [(i, v) for i, v in swings['highs']]
        lows = [(i, v) for i, v in swings['lows']]

        details["swing_highs"] = len(highs)
        details["swing_lows"] = len(lows)

        # ── 2. STRUCTURE TYPE (HH/HL or LH/LL) ──
        structure_result = self._classify_structure(
            highs, lows
        )
        self.structure_type = structure_result["type"]
        details["structure"] = structure_result

        # ── 3. BREAK OF STRUCTURE (BOS) ──
        bos = self._detect_bos(df, highs, lows)
        if bos["detected"]:
            self.last_bos = bos
            details["bos"] = bos
            warnings.append(
                f"⚡ Break of Structure: {bos['direction']} "
                f"at {bos['level']:.0f}"
            )

        # ── 4. CHANGE OF CHARACTER (CHoCH) ──
        choch = self._detect_choch(df, highs, lows)
        if choch["detected"]:
            self.last_choch = choch
            details["choch"] = choch
            warnings.append(
                f"🔄 Change of Character: "
                f"{choch['from']} → {choch['to']} "
                f"at {choch['level']:.0f}"
            )

        # ── 5. ORDER BLOCKS ──
        obs = self._find_order_blocks(df)
        self.order_blocks = obs
        relevant_obs = [
            ob for ob in obs
            if abs(price - ob['level']) < snapshot.atr * 2
        ]
        details["order_blocks_nearby"] = len(relevant_obs)
        if relevant_obs:
            nearest_ob = min(
                relevant_obs,
                key=lambda x: abs(price - x['level']),
            )
            details["nearest_order_block"] = {
                "level": round(nearest_ob['level'], 0),
                "type": nearest_ob['type'],
                "distance": round(
                    abs(price - nearest_ob['level']), 0
                ),
            }

        # ── 6. FAIR VALUE GAPS ──
        fvgs = self._find_fair_value_gaps(df)
        self.fair_value_gaps = fvgs
        unfilled_fvgs = [
            f for f in fvgs if not f['filled']
        ]
        nearby_fvgs = [
            f for f in unfilled_fvgs
            if abs(price - f['mid']) < snapshot.atr * 3
        ]
        details["unfilled_fvgs"] = len(unfilled_fvgs)
        details["nearby_fvgs"] = len(nearby_fvgs)

        if nearby_fvgs:
            nearest_fvg = min(
                nearby_fvgs,
                key=lambda x: abs(price - x['mid']),
            )
            details["nearest_fvg"] = {
                "high": round(nearest_fvg['high'], 0),
                "low": round(nearest_fvg['low'], 0),
                "type": nearest_fvg['type'],
                "distance": round(
                    abs(price - nearest_fvg['mid']), 0
                ),
            }

        # ── 7. LIQUIDITY ZONES ──
        liq_zones = self._find_liquidity_zones(df, highs, lows)
        self.liquidity_zones = liq_zones
        nearby_liq = [
            z for z in liq_zones
            if abs(price - z['level']) < snapshot.atr * 2
        ]
        details["liquidity_zones_nearby"] = len(nearby_liq)

        if nearby_liq:
            for zone in nearby_liq:
                if abs(price - zone['level']) < snapshot.atr * 0.5:
                    warnings.append(
                        f"⚠️ Near liquidity zone at "
                        f"{zone['level']:.0f} — "
                        f"stop hunt possible"
                    )

        # ── 8. VWAP STRUCTURE ──
        vwap = snapshot.vwap
        vwap_structure = self._analyze_vwap_structure(
            df, price, vwap
        )
        details["vwap_structure"] = vwap_structure

        # ══════════════════════════════════════
        # COMBINE STRUCTURE SIGNALS (Hierarchical Confidence Model)
        # ══════════════════════════════════════

        # Component directional votes
        bos_bull = 1.0 if (bos.get("detected") and bos.get("direction") == "bullish") else 0.0
        bos_bear = 1.0 if (bos.get("detected") and bos.get("direction") == "bearish") else 0.0
        
        choch_bull = 1.0 if (choch.get("detected") and choch.get("to") == "BULLISH") else 0.0
        choch_bear = 1.0 if (choch.get("detected") and choch.get("to") == "BEARISH") else 0.0
        
        macro_bull = 1.0 if self.structure_type == "BULLISH" else 0.0
        macro_bear = 1.0 if self.structure_type == "BEARISH" else 0.0

        # Weighted hierarchy: BOS (60%), CHoCH (20%), Macro Swings (20%)
        weighted_bear_score = 0.60 * bos_bear + 0.20 * choch_bear + 0.20 * macro_bear
        weighted_bull_score = 0.60 * bos_bull + 0.20 * choch_bull + 0.20 * macro_bull

        if weighted_bear_score > weighted_bull_score and weighted_bear_score >= 0.50:
            struct_direction = Direction.BEARISH
            struct_score = min(max(int(weighted_bear_score * 100), 65), 90)
        elif weighted_bull_score > weighted_bear_score and weighted_bull_score >= 0.50:
            struct_direction = Direction.BULLISH
            struct_score = min(max(int(weighted_bull_score * 100), 65), 90)
        elif self.structure_type == "BEARISH":
            struct_direction = Direction.BEARISH
            struct_score = 60
        elif self.structure_type == "BULLISH":
            struct_direction = Direction.BULLISH
            struct_score = 60
        else:
            struct_direction = Direction.NEUTRAL
            struct_score = 40

        details["hierarchical_score"] = {
            "bull_score": round(weighted_bull_score, 2),
            "bear_score": round(weighted_bear_score, 2),
            "dominant": struct_direction.value if hasattr(struct_direction, "value") else str(struct_direction)
        }

        # Order block proximity score
        ob_score = 50
        if relevant_obs:
            nearest = min(relevant_obs, key=lambda x: abs(price - x['level']))
            atr = snapshot.atr or 0
            buffer = min(max(atr * 0.15, 5), 15)
            
            if nearest['low'] - buffer <= price <= nearest['high'] + buffer:
                if nearest['type'] == 'bullish':
                    ob_score = 80
                    details["ob_verdict"] = "At BULLISH order block — buy zone"
                elif nearest['type'] == 'bearish':
                    ob_score = 80
                    details["ob_verdict"] = "At BEARISH order block — sell zone"

        # FVG score
        fvg_score = 50
        if nearby_fvgs:
            fvg_score = 70
            details["fvg_verdict"] = (
                "Price near unfilled FVG — magnet zone"
            )

        # Combine
        factors = {
            "structure": (struct_score, 0.30),
            "events": (event_score, 0.25),
            "order_blocks": (ob_score, 0.20),
            "fvg": (fvg_score, 0.15),
            "liquidity": (
                70 if nearby_liq else 50, 0.10
            ),
        }
        confidence = self._calculate_confidence(factors)

        direction = struct_direction

        if confidence >= 70:
            strength = Strength.STRONG
        elif confidence >= 45:
            strength = Strength.MODERATE
        else:
            strength = Strength.WEAK

        return AgentOutput(
            agent_name=self.name,
            timestamp=datetime.now(),
            direction=direction,
            confidence=round(confidence, 1),
            strength=strength,
            details=details,
            warnings=warnings,
        )

    def _classify_structure(
        self,
        highs: List[Tuple[int, float]],
        lows: List[Tuple[int, float]],
    ) -> Dict:
        """Classify as HH/HL (bullish) or LH/LL (bearish)"""

        if len(highs) < 2 or len(lows) < 2:
            return {"type": "UNDEFINED", "reason": "Not enough swings"}

        # Recent swing analysis
        last_2_highs = [h[1] for h in highs[-2:]]
        last_2_lows = [l[1] for l in lows[-2:]]

        hh = last_2_highs[-1] > last_2_highs[-2]  # Higher High
        hl = last_2_lows[-1] > last_2_lows[-2]    # Higher Low
        lh = last_2_highs[-1] < last_2_highs[-2]  # Lower High
        ll = last_2_lows[-1] < last_2_lows[-2]    # Lower Low

        if hh and hl:
            return {
                "type": "BULLISH",
                "pattern": "Higher Highs + Higher Lows",
                "last_high": round(last_2_highs[-1], 0),
                "last_low": round(last_2_lows[-1], 0),
            }
        elif lh and ll:
            return {
                "type": "BEARISH",
                "pattern": "Lower Highs + Lower Lows",
                "last_high": round(last_2_highs[-1], 0),
                "last_low": round(last_2_lows[-1], 0),
            }
        elif hh and ll:
            return {
                "type": "EXPANDING",
                "pattern": "Expanding range",
                "last_high": round(last_2_highs[-1], 0),
                "last_low": round(last_2_lows[-1], 0),
            }
        elif lh and hl:
            return {
                "type": "CONTRACTING",
                "pattern": "Contracting range (triangle)",
                "last_high": round(last_2_highs[-1], 0),
                "last_low": round(last_2_lows[-1], 0),
            }
        else:
            return {"type": "UNDEFINED", "reason": "Mixed structure"}

    def _detect_bos(
        self,
        df: pd.DataFrame,
        highs: List[Tuple[int, float]],
        lows: List[Tuple[int, float]],
    ) -> Dict:
        """
        Break of Structure:
        - Bullish BOS: Price breaks above a significant swing high
        - Bearish BOS: Price breaks below a significant swing low
        """
        if len(highs) < 2 or len(lows) < 2:
            return {"detected": False}

        price = df['close'].iloc[-1]
        prev_high = highs[-2][1] if len(highs) >= 2 else 0
        prev_low = lows[-2][1] if len(lows) >= 2 else 0

        # Confirmation: need N candles above/below
        confirm = self.th.structure_bos_confirmation

        if price > prev_high:
            # Check confirmation
            recent_closes = df['close'].tail(confirm)
            if all(c > prev_high for c in recent_closes):
                return {
                    "detected": True,
                    "direction": "bullish",
                    "level": prev_high,
                    "confirmed": True,
                }

        if price < prev_low:
            recent_closes = df['close'].tail(confirm)
            if all(c < prev_low for c in recent_closes):
                return {
                    "detected": True,
                    "direction": "bearish",
                    "level": prev_low,
                    "confirmed": True,
                }

        return {"detected": False}

    def _detect_choch(
        self,
        df: pd.DataFrame,
        highs: List[Tuple[int, float]],
        lows: List[Tuple[int, float]],
    ) -> Dict:
        """
        Change of Character:
        - Was making HH/HL → now breaks a HL (bullish → bearish)
        - Was making LH/LL → now breaks a LH (bearish → bullish)
        """
        if len(highs) < 3 or len(lows) < 3:
            return {"detected": False}

        price = df['close'].iloc[-1]

        # Check if structure was bullish and now breaking
        last_3_lows = [l[1] for l in lows[-3:]]
        was_bullish = (
            last_3_lows[-2] > last_3_lows[-3]
        )  # Had HL

        if was_bullish and price < last_3_lows[-2]:
            return {
                "detected": True,
                "from": "BULLISH",
                "to": "BEARISH",
                "level": last_3_lows[-2],
                "type": "HL_BREAK",
            }

        last_3_highs = [h[1] for h in highs[-3:]]
        was_bearish = (
            last_3_highs[-2] < last_3_highs[-3]
        )  # Had LH

        if was_bearish and price > last_3_highs[-2]:
            return {
                "detected": True,
                "from": "BEARISH",
                "to": "BULLISH",
                "level": last_3_highs[-2],
                "type": "LH_BREAK",
            }

        return {"detected": False}

    def _find_order_blocks(
        self, df: pd.DataFrame
    ) -> List[Dict]:
        """
        Order Blocks: The last opposing candle before
        a strong move. Institutional entry zones.

        Bullish OB: Last bearish candle before a rally
        Bearish OB: Last bullish candle before a drop
        """
        order_blocks = []
        lookback = min(
            self.th.structure_ob_lookback, len(df) - 3
        )

        for i in range(3, lookback):
            idx = len(df) - i

            if idx < 1 or idx >= len(df) - 2:
                continue

            curr = df.iloc[idx]
            next1 = df.iloc[idx + 1]
            next2 = df.iloc[idx + 2]

            curr_bearish = curr['close'] < curr['open']
            curr_bullish = curr['close'] > curr['open']

            # Bullish OB: bearish candle followed by 2 strong bullish
            if curr_bearish:
                if (next1['close'] > next1['open'] and
                    next2['close'] > next2['open'] and
                    next2['close'] > curr['high']):
                    order_blocks.append({
                        "type": "bullish",
                        "level": (curr['open'] + curr['close']) / 2,
                        "high": curr['open'],
                        "low": curr['close'],
                        "index": idx,
                    })

            # Bearish OB: bullish candle followed by 2 strong bearish
            if curr_bullish:
                if (next1['close'] < next1['open'] and
                    next2['close'] < next2['open'] and
                    next2['close'] < curr['low']):
                    order_blocks.append({
                        "type": "bearish",
                        "level": (curr['open'] + curr['close']) / 2,
                        "high": curr['close'],
                        "low": curr['open'],
                        "index": idx,
                    })

        return order_blocks[-10:]  # Keep last 10

    def _find_fair_value_gaps(
        self, df: pd.DataFrame
    ) -> List[Dict]:
        """
        Fair Value Gap: A 3-candle pattern where
        candle 1's high doesn't touch candle 3's low
        (or vice versa). Creates an imbalance zone.
        """
        fvgs = []

        for i in range(2, min(50, len(df))):
            idx = len(df) - i

            if idx < 2:
                break

            c1 = df.iloc[idx - 2]
            c2 = df.iloc[idx - 1]
            c3 = df.iloc[idx]

            # Bullish FVG: c1 high < c3 low (gap up)
            if c1['high'] < c3['low']:
                gap_size = (
                    (c3['low'] - c1['high']) /
                    c2['close'] * 100
                )
                if gap_size >= self.th.structure_fvg_min_gap_pct:
                    # Check if filled
                    filled = False
                    for j in range(idx, len(df)):
                        if df['low'].iloc[j] <= c1['high']:
                            filled = True
                            break

                    fvgs.append({
                        "type": "bullish",
                        "high": c3['low'],
                        "low": c1['high'],
                        "mid": (c3['low'] + c1['high']) / 2,
                        "gap_pct": round(gap_size, 3),
                        "filled": filled,
                    })

            # Bearish FVG: c1 low > c3 high (gap down)
            if c1['low'] > c3['high']:
                gap_size = (
                    (c1['low'] - c3['high']) /
                    c2['close'] * 100
                )
                if gap_size >= self.th.structure_fvg_min_gap_pct:
                    filled = False
                    for j in range(idx, len(df)):
                        if df['high'].iloc[j] >= c1['low']:
                            filled = True
                            break

                    fvgs.append({
                        "type": "bearish",
                        "high": c1['low'],
                        "low": c3['high'],
                        "mid": (c1['low'] + c3['high']) / 2,
                        "gap_pct": round(gap_size, 3),
                        "filled": filled,
                    })

        return fvgs

    def _find_liquidity_zones(
        self,
        df: pd.DataFrame,
        highs: List[Tuple[int, float]],
        lows: List[Tuple[int, float]],
    ) -> List[Dict]:
        """
        Liquidity zones: Areas where many stop losses
        are likely clustered (below swing lows, above swing highs).
        """
        zones = []

        # Below each swing low = buy-side liquidity
        for idx, low in lows:
            zones.append({
                "type": "buy_side",
                "level": low,
                "description": f"Stops below swing low {low:.0f}",
            })

        # Above each swing high = sell-side liquidity
        for idx, high in highs:
            zones.append({
                "type": "sell_side",
                "level": high,
                "description": f"Stops above swing high {high:.0f}",
            })

        return zones

    def _analyze_vwap_structure(
        self,
        df: pd.DataFrame,
        price: float,
        vwap: float,
    ) -> Dict:
        """VWAP relationship to price and structure"""

        if vwap <= 0:
            return {"status": "No VWAP data"}

        distance = price - vwap
        distance_pct = (distance / vwap) * 100

        if distance_pct > 0.3:
            return {
                "position": "WELL_ABOVE_VWAP",
                "distance_pct": f"+{distance_pct:.2f}%",
                "bias": "Bullish — buyers in control",
            }
        elif distance_pct > 0.1:
            return {
                "position": "ABOVE_VWAP",
                "distance_pct": f"+{distance_pct:.2f}%",
                "bias": "Mildly bullish",
            }
        elif distance_pct > -0.1:
            return {
                "position": "AT_VWAP",
                "distance_pct": f"{distance_pct:+.2f}%",
                "bias": "Neutral — decision point",
            }
        elif distance_pct > -0.3:
            return {
                "position": "BELOW_VWAP",
                "distance_pct": f"{distance_pct:.2f}%",
                "bias": "Mildly bearish",
            }
        else:
            return {
                "position": "WELL_BELOW_VWAP",
                "distance_pct": f"{distance_pct:.2f}%",
                "bias": "Bearish — sellers in control",
            }

    def get_structure_summary(self) -> Dict:
        """Get current structure state"""
        return {
            "structure_type": self.structure_type,
            "last_bos": self.last_bos,
            "last_choch": self.last_choch,
            "order_blocks": len(self.order_blocks),
            "unfilled_fvgs": len([
                f for f in self.fair_value_gaps
                if not f.get('filled', True)
            ]),
            "liquidity_zones": len(self.liquidity_zones),
        }
