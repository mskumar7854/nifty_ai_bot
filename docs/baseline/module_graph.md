# Module Dependency Graph Baseline

### `agents/__init__.py`
- imports `agents.consolidation_agent`
- imports `agents.correlation_agent`
- imports `agents.decay_agent`
- imports `agents.delta_gamma_agent`
- imports `agents.expiry_agent`
- imports `agents.expiry_day_agent`
- imports `agents.gap_agent`
- imports `agents.institutional_agent`
- imports `agents.learning_agent`
- imports `agents.level_agent`
- imports `agents.market_agent`
- imports `agents.momentum_agent`
- imports `agents.multi_timeframe_agent`
- imports `agents.oi_agent`
- imports `agents.order_flow_agent`
- imports `agents.price_action_agent`
- imports `agents.regime_agent`
- imports `agents.risk_agent`
- imports `agents.sentiment_agent`
- imports `agents.structure_agent`
- imports `agents.time_session_agent`
- imports `agents.trap_agent`
- imports `agents.volatility_agent`

### `agents/base_agent.py`
- imports `models.signals`

### `agents/consolidation_agent.py`
- imports `agents.base_agent`
- imports `models.signals`

### `agents/correlation_agent.py`
- imports `agents.base_agent`
- imports `models.signals`

### `agents/decay_agent.py`
- imports `agents.base_agent`
- imports `models.signals`

### `agents/delta_gamma_agent.py`
- imports `agents.base_agent`
- imports `models.signals`

### `agents/expiry_agent.py`
- imports `agents.base_agent`
- imports `models.signals`

### `agents/expiry_day_agent.py`
- imports `agents.base_agent`
- imports `models.signals`

### `agents/gap_agent.py`
- imports `agents.base_agent`
- imports `models.signals`

### `agents/institutional_agent.py`
- imports `agents.base_agent`
- imports `models.signals`

### `agents/learning_agent.py`
- imports `agents.base_agent`
- imports `agents.learning_agent_v2`
- imports `models.signals`

### `agents/learning_agent_v2.py`
- No local dependencies

### `agents/level_agent.py`
- imports `agents.base_agent`
- imports `models.signals`

### `agents/market_agent.py`
- imports `agents.base_agent`
- imports `models.signals`

### `agents/momentum_agent.py`
- imports `agents.base_agent`
- imports `models.signals`

### `agents/multi_timeframe_agent.py`
- imports `agents.base_agent`
- imports `models.signals`

### `agents/oi_agent.py`
- imports `agents.base_agent`
- imports `models.signals`

### `agents/order_flow_agent.py`
- imports `agents.base_agent`
- imports `models.signals`

### `agents/price_action_agent.py`
- imports `agents.base_agent`
- imports `models.signals`

### `agents/regime_agent.py`
- imports `agents.base_agent`
- imports `models.signals`

### `agents/risk_agent.py`
- imports `agents.base_agent`
- imports `models.signals`

### `agents/sentiment_agent.py`
- imports `agents.base_agent`
- imports `models.signals`

### `agents/structure_agent.py`
- imports `agents.base_agent`
- imports `models.signals`

### `agents/time_session_agent.py`
- imports `agents.base_agent`
- imports `models.signals`

### `agents/trap_agent.py`
- imports `agents.base_agent`
- imports `models.signals`

### `agents/volatility_agent.py`
- imports `agents.base_agent`
- imports `models.signals`

### `analytics/__init__.py`
- No local dependencies

### `analytics/agent_attribution.py`
- imports `analytics.analytics_bus`

### `analytics/analytics_bus.py`
- No local dependencies

### `analytics/attribution_readiness.py`
- imports `analytics.confidence_calibration`

### `analytics/confidence_calibration.py`
- imports `analytics.analytics_bus`

### `analytics/confidence_diagnostics.py`
- No local dependencies

### `analytics/coverage_monitor.py`
- imports `analytics.analytics_bus`

### `analytics/daily_summarizer.py`
- No local dependencies

### `analytics/data_quality.py`
- imports `analytics.analytics_bus`

### `analytics/edge_waterfall.py`
- imports `analytics.analytics_bus`

### `analytics/execution_analytics.py`
- imports `analytics.analytics_bus`

### `analytics/regime_attribution.py`
- imports `analytics.analytics_bus`
- imports `analytics.confidence_calibration`

### `analytics/trade_quality.py`
- imports `analytics.analytics_bus`

### `core/__init__.py`
- imports `core.alert_manager`
- imports `core.data_manager`
- imports `core.decision_engine`
- imports `core.trade_logger`

### `core/alert_manager.py`
- imports `models.signals`

### `core/burnin_tracker.py`
- imports `core.execution_fidelity`

### `core/confidence_calibrator.py`
- No local dependencies

### `core/confluence_scorer.py`
- imports `models.signals`

### `core/data_manager.py`
- imports `core.options_resolver`
- imports `core.regime_classifier`
- imports `core.regime_state_manager`
- imports `core.session_guard`
- imports `core.system_state`
- imports `models.signals`

### `core/db_manager.py`
- No local dependencies

### `core/decision_engine.py`
- imports `agents`
- imports `models.signals`

### `core/decision_engine_v2.py`
- imports `agents`
- imports `core.confluence_scorer`
- imports `core.signal_quality`
- imports `models.signals`

