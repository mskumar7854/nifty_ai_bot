"""
P0-D: Simulation Hard Lock CI Tests
====================================
These tests ensure the broker-layer simulation lock (P0-A) cannot be bypassed.
Run in CI on every PR that touches dhan_client.py, position_manager.py, or main.py.
"""

import os
import pytest
from unittest.mock import patch, MagicMock
from dhan_client import SimulationModeError


class TestSimulationHardLock:
    """P0-A: SimulationModeError must block ALL order-placing methods in SIMULATION mode."""

    def test_simulation_hard_lock_blocks_real_orders(self):
        """Real orders MUST NEVER reach broker in SIMULATION mode."""
        with patch.dict(os.environ, {"SYSTEM_MODE": "SIMULATION"}):
            # Need to reset the singleton
            import dhan_client
            dhan_client._client = None

            with patch("dhan_client.dhanhq") as mock_dhan_cls, \
                 patch("dhan_client.ACCESS_TOKEN", "not-a-jwt"), \
                 patch("dhan_client._client", None):
                mock_dhan_cls.return_value = MagicMock()
                from dhan_client import get_dhan_client
                client = get_dhan_client()

                with pytest.raises(SimulationModeError):
                    client.place_order(
                        security_id="123",
                        exchange_segment="NSE_FNO",
                        transaction_type="BUY",
                        quantity=50,
                        order_type="MARKET",
                        product_type="INTRADAY"
                    )

    def test_simulation_lock_logs_call_stack(self, caplog):
        """Call stack must be logged so we know the origin of the rogue call."""
        import logging
        with patch.dict(os.environ, {"SYSTEM_MODE": "SIMULATION"}):
            import dhan_client
            dhan_client._client = None

            with patch("dhan_client.dhanhq") as mock_dhan_cls, \
                 patch("dhan_client.ACCESS_TOKEN", "not-a-jwt"), \
                 patch("dhan_client._client", None):
                mock_dhan_cls.return_value = MagicMock()
                from dhan_client import get_dhan_client
                client = get_dhan_client()

                with caplog.at_level(logging.CRITICAL):
                    with pytest.raises(SimulationModeError):
                        client.place_order(security_id="123")

                assert "Call stack" in caplog.text

    def test_simulation_blocks_modify_order(self):
        """modify_order must also be blocked in SIMULATION mode."""
        with patch.dict(os.environ, {"SYSTEM_MODE": "SIMULATION"}):
            import dhan_client
            dhan_client._client = None

            with patch("dhan_client.dhanhq") as mock_dhan_cls, \
                 patch("dhan_client.ACCESS_TOKEN", "not-a-jwt"), \
                 patch("dhan_client._client", None):
                mock_dhan_cls.return_value = MagicMock()
                from dhan_client import get_dhan_client
                client = get_dhan_client()

                with pytest.raises(SimulationModeError):
                    client.modify_order(order_id="123", quantity=100)

    def test_simulation_blocks_cancel_order(self):
        """cancel_order must also be blocked in SIMULATION mode."""
        with patch.dict(os.environ, {"SYSTEM_MODE": "SIMULATION"}):
            import dhan_client
            dhan_client._client = None

            with patch("dhan_client.dhanhq") as mock_dhan_cls, \
                 patch("dhan_client.ACCESS_TOKEN", "not-a-jwt"), \
                 patch("dhan_client._client", None):
                mock_dhan_cls.return_value = MagicMock()
                from dhan_client import get_dhan_client
                client = get_dhan_client()

                with pytest.raises(SimulationModeError):
                    client.cancel_order(order_id="123")

    def test_live_mode_allows_order(self):
        """Sanity check: LIVE mode does not raise SimulationModeError."""
        with patch.dict(os.environ, {"SYSTEM_MODE": "LIVE"}):
            import dhan_client
            dhan_client._client = None

            with patch("dhan_client.dhanhq") as mock_dhan_cls, \
                 patch("dhan_client.ACCESS_TOKEN", "not-a-jwt"), \
                 patch("dhan_client._client", None):
                mock_real = MagicMock()
                mock_real.place_order.return_value = {"status": "ok"}
                mock_dhan_cls.return_value = mock_real
                from dhan_client import get_dhan_client
                client = get_dhan_client()

                result = client.place_order(security_id="123", quantity=50)
                assert result == {"status": "ok"}

    def test_read_methods_pass_through_in_simulation(self):
        """Read-only methods like get_positions must work in SIMULATION mode."""
        with patch.dict(os.environ, {"SYSTEM_MODE": "SIMULATION"}):
            import dhan_client
            dhan_client._client = None

            with patch("dhan_client.dhanhq") as mock_dhan_cls, \
                 patch("dhan_client.ACCESS_TOKEN", "not-a-jwt"), \
                 patch("dhan_client._client", None):
                mock_real = MagicMock()
                mock_real.get_positions.return_value = {"status": "success", "data": []}
                mock_real.get_fund_limits.return_value = {"status": "success"}
                mock_dhan_cls.return_value = mock_real
                from dhan_client import get_dhan_client
                client = get_dhan_client()

                # These should NOT raise
                result = client.get_positions()
                assert result["status"] == "success"

                result = client.get_fund_limits()
                assert result["status"] == "success"
