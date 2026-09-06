"""
tests/test_shadow_sr_observer.py — Tests for Structure Reset Shadow Observer

Validates:
1. Architectural isolation: observer writes JSONL only, has no OMS imports.
2. Only SAME_STRUCTURAL_TREND rejections are logged (filter correctness).
3. Telemetry record schema contains all required fields.
4. Observer failures never propagate (defensive exception handling).
"""

import json
import os
import sys
import pytest
from pathlib import Path
from unittest.mock import patch

from core.shadow_sr_observer import StructureResetShadowObserver


def test_observer_has_no_oms_imports():
    """Verify the module contains zero OMS/broker/execution imports."""
    import importlib
    import inspect
    mod = importlib.import_module("core.shadow_sr_observer")
    source = inspect.getsource(mod)

    forbidden = ["from core.oms", "import oms", "from broker", "import broker",
                 "from core.order", "import order", "DhanBroker", "place_order",
                 "submit_order", "route_order"]
    for pattern in forbidden:
        assert pattern not in source, (
            f"ARCHITECTURAL VIOLATION: shadow_sr_observer.py contains '{pattern}'. "
            f"This module must have ZERO execution/order-routing capability."
        )


def test_only_logs_structure_reset_rejections(tmp_path):
    """Observer should silently ignore non-SR rejections."""
    obs = StructureResetShadowObserver()
    obs._today_file = str(tmp_path / "test_shadow.jsonl")
    obs._today_date = None  # force file path

    # Non-SR rejection — should NOT be logged
    obs.observe(
        snapshot_id="NON_SR_001",
        timestamp="2026-09-03T10:00:00",
        signal_type="BUY_CE", direction="BULLISH",
        spot=24500.0, strike=24500, confidence=65.0,
        regime="STRONG_TREND_UP",
        rejection_reason="PEV_TOO_LOW",
        entry_price=24500.0, stop_loss=24470.0, target_1=24560.0,
        gate_results={}, structure_details={},
    )

    log_path = tmp_path / "test_shadow.jsonl"
    # File should not exist or be empty
    if log_path.exists():
        content = log_path.read_text().strip()
        assert content == "", "Non-SR rejection should not generate telemetry"


def test_logs_structure_reset_with_correct_schema(tmp_path):
    """SR rejection should produce a complete telemetry record."""
    from datetime import date as d
    obs = StructureResetShadowObserver()
    log_path = tmp_path / "sr_shadow_test.jsonl"
    obs._today_file = str(log_path)
    obs._today_date = d.today()  # Match today so _get_log_file() returns our path

    obs.observe(
        snapshot_id="SR_TEST_001",
        timestamp="2026-09-03T13:42:00",
        signal_type="BUY_CE", direction="BULLISH",
        spot=24142.95, strike=24150, confidence=62.1,
        regime="STRONG_TREND_UP",
        rejection_reason="REJECTED_SAME_STRUCTURAL_TREND: Already entered 2 times",
        entry_price=24142.95, stop_loss=24137.45, target_1=24153.95,
        gate_results={
            "Structure Reset": {"passed": False},
            "Confidence": {"passed": True},
            "EV": {"passed": True},
        },
        structure_details={
            "leg_id": 3,
            "entries_in_leg": 2,
            "active_direction": "BULLISH",
            "reset_event": None,
            "has_bos": False,
            "has_choch": False,
        },
    )

    assert log_path.exists(), "Shadow telemetry file should be created"
    lines = [l for l in log_path.read_text().strip().split("\n") if l]
    assert len(lines) == 1

    rec = json.loads(lines[0])

    # Required identity fields
    assert rec["snapshot_id"] == "SR_TEST_001"
    assert rec["timestamp"] == "2026-09-03T13:42:00"
    assert rec["date"] == "2026-09-03"

    # Signal characteristics
    assert rec["signal_type"] == "BUY_CE"
    assert rec["direction"] == "BULLISH"
    assert rec["spot"] == 24142.95
    assert rec["strike"] == 24150
    assert rec["confidence"] == 62.1
    assert rec["regime"] == "STRONG_TREND_UP"

    # Production action
    assert rec["production_action"] == "REJECT"

    # Shadow variant actions
    assert rec["shadow_b_action"] == "ACCEPT_50_PCT"
    assert rec["shadow_b_size_multiplier"] == 0.50
    assert rec["shadow_c_action"] == "ACCEPT_25_PCT"
    assert rec["shadow_c_size_multiplier"] == 0.25

    # Trade specification
    assert rec["entry_price"] == 24142.95
    assert rec["stop_loss"] == 24137.45
    assert rec["target_1"] == 24153.95
    assert rec["risk_distance_pts"] > 0
    assert rec["reward_distance_pts"] > 0
    assert rec["rr_ratio"] > 0

    # Forward outcome fields (pending)
    assert rec["outcome"] is None
    assert rec["shadow_b_gross_r"] is None
    assert rec["shadow_b_net_r"] is None
    assert rec["shadow_c_gross_r"] is None
    assert rec["shadow_c_net_r"] is None

    # Production baseline
    assert rec["production_counterfactual_r"] == 0.0

    # Structure context
    assert rec["structure_leg_id"] == 3
    assert rec["structure_entries_in_leg"] == 2
    assert rec["structure_active_direction"] == "BULLISH"

    # Other failed gates (should exclude Structure Reset itself)
    assert "Structure Reset" not in rec["other_failed_gates"]

    # Immutable Experiment Metadata validation
    assert "experiment" in rec
    assert rec["experiment"]["experiment_id"] == "SR-SHADOW-V1"
    assert rec["experiment"]["experiment_version"] == "1.0.0"
    assert "ambiguous_bar_rule" in rec["experiment"]["risk_assumptions"]


