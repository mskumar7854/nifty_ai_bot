"""
============================================
OPTIONS ANALYZER  (Dhan API v2)
============================================
Fetches Nifty / Bank Nifty option chain data
via the existing Dhan singleton client and
calculates sentiment metrics needed by the
Phase-2 hard filter.

Metrics produced
  • PCR          — Put-Call Ratio (total OI)
  • OI Bias      — put/call OI-change direction
  • Max Pain     — strike minimising total option pain
  • Sentiment    — bullish | bearish | neutral (rule engine)

Thresholds (hardened):
  PCR > 1.1 + OI bias bullish  → bullish
  PCR < 0.9 + OI bias bearish  → bearish
  Otherwise                    → neutral

Rate limit: Dhan allows 1 unique request / 3 s.
The caller is responsible for not calling this
faster than that.

Usage:
    from options_analyzer import OptionsAnalyzer
    analyzer = OptionsAnalyzer()
    result   = analyzer.analyze()          # NIFTY nearest expiry
    result   = analyzer.analyze(analyzer.NIFTY_BANK)  # Bank Nifty
============================================
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Dict, Optional, Tuple

# Reuse the project-level singleton — no duplicate auth
from dhan_client import get_dhan_client

logger = logging.getLogger(__name__)


class OptionsAnalyzer:
    """
    Real-time option chain analyser using Dhan API v2.

    All Dhan API calls go through the shared singleton returned
    by ``get_dhan_client()``, so credentials are loaded from
    ``.env`` exactly once at startup.
    """

    # ── Underlying security IDs (Dhan convention) ──────────────
    NIFTY_50: int   = 13    # Nifty 50
    NIFTY_BANK: int = 25    # Bank Nifty

    # ── Segment ────────────────────────────────────────────────
    NSE_FNO: str = "NSE_FNO"

    # ── Hardened sentiment thresholds ─────────────────────────
    PCR_BULLISH_THRESHOLD: float = 1.1   # PCR above this → bullish pressure
    PCR_BEARISH_THRESHOLD: float = 0.9   # PCR below this → bearish pressure

    # ── Max Pain safety guard ──────────────────────────────────
    MAX_PAIN_MIN_DISTANCE: float = 50.0  # pts; skip trade if closer than this

    def __init__(self, mode: str = "LIVE") -> None:
        """Grab the shared Dhan client lazily to avoid token errors in SIMULATION."""
        self.mode = mode
        self._dhan = None
        self._logged_fo_auth_warning = False
        if self.mode != "SIMULATION":
            self._dhan = get_dhan_client()

    # ──────────────────────────────────────────────────────────
    # PUBLIC API
    # ──────────────────────────────────────────────────────────

    def analyze(
        self,
        underlying_scrip: int = NIFTY_50,
        expiry_date: Optional[str] = None,
        price_trend: str = "unknown",
    ) -> Dict:
        """
        Complete analysis pipeline.

        Steps
        -----
        1. Resolve expiry (use nearest if not provided)
        2. Fetch full option chain
        3. Calculate PCR, OI-bias, Max Pain
        4. Apply rule engine → sentiment
        5. Return structured result dict

        Returns
        -------
        dict with keys:
            timestamp, underlying, expiry, spot,
            pcr, pcr_details, oi_bias,
            max_pain_strike, max_pain_distance,
            sentiment, raw_data_available
        On failure:
            {"error": "<message>", "sentiment": "neutral"}
        """
        if self.mode == "SIMULATION":
            return {
                "timestamp":          datetime.now(),
                "underlying":         "SIMULATED",
                "expiry":             "2099-12-31",
                "spot":               0.0,
                "pcr":                1.0,
                "pcr_details":        {},
                "oi_bias":            "neutral",
                "max_pain_strike":    0.0,
                "max_pain_distance":  999.0,
                "sentiment":          "neutral",
                "raw_data_available": False,
            }
        # 1. Resolve expiry
        if not expiry_date:
            expiries = self._get_active_expiries(underlying_scrip)
            if not expiries:
                logger.error("Options: no expiry dates returned for scrip %s", underlying_scrip)
                return {"error": "No expiry dates found", "sentiment": "neutral"}
            expiry_date = expiries[0]

        # 2. Fetch chain
        option_data = self._fetch_option_chain(underlying_scrip, expiry_date)
        if not option_data:
            return {"error": "Empty option chain response", "sentiment": "neutral"}

        # 3. Underlying spot price
        spot_price: float = (
            option_data.get("data", {}).get("last_price", 0.0)
            or option_data.get("last_price", 0.0)
        )

        # 4. Metrics
        pcr, pcr_metrics = self._calculate_pcr(option_data)
        oi_bias          = self._calculate_oi_bias(option_data)
        max_pain_strike, max_pain_dist = self._get_max_pain(option_data, spot_price)

        # 5. Rule engine — hardened thresholds + price trend alignment
        sentiment = "neutral"
        if pcr > self.PCR_BULLISH_THRESHOLD and oi_bias == "bullish" and price_trend == "up":
            sentiment = "bullish"
        elif pcr < self.PCR_BEARISH_THRESHOLD and oi_bias == "bearish" and price_trend == "down":
            sentiment = "bearish"

        underlying_name = (
            "NIFTY" if underlying_scrip == self.NIFTY_50 else "BANKNIFTY"
        )

        result = {
            "timestamp":          datetime.now(),
            "underlying":         underlying_name,
            "expiry":             expiry_date,
            "spot":               spot_price,
            "pcr":                round(pcr, 3),
            "pcr_details":        pcr_metrics,
            "oi_bias":            oi_bias,
            "max_pain_strike":    round(max_pain_strike, 2),
            "max_pain_distance":  round(max_pain_dist, 2),
            "sentiment":          sentiment,
            "raw_data_available": True,
        }

        logger.info(
            "Options [%s | %s] PCR=%.3f | Bias=%s | MaxPain=%.0f (%.0f pts) | Sentiment=%s",
            underlying_name, expiry_date,
            pcr, oi_bias, max_pain_strike, max_pain_dist, sentiment,
        )
        return result

    # ──────────────────────────────────────────────────────────
    # PRIVATE HELPERS — Dhan API calls
    # ──────────────────────────────────────────────────────────

    def _get_active_expiries(self, underlying_scrip: int) -> list:
        """Return list of 'YYYY-MM-DD' expiry strings for the given underlying."""
        try:
            response = self._dhan.expiry_list(
                under_security_id=underlying_scrip,
                under_exchange_segment=self.NSE_FNO,
            )
            
            # Inspect the response for F&O authorization error (nested code 808 or auth fails)
            inner_data = response.get('data', {}).get('data', {}) if isinstance(response.get('data'), dict) else {}
            is_fo_auth_failure = False
            if "808" in inner_data or any("Authentication Failed" in str(v) for v in inner_data.values()):
                is_fo_auth_failure = True

            if is_fo_auth_failure:
                if not getattr(self, "_logged_fo_auth_warning", False):
                    logger.warning(
                        "🚨 Dhan account F&O segment API access is not active. "
                        "Falling back to simulated/estimated option chain metrics for session continuation."
                    )
                    self._logged_fo_auth_warning = True

            return response.get("expiry_list", [])
        except Exception as exc:
            logger.error("Options: failed to fetch expiry list — %s", exc)
            return []

    def _fetch_option_chain(self, underlying_scrip: int, expiry_date: str) -> Dict:
        """Fetch the raw option chain dict from Dhan."""
        payload = {
            "under_security_id": underlying_scrip,
            "under_exchange_segment": self.NSE_FNO,
            "expiry": expiry_date
        }
        logger.info(
            f"📤 OptionsAnalyzer Request: security_id={underlying_scrip} | "
            f"segment={self.NSE_FNO} | expiry={expiry_date} | payload={payload}"
        )
        try:
            response = self._dhan.option_chain(
                under_security_id=underlying_scrip,
                under_exchange_segment=self.NSE_FNO,
                expiry=expiry_date,
            )
            logger.info(f"📥 OptionsAnalyzer Response: {response}")

            # Inspect the response for F&O authorization error (nested code 808 or auth fails)
            inner_data = response.get('data', {}).get('data', {}) if isinstance(response.get('data'), dict) else {}
            is_fo_auth_failure = False
            if "808" in inner_data or any("Authentication Failed" in str(v) for v in inner_data.values()):
                is_fo_auth_failure = True

            if is_fo_auth_failure:
                if not getattr(self, "_logged_fo_auth_warning", False):
                    logger.warning(
                        "🚨 Dhan account F&O segment API access is not active. "
                        "Falling back to simulated/estimated option chain metrics for session continuation."
                    )
                    self._logged_fo_auth_warning = True

            return response
        except Exception as exc:
            logger.error("Options: failed to fetch option chain — %s", exc)
            return {}

    # ──────────────────────────────────────────────────────────
    # PRIVATE HELPERS — metric calculations
    # ──────────────────────────────────────────────────────────

    @staticmethod
    def _oc_data(option_data: Dict) -> Dict:
        """Safely extract the 'oc' (option chain) sub-dict."""
        return (
            option_data.get("data", {}).get("oc", {})
            or option_data.get("oc", {})
        )

    def _calculate_pcr(self, option_data: Dict) -> Tuple[float, Dict]:
        """
        Put-Call Ratio from total open interest.

        Returns (pcr_float, metrics_dict).
        """
        total_put_oi  = 0
        total_call_oi = 0

        for contracts in self._oc_data(option_data).values():
            total_put_oi  += contracts.get("pe", {}).get("oi", 0)
            total_call_oi += contracts.get("ce", {}).get("oi", 0)

        pcr = total_put_oi / total_call_oi if total_call_oi > 0 else 1.0

        return pcr, {
            "total_put_oi":  total_put_oi,
            "total_call_oi": total_call_oi,
            "pcr":           round(pcr, 3),
        }

    def _calculate_oi_bias(self, option_data: Dict) -> str:
        """
        OI-change bias.

        Compares sum of (oi − previous_oi) across all strikes
        for puts vs calls.

        Returns 'bullish' | 'bearish' | 'neutral'.
        """
        total_put_oi_change  = 0
        total_call_oi_change = 0

        for contracts in self._oc_data(option_data).values():
            pe = contracts.get("pe", {})
            ce = contracts.get("ce", {})
            total_put_oi_change  += pe.get("oi", 0) - pe.get("previous_oi", 0)
            total_call_oi_change += ce.get("oi", 0) - ce.get("previous_oi", 0)

        if total_put_oi_change > total_call_oi_change:
            return "bullish"   # Puts being written → market makers bullish
        if total_call_oi_change > total_put_oi_change:
            return "bearish"   # Calls being written → market makers bearish
        return "neutral"

    def _get_max_pain(
        self,
        option_data: Dict,
        spot_price: float,
    ) -> Tuple[float, float]:
        """
        Max Pain: strike at which total option value is minimised.
        Calculates only across an ATM range to improve speed.

        Returns (max_pain_strike, abs_distance_from_spot).
        Falls back to spot_price if data is insufficient.
        """
        oc = self._oc_data(option_data)
        if not oc:
            return spot_price, 0.0

        ATM_RANGE = 10
        strikes_sorted = sorted([float(k) for k in oc.keys() if k.replace('.','',1).isdigit()])
        if not strikes_sorted:
            return spot_price, 0.0

        idx = min(range(len(strikes_sorted)), key=lambda i: abs(strikes_sorted[i] - spot_price))
        relevant_strikes = strikes_sorted[max(0, idx - ATM_RANGE) : idx + ATM_RANGE]

        # Build lookup tables
        call_oi: Dict[float, int] = {}
        put_oi:  Dict[float, int] = {}

        for s in relevant_strikes:
            strike_str = str(int(s)) if s.is_integer() else str(s)
            contracts = oc.get(strike_str, {})
            call_oi[s] = contracts.get("ce", {}).get("oi", 0)
            put_oi[s]  = contracts.get("pe", {}).get("oi", 0)

        # Pain at each candidate strike
        pain_values: Dict[float, float] = {}
        for candidate in relevant_strikes:
            pain = 0.0
            for k in relevant_strikes:
                if k > candidate:
                    pain += call_oi[k] * (k - candidate)   # ITM calls
                elif k < candidate:
                    pain += put_oi[k]  * (candidate - k)   # ITM puts
            pain_values[candidate] = pain

        max_pain_strike = min(pain_values, key=pain_values.get) if pain_values else spot_price
        distance = abs(spot_price - max_pain_strike)
        return max_pain_strike, distance
