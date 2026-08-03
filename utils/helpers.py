"""
============================================
UTILITY HELPER FUNCTIONS
============================================
"""

from datetime import datetime, time
import json
import os


def get_ist_now() -> datetime:
    import pytz
    ist = pytz.timezone('Asia/Kolkata')
    return datetime.now(ist)

def timestamp_now() -> str:
    """Current timestamp as string"""
    return get_ist_now().strftime("%Y-%m-%d %H:%M:%S")

def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """Safe division to avoid ZeroDivisionError"""
    if denominator == 0:
        return default
    return numerator / denominator


def is_market_hours() -> bool:
    """Check if current time is within Indian market hours (09:15 to 15:40 IST)."""
    now = get_ist_now().time()
    market_open = time(9, 15)
    market_close = time(15, 40)
    return market_open <= now <= market_close


def is_pre_market() -> bool:
    """Check if it's pre-market session"""
    now = get_ist_now().time()
    return time(9, 0) <= now < time(9, 15)


def is_post_market() -> bool:
    """Check if it's strictly post-market (15:40 to 16:00) to allow clean shutdown."""
    now = get_ist_now().time()
    return time(15, 40) <= now <= time(16, 0)


def save_json(data: dict, filepath: str):
    """Save dictionary to JSON file"""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2, default=str)


def load_json(filepath: str) -> dict:
    """Load JSON file to dictionary"""
    if not os.path.exists(filepath):
        return {}
    with open(filepath, 'r') as f:
        return json.load(f)


def round_to_tick(price: float, tick_size: float = 0.05) -> float:
    """Round price to nearest tick size"""
    return round(price / tick_size) * tick_size


def calculate_percentage(value: float, total: float) -> float:
    """Calculate percentage"""
    return safe_divide(value * 100, total)
