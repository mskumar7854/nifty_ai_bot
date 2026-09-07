import time
from datetime import datetime
from unittest.mock import MagicMock
import pandas as pd
import pytest

from config.settings import Settings
from core.decision_engine import DecisionEngine
from core.pipelines.decision_pipeline import DecisionPipeline
from models import MarketRegime, Signal, SignalType, Direction, Strength, MarketSnapshot
from models.regime import normalize_regime_family


@pytest.fixture
def settings():
    return Settings()


@pytest.fixture
def base_snapshot():
    return MarketSnapshot(
        timestamp=datetime.now(),
        price=23670.0,
        open=23720.0,
        high=23725.0,
        low=23665.0,
        close=23670.0,
        volume=150000,
        vwap=23710.0,
        rsi=42.0,
        ema_fast=23700.0,
        ema_slow=23715.0,
        atr=25.0,
        total_ce_oi=6000000,
        total_pe_oi=4500000,
        pcr=0.75,
        max_pain=23700.0,
        india_vix=14.5,
        bb_upper=23750.0,
        bb_lower=23700.0,
        bb_width=1.5,  # Normal width (> 0.5 squeeze_threshold)
    )


@pytest.fixture
def mock_pipeline_ctx(settings):
    class MockContext:
        def __init__(self, s):
            self.settings = s
            self.system = MagicMock()
            self.telemetry = MagicMock()
            self.telemetry.metrics_logger = MagicMock()
            self.data_manager = MagicMock()
            self.simulation = None
            self.is_simulation = False

    return MockContext(settings)


