import pytest
import asyncio
import time
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock

from models import Signal, SignalType, Direction, Strength, MarketSnapshot
from core.entry_engine import EntryEngine, PendingEntry
from core.pipelines.execution_pipeline import ExecutionPipeline
from config.settings import Settings
from core.context import RuntimeContext
from main import LegacySystem
from core.db_manager import DBManager
from web.dashboard import Dashboard


def test_signal_compatibility_attributes():
    """Verify Signal has default symbol and security_id attributes."""
    sig = Signal(
        id="sig_test_compat",
        timestamp=datetime.now(),
        signal_type=SignalType.BUY_PE,
        direction=Direction.BEARISH,
        confidence=65.0,
        strength=Strength.STRONG,
    )
    assert hasattr(sig, "symbol")
    assert sig.symbol == "NIFTY"
    assert hasattr(sig, "security_id")
    assert sig.security_id is None


def make_snapshot(price=100.0, atr=5.0):
    return MarketSnapshot(
        timestamp=datetime.now(),
        price=price,
        open=price,
        high=price + 2,
        low=price - 2,
        close=price,
        volume=1000,
        vwap=price,
        rsi=50.0,
        ema_fast=price,
        ema_slow=price,
        atr=atr
    )


def test_entry_engine_removes_confirmed_entry():
    """Verify EntryEngine removes confirmed entries from self.pending_entries."""
    settings = Settings()
    engine = EntryEngine(settings)
    
    sig = Signal(
        id="sig_entry_test",
        timestamp=datetime.now(),
        signal_type=SignalType.BUY_PE,
        direction=Direction.BEARISH,
        confidence=65.0,
        strength=Strength.STRONG,
        entry_price=100.0
    )
    snap = make_snapshot(price=100.0)
    
    entry = engine.create_pending_entry(sig, snap, None)
    eid = entry.entry_id
    assert eid in engine.pending_entries
    assert len(engine.pending_entries) == 1
    
    # Confirm entry
    confirmed = engine.check_confirmations(snap, None)
    assert len(confirmed) == 1
    assert confirmed[0][0] == eid
    
    # Invariant: confirmed entry MUST be deleted from pending_entries to prevent re-triggering / memory leaks
    assert eid not in engine.pending_entries
    assert len(engine.pending_entries) == 0


@pytest.mark.asyncio
async def test_execution_pipeline_unpacks_pending_entry():
    """Verify ExecutionPipeline unpacks PendingEntry safely when mode='confirmed'."""
    ctx = MagicMock()
    ctx.settings = Settings()
    system = MagicMock()
    system.broker_health.is_healthy = True
    system.trading_enabled = True
    
    pos_mgr = MagicMock()
    pos_mgr.calculate_position_size.return_value = {
        "allowed": True,
        "qty": 50,
        "sl_price": 25.0
    }
    mock_pos = MagicMock()
    mock_pos.entry_price = 32.65
    mock_pos.qty = 50
    mock_pos.position_id = "POS_TEST_123"
    pos_mgr.open_position_with_sl_guarantee = AsyncMock(return_value=mock_pos)
    
    system.position_manager = pos_mgr
    system.oms = MagicMock()
    ctx.system = system
    
    pipeline = ExecutionPipeline(ctx)
    
    sig = Signal(
        id="sig_unpack_test",
        timestamp=datetime.now(),
        signal_type=SignalType.BUY_PE,
        direction=Direction.BEARISH,
        confidence=65.0,
        strength=Strength.STRONG,
        entry_price=32.65,
        metadata={"premium_entry": 32.65}
    )
    snap = make_snapshot(price=23650.0)
    
    pending = PendingEntry(
        entry_id="ENT-TEST1",
        signal=sig,
        created_at=datetime.now(),
        adjusted_entry=32.65
    )
    
    # Passing PendingEntry directly MUST NOT raise AttributeError: 'PendingEntry' object has no attribute 'metadata'
    res = await pipeline.execute(pending, snap, is_simulation=True, mode="confirmed")
    assert res.status == "filled"
    assert res.position_id == "POS_TEST_123"


def test_legacy_system_oms_wiring():
    """Verify LegacySystem wires self.oms from self.position_manager.oms."""
    settings = Settings()
    db_mgr = DBManager()
    sys = LegacySystem(settings, db_mgr)
    assert hasattr(sys, "oms")
    assert sys.oms is not None
    assert sys.oms is sys.position_manager.oms


def test_dashboard_api_trades_contains_recovered_trades(monkeypatch):
    """Verify Dashboard /api/trades returns historical recovered trades."""
    monkeypatch.setenv("NIFTY_DB_PATH", "data/trading_v4_sim.db")
    dash = Dashboard(port=5097)
    with dash.app.test_client() as client:
        res = client.get("/api/trades")
        assert res.status_code == 200
        data = res.get_json()
        assert data["status"] == "ok"
        trade_ids = [t["trade_id"] for t in data.get("trades", [])]
        assert "TRD_20260908_094410_319A" in trade_ids
        assert "TRD_20260908_095901_02CC" in trade_ids
