"""
============================================
🧠 THRESHOLD TUNER v2 — SPLIT CONTROL LOOPS
Self-correcting feedback loop that adjusts
MIN_GAP and MIN_CONFIDENCE independently.

Design Rules (non-negotiable):
  1. GAP  = quality control (how strong is the edge?)
  2. CONF = frequency control (how often do we trade?)
  3. Never adjust both simultaneously (lose diagnostic clarity)
  4. Adjustments are TINY (±0.002 gap / ±0.010 conf)
  5. Values are CLAMPED at all times
  6. Minimum 20 weighted trades before any tuning
  7. Window RESETS after every evaluation
  8. Drawdown-aware: MDD triggers gap tighten only
  9. State persists to disk with atomic write + backup
 10. Tuner is ADVISORY only — does not halt execution
============================================
"""

import json
import os
import time
import shutil
from datetime import datetime
from typing import Optional
from utils.logger import get_logger

# ══════════════════════════════════════════
# CONSTANTS
# ══════════════════════════════════════════

# ── Safety Clamps (absolute limits, NEVER violated) ──
MIN_GAP_FLOOR    = 0.035   # noise floor — below this we trade garbage
MIN_GAP_CEILING  = 0.080   # too tight — system misses every real trade
MIN_CONF_FLOOR   = 0.280   # reckless floor — below this = no edge filter
MIN_CONF_CEILING = 0.500   # over-strict — system locks itself out

# ── Target Performance Zones ──
WIN_RATE_LOW   = 0.42      # below this: quality is failing → tighten GAP
WIN_RATE_HIGH  = 0.65      # above this with few trades: too strict → loosen CONF
AVG_R_LOW      = 1.0       # below this: edge is thin → tighten GAP
AVG_R_CRITICAL = -1.5      # below this: emergency → double-tighten GAP

TRADE_COUNT_MIN = 3        # fewer than this per session: too strict → loosen CONF
TRADE_COUNT_MAX = 12       # more than this per session: too loose → tighten CONF

MDD_R_THRESHOLD = 3.0      # consecutive loss drawdown in R before tightening

# ── Evaluation Window ──
MIN_WEIGHTED_TRADES = 20   # weighted count before any decision is made

# ── Step Sizes (deliberately tiny) ──
GAP_STEP  = 0.002          # ±1 step per evaluation cycle
CONF_STEP = 0.010

# ── File Paths ──
TUNER_STATE_FILE  = "data/tuner_state.json"
TUNER_BACKUP_FILE = "data/tuner_state.bak.json"


# ══════════════════════════════════════════
# DATA MODEL
# ══════════════════════════════════════════

class TunerTrade:
    """A closed trade record, optionally quality-weighted."""
    __slots__ = ["result_r", "win", "gap", "confidence", "quality",
                 "weight", "timestamp"]

    def __init__(self, result_r: float, win: bool, gap: float,
                 confidence: float, quality: str = "UNKNOWN", weight: float = 1.0):
        self.result_r   = result_r
        self.win        = win
        self.gap        = gap
        self.confidence = confidence
        self.quality    = quality
        self.weight     = weight          # 1.5 for STRONG, 1.0 for rest
        self.timestamp  = time.time()


# ══════════════════════════════════════════
# TUNER
# ══════════════════════════════════════════

