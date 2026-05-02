"""
============================================
🧠 SIGNAL WEIGHTS CONFIG
Intelligence Layer v1.0
============================================
Each agent's influence on the final trade 
decision is balanced here. 
============================================
"""

# ── AGENT WEIGHT MATRIX ──
# Total should ideally sum to 1.0, 
# but the system normalizes by total_weight_used.
AGENT_WEIGHTS = {
    "market": 0.25,        # Higher weight for overall trend
    "momentum": 0.25,      # Core momentum indicator
    "oi": 0.15,            # Option chain confirmation
    "trap": 0.10,          # Wick/Liquidity trap detection
    "risk": 0.10,          # Advisory risk assessment
    "sentiment": 0.05,     # External sentiment (social/news)
    "learning": 0.05,      # Historical pattern matching
    "expiry_day": 0.03,    # Intraday decay risk
    "decay": 0.02,         # Time value risk
}

# ── PROBABILISTIC FILTERS ──
MIN_CONFIDENCE = 0.6       # Minimum normalized score to trade
MIN_DIRECTION_GAP = 0.1    # Min difference between Buy and Sell scores

# ── SAFETY CLAMPS ──
CONFIDENCE_MIN = 0.1
CONFIDENCE_MAX = 0.95
