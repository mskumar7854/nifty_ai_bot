import asyncio
from unittest.mock import MagicMock
from core.pipelines.execution_pipeline import ExecutionPipeline
from core.position_manager import PositionManager
from core.simulation_broker import SimulationBroker
from models.signal import Signal, SignalType, Direction
from models.regime import MarketRegime as Regime
from core.data_manager import MarketSnapshot
from config.settings import Settings

async def test_simulated_lifecycle():
    settings = Settings()
    settings.system_mode.mode = "SIMULATION"
    settings.db_path = "data/test_db.db"
    
    import sqlite3
    import os
    if os.path.exists(settings.db_path):
        os.remove(settings.db_path)
    
    conn = sqlite3.connect(settings.db_path)
    conn.execute('''CREATE TABLE decision_snapshots_v2 (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                snapshot_id TEXT NOT NULL UNIQUE,
                timestamp TEXT NOT NULL,
                symbol TEXT,
                expiry TEXT,
                mode TEXT,
                schema_version TEXT,
                pipeline_version TEXT,
                strategy_version TEXT,
                git_commit TEXT,
                snapshot_hash TEXT NOT NULL,
                trade_id TEXT)''')
    conn.commit()
    conn.close()
    
    broker = SimulationBroker()
    pos_manager = PositionManager(settings, broker=broker)
    
    ctx = MagicMock()
    ctx.system = MagicMock()
    ctx.system.position_manager = pos_manager
    ctx.system.settings = settings
    
    pipeline = ExecutionPipeline(ctx)
    
    sig = Signal(
        id="test_signal_123",
        timestamp="2026-08-18T10:00:00",
        strength=0.9,
        signal_type=SignalType.BUY_CE,
        direction=Direction.BULLISH,
        confidence=80,
        regime=Regime.TRENDING_UP,
        metadata={"instrument": {"strike": 24500, "type": "CE", "expiry": "2026-08-20"}, "premium_entry": 100, "premium_sl": 80, "premium_t1": 120, "premium_t2": 150}
    )
    sig.symbol = "NIFTY"
    sig.security_id = "12345"
    
    snap = MarketSnapshot(
        timestamp="2026-08-18T10:00:00",
        price=24500,
        india_vix=12.0,
        open=24400,
        high=24600,
        low=24300,
        close=24500,
        volume=1000000,
        vwap=24450,
        rsi=60.0,
        ema_fast=24480,
        ema_slow=24400,
        atr=50.0
    )
    
    print("Executing confirmed...")
    # Write dummy decision_snapshots_v2
    import sqlite3
    import uuid
    from datetime import datetime
    
    intent_id = f"INT_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:4].upper()}"
    sig.id = intent_id # Override signal ID to act as trade_id/intent_id
    sig.security_id = "NIFTY-50"
    
    conn = sqlite3.connect("data/test_db.db")
    conn.execute("INSERT INTO decision_snapshots_v2 (snapshot_id, timestamp, trade_id, snapshot_hash) VALUES (?, ?, ?, ?)", 
                 (intent_id, "2026-08-18T10:00:00", intent_id, "dummyhash"))
    conn.commit()
    conn.close()

    res = await pipeline.execute(sig, snap, is_simulation=True, mode="confirmed")
    print(res)
    
    print("Open Positions:")
    print(pos_manager.open_positions)
    print("Broker Orders:")
    print(broker.orders)
    
    print(f"Closing position {sig.id}...")
    close_res = pos_manager.close_position(sig.id, 0.0, reason="TEST_EXIT")
    print("Close Result:")
    print(close_res)
    print("Broker Orders after close:")
    print(broker.orders)
    
    print("\n--- PHASE 2: DATABASE RECONCILIATION ---")
    conn = sqlite3.connect("data/test_db.db")
    conn.row_factory = sqlite3.Row
    
    ds = conn.execute("SELECT trade_id FROM decision_snapshots_v2 WHERE trade_id = ?", (intent_id,)).fetchone()
    order = conn.execute("SELECT intent_id FROM orders WHERE intent_id = ? AND transaction_type = 'BUY'", (intent_id,)).fetchone()
    to = conn.execute("SELECT trade_id FROM trade_outcomes WHERE trade_id = ?", (intent_id,)).fetchone()
    te = conn.execute("SELECT intent_id FROM trade_economics WHERE intent_id = ?", (intent_id,)).fetchone()
    
    print(f"decision_snapshots_v2.trade_id : {ds['trade_id'] if ds else 'MISSING'}")
    print(f"orders.intent_id             : {order['intent_id'] if order else 'MISSING'}")
    print(f"trade_outcomes.trade_id      : {to['trade_id'] if to else 'MISSING'}")
    print(f"trade_economics.intent_id    : {te['intent_id'] if te else 'MISSING'}")
    
    assert ds and order and to and te
    print("\n✅ Database reconciliation successful: All entities linked correctly.")
    conn.close()

if __name__ == "__main__":
    asyncio.run(test_simulated_lifecycle())
