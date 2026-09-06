import os
import json
import logging
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List
from datetime import datetime

logger = logging.getLogger("rejection_telemetry")

# Telemetry Rejection & Exit Reason Codes (3 Aug 2026 Sync)
ENTRY_AFTER_CUTOFF = "ENTRY_AFTER_CUTOFF"            # Trade entry rejected past 15:20 IST cutoff
BROKER_SQUAREOFF_BUFFER = "BROKER_SQUAREOFF_BUFFER"  # Force flattened prior to 15:25 IST broker square-off

@dataclass
class GateEvaluation:
    gate_name: str
    passed: bool
    threshold: float
    actual: float
    delta: float
    inputs: Dict[str, Any] = field(default_factory=dict)

@dataclass
class RejectionRecord:
    signal_id: str
    timestamp: str
    regime: str
    mpm_mode: str
    primary_blocker: str
    total_failed_gates: int
    evaluation_duration_ms: float
    gate_details: Dict[str, GateEvaluation] = field(default_factory=dict)

class NiftyJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        import numpy as np
        if isinstance(obj, np.bool_):
            return bool(obj)
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)

class RejectionLogger:
    def __init__(self, log_dir: str = "data/telemetry/rejections"):
        self.log_dir = log_dir
        os.makedirs(self.log_dir, exist_ok=True)
        self.current_file = os.path.join(
            self.log_dir, 
            f"rejections_{datetime.now().strftime('%Y%m%d')}.jsonl"
        )
        
    def log_rejection(self, record: RejectionRecord):
        try:
            with open(self.current_file, "a") as f:
                f.write(json.dumps(asdict(record), cls=NiftyJSONEncoder) + "\n")
        except Exception as e:
            logger.error(f"Failed to write rejection record: {e}")
