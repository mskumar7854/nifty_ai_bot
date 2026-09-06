# Nifty AI - Telemetry & Execution Contract

This document explicitly defines the architectural invariants and telemetry contract for the Nifty AI trading system. These invariants guarantee that the Operations Console always reflects the canonical truth of the backend execution state, preventing silent state corruption, data loss, or misleading metrics.

**Status: COMPLETE / FROZEN (v5.0-VAL-1)**

---

## 1. Architectural Invariants

The following invariants constitute the permanent telemetry contract of the system. Future feature development must respect these boundaries:

1. **No Frontend Reconstruction of Execution Truth**: The Operations Console must never derive, infer, or reconstruct execution state from timestamps, logs, or secondary attributes. It strictly renders the canonical `status_data` provided by the backend Orchestrator.
2. **Every Execution has Canonical Correlation Identity**: A deterministic identifier (e.g., `decision_id` or `snapshot_id`) serves as the primary canonical correlation key across MarketSnapshot -> DecisionSnapshot -> GateEvaluation -> OMS Intent -> Order -> Position -> Outcome.
3. **Every Filled Order Resolves to Open or Closed State**: Silent disappearance of orders is strictly prohibited. The invariant `Filled = Open + Closed` must continually hold.
4. **Failed/Cancelled Orders Never Create Positions**: Orders that terminate via rejection or cancellation must immediately register in the exact terminal state (Failed or Cancelled) and guarantee zero resultant open positions.
5. **Every Rejection has Authoritative Gate Provenance**: A blocked trade must include a strict, auditable causal chain (e.g., `passed = false`, `actual = SAME_STRUCTURAL_TREND`, `requirement = NEW_STRUCTURAL_STATE_REQUIRED`). "Ghost rejections" without gate matrix evidence are forbidden.
6. **Decision-Time Market Data is Distinct from Live Market Data**: The system must explicitly disambiguate `market.live_nifty` (current spot, updated on tick) from `snapshot.spot_price` (the deterministic snapshot data at the exact moment of signal evaluation).
7. **Reconciliation Mismatches are Surfaced, Never Hidden**: Any failure in invariant calculus (e.g., `Filled != Open + Closed`) must actively raise a `MISMATCH` alarm on the Operations Console. The system must never auto-correct or mask impossible states.
8. **Execution Ledger is Separated from Outcome/P&L Ledger**: Every filled order appears in Today's Execution Ledger immediately as `Outcome: OPEN`. Realized P&L, Win Rate, and Closed Outcomes are calculated strictly from `CLOSED` trades.
9. **Crash Recovery Enforces Strict State Semantics**: Only confirmed fills (`ENTRY_FILLED`, `FILLED_ACTIVE`, `PARTIAL_FILLED`) hydrate active `OpenPosition` objects on process restart. Pending in-flight submissions (`ENTRY_SUBMITTED`) are logged as pending orders and never create phantom open positions.
10. **Telemetry Tests Remain Part of the Permanent Regression Suite**: Execution invariants must be continuously validated via `pytest tests/test_dashboard_invariants.py` (7 permanent lifecycle scenarios).

---

## 2. Operational Invariant Mapping

**Every terminal execution event must be observable in exactly one lifecycle category:**

* **ENTRY_SUBMITTED** -> `PENDING ORDER` -> (No OpenPosition until fill)
* **ENTRY_FILLED** -> `OPEN POSITION` (in Execution Ledger as `OPEN`)
* **POSITION_CLOSED** -> `CLOSED OUTCOME` (in Execution Ledger as `WIN/LOSS`, contributing to realized P&L)
* **FAILED** -> `FAILED` -> `NO POSITION`
* **CANCELLED** -> `CANCELLED` -> `NO POSITION`

---

## 3. Quantity-Based Reconciliation Assumption

**Note for future scaling:** 
Currently, the execution lifecycle assumes a strictly **record-count-based** model (one-fill equates to one-position). The current calculus (`Filled Orders = Open Positions + Closed Outcomes`) correctly governs this paradigm.

If the OMS evolves to support advanced scale-in/scale-out architectures—including partial fills, partial exits, or aggregated orders—this reconciliation model must be migrated to a **quantity-based invariant**:

`Filled Quantity = Open Quantity + Closed Quantity`

This ensures that partial executions strictly respect the underlying topological rules of position accounting.
