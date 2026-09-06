"""
================================================================================
EXCHANGE SESSION ORCHESTRATOR  —  Layer 0 of the system architecture
================================================================================

Responsibilities (ONLY these — nothing else lives here):
  1. Compute market session state from the system clock
  2. Expose polling intervals driven by session state
  3. Expose runtime posture driven by session + data health
  4. Provide a sleep primitive that main.py uses instead of asyncio.sleep(1)
  5. Log ONLY on state transitions — completely silent in steady state

Hierarchy:
  ExchangeSessionOrchestrator
       ↓
  DataManager polling            (frequency controlled here)
       ↓
  Strategy / Agents              (enabled only when posture == LIVE)
       ↓
  Execution Layer

Session States
--------------
  CLOSED          — nights, weekends          — poll 1800s
  PRE_MARKET      — 08:00–09:15              — poll  60s
  OPEN_STORM — 09:15–09:28              — poll  15s
  LIVE_MARKET     — 09:20–14:00              — poll   1s
  LUNCH_DRIFT     — 14:00–14:15 (signals ON, -10% conf) — poll 5s
  POWER_HOUR      — 14:15–15:30             — poll   1s
  POST_MARKET     — 15:30–16:00             — poll  60s

Runtime Postures
----------------
  STANDBY     — market closed / pre-market / post-market
  OBSERVATION — opening session or data degraded (monitoring only)
  LIVE        — active session + fresh data
  DEGRADED    — session open but candle data stale > 90s
  HALTED      — external kill switch

Data Health
-----------
  FRESH       — last candle age < 90s
  STALE       — last candle age 90s–300s
  DEAD        — last candle age > 300s (or no data at all)
"""

import asyncio
import logging
import time as _time
from datetime import datetime, time as dtime
from enum import Enum, auto
from typing import Tuple

logger = logging.getLogger("session_orchestrator")


from dataclasses import dataclass

# ── Enums ─────────────────────────────────────────────────────────────────────

class MarketSessionState(Enum):
    CLOSED          = auto()   # Weekday nights
    WEEKEND_CLOSED  = auto()   # Saturday/Sunday or detected holidays
    PRE_MARKET      = auto()
    OPEN_STORM      = auto()
    LIVE_MARKET     = auto()
    LUNCH_DRIFT     = auto()
    POWER_HOUR      = auto()
    EXIT_WINDOW     = auto()   # 15:20–15:40 — No new trades, exit & flatten only
    POST_MARKET     = auto()


class RuntimePosture(Enum):
    STANDBY     = auto()   # Market closed / pre-open / post-close
    OBSERVATION = auto()   # Opening window or data degraded — no signals
    LIVE        = auto()   # Active session + fresh data — full pipeline
    DEGRADED    = auto()   # Session open but candle feed stale
    HALTED      = auto()   # External kill switch


class DataHealth(Enum):
    FRESH = auto()   # last candle age < 90s
    STALE = auto()   # last candle age 90–300s
    DEAD  = auto()   # last candle age > 300s or no data


@dataclass(frozen=True)
class SessionCapabilities:
    """Explicit capability matrix per session state."""
    can_open_positions: bool
    can_modify_positions: bool
    can_exit_positions: bool
    can_collect_market_data: bool
    can_generate_signals: bool
    can_publish_orders: bool


@dataclass(frozen=True)
class RuntimeState:
    """Immutable snapshot of exchange session, posture, data health, and polling interval."""
    session: MarketSessionState
    posture: RuntimePosture
    data_health: DataHealth
    poll_interval_s: float
    is_trading_allowed: bool
    capabilities: SessionCapabilities | None = None


# ── Poll intervals (seconds) per session state ────────────────────────────────
_POLL_INTERVALS = {
    MarketSessionState.CLOSED:           300,   # 5 min — weekday nights
    MarketSessionState.WEEKEND_CLOSED:  1800,   # 30 min — weekends/holidays
    MarketSessionState.PRE_MARKET:        60,   # 1 min
    MarketSessionState.OPEN_STORM:        15,   # 15 s
    MarketSessionState.LIVE_MARKET:        1,   # 1 s
    MarketSessionState.LUNCH_DRIFT:        5,   # 5 s
    MarketSessionState.POWER_HOUR:         1,   # 1 s
    MarketSessionState.EXIT_WINDOW:        1,   # 1 s — rapid exit monitoring
    MarketSessionState.POST_MARKET:       60,   # 1 min
}

