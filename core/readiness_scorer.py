"""
============================================
🎯 READINESS SCORER — Phase B

Weighted composite scoring for go-live decisions.

Formula:
    readiness_score =
        profitability_score * 0.35 +
        stability_score     * 0.25 +
        discipline_score    * 0.20 +
        execution_score     * 0.20

Readiness Gates:
    < 50   UNSAFE
    50–64  EXPERIMENTAL
    65–74  CONTROLLED_BURNIN
    75–84  SMALL_CAPITAL_ELIGIBLE
    85+    OPERATIONALLY_MATURE

Unlike binary gating, this weighted score:
    - Exposes partial weaknesses
    - Allows independent category vetoes
    - Scales naturally as evidence accumulates
    - Guards against false deployment confidence
============================================
"""

from typing import Dict, Tuple

from utils.logger import get_logger


# ── Minimum data requirements ──
MIN_TRADES_FOR_RELIABLE_SCORE = 20
MIN_DAYS_FOR_RELIABLE_SCORE = 14


READINESS_GATES = [
    (85.0, "OPERATIONALLY_MATURE",    "✅ Operationally mature — eligible for full capital deployment"),
    (75.0, "SMALL_CAPITAL_ELIGIBLE",  "🟡 Small capital eligible — deploy ≤10% real capital with strict stops"),
    (65.0, "CONTROLLED_BURNIN",       "⚠️ Controlled burn-in — continue simulation, strategy showing edge"),
    (50.0, "EXPERIMENTAL",            "🔶 Experimental — significant weaknesses remain, do not deploy"),
    (0.0,  "UNSAFE",                  "🚫 Unsafe — system requires fundamental improvement before consideration"),
]


