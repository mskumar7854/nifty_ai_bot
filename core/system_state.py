import os
import json
import logging
import time
from datetime import datetime
from typing import Optional, Callable

logger = logging.getLogger("system.state")

class TradingStateManager:
    _instance = None

    ALLOWED_TRANSITIONS = {
        "ACTIVE": ["PAUSED_MANUAL", "PAUSED_FINANCIAL", "PAUSED_STRUCTURAL", "HALTED"],
        "PAUSED_MANUAL": ["ACTIVE", "HALTED"],
        "PAUSED_FINANCIAL": ["ACTIVE", "HALTED"],
        "PAUSED_STRUCTURAL": ["ACTIVE", "HALTED"],
        "HALTED": ["RECONCILIATION_REQUIRED"],
        "RECONCILIATION_REQUIRED": ["RESET_AUTHORIZED", "HALTED"],
        "RESET_AUTHORIZED": ["ACTIVE", "HALTED"],
    }

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(TradingStateManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, state_file: Optional[str] = None):
        if self._initialized:
            if state_file and state_file != self.state_file:
                self.state_file = state_file
                self.load_state()
            return
        
        env_state_file = os.environ.get("NIFTY_SYSTEM_STATE_FILE")
        self.state_file = state_file or env_state_file or os.path.join("data", "system_state.json")
        self.state = "ACTIVE"
        self.reason = "Initial startup state"
        self.alert_callback: Optional[Callable[[str], None]] = None
        self._initialized = True
        self.load_state()

        # Log initial startup transition
        self.log_transition("NONE", self.state, f"Startup loaded: {self.reason}")

    @classmethod
    def reset_instance(cls, state_file: Optional[str] = None):
        """Helper to safely isolate test instances without contaminating production state."""
        cls._instance = None
        if state_file is not None:
            return cls(state_file=state_file)
        return None

    def load_state(self):
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, "r") as f:
                    data = json.load(f)
                    saved_state = data.get("state", "ACTIVE")
                    saved_reason = data.get("reason", "")
                    
                    if saved_state in ["HALTED", "PAUSED_STRUCTURAL", "PAUSED_MANUAL", "RECONCILIATION_REQUIRED", "RESET_AUTHORIZED"]:
                        self.state = saved_state
                        self.reason = saved_reason
                        logger.warning(f"🔒 Persistent state loaded from storage: {self.state} | Reason: {self.reason}")
                    elif saved_state == "ACTIVE":
                        self.state = "ACTIVE"
                        self.reason = saved_reason or "System ACTIVE"
                    else:
                        self.state = "ACTIVE"
                        self.reason = f"Cleared temporary state ({saved_state}) on startup"
                        self.save_state()
            except Exception as e:
                logger.error(f"Failed to load system state: {e}. Defaulting to ACTIVE.")
                self.state = "ACTIVE"
        else:
            self.state = "ACTIVE"
            self.save_state()

    def save_state(self):
        os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
        try:
            with open(self.state_file, "w") as f:
                json.dump({
                    "state": self.state,
                    "reason": self.reason,
                    "timestamp": datetime.now().isoformat()
                }, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save system state: {e}")

    def register_alert_callback(self, callback: Callable[[str], None]):
        self.alert_callback = callback

    def send_alert(self, message: str):
        if self.alert_callback:
            try:
                self.alert_callback(message)
            except Exception as e:
                logger.error(f"Failed to dispatch state change alert: {e}")

    def get_state(self) -> str:
        return self.state

    def set_state(
        self,
        state: str,
        reason: str = "",
        signal_id: str = "N/A",
        source: str = "system",
        operator_id: Optional[str] = None,
        event: Optional[str] = None,
    ):
        valid_states = [
            "ACTIVE",
            "PAUSED_STRUCTURAL",
            "PAUSED_FINANCIAL",
            "PAUSED_MANUAL",
            "HALTED",
            "RECONCILIATION_REQUIRED",
            "RESET_AUTHORIZED",
        ]
        if state not in valid_states:
            raise ValueError(f"Invalid state: {state}")
        
        old_state = self.state
        allowed = self.ALLOWED_TRANSITIONS.get(old_state, [])
        if state != old_state and state not in allowed:
            err_msg = f"❌ ILLEGAL STATE TRANSITION ATTEMPT: {old_state} ➔ {state} (Blocked by Transition Matrix)"
            logger.error(err_msg)
            self.send_alert(err_msg)
            if old_state != "HALTED":
                self.state = "HALTED"
                self.reason = f"Security Violation: Illegal state transition attempt ({old_state} ➔ {state})"
                self.save_state()
                self.log_transition(
                    old_state, "HALTED", self.reason, signal_id,
                    event_type="SYSTEM_TRANSITION", source="system",
                    event="illegal_transition_breach"
                )
            raise ValueError(err_msg)
            
        self.state = state
        self.reason = reason
        self.save_state()
        logger.info(f"🔄 System state transitioned to: {self.state} | Reason: {self.reason}")
        
        event_type = "OPERATOR_ACTION" if source in ("operator", "telegram") or "manual" in reason.lower() or "resume" in reason.lower() else "SYSTEM_TRANSITION"
        self.log_transition(
            old_state, self.state, self.reason, signal_id,
            event_type=event_type, source=source,
            operator_id=operator_id, event=event
        )

    def log_transition(
        self,
        from_state: str,
        to_state: str,
        reason: str,
        signal_id: str = "N/A",
        event_type: str = "SYSTEM_TRANSITION",
        source: str = "system",
        operator_id: Optional[str] = None,
        event: Optional[str] = None,
    ):
        transition_record = {
            "schema_version": "1.0",
            "event_type": event_type,
            "event": event or ("operator_action" if source in ("operator", "telegram") else "system_transition"),
            "source": source,
            "operator_id": operator_id or ("system" if source == "system" else "unknown"),
            "from_state": from_state,
            "to_state": to_state,
            "from": from_state,
            "to": to_state,
            "reason": reason,
            "signal_id": signal_id,
            "ts": time.time(),
            "timestamp": datetime.now().isoformat(),
            "datetime": datetime.now().isoformat()
        }
        env_audit_file = os.environ.get("NIFTY_AUDIT_FILE")
        if env_audit_file:
            audit_file = env_audit_file
        elif "system_state_test" in self.state_file:
            audit_file = os.path.join("data", "state_transitions_test.jsonl")
        else:
            audit_file = os.path.join("data", "state_transitions.jsonl")
        os.makedirs(os.path.dirname(audit_file), exist_ok=True)
        try:
            with open(audit_file, "a") as f:
                f.write(json.dumps(transition_record) + "\n")
        except Exception as e:
            logger.error(f"Failed to write state transition audit log: {e}")

    def is_trading_allowed(self) -> bool:
        """Invariants: HALTED, RECONCILIATION_REQUIRED, and RESET_AUTHORIZED block trading. Only ACTIVE permits trading."""
        return self.state == "ACTIVE"

    def trigger_structural_halt(self, reason: str, signal_id: str = "N/A"):
        if self.state == "HALTED":
            return
        self.set_state("HALTED", reason, signal_id=signal_id)
        alert_msg = f"🚨 **CRITICAL STRUCTURAL HALT** 🚨\nReason: {reason}\n\n⚠️ System is locked. Operator reconciliation & authorization required."
        logger.critical(alert_msg)
        self.send_alert(alert_msg)

    def trigger_financial_pause(self, reason: str, signal_id: str = "N/A"):
        if self.state in ["HALTED", "PAUSED_FINANCIAL"]:
            return
        self.set_state("PAUSED_FINANCIAL", reason, signal_id=signal_id)
        alert_msg = f"🛡️ **FINANCIAL PAUSE** 🛡️\nReason: {reason}\n\nSend /resume to re-enable trading."
        logger.warning(alert_msg)
        self.send_alert(alert_msg)

    def trigger_structural_pause(self, reason: str, signal_id: str = "N/A"):
        if self.state in ["HALTED", "PAUSED_STRUCTURAL"]:
            return
        self.set_state("PAUSED_STRUCTURAL", reason, signal_id=signal_id)
        alert_msg = f"🔒 **STRUCTURAL PAUSE** 🔒\nReason: {reason}\n\nPersistent pause activated. Operator intervention required."
        logger.warning(alert_msg)
        self.send_alert(alert_msg)

    # ── 3-STEP OPERATOR RECOVERY WORKFLOW ──
    def operator_initiate_reconciliation(self, operator_id: str, reason: str):
        """Step 1 of 3: Transition from HALTED to RECONCILIATION_REQUIRED."""
        if self.state != "HALTED":
            raise ValueError(f"Cannot initiate reconciliation from state '{self.state}'. System must be in 'HALTED'.")
        self.set_state(
            "RECONCILIATION_REQUIRED",
            reason=reason,
            source="operator",
            operator_id=operator_id,
            event="operator_reconciliation"
        )

    def operator_authorize_reset(self, operator_id: str, reason: str):
        """Step 2 of 3: Transition from RECONCILIATION_REQUIRED to RESET_AUTHORIZED."""
        if self.state != "RECONCILIATION_REQUIRED":
            raise ValueError(f"Cannot authorize reset from state '{self.state}'. System must be in 'RECONCILIATION_REQUIRED'.")
        self.set_state(
            "RESET_AUTHORIZED",
            reason=reason,
            source="operator",
            operator_id=operator_id,
            event="operator_authorization"
        )

    def operator_complete_reset(self, operator_id: str, reason: str):
        """Step 3 of 3: Transition from RESET_AUTHORIZED to ACTIVE (trading re-enabled)."""
        if self.state != "RESET_AUTHORIZED":
            raise ValueError(f"Cannot complete reset from state '{self.state}'. System must be in 'RESET_AUTHORIZED'.")
        self.set_state(
            "ACTIVE",
            reason=reason,
            source="operator",
            operator_id=operator_id,
            event="operator_activation"
        )

    def operator_reconcile_and_reset(self, operator_id: str, reason: str):
        """
        Executes the explicit 3-step operator recovery workflow sequentially.
        Produces 3 distinct auditable transition events in state_transitions.jsonl.
        """
        self.operator_initiate_reconciliation(operator_id, f"Reconciliation started: {reason}")
        self.operator_authorize_reset(operator_id, f"Reset authorized: {reason}")
        self.operator_complete_reset(operator_id, f"System armed ACTIVE: {reason}")

    def force_activate(self, reason: str = "Operator force activation", operator_id: str = "operator"):
        """Emergency recovery that navigates the required state transitions or activates directly."""
        if self.state == "HALTED":
            self.operator_reconcile_and_reset(operator_id, reason)
        elif self.state == "RECONCILIATION_REQUIRED":
            self.operator_authorize_reset(operator_id, reason)
            self.operator_complete_reset(operator_id, reason)
        elif self.state == "RESET_AUTHORIZED":
            self.operator_complete_reset(operator_id, reason)
        else:
            old_state = self.state
            self.state = "ACTIVE"
            self.reason = reason
            self.save_state()
            logger.warning(f"🔓 ACTIVE override triggered: {old_state} ➔ ACTIVE | Reason: {self.reason}")
            self.log_transition(
                old_state, "ACTIVE", self.reason,
                event_type="OPERATOR_ACTION",
                source="operator",
                operator_id=operator_id,
                event="operator_activation"
            )

def get_state_manager(state_file: Optional[str] = None) -> TradingStateManager:
    if state_file:
        return TradingStateManager(state_file=state_file)
    return TradingStateManager()

# ── OPERATIONAL CIRCUIT BREAKER PERSISTENCE ──
OP_STATE_FILE = "data/operational_state.json"
OP_TMP_FILE = "data/operational_state.tmp"

def load_operational_state() -> dict:
    if not os.path.exists(OP_STATE_FILE):
        return _get_default_op_state()
    try:
        with open(OP_STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if data.get("schema_version") != 1:
            return _get_default_op_state()
        return data
    except Exception as e:
        return _get_default_op_state()

def save_operational_state(data: dict) -> None:
    data["schema_version"] = 1
    os.makedirs(os.path.dirname(OP_STATE_FILE), exist_ok=True)
    try:
        with open(OP_TMP_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(OP_TMP_FILE, OP_STATE_FILE)
    except Exception as e:
        if os.path.exists(OP_TMP_FILE):
            try:
                os.remove(OP_TMP_FILE)
            except:
                pass

def _get_default_op_state() -> dict:
    return {
        "schema_version": 1,
        "last_startup": time.time(),
        "last_clean_shutdown": False,
        "oi_circuit": {
            "open_until": 0.0,
            "failure_count": 0,
            "last_error": "",
            "reason": "",
            "warning_logged": False
        },
        "quote_circuit": {
            "open_until": 0.0,
            "failure_count": 0,
            "last_error": "",
            "reason": ""
        }
    }
