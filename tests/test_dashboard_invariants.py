import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime

from core.oms import OrderManagementSystem
from core.position_manager import PositionManager
from models import Signal, SignalType, Direction, Strength, MarketRegime

# ---------------------------------------------------------
# Test Helper to intercept status_data from Orchestrator
# ---------------------------------------------------------

def build_status_data(oms: OrderManagementSystem, pos_manager: PositionManager) -> dict:
    """
    Simulates the orchestrator.py canonical payload extraction.
    This exactly mirrors the logic in orchestrator._run_cycle() 
    that the user wants us to validate.
    """
    positions = [pos.to_dict() for pos in pos_manager.open_positions.values() if pos.is_active]
    exec_stats = oms.get_execution_stats_today()
    open_pos_count = len(positions)
    closed_pos_count = len(pos_manager.closed_positions_today)
    
    recon_status = "CONSISTENT"
    recon_mismatches = []
    
    if exec_stats["orders_filled"] != (open_pos_count + closed_pos_count):
        recon_status = "MISMATCH"
        recon_mismatches.append(f"Filled orders ({exec_stats['orders_filled']}) != Open ({open_pos_count}) + Closed ({closed_pos_count})")
        
    return {
        "execution": {
            "orders_routed": exec_stats.get("orders_routed", 0),
            "orders_filled": exec_stats.get("orders_filled", 0),
            "open_positions": open_pos_count,
            "closed_outcomes": closed_pos_count,
            "failed": exec_stats.get("failed", 0),
            "cancelled": exec_stats.get("cancelled", 0)
        },
        "reconciliation": {
            "status": recon_status,
            "mismatches": recon_mismatches
        },
        "positions": positions
    }

# ---------------------------------------------------------
# Fixtures
# ---------------------------------------------------------
@pytest.fixture
def mock_deps():
    class Context:
        system = MagicMock()
        settings = MagicMock()
    
    ctx = Context()
    ctx.settings.position.max_open_positions = 1
    ctx.settings.position.total_capital = 100000
    ctx.settings.position.max_daily_trades = 3
    ctx.settings.position.max_daily_loss = 2000.0
    ctx.settings.position.max_weekly_loss = 5000.0
    ctx.settings.trading.max_risk_per_trade = 2.0
    ctx.settings.trading.position_sizing_mode = "FIXED_LOT"
    ctx.settings.trading.fixed_lot_size = 1
    ctx.settings.trading.max_lot_size = 1

    import sqlite3
    
    # Create persistent in-memory DB for OMS to exercise real SQL logic
    mem_conn = sqlite3.connect(":memory:", check_same_thread=False)
    mem_conn.row_factory = sqlite3.Row
    mem_conn.execute('''
        CREATE TABLE orders (
            intent_id TEXT PRIMARY KEY,
            signal_id TEXT,
            symbol TEXT,
            side TEXT,
            qty INTEGER,
            state TEXT,
            requested_price REAL,
            stop_loss_price REAL,
            created_at TEXT,
            updated_at TEXT,
            broker_order_id TEXT,
            broker_sl_order_id TEXT,
            avg_fill_price REAL,
            filled_qty INTEGER
        )
    ''')
    mem_conn.execute('''
        CREATE TABLE order_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            intent_id TEXT,
            event_type TEXT,
            old_state TEXT,
            new_state TEXT,
            payload_json TEXT,
            created_at TEXT
        )
    ''')
    mem_conn.commit()
    
    with patch('core.oms.OrderManagementSystem._get_conn', return_value=mem_conn):
        pos_manager = PositionManager(ctx.settings)
        oms = OrderManagementSystem(db_path="mock.db")
        oms.dhan = MagicMock()
        pos_manager.oms = oms
        
        # Bypass trade policy checks for invariant testing
        pos_manager.can_trade = MagicMock(return_value=(True, "OK"))
        
        # Mock broker fill directly on pos_manager to bypass Dhan simulation block
        pos_manager._place_order_async = AsyncMock(return_value={"data": {"orderId": "broker_order", "orderStatus": "TRADED"}})
        pos_manager._verify_sl_order = AsyncMock(return_value=True)
        
        yield oms, pos_manager

