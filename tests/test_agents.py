"""
============================================
AGENT TESTS
Run: pytest tests/ -v
============================================
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from config.settings import Settings
from models import Direction, Strength, MarketSnapshot
from agents.market_agent import MarketAgent
from agents.momentum_agent import MomentumAgent
from agents.trap_agent import TrapAgent
from agents.risk_agent import RiskAgent
from agents.time_session_agent import TimeSessionAgent
from core.data_manager import DataManager


@pytest.fixture
def settings():
    return Settings()


@pytest.fixture
def sample_df():
    """Generate sample OHLCV data"""
    data = []
    price = 24500

    for i in range(100):
        o = price + np.random.normal(0, 10)
        h = max(o, price) + abs(np.random.normal(0, 15))
        l = min(o, price) - abs(np.random.normal(0, 15))
        v = int(np.random.uniform(50000, 500000))
        price += np.random.normal(2, 5)  # Slight uptrend

        data.append({
            'timestamp': datetime.now() - timedelta(minutes=(100 - i)),
            'open': round(o, 2),
            'high': round(h, 2),
            'low': round(l, 2),
            'close': round(price, 2),
            'volume': v,
        })

    return pd.DataFrame(data)


@pytest.fixture
def bullish_snapshot():
    return MarketSnapshot(
        timestamp=datetime.now(),
        price=24600,
        open=24550, high=24620, low=24540, close=24600,
        volume=200000,
        vwap=24500,
        rsi=65,
        ema_fast=24580,
        ema_slow=24550,
        atr=30,
        total_ce_oi=5000000,
        total_pe_oi=6000000,
        pcr=1.2,
        max_pain=24500,
        india_vix=13.5,
    )


class TestMarketAgent:
    def test_bullish_detection(self, settings, sample_df, bullish_snapshot):
        agent = MarketAgent(settings)
        output = agent.run(sample_df, bullish_snapshot)

        assert output.agent_name == "market"
        assert output.direction == Direction.BULLISH
        assert output.confidence > 50

    def test_neutral_near_vwap(self, settings, sample_df):
        snapshot = MarketSnapshot(
            timestamp=datetime.now(),
            price=24502, open=24500, high=24510, low=24495, close=24502,
            volume=100000, vwap=24500, rsi=50,
            ema_fast=24500, ema_slow=24500, atr=25,
        )
        agent = MarketAgent(settings)
        output = agent.run(sample_df, snapshot)

        assert output.direction == Direction.NEUTRAL or output.confidence < 60


class TestMomentumAgent:
    def test_strong_momentum(self, settings, sample_df, bullish_snapshot):
        agent = MomentumAgent(settings)
        output = agent.run(sample_df, bullish_snapshot)

        assert output.agent_name == "momentum"
        assert output.confidence > 0


class TestRiskAgent:
    def test_initial_risk_ok(self, settings, sample_df, bullish_snapshot):
        agent = RiskAgent(settings)
        output = agent.run(sample_df, bullish_snapshot)

        assert output.confidence > 0
        assert "trades_today" in output.details


class TestTimeSessionAgent:
    def test_open_market_permission(self, settings, sample_df):
        # 09:28 on a Monday
        snap = MarketSnapshot(
            timestamp=datetime(2026, 9, 7, 9, 28, 5),
            price=24500, open=24500, high=24500, low=24500, close=24500,
            volume=1000, vwap=24500, rsi=50, ema_fast=24500, ema_slow=24500, atr=20
        )
        agent = TimeSessionAgent(settings)
        out = agent.run(sample_df, snap)
        assert out.is_blocker is False
        assert out.confidence >= 40

    def test_epoch_timestamp_fallback(self, settings, sample_df):
        # Epoch timestamp corruption (1970-01-01) should fall back to system clock and not crash
        snap = MarketSnapshot(
            timestamp=pd.to_datetime(100),
            price=24500, open=24500, high=24500, low=24500, close=24500,
            volume=1000, vwap=24500, rsi=50, ema_fast=24500, ema_slow=24500, atr=20
        )
        agent = TimeSessionAgent(settings)
        out = agent.run(sample_df, snap)
        assert out.agent_name == "time_session"


class TestDataManagerSnapshot:
    def test_simulated_snapshot_timestamp_integrity(self, settings):
        dm = DataManager(settings)
        df = dm._fetch_simulated()
        snap = dm.get_snapshot_incremental(df)
        assert isinstance(snap.timestamp, datetime)
        assert snap.timestamp.year >= 2026
        assert isinstance(df.index, pd.DatetimeIndex)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

