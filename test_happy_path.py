"""
============================================
🧪 CHAOS MONKEY BRIDGE TEST - TEST 01
Simulates the Happy Path: Signal -> Confirm -> Execute
============================================
"""

import asyncio
import uuid
import time
from datetime import datetime
from models.signals import Signal, SignalType, Direction, Strength
from core.db_manager import DBManager
from core.telegram_controller import TelegramController
from config.settings import Settings

async def run_test():
    settings = Settings()
    # Ensure SEMI_AUTO for testing
    settings.alerts.trading_mode = "SEMI_AUTO"
    settings.alerts.telegram_signal_expiry_seconds = 30
    
    db = DBManager()
    await db.initialize()
    
    # Mock Engines (we just want to see the state machine work)
    class MockEngine:
        def create_pending_entry(self, signal, snap, df):
            print(f"🔥 EXECUTION: Entry created for signal {signal.id}")

    class MockDM:
        def __init__(self):
            import pandas as pd
            self.ohlcv_data = pd.DataFrame([{"close": 22700.0}])
        def get_ltp(self, symbol): return 22700.0

    mock_engine = MockEngine()
    mock_dm = MockDM()
    
    # 1. Initialize Controller
    bot = TelegramController(settings, mock_engine, mock_dm, None, None, db)
    
    # 2. Create a Mock Signal
    sig_id = str(uuid.uuid4())[:8]
    signal = Signal(
        id=sig_id,
        timestamp=datetime.now(),
        signal_type=SignalType.BUY_CE,
        direction=Direction.BULLISH,
        confidence=85.0,
        strength=Strength.STRONG,
        entry_price=22700.0,
        stop_loss=22650.0,
        target_1=22800.0,
        position_size=50
    )
    signal.symbol = "NIFTY"
    
    print(f"📡 STEP 1: Processing new signal {sig_id}...")
    await bot.process_signal(signal)
    
    # Check DB
    print("🔍 Checking DB after queuing...")
    import sqlite3
    conn = sqlite3.connect(db.db_path)
    res = conn.execute("SELECT status FROM signals WHERE id=?", (sig_id,)).fetchone()
    print(f"   DB Status: {res[0]}")
    
    # 3. Simulate User Confirm (Test 01 Happy Path)
    print("\n✅ STEP 2: Simulating User CONFIRM click...")
    
    # Mock the Telegram update object
    class MockUser:
        id = 123456789 # Matches admin_id
        
    class MockQuery:
        from_user = MockUser()
        data = f"confirm:{sig_id}"
        async def answer(self, text=None, show_alert=False): print("   [Bot] Answering query...")
        async def edit_message_text(self, text, parse_mode=None): print(f"   [Bot] Editing message: {text}")

    class MockUpdate:
        callback_query = MockQuery()
        effective_chat = MockUser()

    await bot.handle_callback_query(MockUpdate(), None)
    
    # Check Final DB State
    res = conn.execute("SELECT status FROM signals WHERE id=?", (sig_id,)).fetchone()
    print(f"\n🏁 FINAL DB Status: {res[0]}")
    conn.close()

if __name__ == "__main__":
    asyncio.run(run_test())
