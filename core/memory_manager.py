"""
============================================
🧠 MEMORY MANAGER — THE SYSTEM'S HIPPOCAMPUS
Tracks recent performance, win/loss streaks,
and localized market behavior to dynamically
adjust engine thresholds.
============================================
"""

from typing import List, Dict
from datetime import datetime
import logging
from config.settings import Settings
from core.db_manager import DBManager

logger = logging.getLogger("memory_manager")

class MemoryManager:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.recent_trades: List[Dict] = []  # Stores dicts: {'time', 'result', 'pnl', 'regime'}
        self.max_memory_size = 20
        
        # Adaptive State
        self.current_streak = 0
        self.is_tilted = False
        self.choppy_blocks = 0

        # ── 📦 SQLite Persistence ──
        self.db = DBManager()

    async def boot(self):
        """Loads memory from disk on startup with corruption fallback."""
        try:
            await self.db.initialize()
            rows = await self.db.load_recent_trades(limit=self.max_memory_size)
            
            # SQLite returns descending (newest first), reverse it for chronological processing
            for row in reversed(rows):
                self.recent_trades.append({
                    "time": row[0],
                    "result": row[1],
                    "pnl": row[2],
                    "regime": row[3]
                })
                self._update_state(row[1]) 
                
            logger.info(f"🧠 Memory Boot Complete: Loaded {len(self.recent_trades)} historical trades.")
            if self.is_tilted:
                logger.warning("⚠️ System woke up in TILTED state. Defense mode active.")

        except Exception as e:
            # THE FALLBACK: If trading_v4.db is corrupted, wipe state and survive.
            logger.critical(f"🚨 CRITICAL: Database failure during boot: {str(e)}")
            logger.warning("🛡️ FALLBACK TRIGGERED: Waking up with Amnesia (clean state) to prevent system crash.")
            self.recent_trades = []
            self.current_streak = 0
            self.is_tilted = False

    async def log_trade_result(self, result: str, pnl: float, regime: str, confidence: float = 0.0, signal_type: str = "", agents: dict = None):
        """Records a completed trade into RAM and persists to SQLite."""
        trade_data = {
            "time": datetime.now(),
            "result": result,  # "WIN", "LOSS", "BREAKEVEN"
            "pnl": pnl,
            "regime": regime,
            "confidence": confidence,
            "signal_type": signal_type,
            "agents": agents or {}
        }
        
        # 1. Update RAM (Instant)
        self.recent_trades.append(trade_data)
        if len(self.recent_trades) > self.max_memory_size:
            self.recent_trades.pop(0)
            
        self._update_state(result)

        # 2. Persist to Disk (Async, Non-Blocking)
        await self.db.save_trade(trade_data)

    def _update_state(self, last_result: str):
        """Updates internal streaks and tilt status."""
        if last_result == "WIN":
            self.current_streak = self.current_streak + 1 if self.current_streak > 0 else 1
        elif last_result == "LOSS":
            self.current_streak = self.current_streak - 1 if self.current_streak < 0 else -1
        else:
            self.current_streak = 0

        # Protect capital: If we lose 2 in a row, we are "tilted" (market is hostile)
        self.is_tilted = self.current_streak <= -2

    def get_confidence_modifier(self) -> float:
        """
        Dynamically adjusts the required confidence based on recent memory.
        Returns a float to ADD or SUBTRACT from the engine's final confidence score.
        """
        modifier = 0.0
        
        # ── SCENARIO A: The bot is losing (Tilted) ──
        # Market is harder than expected. Be extremely picky.
        if self.is_tilted:
            modifier -= 15.0  # Penalize setups, forcing only A++ trades to pass
            
        # ── SCENARIO B: The bot is on a hot streak ──
        # Market is clean and respecting our edge.
        elif self.current_streak >= 2:
            modifier += 5.0   # Slight boost, but don't get arrogant
            
        return modifier

    def is_trading_allowed(self) -> tuple[bool, str]:
        """Emergency circuit breaker based on recent memory."""
        if self.current_streak <= -3:
            return False, "Memory Block: 3 consecutive losses. Halting for session."
        return True, "Clear"
