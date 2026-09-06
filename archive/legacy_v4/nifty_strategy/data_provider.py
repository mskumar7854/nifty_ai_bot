"""
============================================
DATA PROVIDER
============================================
Fetches OHLCV candles from Dhan API.
Falls back to synthetic data for offline dev.

Replace mock methods with actual dhanhq calls
once you have live API access confirmed.
============================================
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional, Callable

from .config import Config


# ══════════════════════════════════════════
# BASE PROVIDER
# ══════════════════════════════════════════

class DataProvider:
    """Abstract base — all providers implement get_candles()."""

    def get_candles(
        self,
        symbol: str,
        timeframe: str,
        from_time: datetime,
        to_time: datetime,
    ) -> pd.DataFrame:
        raise NotImplementedError

    def get_live_quote(self, security_id: str) -> dict:
        raise NotImplementedError


# ══════════════════════════════════════════
# DHAN DATA PROVIDER
# ══════════════════════════════════════════

class DhanDataProvider(DataProvider):
    """
    Fetch historical candles from Dhan.

    When DHAN credentials are active, call the real API.
    Otherwise returns synthetic data so the strategy loop
    can run and be tested without a live connection.
    """

    # Timeframe → Dhan interval string mapping
    TF_MAP = {
        '1min':  '1',
        '3min':  '3',
        '5min':  '5',
        '15min': '15',
        '30min': '30',
        '60min': '60',
    }

    def __init__(self, dhan_client=None):
        """
        dhan_client: dhanhq instance (optional).
                     If None, synthetic data is used.
        """
        self._client = dhan_client

    def get_candles(
        self,
        symbol: str,
        timeframe: str,
        from_time: datetime,
        to_time: datetime,
    ) -> pd.DataFrame:
        """
        Fetch OHLCV data.

        Real call (when live):
            self._client.historical_daily_data(
                security_id=..., exchange_segment="NSE_EQ",
                instrument_type="INDEX",
                from_date=..., to_date=...,
            )
        or intraday:
            self._client.intraday_minute_data(
                security_id=..., exchange_segment=...,
                instrument_type=...,
                from_date=..., to_date=...,
                interval=self.TF_MAP[timeframe],
            )
        """
        if self._client:
            try:
                return self._fetch_from_dhan(symbol, timeframe, from_time, to_time)
            except Exception as e:
                print(f"[DhanDataProvider] API error ({e}) — using synthetic data")

        return self._generate_synthetic(timeframe, from_time, to_time)

    def _fetch_from_dhan(
        self,
        symbol: str,
        timeframe: str,
        from_time: datetime,
        to_time: datetime,
    ) -> pd.DataFrame:
        """
        ── REPLACE THIS BODY WITH ACTUAL DHAN CALL ──
        Example:
            response = self._client.intraday_minute_data(
                security_id="13",           # Nifty 50 index ID
                exchange_segment="NSE_EQ",
                instrument_type="INDEX",
                from_date=from_time.strftime("%Y-%m-%d"),
                to_date=to_time.strftime("%Y-%m-%d"),
                interval=self.TF_MAP.get(timeframe, "5"),
            )
            return pd.DataFrame(response['data'])
        """
        # Stub — returns synthetic until you wire the real call
        return self._generate_synthetic(timeframe, from_time, to_time)

    def _generate_synthetic(
        self,
        timeframe: str,
        from_time: datetime,
        to_time: datetime,
        base_price: float = 22_800,
    ) -> pd.DataFrame:
        """Deterministic synthetic OHLCV for testing."""
        minutes = int(timeframe.replace('min', ''))
        total_secs = int((to_time - from_time).total_seconds())
        periods = max(1, total_secs // (minutes * 60))

        np.random.seed(int(from_time.timestamp()) % 2**31)

        timestamps = [from_time + timedelta(minutes=i * minutes) for i in range(periods)]
        prices = base_price + np.cumsum(np.random.randn(periods) * 15)

        opens  = prices + np.random.randn(periods) * 8
        highs  = np.maximum(opens, prices) + np.abs(np.random.randn(periods) * 12)
        lows   = np.minimum(opens, prices) - np.abs(np.random.randn(periods) * 12)
        closes = prices + np.random.randn(periods) * 8
        volumes = np.random.randint(80_000, 450_000, periods).astype(float)

        df = pd.DataFrame({
            'open':   np.round(opens,  2),
            'high':   np.round(highs,  2),
            'low':    np.round(lows,   2),
            'close':  np.round(closes, 2),
            'volume': volumes,
        }, index=pd.DatetimeIndex(timestamps, name='timestamp'))

        return df

    def get_live_quote(self, security_id: str) -> dict:
        """Return LTP. Replace with actual dhanhq call."""
        if self._client:
            try:
                # Placeholder:
                # return self._client.get_ltp_data(security_id=security_id)
                pass
            except Exception as e:
                print(f"[DhanDataProvider] quote error: {e}")

        return {
            'last_price': 0,
            'bid_price': 0,
            'ask_price': 0,
            'volume': 0,
            'timestamp': datetime.now(),
        }


# ══════════════════════════════════════════
# CANDLE AGGREGATOR  (tick → OHLCV)
# ══════════════════════════════════════════

class CandleAggregator:
    """
    Aggregate real-time ticks into OHLCV candles.

    Feed ticks from WebSocket → get_recent_candles()
    for the strategy to consume.
    """

    def __init__(self, timeframe: str = "5min"):
        self.minutes = int(timeframe.replace('min', ''))
        self._current: Optional[dict] = None
        self._completed: list[pd.Series] = []

    def add_tick(self, price: float, volume: float, ts: Optional[datetime] = None):
        """Add one market tick."""
        ts = ts or datetime.now()
        candle_start = ts.replace(
            minute=(ts.minute // self.minutes) * self.minutes,
            second=0, microsecond=0,
        )

        if self._current is None or candle_start != self._current['start']:
            if self._current:
                self._completed.append(self._to_series(self._current))

            self._current = dict(
                start=candle_start,
                open=price, high=price, low=price, close=price, volume=volume,
            )
        else:
            c = self._current
            c['high']   = max(c['high'], price)
            c['low']    = min(c['low'],  price)
            c['close']  = price
            c['volume'] += volume

    def _to_series(self, c: dict) -> pd.Series:
        return pd.Series({
            'open': c['open'], 'high': c['high'],
            'low': c['low'],   'close': c['close'],
            'volume': c['volume'],
        }, name=c['start'])

    def get_recent_candles(self, count: int = 100) -> pd.DataFrame:
        rows = self._completed[-count:]
        if not rows:
            return pd.DataFrame(columns=['open', 'high', 'low', 'close', 'volume'])
        return pd.DataFrame(rows)
