from dataclasses import dataclass
from typing import Optional

@dataclass
class ExecutionPolicy:
    suppressed: bool = False
    reason: str = ""
    original_sl: float = 0
    adapted_sl: float = 0
    original_qty: int = 0
    adapted_qty: int = 0
    sl_multiplier: float = 1.0
    tp2_multiplier: float = 1.0
    position_scale: float = 1.0

    def to_dict(self) -> dict:
        return {
            "suppressed": self.suppressed,
            "reason": self.reason,
            "original_sl": self.original_sl,
            "adapted_sl": self.adapted_sl,
            "original_qty": self.original_qty,
            "adapted_qty": self.adapted_qty,
            "sl_multiplier": self.sl_multiplier,
            "tp2_multiplier": self.tp2_multiplier,
            "position_scale": self.position_scale,
        }
