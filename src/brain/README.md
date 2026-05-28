# src/brain/ — Auxiliary Cognitive Sub-modules

These files are **experimental / future components**. None are imported by the
production `brain.py` core.

| Module | Status | Notes |
|--------|--------|-------|
| `memory_recall.py` | Production-ready | `MultiHorizonMemoryRecall` — could be wired into brain |
| `feature_creator.py` | Stub | Pending implementation |
| `graph_flow.py` | Stub | Pending implementation |
| `hdc_engine.py` | Stub | Hyperdimensional computing — future |
| `hedging_agent.py` | Stub | Pending implementation |
| `interrogator.py` | Stub | Pending implementation |
| `prediction_buffer.py` | Stub | Pending implementation |
| `prompt_evolver.py` | Stub | Pending implementation |
| `reflex_model.py` | Stub | Pending implementation |
| `scent_detector.py` | Stub | Pending implementation |
| `snn_inference.py` | Stub | Spiking neural net — future |
| `supply_monitor.py` | Stub | Pending implementation |

## Production brain logic lives in:
- `src/brain.py` — TradingBrain orchestrator
- `src/brain_fsm.py` — TradingState enum
- `src/brain_state.py` — DrawdownLadder, MorningBudget, ConsecutiveLossTracker
- `src/brain_reconcile.py` — BrokerReconciler mixin
- `src/brain_health.py` — HealthChecker mixin
- `src/brain_data.py` — DataProvider mixin
- `src/brain_accounting.py` — AccountingMixin
- `src/brain_execution.py` — ExecutionMixin
- `src/brain_position.py` — PositionMonitor mixin

> **Do NOT add `__init__.py` here** — it would shadow `src/brain.py` and break all imports.
