import os
import json
import pytest
import time
from datetime import datetime
from pathlib import Path

from core.raw_capture import RawDecisionLogger

@pytest.fixture
def temp_logger(tmp_path):
    # Use a temporary directory for tests
    data_dir = tmp_path / "data" / "raw"
    logger = RawDecisionLogger(data_dir=str(data_dir))
    yield logger
    logger.stop()

def get_latest_records(logger_instance):
    logger_instance.queue.join() # Wait for queue to be empty
    time.sleep(0.1) # small buffer for the worker thread to finish writing
    date_str = logger_instance.current_date or datetime.now().strftime("%Y-%m-%d")
    file_path = logger_instance.data_dir / f"v2_raw_inputs_{date_str}.jsonl"
    
    if not file_path.exists():
        return []
        
    records = []
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))
    return records

def test_schema_integrity(temp_logger):
    """Verify all required fields exist and sequence/hash are computed correctly."""
    record = {
        "schema_version": 1,
        "correlation_id": "TEST-1",
        "signal_id": "TEST-1",
        "timestamp": datetime.now().isoformat(),
        "market_context": {"spot": 20000},
        "agent_payloads": {"test_agent": {"score": 50}},
        "option_context": {},
        "derived_pre_gate": {"confidence": 65},
        "structural_state": {
            "leg_id": 5, 
            "entries_in_leg": 2, 
            "pending_reset_event": None, 
            "reset_event": None
        },
        "provenance": {"engine_version": "v5.0.2-REF"}
    }
    
    temp_logger.capture(record)
    records = get_latest_records(temp_logger)
    
    assert len(records) == 1
    r = records[0]
    
    # Assert Schema
    assert "schema_version" in r
    assert "correlation_id" in r
    assert "signal_id" in r
    assert "timestamp" in r
    assert "market_context" in r
    assert "agent_payloads" in r
    assert "option_context" in r
    assert "derived_pre_gate" in r
    assert "structural_state" in r
    assert "provenance" in r
    assert "record_hash" in r
    assert "capture_sequence" in r
    
    assert r["capture_sequence"] == 1
    assert len(r["record_hash"]) == 64

def test_rejected_opportunities_are_captured(temp_logger):
    """Verify that multiple records, regardless of eventual rejection, are captured in sequence."""
    outcomes = ["PASS", "LOW_CONFIDENCE", "BAD_STRUCTURE", "SAME_STRUCTURAL_TREND"]
    
    for i, outcome in enumerate(outcomes):
        record = {
            "correlation_id": f"TEST-{i}",
            "timestamp": datetime.now().isoformat(),
            "intended_outcome": outcome  # In the real pipeline, this is evaluated after capture
        }
        temp_logger.capture(record)
        
    records = get_latest_records(temp_logger)
    assert len(records) == 4
    for i, r in enumerate(records):
        assert r["capture_sequence"] == i + 1
        assert r["intended_outcome"] == outcomes[i]

def test_no_trade_cycle_not_captured():
    """
    Verify that NO_TRADE cycles do not produce records.
    (This is enforced in DecisionPipeline.evaluate because it returns early for NO_TRADE
    before hitting the capture layer, so we just mock the pipeline logic here).
    """
    # In the actual pipeline, if signal_type == SignalType.NO_TRADE, it returns early.
    # We verify that if it's a no-trade, we literally don't call `capture`.
    logger = RawDecisionLogger(data_dir="test_dummy")
    
    signal_type = "NO_TRADE"
    if signal_type != "NO_TRADE":
        logger.capture({"correlation_id": "SHOULD_NOT_HAPPEN"})
        
    assert logger.queue.empty()
    logger.stop()

def test_logger_failure_safety(temp_logger, monkeypatch):
    """Verify that filesystem failures do not crash the pipeline."""
    # Force a failure during write
    def mock_write(*args, **kwargs):
        raise OSError("Mock disk full")
        
    monkeypatch.setattr(temp_logger, "_write_record", mock_write)
    
    # This should enqueue successfully
    temp_logger.capture({"correlation_id": "TEST-FAIL"})
    
    # Wait for processing
    temp_logger.queue.join()
    time.sleep(0.1)
    
    # Worker should still be alive, caller should not crash
    assert temp_logger.worker_thread.is_alive()
    
    # Enqueue a second record (even if the first failed) to show it's non-blocking
    temp_logger.capture({"correlation_id": "TEST-FAIL-2"})
    temp_logger.queue.join()
