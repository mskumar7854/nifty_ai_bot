"""
============================================
OPTIONS SELECTOR
============================================
ATM / ITM / OTM strike selection,
symbol building, ladder construction,
and Dhan security-ID lookup helpers.
============================================
"""

from typing import Optional, List
from config import Config


# ══════════════════════════════════════════
# STRIKE SELECTOR
# ══════════════════════════════════════════

class OptionStrikeSelector:
    """Select appropriate Nifty strike for entry."""

    @staticmethod
    def get_atm_strike(spot: float, step: int = Config.STRIKE_STEP) -> int:
        """Nearest strike to spot."""
        return round(spot / step) * step

    @staticmethod
    def get_itm_ce_strike(spot: float, step: int = Config.STRIKE_STEP, steps: int = 1) -> int:
        """CE ITM = strike *below* spot."""
        return OptionStrikeSelector.get_atm_strike(spot, step) - step * steps

    @staticmethod
    def get_itm_pe_strike(spot: float, step: int = Config.STRIKE_STEP, steps: int = 1) -> int:
        """PE ITM = strike *above* spot."""
        return OptionStrikeSelector.get_atm_strike(spot, step) + step * steps

    @staticmethod
    def get_otm_ce_strike(spot: float, step: int = Config.STRIKE_STEP, steps: int = 1) -> int:
        """CE OTM = strike *above* spot."""
        return OptionStrikeSelector.get_atm_strike(spot, step) + step * steps

    @staticmethod
    def get_otm_pe_strike(spot: float, step: int = Config.STRIKE_STEP, steps: int = 1) -> int:
        """PE OTM = strike *below* spot."""
        return OptionStrikeSelector.get_atm_strike(spot, step) - step * steps

    @staticmethod
    def select_strike(
        spot: float,
        option_type: str,
        preference: str = "ATM",
    ) -> int:
        """
        One-stop selector.
        preference: ATM | ITM | OTM
        """
        sel = OptionStrikeSelector
        if preference == "ATM":
            return sel.get_atm_strike(spot)
        if preference == "ITM":
            return (
                sel.get_itm_ce_strike(spot) if option_type == "CE"
                else sel.get_itm_pe_strike(spot)
            )
        if preference == "OTM":
            return (
                sel.get_otm_ce_strike(spot) if option_type == "CE"
                else sel.get_otm_pe_strike(spot)
            )
        return sel.get_atm_strike(spot)

    @staticmethod
    def calculate_moneyness(spot: float, strike: int, option_type: str) -> str:
        """Return ITM | ATM | OTM string."""
        diff_pct = (spot - strike) / strike * 100
        if option_type == "CE":
            return "ITM" if diff_pct > 1 else ("OTM" if diff_pct < -1 else "ATM")
        # PE — reversed logic
        return "ITM" if diff_pct < -1 else ("OTM" if diff_pct > 1 else "ATM")


# ══════════════════════════════════════════
# CONTRACT BUILDER
# ══════════════════════════════════════════

class OptionContractBuilder:
    """Build trading symbols compatible with Dhan API."""

    @staticmethod
    def get_trading_symbol(
        underlying: str,
        strike: int,
        expiry: str,      # e.g. "28DEC" or "03APR"
        option_type: str, # CE | PE
    ) -> str:
        """
        Format: NIFTY03APR22800CE
        Dhan uses this as the human-readable symbol.
        """
        return f"{underlying.upper()}{expiry}{strike}{option_type.upper()}"

    @staticmethod
    def build_symbol(strike: int, expiry_week: str, option_type: str) -> str:
        """Legacy helper — wraps get_trading_symbol with NIFTY default."""
        return OptionContractBuilder.get_trading_symbol(
            Config.UNDERLYING, strike, expiry_week, option_type
        )


# ══════════════════════════════════════════
# STRIKE LADDER
# ══════════════════════════════════════════

class StrikeLadderBuilder:
    """Build a ±N strike ladder around spot for display / analysis."""

    @staticmethod
    def build_ladder(
        spot: float,
        strikes: int = 5,
        step: int = Config.STRIKE_STEP,
    ) -> List[dict]:
        atm = OptionStrikeSelector.get_atm_strike(spot, step)
        ladder = []

        for i in range(-strikes, strikes + 1):
            strike = atm + i * step
            dist_pct = (strike - spot) / spot * 100
            ladder.append({
                'strike': strike,
                'distance': round(strike - spot, 2),
                'distance_pct': round(dist_pct, 3),
                'label': 'ATM' if i == 0 else (f"ITM{abs(i)}" if i < 0 else f"OTM{i}"),
            })

        return ladder


# ══════════════════════════════════════════
# SECURITY-ID STORE
# ══════════════════════════════════════════
# Replace / extend these with live IDs from Dhan's scrip master CSV.
# Download from: https://dhanhq.co → API → Security Master

OPTION_SECURITY_IDS: dict[str, str] = {
    # Placeholder examples — update with live IDs
    "NIFTY03APR22600CE": "11001",
    "NIFTY03APR22600PE": "11002",
    "NIFTY03APR22700CE": "11003",
    "NIFTY03APR22700PE": "11004",
    "NIFTY03APR22800CE": "11005",
    "NIFTY03APR22800PE": "11006",
    "NIFTY03APR22900CE": "11007",
    "NIFTY03APR22900PE": "11008",
    "NIFTY03APR23000CE": "11009",
    "NIFTY03APR23000PE": "11010",
}


def get_option_security_id(symbol: str) -> Optional[str]:
    """Lookup Dhan security ID for a symbol string."""
    return OPTION_SECURITY_IDS.get(symbol)


def get_available_strikes(base: int = 22800, count: int = 10) -> List[int]:
    """Return list of available Nifty strikes around base."""
    return [base + i * Config.STRIKE_STEP for i in range(-count, count + 1)]
