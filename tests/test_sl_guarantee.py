import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from core.position_manager import (
    EntryResult,
    SL_MAX_RETRIES,
    SL_PLACEMENT_TIMEOUT_SECONDS,
    VALID_SL_STATUSES,
)

# A simplified mock class to stand in for PositionManager
class MockPositionManager:
    def __init__(self):
        self.dhan = MagicMock()
        self.logger = MagicMock()
        self._halt_trading = MagicMock()

    # Copy the core logic of the methods we want to test to the mock instance,
    # or we can test the actual PositionManager methods if we patch appropriately.

@pytest.fixture
def manager():
    from config.settings import Settings
    settings = Settings()
    settings.position.max_daily_trades = 10

    from core.position_manager import PositionManager
    
    mock_client = MagicMock()
    with patch("dhan_client.get_dhan_client", return_value=mock_client):
        pm = PositionManager(settings)
        
        # Patch the async wrapper directly so we can test the logic without real threads
        pm._place_order_async = AsyncMock()
        
        yield pm

@pytest.fixture
def fill():
    return EntryResult(
        filled=True,
        order_id="123",
        fill_price=100.0,
        fill_qty=50,
        symbol="NIFTY",
        security_id="999",
        exchange_segment="NSE_FNO"
    )

@pytest.mark.asyncio
async def test_sl_timeout_but_exists(manager, fill):
    """
    Test 1: SL Timeout -> Still Verified
    If place_order times out, but get_order_list confirms it's there, we return True.
    """
    # 1. Mock place_order to raise TimeoutError
    manager._place_order_async.side_effect = asyncio.TimeoutError
    
    # 2. Mock get_order_list to return empty on first verify, then return the SL order on the second
    manager.dhan.get_order_list.side_effect = [
        {"status": "success", "data": []},
        {"status": "success", "data": [{
            "tradingSymbol": "NIFTY",
            "orderType": "SL-M",
            "orderStatus": "PENDING",
            "triggerPrice": 90.0
        }]}
    ]
    
    # Needs to run within an event loop.
    result = await manager._place_sl_with_retry(fill, stop_loss_price=90.0, sl_transaction_type="SELL")
    
    assert result is True
    assert manager._place_order_async.call_count == 1
    # Check that verification was called (via dhan.get_order_list)
    assert manager.dhan.get_order_list.call_count >= 1

@pytest.mark.asyncio
async def test_sl_failure_triggers_exit(manager, fill):
    """
    Test 2: SL Missing -> Force Exit
    If all retries fail, it should return False and eventually trigger emergency close.
    """
    manager._place_order_async.side_effect = Exception("API Error")
    
    manager.dhan.get_order_list.return_value = {
        "status": "success",
        "data": [] # No SL present
    }
    
    result = await manager._place_sl_with_retry(fill, stop_loss_price=90.0, sl_transaction_type="SELL")
    
    assert result is False
    assert manager._place_order_async.call_count == SL_MAX_RETRIES

@pytest.mark.asyncio
async def test_existing_sl_not_replaced(manager, fill):
    """
    Test 3: Duplicate Prevention
    If get_order_list confirms SL is already placed, we don't call place_order again.
    """
    manager.dhan.get_order_list.return_value = {
        "status": "success",
        "data": [{
            "tradingSymbol": "NIFTY",
            "orderType": "SL-M",
            "orderStatus": "PENDING",
            "triggerPrice": 90.0
        }]
    }
    
    result = await manager._place_sl_with_retry(fill, stop_loss_price=90.0, sl_transaction_type="SELL")
    
    assert result is True
    # Place order should NOT be called at all because verify happens first
    manager._place_order_async.assert_not_called()

@pytest.mark.asyncio
async def test_order_list_failure(manager, fill):
    """
    Test 4: Order List Failure
    If get_order_list raises an exception, _verify_sl_order returns False safely.
    """
    manager.dhan.get_order_list.side_effect = Exception("API down")
    
    result = await manager._verify_sl_order(fill.symbol, expected_trigger=90.0, client_id="SL_123")
    
    assert result is False

@pytest.mark.asyncio
async def test_emergency_close_called_on_fatal_failure(manager, fill):
    """
    Integration-ish test: Ensure that a complete failure in open_position_with_sl_guarantee
    triggers _emergency_close_position.
    """
    signal = MagicMock()
    signal.symbol = "NIFTY"
    signal.security_id = "999"
    signal.direction.value = "BUY"
    signal.metadata = {"quote": None}
    
    size_params = {
        "allowed": True, "qty": 50, "sl_price": 90.0, "lots": 1, "risk_per_lot": 500,
        "target_1": 120.0, "target_2": 150.0, "risk_amount": 500.0
    }
    
    # Entry succeeds
    manager._place_order_async.return_value = {"status": "success", "data": {"orderId": "ENT123"}}
    
    # SL verification always fails
    manager._verify_sl_order = AsyncMock(return_value=False)
    
    # SL placement always fails
    manager._place_sl_with_retry = AsyncMock(return_value=False)
    
    # Emergency close mock
    manager._emergency_close_position = AsyncMock()
    manager._halt_trading = MagicMock()
    
    result = await manager.open_position_with_sl_guarantee(signal, size_params, fill_price=100.0)
    
    assert result is None
    manager._halt_trading.assert_called_once()
    assert manager._emergency_close_position.call_count == 1
    args, kwargs = manager._emergency_close_position.call_args
    assert args[0].symbol == "NIFTY"
    assert args[1] == "SELL" # transaction type for SL
