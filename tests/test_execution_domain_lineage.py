import pytest
import asyncio
import time
import json
import sqlite3
import os
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock

from models import Signal, SignalType, Direction, Strength, MarketSnapshot, OptionQuote
from core.entry_engine import (
    EntryEngine,
    PendingEntry,
    PriceDomain,
    PRICE_DOMAIN_SPOT,
    PRICE_DOMAIN_OPTION_PREMIUM,
)
from core.structural_breaker import StructuralBreaker
from core.pipelines.execution_pipeline import ExecutionPipeline
from config.settings import Settings
from core.snapshot_v2 import persist_snapshot_v2, link_snapshot_trade
from models.snapshot_v2 import DecisionSnapshotV2, SnapshotMetadata, ReplayStatus
from core.telemetry.execution_logger import ExecutionLedgerWriter
from web.dashboard import Dashboard


def make_snapshot(price=23564.45, atr=8.0):
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


def test_pending_entry_strict_domain_and_contract_validation():
    """Verify PriceDomain validation and explicit contract requirement on PendingEntry."""
    settings = Settings()
    engine = EntryEngine(settings)
    snap = make_snapshot()

    # 1. Reject invalid price_domain string
    sig = Signal(
        id="sig_test_1",
        timestamp=datetime.now(),
        signal_type=SignalType.BUY_CE,
        direction=Direction.BULLISH,
        confidence=60.0,
        strength=Strength.STRONG,
    )
    with pytest.raises(ValueError, match="Invalid price_domain 'OPTION_PREM'"):
        PendingEntry(
            entry_id="ENT-FAIL",
            signal=sig,
            created_at=datetime.now(),
            price_domain="OPTION_PREM"  # type: ignore
        )

    # 2. Reject incomplete option contract when creating OPTION_PREMIUM entry
    sig_partial = Signal(
        id="sig_test_partial",
        timestamp=datetime.now(),
        signal_type=SignalType.BUY_CE,
        direction=Direction.BULLISH,
        confidence=60.0,
        strength=Strength.STRONG,
        strike=23550.0,
        # option_type and expiry missing
    )
    with pytest.raises(ValueError, match="Incomplete option contract specification"):
        engine.create_pending_entry(sig_partial, snap, None)

    # 3. Pure spot signal creates SPOT domain
    sig_spot = Signal(
        id="sig_test_spot",
        timestamp=datetime.now(),
        signal_type=SignalType.BUY_CE,
        direction=Direction.BULLISH,
        confidence=60.0,
        strength=Strength.STRONG,
        entry_price=23564.45,
    )
    entry_spot = engine.create_pending_entry(sig_spot, snap, None)
    assert entry_spot.price_domain == PriceDomain.SPOT
    assert entry_spot.spot_entry == 23564.45

    # 4. Complete option signal creates OPTION_PREMIUM domain
    sig_opt = Signal(
        id="sig_test_opt",
        timestamp=datetime.now(),
        signal_type=SignalType.BUY_CE,
        direction=Direction.BULLISH,
        confidence=60.0,
        strength=Strength.STRONG,
        symbol="NIFTY",
        strike=23550.0,
        option_type="CE",
        expiry="2026-09-15",
        entry_price=163.0,
        spot_entry=23564.45,
        metadata={"instrument": {"strike": 23550.0, "type": "CE", "expiry": "2026-09-15"}}
    )
    entry_opt = engine.create_pending_entry(sig_opt, snap, None)
    assert entry_opt.price_domain == PriceDomain.OPTION_PREMIUM
    assert entry_opt.expected_premium == 163.0
    assert entry_opt.spot_entry == 23564.45
    assert entry_opt.strike == 23550.0
    assert entry_opt.option_type == "CE"
    assert entry_opt.expiry == "2026-09-15"
    assert sig_opt.metadata["pending_entry_id"] == entry_opt.entry_id


