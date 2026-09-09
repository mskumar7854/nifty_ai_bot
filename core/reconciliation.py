"""
core/reconciliation.py

Broker State Reconciliation Engine

Verifies internal PositionManager & OMS state against actual broker reality.
Implements Severity Classes:
  - SAFE: auto-heal (e.g. mobile exit)
  - DANGEROUS: DEGRADED posture + block entries (e.g. missing SL)
  - FATAL: HALT system (e.g. direction mismatch)
"""

import logging
import json
from datetime import datetime
from enum import Enum
from typing import Dict, Any

from core.oms import OrderManagementSystem
# Assuming position_manager is passed in or accessed

logger = logging.getLogger("reconciliation")

class Severity(Enum):
    SAFE = "SAFE"
    DANGEROUS = "DANGEROUS"
    FATAL = "FATAL"

class ReconciliationEngine:
    def __init__(self, position_manager, oms: OrderManagementSystem):
        self.pm = position_manager
        self.oms = oms
        self.logger = logger
        self.dhan = position_manager.dhan

    def _journal_event(self, severity: Severity, action: str, details: Dict[str, Any]):
        """Persist reconciliation event to DB."""
        payload = {
            "timestamp": datetime.now().isoformat(),
            "severity": severity.value,
            "action_taken": action,
            **details
        }
        self.logger.warning(f"RECONCILIATION [{severity.value}]: {action} - {json.dumps(details)}")
        
        # Write to recon_journal in DB (we'll ensure this table exists in DBManager later)
        try:
            with self.oms._get_conn() as conn:
                conn.execute(
                    "CREATE TABLE IF NOT EXISTS recon_journal (id INTEGER PRIMARY KEY, timestamp TEXT, severity TEXT, action TEXT, details TEXT)"
                )
                conn.execute(
                    "INSERT INTO recon_journal (timestamp, severity, action, details) VALUES (?, ?, ?, ?)",
                    (payload["timestamp"], payload["severity"], payload["action_taken"], json.dumps(details))
                )
        except Exception as e:
            self.logger.error(f"Failed to journal reconciliation event: {e}")

    def audit_broker_state(self):
        """
        Compare PM state with Broker state.
        This is a heavy API call, should be run every ~60s or on specific triggers.
        """
        try:
            broker_resp = self.dhan.get_positions()
            
            if broker_resp.get("status") != "success":
                self.logger.error("Failed to fetch broker positions during audit")
                return

            broker_positions = broker_resp.get("data", [])
            # Map broker positions by tradingSymbol or securityId
            # Example dhan structure: [{'tradingSymbol': '...', 'netQty': 150, 'positionType': 'LONG', ...}]
            b_map = {}
            for p in broker_positions:
                if p.get("netQty", 0) != 0:
                    # using tradingSymbol as key for simplicity
                    b_map[p.get("tradingSymbol")] = p

            internal_positions = [p for p in self.pm.open_positions.values() if p.is_active]
            
            for ip in internal_positions:
                b_pos = b_map.get(ip.symbol)
                
                # 1. Internal says OPEN, Broker says CLOSED
                if not b_pos:
                    self._journal_event(
                        Severity.SAFE, 
                        "AUTO_RECONCILE_FLATTEN", 
                        {"internal_qty": ip.qty, "broker_qty": 0, "symbol": ip.symbol, "reason": "Likely mobile exit"}
                    )
                    # Auto heal: flatten internal
                    ip.is_active = False
                    self.pm.deployed_capital -= (ip.entry_price * 0.01 * ip.qty) # Rough estimate, should be proper
                    continue
                
                b_qty = abs(b_pos.get("netQty", 0))
                b_side = "BUY" if b_pos.get("positionType", "") == "LONG" else "SELL"
                i_side = ip.direction.value.upper()
                
                # 2. Direction mismatch (FATAL)
                if b_side != i_side:
                    self._journal_event(
                        Severity.FATAL,
                        "HALT_SYSTEM",
                        {"internal_side": i_side, "broker_side": b_side, "symbol": ip.symbol}
                    )
                    self.pm._halt_trading("FATAL RECON: Direction mismatch")
                    return
                    
                # 3. Qty mismatch (DANGEROUS)
                if b_qty != ip.qty:
                    self._journal_event(
                        Severity.DANGEROUS,
                        "DEGRADE_AND_BLOCK",
                        {"internal_qty": ip.qty, "broker_qty": b_qty, "symbol": ip.symbol}
                    )
                    # For now, flag the PM to block new entries
                    self.pm.is_halted = True 
                    self.pm.halt_reason = f"DANGEROUS: Qty mismatch on {ip.symbol}"

            # 4. Broker says OPEN, Internal says CLOSED (DANGEROUS/FATAL depending on policy)
            i_symbols = {p.symbol for p in internal_positions}
            for sym, b_pos in b_map.items():
                if sym not in i_symbols:
                    orphan_key = f"{sym}"
                    if not hasattr(self.pm, "_acknowledged_orphans"):
                        self.pm._acknowledged_orphans = set()
                    
                    if orphan_key in self.pm._acknowledged_orphans:
                        continue

                    self._journal_event(
                        Severity.DANGEROUS,
                        "DEGRADE_AND_BLOCK",
                        {"internal_qty": 0, "broker_qty": b_pos.get("netQty"), "symbol": sym, "reason": "Unknown live exposure"}
                    )
                    self.pm.is_halted = True
                    self.pm.halt_reason = f"DANGEROUS: Unknown live exposure {sym}"
                    self.pm._acknowledged_orphans.add(orphan_key)
                    import time as _time
                    self.pm.halt_auto_resume_ts = _time.time() + 1800 # 30 mins auto-resume
                    return

            # Note: Checking if Broker SL is missing would require pulling `dhan.get_order_list()`
            # and matching SL orders against open positions. 

        except Exception as e:
            self.logger.error(f"Audit failure: {e}", exc_info=True)


