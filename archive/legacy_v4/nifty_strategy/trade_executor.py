"""
============================================
TRADE EXECUTOR
============================================
Wires strategy signals → Dhan API orders.

Uses the project-level dhan_client singleton
(credentials from .env — never hardcoded).
============================================
"""

import sys
import os
import logging
from datetime import datetime
from dataclasses import dataclass
from typing import Optional

# ── Make project root importable ──────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from .config import Config
from risk_manager import Trade, RiskManager
from models.trade_record import TradeRecord
from utils.trade_logger import TradeLogger
from options_selector import (
    OptionStrikeSelector, OptionContractBuilder, get_option_security_id
)

logger = logging.getLogger("trade_executor")


# ══════════════════════════════════════════
# ORDER RESULT
# ══════════════════════════════════════════

@dataclass
class OrderResult:
    success: bool
    order_id: Optional[str] = None
    message: str = ""
    error: Optional[str] = None


# ══════════════════════════════════════════
# DHAN CONNECTOR  (wraps dhanhq client)
# ══════════════════════════════════════════

class DhanConnector:
    """
    Thin wrapper around the dhanhq client.

    Credentials are read from .env via dhan_client.py —
    never pass them as constructor arguments.
    """

    def __init__(self):
        self._client = None

    def connect(self) -> bool:
        """Lazy-init the singleton Dhan client."""
        try:
            # Import project-level singleton (reads .env automatically)
            from dhan_client import get_dhan_client
            self._client = get_dhan_client()
            logger.info("Dhan API connected ✓")
            return True
        except Exception as e:
            logger.error(f"Dhan connection failed: {e}")
            return False

    @property
    def client(self):
        return self._client

    # ── Market data ───────────────────────────────────────
    def get_quote(self, security_id: str) -> dict:
        """
        Live LTP from Dhan.
        Replace with actual dhanhq method when available.
        """
        try:
            if self._client:
                # dhanhq v2: client.get_ltp_data(...)
                # Placeholder until you verify the exact method name:
                return {'last_price': 0, 'bid_price': 0, 'ask_price': 0, 'volume': 0}
        except Exception as e:
            logger.error(f"get_quote error: {e}")
        return {}

    # ── Order management ──────────────────────────────────
    def place_order(
        self,
        security_id: str,
        exchange_segment: str,  # NSE_FNO
        transaction_type: str,  # BUY | SELL
        quantity: int,
        order_type: str = "MARKET",
        price: float = 0,
        product_type: str = "INTRADAY",
    ) -> OrderResult:
        """
        Place order on Dhan.

        dhanhq library call:
          client.place_order(
              security_id=..., exchange_segment=...,
              transaction_type=..., quantity=...,
              order_type=..., product_type=...,
              price=...,
          )
        """
        try:
            if self._client is None:
                return OrderResult(False, error="Not connected")

            response = self._client.place_order(
                security_id=security_id,
                exchange_segment=exchange_segment,
                transaction_type=transaction_type,
                quantity=quantity,
                order_type=order_type,
                product_type=product_type,
                price=price,
            )

            if response.get('status') == 'success':
                order_id = response.get('data', {}).get('orderId', '')
                return OrderResult(True, order_id=str(order_id), message="Order placed")

            return OrderResult(False, error=str(response))

        except Exception as e:
            logger.error(f"place_order exception: {e}")
            return OrderResult(False, error=str(e))

    def cancel_order(self, order_id: str) -> OrderResult:
        try:
            if self._client:
                response = self._client.cancel_order(order_id=order_id)
                if response.get('status') == 'success':
                    return OrderResult(True, order_id=order_id, message="Cancelled")
            return OrderResult(False, error="Not connected or cancel failed")
        except Exception as e:
            return OrderResult(False, error=str(e))

    def get_order_status(self, order_id: str) -> dict:
        try:
            if self._client:
                return self._client.get_order_by_id(order_id=order_id) or {}
        except Exception as e:
            logger.error(f"get_order_status: {e}")
        return {}


