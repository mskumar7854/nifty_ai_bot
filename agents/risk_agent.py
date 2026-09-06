"""
============================================
🧮 RISK MANAGEMENT AGENT
Calculates: Position size, Stop loss,
            Daily limits, Risk per trade
============================================
"""

import pandas as pd
from datetime import datetime, date

from agents.base_agent import BaseAgent
from models import AgentOutput, Direction, Strength, MarketSnapshot
from config.settings import Settings
from utils.helpers import safe_divide


class RiskAgent(BaseAgent):
    """
    The GATEKEEPER agent.
    Determines HOW MUCH to trade and WHEN TO STOP.
    Overrides all other agents if risk limits are breached.
    """

    def __init__(self, settings: Settings):
        super().__init__("risk", settings)
        self.trading_config = settings.trading

        # Daily tracking
        self.daily_trades = 0
        self.daily_pnl = 0.0
        self.current_date = None
        self.trade_history_today: list = []

    def analyze(
        self, df: pd.DataFrame, snapshot: MarketSnapshot
    ) -> AgentOutput:
        """
        Risk pipeline:
        1. Check daily limits
        2. Calculate position size based on ATR
        3. Determine stop loss levels
        4. Risk/reward assessment
        """

        warnings = []
        details = {}

        # Reset daily counters if new day
        current_snap_date = snapshot.timestamp.date() if snapshot.timestamp else date.today()
        if current_snap_date != self.current_date:
            self._reset_daily(current_snap_date)

        # ── 1. DAILY LIMIT CHECK ──
        can_trade = True

        if self.daily_trades >= self.trading_config.max_daily_trades:
            can_trade = False
            warnings.append(
                f"🚫 MAX TRADES REACHED ({self.daily_trades}/"
                f"{self.trading_config.max_daily_trades})"
            )
            details["trade_limit"] = "REACHED"

        if abs(self.daily_pnl) >= self.trading_config.max_daily_loss and \
           self.daily_pnl < 0:
            can_trade = False
            warnings.append(
                f"🚫 MAX DAILY LOSS REACHED (₹{self.daily_pnl:,.0f})"
            )
            details["loss_limit"] = "REACHED"

        details["trades_today"] = f"{self.daily_trades}/{self.trading_config.max_daily_trades}"
        details["daily_pnl"] = f"₹{self.daily_pnl:,.0f}"

        # ── 2. POSITION SIZE CALCULATION ──
        atr = snapshot.atr
        capital = self.trading_config.capital
        risk_pct = self.trading_config.max_risk_per_trade / 100

        max_risk_amount = capital * risk_pct  # e.g., 2% of 1L = 2000

        if atr > 0:
            # Risk-based position sizing
            risk_per_unit = atr * 1.5  # SL at 1.5x ATR
            position_size = int(max_risk_amount / risk_per_unit)
            # Round to lot size
            lot_size = self.trading_config.default_qty
            position_size = max(lot_size, (position_size // lot_size) * lot_size)
        else:
            position_size = self.trading_config.default_qty
            risk_per_unit = 0

        details["position_size"] = position_size
        details["max_risk_amount"] = f"₹{max_risk_amount:,.0f}"
        details["atr"] = f"{atr:.1f}"

        # ── 3. STOP LOSS CALCULATION ──
        price = snapshot.price
        sl_distance = atr * 1.5

        sl_long = price - sl_distance
        sl_short = price + sl_distance

        # Targets (1:2 and 1:3 R:R)
        target1_long = price + (sl_distance * 2)
        target2_long = price + (sl_distance * 3)
        target1_short = price - (sl_distance * 2)
        target2_short = price - (sl_distance * 3)

        details["sl_long"] = round(sl_long, 1)
        details["sl_short"] = round(sl_short, 1)
        details["target1_long"] = round(target1_long, 1)
        details["target2_long"] = round(target2_long, 1)
        details["target1_short"] = round(target1_short, 1)
        details["target2_short"] = round(target2_short, 1)
        details["sl_distance"] = round(sl_distance, 1)

        # ── 4. RISK SCORE ──
        risk_factors = []

        # ATR-based volatility risk
        if atr > 50:
            risk_factors.append("High volatility (wide ATR)")
            vol_risk = 40
        elif atr > 30:
            vol_risk = 60
        else:
            vol_risk = 80

        # VIX risk
        vix = snapshot.india_vix
        if vix > 18:
            risk_factors.append("High VIX environment")
            vix_risk = 35
        elif vix > 14:
            vix_risk = 60
        else:
            vix_risk = 80

        # Daily P&L risk
        if self.daily_pnl < -(self.trading_config.max_daily_loss * 0.5):
            risk_factors.append("Already lost 50%+ of daily limit")
            pnl_risk = 30
        elif self.daily_pnl < 0:
            pnl_risk = 50
        else:
            pnl_risk = 80

        # Trade count risk
        remaining = self.trading_config.max_daily_trades - self.daily_trades
        if remaining <= 1:
            risk_factors.append("Last trade of the day")
            count_risk = 40
        else:
            count_risk = 70

        details["risk_factors"] = risk_factors

        # ── COMBINE ──
        if not can_trade:
            confidence = 0
            direction = Direction.NEUTRAL
            strength = Strength.WEAK
            details["verdict"] = "🚫 TRADING HALTED — Limits reached"
        else:
            factors = {
                "volatility": (vol_risk, 0.3),
                "vix": (vix_risk, 0.25),
                "pnl": (pnl_risk, 0.25),
                "count": (count_risk, 0.2),
            }
            confidence = self._calculate_confidence(factors)
            direction = Direction.NEUTRAL  # Risk agent doesn't set direction
            strength = (
                Strength.STRONG if confidence >= 65
                else Strength.MODERATE if confidence >= 40
                else Strength.WEAK
            )

            if confidence >= 65:
                details["verdict"] = "✅ RISK OK — Clear to trade"
            elif confidence >= 40:
                details["verdict"] = "⚠️ RISK MODERATE — Reduce size"
                warnings.append("Consider half position size")
            else:
                details["verdict"] = "🚫 RISK HIGH — Skip this trade"
                warnings.append("Risk conditions unfavorable")

        return AgentOutput(
            agent_name=self.name,
            timestamp=snapshot.timestamp,
            direction=direction,
            confidence=round(confidence, 1),
            strength=strength,
            details=details,
            warnings=warnings,
        )

    def record_trade(self, pnl: float, timestamp: datetime = None):
        """Record a trade result"""
        self.daily_trades += 1
        self.daily_pnl += pnl
        self.trade_history_today.append({
            "time": timestamp or datetime.now(),
            "pnl": pnl,
            "cumulative": self.daily_pnl,
        })

    def _reset_daily(self, new_date: date = None):
        """Reset daily counters"""
        self.current_date = new_date or date.today()
        self.daily_trades = 0
        self.daily_pnl = 0.0
        self.trade_history_today = []

    def get_trade_params(
        self, direction: Direction, price: float, atr: float
    ) -> dict:
        """Get specific trade parameters for a signal"""
        sl_distance = atr * 1.5

        capital = self.trading_config.capital
        risk_pct = self.trading_config.max_risk_per_trade / 100
        max_risk_amount = capital * risk_pct
        
        if atr > 0:
            risk_per_unit = atr * 1.5
            position_size = int(max_risk_amount / risk_per_unit)
            lot_size = self.trading_config.default_qty
            position_size = max(lot_size, (position_size // lot_size) * lot_size)
        else:
            position_size = self.trading_config.default_qty

        if direction == Direction.BULLISH:
            return {
                "entry": price,
                "stop_loss": round(price - sl_distance, 1),
                "target_1": round(price + sl_distance * 2, 1),
                "target_2": round(price + sl_distance * 3, 1),
                "position_size": position_size,
            }
        elif direction == Direction.BEARISH:
            return {
                "entry": price,
                "stop_loss": round(price + sl_distance, 1),
                "target_1": round(price - sl_distance * 2, 1),
                "target_2": round(price - sl_distance * 3, 1),
                "position_size": position_size,
            }
        return {}