# ── Dashboard labels ──────────────────────────────────────────────────────────
_SESSION_LABELS = {
    MarketSessionState.CLOSED:          "🔴 MARKET CLOSED — Standby",
    MarketSessionState.WEEKEND_CLOSED:  "🔴 MARKET CLOSED — Weekend/Holiday",
    MarketSessionState.PRE_MARKET:      "🟡 PRE-MARKET — Preparation",
    MarketSessionState.OPEN_STORM:      "🟠 OPENING SESSION — High Volatility Protection",
    MarketSessionState.LIVE_MARKET:     "🟢 LIVE MARKET — Active",
    MarketSessionState.LUNCH_DRIFT:     "🟡 LUNCH DRIFT — Reduced Activity",
    MarketSessionState.POWER_HOUR:      "🟢 POWER HOUR — Active",
    MarketSessionState.EXIT_WINDOW:     "🟠 EXIT WINDOW — Risk Reduction & Force Flattening",
    MarketSessionState.POST_MARKET:     "🔴 POST-MARKET — Standby",
}

_POSTURE_LABELS = {
    RuntimePosture.STANDBY:     "STANDBY",
    RuntimePosture.OBSERVATION: "OBSERVATION",
    RuntimePosture.LIVE:        "LIVE",
    RuntimePosture.DEGRADED:    "DEGRADED",
    RuntimePosture.HALTED:      "HALTED",
}

_DATA_HEALTH_LABELS = {
    DataHealth.FRESH: "FRESH",
    DataHealth.STALE: "STALE",
    DataHealth.DEAD:  "DEAD",
}

# Candle-staleness thresholds are now derived from the candle timeframe.
# See ExchangeSessionOrchestrator.__init__ for the computation.
# These module-level constants are kept as defaults / documentation.
_DEFAULT_CANDLE_TF_SECONDS = 60   # 1-minute candles
_HOLIDAY_THRESHOLD_S = 3600  # If >1h stale during live hours, assume holiday

# Lunch confidence penalty (applied by caller via get_confidence_penalty())
LUNCH_CONFIDENCE_PENALTY = 0.10   # –10%

# ── P0: Session & Risk Cutoff Guard Defaults (3 Aug 2026 Sync) ───────────────
# Single source of truth defaults (overridden dynamically via Settings if passed)
EOD_NO_NEW_ENTRY_TIME = dtime(15, 20)  # 15:20 — entry cutoff
EOD_FORCE_EXIT_TIME   = dtime(15, 24)  # 15:24 — hard force-exit deadline before broker 15:25 squareoff
FO_MARKET_CLOSE_TIME  = dtime(15, 40)  # 15:40 — F&O options market close
POST_MARKET_END_TIME  = dtime(16, 0)   # 16:00 — post-market end


# ─────────────────────────────────────────────────────────────────────────────