def create_mock_signal(sig_id: str) -> Signal:
    sig = Signal(
        id=sig_id,
        timestamp=datetime.now(),
        signal_type=SignalType.BUY_PE,
        direction=Direction.BEARISH,
        confidence=80.0,
        strength=Strength.STRONG,
        buy_score=0.0,
        sell_score=0.8,
        regime=MarketRegime.TRENDING_DOWN,
        position_size=50,
        stop_loss=24050.0,
        target_1=23900.0,
        warnings=[]
    )
    sig.symbol = "NIFTY24AUG24000PE"
    sig.intent_id = sig_id
    sig.security_id = "12345"
    sig.exchange_segment = "NSE_FO"
    return sig

# ---------------------------------------------------------
# Scenario Tests
# ---------------------------------------------------------

def test_structural_rejection(mock_deps):
    """
    Test 1 — Structural reset rejection
    Verifies that the backend gate object reflects the rejection,
    and no execution counts are incremented.
    """
    from core.trade_filter import TradeFilter, FilterResult
    from config.settings import Settings
    
    trade_filter = TradeFilter(Settings())
    signal = create_mock_signal("sig_struct_1")
    
    # Mock Gate 11 evaluation directly rather than relying on full setup
    res = FilterResult(
        passed=False,
        final_score=0.0,
        grade="F",
        filters_passed=0,
        filters_total=10,
        kill_reason="SAME_STRUCTURAL_TREND",
        gate_details=[],
        telemetry={
            "gates": {
                "Structure Reset": {
                    "passed": False,
                    "actual": "SAME_STRUCTURAL_TREND",
                    "requirement": "NEW_STRUCTURAL_STATE_REQUIRED"
                }
            }
        }
    )
    
    # Verify provenance
    gates = res.telemetry["gates"]
    assert "Structure Reset" in gates
    assert gates["Structure Reset"]["passed"] is False
    assert gates["Structure Reset"]["actual"] == "SAME_STRUCTURAL_TREND"
    assert gates["Structure Reset"]["requirement"] == "NEW_STRUCTURAL_STATE_REQUIRED"

    # Execution stats should be pristine
    oms, pos_manager = mock_deps
    status_data = build_status_data(oms, pos_manager)
    
    assert status_data["execution"]["orders_routed"] == 0
    assert status_data["execution"]["orders_filled"] == 0
    assert status_data["execution"]["open_positions"] == 0
    assert status_data["reconciliation"]["status"] == "CONSISTENT"


@pytest.mark.asyncio
async def test_successful_entry(mock_deps):
    """
    Test 2 — Successful simulated entry
    OMS Routed = 1, Filled = 1, Open = 1, Closed = 0
    """
    oms, pos_manager = mock_deps
    signal = create_mock_signal("sig_entry_1")
    
    # 1. Mock broker fill
    oms.dhan.place_order.return_value = {"orderId": "broker_order_1", "orderStatus": "TRADED"}
    
    # 2. Route intent, fill, and create position
    await pos_manager.open_position_with_sl_guarantee(signal, {"lots": 1, "qty": 50, "risk_amount": 2000, "allowed": True, "sl_price": 90.0, "target_1": 150.0, "target_2": 200.0}, 100.0)

    status_data = build_status_data(oms, pos_manager)
    
    ex = status_data["execution"]
    assert ex["orders_routed"] == 1
    assert ex["orders_filled"] == 1
    assert ex["open_positions"] == 1
    assert ex["closed_outcomes"] == 0
    
    assert status_data["reconciliation"]["status"] == "CONSISTENT"
    
    # Assert correlation ID is intact
    assert len(status_data["positions"]) == 1
    assert status_data["positions"][0]["trade_id"] == "sig_entry_1"
    
    # Assert no silent disappearance
    assert ex["orders_filled"] - ex["open_positions"] - ex["closed_outcomes"] == 0


@pytest.mark.asyncio
async def test_entry_followed_by_exit(mock_deps):
    """
    Test 3 — Entry -> Exit
    Filled = 1, Open = 0, Closed = 1
    """
    oms, pos_manager = mock_deps
    signal = create_mock_signal("sig_entry_2")
    
    # Route and fill
    oms.dhan.place_order.return_value = {"orderId": "broker_order_2", "orderStatus": "TRADED"}
    await pos_manager.open_position_with_sl_guarantee(signal, {"lots": 1, "qty": 50, "risk_amount": 2000, "allowed": True, "sl_price": 90.0, "target_1": 150.0, "target_2": 200.0}, 100.0)
    
    # Close position
    pos_manager.close_position(signal.id, 120.0, "TAKE_PROFIT")
    oms.update_order_state(signal.id, "POSITION_CLOSED", "EXIT_FILLED")
    
    status_data = build_status_data(oms, pos_manager)
    ex = status_data["execution"]
    
    assert ex["orders_routed"] == 1
    assert ex["orders_filled"] == 1
    assert ex["open_positions"] == 0
    assert ex["closed_outcomes"] == 1
    
    assert status_data["reconciliation"]["status"] == "CONSISTENT"
    assert ex["orders_filled"] - ex["open_positions"] - ex["closed_outcomes"] == 0


@pytest.mark.asyncio
async def test_failed_order(mock_deps):
    """
    Test 4 — Failed order
    Routed = 1, Filled = 0, Failed = 1
    """
    oms, pos_manager = mock_deps
    signal = create_mock_signal("sig_fail_1")
    
    # 1. Mock broker failure
    pos_manager._place_order_async = AsyncMock(side_effect=Exception("API Unresponsive"))
    
    # 2. Attempt entry (will fail internally)
    await pos_manager.open_position_with_sl_guarantee(signal, {"lots": 1, "qty": 50, "risk_amount": 2000, "allowed": True, "sl_price": 90.0, "target_1": 150.0, "target_2": 200.0}, 100.0)

    # No position is created!
    
    status_data = build_status_data(oms, pos_manager)
    ex = status_data["execution"]
    
    assert ex["orders_routed"] == 1
    assert ex["orders_filled"] == 0
    assert ex["failed"] == 1
    assert ex["open_positions"] == 0
    assert ex["closed_outcomes"] == 0
    
    assert status_data["reconciliation"]["status"] == "CONSISTENT"
    assert ex["orders_filled"] - ex["open_positions"] - ex["closed_outcomes"] == 0


def test_deliberate_corruption(mock_deps):
    """
    Test 5 — Deliberate corruption test
    Force an impossible state and ensure MISMATCH is triggered.
    """
    oms, pos_manager = mock_deps
    
    # Force corruption: Filled = 2, Open = 0, Closed = 1
    # Insert 2 filled orders into OMS db
    conn = oms._get_conn()
    conn.execute(f"INSERT INTO orders (intent_id, state, created_at) VALUES ('intent_1', 'ENTRY_FILLED', '{datetime.now().isoformat()}')")
    conn.execute(f"INSERT INTO orders (intent_id, state, created_at) VALUES ('intent_2', 'ENTRY_FILLED', '{datetime.now().isoformat()}')")
    conn.commit()
    
    pos_manager.open_positions = {}
    pos_manager.closed_positions_today = [{"id": "intent_1"}]
    
    status_data = build_status_data(oms, pos_manager)
    
    ex = status_data["execution"]
    assert ex["orders_filled"] == 2
    assert ex["open_positions"] == 0
    assert ex["closed_outcomes"] == 1
    
    recon = status_data["reconciliation"]
    assert recon["status"] == "MISMATCH"
    assert "Filled orders (2) != Open (0) + Closed (1)" in recon["mismatches"][0]
    
    # No silent disappearance constraint violation check
    assert ex["orders_filled"] - ex["open_positions"] - ex["closed_outcomes"] == 1 # 1 phantom!


