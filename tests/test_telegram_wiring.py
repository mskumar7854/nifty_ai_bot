import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from config.settings import Settings
from core.context import RuntimeContext
from core.pipelines.telemetry_pipeline import TelemetryPipeline
from models import Signal, SignalType, Direction, Strength

@pytest.fixture
def settings():
    s = Settings()
    s.alerts.telegram_enabled = True
    s.alerts.console_enabled = False
    s.alerts.sound_enabled = False
    return s

@pytest.fixture
def ctx(settings):
    context = RuntimeContext(
        settings=settings,
        mode="SIMULATION",
        is_simulation=True,
        telegram_enabled=True
    )
    context.system = MagicMock()
    context.db_manager = MagicMock()
    return context

@pytest.fixture
def telemetry(ctx):
    pipe = TelemetryPipeline(ctx)
    pipe.alert_manager = MagicMock()
    pipe.alert_manager.dispatch = AsyncMock()
    pipe.telegram_bot = MagicMock()
    pipe.telegram_bot.notify_trade_close = AsyncMock()
    return pipe

@pytest.mark.asyncio
async def test_approved_signal_dispatches_to_alert_manager(telemetry):
    signal = Signal(
        id="SIG-12345",
        timestamp=datetime.now(),
        signal_type=SignalType.BUY_CE,
        direction=Direction.BULLISH,
        confidence=85.0,
        strength=Strength.STRONG,
        entry_price=24000.0,
        stop_loss=23950.0,
        target_1=24100.0
    )
    
    await telemetry.dispatch_signal(signal)
    
    telemetry.alert_manager.dispatch.assert_called_once_with(signal)

@pytest.mark.asyncio
async def test_no_trade_signal_suppressed(telemetry):
    signal = Signal(
        id="SIG-NO-TRADE",
        timestamp=datetime.now(),
        signal_type=SignalType.NO_TRADE,
        direction=Direction.NEUTRAL,
        confidence=0.0,
        strength=Strength.WEAK
    )
    
    await telemetry.dispatch_signal(signal)
    
    telemetry.alert_manager.dispatch.assert_not_called()

@pytest.mark.asyncio
async def test_none_signal_suppressed(telemetry):
    await telemetry.dispatch_signal(None)
    telemetry.alert_manager.dispatch.assert_not_called()

@pytest.mark.asyncio
async def test_simulation_trade_close_dispatch(telemetry):
    trade_id = "SIM-9988"
    pnl = 1500.0
    outcome = "TARGET_1"
    symbol = "NIFTY26AUG24000CE"
    hold_mins = 12.5
    
    await telemetry.dispatch_trade_close(
        trade_id=trade_id,
        pnl=pnl,
        outcome=outcome,
        symbol=symbol,
        hold_mins=hold_mins
    )
    
    telemetry.telegram_bot.notify_trade_close.assert_called_once_with(
        trade_id="SIM-9988",
        pnl=1500.0,
        outcome="TARGET_1",
        symbol="NIFTY26AUG24000CE",
        hold_mins=12.5
    )

@pytest.mark.asyncio
async def test_trade_close_idempotency(telemetry):
    trade_id = "SIM-UNIQUE-ID-1"
    
    # First dispatch
    await telemetry.dispatch_trade_close(
        trade_id=trade_id,
        pnl=800.0,
        outcome="WIN",
        symbol="NIFTY",
        hold_mins=5.0
    )
    assert telemetry.telegram_bot.notify_trade_close.call_count == 1
    
    # Second dispatch with same trade_id
    await telemetry.dispatch_trade_close(
        trade_id=trade_id,
        pnl=800.0,
        outcome="WIN",
        symbol="NIFTY",
        hold_mins=5.0
    )
    # Must still be called exactly once
    assert telemetry.telegram_bot.notify_trade_close.call_count == 1

@pytest.mark.asyncio
async def test_live_trade_close_dispatch(telemetry, ctx, settings):
    from core.pipelines.execution_pipeline import ExecutionPipeline
    from models import PositionAction
    
    settings.system_mode.mode = "SMALL_CAPITAL"  # Live mode
    ctx.telemetry = telemetry
    
    pos_mgr = MagicMock()
    pos_mgr.close_position.return_value = {
        "type": "full",
        "pnl": -1200.0,
        "net_pnl": -1250.0,
        "reason": "STOP_LOSS",
        "hold_minutes": 15.0,
        "entry": 24000.0,
        "exit": 23950.0
    }
    ctx.system.position_manager = pos_mgr
    
    exec_pipeline = ExecutionPipeline(ctx)
    action = PositionAction(action_type="FULL_EXIT", position_id="LIVE-POS-101", reason="STOP_LOSS")
    
    await exec_pipeline.apply_position_actions([action])
    
    # Assert PositionManager was called
    pos_mgr.close_position.assert_called_once_with("LIVE-POS-101", 0.0, "STOP_LOSS")
    
    # Assert TelegramController received the exact live close metrics
    telemetry.telegram_bot.notify_trade_close.assert_called_once_with(
        trade_id="LIVE-POS-101",
        pnl=-1250.0,
        outcome="STOP_LOSS",
        symbol="NIFTY",
        hold_mins=15.0
    )

@pytest.mark.asyncio
async def test_telegram_failure_isolation(telemetry):
    # Make alert_manager and telegram_bot throw exceptions
    telemetry.alert_manager.dispatch = AsyncMock(side_effect=ConnectionError("Telegram API timeout"))
    telemetry.telegram_bot.notify_trade_close = AsyncMock(side_effect=RuntimeError("Bot offline"))
    
    signal = Signal(
        id="SIG-FAIL-TEST",
        timestamp=datetime.now(),
        signal_type=SignalType.BUY_PE,
        direction=Direction.BEARISH,
        confidence=80.0,
        strength=Strength.STRONG
    )
    
    # Neither dispatch should raise an exception or crash
    try:
        await telemetry.dispatch_signal(signal)
        await telemetry.dispatch_trade_close(
            trade_id="TRADE-FAIL-TEST",
            pnl=-500.0,
            outcome="STOP_LOSS"
        )
    except Exception as exc:
        pytest.fail(f"Telemetry dispatch should not propagate exceptions, but raised: {exc}")
