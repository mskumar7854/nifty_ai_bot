import json
import logging
import os
from datetime import datetime
from typing import Optional

# Setup dedicated lifecycle logging path in logs directory
log_dir = "logs"
os.makedirs(log_dir, exist_ok=True)

lifecycle_handler = logging.FileHandler(os.path.join(log_dir, "signal_lifecycle.jsonl"), encoding="utf-8")
lifecycle_handler.setFormatter(logging.Formatter("%(message)s"))  # raw JSON only

lifecycle_logger = logging.getLogger("signal.lifecycle")
lifecycle_logger.setLevel(logging.INFO)
lifecycle_logger.addHandler(lifecycle_handler)
lifecycle_logger.propagate = False  # don't bleed into main log

def log_signal_created(signal_id: str, direction: str, raw_score_buy: float,
                       raw_score_sell: float, regime: str):
    lifecycle_logger.info(json.dumps({
        "event": "SIGNAL_CREATED",
        "signal_id": signal_id,
        "ts": datetime.now().isoformat(),
        "direction": direction,
        "raw_buy": round(raw_score_buy, 4),
        "raw_sell": round(raw_score_sell, 4),
        "regime": regime
    }))

def log_threshold_applied(signal_id: str, base_threshold: float,
                           adjusted_threshold: float, reason: str,
                           elapsed_min: int, gap_severity: str):
    lifecycle_logger.info(json.dumps({
        "event": "DYNAMIC_THRESHOLD_APPLIED",
        "signal_id": signal_id,
        "ts": datetime.now().isoformat(),
        "base_threshold": base_threshold,
        "adjusted_threshold": adjusted_threshold,
        "delta": round(base_threshold - adjusted_threshold, 4),
        "reason": reason,
        "elapsed_min": elapsed_min,
        "gap_severity": gap_severity,
        # Cohort classification — critical for Phase 3
        "cohort": "ADAPTIVE_ONLY" if adjusted_threshold < base_threshold else "STATIC_VALID"
    }))

def log_master_gate_result(signal_id: str, approved: bool, gate_name: str,
                            reason: Optional[str] = None):
    lifecycle_logger.info(json.dumps({
        "event": "MASTER_GATE_RESULT",
        "signal_id": signal_id,
        "ts": datetime.now().isoformat(),
        "approved": approved,
        "gate": gate_name,
        "reason": reason
    }))

def log_telegram_sent(signal_id: str, message_id: int):
    lifecycle_logger.info(json.dumps({
        "event": "TELEGRAM_SENT",
        "signal_id": signal_id,
        "ts": datetime.now().isoformat(),
        "telegram_msg_id": message_id
    }))

def log_operator_decision(signal_id: str, decision: str, delay_sec: float):
    """decision: APPROVED | REJECTED | TIMEOUT"""
    lifecycle_logger.info(json.dumps({
        "event": "OPERATOR_DECISION",
        "signal_id": signal_id,
        "ts": datetime.now().isoformat(),
        "decision": decision,
        "response_delay_sec": round(delay_sec, 1)
    }))

def log_oms_order_sent(signal_id: str, order_id: str, instrument: str,
                        direction: str, qty: int, limit_price: float,
                        stop_loss: float):
    lifecycle_logger.info(json.dumps({
        "event": "OMS_ORDER_SENT",
        "signal_id": signal_id,
        "ts": datetime.now().isoformat(),
        "order_id": order_id,
        "instrument": instrument,
        "direction": direction,
        "qty": qty,
        "limit_price": limit_price,
        "stop_loss": stop_loss
    }))

def log_broker_ack(signal_id: str, order_id: str, broker_order_id: str,
                    fill_price: float, slippage_pts: float):
    lifecycle_logger.info(json.dumps({
        "event": "BROKER_ACK",
        "signal_id": signal_id,
        "ts": datetime.now().isoformat(),
        "order_id": order_id,
        "broker_order_id": broker_order_id,
        "fill_price": fill_price,
        "slippage_pts": round(slippage_pts, 2)
    }))

def log_broker_ack_missing(signal_id: str, order_id: str, timeout_sec: float):
    lifecycle_logger.warning(json.dumps({
        "event": "BROKER_ACK_MISSING",
        "signal_id": signal_id,
        "ts": datetime.now().isoformat(),
        "order_id": order_id,
        "timeout_sec": timeout_sec
    }))

def log_position_closed(signal_id: str, order_id: str, exit_reason: str,
                         entry_price: float, exit_price: float,
                         realized_r: float, realized_pnl: float,
                         hold_duration_min: float):
    lifecycle_logger.info(json.dumps({
        "event": "POSITION_CLOSED",
        "signal_id": signal_id,
        "ts": datetime.now().isoformat(),
        "order_id": order_id,
        "exit_reason": exit_reason,  # SL_HIT | TARGET_HIT | MANUAL | EXPIRY | TIMEOUT
        "entry_price": entry_price,
        "exit_price": exit_price,
        "realized_r": round(realized_r, 3),
        "realized_pnl": round(realized_pnl, 2),
        "hold_duration_min": round(hold_duration_min, 1)
    }))

def log_mav_state(signal_id: str, state: str, structure_level: float, score: float, reason: str = ''):
    lifecycle_logger.info(json.dumps({
        "event": f"MAV_{state}",
        "signal_id": signal_id,
        "ts": datetime.now().isoformat(),
        "structure_level": structure_level,
        "acceptance_score": score,
        "reason": reason
    }))
