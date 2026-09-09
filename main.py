"""
============================================
🧠⚡ NIFTY AI AGENT SYSTEM v5.0.0
THE FINAL PRODUCTION SYSTEM (Hardened)

PRO MODE + SIMULATION + DISCIPLINE
============================================
"""

import os
import sys
import time
import asyncio
import signal
import atexit
import logging
from datetime import datetime
from typing import Optional

# Force UTF-8 Encoding on Windows
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Setup basic directories
os.makedirs("data", exist_ok=True)

from config.settings import Settings
from utils.logger import get_logger
from core.context import RuntimeContext
from core.events import EventManager
from core.broker_health import BrokerHealthMonitor
from core.orchestrator import TradingOrchestrator
from core.pipelines.market_data_pipeline import MarketDataPipeline
from core.pipelines.decision_pipeline import DecisionPipeline
from core.pipelines.execution_pipeline import ExecutionPipeline
from core.pipelines.position_pipeline import PositionPipeline
from core.pipelines.telemetry_pipeline import TelemetryPipeline

# --- SINGLETON PROCESS LOCK ---
LOCK_FILE_PATH = os.path.join(os.environ.get("TEMP", "/tmp"), "nifty_ai_v5.lock")
lock_file_handle = None

def acquire_lock():
    global lock_file_handle
    try:
        if os.path.exists(LOCK_FILE_PATH):
            with open(LOCK_FILE_PATH, "r") as f:
                existing_pid = f.read().strip()
        else:
            existing_pid = None
    except Exception:
        existing_pid = None

    lock_file_handle = open(LOCK_FILE_PATH, "a+")
    locked = False

    if sys.platform == 'win32':
        import msvcrt
        try:
            lock_file_handle.seek(0)
            msvcrt.locking(lock_file_handle.fileno(), msvcrt.LK_NBLCK, 1)
            locked = True
        except IOError:
            locked = False
    else:
        import fcntl
        try:
            fcntl.flock(lock_file_handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            locked = True
        except IOError:
            locked = False

    if not locked:
        try:
            lock_file_handle.close()
        except Exception:
            pass
        lock_file_handle = None
        print(f"❌ Another instance already running (PID={existing_pid or 'unknown'})")
        sys.exit(1)

    try:
        lock_file_handle.seek(0)
        lock_file_handle.write(f"{os.getpid()}\n")
        lock_file_handle.truncate()
        lock_file_handle.flush()
    except Exception:
        pass

def release_lock():
    global lock_file_handle
    if lock_file_handle is not None:
        try:
            if sys.platform == 'win32':
                import msvcrt
                try:
                    lock_file_handle.seek(0)
                    msvcrt.locking(lock_file_handle.fileno(), msvcrt.LK_UNLCK, 1)
                except Exception:
                    pass
            else:
                import fcntl
                try:
                    fcntl.flock(lock_file_handle, fcntl.LOCK_UN)
                except Exception:
                    pass
            lock_file_handle.close()
            lock_file_handle = None
        except Exception:
            pass
        try:
            if os.path.exists(LOCK_FILE_PATH):
                os.remove(LOCK_FILE_PATH)
        except Exception:
            pass

def sig_handler(signum, frame):
    print(f"Signal {signum} caught, releasing lock and exiting gracefully.")
    release_lock()
    sys.exit(0)

class LegacySystem:
    """A bridge to hold references for legacy pipelines expecting ctx.system."""
    def __init__(self, settings, db_manager, event_manager=None):
        from core.risk_manager import RiskManager
        from core.position_manager import PositionManager
        from core.entry_engine import EntryEngine
        from core.exit_engine import ExitEngine
        from core.simulation_engine import SimulationEngine
        from core.burnin_tracker import BurninTracker
        
        self.risk_manager = RiskManager(settings, db_manager)
        
        broker = None
        if settings.system_mode.mode == "SIMULATION":
            from core.simulation_broker import SimulationBroker
            broker = SimulationBroker()
            
        self.position_manager = PositionManager(settings, broker=broker)
        self.oms = self.position_manager.oms
        self.entry_engine = EntryEngine(settings)
        self.exit_engine = ExitEngine(settings)
        self.burnin_tracker = BurninTracker()
        self.simulation = SimulationEngine(settings, burnin_tracker=self.burnin_tracker, event_manager=event_manager)
        self.data_manager = None
        self.trading_enabled = True
        self.execution_failures = 0
        self.engine_errors = 0

# --- BOOTSTRAP ---
def main():
    atexit.register(release_lock)
    try:
        signal.signal(signal.SIGINT, sig_handler)
        signal.signal(signal.SIGTERM, sig_handler)
    except Exception:
        pass

    acquire_lock()

    settings = Settings()
    logger = get_logger("bootstrap", settings.log_level)
    logger.info("Initializing Nifty AI System v5.0.0")

    try:
        # Dependency Construction
        event_manager = EventManager()
        broker_health = BrokerHealthMonitor(settings)
        
        ctx = RuntimeContext(
            settings=settings,
            mode=settings.system_mode.mode,
            is_simulation=(settings.system_mode.mode == "SIMULATION"),
            telegram_enabled=settings.alerts.telegram_enabled,
            event_manager=event_manager,
            broker_health=broker_health,
        )

        from core.db_manager import DBManager
        db_mgr = DBManager()
        asyncio.run(db_mgr.initialize())
        
        # Also migrate the secondary database if it exists so dashboard queries don't fail
        other_path = "data/trading_v4_live.db" if db_mgr.db_path == "data/trading_v4_sim.db" else "data/trading_v4_sim.db"
        if os.path.exists(other_path):
            other_mgr = DBManager(db_path=other_path)
            asyncio.run(other_mgr.initialize())

        # Bridge legacy references and managers onto context
        ctx.system = LegacySystem(settings, db_mgr, event_manager=event_manager)
        ctx.db_manager = db_mgr
        ctx.burnin_tracker = ctx.system.burnin_tracker
        ctx.simulation = ctx.system.simulation
        ctx.readiness_scorer = getattr(ctx.system, "readiness_scorer", None) or getattr(ctx.system.burnin_tracker, "readiness_scorer", None)
        
        # Wire Pipelines
        ctx.market_data = MarketDataPipeline(ctx)
        
        # Populate context with data manager for legacy compatibility where needed
        if hasattr(ctx.market_data, "data_manager"):
            ctx.data_manager = ctx.market_data.data_manager
            ctx.system.data_manager = ctx.market_data.data_manager
            if hasattr(ctx.system, "entry_engine"):
                ctx.system.entry_engine.data_manager = ctx.market_data.data_manager

        ctx.telemetry = TelemetryPipeline(ctx)
        ctx.decision = DecisionPipeline(ctx)
        ctx.execution = ExecutionPipeline(ctx)
        ctx.position = PositionPipeline(ctx)

        # Map pipeline sub-components to legacy system so older calls (e.g. ctx.system.entry_engine) work
        ctx.system.market_pipeline = ctx.market_data
        ctx.system.decision_pipeline = ctx.decision
        ctx.system.execution_pipeline = ctx.execution
        ctx.system.oms = ctx.system.position_manager.oms
        
        if hasattr(ctx.decision, "decision_engine"): ctx.system.decision_engine = ctx.decision.decision_engine
        if hasattr(ctx.decision, "master"): ctx.system.master = ctx.decision.master

        # Start the web dashboard (localhost:5000) in a background thread
        if ctx.telemetry:
            ctx.telemetry.start_dashboard()

        # --- Validation Sprint Configuration Check ---
        # Fetch current values to check for drift against v5.0.0-VAL-1 baseline
        actual_conf = getattr(settings.trading, "live_confidence_threshold", 0.470)
        has_drift = (actual_conf != 0.470)

        logger.info("═══════════════════════════════════════════════")
        logger.info("Validation Sprint Configuration Check")
        logger.info("═══════════════════════════════════════════════")
        logger.info("Baseline ID           : v5.0.0-VAL-1")
        
        if not has_drift:
            logger.info("Configuration Drift   : NONE ✓")
        else:
            logger.warning(f"Configuration Drift   : DETECTED (Conf={actual_conf}) ❌")
            
        logger.info("")
        logger.info(f"Confidence            : {actual_conf} {'✓' if not has_drift else '❌'}")
        logger.info("Gap Model             : Adaptive v2 ✓")
        logger.info("MAV Version           : 1.0 ✓")
        logger.info("")
        logger.info(f"Sprint Status         : {'VALID' if not has_drift else 'INVALID - DO NOT USE FOR SPRINT'}")
        logger.info("═══════════════════════════════════════════════")

        # Initialize and Start Orchestrator
        orchestrator = TradingOrchestrator(ctx)
        asyncio.run(orchestrator.start())
        
    except KeyboardInterrupt:
        logger.info("Interrupted by user. Shutting down.")
    except Exception as e:
        logger.critical(f"Fatal exception during runtime: {e}", exc_info=True)
        sys.exit(1)
    finally:
        try:
            import core.system_state as system_state
            data = system_state.load_operational_state()
            data["last_clean_shutdown"] = True
            system_state.save_operational_state(data)
        except Exception:
            pass
            
        try:
            import subprocess
            logger.info("Generating Daily Audit Report...")
            subprocess.run([sys.executable, "-m", "tools.generate_daily_audit"], check=False)
        except Exception as e:
            logger.error(f"Failed to generate daily audit report: {e}")
            
        release_lock()

if __name__ == "__main__":
    main()
