import unittest
import os
import json
import time
from datetime import datetime

from core.system_state import TradingStateManager, get_state_manager
from core.structural_breaker import StructuralBreaker

class TestSystemBreakers(unittest.TestCase):
    def setUp(self):
        # Set up a clean state for testing
        self.state_file = os.path.join("data", "system_state.json")
        self.audit_file = os.path.join("data", "state_transitions.jsonl")
        for fpath in [self.state_file, self.audit_file]:
            if os.path.exists(fpath):
                try:
                    os.remove(fpath)
                except Exception:
                    pass
        
        # Clear the singleton instance reference to guarantee complete test isolation
        TradingStateManager._instance = None
        
        # Initialize state manager
        self.state_mgr = TradingStateManager()
        # Reset to ACTIVE for start of each test
        self.state_mgr.set_state("ACTIVE", "Test Setup")
        self.alerts_sent = []
        self.state_mgr.register_alert_callback(self.record_alert)

    def record_alert(self, msg: str):
        self.alerts_sent.append(msg)

    def tearDown(self):
        # Clean up
        for fpath in [self.state_file, self.audit_file]:
            if os.path.exists(fpath):
                try:
                    os.remove(fpath)
                except Exception:
                    pass

    def test_state_persistence(self):
        # Transition to structural halt
        self.state_mgr.trigger_structural_halt("Unit Test Halt")
        self.assertEqual(self.state_mgr.get_state(), "HALTED")
        self.assertFalse(self.state_mgr.is_trading_allowed())
        
        # Force reload from file (simulate restart)
        new_mgr = TradingStateManager()
        new_mgr.load_state()
        self.assertEqual(new_mgr.get_state(), "HALTED")
        
        # Verify transition to financial pause does not persist across clean restart
        # Reset state file to test transient pause behavior
        if os.path.exists(self.state_file):
            try:
                os.remove(self.state_file)
            except Exception:
                pass
        
        # Reset singleton class reference to allow a fresh active manager instance
        TradingStateManager._instance = None
        
        clean_mgr = TradingStateManager()
        clean_mgr.set_state("ACTIVE", "Reset to active")
        clean_mgr.set_state("PAUSED_FINANCIAL", "Drawdown limit")
        self.assertEqual(clean_mgr.get_state(), "PAUSED_FINANCIAL")
        
        # Re-initialize to verify reload cleans temporary financial pauses
        # Reset singleton to simulate clean restart loader behavior
        TradingStateManager._instance = None
        temp_mgr = TradingStateManager()
        temp_mgr.load_state()
        self.assertEqual(temp_mgr.get_state(), "ACTIVE")

        # Verify transition logs have the correct schema version and enriched fields (backward compatibility checks)
        audit_file = os.path.join("data", "state_transitions.jsonl")
        self.assertTrue(os.path.exists(audit_file))
        with open(audit_file, "r") as f:
            for line in f:
                if line.strip():
                    record = json.loads(line.strip())
                    self.assertEqual(record.get("schema_version"), "1.0")
                    self.assertIn(record.get("event_type"), ["SYSTEM_TRANSITION", "OPERATOR_ACTION"])
                    self.assertIn(record.get("source"), ["system", "telegram"])

    def test_duplicate_order_breaker(self):
        breaker = StructuralBreaker(self.state_mgr)
        
        # First order: should be allowed
        allowed = breaker.check_duplicate_order("NIFTY26MAY21500CE", "BUY")
        self.assertTrue(allowed)
        self.assertEqual(self.state_mgr.get_state(), "ACTIVE")
        
        # Duplicate order within window: should be blocked and trigger structural halt
        allowed_dup = breaker.check_duplicate_order("NIFTY26MAY21500CE", "BUY", window_sec=10.0)
        self.assertFalse(allowed_dup)
        self.assertEqual(self.state_mgr.get_state(), "HALTED")
        self.assertIn("Duplicate order", self.state_mgr.reason)
        self.assertTrue(len(self.alerts_sent) > 0)

    def test_broker_ack_breaker(self):
        breaker = StructuralBreaker(self.state_mgr)
        
        # Fast ACK: should pass
        self.assertTrue(breaker.check_broker_ack("ORD123", elapsed_sec=2.0))
        self.assertEqual(self.state_mgr.get_state(), "ACTIVE")
        
        # Slow ACK: should trigger halt
        self.assertFalse(breaker.check_broker_ack("ORD124", elapsed_sec=6.0))
        self.assertEqual(self.state_mgr.get_state(), "HALTED")

    def test_stop_loss_attached_breaker(self):
        breaker = StructuralBreaker(self.state_mgr)
        
        # Valid SL: should pass
        self.assertTrue(breaker.check_stop_loss_attached("ORD123", stop_loss=50.5))
        self.assertEqual(self.state_mgr.get_state(), "ACTIVE")
        
        # Invalid SL: should halt
        self.assertFalse(breaker.check_stop_loss_attached("ORD124", stop_loss=0.0))
        self.assertEqual(self.state_mgr.get_state(), "HALTED")

    def test_position_mismatch_breaker(self):
        breaker = StructuralBreaker(self.state_mgr)
        
        # Match: should pass
        self.assertTrue(breaker.check_position_mismatch(internal_count=2, broker_count=2))
        self.assertEqual(self.state_mgr.get_state(), "ACTIVE")
        
        # Mismatch: should halt
        self.assertFalse(breaker.check_position_mismatch(internal_count=2, broker_count=1))
        self.assertEqual(self.state_mgr.get_state(), "HALTED")

    def test_telegram_sync_delay_breaker(self):
        breaker = StructuralBreaker(self.state_mgr)
        now = time.time()
        
        # Small delay: should pass
        is_valid, should_halt = breaker.check_telegram_execution_sync(
            "SIG123", sent_time=now - 5.0, current_time=now, current_price=22000.0, signal_price=22000.0
        )
        self.assertTrue(is_valid)
        self.assertFalse(should_halt)
        self.assertEqual(self.state_mgr.get_state(), "ACTIVE")
        
        # Big delay but safe price drift: should pass
        is_valid, should_halt = breaker.check_telegram_execution_sync(
            "SIG124", sent_time=now - 35.0, current_time=now, current_price=22000.0, signal_price=22000.0
        )
        self.assertTrue(is_valid)
        self.assertFalse(should_halt)
        self.assertEqual(self.state_mgr.get_state(), "ACTIVE")

        # Big delay with unsafe price drift (> 0.3%): should reject signal but NOT halt system
        is_valid, should_halt = breaker.check_telegram_execution_sync(
            "SIG125", sent_time=now - 35.0, current_time=now, current_price=22110.0, signal_price=22000.0 # 0.5% drift
        )
        self.assertFalse(is_valid)
        self.assertFalse(should_halt)
        self.assertEqual(self.state_mgr.get_state(), "ACTIVE")

        # Critical queue stall delay (> 300s): should halt system
        is_valid, should_halt = breaker.check_telegram_execution_sync(
            "SIG126", sent_time=now - 350.0, current_time=now, current_price=22000.0, signal_price=22000.0
        )
        self.assertFalse(is_valid)
        self.assertTrue(should_halt)
        self.assertEqual(self.state_mgr.get_state(), "HALTED")

    def test_happy_path_integration(self):
        """
        Test 7: Full healthy-path integration
        Simulates a complete, healthy cycle from signal creation through mock approval,
        duplicate checks, SL attachment, broker ACK, and successful completion.
        """
        breaker = StructuralBreaker(self.state_mgr)
        now = time.time()
        
        # 1. Signal creation & Telegram sync check (happy path)
        is_valid, should_halt = breaker.check_telegram_execution_sync(
            "SIG_HAPPY", now - 2.0, now, 22000.0, 22000.0
        )
        self.assertTrue(is_valid)
        self.assertFalse(should_halt)
        
        # 2. Duplicate order check
        allowed = breaker.check_duplicate_order("NIFTY26MAY21500CE", "BUY")
        self.assertTrue(allowed)
        
        # 3. Stop loss attachment check (SL attached = 50.0)
        has_sl = breaker.check_stop_loss_attached("ORD_HAPPY", stop_loss=50.0)
        self.assertTrue(has_sl)
        
        # 4. Broker ACK timing check (200ms ACK delay)
        ack_ok = breaker.check_broker_ack("ORD_HAPPY", elapsed_sec=0.2)
        self.assertTrue(ack_ok)
        
        # 5. Position mismatch check (both sides report 1 position)
        recon_ok = breaker.check_position_mismatch(internal_count=1, broker_count=1)
        self.assertTrue(recon_ok)
        
        # Verify the entire cycle left system ACTIVE
        self.assertEqual(self.state_mgr.get_state(), "ACTIVE")
        self.assertTrue(self.state_mgr.is_trading_allowed())

    def test_restart_recovery_integration(self):
        """
        Test 8: Restart recovery verification
        Simulates: ACTIVE -> open positions -> system halt state written to disk ->
        process kill simulated -> restart & state re-load -> state is correctly restored.
        """
        # 1. Start clean ACTIVE
        self.state_mgr.set_state("ACTIVE", "Initial clean state")
        self.assertEqual(self.state_mgr.get_state(), "ACTIVE")
        
        # 2. Open positions mismatch occurs, causing a structural halt
        breaker = StructuralBreaker(self.state_mgr)
        self.assertFalse(breaker.check_position_mismatch(internal_count=2, broker_count=1))
        self.assertEqual(self.state_mgr.get_state(), "HALTED")
        
        # 3. Verify state persisted on disk
        self.assertTrue(os.path.exists(self.state_file))
        with open(self.state_file, "r") as f:
            saved_data = json.load(f)
            self.assertEqual(saved_data["state"], "HALTED")
            
        # 4. Simulate a process restart by creating a brand-new state manager instance
        restarted_mgr = TradingStateManager()
        restarted_mgr.load_state()
        
        # 5. Verify the restarted state manager successfully recovered the HALTED status
        self.assertEqual(restarted_mgr.get_state(), "HALTED")
        self.assertFalse(restarted_mgr.is_trading_allowed())

if __name__ == "__main__":
    unittest.main()