def test_exact_production_bug_regression_option_confirmation():
    """
    Direct regression test of the 2026-09-09 production bug:
    Spot = 23,564.45
    Expected option premium = 163.00
    Live option quote = 163.00

    MUST CONFIRM without interference from the 23,564.45 spot index price.
    """
    settings = Settings()
    engine = EntryEngine(settings)
    snap = make_snapshot(price=23564.45)

    sig = Signal(
        id="20260909-124215-2844-64E8",
        timestamp=datetime.now(),
        signal_type=SignalType.BUY_CE,
        direction=Direction.BULLISH,
        confidence=59.2,
        strength=Strength.STRONG,
        symbol="NIFTY",
        strike=23550.0,
        option_type="CE",
        expiry="2026-09-15",
        entry_price=163.0,
        spot_entry=23564.45,
    )
    pending = engine.create_pending_entry(sig, snap, None)

    # Injected quote matching expected premium
    mock_quote = OptionQuote(
        security_id="SEC_23550_CE",
        symbol="NIFTY26SEP23550CE",
        ltp=163.0,
        bid=162.7,
        ask=163.0,
        volume=50000,
        oi=1000000,
        iv=14.5
    )
    quotes_dict = {"23550_CE_2026-09-15": mock_quote}

    confirmed = engine.check_confirmations(snap, None, quotes=quotes_dict)
    assert len(confirmed) == 1
    eid, confirmed_entry = confirmed[0]
    assert eid == pending.entry_id
    assert confirmed_entry.status == "CONFIRMED"
    assert confirmed_entry.adjusted_entry == 163.0
    assert sig.metadata.get("confirmed_quote") is mock_quote


def test_option_premium_chase_protection():
    """Verify that if live option premium spikes > 0.5% (chasing), entry does NOT confirm."""
    settings = Settings()
    engine = EntryEngine(settings)
    snap = make_snapshot(price=23564.45)

    sig = Signal(
        id="sig_chase_test",
        timestamp=datetime.now(),
        signal_type=SignalType.BUY_CE,
        direction=Direction.BULLISH,
        confidence=59.2,
        strength=Strength.STRONG,
        symbol="NIFTY",
        strike=23550.0,
        option_type="CE",
        expiry="2026-09-15",
        entry_price=163.0,
        spot_entry=23564.45,
    )
    engine.create_pending_entry(sig, snap, None)

    # Live quote spiked to 175.0 (7.36% drift > 0.5% tolerance)
    spiked_quote = OptionQuote(
        security_id="SEC_23550_CE",
        symbol="NIFTY26SEP23550CE",
        ltp=175.0,
        bid=174.5,
        ask=175.0,
        volume=50000,
        oi=1000000,
        iv=15.0
    )
    quotes_dict = {"23550_CE_2026-09-15": spiked_quote}

    confirmed = engine.check_confirmations(snap, None, quotes=quotes_dict)
    assert len(confirmed) == 0  # Protected from chasing!


def test_spot_domain_backward_compatibility():
    """Verify legacy spot-domain signals still confirm against snapshot.price."""
    settings = Settings()
    engine = EntryEngine(settings)
    snap = make_snapshot(price=23564.45)

    sig = Signal(
        id="sig_spot_compat",
        timestamp=datetime.now(),
        signal_type=SignalType.BUY_CE,
        direction=Direction.BULLISH,
        confidence=60.0,
        strength=Strength.STRONG,
        entry_price=23560.0,
        spot_entry=23560.0,
    )
    entry = engine.create_pending_entry(sig, snap, None)
    assert entry.price_domain == PriceDomain.SPOT

    # 23564.45 vs 23560.0 is 0.019% diff <= 0.5% tolerance
    confirmed = engine.check_confirmations(snap, None)
    assert len(confirmed) == 1
    assert confirmed[0][1].status == "CONFIRMED"
    assert confirmed[0][1].adjusted_entry == 23564.45


def test_structural_breaker_uses_spot_entry():
    """Verify structural breaker evaluates spot ↔ spot drift without option premium pollution."""
    state_mgr = MagicMock()
    breaker = StructuralBreaker(state_mgr)

    now = time.time()
    sent_time = now - 35.0  # > 30s delay triggers drift check

    current_spot = 23570.0
    signal_spot_entry = 23564.45  # Nifty drifted 0.024% <= 0.3%
    option_premium = 163.0

    # Spot vs Spot: Valid!
    is_valid, should_halt = breaker.check_telegram_execution_sync(
        "SIG_TEST", sent_time, now, current_spot, signal_spot_entry
    )
    assert is_valid is True
    assert should_halt is False

    # Bug reproduction: Spot vs Option Premium causes false rejection
    is_valid_bug, _ = breaker.check_telegram_execution_sync(
        "SIG_TEST", sent_time, now, current_spot, option_premium
    )
    assert is_valid_bug is False  # Proves the bug would have falsely rejected


