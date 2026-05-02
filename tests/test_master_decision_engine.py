"""
P2-E: Master Decision Engine Test Suite
==========================================
Tests the type-safe ApprovalResult contract (P1-A)
and gate behavior.
"""

import pytest
from core.master_decision_engine import ApprovalResult


class TestApprovalResult:
    """P1-A: ApprovalResult must enforce .approved usage."""

    def test_raises_on_bool_usage(self):
        """ApprovalResult must not be usable as a bool."""
        result = ApprovalResult(approved=False, reason="test")
        with pytest.raises(TypeError, match="cannot be used directly as bool"):
            if result:
                pass

    def test_raises_on_not_bool_usage(self):
        """'if not result' must also raise TypeError."""
        result = ApprovalResult(approved=True, reason="test")
        with pytest.raises(TypeError):
            if not result:
                pass

    def test_approved_true_accessible(self):
        """result.approved must be directly accessible."""
        result = ApprovalResult(approved=True, reason="All gates passed")
        assert result.approved is True
        assert result.reason == "All gates passed"

    def test_approved_false_accessible(self):
        """result.approved=False must be accessible."""
        result = ApprovalResult(
            approved=False,
            reason="Low confidence",
            gates_failed=["G0_PROBABILITY"]
        )
        assert result.approved is False
        assert result.gate_failed == "G0_PROBABILITY"

    def test_gate_failed_returns_none_on_success(self):
        """gate_failed property returns None when no gates failed."""
        result = ApprovalResult(approved=True, reason="ok")
        assert result.gate_failed is None

    def test_gate_failed_returns_first_failed_gate(self):
        """gate_failed returns the first failed gate name."""
        result = ApprovalResult(
            approved=False,
            reason="blocked",
            gates_failed=["G3_RISK_CORE", "G5_DAILY_TARGET"]
        )
        assert result.gate_failed == "G3_RISK_CORE"

    def test_str_representation_approved(self):
        """String representation for approved result."""
        result = ApprovalResult(approved=True, reason="All gates passed")
        s = str(result)
        assert "APPROVED" in s
        assert "✅" in s

    def test_str_representation_blocked(self):
        """String representation for blocked result."""
        result = ApprovalResult(approved=False, reason="Risk limit hit")
        s = str(result)
        assert "BLOCKED" in s
        assert "❌" in s
