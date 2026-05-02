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
from models.signals import Direction, Strength, MarketSnapshot
from agents.market_agent import MarketAgent
from agents.momentum_agent import MomentumAgent
from agents.trap_agent import TrapAgent
from agents.risk_agent import RiskAgent


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

    def test_daily_limit_reached(self, settings, sample_df, bullish_snapshot):
        agent = RiskAgent(settings)
        agent.daily_trades = settings.trading.max_daily_trades

        output = agent.run(sample_df, bullish_snapshot)

        assert output.confidence == 0
        assert any("MAX TRADES" in w for w in output.warnings)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
