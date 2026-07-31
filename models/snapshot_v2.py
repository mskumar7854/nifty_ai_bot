import json
import hashlib
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Any, Optional
from datetime import datetime
import os
import subprocess

def get_git_commit() -> str:
    """Retrieve the current git commit hash."""
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL)
        return commit.decode("utf-8").strip()
    except Exception:
        return "UNKNOWN"

@dataclass
class SnapshotMetadata:
    snapshot_id: str
    timestamp: str
    symbol: str
    expiry: str
    mode: str
    schema_version: str = "2.0"
    pipeline_version: str = "2.1"
    strategy_version: str = "4.8.0"
    git_commit: str = field(default_factory=get_git_commit)
    parent_snapshot_id: Optional[str] = None
    trade_id: Optional[str] = None
    shadow_trade_id: Optional[str] = None
    experiment_id: Optional[str] = None
    replay_run_id: Optional[str] = None

@dataclass
class AgentOpinion:
    signal: str
    confidence: float
    details: Dict[str, Any] = field(default_factory=dict)

@dataclass
class GateResult:
    passed: bool
    actual: float
    required: float
    detail: str = ""

@dataclass
class ReplayStatus:
    deterministic: bool = True
    missing_fields: List[str] = field(default_factory=list)
    fallback_values: List[str] = field(default_factory=list)

@dataclass
class Outcome:
    status: str
    trade_id: str
    entry_time: str = ""
    exit_time: str = ""
    entry_price: float = 0.0
    exit_price: float = 0.0
    realized_r: float = 0.0
    max_favorable_excursion_r: float = 0.0
    max_adverse_excursion_r: float = 0.0
    exit_reason: str = ""

@dataclass
class DecisionSnapshotV2:
    """
    DecisionSnapshotV2 (Deterministic Replay Foundation)
    Contains everything required to replay, audit, explain, and statistically analyze a trading decision
    without consulting any external runtime state.
    """
    metadata: SnapshotMetadata
    market: Dict[str, Any]
    agents: Dict[str, AgentOpinion]
    confidence: Dict[str, Any]
    confluence: Dict[str, Any]
    expected_value: Dict[str, Any]
    structure: Dict[str, Any]
    risk: Dict[str, Any]
    gate_results: Dict[str, GateResult]
    decision: Dict[str, Any]
    execution: Dict[str, Any]
    event_timeline: Dict[str, str]
    replay: ReplayStatus
    outcome: Optional[Outcome] = None
    snapshot_hash: str = ""

    def compute_hash(self) -> str:
        """Computes a SHA256 hash of the JSON representation (excluding the hash field itself)."""
        d = asdict(self)
        d.pop("snapshot_hash", None)
        raw = json.dumps(d, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    def __post_init__(self):
        if not self.snapshot_hash:
            self.snapshot_hash = self.compute_hash()

    def to_json(self) -> str:
        return json.dumps(asdict(self), default=str)