class ReadinessScorer:
    """
    Weighted readiness scorer for live deployment decisions.

    Takes BurninTracker.get_lifetime_stats() as input.
    Returns structured score with per-category breakdowns.
    """

    def __init__(self):
        self.logger = get_logger("readiness_scorer")

    def score(self, stats: Dict) -> Dict:
        """
        Compute full readiness assessment from lifetime stats.

        Args:
            stats: Output of BurninTracker.get_lifetime_stats()

        Returns:
            Structured dict with final_score, gate, category scores, and recommendations.
        """
        trading = stats.get("trading", {})
        execution = stats.get("execution", {})
        operational = stats.get("operational", {})
        snapshots = stats.get("daily_snapshots", [])

        trades = trading.get("lifetime_trades", 0)
        trading_days = len(set(s.get("date", "") for s in snapshots))

        # ── Compute each category score ──
        profitability_score, profitability_detail = self._score_profitability(trading)
        stability_score, stability_detail = self._score_stability(trading, operational)
        discipline_score, discipline_detail = self._score_discipline(trading)
        execution_score, execution_detail = self._score_execution(execution, trading_days)

        # ── Weighted composite ──
        raw_score = (
            profitability_score * 0.35 +
            stability_score     * 0.25 +
            discipline_score    * 0.20 +
            execution_score     * 0.20
        )

        # ── Data sufficiency penalty ──
        # If not enough evidence, cap the maximum score
        data_penalty = 0.0
        data_warnings = []
        if trades < MIN_TRADES_FOR_RELIABLE_SCORE:
            cap = 60.0
            if raw_score > cap:
                data_penalty = raw_score - cap
                raw_score = cap
            data_warnings.append(
                f"Only {trades} trades (need {MIN_TRADES_FOR_RELIABLE_SCORE} for reliable score)"
            )
        if trading_days < MIN_DAYS_FOR_RELIABLE_SCORE:
            cap = 65.0
            if raw_score > cap:
                data_penalty = max(data_penalty, raw_score - cap)
                raw_score = cap
            data_warnings.append(
                f"Only {trading_days} days (need {MIN_DAYS_FOR_RELIABLE_SCORE} for reliable score)"
            )

        final_score = round(max(0.0, min(100.0, raw_score)), 1)

        # ── Gate classification ──
        gate, description = self._classify_gate(final_score)

        # ── Recommendations ──
        recommendations = self._generate_recommendations(
            profitability_score, stability_score,
            discipline_score, execution_score,
            trading, execution, operational,
        )

        result = {
            "final_score": final_score,
            "gate": gate,
            "gate_description": description,
            "data_warnings": data_warnings,
            "categories": {
                "profitability": {
                    "score": round(profitability_score, 1),
                    "weight": 0.35,
                    "weighted_contribution": round(profitability_score * 0.35, 1),
                    "detail": profitability_detail,
                },
                "stability": {
                    "score": round(stability_score, 1),
                    "weight": 0.25,
                    "weighted_contribution": round(stability_score * 0.25, 1),
                    "detail": stability_detail,
                },
                "discipline": {
                    "score": round(discipline_score, 1),
                    "weight": 0.20,
                    "weighted_contribution": round(discipline_score * 0.20, 1),
                    "detail": discipline_detail,
                },
                "execution": {
                    "score": round(execution_score, 1),
                    "weight": 0.20,
                    "weighted_contribution": round(execution_score * 0.20, 1),
                    "detail": execution_detail,
                },
            },
            "recommendations": recommendations,
            "evidence": {
                "trades": trades,
                "trading_days": trading_days,
            },
        }

        self.logger.info(
            f"🎯 Readiness Score: {final_score} | Gate: {gate} | "
            f"P:{profitability_score:.0f} S:{stability_score:.0f} "
            f"D:{discipline_score:.0f} E:{execution_score:.0f}"
        )

        return result

    # ─────────────────────────────────────────
    # CATEGORY SCORERS
    # ─────────────────────────────────────────

    def _score_profitability(self, trading: Dict) -> Tuple[float, Dict]:
        """Profitability score (0–100). Weight: 35%."""
        score = 0.0
        detail = {}

        # Profit factor ≥ 1.5 → 40 pts
        pf = trading.get("profit_factor", 0.0)
        pf_pts = min(40.0, (pf / 1.5) * 40.0) if pf > 0 else 0
        score += pf_pts
        detail["profit_factor"] = {"value": round(pf, 2), "pts": round(pf_pts, 1), "target": "≥1.5"}

        # Win rate ≥ 55% → 30 pts
        wr = trading.get("win_rate", 0.0)
        wr_pts = min(30.0, (wr / 55.0) * 30.0) if wr > 0 else 0
        score += wr_pts
        detail["win_rate"] = {"value": f"{wr:.1f}%", "pts": round(wr_pts, 1), "target": "≥55%"}

        # Expectancy > ₹200/trade → 20 pts
        exp = trading.get("expectancy", 0.0)
        exp_pts = min(20.0, (exp / 200.0) * 20.0) if exp > 0 else 0
        score += exp_pts
        detail["expectancy"] = {"value": f"₹{exp:.0f}", "pts": round(exp_pts, 1), "target": ">₹200"}

        # Net P&L > 0 → 10 pts
        net = trading.get("net_pnl", 0.0)
        net_pts = 10.0 if net > 0 else 0
        score += net_pts
        detail["net_pnl"] = {"value": f"₹{net:.0f}", "pts": net_pts, "target": ">0"}

        return min(100.0, score), detail

    def _score_stability(self, trading: Dict, operational: Dict) -> Tuple[float, Dict]:
        """Stability score (0–100). Weight: 25%."""
        score = 0.0
        detail = {}

        # Max drawdown < 5% → 40 pts (this comes from SimulationEngine; use operational proxy)
        # We approximate from trading — a net loss > 10% of expected capital is a red flag
        net = trading.get("net_pnl", 0.0)
        loss_proxy = -net if net < 0 else 0
        dd_pts = 40.0 if loss_proxy < 5000 else max(0, 40.0 - (loss_proxy / 5000) * 20)
        score += dd_pts
        detail["drawdown_proxy"] = {"value": f"₹{loss_proxy:.0f} max loss", "pts": round(dd_pts, 1), "target": "<₹5000"}

        # API failures < 2/day → 20 pts
        api_per_day = operational.get("api_failures_per_day", 0.0)
        api_pts = 20.0 if api_per_day < 2 else max(0, 20.0 - (api_per_day - 2) * 5)
        score += api_pts
        detail["api_stability"] = {"value": f"{api_per_day:.1f}/day", "pts": round(api_pts, 1), "target": "<2/day"}

        # No circuit breaker trips in session → 20 pts
        trips = operational.get("session_circuit_trips", 0)
        trip_pts = 20.0 if trips == 0 else max(0, 20.0 - trips * 7)
        score += trip_pts
        detail["circuit_breakers"] = {"value": f"{trips} trips", "pts": round(trip_pts, 1), "target": "0"}

        # Uptime > 95% → 20 pts
        uptime = operational.get("uptime_pct", 100.0)
        uptime_pts = min(20.0, (uptime / 95.0) * 20.0)
        score += uptime_pts
        detail["uptime"] = {"value": f"{uptime:.1f}%", "pts": round(uptime_pts, 1), "target": ">95%"}

        return min(100.0, score), detail

    def _score_discipline(self, trading: Dict) -> Tuple[float, Dict]:
        """Discipline score (0–100). Weight: 20%."""
        score = 0.0
        detail = {}

        # Trade frequency (inferred from trades/days context — default 2/day assumed good)
        # Using max_consecutive_losses as primary discipline signal
        max_streak = trading.get("max_consecutive_losses", 0)
        streak_pts = 30.0 if max_streak <= 4 else max(0, 30.0 - (max_streak - 4) * 7.5)
        score += streak_pts
        detail["max_loss_streak"] = {"value": max_streak, "pts": round(streak_pts, 1), "target": "≤4"}

        # Avg R:R > 1.0 → 30 pts
        avg_rr = trading.get("avg_rr", 0.0)
        rr_pts = min(30.0, avg_rr * 30.0) if avg_rr > 0 else 0
        score += rr_pts
        detail["avg_rr"] = {"value": round(avg_rr, 2), "pts": round(rr_pts, 1), "target": ">1.0"}

        # Net P&L consistency (no catastrophic single session loss)
        # Proxied by: if net_pnl > 0, award discipline points
        net = trading.get("net_pnl", 0.0)
        pnl_pts = 20.0 if net > 0 else max(0.0, 20.0 + net / 1000)  # lose 1pt per ₹1000 loss
        score += pnl_pts
        detail["pnl_consistency"] = {"value": f"₹{net:.0f}", "pts": round(pnl_pts, 1), "target": ">0"}

        # Signal quality (win rate as discipline proxy) → 20 pts
        wr = trading.get("win_rate", 0.0)
        wr_disc_pts = min(20.0, (wr / 60.0) * 20.0)
        score += wr_disc_pts
        detail["signal_quality"] = {"value": f"{wr:.1f}%", "pts": round(wr_disc_pts, 1), "target": ">60%"}

        return min(100.0, score), detail

    def _score_execution(self, execution: Dict, trading_days: int) -> Tuple[float, Dict]:
        """Execution quality score (0–100). Weight: 20%. Requires Phase A data."""
        score = 0.0
        detail = {}

        # Fill success rate > 95% → 30 pts
        fill_rate = execution.get("fill_success_rate_pct", 100.0)
        fill_pts = min(30.0, (fill_rate / 95.0) * 30.0)
        score += fill_pts
        detail["fill_rate"] = {"value": f"{fill_rate:.1f}%", "pts": round(fill_pts, 1), "target": ">95%"}

        # Avg slippage < 0.5 pts → 30 pts
        avg_slip = execution.get("avg_slippage_pts", 0.0)
        slip_pts = max(0.0, 30.0 * (1.0 - avg_slip / 0.5)) if avg_slip < 0.5 else 0
        score += slip_pts
        detail["avg_slippage"] = {"value": f"{avg_slip:.3f}pts", "pts": round(slip_pts, 1), "target": "<0.5pts"}

        # Avg spread cost < 0.8% of premium (proxied by spread_pts < 0.8) → 20 pts
        avg_spread = execution.get("avg_spread_pts", 0.0)
        spread_pts = max(0.0, 20.0 * (1.0 - avg_spread / 0.8)) if avg_spread < 0.8 else 0
        score += spread_pts
        detail["avg_spread"] = {"value": f"{avg_spread:.3f}pts", "pts": round(spread_pts, 1), "target": "<0.8pts"}

        # ≥ 14 trading days of data → 20 pts
        day_pts = min(20.0, (trading_days / 14.0) * 20.0)
        score += day_pts
        detail["data_maturity"] = {"value": f"{trading_days} days", "pts": round(day_pts, 1), "target": "≥14 days"}

        # If Phase A has no data yet (0 exec attempts), return neutral partial score
        if execution.get("attempts", 0) == 0:
            detail["note"] = "Phase A execution data not yet accumulated"
            score = min(score, 50.0)

        return min(100.0, score), detail

    # ─────────────────────────────────────────
    # HELPERS
    # ─────────────────────────────────────────

    def _classify_gate(self, score: float) -> Tuple[str, str]:
        for threshold, gate, description in READINESS_GATES:
            if score >= threshold:
                return gate, description
        return "UNSAFE", "🚫 Unsafe"

    def _generate_recommendations(
        self, p_score, s_score, d_score, e_score,
        trading, execution, operational
    ) -> list:
        recs = []

        if p_score < 60:
            pf = trading.get("profit_factor", 0)
            if pf < 1.2:
                recs.append("Profit factor below 1.2 — review strategy edge and filter thresholds")
            wr = trading.get("win_rate", 0)
            if wr < 45:
                recs.append(f"Win rate {wr:.0f}% is low — analyze losing trades by regime")

        if s_score < 60:
            trips = operational.get("session_circuit_trips", 0)
            if trips > 0:
                recs.append(f"{trips} circuit breaker trips in session — investigate API stability")
            api = operational.get("api_failures_per_day", 0)
            if api >= 3:
                recs.append(f"API failure rate {api:.1f}/day — check network or token freshness")

        if d_score < 60:
            streak = trading.get("max_consecutive_losses", 0)
            if streak > 4:
                recs.append(f"Max loss streak of {streak} — review session kill-switch thresholds")

        if e_score < 60:
            fill = execution.get("fill_success_rate_pct", 100)
            if fill < 90:
                recs.append(f"Fill rate {fill:.0f}% — high rejection, consider ATM-only entries")
            slip = execution.get("avg_slippage_pts", 0)
            if slip > 0.5:
                recs.append(f"Avg slippage {slip:.2f}pts — avoid FAR_OTM options")

        if not recs:
            recs.append("System performing well across all categories — continue accumulating evidence")

        return recs
