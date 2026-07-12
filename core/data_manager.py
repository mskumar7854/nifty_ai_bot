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

from models import MarketSnapshot, DataSource, OptionQuote
from utils.indicators import (
    calculate_vwap, calculate_rsi, calculate_ema, calculate_atr
)
from utils.logger import get_logger
from config.settings import Settings
from dhan_client import get_dhan_client
from core.regime_classifier import RegimeClassifier
from core.regime_state_manager import RegimeStateManager
from config.config import OPTION_CHAIN_SEGMENT, CANDLE_SEGMENT

# ── Bounded executor for Dhan API calls ──
# All dhan.option_chain() / dhan.get_order_book() calls run here.
# max_workers=2: one for OI analytics, one for quote fetch.
# This prevents threadpool exhaustion even if Dhan hangs repeatedly.
import concurrent.futures as _cf
_DHAN_FETCH_TIMEOUT: float = 10.0          # Hard cap: never wait more than 10s for Dhan REST
_OI_EXECUTOR = _cf.ThreadPoolExecutor(max_workers=2, thread_name_prefix="dhan_oi")


def normalize_option_chain(chain, spot: float = 0.0, atm_radius: float = 500.0) -> list:
    """
    🔧 CANONICAL OPTION CHAIN NORMALIZER

    Converts either API response format into a uniform list of row dicts:
        [
            {"strike": 23800.0, "ce": {...}, "pe": {...}},
            ...
        ]

    Handles two formats returned by the Dhan option_chain() endpoint:

    Format A — dict keyed by strike string (current Dhan API):
        {
            "23800.000000": {"ce": {"oi": ..., "last_price": ...}, "pe": {...}},
            ...
        }

    Format B — list of row dicts (legacy / possible future format):
        [
            {"strikePrice": 23800, "callOption": {...}, "putOption": {...}},
            ...
        ]

    Args:
        chain:       Raw chain data from response['data']['data'] (dict or list).
        spot:        Current spot price. Used for ATM-relative filtering.
                     Pass 0.0 to disable filtering.
        atm_radius:  Only include strikes within spot ± atm_radius.
                     Default 500 covers ATM±500 for intraday NIFTY.
                     Pass float('inf') to include all strikes.

    Returns:
        List of normalized row dicts, sorted ascending by strike.
        Empty list if chain is neither dict nor list.
    """
    normalized = []

    if isinstance(chain, dict):
        # Format A: keys are strike price strings
        for strike_key, value in chain.items():
            try:
                strike = float(strike_key)
            except (TypeError, ValueError):
                continue  # Skip malformed keys
            if not isinstance(value, dict):
                continue  # Skip unexpected values
            normalized.append({
                "strike": strike,
                "ce": value.get("ce", {}),
                "pe": value.get("pe", {}),
            })

    elif isinstance(chain, list):
        # Format B: list of row dicts with strikePrice/callOption/putOption
        for row in chain:
            if not isinstance(row, dict):
                continue  # Skip if somehow a string slipped in
            strike = float(row.get("strikePrice", row.get("strike_price", 0)) or 0)
            normalized.append({
                "strike": strike,
                "ce": row.get("callOption", row.get("ce", {})),
                "pe": row.get("putOption", row.get("pe", {})),
            })

    # ATM-relative filtering (skip if spot not provided)
    if spot > 0 and atm_radius < float('inf'):
        lo = spot - atm_radius
        hi = spot + atm_radius
        normalized = [r for r in normalized if lo <= r["strike"] <= hi]

    normalized.sort(key=lambda r: r["strike"])
    return normalized


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

        # --- System State (Operational Persistence) ---
        import core.system_state as system_state
        op_state = system_state.load_operational_state()
        
        self.oi_circuit = op_state.get("oi_circuit", {
            "open_until": 0.0,
            "reason": None,
            "failure_count": 0,
            "last_error": None,
            "warning_logged": False,
        })
        self.quote_circuit = op_state.get("quote_circuit", {
            "open_until": 0.0,
            "reason": None,
            "failure_count": 0,
            "last_error": None,
        })
        # ── SPLIT CIRCUIT BREAKER ──
        # quote_circuit guards fetch_option_quote (per-trade execution path).
        # oi_circuit guards _get_oi_data (60s analytics path).
        # A rate-limit on one path never silences the other.

        # Consecutive timeout counter — after 3 hung requests, trip the circuit.
        self._oi_timeout_count: int = 0
        self._quote_timeout_count: int = 0

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
        self._oi_fetch_interval: float = 300.0  # seconds (increased from 60.0 to avoid 805 rate limit)
        # ── Last-good OI snapshot (stale-cache for degraded resilience) ──
        # Survives API spikes. Serves stale-but-real data instead of pure simulation.
        self._last_good_oi_snapshot: dict = {}
        self._last_good_oi_ts: float = 0.0

        # ── OI Updater State ──
        self._oi_updater_running = False
        self._oi_updater_task = None
        self._oi_updater_last_tick = 0.0


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


    def _save_circuit_state(self):
        try:
            import core.system_state as system_state
            data = system_state.load_operational_state()
            data["oi_circuit"] = self.oi_circuit
            data["quote_circuit"] = self.quote_circuit
            system_state.save_operational_state(data)
        except Exception as e:
            self.logger.error(f"Failed to persist circuit state: {e}")

    async def start_oi_updater(self):
        """Starts the background OI updater task."""
        if self.data_source != "api":
            return
        if not self._oi_updater_running:
            self.logger.info("🚀 Starting background OI Updater loop...")
            self._oi_updater_running = True
            import time
            self._oi_updater_last_tick = time.time()
            import asyncio
            self._oi_updater_task = asyncio.create_task(self._oi_updater_loop())

    async def stop_oi_updater(self):
        """Stops the background OI updater task."""
        if self._oi_updater_running:
            self.logger.info("🛑 Stopping background OI Updater loop...")
            self._oi_updater_running = False
            if self._oi_updater_task:
                self._oi_updater_task.cancel()
                import asyncio
                try:
                    await self._oi_updater_task
                except asyncio.CancelledError:
                    pass
                self._oi_updater_task = None
            self.logger.info("🛑 OI Updater stopped.")
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
            # ── DNS Guard: Don't attempt bootstrap if DNS is broken ──
            from utils.dns_health import dns_ok
            if not dns_ok(force=True):
                self.logger.error("🌐 DNS_OUTAGE: Skipping bootstrap — DNS resolution failed. Will retry on next cycle.")
                return

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
            # ── DNS Guard: Don't force bootstrap if DNS is broken ──
            from utils.dns_health import dns_ok
            if not dns_ok():
                self.logger.warning("🌐 DNS_OUTAGE: Skipping forced bootstrap — DNS unavailable.")
                return self.ohlcv_data, self._empty_snapshot()
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
            # HOWEVER: we also guarantee last_market_activity_ts is always at
            # least as fresh as the candle's own timestamp. This prevents
            # low-volume periods (where OHLCV stays flat for 30-60s) from
            # causing a false DataHealth=DEAD transition.
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
                    self.logger.info(f"📡 MARKET_ACTIVITY_UPDATE ts={self.last_market_activity_ts} source=tick (fingerprint changed: {fingerprint})")
                else:
                    # OHLCV unchanged — but use the candle's own timestamp as
                    # a floor so the orchestrator doesn't see phantom staleness.
                    # Only refresh if the candle ts is newer than current activity ts.
                    try:
                        candle_ts = df.index[-1]
                        if hasattr(candle_ts, "to_pydatetime"):
                            candle_ts = candle_ts.to_pydatetime()
                        # Remove timezone info for comparison with naive datetime.now()
                        if hasattr(candle_ts, "tzinfo") and candle_ts.tzinfo is not None:
                            candle_ts = candle_ts.replace(tzinfo=None)
                        if (self.last_market_activity_ts is None or
                                candle_ts > self.last_market_activity_ts):
                            self.last_market_activity_ts = candle_ts
                            self.logger.info(f"📡 MARKET_ACTIVITY_UPDATE ts={self.last_market_activity_ts} source=candle_ts (candle_ts newer)")
                    except Exception:
                        pass  # Candle ts fallback is best-effort
            except Exception:
                pass  # Don't let mutation tracking break the hot path


        snapshot = await asyncio.to_thread(self.get_snapshot_incremental, df)
        return df, snapshot


    def _get_oi_data(self) -> dict:
        """
        🟢 REAL OI DATA FETCHER (Snapshot Accessor)
        O(1) read from the background cache.
        Appends dynamic freshness metadata so the strategy engine can apply penalties.
        """
        import time as _time
        now = _time.time()
        
        # Determine source
        source_data = self._oi_cache if self._oi_cache else self._last_good_oi_snapshot
        
        if not source_data or self.data_source != "api":
            return {'data_source': DataSource.SIMULATED}
            
        age_sec = round(now - self._oi_last_fetch, 1)
        
        if age_sec <= 60:
            quality = "LIVE"
        elif age_sec <= 180:
            quality = "SLIGHTLY_STALE"
        elif age_sec <= 300:
            quality = "STALE"
        elif age_sec <= 900:
            quality = "DEGRADED"
        else:
            quality = "INVALID"
            # Hard cutoff: do not propagate >900s stale data
            self.logger.error(f"🚨 OI data completely INVALID (age={age_sec}s). Purging snapshot.")
            self._oi_cache = {}
            self._last_good_oi_snapshot = {}
            return {'data_source': DataSource.SIMULATED}
            
        # Append metadata
        result = dict(source_data)  # shallow copy
        result["age_sec"] = age_sec
        result["quality"] = quality
        return result

    async def _oi_updater_loop(self):
        """
        Background task that updates OI every 60s independently of the cycle.
        """
        import asyncio, random, time as _time
        from core.options_resolver import OptionContractBuilder
        
        # Initial wait to let bootstrap finish
        await asyncio.sleep(2)
        
        while self._oi_updater_running:
            self._oi_updater_last_tick = _time.time()
            try:
                now = _time.time()

                # ── DNS Guard: Don't attempt OI fetch if DNS is broken ──
                from utils.dns_health import dns_ok
                if not dns_ok():
                    await asyncio.sleep(10)  # Wait longer during DNS outage
                    continue

                # Check circuit breaker
                if now < self.oi_circuit["open_until"]:
                    if not self.oi_circuit.get("warning_logged", False):
                        cooldown_rem = int(self.oi_circuit["open_until"] - now)
                        self.logger.warning(
                            f"[OI UPDATER] Circuit breaker OPEN — skipping fetch. "
                            f"Cooldown remaining: {cooldown_rem}s. Last error: {self.oi_circuit['last_error']}"
                        )
                        self.oi_circuit["warning_logged"] = True
                    # Sleep 5s and check breaker again
                    await asyncio.sleep(5)
                    continue
                else:
                    self.oi_circuit["warning_logged"] = False

                expiry_str = OptionContractBuilder.get_expiry_str()
                dhan = get_dhan_client()

                if self._api_security_id is None:
                    self._api_security_id = self._discover_nifty_id(dhan)

                security_id_int = int(self._api_security_id)
                self.logger.debug(f"📤 OI Updater | security_id={security_id_int} | expiry={expiry_str}")

                # ── Retry loop: 3 attempts with exponential backoff ──
                response = None
                last_error = None
                t_fetch_start = _time.perf_counter()

                for attempt in range(3):
                    try:
                        future = _OI_EXECUTOR.submit(
                            lambda: dhan.option_chain(
                                under_security_id=security_id_int,
                                under_exchange_segment="IDX_I",
                                expiry=expiry_str
                            )
                        )
                        # We use asyncio.to_thread here to not block the updater loop on future.result()
                        response = await asyncio.to_thread(future.result, _DHAN_FETCH_TIMEOUT)
                        self._oi_timeout_count = 0  # Reset on success
                        
                        if response.get('status') == 'success':
                            break
                        
                        last_error = response.get('remarks', 'unknown')
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
                            if error_code == "805":
                                self.logger.error(
                                    "🚨 RAW DHAN 805 RESPONSE | type=%s | response=%s",
                                    type(response),
                                    repr(response)
                                )
                            fail_count = self.oi_circuit.get("failure_count", 0) + 1
                            if error_code == "805":
                                backoff = min(30 * (2 ** (fail_count - 1)), 300)
                            else:
                                backoff = 900
                            self.oi_circuit.update({
                                "open_until": _time.time() + backoff,
                                "reason": "AUTH_FAILURE" if error_code == "808" else "RATE_LIMIT" if error_code == "805" else "PERMISSION_DENIED",
                                "failure_count": fail_count,
                                "last_error": error_code
                            })
                            self.logger.warning(f"🚨 OI Updater: Non-retryable error {error_code}! Tripping circuit for {backoff}s.")
                            self._save_circuit_state()
                            break
                            
                        if attempt < 2:
                            await asyncio.sleep(1 << attempt)

                    except _cf.TimeoutError:
                        future.cancel()
                        self._oi_timeout_count += 1
                        last_error = f"TimeoutError (>{_DHAN_FETCH_TIMEOUT:.0f}s)"
                        self.logger.error(
                            f"⏱️ OI Updater TIMEOUT after {_DHAN_FETCH_TIMEOUT:.0f}s | "
                            f"attempt={attempt+1} | consecutive={self._oi_timeout_count} | Worker abandoned."
                        )
                        if self._oi_timeout_count >= 3:
                            self.oi_circuit.update({
                                "open_until": _time.time() + 300,
                                "reason": "TIMEOUT_STORM",
                                "failure_count": self.oi_circuit["failure_count"] + 1,
                                "last_error": "TIMEOUT"
                            })
                            self.logger.warning(f"🚨 OI circuit tripped: 3 timeouts.")
                            self._save_circuit_state()
                            self._oi_timeout_count = 0
                            break
                        if attempt < 2:
                            await asyncio.sleep(1 << attempt)

                    except Exception as e:
                        self.logger.error(
                            "🚨 DHAN EXCEPTION | type=%s | repr=%s",
                            type(e).__name__,
                            repr(e)
                        )
                        last_error = f"Exception: {e}"
                        if attempt >= 2:
                            raise e
                        await asyncio.sleep(1 << attempt)


                self._oi_last_fetch_ms = ((_time.perf_counter() - t_fetch_start) * 1000)

                if response is None or response.get('status') != 'success':
                    self._oi_fail_count += 1
                    self.logger.warning(f"⚠️ OI Updater fail: {last_error}")
                else:
                    self.oi_circuit["failure_count"] = 0
                    self._oi_success_count += 1
                    self._oi_last_success_ts = _time.time()
                    self._oi_last_fetch = _time.time()
                    
                    try:
                        chain_data = response['data']['data']['oc']
                        spot_price = response['data']['data']['last_price']
                        
                        chain_list = normalize_option_chain(chain_data, spot=spot_price, atm_radius=500.0)
                        
                        total_ce_oi = 0
                        total_pe_oi = 0
                        max_ce_oi = 0
                        max_pe_oi = 0
                        max_ce_strike = 0
                        max_pe_strike = 0

                        for row in chain_list:
                            ce = row['ce']
                            pe = row['pe']
                            strike = row['strike']

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
                            'max_ce_oi': max_ce_oi,
                            'max_pe_oi': max_pe_oi,
                            'max_ce_strike': max_ce_strike,
                            'max_pe_strike': max_pe_strike,
                            'pcr': pcr,
                            'data_source': DataSource.REAL
                        }
                        
                        self._oi_cache = result
                        self._last_good_oi_snapshot = result
                        self._last_good_oi_ts = _time.time()
                        
                    except Exception as e:
                        self.logger.error(f"⚠️ OI Updater parsing exception: {e}")

                # Jittered sleep: 300s +/- 10s to avoid aggressive rate limits
                jitter_sleep = 300 + random.uniform(-10, 10)
                await asyncio.sleep(jitter_sleep)

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.exception(f"💥 Uncaught exception in _oi_updater_loop: {e}")
                await asyncio.sleep(5)  # Prevent tight loop crash

    def fetch_option_quote(self, strike: int, opt_type: str, expiry: str) -> "OptionQuote":
        """
        🚀 PHASE A: Execution Realism
        Fetches the live LTP, Bid, and Ask for a specific option contract.
        If in SIMULATION mode, generates a highly realistic synthetic premium
        incorporating spread, IV, and distance from Spot.
        """
        from models import OptionQuote
        import time as _time
        
        # 1. LIVE API MODE
        if self.data_source == "api":
            now = _time.time()
            if now < self.quote_circuit["open_until"]:
                cooldown_q = int(self.quote_circuit["open_until"] - now)
                self.logger.warning(
                    f"OI quote_circuit OPEN — skipping live quote fetch | "
                    f"cooldown={cooldown_q}s | last_err={self.quote_circuit['last_error']}"
                )
                return None
            else:
                try:
                    dhan = get_dhan_client()

                    # Fetch option chain once to find the specific contract
                    if self._api_security_id is None:
                        self._api_security_id = self._discover_nifty_id(dhan)

                    security_id_int = int(self._api_security_id)

                    self.logger.debug(
                        f"📤 OC quote request | security_id={security_id_int} | "
                        f"expiry={expiry} | strike={strike} {opt_type}"
                    )

                    # 🔒 SAFETY: Run in bounded executor with hard timeout.
                    # Uses quote_circuit (separate from oi_circuit) so a rate-limit
                    # here never silences the 60s OI analytics fetch.
                    t_start = _time.perf_counter()
                    future = _OI_EXECUTOR.submit(
                        lambda: dhan.option_chain(
                            under_security_id=security_id_int,
                            under_exchange_segment="IDX_I",
                            expiry=expiry,
                            is_execution=True  # type: ignore
                        )
                    )
                    try:
                        response = future.result(timeout=_DHAN_FETCH_TIMEOUT)
                        fetch_time_ms = (_time.perf_counter() - t_start) * 1000
                        self._quote_timeout_count = 0  # Reset on success
                    except _cf.TimeoutError:
                        fetch_time_ms = (_time.perf_counter() - t_start) * 1000
                        future.cancel()
                        self._quote_timeout_count += 1
                        self.logger.error(
                            f"⏱️ Quote fetch TIMEOUT after {_DHAN_FETCH_TIMEOUT:.0f}s ({fetch_time_ms:.1f}ms) | "
                            f"consecutive={self._quote_timeout_count} | Worker abandoned."
                        )
                        self.logger.warning(
                            f"🔍 QUOTE DEBUG | strike={strike} {opt_type} TIMEOUT | time={fetch_time_ms:.1f}ms"
                        )
                        if self._quote_timeout_count >= 3:
                            self.quote_circuit.update({
                                "open_until": _time.time() + 300,
                                "reason": "TIMEOUT_STORM",
                                "failure_count": self.quote_circuit["failure_count"] + 1,
                                "last_error": "TIMEOUT"
                            })
                            self._quote_timeout_count = 0
                            self.logger.warning(
                                "🚨 quote_circuit tripped: 3 consecutive timeouts. 5-min cooldown."
                            )
                            self._save_circuit_state()
                        raise  # Fall through to except block below

                    self.logger.debug(
                        f"📥 OC quote response | status={response.get('status')}"
                    )

                    # Inspect the response for non-retryable errors
                    status = str(response.get('status', '')).lower()
                    is_non_retryable = False
                    error_code = None
                    
                    if status in ('failure', 'error'):
                        error_str = str(response.get('remarks', '')) + " " + str(response.get('errorCode', '')) + " " + str(response.get('errorMsg', ''))
                        inner_data = response.get('data', {})
                        if isinstance(inner_data, dict):
                            error_str += " " + str(inner_data.get('errorCode', '')) + " " + str(inner_data.get('errorMsg', ''))
                        
                        for err in ["805", "808", "permission_denied", "invalid_client"]:
                            if err in error_str:
                                error_code = err
                                is_non_retryable = True
                                break

                    if is_non_retryable:
                        fail_count = self.quote_circuit.get("failure_count", 0) + 1
                        if error_code == "805":
                            self.logger.error(
                                "🚨 RAW DHAN 805 RESPONSE (QUOTE) | type=%s | response=%s",
                                type(response),
                                repr(response)
                            )
                            backoff = min(30 * (2 ** (fail_count - 1)), 300)
                        else:
                            backoff = 900
                        # ── Use quote_circuit (NOT oi_circuit) ──
                        self.quote_circuit.update({
                            "open_until": _time.time() + backoff,
                            "reason": "AUTH_FAILURE" if error_code == "808" else "RATE_LIMIT",
                            "failure_count": fail_count,
                            "last_error": error_code
                        })
                        self.logger.warning(
                            f"🚨 DataManager: Non-retryable quote error {error_code}! "
                            f"Tripping quote_circuit for {backoff}s."
                        )
                        raise ValueError(f"Non-retryable Dhan API error: {error_code}")
                    
                    if response.get('status') == 'success':
                        self.logger.info(f"QUOTE_FETCH_RESPONSE_STATUS={response.get('status')}")
                        self.quote_circuit["failure_count"] = 0
                        raw_data = response.get('data', {})
                        data_block = raw_data.get('data', {}) if isinstance(raw_data, dict) else {}

                        # Primary path: response['data']['data']['oc']
                        if isinstance(data_block, dict) and 'oc' in data_block:
                            chain_raw = data_block['oc']
                        elif isinstance(data_block, (dict, list)):
                            chain_raw = data_block
                        elif isinstance(raw_data, list):
                            chain_raw = raw_data
                        else:
                            chain_raw = {}

                        # Normalize — no ATM filter; we need exact requested strike
                        chain = normalize_option_chain(chain_raw, spot=0.0)

                        target_strike = float(strike)
                        for row in chain:
                            if row['strike'] == target_strike:
                                opt_data = row['ce'] if opt_type == 'CE' else row['pe']
                                
                                ltp = float(opt_data.get('lastPrice', opt_data.get('last_price', 0)))
                                bid = float(opt_data.get('bidPrice', opt_data.get('bid_price', opt_data.get('top_bid_price', 0))) or ltp)
                                ask = float(opt_data.get('askPrice', opt_data.get('ask_price', opt_data.get('top_ask_price', 0))) or ltp)
                                
                                self.logger.info(
                                    f"🔍 QUOTE DEBUG | strike={strike} | expiry={expiry} | "
                                    f"type={opt_type} | bid={bid} | ask={ask} | ltp={ltp} | "
                                    f"time={fetch_time_ms:.1f}ms"
                                )
                                
                                quote_obj = OptionQuote(
                                    security_id=opt_data.get('securityId', opt_data.get('security_id', '')),
                                    symbol=opt_data.get('tradingSymbol', opt_data.get('trading_symbol', f"NIFTY {strike} {opt_type}")),
                                    ltp=ltp,
                                    bid=bid,
                                    ask=ask,
                                    volume=int(opt_data.get('volume', 0)),
                                    oi=int(opt_data.get('openInterest', opt_data.get('oi', 0)))
                                )
                                if isinstance(response, dict) and "cache_metadata" in response:
                                    meta = response["cache_metadata"]
                                    quote_obj.is_stale = meta.get("is_stale", False)
                                    quote_obj.cache_age = meta.get("cache_age", 0.0)
                                    quote_obj.cache_source = meta.get("source", "api")
                                
                                self.logger.info(f"QUOTE_FETCH_SUCCESS | strike={strike} {opt_type} | premium={ltp}")
                                return quote_obj
                        
                        self.logger.warning(
                            f"🔍 QUOTE DEBUG | strike={strike} {opt_type} NOT FOUND in chain | time={fetch_time_ms:.1f}ms"
                        )
                except Exception as e:
                    self.logger.error(f"Option quote fetch failed: {e}")
                    self.logger.warning(f"🔍 QUOTE DEBUG | strike={strike} {opt_type} FAILED | error={str(e)}")
                    return None

        # 2. SIMULATION MODE (Synthetic Option Pricing)
        # This is CRITICAL for realistic paper trading offline.
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

        from core.options_resolver import OptionContractBuilder
        expiry_ctx = OptionContractBuilder.get_expiry_context()

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
            is_expiry_day=expiry_ctx.get("is_expiry_day", False),
            days_to_expiry=expiry_ctx.get("days_to_expiry", 7),
            is_monthly_expiry=(expiry_ctx.get("expiry_type") == "monthly"),
            expiry_type=expiry_ctx.get("expiry_type", "weekly"),
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

        from core.options_resolver import OptionContractBuilder
        expiry_ctx = OptionContractBuilder.get_expiry_context()

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
            is_expiry_day=expiry_ctx.get("is_expiry_day", False),
            days_to_expiry=expiry_ctx.get("days_to_expiry", 7),
            is_monthly_expiry=(expiry_ctx.get("expiry_type") == "monthly"),
            expiry_type=expiry_ctx.get("expiry_type", "weekly"),
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
        from utils.dns_health import get_dns_status

        avg_latency = 0.0
        if self._api_fetch_count > 0:
            avg_latency = self._api_total_latency_ms / self._api_fetch_count
            
        now_cb = time.time()
        oi_circuit_status = "OPEN" if now_cb < self.oi_circuit["open_until"] else "CLOSED"
        quote_circuit_status = "OPEN" if now_cb < self.quote_circuit["open_until"] else "CLOSED"
        oi_cooldown = max(0, int(self.oi_circuit["open_until"] - now_cb))
        quote_cooldown = max(0, int(self.quote_circuit["open_until"] - now_cb))

        result = {
            "last_api_fetch_ts": self._last_api_fetch_ts,
            "cache_hit_count": self._api_cache_hit_count,
            "api_fetch_count": self._api_fetch_count,
            "avg_fetch_latency": avg_latency,
            "oi_circuit": oi_circuit_status,
            "quote_circuit": quote_circuit_status,
            "oi_cooldown_seconds": oi_cooldown,
            "quote_cooldown_seconds": quote_cooldown,
            "cooldown_remaining_seconds": oi_cooldown,
            "cooldown_remaining_formatted": f"{oi_cooldown // 60}m {oi_cooldown % 60}s" if oi_cooldown > 0 else "0s",
            "last_oi_error": self.oi_circuit["last_error"],
            "last_quote_error": self.quote_circuit["last_error"],
            "last_oi_success": datetime.fromtimestamp(self._oi_last_success_ts).strftime("%Y-%m-%d %H:%M:%S") if self._oi_last_success_ts > 0 else None,
            "executor_active_threads": len(_OI_EXECUTOR._threads),
            "executor_pending_tasks": _OI_EXECUTOR._work_queue.qsize(),
            "oi_updater_alive": self._oi_updater_running and (time.time() - self._oi_updater_last_tick < 120),
            "oi_updater_age_sec": int(time.time() - self._oi_updater_last_tick) if self._oi_updater_last_tick > 0 else -1,
        }
        result.update(get_dns_status())
        return result

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

            # ── CRITICAL: Seed last_market_activity_ts from bootstrap ──
            # Without this, the orchestrator sees None → DataHealth.DEAD
            # and the system stays DEGRADED until an incremental fetch
            # succeeds (which itself requires LIVE session + is_market_open).
            # This breaks the chicken-and-egg deadlock.
            try:
                last_ts = df.index[-1]
                if hasattr(last_ts, "to_pydatetime"):
                    last_ts = last_ts.to_pydatetime()
                if hasattr(last_ts, "tzinfo") and last_ts.tzinfo is not None:
                    last_ts = last_ts.replace(tzinfo=None)
                self.last_market_activity_ts = last_ts
                self.logger.info(
                    f"📌 Bootstrap seeded last_market_activity_ts = {last_ts}"
                )
            except Exception as e:
                self.logger.warning(f"Failed to seed last_market_activity_ts from bootstrap: {e}")

            # Capping memory
            MAX_CANDLES = 2000
            if len(self.ohlcv_data) > MAX_CANDLES:
                self.ohlcv_data = self.ohlcv_data.tail(MAX_CANDLES)

            return self.df_1m

        except Exception as e:
            self.logger.critical(f"API CRITICAL FAILURE during bootstrap: {str(e)}")
            return pd.DataFrame()


    @staticmethod
    def _classify_api_failure(error: Exception) -> str:
        """Classify API failure for circuit breaker decisions."""
        err_str = str(error).lower()
        if "getaddrinfo" in err_str or "name resolution" in err_str or "resolve" in err_str:
            return "DNS_FAILURE"
        if "connection" in err_str or "timeout" in err_str or "reset" in err_str:
            return "NETWORK_FAILURE"
        if "401" in err_str or "403" in err_str or "808" in err_str or "dh-901" in err_str:
            return "AUTH_FAILURE"
        if "429" in err_str or "805" in err_str or "rate" in err_str:
            return "RATE_LIMIT"
        return "API_FAILURE"

    def _fetch_from_api_incremental(self) -> pd.DataFrame:
        """
        🚀 RUNTIME OPTIMIZATION: Incremental streaming update.
        Only fetches today's candles. Uses precise row updating/appending.
        """
        import time
        if not self._is_market_open_safe():
            return self.ohlcv_data

        # ── DNS Guard: Don't attempt API call if DNS is broken ──
        from utils.dns_health import dns_ok
        if not dns_ok():
            return self.ohlcv_data

        if time.time() < self._api_circuit_breaker_until:
            return self.ohlcv_data

        now = time.time()
        time_since_last_api = now - self._last_api_fetch_ts
        if time_since_last_api < self._api_fetch_cooldown:
            return self.ohlcv_data

        try:
            now = time.time()
            if hasattr(self, '_last_api_fetch_ts') and (now - self._last_api_fetch_ts) < 0.9:
                if self.ohlcv_data is not None and not self.ohlcv_data.empty:
                    return self.ohlcv_data

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

            # Keep all candles, including the active mutating one
            # if len(df_new) > 1:
            #     df_new = df_new.iloc[:-1]

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
                    # ── P1 Fix: Handle Broker Lag (Stale array + live mutation) ──
                    # Instead of rejecting, we assume the broker's endpoint is lagging behind
                    # the real world, but the *last row* is still carrying live prices.
                    self.logger.warning(f"⚠️ [DATA_STATE] BROKER_LAG: Broker API timestamp frozen at {latest_api_ts} while local is {last_ts}.")
                    # Update the local candle with the live price
                    live_close = df_new.iloc[-1]['close']
                    self.ohlcv_data.iloc[-1, self.ohlcv_data.columns.get_loc('close')] = live_close
                    self.ohlcv_data.iloc[-1, self.ohlcv_data.columns.get_loc('high')] = max(self.ohlcv_data.iloc[-1]['high'], live_close)
                    self.ohlcv_data.iloc[-1, self.ohlcv_data.columns.get_loc('low')] = min(self.ohlcv_data.iloc[-1]['low'], live_close)

                # ── P2 Fix: Synthetic Candle Fallback (>120s lag) ──
                # If local time has advanced to a new minute, but the broker hasn't delivered
                # a new candle for > 120 seconds, we synthesize a candle to prevent dataframe lag.
                current_minute = pd.Timestamp(datetime.now()).floor('min')
                local_last_ts = self.ohlcv_data.index[-1]
                
                lag_seconds = (datetime.now() - local_last_ts.to_pydatetime()).total_seconds()
                
                if lag_seconds > 120 and current_minute > local_last_ts:
                    self.logger.warning(
                        f"⚠️ [DATA_STATE] BROKER_LAG > 120s! Synthesizing missing candle for {current_minute} "
                        f"to prevent indicator distortion."
                    )
                    last_close = self.ohlcv_data.iloc[-1]['close']
                    new_candle = pd.Series({
                        'open': last_close,
                        'high': last_close,
                        'low': last_close,
                        'close': last_close,
                        'volume': 0
                    }, name=current_minute)
                    self.ohlcv_data.loc[current_minute] = new_candle
                    self.last_new_candle_ts = time.time()

            # Memory limit
            MAX_CANDLES = 2000
            if len(self.ohlcv_data) > MAX_CANDLES:
                self.ohlcv_data = self.ohlcv_data.tail(MAX_CANDLES)

            self.df_1m = self.ohlcv_data
            return self.ohlcv_data

        except Exception as e:
            failure_type = self._classify_api_failure(e)
            self._api_failures += 1
            self.logger.error(f"Incremental fetch exception [{failure_type}]: {e}")
            if failure_type == "DNS_FAILURE":
                # Don't trip circuit breaker for DNS — it's infrastructure, not API.
                # dns_health.py will gate future calls anyway.
                pass
            elif self._api_failures >= 3:
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
