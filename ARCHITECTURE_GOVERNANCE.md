# Nifty AI System - Architecture Governance (V3.2)

This document outlines the strict governance rules for the V3.2 Domain-Driven Blackboard Architecture.
Every future change must satisfy these rules.

## Rule 1: No Direct Bot Communication
- Only: Bot -> Blackboard -> Orchestrator
- Never let bots invoke one another (e.g., MarketBot never calls OptionsBot).

## Rule 2: Stateless Bots Only
- Every bot must satisfy the pure function pattern: Input -> Output.
- No hidden globals, no cached decisions, no internal state histories.

## Rule 3: State Only Through StateManager
- Never use direct class properties to store state across ticks (e.g., self.last_trade).
- Always use the centralized interface: state_manager.get_position(...).
- This ensures replay remains deterministic.

## Rule 4: Every Decision Must Be Explainable
- Every DecisionReport must answer:
  - Why did we trade? (why)
  - Why didn't we trade? (why_not)
  - What evidence mattered?
  - Which gates rejected?
- If a replay cannot explain a decision, it is considered a software defect.

## Rule 5: Plugins Never Modify the Blackboard Directly
- Plugins generate objective facts (e.g., MomentumReport).
- The parent Bot decides what facts to publish to the Blackboard. This prevents plugin conflicts.

## Rule 6: Fact vs. Opinion Separation on the Blackboard
- **Facts**: Objective market data that never changes (VWAP, ATR, PCR, OI). Resides in MarketSnapshot.
- **Opinions**: Inferred conclusions (Trend is Bearish, Confidence is 89, Grade A, EV 1.6R). Derived from facts.

## Rule 7: Replay Snapshots
- Save the entire Blackboard (MarketSnapshot + DecisionContext + DecisionReport) at every evaluation.
- Replay tests evaluate identical snapshots against newer engine iterations for rigorous regression testing.

## Rule 8: Architecture Versioning
- Embed ARCHITECTURE_VERSION = "3.2" inside all replay logs and telemetry.
- Prevents ambiguity years down the line about which platform produced which trades.
