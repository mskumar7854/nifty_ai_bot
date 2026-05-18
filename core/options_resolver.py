"""
============================================
V3 OPTIONS RESOLVER
Bridges AI abstract signals (BUY_CE) to
concrete tradable instruments (e.g., 24400 CE).
============================================
"""

from typing import Optional, List
from datetime import datetime, date, timedelta

class OptionStrikeSelector:
    """Selects the exact strike based on Nifty Spot and strategy."""

    STRIKE_STEP = 50  # Nifty strike step

    @classmethod
    def get_atm_strike(cls, spot: float) -> int:
        """Find the nearest ATM strike."""
        return round(spot / cls.STRIKE_STEP) * cls.STRIKE_STEP

    @classmethod
    def get_itm_strike(cls, spot: float, option_type: str, steps: int = 1) -> int:
        """Find an ITM strike."""
        atm = cls.get_atm_strike(spot)
        if option_type == "CE":
            return atm - (cls.STRIKE_STEP * steps)
        else:
            return atm + (cls.STRIKE_STEP * steps)

    @classmethod
    def get_otm_strike(cls, spot: float, option_type: str, steps: int = 1) -> int:
        """Find an OTM strike."""
        atm = cls.get_atm_strike(spot)
        if option_type == "CE":
            return atm + (cls.STRIKE_STEP * steps)
        else:
            return atm - (cls.STRIKE_STEP * steps)

    @classmethod
    def select_strike(cls, spot: float, option_type: str, confidence: float, regime: str) -> dict:
        """
        Context-Aware Strike Selection.
        """
        strike = cls.get_atm_strike(spot)
        selection_type = "ATM"
        estimated_delta = 0.52

        momentum_strong = regime in ["TRENDING_UP", "TRENDING_DOWN", "BREAKOUT"]
        volatility_high = regime in ["VOLATILE"]

        if confidence >= 75 and not volatility_high:
            strike = cls.get_atm_strike(spot)
            selection_type = "ATM"
            estimated_delta = 0.52
        elif momentum_strong:
            strike = cls.get_itm_strike(spot, option_type, steps=1)
            selection_type = "ITM"
            estimated_delta = 0.65
        elif volatility_high:
            strike = cls.get_itm_strike(spot, option_type, steps=1)
            selection_type = "ITM"
            estimated_delta = 0.60 # Slightly lower delta estimation due to higher premiums in IV crush risk

        return {
            "strike": strike,
            "type": selection_type,
            "delta": estimated_delta
        }

class OptionContractBuilder:
    """Builds the Dhan-compatible symbol and resolves security IDs."""

    @staticmethod
    def get_expiry_str() -> str:
        """Calculates the upcoming Thursday expiry. Format: YYYY-MM-DD"""
        today = date.today()
        days_to_thursday = (3 - today.weekday()) % 7
        if days_to_thursday == 0:
            from datetime import datetime as _dt
            if _dt.now().hour >= 16:
                days_to_thursday = 7
        expiry = today + timedelta(days=days_to_thursday)
        return expiry.strftime("%Y-%m-%d")

    @staticmethod
    def get_trading_symbol(underlying: str, strike: int, option_type: str) -> str:
        """Builds a human readable symbol (e.g., NIFTY 24400 CE)"""
        # Convert e.g., 2026-05-22 to "22 MAY" or just keep the old style if desired
        return f"{underlying.upper()} {strike} {option_type.upper()}"

    @staticmethod
    def resolve_instrument(direction: str, spot: float, confidence: float, regime: str, underlying: str = "NIFTY") -> dict:
        """
        Takes the abstract direction (BULLISH/BEARISH or BUY_CE/BUY_PE)
        and outputs the exact instrument details.
        """
        # 1. Determine Option Type
        opt_type = "CE" if direction in ["BULLISH", "BUY_CE"] else "PE"
        
        # 2. Select Strike
        strike_info = OptionStrikeSelector.select_strike(spot, opt_type, confidence, regime)
        strike = strike_info["strike"]
        
        # 3. Build Symbol
        symbol = OptionContractBuilder.get_trading_symbol(underlying, strike, opt_type)
        
        # 4. Expiry
        expiry = OptionContractBuilder.get_expiry_str()
        
        return {
            "type": opt_type,
            "strike": strike,
            "symbol": symbol,
            "expiry": expiry,
            "moneyness": strike_info["type"],
            "delta": strike_info["delta"],
            "security_id": ""  # To be populated by DataManager via API lookup
        }

class OptionExecutionTranslator:
    """Translates Spot Target/SL levels to Option Premium levels."""

    @staticmethod
    def translate_levels(signal, quote, instrument_info) -> dict:
        premium = quote.ask if quote.ask > 0 else quote.ltp
        if premium <= 0:
            premium = 100.0  # Fallback
            
        delta = instrument_info.get("delta", 0.5)
        spot_entry = signal.entry_price
        
        # SL Translation
        spot_sl_distance = abs(spot_entry - signal.stop_loss)
        premium_sl = max(1.0, premium - (spot_sl_distance * delta))
        
        # Targets Translation
        spot_t1_distance = abs(signal.target_1 - spot_entry) if signal.target_1 else spot_sl_distance * 1.5
        spot_t2_distance = abs(signal.target_2 - spot_entry) if signal.target_2 else spot_sl_distance * 2.5
        spot_t3_distance = abs(signal.target_3 - spot_entry) if signal.target_3 else spot_sl_distance * 3.5
        
        premium_t1 = premium + (spot_t1_distance * delta)
        premium_t2 = premium + (spot_t2_distance * delta)
        premium_t3 = premium + (spot_t3_distance * delta)
        
        # Decay risk (High IV or expiry day = high decay risk)
        decay_risk = "High" if (quote.iv and quote.iv > 20) else "Moderate"
        
        return {
            "premium_entry": round(premium, 1),
            "premium_sl": round(premium_sl, 1),
            "premium_t1": round(premium_t1, 1),
            "premium_t2": round(premium_t2, 1),
            "premium_t3": round(premium_t3, 1),
            "delta_used": delta,
            "decay_risk": decay_risk
        }

