import pytest
import pandas as pd
from datetime import datetime, timedelta
from config.settings import Settings
from models import MarketSnapshot, DataSource
from agents.oi_agent import OIAgent

@pytest.fixture
def settings():
    # Use default settings which should now have our OI thresholds
    return Settings()

@pytest.fixture
def oi_agent(settings):
    return OIAgent(settings)

def test_oi_agent_initialization(oi_agent):
    assert oi_agent.name == "oi"
    assert len(oi_agent._history) == 0

def test_simulated_data_guard(oi_agent, settings):
    settings.system_mode.mode = "LIVE"
    
    # Empty chain, simulated data
    snapshot = MarketSnapshot(
        timestamp=datetime.now(),
        price=25000, open=25000, high=25000, low=25000, close=25000,
        volume=1000, vwap=25000, rsi=50, ema_fast=25000, ema_slow=25000, atr=50,
        oi_data_source=DataSource.SIMULATED,
        oi_chain_data=[]
    )
    
    df = pd.DataFrame()
    output = oi_agent.analyze(df, snapshot)
    
    assert output.details.get("abstained") is True
    assert output.details.get("reason") == "no_real_oi_data"

def test_empty_chain_guard(oi_agent, settings):
    settings.system_mode.mode = "SIMULATION" # Allow simulated data
    
    snapshot = MarketSnapshot(
        timestamp=datetime.now(),
        price=25000, open=25000, high=25000, low=25000, close=25000,
        volume=1000, vwap=25000, rsi=50, ema_fast=25000, ema_slow=25000, atr=50,
        oi_data_source=DataSource.REAL,
        oi_chain_data=[]
    )
    
    df = pd.DataFrame()
    output = oi_agent.analyze(df, snapshot)
    
    assert output.details.get("abstained") is True
    assert output.details.get("reason") == "empty_chain"

def test_zone_detection(oi_agent, settings):
    settings.system_mode.mode = "SIMULATION"
    
    # Synthetic chain data
    chain = [
        {"strike": 24800, "ce": {"oi": 100}, "pe": {"oi": 5000}},
        {"strike": 24850, "ce": {"oi": 150}, "pe": {"oi": 4000}},
        {"strike": 24900, "ce": {"oi": 200}, "pe": {"oi": 6000}}, # Put wall
        {"strike": 24950, "ce": {"oi": 300}, "pe": {"oi": 2000}},
        {"strike": 25000, "ce": {"oi": 8000}, "pe": {"oi": 1500}}, # Call wall
        {"strike": 25050, "ce": {"oi": 6000}, "pe": {"oi": 1000}}, # Call wall adjacent
        {"strike": 25100, "ce": {"oi": 150}, "pe": {"oi": 500}},
    ]
    
    snapshot = MarketSnapshot(
        timestamp=datetime.now(),
        price=24950, open=24950, high=24950, low=24950, close=24950,
        volume=1000, vwap=24950, rsi=50, ema_fast=24950, ema_slow=24950, atr=50,
        oi_data_source=DataSource.REAL,
        oi_chain_data=chain,
        oi_spot_price=24950
    )
    
    df = pd.DataFrame()
    output = oi_agent.analyze(df, snapshot)
    
    # Check that it didn't abstain
    assert not output.details.get("abstained")
    
    ms = output.details.get("market_structure")
    assert ms is not None
    assert ms["oi"] is not None
    
    oi_data = ms["oi"]
    
    res_zone = oi_data.get("resistance_zone")
    assert res_zone is not None
    assert res_zone["peak_strike"] == 25000
    assert res_zone["low"] == 25000
    assert res_zone["high"] == 25050
    
    sup_zone = oi_data.get("support_zone")
    assert sup_zone is not None
    assert sup_zone["peak_strike"] == 24900
    
def test_data_freshness_penalty(oi_agent, settings):
    settings.system_mode.mode = "SIMULATION"
    
    # Same chain as above
    chain = [
        {"strike": 24900, "ce": {"oi": 200}, "pe": {"oi": 6000}}, 
        {"strike": 24950, "ce": {"oi": 300}, "pe": {"oi": 2000}},
        {"strike": 25000, "ce": {"oi": 8000}, "pe": {"oi": 1500}}, 
    ]
    
    ts = datetime.now()
    
    # Mock data age
    snapshot = MarketSnapshot(
        timestamp=ts,
        price=24950, open=24950, high=24950, low=24950, close=24950,
        volume=1000, vwap=24950, rsi=50, ema_fast=24950, ema_slow=24950, atr=50,
        oi_data_source=DataSource.REAL,
        oi_chain_data=chain,
        oi_spot_price=24950,
    )
    
    snapshot.age_sec = 600 # 10 minutes old!
    
    df = pd.DataFrame()
    output = oi_agent.analyze(df, snapshot)
    
    ms = output.details.get("market_structure")
    oi_data = ms["oi"]
    
    # Should have heavily reduced reliability
    assert oi_data["reliability_score"] < 60
    assert oi_data["data_quality"] == "STALE"
    
    # Should appear in explanations
    assert any("✗" in expl for expl in oi_data["explanation"])
