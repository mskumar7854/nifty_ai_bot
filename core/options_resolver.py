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
    def select_strike_by_quality(cls, spot: float, option_type: str, quality: str) -> int:
        """
        Delta-Aware Strike Selection (Phase B)
        - STRONG Quality: slightly OTM or ATM for gamma explosion
        - MODERATE Quality: ATM
        - WEAK Quality: ITM (defensive)
        """
        # For Phase A, we can keep it simple: always use ATM.
        # But setting up the structure for Phase B.
        if quality == "STRONG":
            return cls.get_atm_strike(spot)  # In Phase B, maybe OTM
        elif quality == "MODERATE":
            return cls.get_atm_strike(spot)
        else:
            return cls.get_itm_strike(spot, option_type, steps=1)

class OptionContractBuilder:
    """Builds the Dhan-compatible symbol and resolves security IDs."""

    @staticmethod
    def get_expiry_str() -> str:
        """Calculates the upcoming Thursday expiry. Format: YYYY-MM-DD"""
        today = date.today()
        days_to_thursday = (3 - today.weekday()) % 7
        expiry = today + timedelta(days=days_to_thursday)
        return expiry.strftime("%Y-%m-%d")

    @staticmethod
    def get_trading_symbol(underlying: str, strike: int, option_type: str) -> str:
        """Builds a human readable symbol (e.g., NIFTY 24400 CE)"""
        return f"{underlying.upper()} {strike} {option_type.upper()}"

    @staticmethod
    def resolve_instrument(direction: str, spot: float, quality: str = "MODERATE", underlying: str = "NIFTY") -> dict:
        """
        Takes the abstract direction (BULLISH/BEARISH or BUY_CE/BUY_PE)
        and outputs the exact instrument details.
        """
        # 1. Determine Option Type
        opt_type = "CE" if direction in ["BULLISH", "BUY_CE"] else "PE"
        
        # 2. Select Strike
        strike = OptionStrikeSelector.select_strike_by_quality(spot, opt_type, quality)
        
        # 3. Build Symbol
        symbol = OptionContractBuilder.get_trading_symbol(underlying, strike, opt_type)
        
        # 4. Expiry
        expiry = OptionContractBuilder.get_expiry_str()
        
        return {
            "type": opt_type,
            "strike": strike,
            "symbol": symbol,
            "expiry": expiry,
            "security_id": ""  # To be populated by DataManager via API lookup
        }
