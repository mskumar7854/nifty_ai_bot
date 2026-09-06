"""
============================================
🎓 LEARNING AGENT v2 — MEMORY CONTROLLED

Fixes from v1:
- Rolling window prevents overfitting
- Exponential decay weights recent trades higher
- Overfit detection alerts
- Pattern staleness tracking
- Automatic pattern pruning
============================================
"""

from datetime import datetime, timedelta

class LearningAgentV2Mixin:
    """
    Mix into your existing LearningAgent to add
    memory control capabilities.
    """

    def _apply_memory_control(self):
        """
        Apply all memory control mechanisms.
        Call this after recording each trade.
        """

        # 1. Rolling window
        self._enforce_rolling_window()

        # 2. Check for overfit
        self._check_overfit()

        # 3. Prune stale patterns
        self._prune_stale_patterns()

        # 4. Recalculate weighted statistics
        self._recalculate_weighted_stats()

    def _enforce_rolling_window(self):
        """Keep only the last N trades"""
        max_trades = self.th.learning_rolling_window

        if len(self.trade_history) > max_trades:
            removed = len(self.trade_history) - max_trades
            self.trade_history = self.trade_history[-max_trades:]
            self.trade_log.info(
                f"Memory control: Removed {removed} old trades, "
                f"keeping last {max_trades}"
            )

    def _check_overfit(self):
        """
        Detect if the learning agent might be overfitting.

        Signs of overfit:
        - Very high accuracy on historical but failing on recent
        - Pattern matching too many conditions (over-specific)
        - Win rate suddenly drops after a period of high accuracy
        """

        if len(self.trade_history) < 20:
            return

        # Split into old and recent
        split_point = len(self.trade_history) * 2 // 3
        old_trades = self.trade_history[:split_point]
        recent_trades = self.trade_history[split_point:]

        # Calculate win rates
        old_wins = sum(
            1 for t in old_trades if t.result == "WIN"
        )
        old_total = sum(
            1 for t in old_trades
            if t.result in ("WIN", "LOSS")
        )
        recent_wins = sum(
            1 for t in recent_trades if t.result == "WIN"
        )
        recent_total = sum(
            1 for t in recent_trades
            if t.result in ("WIN", "LOSS")
        )

        if old_total >= 5 and recent_total >= 5:
            old_wr = old_wins / old_total * 100
            recent_wr = recent_wins / recent_total * 100

            # If old win rate was very high but recent dropped
            if old_wr >= self.th.learning_overfit_threshold * 100 \
               and recent_wr < 50:
                self.trade_log.warning(
                    f"⚠️ OVERFIT DETECTED: Old WR={old_wr:.0f}% "
                    f"but Recent WR={recent_wr:.0f}%"
                )

                # Reset learned patterns to avoid acting on
                # overfitted data
                self.learned_patterns["win_conditions"] = {}
                self.learned_patterns["loss_conditions"] = {}
                self.trade_log.info(
                    "Learned patterns reset due to overfit detection"
                )

    def _prune_stale_patterns(self):
        """
        Remove patterns derived from old data.
        Market conditions change — old patterns may not apply.
        """

        if not self.trade_history:
            return

        staleness_cutoff = datetime.now() - timedelta(
            days=self.th.learning_staleness_days
        )

        # Count trades newer than cutoff
        recent_count = sum(
            1 for t in self.trade_history
            if t.timestamp_entry and
            t.timestamp_entry > staleness_cutoff
        )

        # If most trades are old, force reanalysis
        if recent_count < len(self.trade_history) * 0.3:
            self.trade_log.info(
                f"Pruning stale patterns: only "
                f"{recent_count}/{len(self.trade_history)} "
                f"trades are recent"
            )

            # Weight recent trades more in reanalysis
            self._analyze_all_patterns()

    def _recalculate_weighted_stats(self):
        """
        Apply exponential decay weighting.
        Recent trades matter MORE than old trades.
        """

        if len(self.trade_history) < 5:
            return

        decay = self.th.learning_weight_decay
        weighted_wins = 0
        weighted_total = 0

        for i, trade in enumerate(reversed(self.trade_history)):
            weight = decay ** i  # Most recent = weight 1.0

            if trade.result in ("WIN", "LOSS"):
                weighted_total += weight
                if trade.result == "WIN":
                    weighted_wins += weight

        if weighted_total > 0:
            self.learned_patterns["weighted_win_rate"] = round(
                weighted_wins / weighted_total * 100, 1
            )

        # Weighted average confidence of winners vs losers
        weighted_conf_win = 0
        weighted_conf_loss = 0
        w_win_total = 0
        w_loss_total = 0

        for i, trade in enumerate(reversed(self.trade_history)):
            weight = decay ** i

            if trade.result == "WIN":
                weighted_conf_win += trade.confidence_at_entry * weight
                w_win_total += weight
            elif trade.result == "LOSS":
                weighted_conf_loss += trade.confidence_at_entry * weight
                w_loss_total += weight

        if w_win_total > 0:
            self.learned_patterns["weighted_avg_conf_wins"] = round(
                weighted_conf_win / w_win_total, 1
            )
        if w_loss_total > 0:
            self.learned_patterns["weighted_avg_conf_losses"] = round(
                weighted_conf_loss / w_loss_total, 1
            )
