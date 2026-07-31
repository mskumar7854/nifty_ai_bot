import pytest
import asyncio
from datetime import datetime, timedelta, time as dtime
from unittest.mock import MagicMock, patch

from core.session_guard import (
    ExchangeSessionOrchestrator,
    MarketSessionState,
    RuntimePosture,
    DataHealth,
    RuntimeState,
)
from core.orchestrator import TradingOrchestrator
from core.context import RuntimeContext
from config.settings import Settings


def test_runtime_state_snapshot_consistency():
    """Verify get_runtime_state returns an immutable RuntimeState object."""
    orchestrator = ExchangeSessionOrchestrator(_suppress_logs=True)
    state = orchestrator.get_runtime_state(last_candle_ts=datetime.now())
    
    assert isinstance(state, RuntimeState)
    assert isinstance(state.session, MarketSessionState)
    assert isinstance(state.posture, RuntimePosture)
    assert isinstance(state.data_health, DataHealth)
    assert isinstance(state.poll_interval_s, (int, float))
    assert isinstance(state.is_trading_allowed, bool)


def test_pre_market_data_health_remains_fresh():
    """
    Scenario: Bootstrap succeeded at 08:58 (PRE_MARKET) with last candle from yesterday 15:29.
    Assert: DataHealth remains FRESH even as wall-clock time advances by several minutes.
    """
    orchestrator = ExchangeSessionOrchestrator(_suppress_logs=True)
    yesterday_candle_ts = datetime.now() - timedelta(hours=17)
    
    # Mock datetime.now() to 08:58 IST
    pre_market_time = datetime.now().replace(hour=8, minute=58, second=0)
    
    with patch("core.session_guard.datetime") as mock_datetime:
        mock_datetime.now.return_value = pre_market_time
        
        runtime_state = orchestrator.get_runtime_state(last_candle_ts=yesterday_candle_ts)
        assert runtime_state.session == MarketSessionState.PRE_MARKET
        assert runtime_state.posture == RuntimePosture.STANDBY
        assert runtime_state.data_health == DataHealth.FRESH
        assert runtime_state.poll_interval_s == 60.0
        assert runtime_state.is_trading_allowed is False
        
        # Advance mock time to 09:05 IST (still PRE_MARKET)
        mock_datetime.now.return_value = pre_market_time + timedelta(minutes=7)
        orchestrator._invalidate_cache()
        
        runtime_state_after = orchestrator.get_runtime_state(last_candle_ts=yesterday_candle_ts)
        assert runtime_state_after.session == MarketSessionState.PRE_MARKET
        assert runtime_state_after.data_health == DataHealth.FRESH
        assert runtime_state_after.is_trading_allowed is False


def test_session_poll_intervals():
    """Verify poll intervals across various market session states."""
    orchestrator = ExchangeSessionOrchestrator(_suppress_logs=True)
    
    # 07:30 - CLOSED
    with patch("core.session_guard.datetime") as mock_dt:
        mock_dt.now.return_value = datetime.now().replace(hour=7, minute=30)
        orchestrator._invalidate_cache()
        assert orchestrator.get_poll_interval_seconds() == 300.0
        
    # 08:30 - PRE_MARKET
    with patch("core.session_guard.datetime") as mock_dt:
        mock_dt.now.return_value = datetime.now().replace(hour=8, minute=30)
        orchestrator._invalidate_cache()
        assert orchestrator.get_poll_interval_seconds() == 60.0

    # 09:20 - OPEN_STORM
    with patch("core.session_guard.datetime") as mock_dt:
        mock_dt.now.return_value = datetime.now().replace(hour=9, minute=20)
        orchestrator._invalidate_cache()
        assert orchestrator.get_poll_interval_seconds() == 15.0


@pytest.mark.asyncio
async def test_orchestrator_suppresses_decision_in_pre_market():
    """
    Integration test: Run single cycle in PRE_MARKET posture.
    Assert: Telemetry/Market pipeline runs, but decision engine entry processing is suppressed.
    """
    settings = Settings()
    ctx = RuntimeContext(
        settings=settings,
        mode="SIMULATION",
        is_simulation=True,
        telegram_enabled=False,
    )
    
    ctx.data_manager = MagicMock()
    ctx.data_manager.last_market_activity_ts = datetime.now()
    
    # Setup mock snapshot & df
    snapshot = MagicMock()
    snapshot.price = 24000.0
    ctx.data_manager.update_latest_candle_async = MagicMock()
    
    async def mock_fetch(session):
        return MagicMock(), snapshot
        
    ctx.data_manager.update_latest_candle_async.side_effect = mock_fetch
    
    ctx.market_data = MagicMock()
    ctx.market_data.data_manager = ctx.data_manager
    
    ctx.decision = MagicMock()
    ctx.system = MagicMock()
    ctx.system.decision_engine = MagicMock()
    
    orchestrator = TradingOrchestrator(ctx)
    
    # Mock PRE_MARKET state (08:50 AM)
    pre_market_time = datetime.now().replace(hour=8, minute=50)
    with patch("core.session_guard.datetime") as mock_dt:
        mock_dt.now.return_value = pre_market_time
        
        await orchestrator._run_cycle(session=MagicMock())
        
        # Decision engine process should NOT have been called because trading is NOT allowed in PRE_MARKET
        assert ctx.system.decision_engine.process.call_count == 0
        # But market data fetch should have occurred
        assert ctx.data_manager.update_latest_candle_async.call_count == 1


def test_simulated_trade_handles_string_session_phase_and_regime():
    """Verify simulation_engine.open_simulated_trade doesn't fail when session_phase or regime are strings."""
    from core.simulation_engine import SimulationEngine
    from models.signal import Signal
    from models.enums import SignalType, Direction, Strength
    
    settings = Settings()
    engine = SimulationEngine(settings)
    
    signal = Signal(
        id="test-sig-001",
        timestamp=datetime.now(),
        signal_type=SignalType.BUY_PE,
        direction=Direction.BEARISH,
        confidence=75.0,
        strength=Strength.STRONG,
        entry_price=200.0,
        stop_loss=180.0,
        target_1=230.0,
        position_size=50,
        regime="TRENDING_DOWN",         # Plain string!
        session_phase="MORNING",        # Plain string!
    )
    
    snapshot = MagicMock()
    snapshot.price = 24000.0
    snapshot.vwap = 23950.0
    snapshot.rsi = 55.0
    snapshot.atr = 50.0
    snapshot.india_vix = 14.5
    snapshot.timestamp = datetime.now()
    
    # Executing open_simulated_trade should complete without AttributeError: 'str' object has no attribute 'value'
    trade = engine.open_simulated_trade(
        signal=signal,
        snapshot=snapshot,
        filter_score=85.0,
        filter_grade="A",
        gates_passed=10,
        gates_total=10,
        costs_estimate=40,
    )
    
    assert trade is not None
    assert trade.regime == "TRENDING_DOWN"