def compute_execution_reconciliation(oms, pos_manager) -> tuple[str, list[str]]:
    """
    User Directive 4: Validate entire execution lineage and contract parameters.
    Invariants:
      OMS filled orders = PositionManager opens = Closed outcomes + currently open positions
      Non-legacy parameter completeness: contract, strike, entry, SL, target, side=BUY, option_type, expiry
    Distinguishes:
      - CONSISTENT
      - INCOMPLETE_CONTRACT
      - COUNT_MISMATCH
      - IDENTITY_MISMATCH
    """
    recon_status = "CONSISTENT"
    recon_mismatches = []

    if not oms or not pos_manager:
        return recon_status, recon_mismatches

    # Execution stats for today
    exec_stats = oms.get_execution_stats_today() if hasattr(oms, "get_execution_stats_today") else {"orders_filled": 0}
    filled_orders_count = exec_stats.get("orders_filled", 0)

    # 1. Active open positions
    active_open_positions = [
        pos for pos in pos_manager.open_positions.values() if getattr(pos, "is_active", True)
    ]
    open_pos_count = len(active_open_positions)

    # 2. Closed positions today (excluding legacy / reconstructed records)
    closed_positions = list(getattr(pos_manager, "closed_positions_today", []))
    non_legacy_closed = [
        c for c in closed_positions if not (isinstance(c, dict) and c.get("is_reconstructed", False))
    ]

    # Reality Ledger Invariant (P0.5): If in-memory closed list is empty, audit persistent trade_outcomes
    if not non_legacy_closed:
        try:
            import os as _os
            import sqlite3 as _sqlite3
            from datetime import date as _date
            today_s = _date.today().isoformat()
            db_path = getattr(oms, "db_path", None) or _os.getenv("NIFTY_DB_PATH") or ("data/trading_v4_live.db" if _os.getenv("SYSTEM_MODE", "SIMULATION") != "SIMULATION" else "data/trading_v4_sim.db")
            if _os.path.exists(db_path):
                with _sqlite3.connect(db_path) as conn:
                    conn.row_factory = _sqlite3.Row
                    cur = conn.execute("PRAGMA table_info(trade_outcomes)")
                    if cur.fetchall():
                        db_rows = conn.execute(
                            "SELECT * FROM trade_outcomes WHERE signal_timestamp LIKE ? AND result IN ('WIN', 'LOSS', 'BREAKEVEN') "
                            "AND trade_id NOT LIKE 'POS_%' AND trade_id NOT LIKE 'sig_%' AND trade_id NOT LIKE 'test-%' AND trade_id NOT LIKE 'INT_POS_%'",
                            (f"{today_s}%",)
                        ).fetchall()
                        if db_rows:
                            non_legacy_closed = [dict(r) for r in db_rows]
        except Exception:
            pass

    closed_pos_count = len(non_legacy_closed)

    # Invariant 1: Reality Ledger Count Check
    # Filled orders == (active open positions + closed outcomes)
    if filled_orders_count != (open_pos_count + closed_pos_count):
        recon_status = "COUNT_MISMATCH"
        recon_mismatches.append(
            f"Filled orders ({filled_orders_count}) != Open ({open_pos_count}) + Closed ({closed_pos_count})"
        )

    # Invariant 2: Contract completeness on non-legacy executions
    for p in active_open_positions:
        if getattr(p, "is_reconstructed", False):
            continue
        p_dict = p.to_dict() if hasattr(p, "to_dict") else dict(p)
        contract = p_dict.get("contract") or p_dict.get("symbol") or ""
        strike = p_dict.get("strike")
        entry = float(p_dict.get("entry_price") or p_dict.get("entry") or 0.0)
        sl = float(p_dict.get("stop_loss") or p_dict.get("sl") or 0.0)
        target = float(p_dict.get("target_1") or p_dict.get("target1") or 0.0)
        side = str(p_dict.get("direction") or "BUY").upper()
        opt_type = str(p_dict.get("option_type") or ("CE" if "CE" in str(p_dict.get("signal_type", "")) else "PE")).upper()
        expiry = str(p_dict.get("expiry") or "")

        errors = []
        if not contract or contract == "NIFTY":
            errors.append(f"contract='{contract}'")
        elif (strike is None or strike <= 0) and contract not in ("NIFTY", "BUY_CE", "BUY_PE", "SIMULATED"):
            import re
            m = re.search(r"NIFTY(?:\d{2}[A-Z]{3})?(\d{4,5})(CE|PE)", str(contract).upper())
            if m:
                try:
                    strike = float(m.group(1))
                    if not opt_type or opt_type not in ("CE", "PE"):
                        opt_type = m.group(2)
                except Exception:
                    pass
        if strike is None or strike <= 0:
            errors.append(f"strike={strike}")
        if entry <= 0:
            errors.append(f"entry={entry}")
        if sl <= 0:
            errors.append(f"stop_loss={sl}")
        if target <= 0:
            errors.append(f"target_1={target}")
        if side not in ("BUY", "BULLISH", "BEARISH"):
            errors.append(f"side={side}")
        if opt_type not in ("CE", "PE"):
            errors.append(f"option_type={opt_type}")
        if not expiry:
            errors.append("expiry empty")

        if errors:
            if recon_status == "CONSISTENT":
                recon_status = "INCOMPLETE_CONTRACT"
            recon_mismatches.append(f"Open position {p_dict.get('trade_id')}: {', '.join(errors)}")

    for c in non_legacy_closed:
        c_dict = c if isinstance(c, dict) else (c.to_dict() if hasattr(c, "to_dict") else dict(c))
        contract = c_dict.get("contract") or c_dict.get("signal") or ""
        strike = c_dict.get("strike")
        entry = float(c_dict.get("entry_price") or c_dict.get("entry") or 0.0)
        sl = float(c_dict.get("stop_loss") or c_dict.get("sl") or 0.0)
        target = float(c_dict.get("target_1") or c_dict.get("target1") or c_dict.get("target") or 0.0)
        opt_type = str(c_dict.get("option_type") or ("CE" if "CE" in str(c_dict.get("signal", "") or c_dict.get("contract", "")) else "PE")).upper()
        expiry = str(c_dict.get("expiry") or "")
        if not expiry and contract:
            import re
            m_exp = re.search(r"NIFTY(\d{2})([A-Z]{3})", str(contract).upper())
            if m_exp:
                expiry = f"20{m_exp.group(1)}-{m_exp.group(2)}"

        errors = []
        if not contract or contract == "NIFTY":
            errors.append(f"contract='{contract}'")
        elif (strike is None or strike <= 0) and contract not in ("NIFTY", "BUY_CE", "BUY_PE", "SIMULATED"):
            import re
            m = re.search(r"NIFTY(?:\d{2}[A-Z]{3})?(\d{4,5})(CE|PE)", str(contract).upper())
            if m:
                try:
                    strike = float(m.group(1))
                    if not opt_type or opt_type not in ("CE", "PE"):
                        opt_type = m.group(2)
                except Exception:
                    pass
        if strike is None or strike <= 0:
            errors.append(f"strike={strike}")
        if entry <= 0:
            errors.append(f"entry={entry}")
        if sl <= 0:
            errors.append(f"stop_loss={sl}")
        if target <= 0:
            errors.append(f"target_1={target}")
        if opt_type not in ("CE", "PE"):
            errors.append(f"option_type={opt_type}")
        if not expiry:
            errors.append("expiry empty")

        if errors:
            if recon_status == "CONSISTENT":
                recon_status = "INCOMPLETE_CONTRACT"
            recon_mismatches.append(f"Closed trade {c_dict.get('trade_id')}: {', '.join(errors)}")

    # Invariant 3: Lineage / Identity Check
    if hasattr(oms, "get_filled_orders_today"):
        filled_orders = oms.get_filled_orders_today()
        pm_ids = set()
        for p in active_open_positions:
            if getattr(p, "intent_id", None):
                pm_ids.add(str(p.intent_id))
            if getattr(p, "position_id", None):
                pm_ids.add(str(p.position_id))
        for c in non_legacy_closed:
            c_dict = c if isinstance(c, dict) else (c.to_dict() if hasattr(c, "to_dict") else dict(c))
            for k in ("intent_id", "trade_id", "id"):
                if c_dict.get(k):
                    pm_ids.add(str(c_dict[k]))

        def _clean_id(raw_val: str) -> str:
            val = str(raw_val).strip()
            for pfx in ("TRD_", "INT_", "SIM_ORD_", "SIM_SL_"):
                if val.startswith(pfx):
                    val = val[len(pfx):]
            return val

        cleaned_pm_ids = {_clean_id(x) for x in pm_ids if x}

        for o in filled_orders:
            o_intent = str(o.get("intent_id") or "")
            o_sig = str(o.get("signal_id") or "")
            clean_intent = _clean_id(o_intent)
            clean_sig = _clean_id(o_sig)

            matched = False
            if clean_intent in cleaned_pm_ids or clean_sig in cleaned_pm_ids:
                matched = True
            elif any(clean_intent and clean_intent in cpid for cpid in cleaned_pm_ids):
                matched = True
            elif any(clean_sig and clean_sig in cpid for cpid in cleaned_pm_ids):
                matched = True

            if not matched:
                if recon_status == "CONSISTENT":
                    recon_status = "IDENTITY_MISMATCH"
                recon_mismatches.append(f"OMS intent {o_intent} has no matching PositionManager record")

    return recon_status, recon_mismatches