@pytest.mark.asyncio
async def test_authoritative_full_chain_lineage(tmp_path, monkeypatch):
    """
    Verifies the complete end-to-end lineage:
    SNAP-20260909-TEST → PendingEntry → Confirmed Quote → Position → OMS → Immutable Ledger → Snapshot DB → Operations Console.
    All required fields must match with exact identity throughout.
    """
    test_db = str(tmp_path / "trading_v4_sim.db")
    test_ledger = str(tmp_path / "immutable_executions.jsonl")
    monkeypatch.setenv("NIFTY_DB_PATH", test_db)
    monkeypatch.setattr("core.telemetry.execution_logger.EXECUTIONS_LOG", test_ledger)

    # 1. Setup SQLite Schema
    with sqlite3.connect(test_db) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS decision_snapshots_v2 (
                snapshot_id TEXT PRIMARY KEY,
                timestamp TEXT,
                symbol TEXT,
                expiry TEXT,
                mode TEXT,
                schema_version INTEGER,
                pipeline_version TEXT,
                strategy_version TEXT,
                git_commit TEXT,
                snapshot_hash TEXT,
                parent_snapshot_id TEXT,
                trade_id TEXT,
                shadow_trade_id TEXT,
                experiment_id TEXT,
                replay_run_id TEXT,
                market_json TEXT,
                agents_json TEXT,
                confidence_json TEXT,
                confluence_json TEXT,
                expected_value_json TEXT,
                structure_json TEXT,
                risk_json TEXT,
                amd_json TEXT,
                gate_results_json TEXT,
                decision_json TEXT,
                execution_json TEXT,
                event_timeline_json TEXT,
                replay_status_json TEXT,
                outcome_json TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                signal_id TEXT,
                intent_id TEXT,
                broker_order_id TEXT,
                broker_sl_order_id TEXT,
                symbol TEXT,
                side TEXT,
                qty INTEGER,
                state TEXT,
                requested_price REAL,
                avg_fill_price REAL,
                stop_loss_price REAL,
                filled_qty INTEGER,
                created_at TEXT,
                updated_at TEXT,
                target_price REAL,
                strike REAL,
                expiry TEXT,
                option_type TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS trade_outcomes (
                trade_id TEXT PRIMARY KEY,
                signal_timestamp TEXT,
                opened_at TEXT,
                closed_at TEXT,
                contract TEXT,
                strike REAL,
                option_type TEXT,
                qty INTEGER,
                entry REAL,
                sl REAL,
                target REAL,
                exit_price REAL,
                net_pnl REAL,
                r_multiple REAL,
                result TEXT,
                confidence REAL,
                grade TEXT,
                source TEXT
            )
        """)

    # 2. Persist initial approved Snapshot in DB
    snapshot_id = "20260909-124215-2844-64E8"
    snap_v2 = DecisionSnapshotV2(
        metadata=SnapshotMetadata(
            snapshot_id=snapshot_id,
            timestamp="2026-09-09T12:42:15.640170",
            symbol="NIFTY",
            expiry="2026-09-15",
            mode="SIMULATION",
            schema_version=1,
            pipeline_version="v5.0",
            strategy_version="v3.2",
            git_commit="a67b969",
            trade_id=None
        ),
        snapshot_hash="hash_test_123",
        market={"spot_price": 23564.45},
        agents={},
        confidence={"raw": 59.2},
        confluence={},
        expected_value={"ev_r": 0.57},
        structure={},
        risk={},
        amd={},
        gate_results={},
        decision={"action": "EXECUTE", "reason": "Passed all gates"},
        execution={"entry_price": 23564.45},
        event_timeline={},
        replay=ReplayStatus()
    )
    assert persist_snapshot_v2(snap_v2, db_path=test_db) is True

    # 3. Create context, system, and pipeline
    settings = Settings()
    ctx = MagicMock()
    ctx.settings = settings
    ctx.is_simulation = True

    system = MagicMock()
    system.broker_health.is_healthy = True
    system.trading_enabled = True

    # Wire EntryEngine
    entry_engine = EntryEngine(settings)
    system.entry_engine = entry_engine

    # Wire OMS & PositionManager
    from core.oms import OrderManagementSystem
    oms = OrderManagementSystem(db_path=test_db)
    system.oms = oms

    pos_mgr = MagicMock()
    pos_mgr.calculate_position_size.return_value = {
        "allowed": True,
        "qty": 50,
        "sl_price": 122.25
    }
    mock_pos = MagicMock()
    mock_pos.position_id = "POS_20260909_124215_ABC"
    mock_pos.entry_price = 163.0
    mock_pos.qty = 50
    mock_pos.broker_order_id = "BROKER_ORD_123"
    pos_mgr.open_position_with_sl_guarantee = AsyncMock(return_value=mock_pos)
    pos_mgr.open_positions = {}
    system.position_manager = pos_mgr

    ctx.system = system
    pipeline = ExecutionPipeline(ctx)

    # 4. Construct Signal with option contract details
    sig = Signal(
        id=snapshot_id,
        timestamp=datetime.now(),
        signal_type=SignalType.BUY_CE,
        direction=Direction.BULLISH,
        confidence=59.2,
        strength=Strength.STRONG,
        symbol="NIFTY",
        strike=23550.0,
        option_type="CE",
        expiry="2026-09-15",
        entry_price=163.0,
        stop_loss=122.25,
        target_1=244.50,
        spot_entry=23564.45,
        metadata={
            "instrument": {
                "symbol": "NIFTY26SEP23550CE",
                "strike": 23550.0,
                "type": "CE",
                "expiry": "2026-09-15",
                "security_id": "SEC_23550_CE"
            },
            "premium_entry": 163.0
        }
    )
    snap = make_snapshot(price=23564.45)

    # 5. Phase A: Route to PendingEntry
    pending = entry_engine.create_pending_entry(sig, snap, None)
    pending_entry_id = pending.entry_id
    assert pending_entry_id.startswith("ENT-")
    assert sig.metadata["pending_entry_id"] == pending_entry_id

    # 6. EntryEngine Confirmation via Option Quote
    mock_quote = OptionQuote(
        security_id="SEC_23550_CE",
        symbol="NIFTY26SEP23550CE",
        ltp=163.0,
        bid=162.7,
        ask=163.0,
        volume=50000,
        oi=1000000,
        iv=14.5
    )
    confirmed_entries = entry_engine.check_confirmations(snap, None, quotes={"23550_CE_2026-09-15": mock_quote})
    assert len(confirmed_entries) == 1
    eid, confirmed_pending = confirmed_entries[0]
    assert eid == pending_entry_id
    assert confirmed_pending.adjusted_entry == 163.0

    # 7. Phase B: Execute Confirmed Entry
    exec_result = await pipeline.execute(confirmed_pending, snap, is_simulation=True, mode="confirmed")
    assert exec_result.status == "filled"
    assert exec_result.filled_price == 163.0
    assert exec_result.position_id == "POS_20260909_124215_ABC"

    # 8. Assert Lineage in OMS Orders Table
    with sqlite3.connect(test_db) as conn:
        cur = conn.cursor()
        cur.execute("SELECT signal_id, intent_id, symbol, strike, expiry, option_type, requested_price, qty, state FROM orders")
        order_row = cur.fetchone()
        assert order_row is not None
        assert order_row[0] == snapshot_id
        assert order_row[2] == "NIFTY"
        assert order_row[3] == 23550.0
        assert order_row[4] == "2026-09-15"
        assert order_row[5] == "CE"
        assert order_row[6] == 163.0
        assert order_row[7] == 50
        assert order_row[8] == "ENTRY_FILLED"

    # 9. Assert Lineage in Immutable Executions Ledger (immutable_executions.jsonl)
    assert os.path.exists(test_ledger)
    with open(test_ledger, "r", encoding="utf-8") as f:
        ledger_lines = [json.loads(line) for line in f if line.strip()]
    assert len(ledger_lines) == 1
    rec = ledger_lines[0]
    assert rec["trade_id"] == "POS_20260909_124215_ABC"
    assert rec["decision_snapshot_id"] == snapshot_id
    assert rec["strike"] == 23550.0
    assert rec["option_type"] == "CE"
    assert rec["expiry"] == "2026-09-15"
    assert rec["entry_price"] == 163.0
    assert rec["quantity"] == 50

    # 10. Assert Lineage in decision_snapshots_v2: trade_id successfully linked!
    with sqlite3.connect(test_db) as conn:
        cur = conn.cursor()
        cur.execute("SELECT trade_id, snapshot_id FROM decision_snapshots_v2 WHERE snapshot_id = ?", (snapshot_id,))
        snap_row = cur.fetchone()
        assert snap_row is not None
        assert snap_row[0] == "POS_20260909_124215_ABC"
        assert snap_row[1] == snapshot_id

    # 11. Assert Lineage reaches Operations Console (/api/trades)
    dash = Dashboard(port=5098)
    dash._oms = oms
    dash._position_manager = pos_mgr

    with dash.app.test_client() as client:
        res = client.get("/api/trades")
        assert res.status_code == 200
        data = res.get_json()
        assert data["status"] == "ok"
        trades = data.get("trades", [])
        assert len(trades) >= 1
        console_trade = trades[0]
        assert console_trade["strike"] == 23550.0
        assert console_trade["expiry"] == "2026-09-15"
        assert console_trade["entry"] == 163.0
        assert console_trade["qty"] == 50
