import os, re

base = r'c:/Users/Selva/Downloads/nifty-ai-system'

checks = [
    # (description, file, search_term)
    ('position_manager open_position', 'core/position_manager.py', 'def open_position'),
    ('can_trade in position_manager', 'core/position_manager.py', 'can_trade'),
    ('risk_manager update_daily_pnl', 'core/risk_manager.py', 'def update_daily_pnl'),
    ('discipline_engine class', 'core/discipline_engine.py', 'class DisciplineEngine'),
    ('trade_filter evaluate', 'core/trade_filter.py', 'def evaluate'),
    ('AGENT_WEIGHTS in signal_weights', 'config/signal_weights.py', 'AGENT_WEIGHTS'),
    ('MIN_CONFIDENCE in signal_weights', 'config/signal_weights.py', 'MIN_CONFIDENCE'),
    ('MIN_DIRECTION_GAP in weights', 'config/signal_weights.py', 'MIN_DIRECTION_GAP'),
    ('dhan_client get_dhan_client', 'dhan_client.py', 'get_dhan_client'),
    ('memory_manager class', 'core/memory_manager.py', 'class MemoryManager'),
    ('entry_engine cancel_all_pending', 'core/entry_engine.py', 'cancel_all_pending'),
    ('exit_engine daily_target_hit', 'core/exit_engine.py', 'daily_target_hit'),
    ('simulation_engine class', 'core/simulation_engine.py', 'class SimulationEngine'),
    ('confluence_scorer class', 'core/confluence_scorer.py', 'class ConfluenceScorer'),
    ('signal_quality_grader class', 'core/signal_quality.py', 'class SignalQualityGrader'),
    ('Signal id field in signals.py', 'models/signals.py', r'id: str'),
    ('MarketRegime enum', 'models/signals.py', 'class MarketRegime'),
    ('SignalGrade enum', 'models/signals.py', 'class SignalGrade'),
    ('InstrumentConfig in settings', 'config/settings.py', 'class InstrumentConfig'),
    ('TradeFilterConfig in settings', 'config/settings.py', 'class TradeFilterConfig'),
    ('EnginePipelineConfig in settings', 'config/settings.py', 'class EnginePipelineConfig'),
    ('session_strategy class', 'core/session_strategy.py', 'class SessionStrategy'),
    ('slippage_model class', 'core/slippage_model.py', 'class SlippageModel'),
    ('trade_logger class', 'core/trade_logger.py', 'class TradeLogger'),
    ('metrics_engine class', 'core/metrics_engine.py', 'class MetricsEngine'),
    ('AgentLogger info method', 'utils/logger.py', 'def info'),
    ('is_paused in telegram', 'core/telegram_controller.py', 'is_paused'),
    ('kill_cmd in telegram', 'core/telegram_controller.py', 'def kill_cmd'),
    ('boot_recovery in telegram', 'core/telegram_controller.py', 'def boot_recovery'),
    ('phase_1_gatekeepers in settings', 'config/settings.py', 'phase_1_gatekeepers'),
    ('phase_4_risk in settings', 'config/settings.py', 'phase_4_risk'),
    ('_get_dynamic_confirmation_route', 'core/decision_engine_v3.py', '_get_dynamic_confirmation_route'),
    ('compute_weighted_score', 'core/decision_engine_v3.py', 'def compute_weighted_score'),
    ('data_manager fetch_latest_async', 'core/data_manager.py', 'fetch_latest_async'),
    ('options_analyzer pcr', 'options_analyzer.py', 'pcr'),
    ('master_decision_engine approve', 'core/master_decision_engine.py', 'def approve'),
    ('squeeze_threshold in ThresholdConfig', 'config/settings.py', 'squeeze_threshold'),
    ('dashboard update_status', 'web/dashboard.py', 'def update_status'),
    ('signal_queue in telegram', 'core/telegram_controller.py', 'signal_queue'),
    ('_classify_market method', 'core/decision_engine_v3.py', 'def _classify_market'),
    ('halt_trading in main', 'main.py', 'def halt_trading'),
    ('trading_enabled flag in main', 'main.py', 'self.trading_enabled'),
    ('engine_errors counter', 'main.py', 'self.engine_errors'),
    ('execution_failures counter', 'main.py', 'self.execution_failures'),
    ('circuit breaker exec failures', 'main.py', 'execution_failures > 3'),
    ('circuit breaker engine errors', 'main.py', 'engine_errors > 10'),
    ('stop_cmd registered in main', 'main.py', 'stop_cmd'),
    ('emit_signal in dashboard', 'web/dashboard.py', 'def emit_signal'),
    ('SocketIO in dashboard', 'web/dashboard.py', 'SocketIO'),
    ('gevent async_mode in dashboard', 'web/dashboard.py', 'gevent'),
    ('global error handler in dashboard', 'web/dashboard.py', 'errorhandler'),
    ('stop_cmd in telegram controller', 'core/telegram_controller.py', 'def stop_cmd'),
    ('notify_halt in telegram controller', 'core/telegram_controller.py', 'def notify_halt'),
    ('gevent in requirements', 'requirements.txt', 'gevent'),
    ('flask-socketio in requirements', 'requirements.txt', 'Flask-SocketIO'),
    ('healthcheck in docker-compose', 'docker-compose.yml', 'healthcheck'),
    ('restart always in docker-compose', 'docker-compose.yml', 'restart: always'),
    ('curl in Dockerfile', 'Dockerfile', 'curl'),
    ('_reconcile_broker_positions', 'main.py', '_reconcile_broker_positions'),
]

passed, failed, missing = [], [], []

for desc, fpath, term in checks:
    full = os.path.join(base, fpath).replace('/', os.sep)
    if not os.path.exists(full):
        missing.append((desc, fpath))
        continue
    with open(full, encoding='utf-8', errors='ignore') as f:
        content = f.read()
    if re.search(term, content):
        passed.append((desc, fpath))
    else:
        failed.append((desc, fpath))

print("=" * 60)
print("FAILS (Documented but NOT found in code):")
print("=" * 60)
for desc, fp in failed:
    print(f"  FAIL | {fp} | {desc}")

print()
print("=" * 60)
print("MISSING FILES:")
print("=" * 60)
for desc, fp in missing:
    print(f"  MISSING | {fp} | {desc}")

print()
print("=" * 60)
print(f"RESULT: {len(passed)} PASS  |  {len(failed)} FAIL  |  {len(missing)} FILE MISSING")
print("=" * 60)
