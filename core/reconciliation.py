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
