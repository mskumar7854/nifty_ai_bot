import pytest
from datetime import datetime, timedelta
from core.trade_filter import TradeFilter, FilterResult
from core.risk_manager import RiskManager
from models import Signal, SignalType, Direction, Strength, MarketRegime, SignalGrade
from config.settings import Settings

def _generate_mock_signals(regime: MarketRegime, count: int, start_time: datetime, is_high_ev: bool = False):
    signals = []
    current_time = start_time
    for i in range(count):
        conf = 85.0 if is_high_ev else 65.0
        if conf > 80: grade = SignalGrade.A
        elif conf > 70: grade = SignalGrade.B_PLUS
        else: grade = SignalGrade.C

        signal = Signal(
            id=f"sim_sig_{regime.name}_{i}",
            timestamp=current_time, signal_type=SignalType.BUY_CE, direction=Direction.BULLISH,
            confidence=conf, strength=Strength.MODERATE, entry_price=100.0,
            stop_loss=90.0, target_1=120.0 if is_high_ev else 105.0, position_size=50,
            regime=regime, reasons=["regression test"], warnings=[], grade=grade
        )
        signals.append(signal)
        current_time += timedelta(minutes=5)
    return signals

def test_v21_vs_baseline_2026_07_23():
    settings = Settings()
    trade_filter_v2 = TradeFilter(settings)

    def baseline_evaluate(signal): return True 

    start_time = datetime(2026, 7, 23, 10, 0)
    signals = []
    signals.extend(_generate_mock_signals(MarketRegime.TRENDING_UP, 20, start_time, is_high_ev=False)) 
    signals.extend(_generate_mock_signals(MarketRegime.TRENDING_UP, 11, start_time + timedelta(hours=2), is_high_ev=True))

    baseline_executions = 0
    v2_executions = 0

    for sig in signals:
        if baseline_evaluate(sig): baseline_executions += 1
            
        res = trade_filter_v2.evaluate(
            signal=sig, snapshot=None, agent_outputs={}, regime_info={"regime": sig.regime.name},
            structure_info={"structure": "CONTINUATION"}, learning_info={"confidence": sig.confidence, "current_streak": 0},
            decay_info={"theta_pct_per_hour": 0.5, "iv_crushing": False}, cost_info={"total_costs": 100},
            position_manager_status={"today_trades": v2_executions}, confluence_score=sig.confidence
        )
        
        if res.passed: v2_executions += 1

    assert baseline_executions == 31
    assert v2_executions < 10, f"V2.1 Executed too many trades: {v2_executions}"
    print(f"\n[2026-07-23 Regression] Baseline Executions: {baseline_executions} | V2.1 Executions: {v2_executions}")

def test_regime_specific_gating_choppy():
    settings = Settings()
    trade_filter_v2 = TradeFilter(settings)
    
    start_time = datetime(2026, 5, 6, 10, 0)
    signals = _generate_mock_signals(MarketRegime.VOLATILE, 15, start_time, is_high_ev=True)
    
    v2_executions = 0
    for sig in signals:
        res = trade_filter_v2.evaluate(
            signal=sig, snapshot=None, agent_outputs={}, regime_info={"regime": "CHOPPY"},
            structure_info={"structure": "UNKNOWN"}, learning_info={"confidence": sig.confidence, "current_streak": 0},
            decay_info={"theta_pct_per_hour": 0.5, "iv_crushing": False}, cost_info={"total_costs": 100},
            position_manager_status={"today_trades": v2_executions}, confluence_score=sig.confidence
        )
        if res.passed: v2_executions += 1
        
    assert v2_executions == 0, "V2.1 failed to block trades on CHOPPY day."

def test_regime_specific_gating_reversal():
    settings = Settings()
    trade_filter_v2 = TradeFilter(settings)
    
    start_time = datetime(2026, 5, 7, 10, 0)
    signals = _generate_mock_signals(MarketRegime.RANGING, 5, start_time, is_high_ev=True) 
    
    for sig in signals:
        sig.grade = SignalGrade.B_PLUS
        res = trade_filter_v2.evaluate(
            signal=sig, snapshot=None, agent_outputs={}, regime_info={"regime": "REVERSAL"},
            structure_info={"structure": "CONTINUATION"}, learning_info={"confidence": sig.confidence, "current_streak": 0},
            decay_info={"theta_pct_per_hour": 0.5, "iv_crushing": False}, cost_info={"total_costs": 100},
            position_manager_status={"today_trades": 0}, confluence_score=sig.confidence
        )
        assert not res.passed
        assert any(g["gate"] == "Regime-Aware Grade" and not g["pass"] for g in res.gate_details)
