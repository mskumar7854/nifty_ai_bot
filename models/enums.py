from enum import Enum

class Direction(Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"

class SignalType(Enum):
    BUY_CE = "BUY_CE"
    BUY_PE = "BUY_PE"
    NO_TRADE = "NO_TRADE"
    EXIT = "EXIT"

class Strength(Enum):
    STRONG = "STRONG"
    MODERATE = "MODERATE"
    WEAK = "WEAK"

class SignalGrade(Enum):
    A_PLUS = "A+"
    A = "A"
    B_PLUS = "B+"
    B = "B"
    C = "C"
    D = "D"

class SignalStatus(str, Enum):
    FRESH = "FRESH ✅"
    ACTIVE = "ACTIVE ✅"
    EXPIRING = "EXPIRING ⚠️"
    EXPIRED = "EXPIRED ⛔"
    T1_HIT = "T1 HIT 🎯"
    T2_HIT = "T2 HIT 🎯"
    T3_HIT = "T3 HIT 🎯"
    TRAILING = "TRAILING 🔄"
    BREAKEVEN = "BREAKEVEN 🛡️"
    CLOSED_WIN = "WIN 🏆"
    CLOSED_LOSS = "LOSS ❌"
    CLOSED_BREAKEVEN = "BREAKEVEN ⚪"
