"""
============================================
DATA MANAGER
Handles all data fetching, caching, and
preparation for agents
============================================
"""

import aiohttp
import pandas as pd
import numpy as np
import time
from datetime import datetime, timedelta
from typing import Optional, Tuple

from models.signals import MarketSnapshot, DataSource, OptionQuote
from utils.indicators import (
    calculate_vwap, calculate_rsi, calculate_ema, calculate_atr
)
from utils.logger import get_logger
from config.settings import Settings
from dhan_client import get_dhan_client
from core.regime_classifier import RegimeClassifier
from core.regime_state_manager import RegimeStateManager
from config.config import OPTION_CHAIN_SEGMENT, CANDLE_SEGMENT


class DataManager:
    """
    Central data hub for the entire system.
    Currently uses simulated data.
    Ready to plug in real API (Zerodha, etc.)
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self.logger = get_logger("data_manager")
        self.data_source = settings.data_source

        # Data storage
        self.ohlcv_data: Optional[pd.DataFrame] = None
        self.df_1m: Optional[pd.DataFrame] = None
        self.df_5m: Optional[pd.DataFrame] = None
        self.tick_count = 0

        # API Throttling & Cache
        self.last_fetch_time = datetime.min
        self.fetch_interval_seconds = 1.0  # Safe throttle
        self.prev_day_close: Optional[float] = None
        self._day_open: Optional[float] = None   # today's first candle open
        self._api_security_id = None
        # ── Spot index candles live in IDX_I (Option chains live in NSE_FNO) ──
        self._api_exchange_segment = CANDLE_SEGMENT
        self._api_instrument_type = "INDEX"
        self._logged_fo_auth_warning = False
        self._api_failures = 0
        self._api_circuit_breaker_until = 0.0
        self.oi_circuit = {
            "open_until": 0.0,
            "reason": None,
            "failure_count": 0,
            "last_error": None
        }

        # ── API Polling Telemetry & Cadence Cooldown (Phase 2 Optimization) ──
        self._last_api_fetch_ts = 0.0
        self._api_fetch_cooldown = 1.0  # seconds (reduced from 10 to keep DataHealth FRESH)
        self._api_cache_hit_count = 0
        self._api_fetch_count = 0
        self._api_total_latency_ms = 0.0

        # ── Incremental Engine Metadata ──
        self._warmup_complete = False
        self.last_successful_fetch_ts = 0.0
        self.last_new_candle_ts = 0.0
        self.last_incremental_latency_ms = 0.0

        # ── Market Activity Tracking (mutation-based freshness) ──
        # Updated whenever ANY OHLCV value changes on the latest candle,
        # not just when a new candle timestamp appears.
        # This correctly models discrete-time candle feeds where the
        # active candle mutates continuously during its minute.
        self.last_market_activity_ts: datetime | None = None
        self._last_ohlcv_fingerprint: tuple | None = None

        # ── Real OI Cache (refreshed every 60s) ──
        self._oi_cache: dict = {}
        self._oi_last_fetch: float = 0.0
        self._oi_fetch_interval: float = 60.0  # seconds

        # ── OI Health Tracking ──
        self._oi_fail_count: int = 0      # total failures this session
        self._oi_success_count: int = 0   # total successes this session
        self._oi_last_success_ts: float = 0.0  # epoch of last successful fetch
        self._oi_last_fetch_ms: float = 0.0    # latency of last fetch attempt

        # Simulated state
        self._sim_price = 23400.0
        self._sim_trend = 1
        self._sim_vix = 13.5

        # ── ⚡ HFT DELTA CACHE ──
        self.cached_ema_fast: Optional[float] = None
        self.cached_ema_slow: Optional[float] = None
        self.cached_rsi_avg_gain: Optional[float] = None
        self.cached_rsi_avg_loss: Optional[float] = None
        self.cached_atr: Optional[float] = None
        self.cached_vwap_tp_sum: float = 0.0
        self.cached_vwap_vol_sum: float = 0.0

        # Phase 1: Market Regime Classifier (Wrapped with Hysteresis)
        self.regime_classifier = RegimeStateManager(
            classifier=RegimeClassifier(lookback=20),
            confirm_threshold=3
        )

        self.logger.info(f"DataManager initialized | Source: {self.data_source}")

    # Removed legacy get_latest_data, get_snapshot, and fetch_latest

    async def startup_bootstrap(self, session: aiohttp.ClientSession = None) -> None:
        """BOOT-TIME ONLY: Fetch historical data, initialize dataframe, and validate warmup."""
        import asyncio
        self.logger.info("🚀 USING BOOTSTRAP HYDRATION PATH")
        if self.data_source == "simulated":
            df = self._fetch_simulated()
            if df is not None and not df.empty:
                self.ohlcv_data = df
                self._warmup_complete = True
            return

        if self.data_source == "api":
            df = await asyncio.to_thread(self._fetch_history_for_bootstrap)
            if df is not None and not df.empty:
                self.logger.info("✅ Bootstrap completed successfully. Setting _warmup_complete = True")
                self._warmup_complete = True
            else:
                self.logger.error("❌ Bootstrap failed or returned empty df. _warmup_complete remains False.")
        else:
            self._fetch_simulated()
            self._warmup_complete = True

    async def update_latest_candle_async(self, session: aiohttp.ClientSession) -> Tuple[pd.DataFrame, MarketSnapshot]:
        """
        🚀 RUNTIME HFT DATA FETCH
        Fetches incremental data without blocking and returns (df, snapshot).
        """
        import asyncio
        
        if not getattr(self, '_warmup_complete', False):
            self.logger.warning("⚠️ update_latest_candle_async called before warmup! Forcing bootstrap.")
            await self.startup_bootstrap(session)
            
        if self.data_source == "simulated":
            df = self._fetch_simulated()
        elif self.data_source == "api":
            self.logger.debug("⚡ USING INCREMENTAL PATH")
            df = await asyncio.to_thread(self._fetch_from_api_incremental)
        else:
            df = self._fetch_simulated()

        if df is not None and not df.empty:
            self.ohlcv_data = df
            self.last_fetch_time = datetime.now()

            # ── Market mutation detection ──
            # Track whether the latest candle's OHLCV values actually changed.
            # This is the authoritative signal for "market is alive" —
            # NOT the candle timestamp (which stays fixed within each minute).
            try:
                last_row = df.iloc[-1]
                fingerprint = (
                    float(last_row.get('open', 0)),
                    float(last_row.get('high', 0)),
                    float(last_row.get('low', 0)),
                    float(last_row.get('close', 0)),
                    float(last_row.get('volume', 0)),
                )
                if fingerprint != self._last_ohlcv_fingerprint:
                    self._last_ohlcv_fingerprint = fingerprint
                    self.last_market_activity_ts = datetime.now()
            except Exception:
                pass  # Don't let mutation tracking break the hot path

        snapshot = await asyncio.to_thread(self.get_snapshot_incremental, df)
        return df, snapshot

    def _get_oi_data(self) -> dict:
        """
        🟢 REAL OI DATA FETCHER
        Pulls option chain from Dhan API and extracts:
          - total_ce_oi, total_pe_oi, pcr, max_pain, india_vix
          - max_ce_oi_strike, max_pe_oi_strike

        - Runs on a 60s cache to avoid API rate limits.
        - Retries up to 3 times on transient failure (with 1s/2s/4s backoff).
        - Logs every 5th failure at WARNING (not just the first).
        - Falls back to simulated data only after all retries exhausted.
        - Sets DataSource.REAL flag when successful.
        - Tracks OI health metrics: _oi_fail_count, _oi_success_count, _oi_last_fetch_ms.

        Segment: NSE_FNO (required for option chain — IDX_I is index spot only).
        security_id: cast to int before API call (Dhan API is type-strict).
        """
        import time as _time
        now = _time.time()

        # Return cache if fresh
        if self._oi_cache and (now - self._oi_last_fetch) < self._oi_fetch_interval:
            return self._oi_cache

        if self.data_source != "api":
            return {'data_source': DataSource.SIMULATED}  # Caller will use simulated fallback

        # Check circuit breaker
        if now < self.oi_circuit["open_until"]:
            if not self.oi_circuit.get("warning_logged", False):
                cooldown_rem = int(self.oi_circuit["open_until"] - now)
                self.logger.warning(
                    f"[DATAMANAGER] OI circuit breaker OPEN — skipping fetch. "
                    f"Cooldown remaining: {cooldown_rem}s. Last error: {self.oi_circuit['last_error']}"
                )
                self.oi_circuit["warning_logged"] = True
            
            # Cache the circuit breaker simulated result to reduce CPU and check interval
            fallback = {'data_source': DataSource.SIMULATED}
            self._oi_cache = fallback
            self._oi_last_fetch = now
            return fallback
        else:
            self.oi_circuit["warning_logged"] = False

        # ── Expiry resolution (Dynamic via Resolver) ──
        from core.options_resolver import OptionContractBuilder
        expiry_str = OptionContractBuilder.get_expiry_str()

        try:
            dhan = get_dhan_client()

            if self._api_security_id is None:
                self._api_security_id = self._discover_nifty_id(dhan)

            # ── FIX: security_id must be int for Dhan API ──
            security_id_int = int(self._api_security_id)

            # Construct and log the full raw request payload
            payload_log = {
                "security_id": security_id_int,
                "exchange_segment": "IDX_I",
                "expiry": expiry_str,
                "underlying": "NIFTY",
                "request_json": {
                    "UnderlyingScrip": security_id_int,
                    "UnderlyingSeg": "IDX_I",
                    "Expiry": expiry_str
                }
            }
            self.logger.info(f"📤 Sending Option Chain Request: {payload_log}")

            # ── Retry loop: 3 attempts with exponential backoff ──
            response = None
            last_error = None
            t_fetch_start = _time.perf_counter()

            for attempt in range(3):
                try:
                    response = dhan.option_chain(
                        under_security_id=security_id_int,
                        under_exchange_segment="IDX_I",
                        expiry=expiry_str
                    )
                    # Log the full raw response body
                    self.logger.info(f"📥 Received Option Chain Response: {response}")

                    if response.get('status') == 'success':
                        break  # Success — exit retry loop
                    
                    last_error = response.get('remarks', 'unknown')
                    
                    # Inspect the response for non-retryable errors
                    inner_data = response.get('data', {}).get('data', {}) if isinstance(response.get('data'), dict) else {}
                    error_str = str(last_error) + " " + str(inner_data) + " " + str(response)
                    
                    is_non_retryable = False
                    error_code = None
                    for err in ["805", "808", "permission_denied", "invalid_client"]:
                        if err in error_str:
                            error_code = err
                            is_non_retryable = True
                            break
                            
                    if is_non_retryable:
                        self.oi_circuit.update({
                            "open_until": _time.time() + 900,
                            "reason": "AUTH_FAILURE" if error_code == "808" else "RATE_LIMIT" if error_code == "805" else "PERMISSION_DENIED",
                            "failure_count": self.oi_circuit["failure_count"] + 1,
                            "last_error": error_code
                        })
                        self.logger.warning(
                            f"🚨 DataManager: Non-retryable error {error_code} detected! "
                            f"Tripping circuit breaker for 15 minutes."
                        )
                        break  # Halt retries immediately
                    
                    if attempt < 2:
                        _time.sleep(2 ** attempt)  # 1s, 2s backoff
                except Exception as retry_exc:
                    last_error = str(retry_exc)
                    # Also check exception message for non-retryable errors
                    is_non_retryable = False
                    error_code = None
                    for err in ["805", "808", "permission_denied", "invalid_client"]:
                        if err in last_error:
                            error_code = err
                            is_non_retryable = True
                            break
                            
                    if is_non_retryable:
                        self.oi_circuit.update({
                            "open_until": _time.time() + 900,
                            "reason": "AUTH_FAILURE" if error_code == "808" else "RATE_LIMIT" if error_code == "805" else "PERMISSION_DENIED",
                            "failure_count": self.oi_circuit["failure_count"] + 1,
                            "last_error": error_code
                        })
                        self.logger.warning(
                            f"🚨 DataManager: Non-retryable exception {error_code} detected! "
                            f"Tripping circuit breaker for 15 minutes."
                        )
                        break  # Immediately halt further retries
                        
                    if attempt < 2:
                        _time.sleep(2 ** attempt)

            self._oi_last_fetch_ms = ((_time.perf_counter() - t_fetch_start) * 1000)

            if response is None or response.get('status') != 'success':
                # Parse and inspect the response for F&O authorization error (nested code 808 or auth fails)
                is_fo_auth_failure = False
                if response is not None:
                    inner_data = response.get('data', {}).get('data', {}) if isinstance(response.get('data'), dict) else {}
                    if "808" in inner_data or any("Authentication Failed" in str(v) for v in inner_data.values()):
                        is_fo_auth_failure = True
                
                if is_fo_auth_failure:
                    if not self._logged_fo_auth_warning:
                        self.logger.warning(
                            "🚨 Dhan account F&O segment API access is not active. "
                            "Falling back to simulated/estimated option chain metrics for session continuation."
                        )
                        self._logged_fo_auth_warning = True

                # ── Per-count failure logging (not just first-occurrence) ──
                self._oi_fail_count += 1
                if self._oi_fail_count % 5 == 1:  # log 1st, 6th, 11th...
                    self.logger.warning(
                        f"⚠️ OI Fetch FAILED (#{self._oi_fail_count}) | "
                        f"security_id={security_id_int} | "
                        f"segment={OPTION_CHAIN_SEGMENT} | "
                        f"expiry={expiry_str} | "
                        f"status={response.get('status') if response else 'no_response'} | "
                        f"remarks={response.get('remarks') if response else last_error} | "
                        f"fetch_ms={self._oi_last_fetch_ms:.0f}"
                    )
                else:
                    self.logger.debug(
                        f"OI Fetch failed (#{self._oi_fail_count}): {last_error}"
                    )
                
                # Cache the failure fallback result to reduce processing and checks
                fallback = {'data_source': DataSource.SIMULATED, 'fetch_ms': self._oi_last_fetch_ms}
                self._oi_cache = fallback
                self._oi_last_fetch = now
                return fallback

            # ── Parse option chain ──
            # Handle both: response['data']['data'] and response['data'] as list
            raw_data = response.get('data', {})
            if isinstance(raw_data, dict):
                chain = raw_data.get('data', [])
            elif isinstance(raw_data, list):
                chain = raw_data
            else:
                chain = []

            if not chain:
                self._oi_fail_count += 1
                self.logger.warning(
                    f"⚠️ OI Fetch: API success but chain is EMPTY (#{self._oi_fail_count}) | "
                    f"expiry={expiry_str} | data_type={type(raw_data).__name__} | "
                    f"data_keys={list(raw_data.keys()) if isinstance(raw_data, dict) else 'N/A'}"
                )
                return {'data_source': DataSource.SIMULATED, 'fetch_ms': self._oi_last_fetch_ms}

            total_ce_oi, total_pe_oi = 0.0, 0.0
            max_ce_oi, max_pe_oi = 0.0, 0.0
            max_ce_strike, max_pe_strike = 0, 0
            max_pain_strike = 0

            for row in chain:
                ce = row.get('callOption', row.get('ce', {}))
                pe = row.get('putOption', row.get('pe', {}))
                strike = row.get('strikePrice', row.get('strike_price', 0))

                ce_oi = float(ce.get('openInterest', ce.get('oi', 0)))
                pe_oi = float(pe.get('openInterest', pe.get('oi', 0)))

                total_ce_oi += ce_oi
                total_pe_oi += pe_oi

                if ce_oi > max_ce_oi:
                    max_ce_oi = ce_oi
                    max_ce_strike = strike
                if pe_oi > max_pe_oi:
                    max_pe_oi = pe_oi
                    max_pe_strike = strike

            pcr = round(total_pe_oi / max(total_ce_oi, 1), 3)

            result = {
                'total_ce_oi': total_ce_oi,
                'total_pe_oi': total_pe_oi,
                'pcr': pcr,
                'max_pain': max_pain_strike or max_pe_strike,
                'max_ce_oi_strike': max_ce_strike,
                'max_pe_oi_strike': max_pe_strike,
                'india_vix': self._sim_vix,  # VIX from separate Dhan call if needed
                'data_source': DataSource.REAL,
                'fetch_ms': self._oi_last_fetch_ms,
            }

            self._oi_cache = result
            self._oi_last_fetch = now
            self._oi_success_count += 1
            self._oi_last_success_ts = now
            self.logger.info(
                f"🟢 REAL OI Fetched: CE={total_ce_oi/1e6:.1f}M | "
                f"PE={total_pe_oi/1e6:.1f}M | PCR={pcr} | "
                f"fetch_ms={self._oi_last_fetch_ms:.0f}"
            )
            return result

        except Exception as e:
            self._oi_fail_count += 1
            self.logger.warning(f"⚠️ OI Fetch exception (#{self._oi_fail_count}, using simulated): {e}")
            return {'data_source': DataSource.SIMULATED, 'fetch_ms': getattr(self, '_oi_last_fetch_ms', 0)}

    def fetch_option_quote(self, strike: int, opt_type: str, expiry: str) -> "OptionQuote":
        """
        🚀 PHASE A: Execution Realism
        Fetches the live LTP, Bid, and Ask for a specific option contract.
        If in SIMULATION mode, generates a highly realistic synthetic premium
        incorporating spread, IV, and distance from Spot.
        """
        from models.signals import OptionQuote
        import time as _time
        
        # 1. LIVE API MODE
        if self.data_source == "api":
            now = _time.time()
            if now < self.oi_circuit["open_until"]:
                self.logger.warning("OI circuit breaker OPEN — skipping live quote fetch and falling back to synthetic quote")
            else:
                try:
                    dhan = get_dhan_client()
                    
                    # Fetch option chain once to find the specific contract
                    if self._api_security_id is None:
                        self._api_security_id = self._discover_nifty_id(dhan)
                        
                    security_id_int = int(self._api_security_id)
                    
                    payload_log = {
                        "security_id": security_id_int,
                        "exchange_segment": "IDX_I",
                        "expiry": expiry,
                        "underlying": "NIFTY",
                        "request_json": {
                            "UnderlyingScrip": security_id_int,
                            "UnderlyingSeg": "IDX_I",
                            "Expiry": expiry
                        }
                    }
                    self.logger.info(f"📤 Sending Option Chain Request for Quote: {payload_log}")
                    
                    response = dhan.option_chain(
                        under_security_id=security_id_int,
                        under_exchange_segment="IDX_I",
                        expiry=expiry
                    )
                    self.logger.info(f"📥 Received Option Chain Response for Quote: {response}")
                    
                    # Inspect the response for non-retryable errors
                    inner_data = response.get('data', {}).get('data', {}) if isinstance(response.get('data'), dict) else {}
                    error_str = str(response.get('remarks', '')) + " " + str(inner_data) + " " + str(response)
                    
                    is_non_retryable = False
                    error_code = None
                    for err in ["805", "808", "permission_denied", "invalid_client"]:
                        if err in error_str:
                            error_code = err
                            is_non_retryable = True
                            break
                            
                    if is_non_retryable:
                        self.oi_circuit.update({
                            "open_until": _time.time() + 900,
                            "reason": "AUTH_FAILURE" if error_code == "808" else "RATE_LIMIT",
                            "failure_count": self.oi_circuit["failure_count"] + 1,
                            "last_error": error_code
                        })
                        self.logger.warning(
                            f"🚨 DataManager: Non-retryable error {error_code} detected during option quote fetch! "
                            f"Tripping circuit breaker for 15 minutes."
                        )
                    
                    if response.get('status') == 'success':
                        # Handle both: response['data']['data'] and response['data'] as list
                        raw_data = response.get('data', {})
                        if isinstance(raw_data, dict):
                            chain = raw_data.get('data', [])
                        elif isinstance(raw_data, list):
                            chain = raw_data
                        else:
                            chain = []
                            
                        for row in chain:
                            if row.get('strikePrice', row.get('strike_price', 0)) == strike:
                                opt_data = row.get('callOption', row.get('ce', {})) if opt_type == 'CE' else row.get('putOption', row.get('pe', {}))
                                return OptionQuote(
                                    security_id=opt_data.get('securityId', opt_data.get('security_id', '')),
                                    symbol=opt_data.get('tradingSymbol', opt_data.get('trading_symbol', f"NIFTY {strike} {opt_type}")),
                                    ltp=float(opt_data.get('lastPrice', opt_data.get('last_price', 0))),
                                    bid=float(opt_data.get('bidPrice', opt_data.get('bid_price', 0)) or opt_data.get('lastPrice', opt_data.get('last_price', 0))),
                                    ask=float(opt_data.get('askPrice', opt_data.get('ask_price', 0)) or opt_data.get('lastPrice', opt_data.get('last_price', 0))),
                                    volume=int(opt_data.get('volume', 0)),
                                    oi=int(opt_data.get('openInterest', opt_data.get('oi', 0)))
                                )
                except Exception as e:
                    self.logger.error(f"Option quote fetch failed: {e}")
                    # Fallback to simulation logic below if API fails

        # 2. SIMULATION MODE (Synthetic Option Pricing)
        # This is CRITICAL for realistic paper trading. We cannot use Spot Nifty.
        spot = self._sim_price if self.data_source == "simulated" else self.ohlcv_data['close'].iloc[-1]
        
        # Extremely rough Black-Scholes approximation for simulation realism
        diff = spot - strike if opt_type == "CE" else strike - spot
        intrinsic = max(0.0, diff)
        
        # Extrinsic value decays the further out of the money you are
        otm_dist = max(0.0, -diff)
        extrinsic = max(5.0, 150.0 - (otm_dist * 0.4))
        
        premium = intrinsic + extrinsic
        
        # Simulate bid/ask spread (wider for OTM)
        spread_pct = 0.002 + (otm_dist * 0.00001)  # 0.2% base spread, increasing for OTM
        bid = round(premium * (1 - spread_pct), 2)
        ask = round(premium * (1 + spread_pct), 2)
        
        return OptionQuote(
            security_id=f"SIM_{strike}_{opt_type}",
            symbol=f"NIFTY {strike} {opt_type}",
            ltp=round(premium, 2),
            bid=bid,
            ask=ask,
            volume=int(np.random.uniform(10000, 500000)),
            oi=int(np.random.uniform(500000, 5000000)),
            iv=self._sim_vix
        )

    def get_snapshot_incremental(self, df: pd.DataFrame) -> MarketSnapshot:
        """
        🚀 DELTA STATE CACHING
        Calculates indicators ONLY for the new tick to save CPU.
        """
        if df is None or len(df) < 21:
            return self._empty_snapshot()

        latest = df.iloc[-1]
        price = latest['close']
        vol = latest['volume']
        high = latest['high']
        low = latest['low']

        # 1. EMA Incremental (Span 9 and 21)
        if self.cached_ema_fast is None:
            # First run, initialize with standard calc
            self.cached_ema_fast = calculate_ema(df['close'], 9).iloc[-1]
            self.cached_ema_slow = calculate_ema(df['close'], 21).iloc[-1]
        else:
            alpha_f = 2 / (9 + 1)
            alpha_s = 2 / (21 + 1)
            self.cached_ema_fast = (price - self.cached_ema_fast) * alpha_f + self.cached_ema_fast
            self.cached_ema_slow = (price - self.cached_ema_slow) * alpha_s + self.cached_ema_slow

        # 2. RSI Incremental (EWM com=period-1)
        if self.cached_rsi_avg_gain is None:
            delta = df['close'].diff()
            gain = delta.where(delta > 0, 0.0)
            loss = -delta.where(delta < 0, 0.0)
            self.cached_rsi_avg_gain = gain.ewm(com=13, min_periods=14).mean().iloc[-1]
            self.cached_rsi_avg_loss = loss.ewm(com=13, min_periods=14).mean().iloc[-1]
        else:
            alpha_rsi = 1 / 14
            delta = price - df['close'].iloc[-2]
            gain = max(0, delta)
            loss = max(0, -delta)
            self.cached_rsi_avg_gain = (gain - self.cached_rsi_avg_gain) * alpha_rsi + self.cached_rsi_avg_gain
            self.cached_rsi_avg_loss = (loss - self.cached_rsi_avg_loss) * alpha_rsi + self.cached_rsi_avg_loss

        rs = self.cached_rsi_avg_gain / self.cached_rsi_avg_loss if self.cached_rsi_avg_loss > 0 else 100
        rsi_val = 100 - (100 / (1 + rs))

        # 3. VWAP Incremental
        tp = (high + low + price) / 3
        self.cached_vwap_tp_sum += tp * vol
        self.cached_vwap_vol_sum += vol
        vwap_val = self.cached_vwap_tp_sum / self.cached_vwap_vol_sum

        # 4. ATR (Simplified incremental)
        if self.cached_atr is None:
            self.cached_atr = calculate_atr(df, 14).iloc[-1]
        else:
            tr = max(high-low, abs(high-df['close'].iloc[-2]), abs(low-df['close'].iloc[-2]))
            self.cached_atr = (self.cached_atr * 13 + tr) / 14

        # 5. OI Data (real when DATA_SOURCE=api, simulated fallback otherwise)
        oi = self._get_oi_data()
        
        # 6. Regime Classification
        regime_state = self.regime_classifier.classify(
            df=df,
            snapshot_vwap=vwap_val,
            snapshot_atr=self.cached_atr,
            prev_day_close=self.prev_day_close
        )

        return MarketSnapshot(
            timestamp=latest.name if isinstance(latest.name, datetime) else pd.to_datetime(latest.name),
            price=price, open=latest['open'], high=high, low=low, close=price,
            volume=int(vol),
            vwap=vwap_val,
            rsi=rsi_val,
            ema_fast=self.cached_ema_fast,
            ema_slow=self.cached_ema_slow,
            atr=self.cached_atr,
            # Gap data — feeds into decision engine's GapPenaltyManager
            prev_day_close=self.prev_day_close or 0.0,
            day_open=self._day_open or latest['open'],
            # OI/Greeks/VIX below are SIMULATED — agents must check oi_data_source
            total_ce_oi=oi.get('total_ce_oi', self._sim_ce_oi()),
            total_pe_oi=oi.get('total_pe_oi', self._sim_pe_oi()),
            pcr=oi.get('pcr', self._sim_pcr()),
            max_pain=oi.get('max_pain', round(price / 100) * 100),
            india_vix=oi.get('india_vix', self._sim_vix),
            expiry_type="weekly",
            time_to_expiry_hours=24.0,
            minutes_to_close=180,
            atm_straddle_price=250.0,
            atm_straddle_open=300.0,
            straddle_decay_pct=16.6,
            atm_ce_premium=130.0,
            atm_pe_premium=120.0,
            atm_ce_premium_open=150.0,
            atm_pe_premium_open=150.0,
            atm_gamma=0.04,
            gamma_exposure=5000000.0,
            max_ce_oi_strike=oi.get('max_ce_oi_strike', round(price / 100) * 100 + 200),
            max_pe_oi_strike=oi.get('max_pe_oi_strike', round(price / 100) * 100 - 200),
            max_ce_oi_value=oi.get('total_ce_oi', self._sim_ce_oi()) * 0.3,
            max_pe_oi_value=oi.get('total_pe_oi', self._sim_pe_oi()) * 0.3,
            atm_iv=self._sim_vix + 2.0,
            iv_change_today=-1.5,
            iv_percentile_30d=45.0,
            oi_data_source=oi.get('data_source', DataSource.SIMULATED),
            regime_state=regime_state.to_dict(),
        )

    def get_snapshot_from_df(self, df: pd.DataFrame) -> MarketSnapshot:
        """Create current market snapshot from given dataframe"""

        if df is None or len(df) < 14:
            return self._empty_snapshot()

        # Calculate indicators
        vwap = calculate_vwap(df)
        rsi = calculate_rsi(df['close'], 14)
        ema_fast = calculate_ema(df['close'], 9)
        ema_slow = calculate_ema(df['close'], 21)
        atr = calculate_atr(df, 14)

        latest = df.iloc[-1]
        
        # Calculate Regime
        vwap_val = vwap.iloc[-1] if len(vwap) > 0 else latest['close']
        atr_val = atr.iloc[-1] if len(atr) > 0 and not pd.isna(atr.iloc[-1]) else 25
        regime_state = self.regime_classifier.classify(
            df=df,
            snapshot_vwap=vwap_val,
            snapshot_atr=atr_val,
            prev_day_close=self.prev_day_close
        )

        snapshot = MarketSnapshot(
            timestamp=latest.name if isinstance(latest.name, datetime) else pd.to_datetime(latest.name),
            price=latest['close'],
            open=latest['open'],
            high=latest['high'],
            low=latest['low'],
            close=latest['close'],
            volume=int(latest['volume']),
            vwap=vwap.iloc[-1] if len(vwap) > 0 else latest['close'],
            rsi=rsi.iloc[-1] if len(rsi) > 0 else 50,
            ema_fast=ema_fast.iloc[-1] if len(ema_fast) > 0 else latest['close'],
            ema_slow=ema_slow.iloc[-1] if len(ema_slow) > 0 else latest['close'],
            atr=atr.iloc[-1] if len(atr) > 0 and not pd.isna(atr.iloc[-1]) else 25,

            # ⚠️ P1.2: All OI/Greeks/VIX below are SIMULATED — agents must check oi_data_source
            total_ce_oi=self._sim_ce_oi(),
            total_pe_oi=self._sim_pe_oi(),
            pcr=self._sim_pcr(),
            max_pain=round(self._sim_price / 100) * 100,  # Nearest 100
            india_vix=self._sim_vix,

            # --- SIMULATED ADVANCED DATA ---
            expiry_type="weekly",
            time_to_expiry_hours=24.0,
            minutes_to_close=180,
            atm_straddle_price=250.0,
            atm_straddle_open=300.0,
            straddle_decay_pct=16.6,
            atm_ce_premium=130.0,
            atm_pe_premium=120.0,
            atm_ce_premium_open=150.0,
            atm_pe_premium_open=150.0,
            atm_gamma=0.04,
            gamma_exposure=5000000.0,
            max_ce_oi_strike=round(self._sim_price / 100) * 100 + 200,
            max_pe_oi_strike=round(self._sim_price / 100) * 100 - 200,
            max_ce_oi_value=self._sim_ce_oi() * 0.3,
            max_pe_oi_value=self._sim_pe_oi() * 0.3,
            atm_iv=self._sim_vix + 2.0,
            iv_change_today=-1.5,
            iv_percentile_30d=45.0,
            oi_data_source=DataSource.SIMULATED,  # P1.2: FLAG — not real data
            regime_state=regime_state.to_dict(),
        )

        self.logger.debug(f"Snapshot price: {snapshot.price:.2f}")
        return snapshot

    def get_dataframe(self) -> pd.DataFrame:
        """Return current dataframe"""
        if self.ohlcv_data is None and self.data_source == "simulated":
            self._fetch_simulated()
        return self.ohlcv_data

    def get_polling_telemetry(self) -> dict:
        """
        Exposes active API cadence & polling metrics for characterization.
        """
        avg_latency = 0.0
        if self._api_fetch_count > 0:
            avg_latency = self._api_total_latency_ms / self._api_fetch_count
            
        now = time.time()
        oi_circuit_status = "CLOSED"
        cooldown_remaining = 0
        if now < self.oi_circuit["open_until"]:
            oi_circuit_status = "OPEN"
            cooldown_remaining = int(self.oi_circuit["open_until"] - now)
            
        return {
            "last_api_fetch_ts": self._last_api_fetch_ts,
            "cache_hit_count": self._api_cache_hit_count,
            "api_fetch_count": self._api_fetch_count,
            "avg_fetch_latency": avg_latency,
            "oi_circuit": oi_circuit_status,
            "cooldown_remaining_seconds": cooldown_remaining,
            "cooldown_remaining_formatted": f"{cooldown_remaining // 60}m {cooldown_remaining % 60}s" if cooldown_remaining > 0 else "0s",
            "last_oi_error": self.oi_circuit["last_error"],
            "last_oi_success": datetime.fromtimestamp(self._oi_last_success_ts).strftime("%Y-%m-%d %H:%M:%S") if self._oi_last_success_ts > 0 else None
        }

    # ============================================
    # SIMULATED DATA (for development/testing)
    # ============================================

    def _fetch_simulated(self) -> pd.DataFrame:
        """Generate realistic simulated Nifty data"""
        self.tick_count += 1

        # Generate price movement
        np.random.seed(None)  # True random

        # Trend changes occasionally
        if self.tick_count % 50 == 0:
            self._sim_trend = np.random.choice([-1, 1])

        # Price movement
        noise = np.random.normal(0, 8)
        trend_component = self._sim_trend * np.random.uniform(1, 5)
        self._sim_price += trend_component + noise
        self._sim_price = max(23000, min(23800, self._sim_price))

        # VIX movement
        self._sim_vix += np.random.normal(0, 0.3)
        self._sim_vix = max(9, min(25, self._sim_vix))

        # Generate OHLCV candle
        new_close = self._sim_price
        new_open = new_close + np.random.normal(0, 10)
        new_high = max(new_open, new_close) + abs(np.random.normal(0, 15))
        new_low = min(new_open, new_close) - abs(np.random.normal(0, 15))
        new_volume = int(np.random.uniform(50000, 500000))

        new_row = pd.DataFrame([{
            'timestamp': datetime.now(),
            'open': round(new_open, 2),
            'high': round(new_high, 2),
            'low': round(new_low, 2),
            'close': round(new_close, 2),
            'volume': new_volume,
        }])

        if self.ohlcv_data is None:
            # Initialize with historical data
            self.ohlcv_data = self._generate_initial_history()

        # Append new data
        self.ohlcv_data = pd.concat(
            [self.ohlcv_data, new_row], ignore_index=True
        )

        # Keep only last 200 candles
        if len(self.ohlcv_data) > 200:
            self.ohlcv_data = self.ohlcv_data.tail(200).reset_index(drop=True)

        return self.ohlcv_data

    def _generate_initial_history(self) -> pd.DataFrame:
        """Generate 100 candles of initial history"""
        data = []
        price = self._sim_price - 200  # Start lower

        for i in range(100):
            noise = np.random.normal(0, 8)
            trend = np.random.choice([-1, 1]) * np.random.uniform(1, 4)
            price += trend + noise
            price = max(23000, min(23800, price))

            o = price + np.random.normal(0, 10)
            h = max(o, price) + abs(np.random.normal(0, 15))
            l = min(o, price) - abs(np.random.normal(0, 15))
            v = int(np.random.uniform(50000, 500000))

            data.append({
                'timestamp': datetime.now() - timedelta(minutes=(100 - i)),
                'open': round(o, 2),
                'high': round(h, 2),
                'low': round(l, 2),
                'close': round(price, 2),
                'volume': v,
            })

        return pd.DataFrame(data)

    def _sim_ce_oi(self) -> float:
        """Simulated CE OI"""
        base = 5000000
        return base + np.random.normal(0, 500000)

    def _sim_pe_oi(self) -> float:
        """Simulated PE OI"""
        base = 5500000
        return base + np.random.normal(0, 500000)

    def _sim_pcr(self) -> float:
        """Simulated Put-Call Ratio"""
        return round(np.random.uniform(0.7, 1.4), 2)

    # ============================================
    # REAL API DATA (plug in later)
    # ============================================

    def _fetch_history_for_bootstrap(self) -> pd.DataFrame:
        """
        Fetch 5 days of history. Used strictly at boot time.
        """
        import time
        try:
            dhan = get_dhan_client()

            if self._api_security_id is None:
                self._api_security_id = self._discover_nifty_id(dhan)

            today_str = datetime.now().strftime("%Y-%m-%d")
            from_date_str = (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d")

            t_start = time.perf_counter()
            self.logger.info(
                f"🕯️ Boot-Time Candle fetch started: security_id={self._api_security_id} | "
                f"from_date={from_date_str} to_date={today_str}"
            )

            try:
                response = dhan.intraday_minute_data(
                    security_id=self._api_security_id,
                    exchange_segment=self._api_exchange_segment,
                    instrument_type=self._api_instrument_type,
                    from_date=from_date_str,
                    to_date=today_str
                )
            except Exception as e:
                self.logger.error(f"❌ Bootstrap Candle fetch Exception: {e}")
                raise e

            fetch_time_ms = (time.perf_counter() - t_start) * 1000
            self.logger.info(f"🕯️ Bootstrap fetch returned in {fetch_time_ms:.1f}ms | status={response.get('status')}")

            if response.get('status') != 'success':
                self.logger.error(f"Dhan API Error during bootstrap: {response}")
                return pd.DataFrame()

            raw_data = response.get('data', [])
            if not raw_data:
                self.logger.warning("No data returned from API for bootstrap.")
                return pd.DataFrame()

            df = pd.DataFrame(raw_data)
            df.columns = [c.lower() for c in df.columns]

            time_col = 'start_time' if 'start_time' in df.columns else 'timestamp'
            if pd.api.types.is_numeric_dtype(df[time_col]):
                df['timestamp'] = pd.to_datetime(df[time_col], unit='s').dt.tz_localize('UTC').dt.tz_convert('Asia/Kolkata').dt.tz_localize(None)
            else:
                df['timestamp'] = pd.to_datetime(df[time_col])
            df.set_index('timestamp', inplace=True)

            df.dropna(inplace=True)
            df.sort_index(inplace=True)
            df = df[~df.index.duplicated(keep="last")]

            self.logger.info(f"🕯️ Hydrated {len(raw_data)} raw candles from API. Cleaned dataframe size: {len(df)}")

            if len(df) > 1:
                df = df.iloc[:-1]

            self._handle_gap(df)

            if len(df) < self.settings.trade_filter.min_candles_warmup:
                self.logger.warning(
                    f"Bootstrap Warmup progress: {len(df)}/{self.settings.trade_filter.min_candles_warmup} candles. "
                    f"Hydration NOT complete."
                )
                return pd.DataFrame()

            self.logger.info(
                f"🎉 Hydration COMPLETE: {len(df)} candles warmed up. "
                f"Reason='bootstrap_complete_passed' | df_1m size={len(df)}"
            )

            self.df_1m = df
            self.df_5m = self._resample_data(df, self.settings.trend_timeframe)
            self.ohlcv_data = df
            
            # Capping memory
            MAX_CANDLES = 2000
            if len(self.ohlcv_data) > MAX_CANDLES:
                self.ohlcv_data = self.ohlcv_data.tail(MAX_CANDLES)

            return self.df_1m

        except Exception as e:
            self.logger.critical(f"API CRITICAL FAILURE during bootstrap: {str(e)}")
            return pd.DataFrame()


    def _fetch_from_api_incremental(self) -> pd.DataFrame:
        """
        🚀 RUNTIME OPTIMIZATION: Incremental streaming update.
        Only fetches today's candles. Uses precise row updating/appending.
        """
        import time
        if not self._is_market_open_safe():
            return self.ohlcv_data

        if time.time() < self._api_circuit_breaker_until:
            return self.ohlcv_data

        now = time.time()
        time_since_last_api = now - self._last_api_fetch_ts
        if time_since_last_api < self._api_fetch_cooldown:
            return self.ohlcv_data

        try:
            dhan = get_dhan_client()

            if self._api_security_id is None:
                self._api_security_id = self._discover_nifty_id(dhan)

            today_str = datetime.now().strftime("%Y-%m-%d")

            t_start = time.perf_counter()

            response = dhan.intraday_minute_data(
                security_id=self._api_security_id,
                exchange_segment=self._api_exchange_segment,
                instrument_type=self._api_instrument_type,
                from_date=today_str,
                to_date=today_str
            )

            fetch_time_ms = (time.perf_counter() - t_start) * 1000

            if response.get('status') != 'success':
                self._api_failures += 1
                if self._api_failures >= 3:
                    self.logger.critical("API Circuit Breaker TRIPPED! Suspending API calls for 60s")
                    self._api_circuit_breaker_until = time.time() + 60
                return self.ohlcv_data

            self._api_failures = 0
            self._last_api_fetch_ts = time.time()
            self._api_fetch_count += 1
            self._api_total_latency_ms += fetch_time_ms

            # Freshness Metadata Update
            self.last_successful_fetch_ts = time.time()
            self.last_incremental_latency_ms = fetch_time_ms

            raw_data = response.get('data', [])
            if not raw_data:
                return self.ohlcv_data

            # Fast transform
            df_new = pd.DataFrame(raw_data)
            df_new.columns = [c.lower() for c in df_new.columns]

            time_col = 'start_time' if 'start_time' in df_new.columns else 'timestamp'
            if pd.api.types.is_numeric_dtype(df_new[time_col]):
                df_new['timestamp'] = pd.to_datetime(df_new[time_col], unit='s').dt.tz_localize('UTC').dt.tz_convert('Asia/Kolkata').dt.tz_localize(None)
            else:
                df_new['timestamp'] = pd.to_datetime(df_new[time_col])
                
            df_new.set_index('timestamp', inplace=True)
            df_new.dropna(inplace=True)
            df_new.sort_index(inplace=True)
            df_new = df_new[~df_new.index.duplicated(keep="last")]

            if len(df_new) > 1:
                df_new = df_new.iloc[:-1]

            if df_new.empty:
                return self.ohlcv_data

            if self.ohlcv_data is None or self.ohlcv_data.empty:
                self.ohlcv_data = df_new
            else:
                latest_api_ts = df_new.index[-1]
                last_ts = self.ohlcv_data.index[-1]

                if latest_api_ts == last_ts:
                    # Update last row (candle mutated before close)
                    self.ohlcv_data.loc[latest_api_ts] = df_new.iloc[-1]
                elif latest_api_ts > last_ts:
                    # Append new rows strictly > last_ts
                    new_rows = df_new[df_new.index > last_ts]
                    if not new_rows.empty:
                        self.ohlcv_data = pd.concat([self.ohlcv_data, new_rows])
                        self.last_new_candle_ts = time.time()
                else:
                    # Reject as stale (latency/out-of-order)
                    self.logger.warning(f"⚠️ Stale candle received! {latest_api_ts} < {last_ts}. Rejecting.")

            # Memory limit
            MAX_CANDLES = 2000
            if len(self.ohlcv_data) > MAX_CANDLES:
                self.ohlcv_data = self.ohlcv_data.tail(MAX_CANDLES)

            self.df_1m = self.ohlcv_data
            return self.ohlcv_data

        except Exception as e:
            self._api_failures += 1
            self.logger.error(f"Incremental fetch exception: {e}")
            if self._api_failures >= 3:
                self._api_circuit_breaker_until = time.time() + 60
            return self.ohlcv_data

    def _handle_gap(self, df: pd.DataFrame):
        """Detect and handle opening gaps"""
        if df.empty:
            return

        today = datetime.now().date()
        today_data = df[df.index.date == today]

        if not today_data.empty:
            today_open = today_data.iloc[0]['open']

            # Find previous day close
            prev_data = df[df.index.date < today]
            if not prev_data.empty:
                prev_close = prev_data.iloc[-1]['close']
                gap = abs(today_open - prev_close)
                
                if gap < 30: bucket = "NORMAL"
                elif gap < 60: bucket = "ELEVATED"
                elif gap < 100: bucket = "HIGH"
                else: bucket = "CRITICAL"
                
                current_candle = df.index[-1]
                if not hasattr(self, '_last_gap_bucket'):
                    self._last_gap_bucket = None
                    self._last_gap_candle = None
                
                if self._last_gap_bucket != bucket or self._last_gap_candle != current_candle:
                    if bucket != "NORMAL" and gap > self.settings.trade_filter.gap_threshold_points:
                        self.logger.warning(f"🚨 {bucket} GAP DETECTED: {gap:.1f} pts! Indicators may be unstable.")
                    self._last_gap_bucket = bucket
                    self._last_gap_candle = current_candle

                # Store prev_day_close and day_open for snapshot consumption
                # so the gap penalty manager can initialise correctly.
                self.prev_day_close = prev_close
                self._day_open = today_open

    def _resample_data(self, df: pd.DataFrame, timeframe: str) -> pd.DataFrame:
        """Resample 1m data to target timeframe"""
        resampled = df.resample(timeframe).agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        }).dropna()
        return resampled

    def _check_mtf_sync(self) -> bool:
        """Ensure 1m and 5m candles are aligned"""
        if self.df_1m is None or self.df_5m is None or self.df_1m.empty or self.df_5m.empty:
            return False

        last_1m = self.df_1m.index[-1]
        last_5m = self.df_5m.index[-1]

        # 5m candle should cover the range up to 1m
        return last_1m >= last_5m

    def _is_market_open_safe(self) -> bool:
        """Check if current time is after market_open_safe_time using SessionGuard.
        
        Transition logging is handled inside SessionGuard.can_trade() —
        this method is intentionally silent during steady-state protection.
        """
        from core.session_guard import orchestrator
        return orchestrator.is_live()

    def _discover_nifty_id(self, dhan) -> str:
        """
        Dynamically find Nifty 50 Security ID.
        🛡️ Risk #5 Fix: IDs now sourced from settings.instruments (InstrumentConfig)
        rather than being hardcoded here. Override via env var e.g. NIFTY_SECURITY_ID=1.
        Raises RuntimeError if instrument is not registered.
        """
        self.logger.info("Discovering NIFTY 50 Security ID via InstrumentConfig...")
        instrument_name = self.settings.trading.instrument.upper()
        return self.settings.instruments.get_security_id(instrument_name)

    def _fetch_from_csv(self) -> pd.DataFrame:
        """Load data from CSV file"""
        try:
            df = pd.read_csv("data/market_data.csv")
            self.ohlcv_data = df
            return df
        except FileNotFoundError:
            self.logger.warning("CSV not found — using simulated")
            return self._fetch_simulated()

    def _empty_snapshot(self) -> MarketSnapshot:
        """Return empty snapshot when no data available"""
        return MarketSnapshot(
            timestamp=datetime.now(),
            price=0, open=0, high=0, low=0, close=0,
            volume=0, vwap=0, rsi=50,
            ema_fast=0, ema_slow=0, atr=25,
        )
