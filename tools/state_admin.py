#!/usr/bin/env python3
"""
tools/state_admin.py — System State Operator Administration CLI

Provides explicit, auditable operator controls for managing system state,
inspecting transitions, and executing the 3-step circuit-breaker recovery workflow:
    HALTED ➔ RECONCILIATION_REQUIRED ➔ RESET_AUTHORIZED ➔ ACTIVE
"""

import sys
import os
import argparse
import json
from pathlib import Path

# Ensure repo root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from core.system_state import TradingStateManager, get_state_manager

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

def cmd_status(args):
    mgr = get_state_manager(state_file=args.state_file)
    print(f"\n{'='*45}")
    print(f"  SYSTEM TRADING STATE")
    print(f"{'='*45}")
    print(f"State File        : {mgr.state_file}")
    print(f"Current State     : {mgr.get_state()}")
    print(f"Trading Allowed   : {'✅ YES' if mgr.is_trading_allowed() else '❌ NO'}")
    print(f"Current Reason    : {mgr.reason}")
    print(f"{'='*45}\n")

    # Show recent audit log transitions
    audit_file = os.environ.get("NIFTY_AUDIT_FILE") or (
        os.path.join("data", "state_transitions_test.jsonl")
        if "test" in mgr.state_file
        else os.path.join("data", "state_transitions.jsonl")
    )
    if os.path.exists(audit_file):
        print(f"Recent State Transitions ({audit_file}):")
        with open(audit_file, "r") as f:
            lines = [line.strip() for line in f if line.strip()]
            for line in lines[-5:]:
                try:
                    rec = json.loads(line)
                    ts = rec.get("datetime") or rec.get("timestamp") or str(rec.get("ts", ""))
                    op = rec.get("operator_id", "system")
                    print(f"  [{ts}] {rec.get('from_state', rec.get('from'))} ➔ {rec.get('to_state', rec.get('to'))} | op={op} | {rec.get('reason')}")
                except Exception:
                    print(f"  {line}")
        print()
    else:
        print("No audit transitions file found on disk yet.\n")

def cmd_halt(args):
    mgr = get_state_manager(state_file=args.state_file)
    operator = args.operator or os.environ.get("OPERATOR_NAME") or "manual_operator"
    reason = args.reason or "Operator manual halt"
    mgr.set_state(
        "HALTED",
        reason=reason,
        source="operator",
        operator_id=operator,
        event="operator_halt"
    )
    print(f"✅ System transitioned to HALTED by operator '{operator}'. Reason: {reason}")

def cmd_reconcile(args):
    mgr = get_state_manager(state_file=args.state_file)
    operator = args.operator or os.environ.get("OPERATOR_NAME") or "manual_operator"
    reason = args.reason or "Broker exposure verified and reconciled"
    try:
        mgr.operator_initiate_reconciliation(operator_id=operator, reason=reason)
        print(f"✅ Step 1/3 Complete: State is now RECONCILIATION_REQUIRED by '{operator}'.")
    except ValueError as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)

def cmd_authorize(args):
    mgr = get_state_manager(state_file=args.state_file)
    operator = args.operator or os.environ.get("OPERATOR_NAME") or "manual_operator"
    reason = args.reason or "Reset authorized post-reconciliation"
    try:
        mgr.operator_authorize_reset(operator_id=operator, reason=reason)
        print(f"✅ Step 2/3 Complete: State is now RESET_AUTHORIZED by '{operator}'.")
    except ValueError as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)

def cmd_arm(args):
    mgr = get_state_manager(state_file=args.state_file)
    operator = args.operator or os.environ.get("OPERATOR_NAME") or "manual_operator"
    reason = args.reason or "System armed to ACTIVE state"
    try:
        mgr.operator_complete_reset(operator_id=operator, reason=reason)
        print(f"✅ Step 3/3 Complete: System is now ACTIVE and trading is re-enabled by '{operator}'.")
    except ValueError as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)

def cmd_reset(args):
    mgr = get_state_manager(state_file=args.state_file)
    operator = args.operator or os.environ.get("OPERATOR_NAME") or "manual_operator"
    reason = args.reason or "Operator verified broker reconciliation and authorized reset"
    try:
        mgr.operator_reconcile_and_reset(operator_id=operator, reason=reason)
        print(f"✅ 3-Step Recovery Workflow Executed Successfully by '{operator}':")
        print(f"   1. HALTED ➔ RECONCILIATION_REQUIRED")
        print(f"   2. RECONCILIATION_REQUIRED ➔ RESET_AUTHORIZED")
        print(f"   3. RESET_AUTHORIZED ➔ ACTIVE")
        print(f"Current State: {mgr.get_state()} (Trading Allowed: {mgr.is_trading_allowed()})")
    except ValueError as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="System State Operator Administration CLI")
    parser.add_argument("--state-file", default=None, help="Explicit path to system_state.json")
    subparsers = parser.add_subparsers(dest="command", help="Sub-commands")

    # status
    p_status = subparsers.add_parser("status", help="Show current state and recent transitions")
    p_status.set_defaults(func=cmd_status)

    # halt
    p_halt = subparsers.add_parser("halt", help="Halt the trading system")
    p_halt.add_argument("--operator", required=False, default="operator", help="Operator ID/Name")
    p_halt.add_argument("--reason", required=True, help="Reason for halting")
    p_halt.set_defaults(func=cmd_halt)

    # reconcile (step 1)
    p_rec = subparsers.add_parser("reconcile", help="Step 1: Initiate reconciliation (HALTED -> RECONCILIATION_REQUIRED)")
    p_rec.add_argument("--operator", required=False, default="operator", help="Operator ID/Name")
    p_rec.add_argument("--reason", required=True, help="Reconciliation evidence/details")
    p_rec.set_defaults(func=cmd_reconcile)

    # authorize (step 2)
    p_auth = subparsers.add_parser("authorize", help="Step 2: Authorize reset (RECONCILIATION_REQUIRED -> RESET_AUTHORIZED)")
    p_auth.add_argument("--operator", required=False, default="operator", help="Operator ID/Name")
    p_auth.add_argument("--reason", required=True, help="Authorization details")
    p_auth.set_defaults(func=cmd_authorize)

    # arm (step 3)
    p_arm = subparsers.add_parser("arm", help="Step 3: Arm trading (RESET_AUTHORIZED -> ACTIVE)")
    p_arm.add_argument("--operator", required=False, default="operator", help="Operator ID/Name")
    p_arm.add_argument("--reason", required=False, default="Arming system to ACTIVE", help="Activation details")
    p_arm.set_defaults(func=cmd_arm)

    # reset (convenience 3-step sequence)
    p_reset = subparsers.add_parser("reset", help="Execute full 3-step recovery (HALTED -> RECONCILIATION_REQUIRED -> RESET_AUTHORIZED -> ACTIVE)")
    p_reset.add_argument("--operator", required=True, help="Operator ID/Name executing reset")
    p_reset.add_argument("--reason", required=True, help="Auditable justification for reset")
    p_reset.set_defaults(func=cmd_reset)

    args = parser.parse_args()
    if not hasattr(args, "func"):
        parser.print_help()
        sys.exit(0)
    args.func(args)

if __name__ == "__main__":
    main()
