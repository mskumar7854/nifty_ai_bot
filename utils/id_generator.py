import time
import random
import threading
from datetime import datetime

class TradeIdGenerator:
    _lock = threading.Lock()
    _sequence = 0
    _last_timestamp = ""

    @classmethod
    def generate(cls) -> str:
        with cls._lock:
            now = datetime.now()
            # YYYYMMDD-HHMMSS
            ts_str = now.strftime("%Y%m%d-%H%M%S")
            
            if ts_str == cls._last_timestamp:
                cls._sequence += 1
            else:
                cls._sequence = 1
                cls._last_timestamp = ts_str
            
            # Format sequence as 3 digits, e.g. 001
            seq_str = f"{cls._sequence:03d}"
            
            # 4 hex chars random string
            rand_str = f"{random.randint(0, 65535):04X}"
            
            return f"{ts_str}-{seq_str}-{rand_str}"

def generate_trade_id() -> str:
    return TradeIdGenerator.generate()
