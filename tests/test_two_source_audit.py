"""
Tests for Two-Source Audit Architecture in generate_daily_audit.py:
1. Deduplication of telemetry records by engine_cycle_id
2. Structured consumption of decision_status == 'HALTED'
3. Preservation of lifecycle funnel (engine cycles vs directional candidates)
4. Independent campaign accounting (economic-valid vs capture-valid)
"""

import json
import pytest
from pathlib import Path
from tools.generate_daily_audit import (
    _load_execution_metrics,
    _get_campaign_progress,
    WORKSPACE
)


def test_load_execution_metrics_deduplication(tmp_path, monkeypatch):
    """Verify that multiple telemetry records for the same engine_cycle_id are deduplicated."""
    metrics_file = tmp_path / "execution_metrics.jsonl"
    
    # 6 records across 2 cycles for test date 2026-09-04
    records = [
        {"engine_cycle_id": 1, "timestamp": "2026-09-04T09:15:00", "decision_status": "HALTED", "rejection_reason": "Phase 1 Halt: PRE_MARKET", "regime": "RANGE"},
        {"engine_cycle_id": 1, "timestamp": "2026-09-04T09:15:00", "decision_status": "HALTED", "rejection_reason": "Phase 1 Halt: PRE_MARKET", "regime": "RANGE"},
        {"engine_cycle_id": 2, "timestamp": "2026-09-04T09:16:00", "decision_status": "HALTED", "rejection_reason": "Phase 2 Halt: Intraday Spike Freeze active", "regime": "TREND_UP"},
        {"engine_cycle_id": 2, "timestamp": "2026-09-04T09:16:00", "decision_status": "HALTED", "rejection_reason": "Phase 2 Halt: Intraday Spike Freeze active", "regime": "TREND_UP"},
        {"engine_cycle_id": 2, "timestamp": "2026-09-04T09:16:00", "decision_status": "HALTED", "rejection_reason": "Phase 2 Halt: Intraday Spike Freeze active", "regime": "TREND_UP"},
        # Another date that shouldn't be counted
        {"engine_cycle_id": 99, "timestamp": "2026-09-05T09:15:00", "decision_status": "HALTED", "regime": "RANGE"}
    ]
    with open(metrics_file, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")

    # Monkeypatch WORKSPACE to tmp_path
    monkeypatch.setattr("tools.generate_daily_audit.WORKSPACE", tmp_path)
    (tmp_path / "data").mkdir(exist_ok=True)
    import shutil
    shutil.move(str(metrics_file), str(tmp_path / "data" / "execution_metrics.jsonl"))

    metrics = _load_execution_metrics("2026-09-04")
    assert metrics["has_data"] is True
    assert metrics["total_records"] == 5
    assert metrics["evaluation_cycles"] == 2
    assert metrics["halted_cycles"] == 2
    assert metrics["authorized_cycles"] == 0
    assert metrics["is_safety_freeze"] is True
    assert metrics["regimes"]["RANGE"] == 1
    assert metrics["regimes"]["TREND_UP"] == 1
    assert metrics["cycle_reasons"]["Phase 1 Halt: PRE_MARKET"] == 1
    assert metrics["cycle_reasons"]["Phase 2 Halt: Intraday Spike Freeze active"] == 1


def test_campaign_accounting_independent_tracking():
    """
    Verify that safety freeze sessions count as capture-valid observed sessions,
    but NOT economic-validation sessions.
    """
    progress = _get_campaign_progress("2026-09-04", "🟡 HALTED — SAFETY FREEZE ACTIVE")
    assert progress["observed"] >= 1
    assert progress["capture_valid"] >= 1
    assert progress["economic_valid"] == 0
    assert progress["valid"] == 0
    assert progress["required"] == 20
    assert progress["remaining"] == 20


def test_live_2026_09_04_execution_metrics():
    """Verify live metrics file parsing for 2026-09-04."""
    live_metrics_path = WORKSPACE / "data" / "execution_metrics.jsonl"
    if not live_metrics_path.exists():
        pytest.skip("Live execution metrics not found")

    metrics = _load_execution_metrics("2026-09-04")
    assert metrics["has_data"] is True
    assert metrics["evaluation_cycles"] == 17219
    assert metrics["halted_cycles"] == 17219
    assert metrics["authorized_cycles"] == 0
    assert metrics["is_safety_freeze"] is True
    assert "Phase 2 Halt: Intraday Spike Freeze active" in metrics["cycle_reasons"]
    assert metrics["cycle_reasons"]["Phase 2 Halt: Intraday Spike Freeze active"] == 17131
    assert metrics["cycle_reasons"]["Phase 1 Halt: Bad time to trade: PRE_MARKET"] == 88
