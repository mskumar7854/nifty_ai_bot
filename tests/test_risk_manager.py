"""
P2-E: Risk Manager Test Suite
================================
Tests crash-safe P&L persistence, daily limit enforcement,
and trading halt behavior.
"""

import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import date


class TestRiskManagerPersistence:
    """P0-B: Daily P&L must survive crashes and restarts."""

    def _make_risk_manager(self, state_file: Path):
        """Helper to create a RiskManager with a custom state file."""
        settings = MagicMock()
        settings.position.max_daily_loss = 3000.0
        settings.friday_cutoff = "15:10"
        settings.daily_cutoff = "15:20"
        
        db_manager = MagicMock()
        
        # Patch the STATE_FILE path
        with patch("core.risk_manager.STATE_FILE", state_file):
            from core.risk_manager import RiskManager
            return RiskManager(settings, db_manager)

    def test_pnl_persists_across_restart(self, tmp_path):
        """P&L must survive a simulated crash/restart."""
        state_file = tmp_path / "risk_state.json"
        
        rm = self._make_risk_manager(state_file)
        with patch("core.risk_manager.STATE_FILE", state_file):
            rm.update_daily_pnl_manual(-1500)
            assert rm.daily_pnl == -1500
        
        # Simulate restart
        rm2 = self._make_risk_manager(state_file)
        assert rm2.daily_pnl == -1500

    def test_pnl_resets_on_new_day(self, tmp_path):
        """Counter resets when date in state file doesn't match today."""
        state_file = tmp_path / "risk_state.json"
        
        # Write a state file with yesterday's date
        yesterday_state = {
            "date": "2020-01-01",  # Definitely not today
            "daily_pnl": -2000,
            "trades_today": 5,
            "trading_enabled": False,
        }
        state_file.write_text(json.dumps(yesterday_state))
        
        rm = self._make_risk_manager(state_file)
        assert rm.daily_pnl == 0.0
        assert rm.trades_today == 0
        assert rm.trading_enabled is True

    def test_trading_halts_at_daily_limit(self, tmp_path):
        """Trading must halt when daily loss limit is hit."""
        state_file = tmp_path / "risk_state.json"
        
        rm = self._make_risk_manager(state_file)
        with patch("core.risk_manager.STATE_FILE", state_file):
            rm.update_daily_pnl_manual(-3000)
        
        assert rm.trading_enabled is False

    def test_state_file_is_valid_json(self, tmp_path):
        """State file must always be valid JSON after write."""
        state_file = tmp_path / "risk_state.json"
        
        rm = self._make_risk_manager(state_file)
        with patch("core.risk_manager.STATE_FILE", state_file):
            rm.update_daily_pnl_manual(-500)
        
        # Read the file and verify it's valid JSON
        data = json.loads(state_file.read_text())
        assert data["date"] == date.today().isoformat()
        assert data["daily_pnl"] == -500
        assert data["trades_today"] == 1

    def test_corrupt_state_file_starts_fresh(self, tmp_path):
        """Corrupt state file should not crash — start fresh instead."""
        state_file = tmp_path / "risk_state.json"
        state_file.write_text("{{invalid json}}}}}")
        
        rm = self._make_risk_manager(state_file)
        assert rm.daily_pnl == 0.0
        assert rm.trading_enabled is True
