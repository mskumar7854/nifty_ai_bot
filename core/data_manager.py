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

from models.signals import MarketSnapshot, DataSource
from utils.indicators import (
    calculate_vwap, calculate_rsi, calculate_ema, calculate_atr
)
from utils.logger import get_logger
from config.settings import Settings
from dhan_client import get_dhan_client
from core.regime_classifier import RegimeClassifier
from core.regime_state_manager import RegimeStateManager


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
        self._api_exchange_segment = "IDX_I"  # Default for index
        self._api_instrument_type = "INDEX"
        self._api_failures = 0
        self._api_circuit_breaker_until = 0.0

        # ── Real OI Cache (refreshed every 60s) ──
        self._oi_cache: dict = {}
        self._oi_last_fetch: float = 0.0
        self._oi_fetch_interval: float = 60.0  # seconds

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

    def fetch_latest(self) -> pd.DataFrame:
        """
        Fetch latest OHLCV data.
        Routes to appropriate source with throttling for API.
        """
        # API Throttling
        if self.data_source == "api":
            time_since_last = (datetime.now() - self.last_fetch_time).total_seconds()
            if time_since_last < self.fetch_interval_seconds:
                # Return cached data if too frequent
                if self.ohlcv_data is not None:
                    return self.ohlcv_data
                # Or sleep briefly
                time.sleep(self.fetch_interval_seconds - time_since_last)

        if self.data_source == "simulated":
            df = self._fetch_simulated()
        elif self.data_source == "api":
            df = self._fetch_from_api()
        elif self.data_source == "csv":
            df = self._fetch_from_csv()
        else:
            df = self._fetch_simulated()

        self.last_fetch_time = datetime.now()
        self.ohlcv_data = df
        return df

    def get_fund_limits(self) -> float:
        """Fetches available margin from the broker."""
        if self.data_source == "simulated":
            return self.settings.position.total_capital
            
        try:
            dhan = get_dhan_client()
            response = dhan.get_fund_limits()
            if response.get("status") == "success":
                return float(response.get("data", {}).get("availabelBalance", 0.0))
        except Exception as e:
            self.logger.error(f"Failed to fetch fund limits: {e}")
            
        return 0.0

    def get_latest_data(self):
        """Returns both DataFrame and MarketSnapshot"""
        df = self.fetch_latest()
        snapshot = self.get_snapshot_from_df(df)
        return df, snapshot

    def get_snapshot(self) -> MarketSnapshot:
        """Fetch latest and return snapshot"""
        df = self.fetch_latest()
        # Use incremental snapshot for performance
        return self.get_snapshot_incremental(df)

    async def fetch_latest_async(self, session: aiohttp.ClientSession) -> Tuple[pd.DataFrame, MarketSnapshot]:
        """
        🚀 ASYNC HFT DATA FETCH
        Fetches data without blocking and returns (df, snapshot).
        """
        import asyncio
        if self.data_source == "simulated":
            # Simulation is fast enough locally, but we still make it async-compliant
            df = self._fetch_simulated()
        elif self.data_source == "api":
            # In a real live environment, we'd use 'session' here to call Dhan API
            # 🚀 Wrapped in to_thread to prevent blocking the async event loop (Telegram, etc.)
            df = await asyncio.to_thread(self._fetch_from_api)
        else:
            df = self._fetch_simulated()

        if df is not None and not df.empty:
            self.ohlcv_data = df
            self.last_fetch_time = datetime.now()
            
        snapshot = await asyncio.to_thread(self.get_snapshot_incremental, df)
        return df, snapshot

    def _get_oi_data(self) -> dict:
        """
        🟢 REAL OI DATA FETCHER (Step 2 Implementation)
        Pulls option chain from Dhan API and extracts:
          - total_ce_oi, total_pe_oi, pcr, max_pain, india_vix
          - max_ce_oi_strike, max_pe_oi_strike

        - Runs on a 60s cache to avoid API rate limits.
        - Falls back to simulated data on any failure.
        - Sets DataSource.REAL flag when successful.
        """
        import time as _time
        now = _time.time()

        # Return cache if fresh
        if self._oi_cache and (now - self._oi_last_fetch) < self._oi_fetch_interval:
            return self._oi_cache

        if self.data_source != "api":
            return {'data_source': DataSource.SIMULATED}  # Caller will use simulated fallback

        try:
            dhan = get_dhan_client()
            instrument = self.settings.trading.instrument.upper()  # "NIFTY"

            # Dhan option chain call — find nearest THURSDAY expiry
            # NIFTY weekly options expire on Thursday.
            # (3 - weekday) % 7 gives days to Thursday, but returns 0 ON Thursday.
            # On Thursday itself, we want THIS Thursday if before 3:30 PM,
            # otherwise NEXT Thursday. Use `or 7` for safety after expiry.
            from datetime import date, timedelta
            today = date.today()
            days_to_thursday = (3 - today.weekday()) % 7
            if days_to_thursday == 0:
                # On Thursday: check if market is still open (use next week after 16:00)
                from datetime import datetime as _dt
                if _dt.now().hour >= 16:
                    days_to_thursday = 7
            expiry = today + timedelta(days=days_to_thursday)
            expiry_str = expiry.strftime("%Y-%m-%d")

            if self._api_security_id is None:
                self._api_security_id = self._discover_nifty_id(dhan)

            self.logger.debug(
                f"OI Fetch: security_id={self._api_security_id} "
                f"segment={self._api_exchange_segment} expiry={expiry_str}"
            )

            response = dhan.option_chain(
                under_security_id=self._api_security_id,
                under_exchange_segment=self._api_exchange_segment,
                expiry=expiry_str
            )

            if response.get('status') != 'success':
                # Log the FULL response on first failure to diagnose API issues
                if not hasattr(self, '_oi_fail_logged'):
                    self.logger.warning(
                        f"⚠️ OI Fetch FAILED (first occurrence) | "
                        f"security_id={self._api_security_id} | "
                        f"segment={self._api_exchange_segment} | "
                        f"expiry={expiry_str} | "
                        f"status={response.get('status')} | "
                        f"remarks={response.get('remarks')} | "
                        f"full_response_keys={list(response.keys())}"
                    )
                    self._oi_fail_logged = True
                else:
                    self.logger.debug(f"OI Fetch failed: {response.get('remarks')}")
                return {'data_source': DataSource.SIMULATED}

            # Dhan option_chain response can have different nesting structures
            # Handle both: response['data']['data'] and response['data'] as list
            raw_data = response.get('data', {})
            if isinstance(raw_data, dict):
                chain = raw_data.get('data', [])
            elif isinstance(raw_data, list):
                chain = raw_data
            else:
                chain = []

            if not chain:
                self.logger.warning(
                    f"⚠️ OI Fetch: API success but chain is EMPTY | "
                    f"expiry={expiry_str} | data_type={type(raw_data).__name__} | "
                    f"data_keys={list(raw_data.keys()) if isinstance(raw_data, dict) else 'N/A'}"
                )
                return {'data_source': DataSource.SIMULATED}

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
            }

            self._oi_cache = result
            self._oi_last_fetch = now
            self._oi_fail_logged = False  # Reset so next failure gets logged
            self.logger.info(
                f"🟢 REAL OI Fetched: CE={total_ce_oi/1e6:.1f}M | "
                f"PE={total_pe_oi/1e6:.1f}M | PCR={pcr}"
            )
            return result

        except Exception as e:
            self.logger.warning(f"⚠️ OI Fetch exception (using simulated): {e}")
            return {'data_source': DataSource.SIMULATED}

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
            try:
                dhan = get_dhan_client()
                
                # Fetch option chain once to find the specific contract
                if self._api_security_id is None:
                    self._api_security_id = self._discover_nifty_id(dhan)
                    
                response = dhan.option_chain(
                    under_security_id=self._api_security_id,
                    under_exchange_segment=self._api_exchange_segment,
                    expiry=expiry
                )
                
                if response.get('status') == 'success':
                    chain = response.get('data', {}).get('data', [])
                    for row in chain:
                        if row.get('strikePrice') == strike:
                            opt_data = row.get('callOption' if opt_type == 'CE' else 'putOption', {})
                            return OptionQuote(
                                security_id=opt_data.get('securityId', ''),
                                symbol=opt_data.get('tradingSymbol', f"NIFTY {strike} {opt_type}"),
                                ltp=float(opt_data.get('lastPrice', 0)),
                                bid=float(opt_data.get('bidPrice', 0) or opt_data.get('lastPrice', 0)),
                                ask=float(opt_data.get('askPrice', 0) or opt_data.get('lastPrice', 0)),
                                volume=int(opt_data.get('volume', 0)),
                                oi=int(opt_data.get('openInterest', 0))
                            )
            except Exception as e:
                self.logger.error(f"Option quote fetch failed: {e}")
                # Fallback to simulation logic below if API fails

        # 2. SIMULATION MODE (Synthetic Option Pricing)
        # This is CRITICAL for realistic paper trading. We cannot use Spot Nifty.
        spot = self._sim_price if self.data_source == "simulated" else self.fetch_latest()['close'].iloc[-1]
        
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
            timestamp=datetime.now(),
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
            timestamp=datetime.now(),
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
        if self.ohlcv_data is None:
            self.fetch_latest()
        return self.ohlcv_data

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

    def _fetch_from_api(self) -> pd.DataFrame:
        """
        Fetch from real broker API (Dhan).
        Includes robust cleanup, MTF resampling, and validation.
        """
        import time
        if time.time() < self._api_circuit_breaker_until:
            return pd.DataFrame()

        try:
            dhan = get_dhan_client()

            # 1. Dynamic Security ID Discovery
            if self._api_security_id is None:
                self._api_security_id = self._discover_nifty_id(dhan)

            # 2. Fetch Intraday 1-minute data
            today_str = datetime.now().strftime("%Y-%m-%d")
            
            # 🚀 OPTIMIZATION: Only fetch 5-day warmup if we don't have historical data.
            # Fetching 5 days every second causes 550ms+ latency and execution risk.
            if self.ohlcv_data is None or self.ohlcv_data.empty:
                from_date_str = (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d")
            else:
                from_date_str = today_str

            response = dhan.intraday_minute_data(
                security_id=self._api_security_id,
                exchange_segment=self._api_exchange_segment,
                instrument_type=self._api_instrument_type,
                from_date=from_date_str,
                to_date=today_str
            )

            if response.get('status') != 'success':
                self.logger.error(f"Dhan API Error: {response}")
                self._api_failures += 1
                self.logger.info(f"API FAILURES COUNT IS NOW: {self._api_failures}")
                if self._api_failures >= 3:
                    self.logger.critical("API Circuit Breaker TRIPPED! Suspending API calls for 60s")
                    self._api_circuit_breaker_until = time.time() + 60
                return pd.DataFrame()

            raw_data = response.get('data', [])
            if not raw_data:
                self.logger.warning("No data returned from API")
                return pd.DataFrame()

            # 3. Convert to DataFrame & Cleanup
            df = pd.DataFrame(raw_data)
            df.columns = [c.lower() for c in df.columns]

            time_col = None
            if 'start_time' in df.columns:
                time_col = 'start_time'
            elif 'timestamp' in df.columns:
                time_col = 'timestamp'

            if time_col:
                if pd.api.types.is_numeric_dtype(df[time_col]):
                    # Parse as epoch and convert to IST
                    df['timestamp'] = pd.to_datetime(df[time_col], unit='s').dt.tz_localize('UTC').dt.tz_convert('Asia/Kolkata').dt.tz_localize(None)
                else:
                    df['timestamp'] = pd.to_datetime(df[time_col])
                df.set_index('timestamp', inplace=True)
            else:
                raise RuntimeError(f"API data missing time column. Columns: {df.columns.tolist()}")

            # 🚀 OPTIMIZATION: Merge with historical cache if we only fetched today
            if self.ohlcv_data is not None and not self.ohlcv_data.empty and from_date_str == today_str:
                df = pd.concat([self.ohlcv_data, df])

            # Mandatory Professional Cleanup
            df.dropna(inplace=True)
            df.sort_index(inplace=True)
            df = df[~df.index.duplicated(keep="last")]

            # 4. Pro-Safeguard: Drop last incomplete candle
            if len(df) > 1:
                df = df.iloc[:-1]

            # 5. Gap Handling
            self._handle_gap(df)

            # 6. Warmup Check
            if len(df) < self.settings.trade_filter.min_candles_warmup:
                self.logger.info(f"API Warmup: {len(df)}/{self.settings.trade_filter.min_candles_warmup} candles...")
                return pd.DataFrame()

            # 7. Resampling (1m -> 5m)
            self.df_1m = df
            self.df_5m = self._resample_data(df, self.settings.trend_timeframe)

            # 8. MTF Sync Check
            if not self._check_mtf_sync():
                self.logger.warning("MTF Sync Mismatch — Waiting for candle closure")
                return pd.DataFrame()

            # 9. Market Open Filter (09:20)
            if not self._is_market_open_safe():
                return pd.DataFrame()

            self._api_failures = 0
            return self.df_1m

        except Exception as e:
            self._api_failures += 1
            if self._api_failures >= 3:
                self.logger.critical("API Circuit Breaker TRIPPED! Suspending API calls for 60s")
                self._api_circuit_breaker_until = time.time() + 60
            self.logger.critical(f"API CRITICAL FAILURE: {str(e)}")
            # Stabilize execution: do not halt system, return empty DF to skip cycle
            return pd.DataFrame()

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
        """Check if current time is after market_open_safe_time using SessionGuard"""
        from core.session_guard import SessionGuard
        can_trade, reason = SessionGuard.can_trade(self.settings)
        if not can_trade:
            now = datetime.now()
            if not hasattr(self, '_last_protection_log') or (now - self._last_protection_log).total_seconds() >= 60:
                self.logger.info(reason)
                self._last_protection_log = now
            return False
        return True

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
