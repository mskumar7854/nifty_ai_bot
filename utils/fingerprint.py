import json
import hashlib
from typing import Dict, Any

class ExecutionFingerprint:
    """
    Dedicated service for generating immutable cryptographic identities 
    for executed trades using canonical JSON and numeric formatting.
    """

    @staticmethod
    def _canonicalize_float(val: float) -> str:
        """
        Rounds floating point numbers to 6 decimal places and formats as string
        to prevent cross-platform floating point representation drift.
        """
        if val is None:
            return "null"
        return f"{val:.6f}"

    @classmethod
    def create(cls, 
               schema_version: int, 
               execution_version: int, 
               trade_id: str, 
               decision_snapshot_id: str,
               execution_context: str,
               security_id: str,
               entry_price: float,
               timestamp: str) -> str:
        """
        Generates a SHA-256 canonical identity fingerprint.
        """
        # Build canonical payload dictionary
        payload_dict = {
            "schema_version": schema_version,
            "execution_version": execution_version,
            "trade_id": trade_id,
            "decision_snapshot_id": decision_snapshot_id,
            "execution_context": execution_context,
            "security_id": security_id,
            "entry_price": cls._canonicalize_float(entry_price),
            "timestamp": timestamp,
        }
        
        # Serialize to canonical JSON (sorted keys, no spaces)
        canonical_json = json.dumps(
            payload_dict,
            separators=(",", ":"),
            sort_keys=True
        )
        
        return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
