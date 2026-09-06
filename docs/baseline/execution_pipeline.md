# Baseline Execution Pipeline

This document records the execution pipeline structure of the Nifty AI Agent System prior to the v5.0 refactoring.

## Main Loop (`main.py`)
1. **Boot Sequence:**
   - Initialize Telemetry, SQLite Memory, and Config.
   - Boot `DataManager`, `BrokerHealthMonitor`, `SimulationEngine` (if SIMULATION).
   - Instantiate `DecisionEngineV3`, `TradeFilter`, `PositionManager`, `MasterDecisionEngine`.
   - Setup Telegram webhook listener.

2. **Cycle Execution (`_run_cycle`):**
   - Perform routine checks: Posture check (via orchestrator), execution failures limit, engine errors limit.
   - Master Gate Pre-check via `MasterDecisionEngine.approve()`.
   - Data ingestion: Update latest candle via `DataManager.update_latest_candle_async`.
   - Force-Exit Sweep (15:20 deadline check).
   - Entry processing: `EntryEngine.check_confirmations()`.
   - Evaluate signals via `DecisionEngineV3.process()`.

## Decision Flow
- `DecisionEngineV3.process()` executes agents in phases (Phase 1, 2, 4) if active.
- Normalizes scores, factors gap penalties and regime uncertainties.
- Passes generated signal to `TradeFilter.evaluate()`.
- If passed, generates trade intent and sends to `PositionManager`.

## Execution and Position Management
- Signal enters `PositionManager.execute_trade()`.
- Further limits checking (capital, open positions, daily limits).
- OMS integration: Creates Intent in database.
- Broker interaction via `dhan_client.py` (`_SimulationGuardedClient` lock if simulated).
- Tracks position with dynamic trailing stops, profit targets, and Trade Health analytics.
