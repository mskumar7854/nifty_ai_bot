"""
============================================
🔒 SYSTEM FINGERPRINT — Runtime State Snapshot

Captures a deterministic fingerprint of the
system configuration at the moment of each
trade decision. Enables:
  - Incident replay (what config was active?)
  - Regression detection (did config drift?)
  - Burn-in comparison (consistent baseline?)
  - Debugging adaptive threshold behavior

Attached to every Signal.metadata["fingerprint"]
and every gate rejection log entry.
============================================
"""

import hashlib
import json
import time
import os
from typing import Dict, Any, Optional


class SystemFingerprint:
    """
    Lightweight, deterministic snapshot of runtime state.
    Computed once per cycle (not per agent) to minimize overhead.
    """

    def __init__(self):
        self._cache: Optional[Dict[str, Any]] = None
        self._cache_time: float = 0.0
        self._cache_ttl: float = 1.0  # Refresh at most once per second

    def capture(
        self,
        active_agents: list,
        weights: dict,
        thresholds: dict,
        regime: str,
        gap_penalty: float,
        system_mode: str,
    ) -> Dict[str, Any]:
        """
        Capture current system state as a fingerprint dict.
        
        Returns a lightweight dict suitable for JSON serialization
        and attachment to signal metadata.
        """
        now = time.time()

        # Return cached if within TTL (avoid recomputing every cycle)
        if self._cache and (now - self._cache_time) < self._cache_ttl:
            return self._cache

        # Build the fingerprint
        fingerprint = {
            "ts": round(now, 3),
            "mode": system_mode,
            "regime": regime,
            "gap_penalty": round(gap_penalty, 4),
            "thresholds": {
                "min_gap": round(thresholds.get("min_gap", 0), 4),
                "min_conf": round(thresholds.get("min_conf", 0), 4),
            },
            "agent_count": len(active_agents),
            "config_hash": self._compute_config_hash(weights, thresholds),
        }

        self._cache = fingerprint
        self._cache_time = now
        return fingerprint

    def _compute_config_hash(self, weights: dict, thresholds: dict) -> str:
        """
        Deterministic hash of weight + threshold configuration.
        Changes when agent weights or thresholds are modified.
        Used for regression detection across burn-in sessions.
        """
        # Sort keys for deterministic ordering
        payload = json.dumps(
            {"w": dict(sorted(weights.items())), "t": dict(sorted(thresholds.items()))},
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode()).hexdigest()[:12]

    @staticmethod
    def compact(fingerprint: dict) -> str:
        """One-line summary for log output."""
        return (
            f"[FP:{fingerprint.get('config_hash', '?')} | "
            f"regime={fingerprint.get('regime', '?')} | "
            f"gap={fingerprint.get('gap_penalty', '?')} | "
            f"agents={fingerprint.get('agent_count', '?')}]"
        )
