"""
============================================
🧠 SIGNAL WEIGHTS CONFIG
Intelligence Layer v2.0
============================================
Each agent's influence on the final trade 
decision is balanced here.

Weights are NORMALIZED by total_weight_used,
so ratios matter more than absolute values.
All 18 active agents must be listed here.
Unlisted agents fall back to 0.02 — silent
dilution that kills the final score.
============================================
"""

# ── AGENT WEIGHT MATRIX ──
# All 18 active agents are listed explicitly.
# Weights sum to ~1.0 (normalized by engine anyway).
AGENT_WEIGHTS = {
    # ── Phase 1: Gatekeepers (structural) ──
    "time_session":     0.00,   # Blocker only — vote doesn't contribute to score
    "regime":           0.10,   # Critical context setter

    # ── Phase 2: Core Direction (highest influence) ──
    "structure":        0.15,   # BOS/CHoCH — highest structural signal
    "price_action":     0.15,   # Engulfing, pin bars — direct price evidence
    "momentum":         0.15,   # RSI/MACD momentum confirmation

    # ── Phase 3: Deep Confirmation ──
    "trap":             0.08,   # Wick trap detection — must confirm no fakeout
    "oi":               0.08,   # PCR + OI bias — options market confirmation
    "order_flow":       0.06,   # Bid/ask imbalance
    "level":            0.05,   # Key S/R levels
    "institutional":    0.06,   # FII/DII activity
    "multi_timeframe":  0.06,   # MTF alignment
    "volatility":       0.04,   # ATR/VIX context

    # ── Phase 4: Risk & Meta ──
    "risk":             0.05,   # Risk limit advisory
    "decay":            0.02,   # Theta decay context
    "expiry_day":       0.02,   # Expiry-day risk
    "learning":         0.04,   # Historical pattern match
    "market":           0.04,   # Overall market trend (legacy)
    "sentiment":        0.02,   # External sentiment (low weight)
}

# ── PROBABILISTIC FILTERS ──
# SIMULATION CALIBRATION: These are intentionally lower than live-trading
# targets. In simulation with random data, achieving 0.6+ is statistically
# near-impossible. Lower thresholds allow the system to PRACTICE execution
# while still filtering genuine low-confidence noise.
#
# Phase graduation targets:
#   Phase 1 (sim):    MIN_CONFIDENCE=0.45, MIN_DIRECTION_GAP=0.05
#   Phase 2 (live):   MIN_CONFIDENCE=0.55, MIN_DIRECTION_GAP=0.08
#   Phase 3 (scaled): MIN_CONFIDENCE=0.60, MIN_DIRECTION_GAP=0.10
MIN_CONFIDENCE = 0.45      # was 0.6 — achievable with 2-3 aligned agents
MIN_DIRECTION_GAP = 0.05   # was 0.1 — min spread between buy/sell scores

# ── SAFETY CLAMPS ──
CONFIDENCE_MIN = 0.1
CONFIDENCE_MAX = 0.95
