import time
import logging
from datetime import datetime
from typing import List, Optional, Tuple, Dict

from models import MarketSnapshot, Signal, PositionState, TradeHealth, ExitDecision, ExitDecisionType, PositionAction
from core.context import RuntimeContext

logger = logging.getLogger("position_pipeline")

class PositionPipeline:
    """
    Position Management Pipeline.
    Manages the lifecycle of an open position.
    
    Stages:
    1. Position State - Updates raw PnL, duration, prices.
    2. Trade Health - Evaluates momentum, regime, structure.
    3. Exit Decision - Answers 'Should this position continue to exist?'
    4. Position Actions - Generates actionable intents for ExecutionPipeline.
    """
    def __init__(self, ctx: RuntimeContext):
        self.ctx = ctx
        self.settings = ctx.settings

    def evaluate(self, position: PositionState, snapshot: MarketSnapshot, df=None, current_signal: Optional[Signal]=None) -> List[PositionAction]:
        """
        Runs the full lifecycle evaluation for an open position.
        """
        # ── Stage 1: Position State Update ──
        self._update_position_state(position, snapshot)
        
        # ── Stage 2: Trade Health ──
        self._evaluate_trade_health(position, snapshot, current_signal)
        
        # ── Stage 3: Exit Decision ──
        decision = self._make_exit_decision(position, snapshot)
        
        # ── Stage 4: Position Actions ──
        actions = self._generate_position_actions(position, decision)
        
        return actions

    def _update_position_state(self, pos, snapshot: MarketSnapshot):
        """Update PnL and duration metrics using proper option premium resolution."""
        # ── P0 Fix: Resolve current option premium (never raw spot) ──
        eval_price = snapshot.price
        
        # If position has instrument info (e.g. SimulatedTrade)
        if hasattr(pos, "instrument") and pos.instrument:
            data_manager = getattr(self.ctx, "data_manager", None)
            if data_manager:
                quote = data_manager.fetch_option_quote(
                    pos.instrument.get("strike"),
                    pos.instrument.get("type"),
                    pos.instrument.get("expiry")
                )
                if quote and quote.bid > 0:
                    eval_price = quote.bid
            
        # Tier 2: ATM proxy
        if eval_price == snapshot.price and hasattr(pos, "signal_type"):
            is_ce = "CE" in str(pos.signal_type)
            atm_premium = snapshot.atm_ce_premium if is_ce else snapshot.atm_pe_premium
            if atm_premium and atm_premium > 0:
                eval_price = atm_premium
                
        # Tier 3: Delta approx
        if eval_price == snapshot.price and (not getattr(snapshot, 'atm_ce_premium', 0) or getattr(snapshot, 'atm_ce_premium', 0) <= 0):
            spot_move = snapshot.price - pos.spot_entry if hasattr(pos, "spot_entry") else 0
            is_ce = "CE" in str(getattr(pos, "signal_type", ""))
            delta = 0.5 if is_ce else -0.5
            eval_price = max(0.05, pos.entry_price + (spot_move * delta))
        
        pos.current_price = round(eval_price, 2)
        
        direction_str = getattr(pos.direction, 'value', str(pos.direction)).upper()
        direction_mult = 1.0 if direction_str in ["BUY", "BULLISH"] else -1.0
        pos.unrealized_pnl = (pos.current_price - pos.entry_price) * pos.qty * direction_mult
        
        if pos.unrealized_pnl > pos.max_favorable:
            pos.max_favorable = pos.unrealized_pnl
        if pos.unrealized_pnl < pos.max_adverse:
            pos.max_adverse = pos.unrealized_pnl

    def _evaluate_trade_health(self, pos: PositionState, snapshot: MarketSnapshot, current_signal: Optional[Signal]):
        """Evaluate trade structure, momentum, and regime alignment."""
        # 1. Premium Efficiency (Expected vs Actual)
        efficiency_score = 100.0
        
        # 2. Momentum
        momentum_score = 50.0
        if current_signal and hasattr(current_signal, "momentum_score"):
            momentum_score = max(0.0, min(100.0, getattr(current_signal, "momentum_score", 50.0)))
            
        # 3. Confidence Decay
        confidence_score = 100.0
        if current_signal:
            current_conf = getattr(current_signal, "confidence", 100.0)
            drop = pos.confidence_at_entry - current_conf
            if current_conf < 60 and drop >= 20:
                confidence_score = 0.0
            elif drop > 0:
                confidence_score = max(0.0, 100.0 - (drop * 2))
                
        final_score = (efficiency_score * 0.4) + (momentum_score * 0.3) + (confidence_score * 0.3)
        final_score = max(0.0, min(100.0, final_score))
        
        pos.health_score = final_score
        
        # State transition
        if pos.health_state == TradeHealth.HEALTHY:
            if final_score < 40: pos.health_state = TradeHealth.CRITICAL
            elif final_score < 60: pos.health_state = TradeHealth.WARNING
            elif final_score < 80: pos.health_state = TradeHealth.CAUTION
        elif pos.health_state == TradeHealth.CAUTION:
            if final_score >= 85: pos.health_state = TradeHealth.HEALTHY
            elif final_score < 40: pos.health_state = TradeHealth.CRITICAL
            elif final_score < 60: pos.health_state = TradeHealth.WARNING
        elif pos.health_state == TradeHealth.WARNING:
            if final_score >= 65: pos.health_state = TradeHealth.CAUTION
            elif final_score < 40: pos.health_state = TradeHealth.CRITICAL
        elif pos.health_state == TradeHealth.CRITICAL:
            if final_score >= 45: pos.health_state = TradeHealth.WARNING

    def _make_exit_decision(self, pos: PositionState, snapshot: MarketSnapshot) -> ExitDecision:
        """Answers: 'Should this position continue to exist?'"""
        direction_str = getattr(pos.direction, 'value', str(pos.direction)).upper()
        entry_ref = getattr(pos, "entry_premium", 0.0) or getattr(pos, "entry_price", 0.0)
        is_long_premium = (pos.stop_loss < entry_ref) if (entry_ref > 0 and pos.stop_loss > 0) else (direction_str in ["BUY", "BULLISH"])
        
        # 1. Hard Stop Loss Trigger
        if is_long_premium:
            if pos.stop_loss > 0 and pos.current_price <= pos.stop_loss:
                return ExitDecision(ExitDecisionType.FULL_EXIT, "Hard Stop Loss Hit", urgency_level="HIGH")
        else:
            if pos.stop_loss > 0 and pos.current_price >= pos.stop_loss:
                return ExitDecision(ExitDecisionType.FULL_EXIT, "Hard Stop Loss Hit", urgency_level="HIGH")

        # 2. Hard Target Trigger
        t2 = getattr(pos, "target_2", 0.0) or 0.0
        t1 = getattr(pos, "target_1", 0.0) or 0.0
        if is_long_premium:
            if t2 > 0 and pos.current_price >= t2:
                return ExitDecision(ExitDecisionType.FULL_EXIT, "Target 2 Hit", urgency_level="NORMAL")
            elif t1 > 0 and pos.current_price >= t1:
                return ExitDecision(ExitDecisionType.FULL_EXIT, "Target 1 Hit", urgency_level="NORMAL")
        else:
            if t2 > 0 and pos.current_price <= t2:
                return ExitDecision(ExitDecisionType.FULL_EXIT, "Target 2 Hit", urgency_level="NORMAL")
            
        # 3. Health Based Exit (Critical deterioration)
        if pos.health_state == TradeHealth.CRITICAL:
            # If deeply critical, maybe exit early before SL
            if pos.unrealized_pnl < 0:
                return ExitDecision(ExitDecisionType.FULL_EXIT, "Trade Health Critical", urgency_level="NORMAL")

        # 4. Trailing Stop Update
        new_sl = self._compute_tsl(pos, snapshot)
        if new_sl and new_sl != pos.stop_loss:
            return ExitDecision(ExitDecisionType.ADJUST_STOP, "Trailing Stop Tightened", new_stop_loss=new_sl)

        return ExitDecision(ExitDecisionType.CONTINUE, "Trade Healthy")

    def _compute_tsl(self, pos: PositionState, snapshot: MarketSnapshot) -> Optional[float]:
        cfg = self.settings.position if hasattr(self.settings, "position") else self.settings
        entry = pos.entry_premium if pos.entry_premium > 0 else pos.entry_price
        
        if pos.current_price > pos.tsl_highest_premium:
            pos.tsl_highest_premium = pos.current_price
            pos.tsl_highest_premium_time = datetime.now()

        if entry <= 0: return None

        profit_pct = (pos.tsl_highest_premium - entry) / entry * 100
        new_sl = pos.stop_loss

        # Phase determination
        if profit_pct >= getattr(cfg, "tsl_tighten_2_trigger_pct", 25.0):
            pos.tsl_phase = "TIGHTEN_2"
            pos.tsl_active = True
        elif profit_pct >= getattr(cfg, "tsl_tighten_1_trigger_pct", 15.0):
            pos.tsl_phase = "TIGHTEN_1"
            pos.tsl_active = True
        elif profit_pct >= getattr(cfg, "tsl_activate_trigger_pct", 10.0):
            pos.tsl_phase = "ACTIVE"
            pos.tsl_active = True
        elif profit_pct >= getattr(cfg, "tsl_breakeven_trigger_pct", 5.0):
            pos.tsl_phase = "BREAKEVEN"
            pos.tsl_breakeven_hit = True
            new_sl = max(pos.entry_price, pos.stop_loss)
            return round(new_sl, 1)

        if not pos.tsl_active:
            return None

        # Calculate trail dist (Simplified for now)
        base_trail_dist = max(5.0, entry * 0.05)
        
        direction_str = getattr(pos.direction, 'value', str(pos.direction)).upper()
        if direction_str in ["BUY", "BULLISH"]:
            candidate_sl = pos.tsl_highest_premium - base_trail_dist
            if candidate_sl > pos.stop_loss:
                new_sl = candidate_sl
        
        if new_sl != pos.stop_loss:
            return round(new_sl, 1)
        return None

    def _generate_position_actions(self, pos: PositionState, decision: ExitDecision) -> List[PositionAction]:
        """Convert an exit decision into concrete PositionAction events."""
        actions = []
        
        if decision.decision == ExitDecisionType.FULL_EXIT:
            actions.append(PositionAction(
                position_id=pos.position_id,
                action_type="FULL_EXIT",
                qty=pos.qty,
                reason=decision.reason
            ))
        elif decision.decision == ExitDecisionType.PARTIAL_EXIT:
            if decision.exit_qty:
                actions.append(PositionAction(
                    position_id=pos.position_id,
                    action_type="PARTIAL_EXIT",
                    qty=decision.exit_qty,
                    reason=decision.reason
                ))
        elif decision.decision == ExitDecisionType.ADJUST_STOP:
            if decision.new_stop_loss:
                actions.append(PositionAction(
                    position_id=pos.position_id,
                    action_type="UPDATE_SL",
                    target_price=decision.new_stop_loss,
                    reason=decision.reason
                ))
                
        return actions
