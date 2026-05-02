"""
============================================
NIFTY INTRADAY STRATEGY — MAIN ENTRY POINT
============================================
Runs the complete TradingBot loop.

Usage:
    cd nifty_strategy
    python main.py

Credentials come from ../.env (DHAN_CLIENT_ID,
DHAN_ACCESS_TOKEN) — never hardcoded here.
============================================
"""

import sys
import os
import time
import signal as _sig
import logging
from datetime import datetime, timedelta
from typing import Optional

# ── Make project root importable so dhan_client.py is found ─
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# ══════════════════════════════════════════════════════════════
# 🛑 DUAL-SYSTEM SAFETY GUARD
# ══════════════════════════════════════════════════════════════
# Graphify analysis (2026-04-09) revealed that running BOTH
# nifty_strategy/ AND main.py v4.6.1 simultaneously causes:
#   • Duplicate real-money orders
#   • Doubled risk with no coordination
#   • Conflicting position tracking
#
# Set ACTIVE_TRADING_SYSTEM=main in your .env when running
# the full v4.6.1 system to block this standalone bot from
# placing live orders.
# ══════════════════════════════════════════════════════════════
_ACTIVE_SYSTEM = os.getenv("ACTIVE_TRADING_SYSTEM", "").strip().lower()
_DHAN_TOKEN    = os.getenv("DHAN_ACCESS_TOKEN", "").strip()

if _ACTIVE_SYSTEM == "main" and _DHAN_TOKEN:
    print("=" * 60)
    print("  🛑 BLOCKED: nifty_strategy bot cannot start.")
    print("  ACTIVE_TRADING_SYSTEM=main is set in your .env.")
    print("  The v4.6.1 system (main.py) is the active trading")
    print("  system. Running both would create DUAL EXECUTION.")
    print()
    print("  ✅ To use nifty_strategy instead:")
    print("     Set ACTIVE_TRADING_SYSTEM=nifty_strategy in .env")
    print("     Stop main.py first.")
    print("=" * 60)
    sys.exit(1)

from .config import Config
from strategy import Strategy
from risk_manager import RiskManager
from utils.trade_logger import TradeLogger
from trade_executor import TradeExecutor, DhanConnector
from data_provider import DhanDataProvider

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("main")


# ══════════════════════════════════════════
# TRADING BOT
# ══════════════════════════════════════════

