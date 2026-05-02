# Graph Report - .  (2026-04-26)

## Corpus Check
- 93 files · ~0 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1181 nodes · 3561 edges · 30 communities detected
- Extraction: 32% EXTRACTED · 68% INFERRED · 0% AMBIGUOUS · INFERRED: 2415 edges (avg confidence: 0.5)
- Token cost: 0 input · 0 output

## God Nodes (most connected - your core abstractions)
1. `Settings` - 272 edges
2. `Direction` - 222 edges
3. `Strength` - 189 edges
4. `MarketSnapshot` - 177 edges
5. `AgentOutput` - 142 edges
6. `BaseAgent` - 126 edges
7. `Config` - 121 edges
8. `SignalType` - 112 edges
9. `Signal` - 111 edges
10. `TradeLogger` - 59 edges

## Surprising Connections (you probably didn't know these)
- `Realistic cost and slippage modeling.      KEY INSIGHT:     A trade that shows ₹` --uses--> `BrokerageConfig`  [INFERRED]
  core\slippage_model.py → config\settings.py
- `============================================ 🚪 EXIT ENGINE — INTELLIGENT EXIT MA` --uses--> `Settings`  [INFERRED]
  core\exit_engine.py → config\settings.py
- `Exit intelligence layer.      Protects profits, limits losses,     enforces dail` --uses--> `Settings`  [INFERRED]
  core\exit_engine.py → config\settings.py
- `Record a trade result and update exit state` --uses--> `Settings`  [INFERRED]
  core\exit_engine.py → config\settings.py
- `Check if a new trade can be taken` --uses--> `Settings`  [INFERRED]
  core\exit_engine.py → config\settings.py

## Communities

### Community 0 - "Community 0"
Cohesion: 0.03
Nodes (178): ABC, AgentCategory, analyze(), BaseAgent, ============================================ ENHANCED BASE AGENT v2 Adds: blocke, How consistently has this agent been giving same direction, Return a blocker output that prevents trading, BaseAgent (+170 more)

### Community 1 - "Community 1"
Cohesion: 0.02
Nodes (124): Config, ============================================ NIFTY INTRADAY STRATEGY — CONFIG ==, CandleAggregator, DataProvider, DhanDataProvider, ============================================ DATA PROVIDER =====================, ── REPLACE THIS BODY WITH ACTUAL DHAN CALL ──         Example:             respo, Deterministic synthetic OHLCV for testing. (+116 more)

### Community 2 - "Community 2"
Cohesion: 0.02
Nodes (70): AlertManager, Play sound alert (system beep), Dashboard, ============================================ 📊 LIVE MONITORING DASHBOARD Web-bas, Web dashboard for monitoring the AI system, Broadcast a live signal to all connected clients, Update dashboard data (called from main loop), Start dashboard using gevent worker (+62 more)

### Community 3 - "Community 3"
Cohesion: 0.04
Nodes (69): ============================================ 🔔 ALERT MANAGER Dispatches signals, Send alert to Telegram, Log NO_TRADE signal quietly, Manages all alert dispatching.     Includes cooldown to prevent alert flooding., Main dispatch method.         Routes signal to all enabled channels., Check if enough time has passed since last alert, Rich formatted console alert, PendingEntry (+61 more)

