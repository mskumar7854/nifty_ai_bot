"""
tests/test_state_recovery_flow.py — End-to-End State Machine Recovery & Persistence

Validates:
1. Invariants:
   - HALTED: is_trading_allowed() is False
   - RECONCILIATION_REQUIRED: is_trading_allowed() is False
   - RESET_AUTHORIZED: is_trading_allowed() is False
   - ACTIVE: is_trading_allowed() is True
2. Illegal transition enforcement (cannot jump directly from HALTED to ACTIVE).
3. 3-step operator recovery workflow produces 3 distinct audit records with operator_id and rationale.
4. Process restart persistence:
   - Starts ACTIVE in process 1
   - Halts in process 1
   - Process 2 boots from disk and loads HALTED
   - Process 3 executes operator reset to ACTIVE
   - Process 4 boots from disk and loads ACTIVE
"""

import os
import json
import subprocess
import sys
import pytest
from core.system_state import TradingStateManager, get_state_manager

def test_trading_allowed_invariants(tmp_path):
    """Ensure that only ACTIVE permits trading; all intermediate/halted states block order routing."""
    state_file = str(tmp_path / "system_state_inv.json")
    mgr = TradingStateManager.reset_instance(state_file=state_file)

    # 1. ACTIVE -> allowed
    mgr.set_state("ACTIVE", "Initial")
    assert mgr.is_trading_allowed() is True

    # 2. HALTED -> blocked
    mgr.trigger_structural_halt("Circuit trip")
    assert mgr.get_state() == "HALTED"
    assert mgr.is_trading_allowed() is False

    # 3. RECONCILIATION_REQUIRED -> blocked
    mgr.operator_initiate_reconciliation("Op1", "Reconciling broker")
    assert mgr.get_state() == "RECONCILIATION_REQUIRED"
    assert mgr.is_trading_allowed() is False

    # 4. RESET_AUTHORIZED -> blocked
    mgr.operator_authorize_reset("Op1", "Reconciliation passed")
    assert mgr.get_state() == "RESET_AUTHORIZED"
    assert mgr.is_trading_allowed() is False

    # 5. ACTIVE -> allowed
    mgr.operator_complete_reset("Op1", "Armed to active")
    assert mgr.get_state() == "ACTIVE"
    assert mgr.is_trading_allowed() is True

def test_recovery_cannot_skip_states(tmp_path):
    """Ensure state machine transition matrix rejects skipping recovery phases."""
    state_file = str(tmp_path / "system_state_noskip.json")
    mgr = TradingStateManager.reset_instance(state_file=state_file)
    mgr.trigger_structural_halt("Trip")
    assert mgr.get_state() == "HALTED"

    # Direct jump HALTED -> ACTIVE must fail
    with pytest.raises(ValueError, match="ILLEGAL STATE TRANSITION ATTEMPT"):
        mgr.set_state("ACTIVE", "Attempt bypass")

    # Direct jump HALTED -> RESET_AUTHORIZED must fail
    with pytest.raises(ValueError, match="ILLEGAL STATE TRANSITION ATTEMPT"):
        mgr.set_state("RESET_AUTHORIZED", "Attempt bypass")

    # Direct completion before authorization must fail
    with pytest.raises(ValueError, match="Cannot complete reset"):
        mgr.operator_complete_reset("Op1", "Bypass")

