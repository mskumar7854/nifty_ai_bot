from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

class DataSource(str, Enum):
    REAL = "real"
    SIMULATED = "simulated"
    UNKNOWN = "unknown"

class SessionPhase(Enum):
    PRE_MARKET = "PRE_MARKET"
    OPENING = "OPENING"
    MORNING = "MORNING"
    LUNCH = "LUNCH"
    AFTERNOON = "AFTERNOON"
    POWER_HOUR = "POWER_HOUR"
    CLOSING = "CLOSING"
    AFTER_HOURS = "AFTER_HOURS"

class TrapType(Enum):
    NONE = "NONE"
    FAKE_BREAKOUT_UP = "FAKE_BREAKOUT_UP"
    FAKE_BREAKOUT_DOWN = "FAKE_BREAKOUT_DOWN"
    LIQUIDITY_SWEEP = "LIQUIDITY_SWEEP"
    STOP_HUNT = "STOP_HUNT"

@dataclass
class OptionQuote:
    security_id: str
    symbol: str
    ltp: float
    bid: float
    ask: float
    volume: int = 0
    oi: int = 0
    iv: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    is_stale: bool = False
    cache_age: float = 0.0
    cache_source: str = "api"

    @property
    def spread_pct(self) -> float:
        if self.ask > 0:
            return ((self.ask - self.bid) / self.ask) * 100
        return 0.0

@dataclass
class MarketSnapshot:
    timestamp: datetime
    price: float
    open: float
    high: float
    low: float
    close: float
    volume: int
    vwap: float
    rsi: float
    ema_fast: float
    ema_slow: float
    atr: float
    total_ce_oi: float = 0
    total_pe_oi: float = 0
    pcr: float = 0
    max_pain: float = 0
    india_vix: float = 0

    rsi_5m: float = 50
    rsi_15m: float = 50
    ema_fast_5m: float = 0
    ema_slow_5m: float = 0
    ema_fast_15m: float = 0
    ema_slow_15m: float = 0
    vwap_5m: float = 0
    atr_5m: float = 0
    atr_15m: float = 0
    banknifty_price: float = 0
    banknifty_change_pct: float = 0
    sgx_nifty: float = 0
    dow_futures: float = 0
    bid_volume: float = 0
    ask_volume: float = 0
    large_buy_orders: int = 0
    large_sell_orders: int = 0
    prev_day_high: float = 0
    prev_day_low: float = 0
    prev_day_close: float = 0
    day_open: float = 0
    pivot: float = 0
    r1: float = 0
    r2: float = 0
    r3: float = 0
    s1: float = 0
    s2: float = 0
    s3: float = 0
    cpr_top: float = 0
    cpr_bottom: float = 0
    days_to_expiry: int = 7
    is_expiry_day: bool = False
    is_monthly_expiry: bool = False
    net_delta: float = 0
    net_gamma: float = 0
    iv_atm: float = 0
    iv_skew: float = 0
    fii_net: float = 0
    dii_net: float = 0
    fii_index_futures_oi_change: float = 0
    bb_upper: float = 0
    bb_lower: float = 0
    bb_middle: float = 0
    bb_width: float = 0
    expiry_type: str = "weekly"
    time_to_expiry_hours: float = 0
    minutes_to_close: int = 0
    atm_straddle_price: float = 0
    atm_straddle_open: float = 0
    straddle_decay_pct: float = 0
    atm_ce_premium: float = 0
    atm_pe_premium: float = 0
    atm_ce_premium_open: float = 0
    atm_pe_premium_open: float = 0
    atm_gamma: float = 0
    gamma_exposure: float = 0
    max_ce_oi_strike: float = 0
    max_pe_oi_strike: float = 0
    max_ce_oi_value: float = 0
    max_pe_oi_value: float = 0
    atm_iv: float = 0
    iv_change_today: float = 0
    iv_percentile_30d: float = 50.0
    oi_data_source: DataSource = DataSource.UNKNOWN
    regime_state: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "time": self.timestamp.strftime("%H:%M:%S"),
            "price": self.price,
            "vwap": self.vwap,
            "rsi": round(self.rsi, 2),
            "atr": round(self.atr, 2),
            "pcr": round(self.pcr, 2),
            "vix": self.india_vix,
            "regime": self.regime_state.get("regime", ""),
            "session": "",
            "regime_state": self.regime_state
        }
