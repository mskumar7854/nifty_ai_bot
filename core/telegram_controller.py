"""
============================================
📱 TELEGRAM COMMAND LAYER (v4.6 Persistent)
Interactive control for the Nifty AI Agent.
Supports Auto/Semi-Auto modes, signal 
queueing, and SQLite-backed state recovery.
============================================
"""

import asyncio
import os
import uuid
import logging
import time
from typing import Optional, Dict
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

from models.signals import Signal, SignalType, Direction
from config.settings import Settings
from core.session_guard import orchestrator
from core.signal_formatter import format_signal_message, format_trade_close_message

logger = logging.getLogger("telegram_controller")

class TelegramController:
    def __init__(self, settings: Settings, system, db_manager):
        self.settings = settings
        self.system = system  # v4.6.1 Parent system for unified execution
        self.db = db_manager 
        
        # Shortcuts for internal use
        self.risk_manager = system.risk_manager
        self.position_manager = system.position_manager
        self.entry_engine = system.entry_engine
        self.data_manager = system.data_manager
        
        self.token = settings.alerts.telegram_bot_token
        self.admin_chat_id = str(settings.alerts.telegram_chat_id)
        self.chat_id = self.admin_chat_id
        self.app = None
        
        # Controlled State
        self.active_signal: Optional[Signal] = None
        self._signal_lock = asyncio.Lock()  # 🛡️ Risk #4 Fix: guards active_signal from async race conditions
        self.signal_queue = asyncio.Queue()
        self.expiry_task: Optional[asyncio.Task] = None
        self.queue_counter = 0 # To track position in current session
        
        # System State
        self.is_paused = False
        self.trading_mode = settings.alerts.trading_mode # AUTO | SEMI_AUTO | MANUAL

    def _is_authorized(self, update: Update) -> bool:
        """SECURITY: Only the configured admin ID can interact with the bot."""
        chat_id = str(update.effective_chat.id)
        return chat_id == self.admin_chat_id

    # ─── BOOT RECOVERY (v4.6.1 Hardened) ───

    async def boot_recovery(self):
        """Loads non-final signals from DB and prunes stale ones."""
        logger.info("🔍 Running Telegram Bot state recovery (v4.6.1)...")
        unprocessed = await self.db.load_unprocessed_signals()
        
        if not unprocessed:
            logger.info("✅ No pending signals to recover.")
            return

        import time
        from datetime import datetime
        from models.signals import Strength, SignalGrade
        
        now = time.time()
        recovered_count = 0
        pruned_count = 0
        executing_count = 0
        
        for row in unprocessed:
            # row: (id, symbol, signal_type, direction, entry, sl, target1, confidence, 
            #       status, execution_status, created_at, queue_pos, metadata)
            sid, symbol, stype, direct, entry, sl, t1, conf, status, exec_status, created_at, qpos, meta = row
            
            # 🛡️ 1. ZOMBIE PRUNING: Is it stale? (> 30s for pending/queued)
            age = now - created_at
            if age > self.settings.alerts.telegram_signal_expiry_seconds:
                await self.db.update_signal_status(sid, "expired_on_restart")
                pruned_count += 1
                continue

            # 🛡️ 2. CRASH DETECTION: Was it mid-execution?
            if exec_status == "executing":
                executing_count += 1
                logger.critical(f"⚠️ CRASH DETECTED: Signal {sid} was mid-execution. Manual check required!")
                await self._alert_manual_check(sid, symbol, direct)
                continue
            
            # 3. Reconstruct Signal object
            sig = Signal(
                id=sid,
                timestamp=datetime.fromtimestamp(created_at),
                signal_type=SignalType(stype),
                direction=Direction(direct),
                confidence=conf,
                strength=Strength.MODERATE,
                entry_price=entry,
                stop_loss=sl,
                target_1=t1,
                status=status,
                execution_status=exec_status or "pending",
                created_at=created_at,
                queue_position=qpos
            )
            sig.symbol = symbol
            
            # Inject back into queue
            await self.signal_queue.put(sig)
            recovered_count += 1

        if pruned_count > 0:
            logger.warning(f"🛡️ Pruned {pruned_count} zombie signals from recovery queue.")
            await self._send_admin_msg(f"🛡️ <b>Recovery:</b> {pruned_count} zombie signals were pruned for your safety.")

        if recovered_count > 0:
            logger.info(f"🔄 Recovered {recovered_count} signals. Processing next...")
            await self._process_next_signal()

    # ─── SIGNAL LIFECYCLE ───

    async def process_signal(self, signal: Signal):
        """Entry point for new signals from the strategy engine."""
        signal.status = "queued"
        signal.created_at = time.time()
        
        # 1. Assign Queue Position (Persistent)
        self.queue_counter += 1
        signal.queue_position = self.queue_counter
        
        # 💾 2. Persist to DB immediately
        await self.db.save_signal(signal)

        if self.active_signal is not None:
            logger.info(f"Signal {signal.id} queued (Position: {signal.queue_position}).")
            await self.signal_queue.put(signal)
            return

        await self._activate_signal(signal)

    async def _activate_signal(self, signal: Signal):
        """Makes a signal active and prompts the user (lock-protected entry point)."""
        async with self._signal_lock:  # 🛡️ Risk #4: serialise activation vs callback
            await self._activate_signal_inner(signal)

    async def _activate_signal_inner(self, signal: Signal):
        """Inner activation logic — must only be called while _signal_lock is held."""
        
        # 🛡️ 1. HARD EXPIRY CHECK: Did it expire while waiting in line?
        waited = time.time() - signal.created_at
        if waited > self.settings.alerts.telegram_signal_expiry_seconds:
            logger.warning(f"Queue starvation: Signal {signal.id} expired before activation ({waited:.1f}s).")
            # Atomic update to expired
            await self.db.update_signal_status(signal.id, "expired_in_queue", expected_current_status="queued")
            return await self._process_next_signal()

        # 🛡️ 2. MASTER GATE CHECK (Global Kill Switch + Weekend Buffer + All rules)
        # Using system.master ensures manual trades respect the same rules as AI.
        approval = self.system.master.approve(signal.signal_type.value)
        if not approval.approved:
            logger.warning(f"Master Reject: {approval.reason}")
            await self.db.update_signal_status(signal.id, "risk_rejected", expected_current_status="queued")
            await self._send_admin_msg(f"🛡️ <b>Trade Rejected:</b> {approval.reason}")
            return await self._process_next_signal()

        # 3. SET AS ACTIVE (Atomic)
        success = await self.db.update_signal_status(signal.id, "pending", expected_current_status="queued")
        if not success:
            logger.error(f"Race condition detected on activation for {signal.id}")
            return await self._process_next_signal()
            
        self.active_signal = signal
        self.active_signal.status = "pending"
        
        # 4. Mode-based routing
        if self.trading_mode == "SEMI_AUTO":
            await self._send_interactive_signal(signal)
            self.expiry_task = asyncio.create_task(self._expire_signal(signal.id))
        elif self.trading_mode == "AUTO":
            # ℹ️ v4.6.1: In AUTO mode, the primary AI loop handles execute_signal.
            # Telegram simply provides a status update.
            await self._notify_auto_signal(signal)
            await self.db.update_signal_status(signal.id, "confirmed", execution_status="executed")
        else: # MANUAL
            await self._notify_manual_alert(signal)
            await self.db.update_signal_status(signal.id, "alert_only", expected_current_status="pending")
            self.active_signal = None
            await self._process_next_signal()

    async def _execute_auto(self, signal: Signal):
        """Execution logic for AUTO mode."""
        await self._notify_auto_signal(signal)
        # Execution Lock
        await self.db.update_signal_status(signal.id, "confirmed", execution_status="executing", expected_current_status="pending")
        try:
            # Send to unified execution path
            await self.system.execute_signal(signal, mode="new")
            await self.db.update_signal_status(signal.id, "confirmed", execution_status="executed")
        except Exception as e:
            await self.db.update_signal_status(signal.id, "confirmed", execution_status="failed")
            logger.error(f"Auto execution failed: {e}")
            
        self.active_signal = None
        await self._process_next_signal()

    # ─── CALLBACK HANDLER (Hardened) ───

    async def handle_callback_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Processes user clicks (CONFIRM/SKIP)."""
        query = update.callback_query
        if not self._is_authorized(update): return
            
        await query.answer()
        
        # Kill expiry timer
        if self.expiry_task and not self.expiry_task.done():
            self.expiry_task.cancel()
            self.expiry_task = None

        action, signal_id = query.data.split(":")

        async with self._signal_lock:  # 🛡️ Risk #4: serialise callback vs activation
            signal = self.active_signal

            # 🛡️ ATOMIC VALIDATION: Is this signal still pending?
            if not signal or signal.id != signal_id:
                await query.edit_message_text("❌ Signal out-of-sync or already processed.")
                return

            if action == "confirm":
                # 1. OPTIMISTIC LOCK: Try to mark as 'confirmed' immediately
                success = await self.db.update_signal_status(
                    signal.id, 
                    status="confirmed", 
                    execution_status="executing", 
                    expected_current_status="pending"
                )
                
                if not success:
                    await query.edit_message_text("❌ Race condition! Signal already expired or skipped.")
                    self.active_signal = None
                    await self._process_next_signal()
                    return

                # 2. Slice/Slippage Check
                ltp = self._get_ltp()
                if not ltp:
                    await query.edit_message_text("❌ Price data unavailable. Execution failed.")
                    await self.db.update_signal_status(signal.id, "confirmed", execution_status="failed")
                    self.active_signal = None
                    await self._process_next_signal()
                    return

                slippage = abs(ltp - signal.entry_price) / signal.entry_price * 100
                if slippage > self.settings.alerts.max_slippage_pct_on_confirm:
                    await query.edit_message_text(f"❌ <b>Rejected: Slippage too high.</b>\nTarget: {signal.entry_price} | Live: {ltp:.1f}", parse_mode='HTML')
                    await self.db.update_signal_status(signal.id, "failed_slippage", execution_status="failed")
                else:
                    # 3. Execution via unified system path
                    try:
                        await self.system.execute_signal(signal, mode="new")
                        await query.edit_message_text(f"✅ <b>Trade Executed @ ₹{ltp:,.1f}.</b>", parse_mode='HTML')
                        await self.db.update_signal_status(signal.id, "confirmed", execution_status="executed")
                    except Exception as e:
                        logger.error(f"Execution failed: {e}")
                        await self.db.update_signal_status(signal.id, "confirmed", execution_status="failed")
                        await query.edit_message_text(f"❌ <b>Execution Error:</b> {str(e)}", parse_mode='HTML')

            elif action == "skip":
                await self.db.update_signal_status(signal.id, "skipped", expected_current_status="pending")
                await query.edit_message_text("❌ <b>Trade Skipped by User.</b>", parse_mode='HTML')

    async def status_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comprehensive system status report."""
        if not self._is_authorized(update): return
        
        # 1. Performance from PositionManager
        stats = self.position_manager.today_stats
        pnl_emoji = "🟢" if stats.total_pnl >= 0 else "🔴"
        
        # 2. Risk from RiskManager
        risk = self.risk_manager.get_status_report()
        risk_emoji = "🟢 ACTIVE" if risk['trading_enabled'] else "🛑 BREACHED"
        
        # 3. Broker Margin
        margin = self.data_manager.get_fund_limits()

        # 4. Broker Health
        broker_h = getattr(self.system, "broker_health", None)
        if broker_h:
            bh = broker_h.get_status()
            bh_emoji = "🟢 HEALTHY" if bh["healthy"] else "🔴 DEGRADED"
            bh_str = (
                f"\n🩺 <b>BROKER HEALTH:</b>\n"
                f"  • Status:     {bh_emoji}\n"
                f"  • API Lag:    {bh['api_latency_ms']:.0f}ms\n"
                f"  • Last Order: {bh['last_order']}\n"
                f"  • Feed Delay: {bh['feed_delay_s']:.0f}s\n"
            )
            if not bh["healthy"]:
                bh_str += f"  • ⚠️ Reason: {bh['degraded_reason']}\n"
        else:
            bh_str = ""

        # 5. Central System State
        from core.system_state import get_state_manager
        state_mgr = get_state_manager()
        current_state = state_mgr.get_state()
        state_emoji = "🟢" if current_state == "ACTIVE" else "🟡" if current_state.startswith("PAUSED") else "🛑"

        msg = (
            f"📊 <b>SYSTEM STATUS v4.7</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🤖 <b>Bot Mode:</b> {self.trading_mode}\n"
            f"{state_emoji} <b>State:</b> <code>{current_state}</code> ({state_mgr.reason})\n"
            f"🛡️ <b>Risk Guard:</b> {risk_emoji}\n"
            f"⏸️ <b>Process:</b> {'PAUSED' if self.is_paused else 'RUNNING'}\n"
            f"{bh_str}\n"
            f"💰 <b>CAPITAL &amp; MARGIN:</b>\n"
            f"  • Margin Available: ₹{margin:,.0f}\n"
            f"  • {pnl_emoji} Today's PnL: ₹{risk['daily_pnl']:,.0f}\n"
            f"  • Limit Remaining: ₹{abs(risk['max_daily_loss']) - abs(risk['daily_pnl']):,.0f}\n\n"
            
            f"🎯 <b>TRADING PERFORMANCE:</b>\n"
            f"  • Trades Taken: {stats.trades_taken}\n"
            f"  • W/L: {stats.wins} / {stats.losses}\n"
            f"  • Win Rate: {stats.win_rate:.1f}%\n\n"
            
            f"📡 <b>PIPELINE:</b>\n"
            f"  • Active: {self.active_signal.id[:8] if self.active_signal else 'None'}\n"
            f"  • Queue: {self.signal_queue.qsize()} signals waiting\n"
            f"━━━━━━━━━━━━━━━━━━"
        )
        await update.message.reply_text(msg, parse_mode='HTML')

    async def force_reconcile_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Force runs the broker reconciliation and attempts to clear halts if clean."""
        if not self._is_authorized(update): return
        
        await update.message.reply_text("🔄 <b>Initiating broker position reconciliation...</b>", parse_mode='HTML')
        
        try:
            # Run reconciliation check (which we've updated to return boolean status)
            is_clean = await self.system._reconcile_broker_positions()
            
            if is_clean:
                from core.system_state import get_state_manager
                state_mgr = get_state_manager()
                
                # Clear halt states
                state_mgr.force_activate("Operator force reconcile cleared all halts")
                self.system.trading_enabled = True
                orchestrator.resume()
                
                # Clear position manager halt state if it exists
                pos_mgr = getattr(self.system, "position_manager", None)
                if pos_mgr:
                    pos_mgr.is_halted = False
                    pos_mgr.halt_reason = ""
                
                msg = (
                    "✅ <b>RECONCILIATION SUCCESSFUL</b>\n\n"
                    "No orphaned positions or missing stop losses found.\n"
                    "<b>System has been re-enabled and is now ACTIVE.</b>"
                )
                await update.message.reply_text(msg, parse_mode='HTML')
            else:
                msg = (
                    "❌ <b>RECONCILIATION FAILED</b>\n\n"
                    "Orphaned positions, missing stop losses, or broker API errors are still present.\n"
                    "Please check the system logs, resolve any issues on the broker manually, and retry."
                )
                await update.message.reply_text(msg, parse_mode='HTML')
        except Exception as e:
            logger.error(f"Error in force_reconcile_cmd: {e}", exc_info=True)
            await update.message.reply_text(f"❌ <b>Error running force reconcile:</b> {e}", parse_mode='HTML')


    async def kill_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Emergency Nuclear Button: Square Off + Clean Exit."""
        if not self._is_authorized(update): return
        
        logger.critical("🚨 NUCLEAR EMERGENCY SHUTDOWN INITIATED 🚨")
        await update.message.reply_text("☢️ <b>NUCLEAR SHUTDOWN INITIATED</b>\nSquaring off ALL positions and cancelling all pending signals...", parse_mode='HTML')
        
        # 1. Cancel logic in Database
        await self.db.execute("UPDATE signals SET status = 'cancelled_by_kill' WHERE status IN ('queued', 'pending')")
        
        # 2. Cancel all pending in EntryEngine
        self.entry_engine.cancel_all_pending()
        
        # 3. Force Close ALL positions (Institutional Market Square Off)
        self.position_manager.close_all_positions(reason="🚨 Emergency Telegram Kill Switch")
        
        # Wait briefly for close confirmations
        await asyncio.sleep(1.5)

        # Optional: Verify broker reports all closed
        try:
            if getattr(self.system, 'is_simulation', False) is False:
                from dhan_client import get_dhan_client
                dhan = get_dhan_client()
                positions = dhan.get_positions()
                if positions and positions.get("status") == "success":
                    open_count = sum(1 for p in positions.get("data", []) 
                                    if p.get("netQty", 0) != 0 and p.get("positionType") == "INTRADAY")
                    if open_count > 0:
                        logger.critical(f"⚠️ {open_count} positions still open after kill!")
                        await update.message.reply_text(
                            f"⚠️ <b>WARNING:</b> {open_count} positions may still be open!\n"
                            f"Check Dhan manually NOW.",
                            parse_mode='HTML'
                        )
        except Exception as e:
            logger.error(f"Post-kill verification failed: {e}")

        # 4. Graceful state save before exit (after confirmed closes)
        try:
            self.position_manager.save_state()
            logger.info("✅ Position state saved")
        except Exception as e:
            logger.error(f"Position state save failed: {e}")

        try:
            if hasattr(self.system, 'simulation') and self.system.simulation:
                self.system.simulation._save_state()
                logger.info("✅ Simulation state saved")
        except Exception as e:
            logger.error(f"Simulation state save failed: {e}")

        try:
            if hasattr(self.system, 'trade_logger') and self.system.trade_logger:
                self.system.trade_logger.save_all()
                logger.info("✅ Trade logs saved")
        except Exception as e:
            logger.error(f"Trade log save failed: {e}")

        logger.critical("🚨 KILL SWITCH: Clean shutdown complete — exiting process")
        await update.message.reply_text("✅ <b>All state saved. Shutting down.</b>", parse_mode='HTML')
        
        # 5. Halt the system gracefully
        self.system.running = False
        self.system.trading_enabled = False
        orchestrator.halt()
        
        # Give async tasks 2s to clean up, then hard exit
        await asyncio.sleep(2)
        import os
        os._exit(0)

    async def restart_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Clean process restart."""
        if not self._is_authorized(update): return
        await update.message.reply_text("🔄 <b>Restarting Bot...</b>", parse_mode='HTML')
        import sys
        os.execv(sys.executable, ['python'] + sys.argv)

    async def start_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Welcome message and system reactivation."""
        if not self._is_authorized(update): return
        
        # If system was halted, we re-enable it here
        if not self.system.trading_enabled:
            self.system.trading_enabled = True
            orchestrator.resume()
            logger.info("🟢 System RE-ENABLED via Telegram /start")

        msg = (
            "👋 <b>Welcome to Nifty AI Control Center</b>\n\n"
            "• Use /status to see current performance.\n"
            "• Use /stop to HALT system (Emergency).\n"
            "• Use /pause or /resume to control AI flow."
        )
        await update.message.reply_text(msg, parse_mode='HTML')

    async def stop_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Emergency Stop Control (Remote Kill Switch)."""
        if not self._is_authorized(update): return
        self.system.trading_enabled = False
        orchestrator.halt()
        logger.critical("🛑 SYSTEM HALTED via Telegram /stop")
        await update.message.reply_text("🛑 <b>EMERGENCY STOP:</b> Trading has been HALTED. AI Agent is now in monitor-only mode. Use /start to re-enable.", parse_mode='HTML')

    async def pause_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Pauses signal generation."""
        if not self._is_authorized(update): return
        
        from core.system_state import get_state_manager
        state_mgr = get_state_manager()
        state_mgr.set_state("PAUSED_MANUAL", "Paused by operator command via Telegram")
        
        self.is_paused = True
        await update.message.reply_text("⏸️ <b>System PAUSED.</b> No new trades will be generated.", parse_mode='HTML')

    async def resume_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Resumes signal generation."""
        if not self._is_authorized(update): return
        
        from core.system_state import get_state_manager
        state_mgr = get_state_manager()
        current_state = state_mgr.get_state()
        
        if current_state in ["HALTED", "PAUSED_STRUCTURAL"]:
            await update.message.reply_text(
                f"❌ <b>RESUME BLOCKED:</b> System is in <code>{current_state}</code> state.\n"
                f"This requires manual code investigation and server restart.",
                parse_mode='HTML'
            )
            return
            
        state_mgr.set_state("ACTIVE", "Resumed by operator command via Telegram")
        self.is_paused = False
        
        if hasattr(self, "system") and self.system:
            self.system.trading_enabled = True
            orchestrator.resume()
            pos_mgr = getattr(self.system, "position_manager", None)
            if pos_mgr:
                pos_mgr.is_halted = False
                pos_mgr.halt_reason = ""
                
        await update.message.reply_text("▶️ <b>System RESUMED.</b> AI Agent is back online.", parse_mode='HTML')

    # ─── HELPERS ───
    async def _send_admin_msg(self, text: str):
        app = self._get_app()
        if app:
            try:
                await app.bot.send_message(chat_id=self.admin_chat_id, text=text, parse_mode='HTML')
            except Exception as e:
                logger.error(f"Failed to send admin message to {self.admin_chat_id}: {e}")

    async def notify_halt(self, reason: str):
        """Notifies admin of a system halt."""
        msg = (
            f"🛑 <b>SYSTEM HALT DETECTED</b>\n\n"
            f"Reason: <code>{reason}</code>\n"
            f"Trading is now DISABLED. Check logs and use /start to re-enable."
        )
        await self._send_admin_msg(msg)

    async def _alert_manual_check(self, sid, symbol, direct):
        msg = (
            f"🚨 <b>MANUAL VERIFICATION REQUIRED</b>\n\n"
            f"Bot crashed during execution of {symbol} {direct} (ID: {sid}).\n"
            f"<b>Check your broker immediately for open positions!</b>"
        )
        await self._send_admin_msg(msg)

    async def _send_interactive_signal(self, signal) -> None:
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ CONFIRM", callback_data=f"confirm:{signal.id}"),
                InlineKeyboardButton("❌ REJECT", callback_data=f"reject:{signal.id}"),
            ]
        ])

        # ── Build snapshot summary for formatter ──
        snap_summary = signal.metadata.get("snapshot_summary", {})

        # Inject signal expiry seconds so formatter can display validity
        signal.metadata["signal_expiry_seconds"] = self.settings.alerts.telegram_signal_expiry_seconds

        # Build the unified two-section signal message
        body = format_signal_message(signal, snapshot_summary=snap_summary)

        # Add SEMI_AUTO header + expiry footer
        text = (
            f"⚡ <b>TRADE CONFIRMATION REQUIRED</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"{body}\n\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"⏳ Expires in {self.settings.alerts.telegram_signal_expiry_seconds}s"
        )

        try:
            app = self._get_app()
            msg = await app.bot.send_message(
                chat_id=self.chat_id,
                text=text,
                parse_mode="HTML",
                reply_markup=keyboard,
            )
            logger.info("Interactive signal posted: signal=%s msg=%s", signal.id, msg.message_id)
        except Exception:
            logger.exception("Failed to post interactive signal %s; expiring.", signal.id)
            await self._expire_signal(signal.id)

    async def _expire_signal(self, signal_id: str) -> None:
        try:
            await self.db.update_signal_status(signal_id, "expired")
            logger.info("Signal expired: %s", signal_id)
        except Exception:
            logger.exception("Error expiring signal %s", signal_id)

    async def _notify_auto_signal(self, signal) -> None:
        # ── Build snapshot summary for formatter ──
        snap_summary = signal.metadata.get("snapshot_summary", {})
        signal.metadata["signal_expiry_seconds"] = self.settings.alerts.telegram_signal_expiry_seconds

        body = format_signal_message(signal, snapshot_summary=snap_summary)

        text = (
            f"🤖 <b>AUTO TRADE EXECUTED</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"{body}"
        )

        await self._send_admin_msg(text)
        logger.info("AUTO signal notified: %s", signal.id)

    async def _notify_manual_alert(self, signal) -> None:
        # ── Build snapshot summary for formatter ──
        snap_summary = signal.metadata.get("snapshot_summary", {})
        signal.metadata["signal_expiry_seconds"] = self.settings.alerts.telegram_signal_expiry_seconds

        body = format_signal_message(signal, snapshot_summary=snap_summary)

        text = (
            f"📋 <b>MANUAL SIGNAL ALERT</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"{body}\n\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"ℹ️ No automatic execution — manual mode active."
        )

        try:
            await self._send_admin_msg(text)
            await self.db.update_signal_status(signal.id, "notified")
            logger.info("Manual alert sent: %s", signal.id)
        except Exception:
            logger.exception("Failed to send manual alert for signal %s", signal.id)

    async def _process_next_signal(self) -> None:
        try:
            # Reconstruct logic to pull from queue
            if not self.signal_queue.empty():
                next_signal = await self.signal_queue.get()
                logger.info("Promoting queued signal to active: %s", next_signal.id)
                await self._activate_signal(next_signal)
            else:
                logger.debug("_process_next_signal: queue empty, nothing to do.")
        except Exception:
            logger.exception("Error in _process_next_signal")

    def _get_ltp(self) -> float | None:
        try:
            _, snapshot = self.data_manager.get_latest_data()
            return float(snapshot.price) if snapshot else None
        except Exception:
            logger.exception("_get_ltp failed")
            return None

    def _get_app(self):
        if getattr(self, "app", None) is None:
            raise RuntimeError(
                "_get_app() called before TelegramController.app was set. "
                "Ensure `telegram_bot.app = app` runs at startup."
            )
        return self.app

    async def notify_trade_close(self, trade_id: str, pnl: float, outcome: str) -> None:
        try:
            text = format_trade_close_message(trade_id, pnl, outcome)
            await self._send_admin_msg(text)
            logger.info("notify_trade_close sent: trade=%s pnl=%.0f outcome=%s", trade_id, pnl, outcome.upper())
        except Exception:
            logger.exception("notify_trade_close failed silently: trade=%s pnl=%.0f", trade_id, pnl)
