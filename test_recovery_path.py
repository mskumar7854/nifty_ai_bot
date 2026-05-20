"""
============================================
🧪 CHAOS MONKEY BRIDGE TEST - TESTS 03 & 04
Simulates Crash Recovery: Soft (<30s) vs Hard (>30s)
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
    settings.alerts.trading_mode = "SEMI_AUTO"
    settings.alerts.telegram_signal_expiry_seconds = 30
    
    db = DBManager()
    await db.initialize()
    
    class MockSystem:
        def __init__(self):
            self.risk_manager = None
            self.position_manager = None
            self.entry_engine = None
            self.data_manager = None
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
            print(f"🔥 Unified EXECUTION: {signal.id} mode={mode}")
    
    class MockApp:
        class Bot:
            async def send_message(self, *args, **kwargs):
                print(f"   [Bot Notification] {kwargs.get('text')}")
                class MockMsg:
                    message_id = 9999
                return MockMsg()
        bot = Bot()

    # ┌────────────────────────────────────────────────────────┐
    # │ TEST 03: SOFT CRASH (Recovery < 30s)                   │
    # └────────────────────────────────────────────────────────┘
    print("\n🌪️ --- TEST 03: SOFT CRASH RECOVERY (< 30s) ---")
    
    # 1. Simulate Signal in DB (as if killed while pending)
    sig_id_soft = "SOFT_" + str(uuid.uuid4())[:4]
    now = time.time()
    
    soft_signal = Signal(
        id=sig_id_soft,
        timestamp=datetime.fromtimestamp(now - 10), # 10s old
        signal_type=SignalType.BUY_CE,
        direction=Direction.BULLISH,
        confidence=90.0,
        strength=Strength.STRONG,
        entry_price=22700.0,
        stop_loss=22650.0,
        target_1=22800.0,
        status="queued",
        created_at=now - 10 
    )
    # Save manually to simulate DB state before recovery
    await db.save_signal(soft_signal)
    print(f"📡 Mocked 'pending' signal {sig_id_soft} (10s old) in DB.")

    # 2. Start new Bot Controller (Simulate Restart)
    bot_v2 = TelegramController(settings, MockSystem(), db)
    bot_v2.app = MockApp()
    
    print("🔄 Bot booting... Running recovery...")
    await bot_v2.boot_recovery()
    
    # Verify RAM state
    print(f"🔍 Checking RAM State:")
    print(f"   Active Signal ID: {bot_v2.active_signal.id if bot_v2.active_signal else 'None'}")
    print(f"   Status in RAM: {bot_v2.active_signal.status if bot_v2.active_signal else 'None'}")

    # ┌────────────────────────────────────────────────────────┐
    # │ TEST 04: HARD CRASH (Zombie Pruning > 30s)             │
    # └────────────────────────────────────────────────────────┘
    print("\n🌪️ --- TEST 04: HARD CRASH / ZOMBIE PRUNING (> 30s) ---")
    
    sig_id_hard = "HARD_" + str(uuid.uuid4())[:4]
    
    hard_signal = Signal(
        id=sig_id_hard,
        timestamp=datetime.fromtimestamp(now - 45), # 45s old
        signal_type=SignalType.BUY_PE,
        direction=Direction.BEARISH,
        confidence=95.0,
        strength=Strength.STRONG,
        entry_price=22700.0,
        stop_loss=22750.0,
        target_1=22600.0,
        status="pending",
        created_at=now - 45 
    )
    await db.save_signal(hard_signal)
    print(f"📡 Mocked 'pending' signal {sig_id_hard} (45s old) in DB.")

    # 2. Restart Bot again
    bot_v3 = TelegramController(settings, MockSystem(), db)
    bot_v3.app = MockApp()
    
    print("🔄 Bot booting... Running recovery...")
    await bot_v3.boot_recovery()
    
    # Verify DB State
    import sqlite3
    conn = sqlite3.connect(db.db_path)
    res = conn.execute("SELECT status FROM signals WHERE id=?", (sig_id_hard,)).fetchone()
    print(f"\n🏁 FINAL DB Status for {sig_id_hard}: {res[0]}")
    conn.close()

if __name__ == "__main__":
    asyncio.run(run_test())