### `core/decision_engine_v3.py`
- imports `agents`
- imports `analytics.analytics_bus`
- imports `core.confidence_calibrator`
- imports `core.confluence_scorer`
- imports `core.gap_penalty_manager`
- imports `core.memory_manager`
- imports `core.signal_lifecycle`
- imports `core.signal_quality`
- imports `core.system_fingerprint`
- imports `core.threshold_tuner`
- imports `models.signals`

### `core/discipline_engine.py`
- No local dependencies

### `core/economics.py`
- No local dependencies

### `core/entry_engine.py`
- imports `models.signals`

### `core/execution_fidelity.py`
- No local dependencies

### `core/exit_engine.py`
- No local dependencies

### `core/gap_penalty_manager.py`
- No local dependencies

### `core/log_observer.py`
- No local dependencies

### `core/master_decision_engine.py`
- imports `core.state_tracker`

### `core/memory_manager.py`
- imports `core.db_manager`

### `core/metrics_engine.py`
- No local dependencies

### `core/metrics_logger.py`
- No local dependencies

### `core/oms.py`
- No local dependencies

### `core/options_resolver.py`
- No local dependencies

### `core/order_tracker.py`
- No local dependencies

### `core/position_manager.py`
- imports `analytics.analytics_bus`
- imports `core.economics`
- imports `core.oms`
- imports `core.shadow_execution`
- imports `core.system_state`
- imports `models.signals`
- imports `models.trade_record`

### `core/readiness_scorer.py`
- No local dependencies

### `core/reconciliation.py`
- imports `core.oms`

### `core/regime_adapter.py`
- imports `models.signals`

### `core/regime_classifier.py`
- No local dependencies

### `core/regime_detector.py`
- imports `agents.base_agent`
- imports `models.signals`

### `core/regime_state_manager.py`
- imports `core.regime_classifier`

### `core/replay_analytics.py`
- imports `core.replay_simulator`

### `core/replay_simulator.py`
- No local dependencies

### `core/risk_manager.py`
- No local dependencies

### `core/session_guard.py`
- No local dependencies

### `core/session_strategy.py`
- imports `core.session_guard`
- imports `models.signals`

### `core/shadow_execution.py`
- imports `core.execution_fidelity`

### `core/signal_formatter.py`
- imports `models.signals`

### `core/signal_lifecycle.py`
- No local dependencies

### `core/signal_quality.py`
- imports `models.signals`

### `core/simulation_engine.py`
- imports `core.burnin_tracker`
- imports `core.execution_fidelity`
- imports `models.signals`

### `core/slippage_model.py`
- No local dependencies

### `core/snapshot.py`
- No local dependencies

### `core/state_tracker.py`
- No local dependencies

### `core/structural_breaker.py`
- No local dependencies

### `core/system_fingerprint.py`
- No local dependencies

### `core/system_state.py`
- No local dependencies

### `core/telegram_controller.py`
- imports `core.session_guard`
- imports `core.signal_formatter`
- imports `core.system_state`
- imports `models.signals`

### `core/telemetry/__init__.py`
- No local dependencies

### `core/telemetry/rejection_schema.py`
- No local dependencies

### `core/threshold_tuner.py`
- No local dependencies

### `core/trade_filter.py`
- imports `core.telemetry.rejection_schema`
- imports `models.signals`

### `core/trade_filter_rewrite.py`
- imports `core.telemetry.rejection_schema`
- imports `models.signals`

### `core/trade_logger.py`
- imports `models.signals`

### `main.py`
- imports `core.alert_manager`
- imports `core.burnin_tracker`
- imports `core.data_manager`
- imports `core.decision_engine_v3`
- imports `core.discipline_engine`
- imports `core.entry_engine`
- imports `core.exit_engine`
- imports `core.log_observer`
- imports `core.master_decision_engine`
- imports `core.metrics_engine`
- imports `core.metrics_logger`
- imports `core.oms`
- imports `core.options_resolver`
- imports `core.position_manager`
- imports `core.readiness_scorer`
- imports `core.reconciliation`
- imports `core.regime_adapter`
- imports `core.risk_manager`
- imports `core.session_guard`
- imports `core.session_strategy`
- imports `core.simulation_engine`
- imports `core.slippage_model`
- imports `core.snapshot`
- imports `core.structural_breaker`
- imports `core.system_state`
- imports `core.telegram_controller`
- imports `core.telemetry.rejection_schema`
- imports `core.trade_filter`
- imports `core.trade_logger`
- imports `models.signals`

### `models/__init__.py`
- imports `models.signals`

### `models/signals.py`
- No local dependencies

### `models/trade_record.py`
- No local dependencies

### `nifty_strategy/config.py`
- No local dependencies

### `nifty_strategy/data_provider.py`
- imports `config`

### `nifty_strategy/indicators.py`
- imports `config`

### `nifty_strategy/main.py`
- imports `config`

### `nifty_strategy/options_selector.py`
- imports `config`

### `nifty_strategy/paper_trader.py`
- No local dependencies

### `nifty_strategy/risk_manager.py`
- imports `config`

### `nifty_strategy/signal_bridge.py`
- imports `config`
- imports `models.trade_record`

### `nifty_strategy/strategy.py`
- imports `config`

### `nifty_strategy/test_strategy.py`
- imports `config`

### `nifty_strategy/trade_executor.py`
- imports `config`
- imports `models.trade_record`

