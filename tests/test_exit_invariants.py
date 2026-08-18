import unittest
import os
import json
from datetime import datetime
from unittest.mock import MagicMock, patch

from core.context import RuntimeContext
from config.settings import Settings
from models import (
    MarketSnapshot, PositionState, Signal, SignalType, Direction,
    TradeHealth, ExitDecisionType
)
from core.position_manager import PositionManager, OpenPosition
from core.pipelines.position_pipeline import PositionPipeline
from core.economics import CostEngine
from core.system_state import TradingStateManager

class TestExitInvariants(unittest.TestCase):
    def setUp(self):
        self.state_file = os.path.join("data", "system_state_test.json")
        self.audit_file = os.path.join("data", "state_transitions_test.jsonl")
        os.environ["NIFTY_SYSTEM_STATE_FILE"] = self.state_file
        os.environ["SYSTEM_MODE"] = "SIMULATION"
        for fpath in [self.state_file, self.audit_file]:
            if os.path.exists(fpath):
                try: os.remove(fpath)
                except Exception: pass
        
        self.settings = Settings()
        self.settings.max_daily_loss = 5000.0
        self.settings.risk_per_trade_pct = 1.0
        
        self.settings.position.tsl_tighten_2_trigger_pct = 25.0
        self.settings.position.tsl_tighten_1_trigger_pct = 15.0
        self.settings.position.tsl_activate_trigger_pct = 10.0
        self.settings.position.tsl_breakeven_trigger_pct = 5.0

        self.ctx = RuntimeContext(
            settings=self.settings,
            mode="SIMULATION",
            is_simulation=True,
            telegram_enabled=False,
            db_manager=MagicMock(),
            data_manager=MagicMock(),
            burnin_tracker=MagicMock(),
            readiness_scorer=MagicMock(),
            simulation=MagicMock()
        )
        
        self.state_mgr = TradingStateManager.reset_instance(state_file=self.state_file)
        self.state_mgr.set_state("ACTIVE", "Test Setup")

        self.oms = MagicMock()
        
        self.pos_mgr = PositionManager(self.settings)
        self.pos_mgr.mode = "SIMULATION"
        self.pos_mgr.oms = self.oms
        self.pos_mgr.trade_logger = MagicMock()
        self.pos_mgr.tuner = MagicMock()
        
        self.pos_pipeline = PositionPipeline(self.ctx)
        
    def tearDown(self):
        for fpath in [self.state_file, self.audit_file]:
            if os.path.exists(fpath):
                try: os.remove(fpath)
                except Exception: pass
        os.environ.pop("NIFTY_SYSTEM_STATE_FILE", None)
        os.environ.pop("SYSTEM_MODE", None)
        TradingStateManager.reset_instance()

    def _create_dummy_position(self, pos_id, qty=50, entry_price=200.0, sl_price=190.0, t2_price=300.0):
        pos = OpenPosition(
            position_id=pos_id, intent_id=f"INT_{pos_id}", entry_time=datetime.now(),
            signal_type=SignalType.BUY_CE, direction=Direction.BULLISH, symbol="NIFTY",
            security_id="123", entry_price=entry_price, entry_bid=entry_price, entry_ask=entry_price,
            current_price=entry_price, stop_loss=sl_price, original_stop_loss=sl_price,
            target_1=entry_price+50, target_2=t2_price, trailing_stop=sl_price, lots=qty//50, qty=qty, entry_premium=entry_price
        )
        return pos

    def _create_snapshot(self, price=200.0):
        return MarketSnapshot(
            timestamp=datetime.now(),
            price=price + 24000.0,
            open=price + 24000.0,
            high=price + 24000.0,
            low=price + 24000.0,
            close=price + 24000.0,
            volume=1000,
            vwap=price + 24000.0,
            rsi=50.0,
            ema_fast=price + 24000.0,
            ema_slow=price + 24000.0,
            atr=10.0,
            india_vix=15.0,
            atm_ce_premium=price,
            atm_pe_premium=price
        )

    # =========================================================================
    # LAYER 1: MATHEMATICAL INVARIANTS
    # =========================================================================

    def test_07_independent_pnl_calculation(self):
        """07 Independent P&L: Outcome P&L matches independently calculated P&L"""
        entry_price = 200.0
        exit_price = 230.0
        qty = 50
        
        buy_value = entry_price * qty
        sell_value = exit_price * qty
        total_turnover = buy_value + sell_value
        
        gross_pnl = sell_value - buy_value
        self.assertEqual(gross_pnl, 1500.0)

        # Independent manual math based on exact rates
        brokerage = 20.0 * 2
        exchange_charges = total_turnover * 0.000495
        gst = (brokerage + exchange_charges) * 0.18
        stt = sell_value * 0.001
        sebi = total_turnover * 0.000001
        stamp_duty = buy_value * 0.00003
        
        total_costs = brokerage + exchange_charges + gst + stt + sebi + stamp_duty
        expected_net = gross_pnl - total_costs

        costs = CostEngine.calculate_costs(entry_price, exit_price, qty, "BUY")
        self.assertAlmostEqual(costs["net_pnl"], round(expected_net, 2), delta=0.01)
        
        self.pos_mgr.open_positions["POS_7"] = self._create_dummy_position("POS_7", qty, entry_price)
        result = self.pos_mgr.close_position("POS_7", exit_price, "Test Exit")
        
        self.assertAlmostEqual(result["net_pnl"], costs["net_pnl"])
        self.assertEqual(result["pnl"], costs["net_pnl"])

    def test_08_independent_r_calculation(self):
        """08 Independent R: Outcome R matches P&L / risk budget"""
        entry_price = 200.0
        sl_price = 190.0
        exit_price = 250.0
        qty = 50
        
        costs = CostEngine.calculate_costs(entry_price, exit_price, qty, "BUY")
        independently_calculated_net_pnl = costs["net_pnl"]
        risk_budget = abs(entry_price - sl_price) * qty
        expected_R = independently_calculated_net_pnl / risk_budget
        
        self.pos_mgr.open_positions["POS_8"] = self._create_dummy_position("POS_8", qty, entry_price, sl_price)
        captured_metrics = {}
        def mock_save(db_path, intent_id, costs, execution_metrics):
            captured_metrics.update(execution_metrics)
            
        with patch('core.economics.CostEngine.save_trade_economics', side_effect=mock_save):
            self.pos_mgr.close_position("POS_8", exit_price, "Target Hit")
            
        self.assertEqual(captured_metrics["realized_r_multiple"], expected_R)

    # =========================================================================
    # LAYER 2: STATE & LIFECYCLE INVARIANTS
    # =========================================================================

    def test_03_tsl_monotonicity(self):
        """03 TSL monotonicity: TSL never regresses (Phase & Stop-price)"""
        entry_price = 200.0
        pos = self._create_dummy_position("POS_3", entry_price=entry_price)
        pos.tsl_highest_premium = entry_price
        
        phases_expected = ["INITIAL", "BREAKEVEN", "ACTIVE", "TIGHTEN_1", "TIGHTEN_2"]
        last_sl = pos.stop_loss
        last_phase_idx = -1
        
        prices_to_test = [200.0, 210.0, 220.0, 230.0, 250.0, 198.0]
        
        for price in prices_to_test:
            snapshot = self._create_snapshot(price)
            self.pos_pipeline._update_position_state(pos, snapshot)
            decision = self.pos_pipeline._make_exit_decision(pos, snapshot)
            
            if decision.decision == ExitDecisionType.ADJUST_STOP:
                new_sl = decision.new_stop_loss
                self.assertGreaterEqual(new_sl, last_sl, "TSL moved backwards!")
                pos.stop_loss = new_sl
                last_sl = new_sl
                
            current_phase_idx = phases_expected.index(pos.tsl_phase) if pos.tsl_phase in phases_expected else 0
            self.assertGreaterEqual(current_phase_idx, last_phase_idx, "TSL phase moved backwards!")
            last_phase_idx = current_phase_idx

    def test_04_closed_state_integrity(self):
        """04 Closed-state integrity: Closed position cannot remain OPEN"""
        self.pos_mgr.open_positions["POS_4"] = self._create_dummy_position("POS_4")
        self.pos_mgr.close_position("POS_4", 210.0, "Manual Exit")
        self.assertNotIn("POS_4", self.pos_mgr.open_positions, "Position remained in open_positions!")

    def test_05_lifecycle_resolution(self):
        """05 Lifecycle resolution: Every filled entry eventually resolves to OPEN or CLOSED"""
        self.pos_mgr.open_positions["POS_5"] = self._create_dummy_position("POS_5")
        snapshot = self._create_snapshot(180.0)
        actions = self.pos_mgr.update_positions(current_price=180.0, snapshot=snapshot)
        self.assertTrue(any(a["type"] == "exit" for a in actions))
        self.assertNotIn("POS_5", self.pos_mgr.open_positions)
        self.assertTrue(any(c["trade_id"] == "POS_5" for c in self.pos_mgr.closed_positions_today))

    def test_09_partial_fill_accounting(self):
        """09 Partial-fill accounting: Partial fills use actual filled quantity"""
        self.pos_mgr.open_positions["POS_9"] = self._create_dummy_position("POS_9", qty=100)
        res = self.pos_mgr.close_position("POS_9", exit_price=210.0, reason="Partial", partial_qty=40)
        self.assertEqual(res["type"], "partial")
        self.assertEqual(res["remaining_qty"], 60)
        
        pos = self.pos_mgr.open_positions["POS_9"]
        self.assertEqual(pos.qty, 60)
        self.assertEqual(pos.realized_pnl, (210.0 - 200.0) * 40)
        
        res_full = self.pos_mgr.close_position("POS_9", exit_price=220.0, reason="Full Exit")
        self.assertEqual(res_full["type"], "full")
        self.assertNotIn("POS_9", self.pos_mgr.open_positions)

    def test_11_duplicate_exit_protection(self):
        """11 Duplicate-exit protection: Simultaneous triggers reject duplicates"""
        self.pos_mgr.open_positions["POS_11"] = self._create_dummy_position("POS_11")
        res1 = self.pos_mgr.close_position("POS_11", 210.0, "Target Hit")
        self.assertIsNotNone(res1)
        res2 = self.pos_mgr.close_position("POS_11", 215.0, "Health Exit")
        self.assertIsNone(res2)

    # =========================================================================
    # LAYER 3: PERSISTENCE & INTEGRATION INVARIANTS
    # =========================================================================

    def test_01_sl_single_exit(self):
        """01 SL single-exit: SL trigger -> exactly one exit"""
        self.pos_mgr.open_positions["POS_1"] = self._create_dummy_position("POS_1", sl_price=190.0)
        snapshot = self._create_snapshot(185.0)
        actions = self.pos_mgr.update_positions(current_price=185.0, snapshot=snapshot)
        exits = [a for a in actions if a["type"] == "exit" and a["position_id"] == "POS_1"]
        self.assertEqual(len(exits), 1)
        self.assertIn("Hard Stop Loss Hit", exits[0]["reason"])

    def test_02_target_single_exit(self):
        """02 Target single-exit: Target trigger -> exactly one exit"""
        self.pos_mgr.open_positions["POS_2"] = self._create_dummy_position("POS_2", t2_price=300.0)
        snapshot = self._create_snapshot(310.0)
        actions = self.pos_mgr.update_positions(current_price=310.0, snapshot=snapshot)
        exits = [a for a in actions if a["type"] == "exit" and a["position_id"] == "POS_2"]
        self.assertEqual(len(exits), 1)
        self.assertIn("Target 2 Hit", exits[0]["reason"])

    def test_06_single_terminal_outcome(self):
        """06 Single terminal outcome: CLOSED position has exactly one outcome"""
        self.pos_mgr.open_positions["POS_6"] = self._create_dummy_position("POS_6")
        self.pos_mgr.closed_positions_today = []
        self.pos_mgr.close_position("POS_6", 210.0, "Manual Exit")
        outcomes = [p for p in self.pos_mgr.closed_positions_today if p.get("trade_id") == "POS_6"]
        self.assertEqual(len(outcomes), 1)

    def test_10_crash_risk_state_recovery(self):
        """10 Crash risk-state recovery: Recovery must preserve risk state, not merely position existence"""
        self.oms.get_open_orders.return_value = [
            {
                "state": "ENTRY_FILLED",
                "signal_id": "POS_10",
                "intent_id": "INT_10",
                "symbol": "NIFTY26MAY21500CE",
                "side": "BUY",
                "avg_fill_price": 200.0,
                "stop_loss_price": 215.0,
                "filled_qty": 50,
                "created_at": datetime.now().isoformat()
            }
        ]
        self.pos_mgr._recover_live_state()
        self.assertIn("POS_10", self.pos_mgr.open_positions)
        recovered_pos = self.pos_mgr.open_positions["POS_10"]
        self.assertEqual(recovered_pos.entry_price, 200.0)
        self.assertEqual(recovered_pos.stop_loss, 215.0)
        self.assertEqual(recovered_pos.qty, 50)
        self.assertEqual(recovered_pos.intent_id, "INT_10")
        
        res = self.pos_mgr.close_position("POS_10", 220.0, "Test Close")
        self.assertIsNotNone(res)
        self.assertNotIn("POS_10", self.pos_mgr.open_positions)

    def test_12_eod_square_off(self):
        """12 EOD square-off: EOD -> zero positions"""
        import dhan_client
        mock_dhan = MagicMock()
        mock_dhan.return_value.place_order.return_value = {"status": "success"}
        old_get_dhan = dhan_client.get_dhan_client
        try:
            dhan_client.get_dhan_client = mock_dhan
            self.pos_mgr.open_positions["POS_12A"] = self._create_dummy_position("POS_12A")
            self.pos_mgr.open_positions["POS_12B"] = self._create_dummy_position("POS_12B")
            self.pos_mgr.close_all_positions(reason="EOD Square-off")
        finally:
            dhan_client.get_dhan_client = old_get_dhan
        self.assertEqual(len(self.pos_mgr.open_positions), 0)

    def test_13_exit_price_provenance(self):
        """13 Exit-price provenance: Use actual fill, not requested price"""
        self.pos_mgr.open_positions["POS_13"] = self._create_dummy_position("POS_13")
        requested_exit = 245.0
        actual_fill = 242.80
        res = self.pos_mgr.close_position("POS_13", actual_fill, "Target Hit (Actual Fill)")
        costs = CostEngine.calculate_costs(200.0, actual_fill, 50, "BUY")
        self.assertAlmostEqual(res["pnl"], costs["net_pnl"])

if __name__ == '__main__':
    unittest.main()
