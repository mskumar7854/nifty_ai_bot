import os
import pytest
from core.system_state import TradingStateManager

@pytest.fixture(autouse=True)
def isolate_system_state_for_tests(tmp_path, monkeypatch):
    """
    Architectural isolation fixture for all tests.
    Ensures zero test writes to production state, audit files, or sqlite databases.
    Injects temporary state, audit, and database paths into environment.
    """
    test_state_file = str(tmp_path / "system_state_test.json")
    test_audit_file = str(tmp_path / "state_transitions_test.jsonl")
    test_db_file = str(tmp_path / "trading_v4_test.db")

    monkeypatch.setenv("NIFTY_SYSTEM_STATE_FILE", test_state_file)
    monkeypatch.setenv("NIFTY_AUDIT_FILE", test_audit_file)
    monkeypatch.setenv("NIFTY_DB_PATH", test_db_file)

    # Initialize clean isolated instance
    TradingStateManager.reset_instance(state_file=test_state_file)

    yield test_state_file, test_audit_file, test_db_file

    # Teardown: clear singleton
    TradingStateManager.reset_instance(state_file=None)
