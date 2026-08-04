import pytest
from datetime import datetime
from core.confidence_calibrator import ConfidenceCalibrator
from core.expected_value_engine import ExpectedValueEngine
from core.opportunity_ranker import OpportunityRanker
from core.trend_structure_tracker import TrendStructureTracker
from core.trade_filter import TradeFilter, FilterResult
from models import Signal, SignalGrade, Direction, MarketRegime, SignalType, Strength
from config.settings import Settings



def test_confidence_calibrator():
    calibrator = ConfidenceCalibrator()
    
    # Fractional input
    cal_trending, _ = calibrator.calibrate(0.85, "TRENDING_DOWN")
    assert 0.50 <= cal_trending <= 0.85
    
    # Continuous Platt fallback
    cal_platt, _ = calibrator.calibrate(0.92, "CUSTOM_REGIME")
    assert 0.10 <= cal_platt <= 0.95


def test_expected_value_engine():
    ev_engine = ExpectedValueEngine(min_ev_r=0.50, min_ev_score=60.0)
    
    # High EV setup (Pwin=0.75, RR=2.5) -> Should PASS
    high_ev = ev_engine.evaluate(calibrated_pwin=0.75, risk_reward_ratio=2.5, spread_pct=0.5)
    assert high_ev["passes_gate"] is True
    assert high_ev["ev_r"] > 0.50
    assert high_ev["normalized_score"] >= 60.0
    
    # Low EV setup (Pwin=0.40, RR=1.2) -> Should FAIL
    low_ev = ev_engine.evaluate(calibrated_pwin=0.40, risk_reward_ratio=1.2, spread_pct=1.0)
    assert low_ev["passes_gate"] is False
    assert low_ev["ev_r"] < 0.50


def test_opportunity_ranker():
    ranker = OpportunityRanker()
    
    candidates = [
        {"id": "setup_1", "ev_score": 65.0, "calibrated_pwin": 0.60, "grade": "B+", "liquidity_score": 80.0},
        {"id": "setup_2", "ev_score": 90.0, "calibrated_pwin": 0.78, "grade": "A+", "liquidity_score": 90.0},
        {"id": "setup_3", "ev_score": 50.0, "calibrated_pwin": 0.45, "grade": "C", "liquidity_score": 60.0},
    ]
    
    ranked = ranker.rank_candidates(candidates, max_select=1)
    assert len(ranked) == 1
    assert ranked[0]["id"] == "setup_2"  # Elite setup ranked #1


def test_trend_structure_tracker():
    tracker = TrendStructureTracker(max_reentry_per_trend=2)
    
    # First trade in BEARISH trend -> Allowed
    ok1, _, _ = tracker.check_reentry_allowed("BEARISH")
    assert ok1 is True
    tracker.record_trade_execution("BEARISH", 24000.0)
    
    # Second trade without structural reset -> Allowed (within max limit 2)
    ok2, _, _ = tracker.check_reentry_allowed("BEARISH")
    assert ok2 is True
    tracker.record_trade_execution("BEARISH", 23980.0)
    
    # Third trade without structural reset -> REJECTED
    ok3, reason3, _ = tracker.check_reentry_allowed("BEARISH")
    assert ok3 is False
    assert "REJECTED_SAME_STRUCTURAL_TREND" in reason3
    
    # Register BOS structural reset event
    tracker.register_structural_event("BOS")
    
    # Re-entry after structural reset -> Allowed!
    ok4, reason4, _ = tracker.check_reentry_allowed("BEARISH")
    assert ok4 is True
    assert "STRUCTURAL_RESET_CONFIRMED" in reason4


def test_regime_aware_grade_gate():
    settings = Settings()
    trade_filter = TradeFilter(settings)
    
    # Create Signal with Grade B+
    signal = Signal(
        id="test_sig_001",
        timestamp=datetime.now(),
        signal_type=SignalType.BUY_PE,
        direction=Direction.BEARISH,
        confidence=80.0,
        strength=Strength.STRONG,
        buy_score=0.0,
        sell_score=0.8,
        regime=MarketRegime.TRENDING_DOWN,
        position_size=50,
        stop_loss=24050.0,
        target_1=23900.0,
        warnings=[]
    )
    signal.grade = SignalGrade.B_PLUS

    
    # Evaluated in TRENDING_DOWN -> Grade B+ is ALLOWED (Required: B+)
    res_trending = trade_filter.evaluate(
        signal=signal,
        snapshot=type("Snapshot", (), {"price": 24000.0, "atr": 10.0, "spread_pct": 0.5, "vix": 14.0})(),
        agent_outputs={},
        regime_info={"regime": "TRENDING_DOWN"},
        structure_info={"structure": "OK"},
        learning_info={"confidence": 80, "current_streak": 1},
        decay_info={"theta_pct_per_hour": 1.0, "iv_crushing": False},
        cost_info={"total_costs": 40.0, "break_even_points": 2.0},
        position_manager_status={"today_trades": 1},
        confluence_score=80.0
    )
    # Check that Gate 10 (Regime-Aware Grade) passed
    g10 = [g for g in res_trending.gate_details if g["gate"] == "Regime-Aware Grade"][0]
    assert g10["pass"] is True
    
    # Evaluated in RANGING -> Grade B+ is REJECTED (Required: A+)
    res_ranging = trade_filter.evaluate(
        signal=signal,
        snapshot=type("Snapshot", (), {"price": 24000.0, "atr": 10.0, "spread_pct": 0.5, "vix": 14.0})(),
        agent_outputs={},
        regime_info={"regime": "RANGING"},
        structure_info={"structure": "OK"},
        learning_info={"confidence": 80, "current_streak": 1},
        decay_info={"theta_pct_per_hour": 1.0, "iv_crushing": False},
        cost_info={"total_costs": 40.0, "break_even_points": 2.0},
        position_manager_status={"today_trades": 1},
        confluence_score=80.0
    )
    g10_ranging = [g for g in res_ranging.gate_details if g["gate"] == "Regime-Aware Grade"][0]
    assert g10_ranging["pass"] is False
    assert "Required: A+" in g10_ranging["detail"]