def test_operator_reset_produces_three_auditable_transitions(tmp_path):
    """Convenience method operator_reconcile_and_reset must write 3 distinct JSONL audit records."""
    state_file = str(tmp_path / "system_state_audit.json")
    audit_file = str(tmp_path / "state_transitions_audit.jsonl")
    
    os.environ["NIFTY_AUDIT_FILE"] = audit_file
    mgr = TradingStateManager.reset_instance(state_file=state_file)
    mgr.trigger_structural_halt("Initial fault")
    assert mgr.get_state() == "HALTED"

    mgr.operator_reconcile_and_reset(operator_id="RiskLead_01", reason="Full reconciliation verified clean")
    assert mgr.get_state() == "ACTIVE"

    # Read audit log records
    assert os.path.exists(audit_file)
    with open(audit_file, "r") as f:
        records = [json.loads(line) for line in f if line.strip()]

    # Filter operator recovery records
    recovery_records = [
        r for r in records
        if r.get("operator_id") == "RiskLead_01" and r.get("event_type") == "OPERATOR_ACTION"
    ]
    assert len(recovery_records) == 3, f"Expected 3 operator transition records, found {len(recovery_records)}"

    # Record 1: HALTED -> RECONCILIATION_REQUIRED
    assert recovery_records[0]["from_state"] == "HALTED"
    assert recovery_records[0]["to_state"] == "RECONCILIATION_REQUIRED"
    assert recovery_records[0]["event"] == "operator_reconciliation"
    assert "RiskLead_01" in recovery_records[0]["operator_id"]

    # Record 2: RECONCILIATION_REQUIRED -> RESET_AUTHORIZED
    assert recovery_records[1]["from_state"] == "RECONCILIATION_REQUIRED"
    assert recovery_records[1]["to_state"] == "RESET_AUTHORIZED"
    assert recovery_records[1]["event"] == "operator_authorization"

    # Record 3: RESET_AUTHORIZED -> ACTIVE
    assert recovery_records[2]["from_state"] == "RESET_AUTHORIZED"
    assert recovery_records[2]["to_state"] == "ACTIVE"
    assert recovery_records[2]["event"] == "operator_activation"

def test_cross_process_halt_and_recovery(tmp_path):
    """
    Subprocess integration test:
    Process 1: Starts ACTIVE, triggers HALT, persists to disk.
    Process 2 (fresh boot): Reads disk, confirms HALTED.
    Process 3: Executes tools.state_admin reset.
    Process 4 (fresh boot): Reads disk, confirms ACTIVE.
    """
    state_file = str(tmp_path / "proc_state.json")
    audit_file = str(tmp_path / "proc_transitions.jsonl")

    # --- Process 1: Boot ACTIVE and trip HALT ---
    cmd_p1 = [
        sys.executable, "-c",
        f"""
import os
os.environ['NIFTY_SYSTEM_STATE_FILE'] = r'{state_file}'
os.environ['NIFTY_AUDIT_FILE'] = r'{audit_file}'
from core.system_state import TradingStateManager
mgr = TradingStateManager(state_file=r'{state_file}')
mgr.set_state('ACTIVE', 'Process 1 boot')
mgr.trigger_structural_halt('Intentional breaker trip in P1')
assert mgr.get_state() == 'HALTED'
        """
    ]
    p1 = subprocess.run(cmd_p1, capture_output=True, text=True)
    assert p1.returncode == 0, f"P1 failed: {p1.stderr}"

    # --- Process 2: Fresh process loads state from disk ---
    cmd_p2 = [
        sys.executable, "-c",
        f"""
import os
os.environ['NIFTY_SYSTEM_STATE_FILE'] = r'{state_file}'
os.environ['NIFTY_AUDIT_FILE'] = r'{audit_file}'
from core.system_state import TradingStateManager
mgr = TradingStateManager(state_file=r'{state_file}')
assert mgr.get_state() == 'HALTED', f'Expected HALTED on restart, got {{mgr.get_state()}}'
assert mgr.is_trading_allowed() is False
        """
    ]
    p2 = subprocess.run(cmd_p2, capture_output=True, text=True)
    assert p2.returncode == 0, f"P2 failed: {p2.stderr}"

    # --- Process 3: Execute state_admin CLI reset ---
    cmd_p3 = [
        sys.executable, "-m", "tools.state_admin",
        "--state-file", state_file,
        "reset",
        "--operator", "ChiefRiskOfficer",
        "--reason", "Post-incident review complete; risk exposure verified flat"
    ]
    p3 = subprocess.run(cmd_p3, capture_output=True, text=True)
    assert p3.returncode == 0, f"P3 state_admin reset failed: {p3.stderr}"

    # --- Process 4: Fresh process boots and confirms ACTIVE ---
    cmd_p4 = [
        sys.executable, "-c",
        f"""
import os
os.environ['NIFTY_SYSTEM_STATE_FILE'] = r'{state_file}'
os.environ['NIFTY_AUDIT_FILE'] = r'{audit_file}'
from core.system_state import TradingStateManager
mgr = TradingStateManager(state_file=r'{state_file}')
assert mgr.get_state() == 'ACTIVE', f'Expected ACTIVE after reset, got {{mgr.get_state()}}'
assert mgr.is_trading_allowed() is True
        """
    ]
    p4 = subprocess.run(cmd_p4, capture_output=True, text=True)
    assert p4.returncode == 0, f"P4 failed: {p4.stderr}"
