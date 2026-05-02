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
        self._api_security_id = None
        self._api_exchange_segment = "IDX_I"  # Default for index
        self._api_instrument_type = "INDEX"

        # ── Real OI Cache (refreshed every 60s) ──
        self._oi_cache: dict = {}
        self._oi_last_fetch: float = 0.0
        self._oi_fetch_interval: float = 60.0  # seconds

        # Simulated state
        self._sim_price = 22700.0
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
        if self.data_source == "simulated":
            # Simulation is fast enough locally, but we still make it async-compliant
            df = self._fetch_simulated()
        elif self.data_source == "api":
            # In a real live environment, we'd use 'session' here to call Dhan API
            # For now, we reuse the existing logic but keep the interface
            df = self._fetch_from_api()
        else:
            df = self._fetch_simulated()

        self.ohlcv_data = df
        snapshot = self.get_snapshot_incremental(df)
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

            # Dhan option chain call — adjust expiry_date to nearest Thursday
            from datetime import date, timedelta
            today = date.today()
            days_to_thursday = (3 - today.weekday()) % 7  # Thursday = 3
            expiry = today + timedelta(days=days_to_thursday)
            expiry_str = expiry.strftime("%Y-%m-%d")

            response = dhan.get_option_chain(
                UnderlyingScrip=instrument,
                ExpiryDate=expiry_str
            )

            if response.get('status') != 'success':
                self.logger.warning(f"OI Fetch failed: {response.get('remarks')}")
                return {}

            chain = response.get('data', {}).get('data', [])
            if not chain:
                return {}

            total_ce_oi, total_pe_oi = 0.0, 0.0
            max_ce_oi, max_pe_oi = 0.0, 0.0
            max_ce_strike, max_pe_strike = 0, 0
            max_pain_strike = 0

            for row in chain:
                ce = row.get('callOption', {})
                pe = row.get('putOption', {})
                strike = row.get('strikePrice', 0)

                ce_oi = float(ce.get('openInterest', 0))
                pe_oi = float(pe.get('openInterest', 0))

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
            self.logger.info(
                f"🟢 REAL OI Fetched: CE={total_ce_oi/1e6:.1f}M | "
                f"PE={total_pe_oi/1e6:.1f}M | PCR={pcr}"
            )
            return result

        except Exception as e:
            self.logger.warning(f"⚠️ OI Fetch failed (using simulated): {e}")
            return {'data_source': DataSource.SIMULATED}

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

        return MarketSnapshot(
            timestamp=datetime.now(),
            price=price, open=latest['open'], high=high, low=low, close=price,
            volume=int(vol),
            vwap=vwap_val,
            rsi=rsi_val,
            ema_fast=self.cached_ema_fast,
            ema_slow=self.cached_ema_slow,
            atr=self.cached_atr,
            # ⚠️ P1.2: All OI/Greeks/VIX below are SIMULATED — agents must check oi_data_source
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
        )

        print("Current Price:", snapshot.price)
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
        self._sim_price = max(22600, min(22800, self._sim_price))

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
            price = max(22600, min(22800, price))

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
        try:
            dhan = get_dhan_client()

            # 1. Dynamic Security ID Discovery
            if self._api_security_id is None:
                self._api_security_id = self._discover_nifty_id(dhan)

            # 2. Fetch Intraday 1-minute data
            today_str = datetime.now().strftime("%Y-%m-%d")
            response = dhan.intraday_minute_data(
                security_id=self._api_security_id,
                exchange_segment=self._api_exchange_segment,
                instrument_type=self._api_instrument_type,
                from_date=today_str,
                to_date=today_str
            )

            if response.get('status') != 'success':
                self.logger.error(f"Dhan API Error: {response}")
                raise RuntimeError(f"API Data Failure: {response.get('remarks')}")

            raw_data = response.get('data', [])
            if not raw_data:
                self.logger.warning("No data returned from API")
                return pd.DataFrame()

            # 3. Convert to DataFrame & Cleanup
            df = pd.DataFrame(raw_data)
            if 'start_Time' in df.columns:
                df['timestamp'] = pd.to_datetime(df['start_Time'])
                df.set_index('timestamp', inplace=True)

            df.columns = [c.lower() for c in df.columns]

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

            return self.df_1m

        except Exception as e:
            self.logger.critical(f"API CRITICAL FAILURE: {str(e)}")
            # No silent fallback for live API
            raise RuntimeError(f"System halted: {str(e)}")

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

                if gap > self.settings.trade_filter.gap_threshold_points:
                    self.logger.warning(f"🚨 LARGE GAP DETECTED: {gap:.1f} pts! Indicators may be unstable.")
                    # We can set a flag here to delay trading if needed

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
        """Check if current time is after market_open_safe_time (09:20)"""
        now = datetime.now()
        safe_time_str = self.settings.trade_filter.market_open_safe_time
        safe_h, safe_m = map(int, safe_time_str.split(':'))
        safe_time = now.replace(hour=safe_h, minute=safe_m, second=0, microsecond=0)

        if now < safe_time:
            self.logger.info(f"Market session start protection — waiting until {safe_time_str}")
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
