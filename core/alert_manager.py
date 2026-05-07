"""
============================================
🔔 ALERT MANAGER
Dispatches signals to multiple channels:
- Console (rich formatted)
- Telegram
- Sound
============================================
"""

import os
import time
from datetime import datetime
from typing import Optional

from models.signals import Signal, SignalType
from utils.logger import get_logger
from config.settings import Settings

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


class AlertManager:
    """
    Manages all alert dispatching.
    Includes cooldown to prevent alert flooding.
    """

    def __init__(self, settings: Settings, telegram_bot):
        self.settings = settings
        self.alert_config = settings.alerts
        self.telegram_bot = telegram_bot
        self.logger = get_logger("alert_manager")
        self.console = Console() if RICH_AVAILABLE else None

        self.last_alert_time: Optional[datetime] = None
        self.alert_count = 0
        self.alert_history: list = []

    async def dispatch(self, signal: Signal):
        """
        Main dispatch method.
        Routes signal to all enabled channels.
        """
        # Skip NO_TRADE signals (optional: can be changed)
        if signal.signal_type == SignalType.NO_TRADE:
            self._log_no_trade(signal)
            return

        # Check cooldown
        if not self._cooldown_passed():
            self.logger.debug("Alert cooldown active — skipping")
            return

        # 1. Console & Sound
        if self.alert_config.console_enabled:
            self._console_alert(signal)

        if self.alert_config.sound_enabled:
            self._sound_alert(signal)

        # 2. Telegram (Now Async & Integrated)
        if self.alert_config.telegram_enabled and self.telegram_bot:
            try:
                await self.telegram_bot.process_signal(signal)
            except Exception as e:
                self.logger.error(f"Telegram failure: {e}")

        # Record
        self.last_alert_time = datetime.now()
        self.alert_count += 1
        self.alert_history.append({
            "time": datetime.now(),
            "signal": signal.signal_type.value,
            "confidence": signal.confidence,
        })

    def _cooldown_passed(self) -> bool:
        """Check if enough time has passed since last alert"""
        if self.last_alert_time is None:
            return True

        elapsed = (datetime.now() - self.last_alert_time).total_seconds()
        return elapsed >= self.alert_config.cooldown_seconds

    def _console_alert(self, signal: Signal):
        """Rich formatted console alert"""
        if not RICH_AVAILABLE or not self.console:
            print(str(signal))
            return

        # Color based on signal
        if signal.signal_type == SignalType.BUY_CE:
            color = "green"
            icon = "🟢"
            title = "BUY CE SIGNAL"
        elif signal.signal_type == SignalType.BUY_PE:
            color = "red"
            icon = "🔴"
            title = "BUY PE SIGNAL"
        else:
            color = "white"
            icon = "⚪"
            title = "SIGNAL"

        # Build table
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Field", style="bold")
        table.add_column("Value")

        table.add_row("Signal", f"[bold {color}]{signal.signal_type.value}[/]")
        table.add_row("Direction", signal.direction.value)
        table.add_row("Confidence", f"[bold]{signal.confidence:.1f}%[/]")
        table.add_row("Strength", signal.strength.value)
        table.add_row("", "")
        table.add_row("Entry", f"₹{signal.entry_price:,.1f}")
        table.add_row("Stop Loss", f"₹{signal.stop_loss:,.1f}")
        table.add_row("Target 1", f"₹{signal.target_1:,.1f}")
        table.add_row("Target 2", f"₹{signal.target_2:,.1f}")
        table.add_row("Qty", str(signal.position_size))
        table.add_row("", "")

        for reason in signal.reasons:
            table.add_row("✓", reason)

        if signal.warnings:
            table.add_row("", "")
            for warning in signal.warnings[:3]:
                table.add_row("⚠️", f"[yellow]{warning}[/]")

        panel = Panel(
            table,
            title=f"{icon} {title}",
            border_style=color,
            padding=(1, 2),
        )

        self.console.print()
        self.console.print(panel)
        self.console.print()



    def _sound_alert(self, signal: Signal):
        """Play sound alert (system beep)"""
        try:
            if signal.signal_type in (SignalType.BUY_CE, SignalType.BUY_PE):
                # Cross-platform beep
                print("\a", end="", flush=True)
        except Exception:
            pass

    def _log_no_trade(self, signal: Signal):
        """Log NO_TRADE signal quietly"""
        reasons = ", ".join(signal.reasons[:2]) if signal.reasons else "No conditions met"
        self.logger.debug(f"NO TRADE: {reasons}")
