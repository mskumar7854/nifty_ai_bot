"""
============================================
ðŸ§ª CHAOS MONKEY BRIDGE TEST - TEST 02
Simulates the Expiry Path: Signal -> Wait -> Expire
============================================
"""

import asyncio
import uuid
import time
from datetime import datetime
from models.signal import Signal, SignalType, Direction, Strength
from core.db_manager import DBManager
from core.telegram_controller import TelegramController
from config.settings import Settings

async def run_test():
    settings = Settings()
    settings.alerts.trading_mode = "SEMI_AUTO"
    settings.alerts.telegram_signal_expiry_seconds = 2 # Shortened for testing
    
    db = DBManager()
    await db.initialize()
    
    class MockEngine:
        def create_pending_entry(self, signal, snap, df): pass

    class MockDM:
        def __init__(self):
            import pandas as pd
            self.ohlcv_data = pd.DataFrame([{"close": 22700.0}])
        def get_ltp(self, symbol): return 22700.0
        def get_latest_data(self):
            class MockSnapshot:
                price = 22700.0
            return None, MockSnapshot()

    class MockSystem:
        def __init__(self, entry_engine=None, data_manager=None):
            self.risk_manager = None
            self.position_manager = None
            self.entry_engine = entry_engine
            self.data_manager = data_manager
            self.broker_health = None
            self.telegram_enabled = True
            self.is_simulation = True
            self.running = True
            self.trading_enabled = True
            
            class MockMaster:
                def approve(self, signal_type):
                    class MockApproval:
                        approved = True
                        reason = ""
                    return MockApproval()
            self.master = MockMaster()

        async def execute_signal(self, signal, mode="new"):
            print(f"ðŸ”¥ Unified EXECUTION: {signal.id} mode={mode}")

    mock_engine = MockEngine()
    mock_dm = MockDM()
    
    bot = TelegramController(settings, MockSystem(mock_engine, mock_dm), db)
    # We need a dummy App object to handle message sending in the background task
    class MockApp:
        class Bot:
            async def send_message(self, *args, **kwargs):
                print(f"   [Bot Notification] {kwargs.get('text')}")
                class MockMsg:
                    message_id = 9999
                return MockMsg()
        bot = Bot()
    bot.app = MockApp()

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
    
    print(f"ðŸ“¡ STEP 1: Processing new signal {sig_id} (Expiry set to 2s)...")
    await bot.process_signal(signal)
    
    print("â³ STEP 2: Waiting for expiry task to fire...")
    # The controller starts a background task: bot.expiry_task
    # We wait long enough for it to finish
    await asyncio.sleep(4) 
    
    # Check DB
    import sqlite3
    conn = sqlite3.connect(db.db_path)
    res = conn.execute("SELECT status FROM signals WHERE id=?", (sig_id,)).fetchone()
    print(f"\nðŸ FINAL DB Status: {res[0]}")
    conn.close()

if __name__ == "__main__":
    asyncio.run(run_test())
