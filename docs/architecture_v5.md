# Nifty AI System v5.0 Architecture

This document describes the v5.0 pipeline-based architecture, which replaces the previous monolithic `NiftyAISystem` setup. The primary goal is formalizing clear data contracts, modular responsibilities, and strict separation of decision, execution, position lifecycle management, and observability.

## Pipeline Architecture

```text
                 TradingOrchestrator
                        │
        ┌───────────────┼───────────────┐
        │               │               │
 RuntimeContext     EventManager   TelemetryPipeline
        │
        ▼
 MarketDataPipeline
        ▼
  MarketSnapshot
        ▼
 DecisionPipeline
        ▼
 TradingDecision
        ▼
 ExecutionPipeline
        ▼
 ExecutionResult
        ▼
 PositionPipeline
        ▼
 PositionAction[]
        ▼
 ExecutionPipeline
```

### 1. TradingOrchestrator
The `TradingOrchestrator` is strictly responsible for runtime coordination. It does not implement business logic, trading rules, or exit conditions. Its duties include:
- Initializing the runtime cycle
- Sequencing the pipelines
- Catching and routing exceptions
- Scheduling periodic tasks

### 2. RuntimeContext
A lightweight dependency container that provides configurations, db connections, caches, and telemetry bindings to the pipelines, preventing the use of global state. It holds infrastructure references like `BrokerHealthMonitor` but does not hold mutable trading objects like the current signal or open positions.

### 3. EventManager
Handles internal domain events as immutable domain facts, significantly improving replayability and debugging. Events are categorized into Market, Decision, Execution, Position, and Risk events (e.g., `OrderSubmitted`, `PositionClosed`, `DailyLossLimitReached`).

### 4. MarketDataPipeline
Ingests live ticks or simulation data and transforms them into a formal `MarketSnapshot`.

### 5. DecisionPipeline
Processes the `MarketSnapshot`, applies technical analysis, regime classification, and filter gates to produce a `TradingDecision` (Signal). 

### 6. ExecutionPipeline
The *only* component allowed to communicate with the broker API. It handles instrument resolution, position sizing, execution fidelity simulation (in paper mode), structural breaker safety checks, and live broker order placements, returning an `ExecutionResult`.

It also exposes an `apply_position_actions()` interface to execute subsequent position lifecycle adjustments (trailing stops, exits).

### 7. PositionPipeline
Evaluates the health of an active `PositionState` continuously and returns a list of actionable `PositionAction` objects (e.g., `FULL_EXIT`, `UPDATE_SL`). It does *not* talk to the broker directly.

### 8. TelemetryPipeline
Handles metrics logging, dashboard updates, and Telegram alerts by reacting to domain events emitted throughout the cycle. It is fully decoupled from the core trading logic.

## Sequence Diagram (One Trading Cycle)

```text
Market
  │
  ▼
MarketDataPipeline
  │
  ▼
DecisionPipeline
  │
  ▼
ExecutionPipeline
  │
  ▼
PositionPipeline
  │
  ▼
ExecutionPipeline
  │
  ▼
Telemetry
```

## Position State Diagram

This complements the Trade Health state machine, representing the high-level lifecycle of `PositionState`.

```text
Pending
  │
  ▼
Open
  │
  ▼
Healthy
  │
  ▼
Warning
  │
  ▼
Critical
  │
  ▼
Closed
```
