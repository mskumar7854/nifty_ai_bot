import pytest
from unittest.mock import MagicMock, patch
import json
import base64
import asyncio

# P0.1 — datetime import test
def test_main_has_datetime_import():
    """Prevent regression of the time-bomb bug."""
    import main
    # If this import succeeds, datetime is in main's namespace
    assert hasattr(main, 'datetime'), "datetime must be imported in main.py"

def _make_mock_jwt(payload_dict):
    header = base64.urlsafe_b64encode(b'{"alg":"HS256"}').decode().rstrip("=")
    payload = base64.urlsafe_b64encode(json.dumps(payload_dict).encode()).decode().rstrip("=")
    signature = "mock_signature"
    return f"{header}.{payload}.{signature}"

# P0.2 — Token expiry test
class TestTokenExpiry:
    def test_expired_token_raises(self):
        """Expired JWT must raise RuntimeError."""
        from datetime import datetime, timedelta, timezone
        
        expired_payload = {
            "exp": (datetime.now(timezone.utc) - timedelta(hours=1)).timestamp(),
            "client_id": "test"
        }
        expired_token = _make_mock_jwt(expired_payload)
        
        with patch("dhan_client.ACCESS_TOKEN", expired_token), \
             patch("dhan_client._client", None):
            from dhan_client import get_dhan_client
            with pytest.raises(RuntimeError, match="EXPIRED"):
                get_dhan_client()
    
    def test_valid_token_passes(self):
        """Valid JWT must succeed."""
        from datetime import datetime, timedelta, timezone
        
        valid_payload = {
            "exp": (datetime.now(timezone.utc) + timedelta(hours=10)).timestamp(),
            "client_id": "test"
        }
        valid_token = _make_mock_jwt(valid_payload)
        
        with patch("dhan_client.ACCESS_TOKEN", valid_token), \
             patch("dhan_client._client", None), \
             patch("dhan_client.dhanhq") as mock_dhan:
            mock_dhan.return_value = MagicMock()
            from dhan_client import get_dhan_client
            client = get_dhan_client()
            assert client is not None
    
    def test_malformed_token_fails_open(self):
        """Non-JWT token should not block trading (warn only)."""
        with patch("dhan_client.ACCESS_TOKEN", "not-a-jwt"), \
             patch("dhan_client._client", None), \
             patch("dhan_client.dhanhq") as mock_dhan:
            mock_dhan.return_value = MagicMock()
            from dhan_client import get_dhan_client
            client = get_dhan_client()
            assert client is not None  # Should not raise


# P0.3 — Reconciliation test
class TestReconciliation:
    def test_orphan_halts_trading(self):
        """An orphaned broker position must halt trading."""
        # Mock system with no internal positions
        system = MagicMock()
        system.is_simulation = False
        system.position_manager.open_positions = {}
        system.trading_enabled = True
        
        # Mock broker returning an orphan
        with patch("dhan_client.get_dhan_client") as mock_get_dhan, \
             patch("core.system_state.get_state_manager") as mock_get_state_mgr:
            
            mock_dhan = MagicMock()
            mock_dhan.get_positions.return_value = {
                "status": "success",
                "data": [
                    {"positionType": "INTRADAY", "netQty": 50, 
                     "securityId": "999", "tradingSymbol": "NIFTY24500CE"}
                ]
            }
            mock_get_dhan.return_value = mock_dhan
            
            mock_state_mgr = MagicMock()
            mock_get_state_mgr.return_value = mock_state_mgr
            
            from main import NiftyAISystem
            result = asyncio.run(NiftyAISystem._reconcile_broker_positions(system))
            
            assert result is False
            assert system.trading_enabled is False, "Trading must halt on orphan"
            mock_state_mgr.trigger_structural_halt.assert_called_with(
                "Orphaned positions detected on broker: NIFTY24500CE (Qty: 50)"
            )
    
    def test_simulation_skips_reconciliation(self):
        system = MagicMock()
        system.is_simulation = True
        system.trading_enabled = True
        
        from main import NiftyAISystem
        asyncio.run(NiftyAISystem._reconcile_broker_positions(system))
        
        assert system.trading_enabled is True  # Still enabled

    def test_failed_fetch_halts_startup_in_live(self):
        """Failure to fetch positions at startup in LIVE mode must halt startup."""
        system = MagicMock()
        system.is_simulation = False
        system.trading_enabled = True
        
        with patch("dhan_client.get_dhan_client") as mock_get_dhan, \
             patch("core.system_state.get_state_manager") as mock_get_state_mgr:
            
            mock_dhan = MagicMock()
            mock_dhan.get_positions.return_value = {
                "status": "failure",
                "remarks": "Invalid access token"
            }
            mock_get_dhan.return_value = mock_dhan
            
            mock_state_mgr = MagicMock()
            mock_get_state_mgr.return_value = mock_state_mgr
            
            from main import NiftyAISystem
            result = asyncio.run(NiftyAISystem._reconcile_broker_positions(system))
            
            assert result is False
            assert system.trading_enabled is False
            mock_state_mgr.set_state.assert_called_with(
                "HALTED", "Startup Broker Reconciliation Failed: Could not fetch broker positions for reconciliation after 3 attempts", source="system"
            )

# Miss 1 - Agent Abstain test
class TestAgentAbstain:
    def test_oi_agent_abstains_on_simulated_data_in_live(self):
        from agents.oi_agent import OIAgent
        from models.signals import MarketSnapshot, DataSource, Direction
        from config.settings import Settings
        from datetime import datetime

        settings = Settings()
        settings.system_mode.mode = "LIVE"
        agent = OIAgent(settings)
        
        # Simulated data
        snapshot = MarketSnapshot(
            timestamp=datetime.now(),
            price=22000, open=22000, high=22000, low=22000, close=22000,
            volume=1000, vwap=22000, rsi=50, ema_fast=22000, ema_slow=22000, atr=50,
            oi_data_source=DataSource.SIMULATED
        )
        
        import pandas as pd
        df = pd.DataFrame()
        output = agent.analyze(df, snapshot)
        
        assert output.details.get("abstained") is True
        assert output.direction == Direction.NEUTRAL