# ══════════════════════════════════════════
# TRADE EXECUTOR
# ══════════════════════════════════════════

class TradeExecutor:
    """
    Converts strategy signals into orders and manages
    open positions (SL, trailing stop, partial exits).
    """

    # Dhan exchange segment for Nifty options
    EXCHANGE_SEGMENT = "NSE_FNO"

    def __init__(self, dhan: DhanConnector, risk_manager: RiskManager):
        self.dhan = dhan
        self.risk = risk_manager
        self.trade_logger: Optional[TradeLogger] = None

    def set_logger(self, trade_logger: TradeLogger):
        self.trade_logger = trade_logger

    # ── Entry ──────────────────────────────────────────────
    def execute_signal(
        self,
        signal: str,
        analysis: dict,
        spot_price: float,
        atr: Optional[float] = None,
        expiry: str = "03APR",    # Update to active weekly expiry
    ) -> Optional[Trade]:
        """
        Full entry flow:
          1. Risk gate
          2. Strike + symbol resolution
          3. LTP fetch
          4. SL / target calc
          5. Position sizing
          6. Order placement
          7. Trade recording
        """
        if signal not in Config.ALLOWED_SIGNALS:
            return None

        can_trade, reason = self.risk.can_take_trade(signal)
        if not can_trade:
            self._log_error(f"Risk gate blocked: {reason}")
            return None

        option_type = "CE" if signal == "BUY_CE" else "PE"
        strike = OptionStrikeSelector.select_strike(spot_price, option_type, "ATM")
        symbol = OptionContractBuilder.get_trading_symbol(
            Config.UNDERLYING, strike, expiry, option_type
        )

        security_id = get_option_security_id(symbol)
        if not security_id:
            self._log_error(f"Security ID not found for {symbol}. Update OPTION_SECURITY_IDS.")
            return None

        # LTP
        quote = self.dhan.get_quote(security_id)
        entry_price = (
            quote.get('last_price')
            or (quote.get('bid_price', 0) + quote.get('ask_price', 0)) / 2
        )
        if entry_price <= 0:
            self._log_error(f"Could not fetch LTP for {symbol}")
            return None

        # SL / target / size
        stop_loss = self.risk.calculate_stop_loss(entry_price, option_type, atr)
        target    = self.risk.calculate_target(entry_price, stop_loss)
        position  = self.risk.calculate_position_size(
            entry_price = entry_price, 
            stop_loss   = stop_loss,
            entry_type  = analysis.get('entry_type', 'AI'),
            score       = analysis.get('score', 0.0)
        )
        quantity  = position['quantity']

        trade = Trade(
            symbol=symbol,
            entry_price=entry_price,
            quantity=quantity,
            option_type=option_type,
            strike=strike,
            expiry=expiry,
            timestamp=datetime.now(),
            entry_reason=(
                f"Signal:{signal} | "
                f"Trend:{analysis.get('trend')} | "
                f"RSI:{analysis['details'].get('rsi_details', {}).get('rsi', ''):.1f}"
            ),
            stop_loss=stop_loss,
            target=target,
            current_price=entry_price,
        )

        result = self.dhan.place_order(
            security_id=security_id,
            exchange_segment=self.EXCHANGE_SEGMENT,
            transaction_type="BUY",
            quantity=quantity,
            order_type="MARKET",
            product_type="INTRADAY",
        )

        if result.success:
            trade.status = "OPEN"
            # Store analysis for later logging upon exit
            trade._analysis_snapshot = analysis
            self.risk.record_trade(trade)
            
            logger.info(f"✅ Order placed | {symbol} | ₹{entry_price:.2f} | "
                        f"SL:₹{stop_loss:.2f} | T:₹{target:.2f}")
            return trade

        self._log_error(f"Order failed: {result.error}")
        return None

    # ── Position management ────────────────────────────────
    def manage_trade(
        self,
        trade: Trade,
        current_price: float,
    ) -> Trade:
        """
        Called every market tick / loop cycle.
        Checks SL → Target → Trail → Partial exit.
        """
        if trade.status != "OPEN":
            return trade

        trade.current_price = current_price
        trade.update_pnl()

        # ── Stop-loss hit ──────────────────────────────────
        if current_price <= trade.stop_loss:
            self._close_trade(trade, current_price, "SL hit")
            return trade

        # ── Target hit ─────────────────────────────────────
        if current_price >= trade.target:
            self._close_trade(trade, current_price, "Target hit")
            return trade

        # ── Trailing stop update ───────────────────────────
        new_sl = self.risk.trail_stop_loss(trade, current_price)
        if new_sl > trade.stop_loss:
            old_sl = trade.stop_loss
            trade.stop_loss = new_sl
            if self.trade_logger:
                self.trade_logger.log_sl_trail(trade, old_sl, new_sl)
            logger.info(f"SL trailed {old_sl:.2f} → {new_sl:.2f} | {trade.symbol}")

        # ── Partial exit at +30% ───────────────────────────
        if trade.pnl_percent >= Config.PARTIAL_EXIT_PERCENT and not trade._partial_exited:
            trade._partial_exited = True
            partial_qty = int(trade.quantity * Config.PARTIAL_EXIT_QTY_PERCENT / 100)
            partial_qty = (partial_qty // Config.LOT_SIZE) * Config.LOT_SIZE or Config.LOT_SIZE

            security_id = get_option_security_id(trade.symbol)
            if security_id and partial_qty > 0:
                res = self.dhan.place_order(
                    security_id=security_id,
                    exchange_segment=self.EXCHANGE_SEGMENT,
                    transaction_type="SELL",
                    quantity=partial_qty,
                    order_type="MARKET",
                    product_type="INTRADAY",
                )
                if res.success:
                    logger.info(
                        f"Partial exit {partial_qty} lots | {trade.symbol} "
                        f"@ ₹{current_price:.2f} | P&L ₹{trade.pnl:+.2f}"
                    )

        return trade

    # ── Internals ──────────────────────────────────────────
    def _close_trade(self, trade: Trade, exit_price: float, reason: str):
        """Place SELL order then update books."""
        security_id = get_option_security_id(trade.symbol)
        if security_id:
            self.dhan.place_order(
                security_id=security_id,
                exchange_segment=self.EXCHANGE_SEGMENT,
                transaction_type="SELL",
                quantity=trade.quantity,
                order_type="MARKET",
                product_type="INTRADAY",
            )

        self.risk.close_trade(trade, exit_price, reason)
        
        # ── Unified Performance Logging (NDJSON) ───────────
        if self.trade_logger:
            analysis = getattr(trade, '_analysis_snapshot', {})
            
            # Map strategy 'Trade' to analytics 'TradeRecord'
            record = TradeRecord(
                signal           = trade.option_type,
                weighted_score   = analysis.get('score', 0.0),
                buy_score        = analysis.get('ai_details', {}).get('confidence', 0.0), # Example mapping
                sell_score       = 0.0,
                gap              = 0.0,
                agent_breakdown  = analysis.get('ai_details', {}).get('agreeing_agents', {}),
                market_regime    = analysis.get('ai_details', {}).get('regime', 'UNKNOWN'),
                volatility       = 0.0, # To be added from indicators if needed
                entry_type       = analysis.get('entry_type', 'AI'),
                account_balance  = 100000.0, # Placeholder — should pull from Dhan
                open_positions    = len(self.risk.active_trades),
                entry_price      = trade.entry_price,
                exit_price       = trade.exit_price,
                quantity         = trade.quantity,
                pnl              = trade.pnl,
                outcome          = "WIN" if trade.pnl > 0 else ("LOSS" if trade.pnl < 0 else "BREAKEVEN"),
                time_in_trade    = (trade.exit_timestamp - trade.timestamp).total_seconds() / 60 if trade.exit_timestamp else 0
            )
            self.trade_logger.log_trade(record)