class ExchangeSessionOrchestrator:
    """
    Layer 0: Exchange clock + data health → RuntimePosture.

    Usage in main.py:
        orchestrator = ExchangeSessionOrchestrator()

        # In the main while loop:
        await orchestrator.sleep_until_next_cycle()

        # At the top of _run_cycle_inner:
        posture = orchestrator.get_posture(last_candle_ts)
        if posture not in (RuntimePosture.LIVE, RuntimePosture.DEGRADED):
            self._monitor_only_with_posture(posture)
            return

    Backwards compat:
        SessionGuard.can_trade(settings) still works — delegates here.
    """

    def __init__(self, *, _suppress_logs: bool = False, candle_tf_seconds: int = _DEFAULT_CANDLE_TF_SECONDS):
        self._last_session_state: MarketSessionState | None = None
        self._last_posture: RuntimePosture | None = None
        self._last_data_health: DataHealth | None = None
        self._halted: bool = False
        self._suppress_logs: bool = _suppress_logs

        # ── Timeframe-aware freshness thresholds ──────────────────
        # For 1-minute candles (60s):
        #   FRESH  < 120s  (2× interval) — normal candle age + broker jitter
        #   STALE  < 240s  (4× interval) — missed candle + transport delay
        #   DEAD   > 420s  (7× interval) — feed genuinely broken
        self._candle_tf_s: int = candle_tf_seconds
        self._fresh_threshold_s: float = candle_tf_seconds * 2.0
        self._stale_threshold_s: float = candle_tf_seconds * 4.0
        self._dead_threshold_s:  float = candle_tf_seconds * 7.0

        # ── Per-cycle evaluation cache ──────────────────────────────
        # Prevents redundant recomputation within the same cycle.
        # Multiple callers (get_posture, get_poll_interval, dashboard)
        # all see the same consistent snapshot.
        # TTL=2.0s covers a full 1s polling cycle + REST fetch overhead.
        self._cache_session: MarketSessionState | None = None
        self._cache_posture: RuntimePosture | None = None
        self._cache_data_health: DataHealth | None = None
        self._cache_ts: float = 0.0          # monotonic timestamp
        self._cache_ttl: float = 2.0         # seconds — covers full REST cycle

    # ── Public API ─────────────────────────────────────────────────────────────

    def _invalidate_cache(self) -> None:
        """Force next _evaluate() call to recompute.
        Must be called whenever external state (halt/resume) changes
        so that sleep_until_next_cycle picks up the new posture immediately.
        """
        self._cache_ts = 0.0

    def halt(self):
        """Externally triggered halt (e.g. kill switch, broker failure)."""
        self._halted = True
        self._invalidate_cache()

    def resume(self):
        """Clear external halt."""
        self._halted = False
        self._invalidate_cache()

    def _is_cache_valid(self) -> bool:
        """True if the per-cycle cache is still fresh."""
        return (_time.monotonic() - self._cache_ts) < self._cache_ttl

    def _evaluate(self, last_candle_ts=None) -> None:
        """
        Single authoritative evaluation point per cycle.
        Computes session state, data health, and posture atomically,
        caches all three, and logs only genuine transitions.
        """
        if self._is_cache_valid():
            return  # Use cached values

        # 1. Session state from wall clock
        state = self._compute_state_for_time(datetime.now().time())

        # Holiday auto-fallback: if we're in a live session but candle
        # data is extremely stale (>1 hr), treat as holiday / closed.
        # v3.9 FIX: Suppress during OPEN_STORM (09:15–09:28) and the first
        # 15 minutes after market open.  At 09:15 the most recent candle
        # is ALWAYS from the previous session (possibly 42h+ for Monday).
        # The holiday check only makes sense once the feed has had time
        # to deliver its first live candle (typically by 09:20).
        _holiday_eligible_sessions = (
            MarketSessionState.LIVE_MARKET,
            MarketSessionState.LUNCH_DRIFT,
            MarketSessionState.POWER_HOUR,
        )
        if state in _holiday_eligible_sessions:
            if last_candle_ts is not None:
                try:
                    ts = (last_candle_ts.to_pydatetime()
                          if hasattr(last_candle_ts, "to_pydatetime")
                          else last_candle_ts)
                    age_s = (datetime.now() - ts).total_seconds()
                    if age_s > _HOLIDAY_THRESHOLD_S:
                        logger.warning(
                            f"[HOLIDAY_FALLBACK] Candle age {age_s:.0f}s > "
                            f"{_HOLIDAY_THRESHOLD_S}s during {state.name} — "
                            f"assuming holiday/closed. last_candle={ts}"
                        )
                        state = MarketSessionState.WEEKEND_CLOSED
                except Exception:
                    pass

        # 2. Data health
        data_health = self._compute_data_health(last_candle_ts)

        # 3. Posture
        if self._halted:
            posture = RuntimePosture.HALTED
        elif state in (MarketSessionState.CLOSED,
                       MarketSessionState.WEEKEND_CLOSED,
                       MarketSessionState.PRE_MARKET,
                       MarketSessionState.POST_MARKET):
            posture = RuntimePosture.STANDBY
        elif state == MarketSessionState.OPEN_STORM:
            posture = RuntimePosture.OBSERVATION
        elif state in (MarketSessionState.LIVE_MARKET,
                       MarketSessionState.LUNCH_DRIFT,
                       MarketSessionState.POWER_HOUR):
            if data_health in (DataHealth.DEAD, DataHealth.STALE):
                posture = RuntimePosture.DEGRADED
            else:
                posture = RuntimePosture.LIVE
        else:
            posture = RuntimePosture.STANDBY

        # 4. Log transitions (only genuine changes)
        self._log_state_transition(state)
        self._log_posture_transition(posture, state, data_health)

        # 5. Cache
        self._cache_session = state
        self._cache_data_health = data_health
        self._cache_posture = posture
        self._cache_ts = _time.monotonic()

    def get_runtime_state(self, last_candle_ts=None) -> RuntimeState:
        """
        Single authoritative runtime state snapshot for the current cycle.
        Returns immutable RuntimeState containing session, posture, data health,
        poll interval, and whether trade entries are allowed.
        """
        self._evaluate(last_candle_ts)
        session = self._cache_session
        posture = self._cache_posture
        health = self._cache_data_health
        poll_s = self.get_poll_interval_seconds(last_candle_ts)
        trading_allowed = posture in (RuntimePosture.LIVE, RuntimePosture.DEGRADED)
        return RuntimeState(
            session=session,
            posture=posture,
            data_health=health,
            poll_interval_s=poll_s,
            is_trading_allowed=trading_allowed,
        )

    def get_session_state(self, last_candle_ts=None) -> MarketSessionState:
        """Current NSE session state derived from wall clock and data freshness."""
        self._evaluate(last_candle_ts)
        return self._cache_session

    def get_data_health(self, last_candle_ts=None) -> DataHealth:
        """
        Evaluate candle freshness.

        Args:
            last_candle_ts: datetime | pd.Timestamp | None — timestamp of the
                            most recent candle in the OHLCV dataframe.
        """
        self._evaluate(last_candle_ts)
        return self._cache_data_health

    def _compute_data_health(self, last_candle_ts) -> DataHealth:
        """Compute data health using timeframe-aware thresholds."""
        if last_candle_ts is None:
            return DataHealth.DEAD

        # Non-live sessions (expected inactivity): if candles are hydrated, return FRESH.
        # Feed staleness decay should only evaluate during active trading sessions.
        state = self._compute_state_for_time(datetime.now().time())
        if state in (MarketSessionState.CLOSED,
                       MarketSessionState.WEEKEND_CLOSED,
                       MarketSessionState.PRE_MARKET,
                       MarketSessionState.POST_MARKET):
            return DataHealth.FRESH

        try:
            if hasattr(last_candle_ts, "to_pydatetime"):
                last_candle_ts = last_candle_ts.to_pydatetime()
            age_s = (datetime.now() - last_candle_ts).total_seconds()

            logger.debug(
                f"HEALTH_CHECK | now={datetime.now().strftime('%H:%M:%S')} "
                f"last_candle={last_candle_ts} "
                f"age={age_s:.1f}s"
            )
        except Exception as e:
            logger.error(f"HEALTH_CHECK | Exception computing age: {e} | last_candle_ts={last_candle_ts}")
            return DataHealth.DEAD

        if age_s < self._fresh_threshold_s:
            return DataHealth.FRESH
        elif age_s < self._stale_threshold_s:
            return DataHealth.STALE
        else:
            return DataHealth.DEAD

    def get_posture(self, last_candle_ts=None) -> RuntimePosture:
        """
        Compute and return the current RuntimePosture.

        Args:
            last_candle_ts: passed to get_data_health(); may be None if no
                            candles have been hydrated yet.
        """
        self._evaluate(last_candle_ts)
        return self._cache_posture

    def get_poll_interval_seconds(self, last_candle_ts=None) -> float:
        """Return how long main.py should sleep before the next cycle.

        Posture is the AUTHORITATIVE source for cadence:
            HALTED   → 60s   (passive observability)
            STANDBY  → session-derived (300s/1800s/60s)
            DEGRADED → 5s    (reduced activity, not full speed)
            LIVE     → session-derived (typically 1s)
        """
        self._evaluate(last_candle_ts)
        if self._cache_posture == RuntimePosture.HALTED:
            return 60.0
        if self._cache_posture == RuntimePosture.DEGRADED:
            return 5.0
        return float(_POLL_INTERVALS.get(self._cache_session, 60.0))

    def get_confidence_penalty(self) -> float:
        """
        Returns a multiplier to apply to agent confidence.
        During LUNCH_DRIFT: 0.90 (–10%).
        All other times: 1.0 (no penalty).
        """
        state = self.get_session_state()
        if state == MarketSessionState.LUNCH_DRIFT:
            return 1.0 - LUNCH_CONFIDENCE_PENALTY
        return 1.0

    # ── P0: EOD Flattening & Centralized Session Guard ───────────────────────────────

    def is_entry_allowed(self, now: datetime | None = None) -> bool:
        """
        Single source of truth: returns True if current time permits new trade entries.

        Policy: Reject all new trade entries at or after 15:20 IST.
        Trade entries are strictly prohibited during EXIT_WINDOW, POST_MARKET, or CLOSED states.
        """
        current_time = (now or datetime.now()).time()
        session = self._compute_state_for_time(current_time)
        return session in (
            MarketSessionState.LIVE_MARKET,
            MarketSessionState.LUNCH_DRIFT,
            MarketSessionState.POWER_HOUR,
        ) and current_time < EOD_NO_NEW_ENTRY_TIME

    def should_force_exit(self, now: datetime | None = None) -> bool:
        """
        Single source of truth: returns True when ALL open intraday positions must be force-closed.

        Policy: Force-flatten at or after 15:24 IST (1 min buffer before broker 15:25 square-off).
        Active positions are force-closed during EXIT_WINDOW state.
        """
        current_time = (now or datetime.now()).time()
        return current_time >= EOD_FORCE_EXIT_TIME and current_time < POST_MARKET_END_TIME

    def is_post_market(self, now: datetime | None = None) -> bool:
        """Returns True if current session is strictly post-market (15:40 to 16:00 IST)."""
        current_time = (now or datetime.now()).time()
        return self._compute_state_for_time(current_time) == MarketSessionState.POST_MARKET

    def get_capabilities(self, now: datetime | None = None) -> SessionCapabilities:
        """
        Capability-based session governance matrix.
        Maps current MarketSessionState -> SessionCapabilities permissions.
        """
        current_time = (now or datetime.now()).time()
        session = self._compute_state_for_time(current_time)

        if session in (MarketSessionState.LIVE_MARKET, MarketSessionState.LUNCH_DRIFT, MarketSessionState.POWER_HOUR):
            can_open = current_time < EOD_NO_NEW_ENTRY_TIME
            return SessionCapabilities(
                can_open_positions=can_open,
                can_modify_positions=True,
                can_exit_positions=True,
                can_collect_market_data=True,
                can_generate_signals=can_open,
                can_publish_orders=True,
            )
        elif session == MarketSessionState.EXIT_WINDOW:
            return SessionCapabilities(
                can_open_positions=False,
                can_modify_positions=True,
                can_exit_positions=True,
                can_collect_market_data=True,
                can_generate_signals=False,
                can_publish_orders=True,
            )
        elif session == MarketSessionState.POST_MARKET:
            return SessionCapabilities(
                can_open_positions=False,
                can_modify_positions=False,
                can_exit_positions=False,
                can_collect_market_data=True,
                can_generate_signals=False,
                can_publish_orders=False,
            )
        else:  # PRE_MARKET, OPEN_STORM, CLOSED, WEEKEND_CLOSED
            is_pre = session in (MarketSessionState.PRE_MARKET, MarketSessionState.OPEN_STORM)
            return SessionCapabilities(
                can_open_positions=False,
                can_modify_positions=False,
                can_exit_positions=False,
                can_collect_market_data=is_pre,
                can_generate_signals=False,
                can_publish_orders=False,
            )

    def is_entry_cutoff(self) -> bool:
        """Backwards-compatible alias: returns True when new trade entries are prohibited."""
        return not self.is_entry_allowed()

    def is_force_exit_time(self) -> bool:
        """Backwards-compatible alias: returns True when hard force-exit is active."""
        return self.should_force_exit()

    def is_live(self, last_candle_ts=None) -> bool:
        """
        True when market session is active (data ingestion & monitoring active).
        Includes LIVE_MARKET, LUNCH_DRIFT, POWER_HOUR, and EXIT_WINDOW.
        """
        if last_candle_ts is not None:
            session = self.get_session_state(last_candle_ts)
        else:
            session = self._compute_state_for_time(datetime.now().time())
            if self._is_cache_valid() and self._cache_session == MarketSessionState.WEEKEND_CLOSED:
                session = MarketSessionState.WEEKEND_CLOSED

        return session in (
            MarketSessionState.LIVE_MARKET,
            MarketSessionState.LUNCH_DRIFT,
            MarketSessionState.POWER_HOUR,
            MarketSessionState.EXIT_WINDOW,
        )

    def get_dashboard_fields(self, last_candle_ts=None) -> dict:
        """
        Returns a dict of session awareness fields for _update_dashboard().
        """
        session = self.get_session_state(last_candle_ts)
        health  = self.get_data_health(last_candle_ts)
        posture = self.get_posture(last_candle_ts)
        return {
            "session_state":   _SESSION_LABELS.get(session, session.name),
            "runtime_posture": _POSTURE_LABELS.get(posture, posture.name),
            "data_health":     _DATA_HEALTH_LABELS.get(health, health.name),
            "poll_interval_s": _POLL_INTERVALS.get(session, 60),
        }

    async def sleep_until_next_cycle(self, last_candle_ts=None) -> None:
        """
        Canonical sleep primitive for main.py.
        """
        interval = self.get_poll_interval_seconds(last_candle_ts)
        await asyncio.sleep(interval)

    # ── Backwards compatibility shim ───────────────────────────────────────────

    @staticmethod
    def can_trade(settings) -> Tuple[bool, str]:
        """
        Drop-in replacement for the old SessionGuard.can_trade(settings).
        """
        o = ExchangeSessionOrchestrator(_suppress_logs=True)
        live = o.is_live()
        if live:
            return True, "Session OK"
        state = o.get_session_state()
        return False, _SESSION_LABELS.get(state, state.name)

    # ── Internal ───────────────────────────────────────────────────────────────

    def _compute_state_for_time(self, t: dtime) -> MarketSessionState:
        """
        Pure function: map a time-of-day → MarketSessionState.
        Weekday session windows (all IST):
          08:00–09:15  PRE_MARKET
          09:15–09:28  OPEN_STORM
          09:28–14:00  LIVE_MARKET
          14:00–14:15  LUNCH_DRIFT
          14:15–15:20  POWER_HOUR
          15:20–15:40  EXIT_WINDOW
          15:40–16:00  POST_MARKET
          > 16:00      CLOSED
        """
        now_dt = datetime.now()
        if now_dt.weekday() >= 5:
            return MarketSessionState.WEEKEND_CLOSED

        if t < dtime(8, 0):
            return MarketSessionState.CLOSED
        elif t < dtime(9, 15):
            return MarketSessionState.PRE_MARKET
        elif t < dtime(9, 28):
            return MarketSessionState.OPEN_STORM
        elif t < dtime(14, 0):
            return MarketSessionState.LIVE_MARKET
        elif t < dtime(14, 15):
            return MarketSessionState.LUNCH_DRIFT
        elif t < dtime(15, 20):
            return MarketSessionState.POWER_HOUR
        elif t < dtime(15, 40):
            return MarketSessionState.EXIT_WINDOW
        elif t < dtime(16, 0):
            return MarketSessionState.POST_MARKET
        else:
            return MarketSessionState.CLOSED

    def _log_state_transition(self, new_state: MarketSessionState) -> None:
        """Log only when session state changes. Silent in steady state."""
        if self._suppress_logs:
            self._last_session_state = new_state
            return
        if new_state != self._last_session_state:
            old = self._last_session_state.name if self._last_session_state else "BOOT"
            logger.info(
                f"📅 Market session: {old} → {new_state.name} | "
                f"{_SESSION_LABELS.get(new_state, '')} | "
                f"Poll interval: {_POLL_INTERVALS.get(new_state, '?')}s"
            )
            self._last_session_state = new_state

    def _log_posture_transition(
        self,
        new_posture: RuntimePosture,
        session: MarketSessionState,
        health: DataHealth,
    ) -> None:
        """Log only when posture changes or live feed health changes. Silent in steady state."""
        if self._suppress_logs:
            self._last_posture = new_posture
            self._last_data_health = health
            return

        posture_changed = new_posture != self._last_posture
        health_changed_in_active_session = (
            health != self._last_data_health and
            new_posture in (RuntimePosture.LIVE, RuntimePosture.DEGRADED)
        )

        if posture_changed or health_changed_in_active_session:
            old_posture = self._last_posture.name if self._last_posture else "BOOT"
            logger.info(
                f"⚡ Runtime posture: {old_posture} → {new_posture.name} | "
                f"Session={session.name} | DataHealth={health.name}"
            )
            self._last_posture = new_posture
            self._last_data_health = health


# ── Singleton (module-level, shared across the process) ───────────────────────
# Import this in main.py:  from core.session_guard import orchestrator
orchestrator = ExchangeSessionOrchestrator()


# ── Legacy alias (keeps old imports working without changes) ───────────────────
class SessionGuard:
    """
    Backwards-compatibility shim.
    Old code: SessionGuard.can_trade(settings)
    This now delegates to ExchangeSessionOrchestrator.
    """
    @staticmethod
    def can_trade(settings) -> Tuple[bool, str]:
        return ExchangeSessionOrchestrator.can_trade(settings)
