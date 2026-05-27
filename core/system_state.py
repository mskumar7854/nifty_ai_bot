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
        "ACTIVE": ["PAUSED_MANUAL", "PAUSED_FINANCIAL", "PAUSED_STRUCTURAL", "PENDING_RECONCILIATION", "HALTED"],
        "PAUSED_MANUAL": ["ACTIVE", "HALTED"],
        "PAUSED_FINANCIAL": ["ACTIVE", "HALTED"],
        "PAUSED_STRUCTURAL": ["ACTIVE", "HALTED"],
        "PENDING_RECONCILIATION": ["HALTED"],
        "HALTED": []  # Terminal state. Cannot transition dynamically.
    }

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(TradingStateManager, cls).__new__(cls, *args, **kwargs)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self.state_file = os.path.join("data", "system_state.json")
        self.state = "ACTIVE"
        self.reason = "Initial startup state"
        self.alert_callback: Optional[Callable[[str], None]] = None
        self._initialized = True
        self.load_state()

        # Log initial startup transition
        self.log_transition("NONE", self.state, f"Startup loaded: {self.reason}")

    def load_state(self):
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, "r") as f:
                    data = json.load(f)
                    saved_state = data.get("state", "ACTIVE")
                    saved_reason = data.get("reason", "")
                    
                    if saved_state in ["HALTED", "PAUSED_STRUCTURAL", "PAUSED_MANUAL"]:
                        self.state = saved_state
                        self.reason = saved_reason
                        logger.warning(f"🔒 Persistent state loaded from storage: {self.state} | Reason: {self.reason}")
                    else:
                        self.state = "ACTIVE"
                        self.reason = "Cleared temporary states on startup"
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

    def set_state(self, state: str, reason: str = "", signal_id: str = "N/A", source: str = "system"):
        valid_states = ["ACTIVE", "PAUSED_STRUCTURAL", "PAUSED_FINANCIAL", "PAUSED_MANUAL", "HALTED", "PENDING_RECONCILIATION"]
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
                self.log_transition(old_state, "HALTED", self.reason, signal_id, event_type="SYSTEM_TRANSITION", source="system")
            return
            
        self.state = state
        self.reason = reason
        self.save_state()
        logger.info(f"🔄 System state transitioned to: {self.state} | Reason: {self.reason}")
        
        event_type = "OPERATOR_ACTION" if source == "telegram" or "manual" in reason.lower() or "resume" in reason.lower() else "SYSTEM_TRANSITION"
        self.log_transition(old_state, self.state, self.reason, signal_id, event_type=event_type, source=source)

    def log_transition(self, from_state: str, to_state: str, reason: str, signal_id: str = "N/A", event_type: str = "SYSTEM_TRANSITION", source: str = "system"):
        transition_record = {
            "schema_version": "1.0",
            "event_type": event_type,
            "source": source,
            "from": from_state,
            "to": to_state,
            "reason": reason,
            "signal_id": signal_id,
            "ts": time.time(),
            "datetime": datetime.now().isoformat()
        }
        audit_file = os.path.join("data", "state_transitions.jsonl")
        os.makedirs(os.path.dirname(audit_file), exist_ok=True)
        try:
            with open(audit_file, "a") as f:
                f.write(json.dumps(transition_record) + "\n")
        except Exception as e:
            logger.error(f"Failed to write state transition audit log: {e}")

    def is_trading_allowed(self) -> bool:
        return self.state == "ACTIVE"

    def trigger_structural_halt(self, reason: str, signal_id: str = "N/A"):
        if self.state == "HALTED":
            return
        self.set_state("HALTED", reason, signal_id=signal_id)
        alert_msg = f"🚨 **CRITICAL STRUCTURAL HALT** 🚨\nReason: {reason}\n\n⚠️ System is locked. Operator restart required."
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

    def force_activate(self, reason: str = "Operator force activation"):
        old_state = self.state
        self.state = "ACTIVE"
        self.reason = reason
        self.save_state()
        logger.warning(f"🔓 FORCE ACTIVE override triggered: {old_state} ➔ ACTIVE | Reason: {self.reason}")
        self.log_transition(old_state, "ACTIVE", self.reason, event_type="OPERATOR_ACTION", source="telegram")

def get_state_manager() -> TradingStateManager:
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