class TradingBot:
    """
    Orchestrates the full intraday strategy loop:

    Every 60 s:
      1. Fetch candles
      2. Run Trend → Momentum → Breakout analysis
      3. Execute signal (if any passes all gates)
      4. Manage open positions (SL / trail / partial exit)

    Credentials are loaded from ../.env by Config.
    """

    def __init__(self):
        # ── Components ──────────────────────────────────
        self.dhan          = DhanConnector()
        self.data_provider = DhanDataProvider()     # synthetic data by default
        self.strategy      = Strategy()
        self.risk          = RiskManager()
        self.trade_logger  = TradeLogger()
        self.executor      = TradeExecutor(self.dhan, self.risk)
        self.executor.set_logger(self.trade_logger)

        self.running       = False
        self._last_update: Optional[datetime] = None

        # Candle cache
        self._candles: dict = {
            'trend':    None,   # 5-min EMA trend
            'momentum': None,   # 1-min RSI
            'entry':    None,   # 5-min breakout
        }

    # ── Lifecycle ──────────────────────────────────────────
    def start(self):
        """Connect and begin loop."""
        logger.info("=" * 55)
        logger.info("  🚀 NIFTY INTRADAY STRATEGY BOT starting …")
        logger.info("=" * 55)

        if not self.dhan.connect():
            logger.error("Could not connect to Dhan. Running in OFFLINE mode (synthetic data).")
            # Not a fatal error — synthetic data allows offline testing

        self.running = True

        # Graceful shutdown on Ctrl-C / SIGTERM
        _sig.signal(_sig.SIGINT,  self._shutdown_handler)
        _sig.signal(_sig.SIGTERM, self._shutdown_handler)

        self._loop()

    def stop(self):
        """Gracefully shut down — close all open positions."""
        logger.info("Shutting down — closing open positions …")
        self.running = False

        for trade in list(self.risk.active_trades):
            if trade.status == "OPEN":
                quote = self.dhan.get_quote(trade.symbol)
                price = quote.get('last_price') or trade.current_price
                self.executor._close_trade(trade, price, "Bot shutdown")

        summary = self.risk.get_daily_summary()
        logger.info(
            f"\n{'─'*50}\n"
            f"  📋 SESSION SUMMARY\n"
            f"  Trades   : {summary['total_trades']}\n"
            f"  Win Rate : {summary['win_rate']:.1f}%\n"
            f"  Total P&L: ₹{summary['total_pnl']:+,.2f}\n"
            f"  Max DD   : ₹{summary['max_drawdown']:,.2f}\n"
            f"{'─'*50}"
        )

    def _shutdown_handler(self, sig, frame):
        self.stop()
        sys.exit(0)

    # ── Main loop ──────────────────────────────────────────
    def _loop(self):
        logger.info("🔄 Trading loop started. Checking every 60 s …")

        while self.running:
            try:
                # ── Daily stop checks ──────────────────────
                should_stop, reason = self.risk.should_stop_trading()
                if should_stop:
                    logger.info(f"⛔ {reason} — stopping for today.")
                    self.stop()
                    break

                # ── Strategy cycle ─────────────────────────
                self._run_strategy_cycle()

                # ── Position management ────────────────────
                self._manage_positions()

                time.sleep(60)

            except KeyboardInterrupt:
                self.stop()
                break
            except Exception as e:
                logger.exception(f"Loop error: {e}")
                self.trade_logger.log_error(str(e))
                time.sleep(30)

    # ── Strategy cycle ─────────────────────────────────────
    def _run_strategy_cycle(self):
        now = datetime.now()

        # Throttle: refresh data at most once per minute
        if self._last_update and (now - self._last_update).seconds < 55:
            return

        self._refresh_candles(now)
        self._last_update = now

        if any(v is None for v in self._candles.values()):
            logger.info("⏳ Waiting for candle data …")
            return

        analysis = self.strategy.analyze(
            trend_df    = self._candles['trend'],
            momentum_df = self._candles['momentum'],
            entry_df    = self._candles['entry'],
            volume_df   = self._candles['trend'],    # reuse trend df for volume
            dt          = now,
        )

        self.trade_logger.log_signal(analysis)
        logger.info(self.strategy.get_signal_summary(analysis))

        if analysis['can_trade'] and analysis['signal'] in Config.ALLOWED_SIGNALS:
            self._execute_trade(analysis)

    def _refresh_candles(self, now: datetime):
        """Pull latest OHLCV from provider."""
        from_time = now - timedelta(hours=4)

        try:
            self._candles['trend'] = self.data_provider.get_candles(
                Config.UNDERLYING, Config.TREND_TIMEFRAME, from_time, now
            )
            self._candles['momentum'] = self.data_provider.get_candles(
                Config.UNDERLYING, Config.MOMENTUM_TIMEFRAME, from_time, now
            )
            self._candles['entry'] = self._candles['trend'].copy()
        except Exception as e:
            logger.error(f"Candle refresh error: {e}")

    def _execute_trade(self, analysis: dict):
        spot = float(self._candles['trend']['close'].iloc[-1])
        atr  = (
            float(self._candles['trend']['atr'].iloc[-1])
            if 'atr' in self._candles['trend'].columns else None
        )

        logger.info(f"🎯 Signal confirmed — executing {analysis['signal']} @ spot ₹{spot:.1f}")

        trade = self.executor.execute_signal(
            signal=analysis['signal'],
            analysis=analysis,
            spot_price=spot,
            atr=atr,
        )

        if trade:
            logger.info(f"✅ Trade open: {trade.symbol} entry ₹{trade.entry_price:.2f}")
        else:
            logger.warning("❌ Execution failed — see log for details")

    def _manage_positions(self):
        """Check SL / target / trail for all open trades."""
        for trade in list(self.risk.active_trades):
            if trade.status != "OPEN":
                continue

            quote = self.dhan.get_quote(trade.symbol)
            price = quote.get('last_price') or trade.current_price
            if price <= 0:
                continue

            self.executor.manage_trade(trade, price)

            pnl_str = f"₹{trade.pnl:+.2f} ({trade.pnl_percent:+.1f}%)"
            logger.info(f"📈 {trade.symbol} | LTP ₹{price:.2f} | {pnl_str} | SL ₹{trade.stop_loss:.2f}")

    # ── Status ─────────────────────────────────────────────
    def get_status(self) -> dict:
        return {
            'running':       self.running,
            'active_trades': len(self.risk.active_trades),
            'daily_summary': self.risk.get_daily_summary(),
            'timestamp':     datetime.now().isoformat(),
        }


# ══════════════════════════════════════════
# ENTRY POINT
# ══════════════════════════════════════════

def main():
    print("=" * 55)
    print("  🚀 NIFTY INTRADAY STRATEGY BOT")
    print("  Credentials loaded from ../.env")
    print(f"  Client ID : {Config.DHAN_CLIENT_ID or '⚠️  NOT SET'}")
    print(f"  Token set : {'✅ Yes' if Config.DHAN_ACCESS_TOKEN else '⚠️  NOT SET'}")
    print("=" * 55)

    bot = TradingBot()
    bot.start()


if __name__ == "__main__":
    main()
