"""
============================================
🎓 LEARNING AGENT — SELF-EVOLVING INTELLIGENCE

Analyzes ALL previous trades to discover:
- What conditions lead to wins
- What conditions lead to losses
- Optimal entry times
- Best confidence thresholds
- Which agent combinations work best
- Streak patterns
- Market condition correlations

THIS IS THE FOUNDATION FOR AI EVOLUTION.
Without this, you're just repeating mistakes.
============================================
"""

import os
import json
import numpy as np
import pandas as pd
from datetime import datetime, timedelta, time
from typing import Dict, List, Optional, Tuple
from collections import defaultdict, Counter

from agents.base_agent import BaseAgent
# from agents.learning_agent_v2 import LearningAgentV2Mixin
from models import (
    AgentOutput, Direction, Strength, MarketSnapshot,
    SignalType, TradeOutcome,
)
from utils.logger import get_logger
from utils.helpers import save_json, load_json
from config.settings import Settings


class LearningAgent(BaseAgent):
    """
    The agent that LEARNS from your trading history.

    It answers:
    - "Should I take this trade based on what worked before?"
    - "Is this a pattern that historically loses?"
    - "Am I in a losing streak? Should I stop?"
    - "Which agents were right in similar situations?"

    This is NOT machine learning (yet).
    This is STATISTICAL PATTERN RECOGNITION from your own data.
    """

    def __init__(self, settings: Settings):
        super().__init__("learning", settings)
        self.th = settings.thresholds
        self.trade_log = get_logger("learning_agent")

        # ── Trade History Storage ──
        self.trade_history: List[TradeOutcome] = []
        self.trades_file = "data/trade_history.json"
        
        # Ensure data directory exists
        os.makedirs("data", exist_ok=True)
        self._load_trade_history()

        # ── Learned Patterns ──
        self.learned_patterns: Dict = {
            "win_conditions": {},
            "loss_conditions": {},
            "optimal_hours": {},
            "confidence_calibration": {},
            "agent_reliability": {},
            "streak_analysis": {},
            "regime_performance": {},
            "session_performance": {},
            "expiry_day_performance": {},
        }

        # ── Current Session Tracking ──
        self.session_trades: List[Dict] = []
        self.current_streak = 0        # positive = wins, negative = losses
        self.today_win_count = 0
        self.today_loss_count = 0

        # ── Pre-compute patterns if history exists ──
        if len(self.trade_history) >= self.th.min_trades_for_learning:
            self._analyze_all_patterns()

    def analyze(
        self, df: pd.DataFrame, snapshot: MarketSnapshot
    ) -> AgentOutput:
        """
        Analysis Pipeline:
        1. Check if current conditions match winning patterns
        2. Check if current conditions match losing patterns
        3. Confidence calibration (is the system overconfident?)
        4. Time-of-day analysis
        5. Streak check
        6. Agent reliability context
        """

        warnings = []
        details = {}
        now = datetime.now()

        # ── INSUFFICIENT DATA CHECK ──
        if len(self.trade_history) < self.th.min_trades_for_learning:
            details["status"] = (
                f"Learning: {len(self.trade_history)}/"
                f"{self.th.min_trades_for_learning} trades"
            )
            details["verdict"] = "Collecting data — no learned patterns yet"
            return AgentOutput(
                agent_name=self.name,
                timestamp=now,
                direction=Direction.NEUTRAL,
                confidence=50,
                strength=Strength.MODERATE,
                details=details,
                warnings=["Not enough trade history for learning"],
            )

        # ── 1. PATTERN MATCH: CURRENT CONDITIONS ──
        condition_score, condition_details = \
            self._match_current_conditions(snapshot, now)
        details.update(condition_details)

        # ── 2. TIME-OF-DAY ANALYSIS ──
        time_score, time_details = self._analyze_time_performance(now)
        details.update(time_details)

        # ── 3. CONFIDENCE CALIBRATION ──
        calib_score, calib_details = self._calibrate_confidence()
        details.update(calib_details)

        # ── 4. STREAK ANALYSIS ──
        streak_score, streak_details, streak_warnings = \
            self._analyze_streak()
        details.update(streak_details)
        warnings.extend(streak_warnings)

        # ── 5. REGIME PERFORMANCE ──
        regime_score, regime_details = \
            self._check_regime_performance(snapshot)
        details.update(regime_details)

        # ── 6. EXPIRY DAY LEARNING ──
        expiry_score = 60
        if snapshot.is_expiry_day:
            expiry_score, expiry_details = \
                self._check_expiry_day_performance()
            details.update(expiry_details)

        # ── 7. AGENT RELIABILITY CHECK ──
        agent_score, agent_details = \
            self._check_agent_reliability()
        details.update(agent_details)

        # ── 8. SIMILAR TRADE PATTERN SEARCH ──
        similar_score, similar_details = \
            self._find_similar_trades(snapshot, now)
        details.update(similar_details)

        # ── COMBINE ALL LEARNING SIGNALS ──
        factors = {
            "conditions": (condition_score, 0.25),
            "time": (time_score, 0.15),
            "calibration": (calib_score, 0.10),
            "streak": (streak_score, 0.15),
            "regime": (regime_score, 0.10),
            "expiry": (expiry_score, 0.05),
            "agents": (agent_score, 0.10),
            "similar": (similar_score, 0.10),
        }
        confidence = self._calculate_confidence(factors)

        # ── DIRECTION FROM LEARNING ──
        # Learning agent doesn't give trade direction
        # It gives PERMISSION based on historical performance
        direction = Direction.NEUTRAL

        # ── BLOCKING LOGIC ──
        block_reasons = []

        if self.current_streak <= -self.th.streak_alert_threshold:
            confidence = min(confidence, 25)
            block_reasons.append(
                f"🚨 {abs(self.current_streak)} consecutive losses"
            )
            warnings.append(
                f"LOSING STREAK: {abs(self.current_streak)} in a row — "
                f"consider stopping"
            )

        if condition_score < 25:
            block_reasons.append(
                "Current conditions historically unprofitable"
            )

        if time_score < 20:
            block_reasons.append(
                "This time slot historically underperforms"
            )

        if block_reasons:
            details["blocked_reasons"] = block_reasons
            warnings.append(
                f"⚠️ Learning Agent CAUTION: {block_reasons[0]}"
            )

        # ── STRENGTH ──
        if confidence >= 70:
            strength = Strength.STRONG
            details["verdict"] = (
                "✅ Historical patterns SUPPORT this trade"
            )
        elif confidence >= 45:
            strength = Strength.MODERATE
            details["verdict"] = (
                "⚠️ Mixed historical performance"
            )
        else:
            strength = Strength.WEAK
            details["verdict"] = (
                "🚫 Historical patterns WARN against this trade"
            )

        # ── SUMMARY STATS ──
        details["total_trades_analyzed"] = len(self.trade_history)
        details["overall_win_rate"] = f"{self._overall_win_rate():.1f}%"
        details["current_streak"] = self.current_streak

        return AgentOutput(
            agent_name=self.name,
            timestamp=now,
            direction=direction,
            confidence=round(confidence, 1),
            strength=strength,
            details=details,
            warnings=warnings,
        )

    # ══════════════════════════════════════
    # PATTERN ANALYSIS METHODS
    # ══════════════════════════════════════

    def _match_current_conditions(
        self, snapshot: MarketSnapshot, now: datetime
    ) -> Tuple[float, Dict]:
        """
        Check if current market conditions match
        historically profitable or unprofitable patterns.
        """
        details = {}

        # Build current condition vector
        current = {
            "rsi_zone": self._categorize_rsi(snapshot.rsi),
            "vwap_position": (
                "above" if snapshot.price > snapshot.vwap else "below"
            ),
            "vix_level": self._categorize_vix(snapshot.india_vix),
            "pcr_zone": self._categorize_pcr(snapshot.pcr),
            "hour": now.hour,
            "is_expiry": snapshot.is_expiry_day,
        }

        # Search trade history for matching conditions
        matching_wins = 0
        matching_losses = 0

        for trade in self.trade_history:
            match_score = 0
            total_checks = 0

            # RSI zone match
            if self._categorize_rsi(trade.rsi_at_entry) == \
               current["rsi_zone"]:
                match_score += 1
            total_checks += 1

            # VWAP match
            if trade.vwap_position_at_entry == \
               current["vwap_position"]:
                match_score += 1
            total_checks += 1

            # VIX match
            if self._categorize_vix(trade.vix_at_entry) == \
               current["vix_level"]:
                match_score += 1
            total_checks += 1

            # Hour match (within 1 hour)
            if abs(trade.entry_hour - current["hour"]) <= 1:
                match_score += 1
            total_checks += 1

            # Expiry match
            if trade.is_expiry_day_trade == current["is_expiry"]:
                match_score += 1
            total_checks += 1

            # Need at least 60% match
            if total_checks > 0 and \
               (match_score / total_checks) >= 0.6:
                if trade.result == "WIN":
                    matching_wins += 1
                elif trade.result == "LOSS":
                    matching_losses += 1

        total_matching = matching_wins + matching_losses

        if total_matching >= self.th.pattern_min_occurrences:
            win_rate = matching_wins / total_matching * 100
            details["condition_match"] = {
                "matching_trades": total_matching,
                "win_rate": f"{win_rate:.1f}%",
                "wins": matching_wins,
                "losses": matching_losses,
            }

            if win_rate >= self.th.win_rate_good:
                score = min(90, 50 + (win_rate - 50) * 0.8)
                details["condition_verdict"] = (
                    f"✅ Similar conditions won {win_rate:.0f}% "
                    f"of the time"
                )
            elif win_rate <= self.th.win_rate_bad:
                score = max(10, 50 - (50 - win_rate) * 0.8)
                details["condition_verdict"] = (
                    f"🚫 Similar conditions only won "
                    f"{win_rate:.0f}%"
                )
            else:
                score = 50
                details["condition_verdict"] = (
                    f"Mixed: {win_rate:.0f}% win rate in "
                    f"similar conditions"
                )
        else:
            score = 50
            details["condition_match"] = {
                "matching_trades": total_matching,
                "note": "Not enough matching trades yet",
            }

        return score, details

    def _analyze_time_performance(
        self, now: datetime
    ) -> Tuple[float, Dict]:
        """
        Which hours of the day have been profitable?
        """
        details = {}
        current_hour = now.hour

        # Group trades by hour
        hour_stats = defaultdict(lambda: {"wins": 0, "losses": 0})

        for trade in self.trade_history:
            h = trade.entry_hour
            if trade.result == "WIN":
                hour_stats[h]["wins"] += 1
            elif trade.result == "LOSS":
                hour_stats[h]["losses"] += 1

        if current_hour in hour_stats:
            stats = hour_stats[current_hour]
            total = stats["wins"] + stats["losses"]
            if total >= self.th.condition_correlation_min_samples:
                win_rate = stats["wins"] / total * 100
                details["hour_performance"] = {
                    "hour": f"{current_hour}:00",
                    "win_rate": f"{win_rate:.1f}%",
                    "sample_size": total,
                }

                if win_rate >= 65:
                    score = 80
                    details["time_verdict"] = (
                        f"✅ {current_hour}:00 hour is historically "
                        f"profitable ({win_rate:.0f}%)"
                    )
                elif win_rate <= 40:
                    score = 25
                    details["time_verdict"] = (
                        f"🚫 {current_hour}:00 hour historically "
                        f"unprofitable ({win_rate:.0f}%)"
                    )
                else:
                    score = 55
                    details["time_verdict"] = (
                        f"⚠️ {current_hour}:00 hour is average "
                        f"({win_rate:.0f}%)"
                    )
            else:
                score = 50
                details["hour_performance"] = {
                    "note": f"Only {total} trades at this hour"
                }
        else:
            score = 50
            details["hour_performance"] = {
                "note": "No trades at this hour yet"
            }

        # Best and worst hours
        if hour_stats:
            best_hour = max(
                hour_stats.items(),
                key=lambda x: x[1]["wins"] / max(
                    x[1]["wins"] + x[1]["losses"], 1
                ),
            )
            worst_hour = min(
                hour_stats.items(),
                key=lambda x: x[1]["wins"] / max(
                    x[1]["wins"] + x[1]["losses"], 1
                ),
            )
            details["best_trading_hour"] = f"{best_hour[0]}:00"
            details["worst_trading_hour"] = f"{worst_hour[0]}:00"

        return score, details

    def _calibrate_confidence(self) -> Tuple[float, Dict]:
        """
        Are the system's confidence scores accurate?
        Do high-confidence trades actually win more?
        """
        details = {}

        if len(self.trade_history) < 15:
            return 50, {"calibration": "Insufficient data"}

        # Group by confidence buckets
        buckets = {
            "50-60": {"wins": 0, "total": 0},
            "60-70": {"wins": 0, "total": 0},
            "70-80": {"wins": 0, "total": 0},
            "80-90": {"wins": 0, "total": 0},
            "90-100": {"wins": 0, "total": 0},
        }

        for trade in self.trade_history:
            conf = trade.confidence_at_entry
            if 50 <= conf < 60:
                bucket = "50-60"
            elif 60 <= conf < 70:
                bucket = "60-70"
            elif 70 <= conf < 80:
                bucket = "70-80"
            elif 80 <= conf < 90:
                bucket = "80-90"
            elif conf >= 90:
                bucket = "90-100"
            else:
                continue

            buckets[bucket]["total"] += 1
            if trade.result == "WIN":
                buckets[bucket]["wins"] += 1

        # Check if higher confidence = higher win rate
        calibration_data = {}
        for bucket, stats in buckets.items():
            if stats["total"] >= 3:
                wr = stats["wins"] / stats["total"] * 100
                calibration_data[bucket] = {
                    "win_rate": f"{wr:.0f}%",
                    "trades": stats["total"],
                }

        details["confidence_calibration"] = calibration_data

        # Check if calibration is good
        # (higher confidence should = higher win rate)
        rates = []
        for bucket in ["50-60", "60-70", "70-80", "80-90", "90-100"]:
            if buckets[bucket]["total"] >= 3:
                rates.append(
                    buckets[bucket]["wins"] /
                    buckets[bucket]["total"] * 100
                )

        if len(rates) >= 3:
            # Check if monotonically increasing (roughly)
            increasing = sum(
                1 for i in range(1, len(rates))
                if rates[i] >= rates[i-1]
            )
            monotonic_pct = increasing / (len(rates) - 1) * 100

            if monotonic_pct >= 60:
                score = 75
                details["calibration_verdict"] = (
                    "✅ Confidence scores are well-calibrated"
                )
            else:
                score = 40
                details["calibration_verdict"] = (
                    "⚠️ Confidence scores NOT well-calibrated — "
                    "high confidence doesn't guarantee wins"
                )

            # Find optimal confidence threshold
            best_rate = 0
            best_bucket = ""
            for bucket, stats in buckets.items():
                if stats["total"] >= 3:
                    wr = stats["wins"] / stats["total"] * 100
                    if wr > best_rate:
                        best_rate = wr
                        best_bucket = bucket

            details["optimal_confidence_zone"] = best_bucket
        else:
            score = 50
            details["calibration_verdict"] = (
                "Insufficient data for calibration"
            )

        return score, details

    def _analyze_streak(self) -> Tuple[float, Dict, List[str]]:
        """
        Detect winning/losing streaks.
        Losing streaks should reduce confidence.
        """
        details = {}
        warnings = []

        if not self.trade_history:
            return 60, {"streak": "No trades"}, []

        # Calculate current streak
        streak = 0
        for trade in reversed(self.trade_history):
            if trade.result == "WIN":
                if streak >= 0:
                    streak += 1
                else:
                    break
            elif trade.result == "LOSS":
                if streak <= 0:
                    streak -= 1
                else:
                    break
            else:
                break

        self.current_streak = streak
        details["current_streak"] = streak

        if streak >= 3:
            score = 80
            details["streak_status"] = (
                f"🔥 {streak} WIN streak — system is hot"
            )
        elif streak <= -self.th.streak_alert_threshold:
            score = 15
            details["streak_status"] = (
                f"🚨 {abs(streak)} LOSS streak — STOP TRADING"
            )
            warnings.append(
                f"🚨 {abs(streak)} consecutive losses — "
                f"take a break"
            )
            warnings.append(
                "Review last few trades before continuing"
            )
        elif streak <= -2:
            score = 35
            details["streak_status"] = (
                f"⚠️ {abs(streak)} losses in a row"
            )
            warnings.append(
                "Recent losses — reduce position size"
            )
        elif streak >= 1:
            score = 65
            details["streak_status"] = (
                f"✅ {streak} recent win(s)"
            )
        else:
            score = 55
            details["streak_status"] = "Neutral"

        # Maximum historical streak
        max_win_streak = 0
        max_loss_streak = 0
        temp_streak = 0

        for trade in self.trade_history:
            if trade.result == "WIN":
                if temp_streak >= 0:
                    temp_streak += 1
                else:
                    temp_streak = 1
                max_win_streak = max(max_win_streak, temp_streak)
            elif trade.result == "LOSS":
                if temp_streak <= 0:
                    temp_streak -= 1
                else:
                    temp_streak = -1
                max_loss_streak = min(max_loss_streak, temp_streak)

        details["max_win_streak"] = max_win_streak
        details["max_loss_streak"] = abs(max_loss_streak)

        return score, details, warnings

    def _check_regime_performance(
        self, snapshot: MarketSnapshot
    ) -> Tuple[float, Dict]:
        """
        How does the system perform in the current
        market regime (trending vs ranging vs volatile)?
        """
        details = {}

        # Determine current regime from VIX and ATR
        if snapshot.india_vix > 18:
            current_regime = "volatile"
        elif snapshot.atr > 40:
            current_regime = "trending"
        else:
            current_regime = "ranging"

        regime_stats = defaultdict(lambda: {"wins": 0, "losses": 0})

        for trade in self.trade_history:
            regime = trade.market_condition or "unknown"
            if trade.result == "WIN":
                regime_stats[regime]["wins"] += 1
            elif trade.result == "LOSS":
                regime_stats[regime]["losses"] += 1

        if current_regime in regime_stats:
            stats = regime_stats[current_regime]
            total = stats["wins"] + stats["losses"]
            if total >= self.th.condition_correlation_min_samples:
                wr = stats["wins"] / total * 100
                details["regime_performance"] = {
                    "regime": current_regime,
                    "win_rate": f"{wr:.1f}%",
                    "trades": total,
                }

                score = min(90, max(15, wr))
            else:
                score = 50
                details["regime_performance"] = {
                    "regime": current_regime,
                    "note": f"Only {total} trades in this regime",
                }
        else:
            score = 50
            details["regime_performance"] = {
                "regime": current_regime,
                "note": "No trades in this regime yet",
            }

        return score, details

    def _check_expiry_day_performance(
        self,
    ) -> Tuple[float, Dict]:
        """How does the system perform on expiry days?"""
        details = {}

        expiry_trades = [
            t for t in self.trade_history
            if t.is_expiry_day_trade
        ]

        if len(expiry_trades) >= 3:
            wins = sum(
                1 for t in expiry_trades if t.result == "WIN"
            )
            total = len(expiry_trades)
            wr = wins / total * 100

            avg_pnl = np.mean(
                [t.pnl for t in expiry_trades]
            )

            details["expiry_day_history"] = {
                "trades": total,
                "win_rate": f"{wr:.1f}%",
                "avg_pnl": f"₹{avg_pnl:,.0f}",
            }

            if wr >= 55:
                score = 70
            elif wr <= 40:
                score = 25
                details["expiry_warning"] = (
                    "🚫 Historically unprofitable on expiry"
                )
            else:
                score = 45
        else:
            score = 50
            details["expiry_day_history"] = {
                "note": "Not enough expiry day trades"
            }

        return score, details

    def get_agent_profit_factors(self) -> Dict[str, float]:
        """Phase 4: Agent Degradation Kill-Switch. Returns PF of each agent over its last 30 trades."""
        agent_pf = {}
        from collections import defaultdict
        agent_trades = defaultdict(list)
        for trade in reversed(self.trade_history):
            for agent_name, vote in trade.agent_votes_at_entry.items():
                if len(agent_trades[agent_name]) < 30:
                    ag_dir = vote.get("direction") or vote.get("dir")
                    if ag_dir == trade.direction.value:
                        agent_trades[agent_name].append(trade.pnl)
                        
        for agent, pnls in agent_trades.items():
            gross_profit = sum(p for p in pnls if p > 0)
            gross_loss = abs(sum(p for p in pnls if p < 0))
            if gross_loss == 0:
                agent_pf[agent] = 999.0 if gross_profit > 0 else 1.0
            else:
                agent_pf[agent] = gross_profit / gross_loss
                
        return agent_pf

    def _check_agent_reliability(self) -> Tuple[float, Dict]:
        """
        Which agents have been most reliable?
        Weight their current opinion higher.
        """
        details = {}

        agent_stats = defaultdict(
            lambda: {"correct": 0, "total": 0}
        )

        for trade in self.trade_history:
            actual_dir = (
                "BULLISH" if trade.result == "WIN" and
                trade.direction == Direction.BULLISH
                else "BEARISH" if trade.result == "WIN" and
                trade.direction == Direction.BEARISH
                else "WRONG"
            )

            for agent_name, vote in \
                trade.agent_votes_at_entry.items():
                agent_dir = vote.get("dir", "NEUTRAL")
                agent_stats[agent_name]["total"] += 1

                if agent_dir == actual_dir or \
                   (agent_dir == trade.direction.value and
                    trade.result == "WIN"):
                    agent_stats[agent_name]["correct"] += 1

        # Calculate reliability scores
        reliability = {}
        for agent, stats in agent_stats.items():
            if stats["total"] >= 5:
                acc = stats["correct"] / stats["total"] * 100
                reliability[agent] = round(acc, 1)

        if reliability:
            best = max(reliability, key=reliability.get)
            worst = min(reliability, key=reliability.get)
            avg_reliability = np.mean(list(reliability.values()))

            details["agent_reliability"] = {
                "best": f"{best} ({reliability[best]:.0f}%)",
                "worst": f"{worst} ({reliability[worst]:.0f}%)",
                "all": {
                    k: f"{v:.0f}%"
                    for k, v in sorted(
                        reliability.items(),
                        key=lambda x: x[1],
                        reverse=True,
                    )[:5]
                },
            }

            score = avg_reliability
        else:
            score = 50
            details["agent_reliability"] = {
                "note": "Insufficient data"
            }

        return score, details

    def _find_similar_trades(
        self, snapshot: MarketSnapshot, now: datetime
    ) -> Tuple[float, Dict]:
        """
        Find trades that happened in very similar
        conditions and report their outcomes.
        """
        details = {}

        similar_trades = []

        for trade in self.trade_history:
            similarity = 0
            checks = 0

            # RSI similarity (within 10 points)
            if abs(trade.rsi_at_entry - snapshot.rsi) < 10:
                similarity += 1
            checks += 1

            # VIX similarity
            if abs(trade.vix_at_entry - snapshot.india_vix) < 3:
                similarity += 1
            checks += 1

            # Same hour
            if trade.entry_hour == now.hour:
                similarity += 1
            checks += 1

            # Same day of week
            if trade.day_of_week == now.weekday():
                similarity += 1
            checks += 1

            # Expiry similarity
            if trade.is_expiry_day_trade == snapshot.is_expiry_day:
                similarity += 1
            checks += 1

            # DTE similarity
            if abs(trade.dte_at_entry - snapshot.days_to_expiry) <= 1:
                similarity += 1
            checks += 1

            # Need 70%+ similarity
            if checks > 0 and (similarity / checks) >= 0.7:
                similar_trades.append(trade)

        if len(similar_trades) >= 3:
            wins = sum(
                1 for t in similar_trades if t.result == "WIN"
            )
            total = len(similar_trades)
            wr = wins / total * 100

            avg_pnl = np.mean([t.pnl for t in similar_trades])

            details["similar_trades"] = {
                "found": total,
                "win_rate": f"{wr:.1f}%",
                "avg_pnl": f"₹{avg_pnl:,.0f}",
            }

            score = min(90, max(15, wr))
        else:
            score = 50
            details["similar_trades"] = {
                "found": len(similar_trades),
                "note": "Not enough similar historical trades",
            }

        return score, details

    # ══════════════════════════════════════
    # TRADE RECORDING
    # ══════════════════════════════════════

    def record_trade(self, trade: TradeOutcome):
        """Record a completed trade for future learning"""
        self.trade_history.append(trade)

        # Update streak
        if trade.result == "WIN":
            self.today_win_count += 1
            if self.current_streak >= 0:
                self.current_streak += 1
            else:
                self.current_streak = 1
        elif trade.result == "LOSS":
            self.today_loss_count += 1
            if self.current_streak <= 0:
                self.current_streak -= 1
            else:
                self.current_streak = -1

        # Save periodically
        if len(self.trade_history) % 5 == 0:
            self._save_trade_history()

        # Re-analyze patterns
        if len(self.trade_history) % 10 == 0:
            self._analyze_all_patterns()

        # Apply V2 Memory Control
        if hasattr(self, "_apply_memory_control"):
            self._apply_memory_control()

        self.trade_log.info(
            f"Trade recorded: {trade.result} | "
            f"PnL: ₹{trade.pnl:,.0f} | "
            f"Streak: {self.current_streak}"
        )

    def _analyze_all_patterns(self):
        """Full pattern analysis on all trade history"""

        if len(self.trade_history) < self.th.min_trades_for_learning:
            return

        wins = [
            t for t in self.trade_history if t.result == "WIN"
        ]
        losses = [
            t for t in self.trade_history if t.result == "LOSS"
        ]

        # Win condition analysis
        if wins:
            self.learned_patterns["win_conditions"] = {
                "avg_confidence": np.mean(
                    [t.confidence_at_entry for t in wins]
                ),
                "avg_rsi": np.mean(
                    [t.rsi_at_entry for t in wins]
                ),
                "avg_vix": np.mean(
                    [t.vix_at_entry for t in wins]
                ),
                "most_common_hour": Counter(
                    [t.entry_hour for t in wins]
                ).most_common(1)[0][0],
                "avg_hold_minutes": np.mean(
                    [t.hold_duration_minutes for t in wins]
                ),
            }

        # Loss condition analysis
        if losses:
            self.learned_patterns["loss_conditions"] = {
                "avg_confidence": np.mean(
                    [t.confidence_at_entry for t in losses]
                ),
                "avg_rsi": np.mean(
                    [t.rsi_at_entry for t in losses]
                ),
                "avg_vix": np.mean(
                    [t.vix_at_entry for t in losses]
                ),
                "most_common_hour": Counter(
                    [t.entry_hour for t in losses]
                ).most_common(1)[0][0],
                "avg_hold_minutes": np.mean(
                    [t.hold_duration_minutes for t in losses]
                ),
            }

    # ══════════════════════════════════════
    # HELPER METHODS
    # ══════════════════════════════════════

    def _overall_win_rate(self) -> float:
        completed = [
            t for t in self.trade_history
            if t.result in ("WIN", "LOSS")
        ]
        if not completed:
            return 50.0
        wins = sum(1 for t in completed if t.result == "WIN")
        return wins / len(completed) * 100

    def _categorize_rsi(self, rsi: float) -> str:
        if rsi >= 70:
            return "overbought"
        elif rsi >= 60:
            return "bullish"
        elif rsi <= 30:
            return "oversold"
        elif rsi <= 40:
            return "bearish"
        else:
            return "neutral"

    def _categorize_vix(self, vix: float) -> str:
        if vix >= 18:
            return "high"
        elif vix <= 12:
            return "low"
        else:
            return "normal"

    def _categorize_pcr(self, pcr: float) -> str:
        if pcr >= 1.2:
            return "bullish"
        elif pcr <= 0.8:
            return "bearish"
        else:
            return "neutral"

    # ══════════════════════════════════════
    # PERSISTENCE
    # ══════════════════════════════════════

    def _save_trade_history(self):
        data = [t.to_dict() for t in self.trade_history]
        save_json({"trades": data}, self.trades_file)

    def _load_trade_history(self):
        if not os.path.exists(self.trades_file):
            return
        try:
            data = load_json(self.trades_file)
            if "trades" in data:
                for t in data["trades"]:
                    try:
                        outcome = TradeOutcome(
                            trade_id=t.get("id", ""),
                            timestamp_entry=datetime.fromisoformat(
                                t.get("entry_time", "")
                            ) if t.get("entry_time") else datetime.now(),
                            signal_type=SignalType(
                                t.get("signal", "NO_TRADE")
                            ),
                            direction=Direction(
                                t.get("direction", "NEUTRAL")
                            ),
                            entry_price=t.get("entry", 0),
                            exit_price=t.get("exit", 0),
                            pnl=t.get("pnl", 0),
                            result=t.get("result", "OPEN"),
                            confidence_at_entry=t.get("confidence", 0),
                            confluence_at_entry=t.get("confluence", 0),
                            regime_at_entry=t.get("regime", ""),
                            session_phase_at_entry=t.get("session", ""),
                            hold_duration_minutes=t.get(
                                "hold_minutes", 0
                            ),
                            dte_at_entry=t.get("dte", 5),
                            is_expiry_day_trade=t.get(
                                "is_expiry", False
                            ),
                            agent_votes_at_entry=t.get("agents", {}),
                            rsi_at_entry=t.get("rsi", 50),
                            vix_at_entry=t.get("vix", 13),
                            entry_hour=t.get("entry_hour", 10),
                            day_of_week=t.get("day_of_week", 0),
                        )
                        self.trade_history.append(outcome)
                    except Exception:
                        continue

                self.trade_log.info(
                    f"Loaded {len(self.trade_history)} "
                    f"historical trades"
                )
        except Exception:
            pass

    def get_learning_report(self) -> dict:
        """Full learning report"""
        return {
            "total_trades": len(self.trade_history),
            "win_rate": f"{self._overall_win_rate():.1f}%",
            "current_streak": self.current_streak,
            "learned_patterns": self.learned_patterns,
            "today": {
                "wins": self.today_win_count,
                "losses": self.today_loss_count,
            },
        }
