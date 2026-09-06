import json
import os
from dataclasses import asdict
from typing import Any

# Define paths relative to the project root (assuming this runs from project root)
DATA_DIR = "data"
EXECUTIONS_LOG = os.path.join(DATA_DIR, "immutable_executions.jsonl")
ATTRIBUTIONS_LOG = os.path.join(DATA_DIR, "execution_attribution.jsonl")
LEARNING_LOG = os.path.join(DATA_DIR, "learning_events.jsonl")

class ExecutionLedgerWriter:
    """
    Append-only persistence layer for the Phase 3 Architecture.
    Never updates or deletes. Only appends to JSONL files.
    """
    
    @staticmethod
    def _ensure_dir():
        if not os.path.exists(DATA_DIR):
            os.makedirs(DATA_DIR)

    @classmethod
    def _append_to_jsonl(cls, file_path: str, data: Any):
        cls._ensure_dir()
        
        # If it's a dataclass, convert to dict
        if hasattr(data, "__dataclass_fields__"):
            data_dict = asdict(data)
        else:
            data_dict = data
            
        with open(file_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(data_dict) + "\n")

    @classmethod
    def append_executed_trade(cls, executed_trade: Any):
        """Appends to the execution reality ledger."""
        cls._append_to_jsonl(EXECUTIONS_LOG, executed_trade)
        
    @classmethod
    def append_execution_attribution(cls, attribution: Any):
        """Appends to the replay attribution ledger."""
        cls._append_to_jsonl(ATTRIBUTIONS_LOG, attribution)
        
    @classmethod
    def append_learning_event(cls, learning_event: Any):
        """Appends to the learning adaptations ledger."""
        cls._append_to_jsonl(LEARNING_LOG, learning_event)