class ThresholdTuner:
    """
    Split-control feedback loop.

    GAP  is tuned on signal QUALITY signals (win rate, avg R, drawdown).
    CONF is tuned on FREQUENCY signals (trade count).

    Both loops are independent — only extreme cases touch both.

    Usage:
        tuner = ThresholdTuner(initial_gap=0.05, initial_conf=0.45)
        tuner.record_trade(...)         # after each closed position
        gap, conf = tuner.get_thresholds()  # called by decision engine
        status = tuner.get_status()     # for /status Telegram command
    """

    def __init__(self, initial_gap: float, initial_conf: float):
        self.logger = get_logger("threshold_tuner")

        # ── Live Thresholds ──
        self.current_gap  = float(initial_gap)
        self.current_conf = float(initial_conf)

        # ── Weighted history window ──
        self._history: list[TunerTrade] = []

        # ── Running drawdown tracker ──
        self._consecutive_losses: int = 0
        self._running_drawdown_r: float = 0.0

        # ── Audit Log ──
        self._tune_log: list[dict] = []

        # ── Oscillation guard: track last 3 actions ──
        self._last_actions: list[str] = []

        # ── Load persisted state ──
        self._load_state()

        self.logger.info(
            f"[TUNER] Initialized v2 | "
            f"GAP={self.current_gap:.3f} | CONF={self.current_conf:.3f}"
        )

    # ──────────────────────────────────────────────────────────
    # PUBLIC API
    # ──────────────────────────────────────────────────────────

    def record_trade(self, pnl: float, stop_distance: float, gap: float,
                     confidence: float, quality: str = "UNKNOWN"):
        """
        Record a completed trade into the evaluation window.

        Args:
            pnl:           Net PnL in rupees (positive = win, negative = loss).
            stop_distance: SL distance in index points (used for R-multiple).
            gap:           Dominance gap at entry (from signal metadata).
            confidence:    Engine weighted_score at entry (0–1).
            quality:       Entry quality tag: STRONG / MODERATE / WEAK / UNKNOWN.
        """
        # ── R-multiple ──
        # Nifty 1 lot ≈ 75 qty.  Using actual stop distance for realism.
        if stop_distance > 0:
            result_r = pnl / (stop_distance * 75)
        else:
            result_r = 1.0 if pnl > 0 else -1.0

        # ── Quality weighting ──
        # STRONG trades carry 1.5x influence (they define the edge).
        # WEAK trades are diluted to 0.7x (not representative of the system at its best).
        weight_map = {"STRONG": 1.5, "MODERATE": 1.0, "WEAK": 0.7}
        weight = weight_map.get(quality, 1.0)

        trade = TunerTrade(
            result_r=result_r,
            win=(pnl > 0),
            gap=gap,
            confidence=confidence,
            quality=quality,
            weight=weight,
        )
        self._history.append(trade)

        # ── Live drawdown tracker ──
        if pnl < 0:
            self._consecutive_losses += 1
            self._running_drawdown_r += abs(result_r)
        else:
            self._consecutive_losses = 0
            self._running_drawdown_r = 0.0

        # ── Weighted window size ──
        weighted_count = sum(t.weight for t in self._history)

        self.logger.info(
            f"[TUNER] Recorded | R={result_r:+.2f} | Win={pnl > 0} | "
            f"Gap={gap:.3f} | Q={quality} | Wt={weight} | "
            f"wN={weighted_count:.0f}/{MIN_WEIGHTED_TRADES} | "
            f"ConsecLoss={self._consecutive_losses}"
        )

        # ── Immediate drawdown guard (does not require full window) ──
        self._check_drawdown_guard()

        # ── Full evaluation (requires MIN_WEIGHTED_TRADES) ──
        self._maybe_tune()

    def get_thresholds(self) -> tuple:
        """Returns (min_gap, min_confidence) for the decision engine."""
        return self.current_gap, self.current_conf

    def get_status(self) -> dict:
        """Human-readable snapshot for /status Telegram or analyze_logs."""
        metrics = self._compute_metrics()
        weighted_count = sum(t.weight for t in self._history)
        return {
            "current_gap":      round(self.current_gap, 4),
            "current_conf":     round(self.current_conf, 3),
            "window_weighted":  round(weighted_count, 1),
            "window_raw":       len(self._history),
            "needed_for_eval":  max(0.0, MIN_WEIGHTED_TRADES - weighted_count),
            "consecutive_loss": self._consecutive_losses,
            "drawdown_r":       round(self._running_drawdown_r, 2),
            "metrics":          metrics,
            "last_action":      self._last_actions[-1] if self._last_actions else "NONE",
            "recent_tune_log":  self._tune_log[-5:],
        }

    # ──────────────────────────────────────────────────────────
    # METRICS
    # ──────────────────────────────────────────────────────────

    def _compute_metrics(self) -> Optional[dict]:
        """
        Compute weighted win_rate, weighted avg_r, raw trade_count.
        Returns None if weighted window is below MIN_WEIGHTED_TRADES.
        """
        total_weight = sum(t.weight for t in self._history)
        if total_weight < MIN_WEIGHTED_TRADES:
            return None

        win_weight = sum(t.weight for t in self._history if t.win)
        win_rate   = win_weight / total_weight

        avg_r = sum(t.result_r * t.weight for t in self._history) / total_weight

        # Max drawdown: worst contiguous losing run in R (weighted)
        max_dd = 0.0
        running = 0.0
        for t in self._history:
            if not t.win:
                running += abs(t.result_r) * t.weight
                max_dd = max(max_dd, running)
            else:
                running = 0.0

        return {
            "win_rate":    round(win_rate, 3),
            "avg_r":       round(avg_r, 3),
            "trade_count": len(self._history),
            "max_dd_r":    round(max_dd, 2),
        }

    # ──────────────────────────────────────────────────────────
    # DRAWDOWN GUARD (real-time, pre-window)
    # ──────────────────────────────────────────────────────────

    def _check_drawdown_guard(self):
        """
        Tighten GAP immediately if we hit MDD_R_THRESHOLD in R,
        regardless of window size. This is the emergency brake.
        """
        if self._running_drawdown_r >= MDD_R_THRESHOLD and self._consecutive_losses >= 3:
            old_gap = self.current_gap
            self.current_gap = min(
                self.current_gap + GAP_STEP,
                MIN_GAP_CEILING
            )
            if self.current_gap != old_gap:
                self.logger.warning(
                    f"[TUNER] !! DRAWDOWN GUARD | "
                    f"ConsecLoss={self._consecutive_losses} | "
                    f"MDD_R={self._running_drawdown_r:.2f} | "
                    f"GAP: {old_gap:.3f}-->{self.current_gap:.3f}"
                )
                self._record_action(
                    "DRAWDOWN_GUARD",
                    f"MDD_R={self._running_drawdown_r:.2f} ({self._consecutive_losses} losses)",
                    gap_delta=self.current_gap - old_gap,
                    conf_delta=0.0,
                    metrics=None,
                    save=True
                )

    # ──────────────────────────────────────────────────────────
    # MAIN TUNING LOGIC
    # ──────────────────────────────────────────────────────────

    def _maybe_tune(self):
        """
        Evaluate the window and apply ONE targeted adjustment.

        Split control:
          GAP  ← quality signals (win rate, avg R, drawdown)
          CONF ← frequency signals (trade count)

        Only in extreme overtrading+quality failure do we touch both.
        """
        metrics = self._compute_metrics()
        if metrics is None:
            return  # Window not full yet

        win_rate    = metrics["win_rate"]
        avg_r       = metrics["avg_r"]
        trade_count = metrics["trade_count"]
        max_dd_r    = metrics["max_dd_r"]

        old_gap  = self.current_gap
        old_conf = self.current_conf
        action   = "NO_CHANGE"
        reason   = ""
        gap_delta  = 0.0
        conf_delta = 0.0

        # ── Oscillation guard: if last 3 actions alternate TIGHTEN/LOOSEN, halve step ──
        step_multiplier = 1.0
        if len(self._last_actions) >= 3:
            recent = self._last_actions[-3:]
            if (recent[0] != recent[1] != recent[2]) and \
               any("TIGHTEN" in a for a in recent) and \
               any("LOOSEN" in a for a in recent):
                step_multiplier = 0.5
                self.logger.warning(
                    "[TUNER] !! Oscillation detected — step size halved this cycle"
                )

        effective_gap_step  = GAP_STEP  * step_multiplier
        effective_conf_step = CONF_STEP * step_multiplier

        # ══════════════════════════════════════════
        # PRIORITY 1 — Emergency (critical avg R)
        # Touch GAP only (quality)
        # ══════════════════════════════════════════
        if avg_r < AVG_R_CRITICAL:
            self.current_gap += effective_gap_step * 2   # Double step for emergency
            action = "EMERGENCY_TIGHTEN_GAP"
            reason = f"Avg R critically negative ({avg_r:.2f})"
            gap_delta = self.current_gap - old_gap

        # ══════════════════════════════════════════
        # PRIORITY 2 — Quality degrading (win rate + avg R low)
        # Touch GAP only — we're taking low-quality trades
        # ══════════════════════════════════════════
        elif win_rate < WIN_RATE_LOW and avg_r < AVG_R_LOW:
            self.current_gap += effective_gap_step
            action = "TIGHTEN_GAP"
            reason = f"Quality failing: WR={win_rate:.2f} AvgR={avg_r:.2f}"
            gap_delta = self.current_gap - old_gap

        # ══════════════════════════════════════════
        # PRIORITY 3 — Overtrading (too many trades)
        # Touch CONF only — system frequency is too high
        # ══════════════════════════════════════════
        elif trade_count > TRADE_COUNT_MAX:
            self.current_conf += effective_conf_step
            action = "TIGHTEN_CONF"
            reason = f"Too many trades ({trade_count} > {TRADE_COUNT_MAX})"
            conf_delta = self.current_conf - old_conf

        # ══════════════════════════════════════════
        # PRIORITY 4 — Drawdown (in-window check)
        # Touch GAP only — even with decent win rate
        # ══════════════════════════════════════════
        elif max_dd_r > MDD_R_THRESHOLD:
            self.current_gap += effective_gap_step
            action = "TIGHTEN_GAP_DRAWDOWN"
            reason = f"In-window MDD too high ({max_dd_r:.2f}R)"
            gap_delta = self.current_gap - old_gap

        # ══════════════════════════════════════════
        # PRIORITY 5 — Too strict (few trades, good win rate)
        # Touch CONF only — ease the frequency gate
        # ══════════════════════════════════════════
        elif trade_count < TRADE_COUNT_MIN and win_rate > WIN_RATE_HIGH:
            self.current_conf -= effective_conf_step
            action = "LOOSEN_CONF"
            reason = f"Too few trades ({trade_count}) with high WR ({win_rate:.2f})"
            conf_delta = self.current_conf - old_conf

        # ══════════════════════════════════════════
        # PRIORITY 6 — Extreme: both overtrading AND low quality
        # Touch both (only here)
        # ══════════════════════════════════════════
        elif trade_count > TRADE_COUNT_MAX and win_rate < WIN_RATE_LOW:
            self.current_gap  += effective_gap_step
            self.current_conf += effective_conf_step
            action = "TIGHTEN_BOTH"
            reason = f"Extreme: N={trade_count} trades AND WR={win_rate:.2f}"
            gap_delta  = self.current_gap  - old_gap
            conf_delta = self.current_conf - old_conf

        # ── Apply Safety Clamps ──
        self.current_gap  = max(MIN_GAP_FLOOR,   min(self.current_gap,  MIN_GAP_CEILING))
        self.current_conf = max(MIN_CONF_FLOOR,   min(self.current_conf, MIN_CONF_CEILING))

        # ── Persist and log ──
        if action != "NO_CHANGE":
            self._record_action(action, reason, gap_delta, conf_delta, metrics, save=True)
            self.logger.info(
                f"[TUNER] >> {action} | {reason} | "
                f"GAP: {old_gap:.3f}-->{self.current_gap:.3f} | "
                f"CONF: {old_conf:.3f}-->{self.current_conf:.3f}"
            )
        else:
            self.logger.info(
                f"[TUNER] OK In target zone -- no change. "
                f"WR={win_rate:.2f} AvgR={avg_r:.2f} N={trade_count} MDD={max_dd_r:.2f}R"
            )

        # ── Always reset window ──
        self._history = []
        self.logger.info("[TUNER] Window reset.")

    # ──────────────────────────────────────────────────────────
    # HELPERS
    # ──────────────────────────────────────────────────────────

    def _record_action(self, action: str, reason: str, gap_delta: float,
                       conf_delta: float, metrics: Optional[dict], save: bool):
        self._last_actions.append(action)
        if len(self._last_actions) > 10:
            self._last_actions.pop(0)

        entry = {
            "ts":         datetime.now().isoformat(timespec="seconds"),
            "action":     action,
            "reason":     reason,
            "gap":        f"{self.current_gap - gap_delta:.3f}→{self.current_gap:.3f}",
            "conf":       f"{self.current_conf - conf_delta:.3f}→{self.current_conf:.3f}",
            "metrics":    metrics,
        }
        self._tune_log.append(entry)
        if len(self._tune_log) > 50:
            self._tune_log.pop(0)

        if save:
            self._save_state()

    # ──────────────────────────────────────────────────────────
    # PERSISTENCE — atomic write with backup
    # ──────────────────────────────────────────────────────────

    def _load_state(self):
        """
        Load persisted thresholds from disk.
        Falls back to backup file if primary is corrupt.
        Clamps all loaded values before accepting.
        """
        for filepath in (TUNER_STATE_FILE, TUNER_BACKUP_FILE):
            if not os.path.exists(filepath):
                continue
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    state = json.load(f)

                loaded_gap  = float(state.get("current_gap",  self.current_gap))
                loaded_conf = float(state.get("current_conf", self.current_conf))

                self.current_gap  = max(MIN_GAP_FLOOR,  min(loaded_gap,  MIN_GAP_CEILING))
                self.current_conf = max(MIN_CONF_FLOOR, min(loaded_conf, MIN_CONF_CEILING))
                self._tune_log    = state.get("tune_log", [])[-50:]
                self._last_actions = state.get("last_actions", [])[-10:]

                self.logger.info(
                    f"[TUNER] Loaded from {os.path.basename(filepath)}: "
                    f"GAP={self.current_gap:.3f} CONF={self.current_conf:.3f}"
                )
                return  # Loaded successfully

            except Exception as e:
                self.logger.warning(
                    f"[TUNER] Failed to load {filepath}: {e} — trying backup..."
                )

        self.logger.info("[TUNER] No persisted state found — using initial defaults.")

    def _save_state(self):
        """
        Atomic write: write to .tmp first, then rename.
        Copy current to .bak before overwriting.
        This guarantees no corrupt state file survives a crash.
        """
        tmp_path = TUNER_STATE_FILE + ".tmp"
        try:
            os.makedirs(os.path.dirname(TUNER_STATE_FILE), exist_ok=True)

            state = {
                "current_gap":   self.current_gap,
                "current_conf":  self.current_conf,
                "tune_log":      self._tune_log,
                "last_actions":  self._last_actions,
                "last_saved":    datetime.now().isoformat(timespec="seconds"),
            }

            # 1. Write to temp file
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2)

            # 2. Backup existing state
            if os.path.exists(TUNER_STATE_FILE):
                shutil.copy2(TUNER_STATE_FILE, TUNER_BACKUP_FILE)

            # 3. Atomic rename (safe even if process dies mid-write)
            os.replace(tmp_path, TUNER_STATE_FILE)

        except Exception as e:
            self.logger.error(f"[TUNER] Save failed: {e}")
            # Clean up temp if it exists
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass
