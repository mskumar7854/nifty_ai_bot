# NIFTY AI BOT — Multi-Timeframe Market Context
## Implementation Plan v1.0 (FROZEN FOR FUTURE IMPLEMENTATION)

**STATUS: ON HOLD PENDING S/R ENGINE GATE 2 VALIDATION (5+ SESSIONS)**

### Objective
Add a **Multi-Timeframe Context Engine (MTF Engine)** that evaluates:
* **15-minute** → higher-timeframe market context
* **5-minute** → setup/structure
* **1-minute** → execution/microstructure

The engine initially operates in **Shadow Mode only**.
It must **not change trade decisions** until empirical validation proves incremental value.

### 1. What We Actually Need
We do **not** need: LLMs, monthly/weekly/daily/4H analysis, vision models, TradingView screenshots, GPT/Claude API calls, LangChain/CrewAI, LSTM, Transformer forecasting, new trading strategy, new agent, or arbitrary new indicators.

### 2. The Three-Timeframe Hierarchy
* **15m**: CONTEXT Layer (Trend, Structure, Major S/R, Market Location)
* **5m**: SETUP Layer (Structure, S/R Interaction, Momentum, Setup State)
* **1m**: EXECUTION Layer (Entry alignment, Microstructure, Local momentum)

### 3. The Central Data Model (`models/mtf_context.py`)
```python
@dataclass
class TimeframeContext:
    timeframe: str
    trend: str
    structure: str
    nearest_support: Optional[float]
    nearest_resistance: Optional[float]
    location: str
    sr_event: Optional[str]
    momentum_state: str
    timestamp: datetime

@dataclass
class MTFState:
    higher: TimeframeContext      # 15m
    setup: TimeframeContext       # 5m
    execution: TimeframeContext   # 1m
    directional_alignment: str
    alignment_score: float
    context_state: str
    conflict_state: str
    trade_context: str
```

### 4. MTF Engine (`core/mtf_engine.py`)
* Receives existing market data (no new APIs).
* Calculates context for each timeframe.
* Compares timeframes (e.g., Aligned Bullish, Conflict).
* Generates structured alignment metadata.
* **Consumes the S/R Engine** (e.g., 15m Resistance + 5m Approach + 1m Breakout).

### 5. MTF Analytics Logger (`core/mtf_analytics_logger.py`)
Outputs to `data/mtf_analytics.csv` to capture states across all 3 timeframes, alignment, and forward returns (5m, 10m, 15m, 30m).

### 6. Integration
Runs after the S/R Engine in Phase 2. Operates strictly in Shadow Mode. **NOT an Agent**.

### 7. Candle Integrity (CRITICAL)
Must never use an unfinished higher-timeframe candle (e.g., at 10:07, the 10:00-10:15 candle cannot influence 15m structure).

### 8. Required Tests (`tests/test_mtf_engine.py`)
Data aggregation, candle integrity, structure, alignment logic, S/R interaction, session handling, and latency (<20ms).

### 9. Development Sequence
1. **CURRENT: S/R Gate 1 Complete. Run for 5+ sessions.**
2. S/R Gate 2: Empirical validation of S/R forward returns.
3. S/R Gate 3: Promotion decision.
4. **MTF Gate 1: Build + Shadow (Execute this plan).**
5. MTF Gate 2: Empirical validation (Directional alignment, Alignment quality, HTF location, MTF + S/R confluence).
6. MTF Gate 3: Promotion to Opportunity Ranking / EV Engine.