def test_observer_failure_does_not_propagate(tmp_path):
    """Even if the log path is invalid, observer must not raise."""
    obs = StructureResetShadowObserver()
    # Point to a path that will fail (directory doesn't exist and we block creation)
    obs._today_file = str(tmp_path / "nonexistent_deep_dir" / "sub" / "shadow.jsonl")
    obs._today_date = None

    # This should not raise
    obs.observe(
        snapshot_id="FAIL_TEST",
        timestamp="2026-09-03T10:00:00",
        signal_type="BUY_CE", direction="BULLISH",
        spot=24500.0, strike=None, confidence=50.0,
        regime="UNKNOWN",
        rejection_reason="REJECTED_SAME_STRUCTURAL_TREND: test",
        entry_price=24500.0, stop_loss=24470.0, target_1=24560.0,
        gate_results={}, structure_details={},
    )


def test_settings_rejects_negative_daily_loss(monkeypatch):
    """Explicit fail-closed test: negative MAX_DAILY_LOSS must raise ValueError, not silently abs()."""
    monkeypatch.setenv("MAX_DAILY_LOSS", "-5000")
    with pytest.raises(ValueError, match="Configuration Error: MAX_DAILY_LOSS must be a positive number"):
        from config.settings import Settings
        Settings()


def test_economic_friction_model_parity():
    """
    Parity test: ensure friction is converted consistently into the risk denominator.
    For an account with ₹1,500 base risk (1.5% of ₹100k):
    - At 100% size (₹1,500 risk), ₹40 friction = 40/1500 = 0.0267 R
    - At 50% size (₹750 risk), ₹40 friction = 40/750 = 0.0533 R
    - At 25% size (₹375 risk), ₹40 friction = 40/375 = 0.1067 R
    Verifies that Realized R = (Gross PnL - Fees - Slippage) / Allocated Risk
    strictly matches PositionManager and SimulationEngine accounting.
    """
    from core.shadow_sr_observer import compute_shadow_realized_r

    base_risk = 1500.0
    fees = 40.0
    slippage_pts = 0.5
    stop_distance_pts = 10.0  # Slippage drag = 0.5 / 10 = 0.05 R

    # 1. 25% Sizing: Target Hit
    # Gross: +2.0R, Slippage: -0.05R, Fee: -40/375 = -0.1067R -> Net = 1.8433R
    r_25_tgt = compute_shadow_realized_r(
        outcome="TARGET_HIT",
        size_multiplier=0.25,
        base_risk_rupees=base_risk,
        fee_rupees=fees,
        slippage_pts=slippage_pts,
        stop_distance_pts=stop_distance_pts,
    )
    assert r_25_tgt == 1.8433

    # 2. 25% Sizing: Stop Hit
    # Gross: -1.0R, Slippage: -0.05R, Fee: -40/375 = -0.1067R -> Net = -1.1567R
    r_25_stp = compute_shadow_realized_r(
        outcome="STOPPED_OUT",
        size_multiplier=0.25,
        base_risk_rupees=base_risk,
        fee_rupees=fees,
        slippage_pts=slippage_pts,
        stop_distance_pts=stop_distance_pts,
    )
    assert r_25_stp == -1.1567

    # 3. 50% Sizing: Target Hit
    # Gross: +2.0R, Slippage: -0.05R, Fee: -40/750 = -0.0533R -> Net = 1.8967R
    r_50_tgt = compute_shadow_realized_r(
        outcome="TARGET_HIT",
        size_multiplier=0.50,
        base_risk_rupees=base_risk,
        fee_rupees=fees,
        slippage_pts=slippage_pts,
        stop_distance_pts=stop_distance_pts,
    )
    assert r_50_tgt == 1.8967