### Community 4 - "Community 4"
Cohesion: 0.06
Nodes (26): DataManager, ============================================ DATA MANAGER Handles all data fetch, Returns both DataFrame and MarketSnapshot, Fetch latest and return snapshot, 🚀 ASYNC HFT DATA FETCH         Fetches data without blocking and returns (df, sn, 🚀 DELTA STATE CACHING         Calculates indicators ONLY for the new tick to sav, Create current market snapshot from given dataframe, Central data hub for the entire system.     Currently uses simulated data.     R (+18 more)

### Community 5 - "Community 5"
Cohesion: 0.09
Nodes (26): AISignalPacket, BridgeDecision, _build(), icon(), is_tradeable(), LayerResult, ╔══════════════════════════════════════════════════════════════╗ ║         SIGNA, Build from a live Signal + MarketSnapshot.         Handles both enum values and (+18 more)

### Community 6 - "Community 6"
Cohesion: 0.06
Nodes (20): DBManager, ============================================ 📦 DATABASE MANAGER Asynchronous SQL, Conditionally update signal status with optimistic locking.                  Ret, Loads signals that didn't reach a final state (for recovery)., Fire-and-forget async save to disk., Loads historical context on system boot., Generic execute for bulk updates or deletions., Generic fetch one for aggregations. (+12 more)

### Community 7 - "Community 7"
Cohesion: 0.08
Nodes (29): AgentIntervals, AlertConfig, BrokerageConfig, DashboardConfig, EnginePipelineConfig, ExitConfig, LegacyPositionConfig, ============================================ SETTINGS v3.2 — PRO MODE FINAL TUNI (+21 more)

### Community 8 - "Community 8"
Cohesion: 0.08
Nodes (16): DecisionEngine, ============================================ 🧠 DECISION ENGINE — THE MASTER AI B, Check for conditions that BLOCK trading entirely.         Returns list of blocke, Calculate weighted consensus from all agents.         Returns: (direction, confi, The brain that makes the final call.      Flow:     1. Collect all agent outputs, Build the final trading signal with parameters, Build a NO TRADE signal, Store signal in history (+8 more)

### Community 9 - "Community 9"
Cohesion: 0.09
Nodes (13): DailyScore, PaperTrade, PaperTrader, ============================================ PAPER TRADING TRACKER =============, Drop-in replacement for TradeExecutor during simulation.      Usage:         pap, Simulate order fill at entry_price (no slippage in paper mode)., Close a paper trade and update scorecards., Trail stop loss on a paper trade. (+5 more)

### Community 10 - "Community 10"
Cohesion: 0.15
Nodes (2): LearningAgent, LearningAgentV2Mixin

### Community 11 - "Community 11"
Cohesion: 0.14
Nodes (17): calculate_percentage(), get_ist_now(), is_market_hours(), is_pre_market(), load_json(), ============================================ UTILITY HELPER FUNCTIONS ==========, Current timestamp as string, Safe division to avoid ZeroDivisionError (+9 more)

### Community 12 - "Community 12"
Cohesion: 0.22
Nodes (3): DailySimReport, SimulatedTrade, SimulationEngine

### Community 13 - "Community 13"
Cohesion: 0.22
Nodes (14): build_ladder(), build_symbol(), get_atm_strike(), get_available_strikes(), get_itm_ce_strike(), get_itm_pe_strike(), get_option_security_id(), get_otm_ce_strike() (+6 more)

### Community 14 - "Community 14"
Cohesion: 0.16
Nodes (10): _get_current_session_name(), _now_ist(), ============================================ 🕐 SESSION STRATEGY — TIME-BASED RUL, True when in closing zone — exit only, no new trades, True if within any market session, Check if current IST time is within a range, Identify which session we're currently in, Get current session rules (+2 more)

### Community 15 - "Community 15"
Cohesion: 0.24
Nodes (2): Classify as HH/HL (bullish) or LH/LL (bearish), StructureAgent

### Community 16 - "Community 16"
Cohesion: 0.29
Nodes (2): PriceActionAgent, Order block: Last bearish candle before a strong bullish move (bullish OB)

### Community 17 - "Community 17"
Cohesion: 0.2
Nodes (5): Remove patterns derived from old data.         Market conditions change — old pa, Apply exponential decay weighting.         Recent trades matter MORE than old tr, Apply all memory control mechanisms.         Call this after recording each trad, Keep only the last N trades, Detect if the learning agent might be overfitting.          Signs of overfit:

### Community 18 - "Community 18"
Cohesion: 0.39
Nodes (1): ExpiryDayAgent

### Community 19 - "Community 19"
Cohesion: 0.33
Nodes (4): analyze_performance(), load_trades(), 🧠 THE LOG LOADER (NDJSON Optimized)     Loads trades with automatic fallback to, 🧠 THE STRATEGY AUDITOR     Answers: What works? Who is winning? Where is the ris

### Community 20 - "Community 20"
Cohesion: 0.67
Nodes (1): ============================================ 🧪 DHAN API BRIDGING TEST Verify tha

### Community 21 - "Community 21"
Cohesion: 1.0
Nodes (2): run_cmd(), verify()

### Community 22 - "Community 22"
Cohesion: 1.0
Nodes (1): ============================================ 🎓 LEARNING AGENT v2 — MEMORY CONTRO

### Community 23 - "Community 23"
Cohesion: 1.0
Nodes (0): 

### Community 24 - "Community 24"
Cohesion: 1.0
Nodes (1): ============================================ 🧠 SIGNAL WEIGHTS CONFIG Intelligenc

### Community 25 - "Community 25"
Cohesion: 1.0
Nodes (1): Standardizes confidence to 0.1 - 0.95 scale.

### Community 26 - "Community 26"
Cohesion: 1.0
Nodes (0): 

### Community 27 - "Community 27"
Cohesion: 1.0
Nodes (1): Safely extract the 'oc' (option chain) sub-dict.

### Community 28 - "Community 28"
Cohesion: 1.0
Nodes (0): 

### Community 29 - "Community 29"
Cohesion: 1.0
Nodes (0): 

## Knowledge Gaps
- **127 isolated node(s):** `============================================ 🎓 LEARNING AGENT v2 — MEMORY CONTRO`, `Mix into your existing LearningAgent to add     memory control capabilities.`, `Apply all memory control mechanisms.         Call this after recording each trad`, `Keep only the last N trades`, `Detect if the learning agent might be overfitting.          Signs of overfit:` (+122 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 22`** (2 nodes): `learning_agent_v2.py`, `============================================ 🎓 LEARNING AGENT v2 — MEMORY CONTRO`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 23`** (2 nodes): `check_db_state.py`, `check_db()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 24`** (2 nodes): `signal_weights.py`, `============================================ 🧠 SIGNAL WEIGHTS CONFIG Intelligenc`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 25`** (2 nodes): `.get_clamped_confidence()`, `Standardizes confidence to 0.1 - 0.95 scale.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 26`** (1 nodes): `inspect_dhan.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 27`** (1 nodes): `Safely extract the 'oc' (option chain) sub-dict.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 28`** (1 nodes): `pre_launch_check.ps1`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 29`** (1 nodes): `sim_runner.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Settings` connect `Community 0` to `Community 2`, `Community 3`, `Community 4`, `Community 6`, `Community 7`, `Community 8`, `Community 10`, `Community 12`, `Community 14`, `Community 15`, `Community 16`, `Community 18`?**
  _High betweenness centrality (0.279) - this node is a cross-community bridge._
- **Why does `============================================ NIFTY INTRADAY STRATEGY — MAIN ENTR` connect `Community 2` to `Community 0`, `Community 1`, `Community 3`, `Community 4`, `Community 12`?**
  _High betweenness centrality (0.243) - this node is a cross-community bridge._
- **Why does `Config` connect `Community 1` to `Community 2`, `Community 3`, `Community 4`, `Community 5`, `Community 13`?**
  _High betweenness centrality (0.210) - this node is a cross-community bridge._
- **Are the 267 inferred relationships involving `Settings` (e.g. with `AgentCategory` and `BaseAgent`) actually correct?**
  _`Settings` has 267 INFERRED edges - model-reasoned connections that need verification._
- **Are the 220 inferred relationships involving `Direction` (e.g. with `AgentCategory` and `BaseAgent`) actually correct?**
  _`Direction` has 220 INFERRED edges - model-reasoned connections that need verification._
- **Are the 187 inferred relationships involving `Strength` (e.g. with `AgentCategory` and `BaseAgent`) actually correct?**
  _`Strength` has 187 INFERRED edges - model-reasoned connections that need verification._
- **Are the 175 inferred relationships involving `MarketSnapshot` (e.g. with `AgentCategory` and `BaseAgent`) actually correct?**
  _`MarketSnapshot` has 175 INFERRED edges - model-reasoned connections that need verification._