"""
============================================
V3 OPTIONS RESOLVER
Bridges AI abstract signals (BUY_CE) to
concrete tradable instruments (e.g., 24400 CE).
============================================
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, date, timedelta
from models.regime import MarketRegime, RegimeContext

# Bidirectional authoritative policy map for all canonical and legacy MarketRegime values
STRIKE_POLICY_MAP: Dict[MarketRegime, Dict[str, Any]] = {
    MarketRegime.STRONG_TREND_UP: {
        "policy": "ITM_1_STEP",
        "moneyness_steps": 1,
        "delta_heuristic": 0.65,
        "reason": "Strong upward momentum; 1-step ITM policy"
    },
    MarketRegime.STRONG_TREND_DOWN: {
        "policy": "ITM_1_STEP",
        "moneyness_steps": 1,
        "delta_heuristic": 0.65,
        "reason": "Strong downward momentum; 1-step ITM policy"
    },
    MarketRegime.BREAKOUT: {
        "policy": "ITM_1_STEP",
        "moneyness_steps": 1,
        "delta_heuristic": 0.65,
        "reason": "Explosive range break; 1-step ITM policy"
    },
    MarketRegime.WEAK_TREND_UP: {
        "policy": "ATM",
        "moneyness_steps": 0,
        "delta_heuristic": 0.52,
        "reason": "Weak trend/pullback; ATM policy"
    },
    MarketRegime.WEAK_TREND_DOWN: {
        "policy": "ATM",
        "moneyness_steps": 0,
        "delta_heuristic": 0.52,
        "reason": "Weak downtrend; ATM policy"
    },
    MarketRegime.RANGING: {
        "policy": "ATM",
        "moneyness_steps": 0,
        "delta_heuristic": 0.50,
        "reason": "Range-bound mean reversion; ATM policy"
    },
    MarketRegime.SQUEEZE: {
        "policy": "ATM",
        "moneyness_steps": 0,
        "delta_heuristic": 0.50,
        "reason": "Volatility compression; ATM policy"
    },
    MarketRegime.VOLATILE_CHOPPY: {
        "policy": "NO_TRADE",
        "moneyness_steps": 0,
        "delta_heuristic": 0.0,
        "reason": "High volatility chop; no trade permitted"
    },
    MarketRegime.UNKNOWN: {
        "policy": "NO_TRADE",
        "moneyness_steps": 0,
        "delta_heuristic": 0.0,
        "reason": "Unknown market regime; fail closed"
    },
    # Legacy alias support
    MarketRegime.TRENDING_UP: {
        "policy": "ITM_1_STEP",
        "moneyness_steps": 1,
        "delta_heuristic": 0.65,
        "reason": "Legacy TRENDING_UP; 1-step ITM"
    },
    MarketRegime.TRENDING_DOWN: {
        "policy": "ITM_1_STEP",
        "moneyness_steps": 1,
        "delta_heuristic": 0.65,
        "reason": "Legacy TRENDING_DOWN; 1-step ITM"
    },
    MarketRegime.VOLATILE: {
        "policy": "NO_TRADE",
        "moneyness_steps": 0,
        "delta_heuristic": 0.0,
        "reason": "Legacy VOLATILE; no trade"
    },
    MarketRegime.LOW_VOL: {
        "policy": "ATM",
        "moneyness_steps": 0,
        "delta_heuristic": 0.50,
        "reason": "Legacy LOW_VOL; ATM policy"
    },
    MarketRegime.TREND_UP: {
        "policy": "ITM_1_STEP",
        "moneyness_steps": 1,
        "delta_heuristic": 0.65,
        "reason": "Legacy TREND_UP; 1-step ITM"
    },
    MarketRegime.TREND_DOWN: {
        "policy": "ITM_1_STEP",
        "moneyness_steps": 1,
        "delta_heuristic": 0.65,
        "reason": "Legacy TREND_DOWN; 1-step ITM"
    },
    MarketRegime.RANGE: {
        "policy": "ATM",
        "moneyness_steps": 0,
        "delta_heuristic": 0.50,
        "reason": "Legacy RANGE; ATM policy"
    }
}


class OptionStrikeSelector:
    """Selects the exact strike based on Nifty Spot, strategy, and canonical regime policy."""

    STRIKE_STEP = 50  # Nifty strike step

    @classmethod
    def get_atm_strike(cls, spot: float) -> int:
        """Find the nearest ATM strike."""
        return round(spot / cls.STRIKE_STEP) * cls.STRIKE_STEP

    @classmethod
    def get_itm_strike(cls, spot: float, option_type: str, steps: int = 1) -> int:
        """Find an ITM strike. CE ITM is spot - steps*50; PE ITM is spot + steps*50."""
        atm = cls.get_atm_strike(spot)
        if option_type == "CE":
            return atm - (cls.STRIKE_STEP * steps)
        else:
            return atm + (cls.STRIKE_STEP * steps)

    @classmethod
    def get_otm_strike(cls, spot: float, option_type: str, steps: int = 1) -> int:
        """Find an OTM strike. CE OTM is spot + steps*50; PE OTM is spot - steps*50."""
        atm = cls.get_atm_strike(spot)
        if option_type == "CE":
            return atm + (cls.STRIKE_STEP * steps)
        else:
            return atm - (cls.STRIKE_STEP * steps)

    @classmethod
    def select_strike(cls, spot: float, option_type: str, confidence: float = 0.0, regime: Any = None) -> dict:
        """
        Context-Aware, Typed Strike Selection with Fail-Closed Invariants.
        """
        atm = cls.get_atm_strike(spot)
        
        # 1. Normalize regime input to MarketRegime enum
        reg_enum = None
        if isinstance(regime, RegimeContext):
            reg_enum = regime.normalized_regime
        elif isinstance(regime, MarketRegime):
            reg_enum = regime
        elif isinstance(regime, str) and regime:
            try:
                reg_enum = MarketRegime[regime.upper()]
            except KeyError:
                try:
                    reg_enum = MarketRegime(regime.upper())
                except ValueError:
                    reg_enum = MarketRegime.UNKNOWN
        else:
            reg_enum = MarketRegime.UNKNOWN

        # 2. Look up policy rule from authoritative map (fail closed if unknown)
        rule = STRIKE_POLICY_MAP.get(reg_enum, STRIKE_POLICY_MAP[MarketRegime.UNKNOWN])
        policy = rule["policy"]

        # 3. High conviction exception (>= 75% confidence on non-blocked regimes retains ATM for efficiency)
        if confidence >= 75 and policy not in ("NO_TRADE", "ITM_1_STEP"):
            policy = "ATM"

        # 4. Resolve strike and build response
        if policy == "NO_TRADE":
            return {
                "atm_strike": atm,
                "selected_strike": None,
                "strike": None,
                "type": "NO_TRADE",
                "selection_type": "NO_TRADE",
                "strike_policy": "NO_TRADE",
                "moneyness_steps": 0,
                "delta_source": "NONE",
                "estimated_delta_heuristic": 0.0,
                "delta": 0.0,  # Legacy compatibility
                "actual_delta": None,
                "actual_iv": None,
                "reason": rule["reason"]
            }
        elif policy == "ITM_1_STEP":
            strike = cls.get_itm_strike(spot, option_type, steps=1)
            return {
                "atm_strike": atm,
                "selected_strike": strike,
                "strike": strike,
                "type": "ITM_1_STEP",
                "selection_type": "ITM_1_STEP",
                "strike_policy": "ITM_1_STEP",
                "moneyness_steps": 1,
                "delta_source": "HEURISTIC",
                "estimated_delta_heuristic": rule["delta_heuristic"],
                "delta": rule["delta_heuristic"],  # Legacy compatibility
                "actual_delta": None,
                "actual_iv": None,
                "reason": rule["reason"]
            }
        else:  # ATM
            strike = atm
            return {
                "atm_strike": atm,
                "selected_strike": strike,
                "strike": strike,
                "type": "ATM",
                "selection_type": "ATM",
                "strike_policy": "ATM",
                "moneyness_steps": 0,
                "delta_source": "HEURISTIC",
                "estimated_delta_heuristic": rule["delta_heuristic"],
                "delta": rule["delta_heuristic"],  # Legacy compatibility
                "actual_delta": None,
                "actual_iv": None,
                "reason": rule["reason"]
            }


class OptionContractBuilder:
    """Builds the Dhan-compatible symbol and resolves security IDs."""

    _cached_expiry = None
    _cached_expiry_date = None

    @classmethod
    def get_expiry_str(cls) -> str:
        """Fetches the exact active expiry from Dhan API to prevent 811 errors."""
        today = date.today()
        if cls._cached_expiry and cls._cached_expiry_date == today:
            return cls._cached_expiry
            
        try:
            from dhan_client import get_dhan_client
            dhan = get_dhan_client()
            resp = dhan.expiry_list(13, "IDX_I")  # 13 = NIFTY 50
            if resp.get("status") == "success" and resp.get("data"):
                raw_data = resp["data"]
                expiry_list = raw_data.get("data", []) if isinstance(raw_data, dict) else (raw_data if isinstance(raw_data, list) else [])
                if expiry_list:
                    cls._cached_expiry = expiry_list[0]
                    cls._cached_expiry_date = today
                    return cls._cached_expiry
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Expiry resolution fallback triggered due to: {e}")
            pass
            
        # Fallback math if API fails
        days_to_thursday = (3 - today.weekday()) % 7
        if days_to_thursday == 0:
            from datetime import datetime as _dt
            if _dt.now().hour >= 16:
                days_to_thursday = 7
        expiry = today + timedelta(days=days_to_thursday)
        return expiry.strftime("%Y-%m-%d")

    @classmethod
    def get_expiry_context(cls) -> dict:
        """Returns detailed context about the active expiry."""
        expiry_str = cls.get_expiry_str()
        today = date.today()
        
        try:
            expiry_date = datetime.strptime(expiry_str, "%Y-%m-%d").date()
        except Exception:
            expiry_date = today
            
        days_to_expiry = (expiry_date - today).days
        if days_to_expiry < 0:
            days_to_expiry = 0
            
        is_expiry_day = (days_to_expiry == 0)
        
        # Monthly expiry check (if expiry is in the last 7 days of its month)
        next_week = expiry_date + timedelta(days=7)
        is_monthly_expiry = (next_week.month != expiry_date.month)
        expiry_type = "monthly" if is_monthly_expiry else "weekly"
        
        return {
            "is_expiry_day": is_expiry_day,
            "days_to_expiry": days_to_expiry,
            "expiry_type": expiry_type,
            "expiry_date_str": expiry_str
        }

    @staticmethod
    def get_trading_symbol(underlying: str, strike: Optional[int], option_type: str) -> str:
        """Builds a human readable symbol (e.g., NIFTY 24400 CE)"""
        if strike is None:
            return f"{underlying.upper()} NO_STRIKE {option_type.upper()}"
        return f"{underlying.upper()} {strike} {option_type.upper()}"

    @staticmethod
    def resolve_instrument(direction: str, spot: float, confidence: float, regime: Any, underlying: str = "NIFTY") -> dict:
        """
        Takes the abstract direction (BULLISH/BEARISH or BUY_CE/BUY_PE)
        and outputs the complete, typed instrument details.
        """
        # 1. Determine Option Type
        opt_type = "CE" if direction in ["BULLISH", "BUY_CE"] else "PE"
        
        # 2. Select Strike via Context-Aware Selector
        strike_info = OptionStrikeSelector.select_strike(spot, opt_type, confidence, regime)
        strike = strike_info["strike"]
        
        # 3. Build Symbol
        symbol = OptionContractBuilder.get_trading_symbol(underlying, strike, opt_type) if strike else ""
        
        # 4. Expiry
        expiry = OptionContractBuilder.get_expiry_str()
        
        return {
            "type": opt_type,
            "strike": strike,
            "symbol": symbol,
            "expiry": expiry,
            "atm_strike": strike_info["atm_strike"],
            "selected_strike": strike_info["selected_strike"],
            "moneyness": strike_info["selection_type"],
            "selection_type": strike_info["selection_type"],
            "strike_policy": strike_info["strike_policy"],
            "moneyness_steps": strike_info["moneyness_steps"],
            "selection_reason": strike_info["reason"],
            "delta_source": strike_info["delta_source"],
            "estimated_delta_heuristic": strike_info["estimated_delta_heuristic"],
            "delta": strike_info["estimated_delta_heuristic"],  # Legacy compatibility
            "actual_delta": None,
            "actual_iv": None,
            "spread_pct": None,
            "volume": None,
            "security_id": ""  # To be populated by DataManager via API lookup
        }


class OptionExecutionTranslator:
    """
    Translates Spot Target/SL levels to Option Premium levels.
    Treats delta-scaling strictly as a fallback approximation.
    """

    @staticmethod
    def translate_levels(signal, quote, instrument_info) -> dict:
        premium = quote.ask if quote and getattr(quote, 'ask', 0) > 0 else (quote.ltp if quote and getattr(quote, 'ltp', 0) > 0 else 100.0)
        
        # Determine delta and provenance
        if instrument_info.get("actual_delta") is not None:
            delta = instrument_info["actual_delta"]
            delta_source = "ACTUAL"
        elif instrument_info.get("estimated_delta_heuristic") is not None:
            delta = instrument_info["estimated_delta_heuristic"]
            delta_source = "HEURISTIC"
        else:
            delta = 0.50
            delta_source = "DEFAULT"
            
        spot_entry = signal.entry_price
        
        # SL Translation (Fallback approximation)
        spot_sl_distance = abs(spot_entry - signal.stop_loss)
        raw_premium_sl_dist = spot_sl_distance * delta
        
        # Enforce a 15% minimum floor so normal premium chop doesn't stop out good spot signals
        safe_sl_dist = max(raw_premium_sl_dist, premium * 0.15, 5.0)
        premium_sl = max(1.0, premium - safe_sl_dist)
        
        # Targets Translation (Relative to the safe sl distance)
        spot_t1_distance = abs(signal.target_1 - spot_entry) if signal.target_1 else spot_sl_distance * 1.5
        spot_t2_distance = abs(signal.target_2 - spot_entry) if signal.target_2 else spot_sl_distance * 2.5
        spot_t3_distance = abs(signal.target_3 - spot_entry) if signal.target_3 else spot_sl_distance * 3.5
        
        premium_t1 = premium + max(spot_t1_distance * delta, safe_sl_dist * 1.5)
        premium_t2 = premium + max(spot_t2_distance * delta, safe_sl_dist * 2.5)
        premium_t3 = premium + max(spot_t3_distance * delta, safe_sl_dist * 3.5)
        
        # Decay risk (High IV or expiry day = high decay risk)
        decay_risk = "High" if (quote and getattr(quote, 'iv', None) and quote.iv > 20) else "Moderate"
        
        return {
            "premium_entry": round(premium, 1),
            "premium_sl": round(premium_sl, 1),
            "premium_t1": round(premium_t1, 1),
            "premium_t2": round(premium_t2, 1),
            "premium_t3": round(premium_t3, 1),
            "delta_used": delta,
            "delta_source": delta_source,
            "pricing_method": "DELTA_APPROXIMATION",
            "decay_risk": decay_risk
        }
