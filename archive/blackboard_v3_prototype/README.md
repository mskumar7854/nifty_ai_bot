# Blackboard Architecture Prototype (v3.2) - Archived

## Status: ARCHIVED / UNUSED

This directory contains the initial prototype for the **v3.2 Domain-Driven Blackboard Architecture** referenced in `ARCHITECTURE_GOVERNANCE.md`.

### Why was it archived?
1. **Never Implemented:** The files in this directory (`MarketBot`, `DecisionBot`, `SignalBot`, `PortfolioBot`, `OMSBot`, `CompanyOrchestrator`, etc.) were incomplete stub skeletons with dummy return values (e.g. `why_not=["Decision logic not fully migrated"]`, `rejection_reason="Unimplemented"`).
2. **Evolution to v5.0 Pipelines:** The production trading system moved forward with the hardened pipeline architecture in `core/pipelines/` driven by `main.py`, `core/orchestrator.py`, and the 23 active AI agents in `agents/`.
3. **Prevention of Confusion:** Archived on 2026-09-06 to ensure the active codebase remains clean, unambiguous, and focused on the production v5.0 pipeline.
