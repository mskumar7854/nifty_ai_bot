"""
tests/test_drawdown_boundary.py — Surgical Boundary Tests for Financial Drawdown

Validates the fix for the ₹1,000 hardcoded floor bug across exact boundaries:
- For a ₹100,000 account @ 10% halt threshold:
  - Drawdown ₹999   ➔ ACTIVE
  - Drawdown ₹9,999 ➔ ACTIVE
  - Drawdown ₹10,000 ➔ HALTED
  - Drawdown ₹10,001 ➔ HALTED

Also verifies capital scaling:
- ₹50,000  @ 10%: ₹4,999 (ACTIVE) vs ₹5,000 (HALTED)
- ₹200,000 @ 10%: ₹19,999 (ACTIVE) vs ₹20,000 (HALTED)
"""

import pytest
from unittest.mock import MagicMock
from config.settings import Settings
from core.position_manager import PositionManager
from core.system_state import TradingStateManager, get_state_manager

def _create_test_pos_manager(capital: float, halt_pct: float, state_file: str) -> tuple[PositionManager, TradingStateManager]:
    state_mgr = TradingStateManager.reset_instance(state_file=state_file)
    state_mgr.set_state("ACTIVE", "Test setup")

    settings = Settings()
    settings.position.total_capital = capital
    settings.position.drawdown_halt_pct = halt_pct
    settings.position.drawdown_reduce_size_pct = halt_pct  # Isolate halt boundary specifically
    settings.position.max_daily_loss = capital * 0.5  # Ensure daily loss doesn't trigger first
    settings.position.max_weekly_loss = capital * 0.5

    pm = PositionManager(settings)
    # Ensure starting state
    pm.total_capital = capital
    pm.peak_capital = capital
    pm.master_high_water_mark = capital
    return pm, state_mgr

@pytest.mark.parametrize("loss_rupees,expected_state", [
    (999.0, "ACTIVE"),
    (9999.0, "ACTIVE"),
    (10000.0, "HALTED"),
    (10001.0, "HALTED"),
])
def test_100k_drawdown_boundaries(loss_rupees, expected_state, tmp_path):
    state_file = str(tmp_path / "system_state_100k.json")
    pm, state_mgr = _create_test_pos_manager(capital=100000.0, halt_pct=10.0, state_file=state_file)

    # Record a single closed trade loss of loss_rupees
    pm.total_capital -= loss_rupees
    pm.today_stats.total_pnl -= loss_rupees
    pm._check_circuit_breakers()

    assert state_mgr.get_state() == expected_state, (
        f"Loss of ₹{loss_rupees} on ₹100,000 capital resulted in {state_mgr.get_state()}, expected {expected_state}"
    )

def test_50k_capital_scaling(tmp_path):
    """₹50,000 @ 10% threshold: ₹4,999 is ACTIVE, ₹5,000 is HALTED"""
    state_file = str(tmp_path / "system_state_50k.json")
    
    # 1. Under boundary: ₹4,999
    pm, state_mgr = _create_test_pos_manager(capital=50000.0, halt_pct=10.0, state_file=state_file)
    pm.total_capital -= 4999.0
    pm.today_stats.total_pnl -= 4999.0
    pm._check_circuit_breakers()
    assert state_mgr.get_state() == "ACTIVE"

    # 2. At boundary: ₹5,000
    pm, state_mgr = _create_test_pos_manager(capital=50000.0, halt_pct=10.0, state_file=state_file)
    pm.total_capital -= 5000.0
    pm.today_stats.total_pnl -= 5000.0
    pm._check_circuit_breakers()
    assert state_mgr.get_state() == "HALTED"

def test_200k_capital_scaling(tmp_path):
    """₹200,000 @ 10% threshold: ₹19,999 is ACTIVE, ₹20,000 is HALTED"""
    state_file = str(tmp_path / "system_state_200k.json")
    
    # 1. Under boundary: ₹19,999
    pm, state_mgr = _create_test_pos_manager(capital=200000.0, halt_pct=10.0, state_file=state_file)
    pm.total_capital -= 19999.0
    pm.today_stats.total_pnl -= 19999.0
    pm._check_circuit_breakers()
    assert state_mgr.get_state() == "ACTIVE"

    # 2. At boundary: ₹20,000
    pm, state_mgr = _create_test_pos_manager(capital=200000.0, halt_pct=10.0, state_file=state_file)
    pm.total_capital -= 20000.0
    pm.today_stats.total_pnl -= 20000.0
    pm._check_circuit_breakers()
    assert state_mgr.get_state() == "HALTED"

def test_magic_mock_fails_safe_to_default_threshold(tmp_path):
    """
    Ensure that when settings are mocked (e.g. MagicMock),
    float(mock) does NOT cause halt_pct to evaluate to 1.0% (₹1,000).
    A loss of ₹1,500 on ₹100,000 capital must remain ACTIVE (since default is 12%).
    """
    state_file = str(tmp_path / "system_state_mock.json")
    state_mgr = TradingStateManager.reset_instance(state_file=state_file)
    state_mgr.set_state("ACTIVE", "Mock test setup")

    mock_settings = MagicMock()
    mock_settings.position.total_capital = 100000.0
    mock_settings.position.max_daily_loss = 50000.0
    mock_settings.position.max_weekly_loss = 50000.0
    # drawdown_halt_pct is NOT explicitly set, returning a MagicMock

    pm = PositionManager(mock_settings)
    pm.total_capital = 100000.0
    pm.peak_capital = 100000.0
    pm.master_high_water_mark = 100000.0

    # Drawdown of ₹1,500 (1.5%) - previously this triggered the bug because mock evaluated to 1.0%
    pm.total_capital -= 1500.0
    pm.today_stats.total_pnl -= 1500.0
    pm._check_circuit_breakers()

    assert state_mgr.get_state() == "ACTIVE", (
        f"MagicMock settings caused false halt at 1.5% drawdown! State: {state_mgr.get_state()}"
    )