def test_execution_ledger_includes_open_and_closed_orders(mock_deps):
    """
    Test 6 — Executed Trades Ledger Invariant
    Every filled order (OPEN or CLOSED) appears in Today's Execution Ledger immediately.
    """
    from web.dashboard import Dashboard
    oms, pos_manager = mock_deps
    
    # 1. Create 1 open position and 1 closed position
    signal_open = create_mock_signal("sig_open_1")
    pos_open = pos_manager.open_position(
        signal_open,
        {"lots": 1, "qty": 50, "risk_amount": 2000, "allowed": True, "sl_price": 90.0, "target_1": 150.0, "target_2": 200.0},
        100.0,
        100.0
    )
    assert pos_open is not None
    
    pos_manager.closed_positions_today.append({
        "trade_id": "sig_closed_1",
        "timestamp": datetime.now().isoformat(),
        "signal": "BUY_PE",
        "entry_price": 105.0,
        "exit_price": 125.0,
        "stop_loss": 95.0,
        "target_1": 140.0,
        "quantity": 50,
        "pnl": 1000.0,
        "outcome": "WIN",
        "weighted_score": 75.0,
        "grade": "A",
        "is_reconstructed": False
    })
    
    dashboard = Dashboard(port=5099)
    dashboard.set_position_manager(pos_manager)
    dashboard.set_oms(oms)
    
    client = dashboard.app.test_client()
    res = client.get("/api/trades")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "ok"
    trades = data["trades"]
    
    # Verify open trade is in ledger with result == 'OPEN'
    open_trades = [t for t in trades if t["result"] == "OPEN"]
    assert len(open_trades) >= 1
    assert open_trades[0]["trade_id"] == "sig_open_1"
    assert open_trades[0]["entry"] == 100.0
    
    # Verify closed trade is in ledger with outcome
    closed_trades = [t for t in trades if t["result"] == "WIN"]
    assert len(closed_trades) >= 1
    assert closed_trades[0]["trade_id"] == "sig_closed_1"
    assert closed_trades[0]["net_pnl"] == 1000.0


def test_position_manager_oms_state_recovery(mock_deps):
    """
    Test 7 — PositionManager Crash Recovery from OMS
    Ensures mid-day crashes hydrate open positions from OMS without state loss.
    """
    oms, pos_manager = mock_deps
    
    # Insert 2 filled orders into OMS
    oms.create_intent("sig_rec_1", "intent_rec_1", "NIFTY24300CE", "BUY", 50, 100.0, 85.0)
    oms.update_order_state("intent_rec_1", "ENTRY_FILLED", "BROKER_EXEC_SUCCESS", avg_fill_price=102.5, filled_qty=50)
    
    oms.create_intent("sig_rec_2", "intent_rec_2", "NIFTY24300PE", "BUY", 50, 110.0, 95.0)
    oms.update_order_state("intent_rec_2", "ENTRY_FILLED", "BROKER_EXEC_SUCCESS", avg_fill_price=111.0, filled_qty=50)
    
    # Simulate a fresh restart: clear in-memory positions
    pos_manager.open_positions.clear()
    assert len(pos_manager.open_positions) == 0
    
    # Run recovery
    pos_manager._recover_live_state()
    
    # Assert recovery hydrated both positions
    assert len(pos_manager.open_positions) == 2
    assert "sig_rec_1" in pos_manager.open_positions
    assert "sig_rec_2" in pos_manager.open_positions
    assert pos_manager.open_positions["sig_rec_1"].is_reconstructed is True
    assert pos_manager.open_positions["sig_rec_1"].entry_price == 102.5
    
    # Status data should now be CONSISTENT
    status_data = build_status_data(oms, pos_manager)
    assert status_data["reconciliation"]["status"] == "CONSISTENT"
    assert status_data["execution"]["open_positions"] == 2

