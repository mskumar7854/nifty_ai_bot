# Extracted Algorithms from `nifty_strategy/`

Before archiving the `nifty_strategy/` directory, the following valuable algorithms, risk ideas, and mathematical logic were extracted for potential future integration into the v5.0 `core/` pipelines.

## 1. The 7-Layer Signal Bridge Logic (`signal_bridge.py`)
A highly structured approach to validating AI signals before execution. It uses a 7-layer pipeline:
1. **Core Alignment**: `confluence_ratio >= 0.65`
2. **Primary Agent Consensus**: At least 2 of 3 primary agents (market, multi_timeframe, oi) must agree.
3. **Warning Intelligence**: Checks for critical danger phrases ("large wick", "stop hunt", "liquidity sweep", etc.). Yields `WAIT` instead of `NO_TRADE`.
4. **Grade × Regime Matrix**: 
   - A+, A, B+ allowed in TRENDING_UP, TRENDING_DOWN, BREAKOUT.
   - B allowed ONLY in BREAKOUT.
   - C, D always skipped.
5. **Strategy 7-Gate Check**: Integrates technicals (EMA, RSI, Breakout).
6. **Entry Quality**: `abs(current - entry) / entry * 100 <= 0.20%` (prevents chasing stale entries).
7. **Scoring Engine**: Base score (70) + Bonus points (70) based on confidence, grade, confluence, regime, and RSI.
*Output:* `STRONG_TRADE` (>=110 pts), `CONDITIONAL` (>=80 pts, half position size).

## 2. Safety Filters (`strategy.py -> SafetyFilter`)
Three micro-gates executed AFTER breakout detection:
- **Gate A (Large-Wick Rejection)**: `dominant_wick / body <= 2.0`. Rejects candles where the wick is more than twice the body size.
- **Gate B (Stale Breakout Distance Cap)**: `distance_pct <= 0.30%`. Rejects entries if the price has moved more than 0.30% past the breakout level.
- **Gate C (Trend ↔ Breakout Match)**: Bullish trend must have a bullish breakout; bearish must have a bearish breakdown.

## 3. Dynamic Position Scaling (`risk_manager.py -> calculate_position_size`)
Adjusts position size based on signal conviction (used specifically for Telegram signals in the legacy code, but applicable to AI confidence):
```python
multiplier = 1.0
if entry_type == "TELEGRAM":
    norm_score = score / 140.0 if score > 1 else score
    if norm_score >= 0.90:
        multiplier = 0.75
    elif norm_score >= 0.85:
        multiplier = 0.50
    else:
        multiplier = 0.25
```

## 4. Trailing Stop Loss Progression (`risk_manager.py -> trail_stop_loss`)
Two-phase trailing mechanism:
- **Phase 1 (+10% or equivalent `TRAIL_TO_COST_PERCENT`)**: Move SL to entry cost.
- **Phase 2 (+20% or equivalent `LOCK_PROFIT_PERCENT`)**: Lock 50% of the open profit. `locked_sl = entry_price + profit * 0.50`.

---
*Note: The actual executable code has been archived in `archive/legacy_v4/nifty_strategy/` to maintain a single source of truth in the production `core/`.*