class TestRegimeInvariantsAndFreeze:
    """
    Test Suite for 09:49 Spike Freeze State Consistency & Diagnostic Regime Invariant.
    Validates:
    - Step 1: _classify_market priority & safeguards
    - Step 2: _no_trade_signal regime confidence & metadata
    - Step 3: decision_status explicit taxonomy in canonical truth
    - Step 4: Normalized regime invariant (compatible aliases vs actual drift)
    - Step 5-8: Complete 8-test verification matrix
    """

    def test_1_halt_cycle_uses_snapshot_regime_state_not_breakout(self, settings, base_snapshot):
        """
        Test 1: During freeze halt, _classify_market uses snapshot.regime_state (TREND_DOWN),
        not the accidental BREAKOUT heuristic caused by price < bb_lower.
        """
        engine = DecisionEngine(settings)
        # Price is below bb_lower (23670 < 23700), which would trigger BREAKOUT if uncorrected
        assert base_snapshot.price < base_snapshot.bb_lower

        # Attach confirmed regime from RegimeStateManager
        base_snapshot.regime_state = {
            "regime": "TREND_DOWN",
            "confidence": 0.72,
            "volatility_state": "NORMAL",
            "trend_strength": 0.65,
            "tradability": 0.80
        }

        # Activate intraday spike freeze
        engine.spike_freeze_until = time.time() + 600

        # Direct classification test
        classified = engine._classify_market(base_snapshot, outputs={})
        assert classified == MarketRegime.TREND_DOWN

        # Engine cycle test
        signal = engine.process(pd.DataFrame(), base_snapshot)
        assert signal.signal_type == SignalType.NO_TRADE
        assert signal.regime == MarketRegime.TREND_DOWN
        assert signal.regime != MarketRegime.BREAKOUT

    def test_2_halt_cycle_populates_regime_conf_from_snapshot_state(self, settings, base_snapshot):
        """
        Test 2: Halt signal extracts regime confidence from snapshot.regime_state
        and sets structured metadata: regime_conf, rejection_reason, is_halted.
        """
        engine = DecisionEngine(settings)
        base_snapshot.regime_state = {
            "regime": "TREND_DOWN",
            "confidence": 0.78,
        }
        engine.spike_freeze_until = time.time() + 600

        signal = engine.process(pd.DataFrame(), base_snapshot)
        assert signal.signal_type == SignalType.NO_TRADE
        assert signal.metadata.get("regime_conf") == 0.78
        assert "Phase 2 Halt: Intraday Spike Freeze active" in signal.metadata.get("rejection_reason", "")
        assert signal.metadata.get("is_halted") is True

    def test_3_decision_status_is_halted_in_canonical_truth(self, settings, mock_pipeline_ctx, base_snapshot):
        """
        Test 3: Canonical truth explicitly sets decision_status = 'HALTED'
        and accurately logs regime and regime_confidence during a halt cycle.
        """
        pipeline = DecisionPipeline(mock_pipeline_ctx)
        base_snapshot.regime_state = {
            "regime": "TREND_DOWN",
            "confidence": 0.72,
        }
        pipeline.decision_engine.spike_freeze_until = time.time() + 600

        signal = pipeline.decision_engine.process(pd.DataFrame(), base_snapshot)

        latencies = {"fetch_ms": 5, "decision_ms": 10}
        pipeline._log_canonical_truth(
            signal=signal,
            cycle_count=821,
            auth=False,
            reason=signal.reasons[0],
            latencies=latencies
        )

        mock_logger = mock_pipeline_ctx.telemetry.metrics_logger
        assert mock_logger.log_cycle.called
        summary = mock_logger.log_cycle.call_args[0][0]

        assert summary["decision_status"] == "HALTED"
        assert summary["execution_authorized"] is False
        assert summary["opportunity_valid"] is False
        assert summary["regime"] == "TREND_DOWN"
        assert summary["regime_confidence"] == 0.72
        assert "Phase 2 Halt" in summary["rejection_reason"]

    def test_4_regime_invariant_passes_on_compatible_aliases(self, settings, mock_pipeline_ctx, base_snapshot):
        """
        Test 4: Regime invariant normalizes compatible aliases and asserts PASS:
        - STRONG_TREND_DOWN vs TREND_DOWN -> PASS
        - STRONG_TREND_UP vs TREND_UP -> PASS
        - RANGING vs RANGE -> PASS
        """
        pipeline = DecisionPipeline(mock_pipeline_ctx)

        # Test canonical family normalization directly
        assert normalize_regime_family(MarketRegime.STRONG_TREND_DOWN) == "TREND_DOWN"
        assert normalize_regime_family("STRONG_TREND_DOWN") == "TREND_DOWN"
        assert normalize_regime_family(MarketRegime.TREND_DOWN) == "TREND_DOWN"
        assert normalize_regime_family("TRENDING_DOWN") == "TREND_DOWN"
        assert normalize_regime_family(MarketRegime.STRONG_TREND_UP) == "TREND_UP"
        assert normalize_regime_family(MarketRegime.TREND_UP) == "TREND_UP"
        assert normalize_regime_family(MarketRegime.RANGING) == "RANGE"
        assert normalize_regime_family("RANGE") == "RANGE"
        assert normalize_regime_family(MarketRegime.SQUEEZE) == "RANGE"
        assert normalize_regime_family(MarketRegime.VOLATILE_CHOPPY) == "VOLATILE"
        assert normalize_regime_family(MarketRegime.BREAKOUT) == "BREAKOUT"

        # Evaluation invariant test: manager has STRONG_TREND_DOWN, execution signal has TREND_DOWN
        base_snapshot.regime_state = {"regime": "STRONG_TREND_DOWN", "confidence": 0.85}
        trade_signal = Signal(
            id="sig_test_001",
            timestamp=datetime.now(),
            signal_type=SignalType.BUY_PE,
            direction=Direction.BEARISH,
            confidence=75,
            strength=Strength.STRONG,
            entry_price=base_snapshot.price,
            regime=MarketRegime.TREND_DOWN,
            reasons=["Trend alignment"],
            metadata={}
        )

        record = pipeline._verify_regime_invariant(base_snapshot, trade_signal)
        assert record["status"] == "PASS"
        assert record["normalized_manager_regime"] == "TREND_DOWN"
        assert record["normalized_execution_regime"] == "TREND_DOWN"
        assert trade_signal.metadata["regime_invariant"]["status"] == "PASS"

    def test_5_regime_invariant_reports_drift_on_family_divergence(self, settings, mock_pipeline_ctx, base_snapshot):
        """
        Test 5: Regime invariant reports DRIFT on actual family divergence
        (TREND_DOWN vs RANGE) and UNVERIFIED_MISSING when data is missing.
        """
        pipeline = DecisionPipeline(mock_pipeline_ctx)

        # Divergence: manager = TREND_DOWN, execution = RANGE
        base_snapshot.regime_state = {"regime": "TREND_DOWN", "confidence": 0.80}
        divergent_signal = Signal(
            id="sig_drift_001",
            timestamp=datetime.now(),
            signal_type=SignalType.BUY_CE,
            direction=Direction.BULLISH,
            confidence=60,
            strength=Strength.MODERATE,
            entry_price=base_snapshot.price,
            regime=MarketRegime.RANGING,
            reasons=["Range bounce"],
            metadata={}
        )

        record = pipeline._verify_regime_invariant(base_snapshot, divergent_signal)
        assert record["status"] == "DRIFT"
        assert record["normalized_manager_regime"] == "TREND_DOWN"
        assert record["normalized_execution_regime"] == "RANGE"

        # Missing data: manager regime is None
        base_snapshot.regime_state = None
        missing_signal = Signal(
            id="sig_missing_001",
            timestamp=datetime.now(),
            signal_type=SignalType.BUY_PE,
            direction=Direction.BEARISH,
            confidence=70,
            strength=Strength.STRONG,
            entry_price=base_snapshot.price,
            regime=MarketRegime.TREND_DOWN,
            reasons=["Trend continuation"],
            metadata={}
        )

        record_missing = pipeline._verify_regime_invariant(base_snapshot, missing_signal)
        assert record_missing["status"] == "UNVERIFIED_MISSING"

    def test_6_freeze_strictness_and_no_execution_leak(self, settings, mock_pipeline_ctx, base_snapshot):
        """
        Test 6: Freeze strictness assertion.
        During freeze: execution_authorized == False, opportunity_valid == False,
        and execution adapters/OMS are NEVER called.
        """
        pipeline = DecisionPipeline(mock_pipeline_ctx)

        # Snapshot shows TREND_DOWN with high confidence
        base_snapshot.regime_state = {"regime": "TREND_DOWN", "confidence": 0.90}
        pipeline.decision_engine.spike_freeze_until = time.time() + 600

        # Spy on downstream execution components
        mock_pipeline_ctx.system.position_manager = MagicMock()
        mock_pipeline_ctx.system.oms = MagicMock()
        mock_pipeline_ctx.system.regime_adapter = MagicMock()

        # Run pipeline evaluate
        result = pipeline.evaluate(df=pd.DataFrame(), snapshot=base_snapshot, cycle_count=822)

        # 1. Pipeline result assertions
        assert result.approved is False
        assert result.signal is None
        assert "Phase 2 Halt: Intraday Spike Freeze active" in result.rejection_reason

        # 2. Assert no execution leak
        assert mock_pipeline_ctx.system.oms.place_order.called is False
        assert mock_pipeline_ctx.system.oms.execute.called is False
        assert mock_pipeline_ctx.system.position_manager.open_position.called is False

    def test_7_legacy_fallback_when_regime_sources_unavailable(self, settings, base_snapshot):
        """
        Test 7: Legacy fallback still works when outputs.regime and snapshot.regime_state are both None.
        Verifies priority layer did not delete or break indicator heuristics.
        """
        engine = DecisionEngine(settings)
        base_snapshot.regime_state = None
        outputs = {}

        # 1. Breakout: price < bb_lower, normal width
        base_snapshot.price = 23670.0
        base_snapshot.bb_lower = 23700.0
        base_snapshot.bb_upper = 23750.0
        base_snapshot.bb_width = 1.5
        assert engine._classify_market(base_snapshot, outputs) == MarketRegime.BREAKOUT

        # 2. Squeeze: bb_width < squeeze_threshold (0.5)
        base_snapshot.price = 23720.0
        base_snapshot.bb_width = 0.1
        assert engine._classify_market(base_snapshot, outputs) == MarketRegime.SQUEEZE

        # 3. Choppy: voting conflict (3 bulls vs 3 bears)
        base_snapshot.bb_width = 1.5
        conflict_outputs = {
            f"b_{i}": MagicMock(direction=Direction.BULLISH) for i in range(3)
        }
        conflict_outputs.update({
            f"s_{i}": MagicMock(direction=Direction.BEARISH) for i in range(3)
        })
        assert engine._classify_market(base_snapshot, conflict_outputs) == MarketRegime.VOLATILE_CHOPPY

        # 4. Ranging: inside bands, normal width
        base_snapshot.price = 23720.0
        assert engine._classify_market(base_snapshot, outputs) == MarketRegime.RANGING

    def test_8_malformed_snapshot_regime_state_safe_fallback(self, settings, base_snapshot):
        """
        Test 8: Malformed snapshot.regime_state (empty dict, non-dict, or invalid regime string)
        does not crash and falls back safely to indicator heuristics.
        """
        engine = DecisionEngine(settings)
        base_snapshot.price = 23720.0
        base_snapshot.bb_lower = 23700.0
        base_snapshot.bb_upper = 23750.0
        base_snapshot.bb_width = 1.5

        # Empty dict
        base_snapshot.regime_state = {}
        res = engine._classify_market(base_snapshot, outputs={})
        assert res == MarketRegime.RANGING

        # Unknown / garbage regime string
        base_snapshot.regime_state = {"regime": "NON_EXISTENT_CHAOTIC_REGIME_123"}
        res = engine._classify_market(base_snapshot, outputs={})
        assert res == MarketRegime.RANGING

        # String instead of dict
        base_snapshot.regime_state = "corrupted_string_state"
        res = engine._classify_market(base_snapshot, outputs={})
        assert res == MarketRegime.RANGING

        # Non-dict integer
        base_snapshot.regime_state = 99999
        res = engine._classify_market(base_snapshot, outputs={})
        assert res == MarketRegime.RANGING

    def test_9_spike_freeze_lifecycle_and_no_perpetual_extension(self, settings, base_snapshot):
        """
        Test 9: Spike freeze triggers on wide candle (>30 & >2*ATR), does NOT
        perpetually re-extend the timer during active freeze, and expires cleanly.
        """
        engine = DecisionEngine(settings)
        base_snapshot.atr = 12.0

        # 1. Wide candle (range = 40.0 > 30 and > 2 * 12 = 24)
        spike_ts = datetime.now()
        df_spike = pd.DataFrame([{
            'open': 23670.0,
            'high': 23700.0,
            'low': 23660.0,
            'close': 23690.0,
            'volume': 100000,
        }], index=pd.DatetimeIndex([spike_ts], name='timestamp'))

        # Process cycle 1: Spike triggers freeze
        sig1 = engine.process(df_spike, base_snapshot)
        assert sig1.signal_type == SignalType.NO_TRADE
        assert "Phase 2 Halt: Intraday Spike Freeze active" in sig1.reasons[0]
        initial_freeze_until = engine.spike_freeze_until
        assert initial_freeze_until > time.time() + 590

        # Process cycle 2 (subsequent tick on same or another spike candle while frozen):
        # Freeze timer MUST NOT be pushed forward
        time.sleep(0.05)
        sig2 = engine.process(df_spike, base_snapshot)
        assert sig2.signal_type == SignalType.NO_TRADE
        assert "Phase 2 Halt: Intraday Spike Freeze active" in sig2.reasons[0]
        assert engine.spike_freeze_until == initial_freeze_until  # Timer was not extended!

        # Process cycle 3: Simulate freeze expiry
        engine.spike_freeze_until = time.time() - 1  # Expired

        # Normal candle (range = 10.0, not a spike)
        normal_ts = spike_ts + pd.Timedelta(minutes=10)
        df_normal = pd.DataFrame([{
            'open': 23670.0,
            'high': 23675.0,
            'low': 23665.0,
            'close': 23672.0,
            'volume': 100000,
        }], index=pd.DatetimeIndex([normal_ts], name='timestamp'))

        sig3 = engine.process(df_normal, base_snapshot)
        # Freeze is cleared, no longer halted on spike freeze
        assert "Phase 2 Halt: Intraday Spike Freeze active" not in (sig3.reasons[0] if sig3.reasons else "")
