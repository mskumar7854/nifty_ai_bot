import time
import json
import logging
import os
import sys
from datetime import datetime

# Setup basic logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("watchdog")

class WatchdogSupervisor:
    """
    Independent Risk Supervisor
    Runs as a completely separate process from the main trading engine.
    """
    def __init__(self):
        self.heartbeat_file = "data/heartbeat.json"
        self.lock_file = "data/SYSTEM_LOCK"
        self.max_heartbeat_age = 15.0  # seconds
        
        # Load max loss from settings, fallback to -25000 if not available
        self.max_daily_loss = -25000.0
        try:
            from config.settings import Settings
            settings = Settings()
            if hasattr(settings, "risk") and hasattr(settings.risk, "max_daily_loss"):
                self.max_daily_loss = -abs(settings.risk.max_daily_loss)
        except Exception:
            pass

    def is_locked(self) -> bool:
        return os.path.exists(self.lock_file)

    def lock_system(self, reason: str):
        """Creates the SYSTEM_LOCK file preventing main loop execution."""
        try:
            with open(self.lock_file, "w") as f:
                json.dump({
                    "reason": reason,
                    "timestamp": datetime.now().isoformat()
                }, f)
            logger.critical(f"🔒 SYSTEM LOCKED: {reason}")
        except Exception as e:
            logger.critical(f"Failed to create lock file: {e}")

    def emergency_squareoff(self, reason: str):
        """Flatten all positions immediately."""
        logger.critical(f"🚨 EMERGENCY SQUAREOFF INITIATED: {reason}")
        try:
            from dhan_client import get_dhan_client
            dhan = get_dhan_client()
            
            # Fetch and close all positions
            pos_resp = dhan.get_positions()
            if pos_resp and pos_resp.get("status") == "success":
                positions = pos_resp.get("data", [])
                for pos in positions:
                    qty = pos.get("netQty", 0)
                    if qty != 0:
                        logger.warning(f"Squaring off {pos.get('tradingSymbol')} (Qty: {qty})")
                        side = "SELL" if qty > 0 else "BUY"
                        dhan.place_order(
                            security_id=pos.get("securityId"),
                            exchange_segment=pos.get("exchangeSegment"),
                            transaction_type=side,
                            quantity=abs(qty),
                            order_type="MARKET",
                            product_type=pos.get("productType"),
                            price=0
                        )
            
            # Cancel all open orders (SLs)
            order_resp = dhan.get_order_list()
            if order_resp and order_resp.get("status") == "success":
                for order in order_resp.get("data", []):
                    if order.get("orderStatus") in ("PENDING", "TRIGGER_PENDING", "OPEN"):
                        dhan.cancel_order(order.get("orderId"))
                        
        except Exception as e:
            logger.critical(f"Emergency squareoff failed: {e}")

    def verify_heartbeat(self):
        """Verify the main loop is actively running."""
        if not os.path.exists(self.heartbeat_file):
            return  # Allow startup grace period
            
        try:
            with open(self.heartbeat_file, "r") as f:
                data = json.load(f)
                
            last_hb = data.get("last_heartbeat", 0)
            age = time.time() - last_hb
            
            if age > self.max_heartbeat_age:
                msg = f"Heartbeat is stale: {age:.1f}s > {self.max_heartbeat_age}s"
                self.emergency_squareoff(msg)
                self.lock_system(msg)
        except Exception as e:
            logger.error(f"Failed to verify heartbeat: {e}")

    def verify_sl_presence(self):
        """Verify every open position has an active SL order."""
        try:
            from dhan_client import get_dhan_client
            dhan = get_dhan_client()
            
            pos_resp = dhan.get_positions()
            if not pos_resp or pos_resp.get("status") != "success":
                return
                
            positions = [p for p in pos_resp.get("data", []) if p.get("netQty", 0) != 0]
            if not positions:
                return  # No open positions
                
            order_resp = dhan.get_order_list()
            if not order_resp or order_resp.get("status") != "success":
                return
                
            orders = order_resp.get("data", [])
            sl_symbols = {
                o.get("tradingSymbol") for o in orders
                if o.get("orderType") in ("SL", "SL-M") and o.get("orderStatus") in ("PENDING", "TRIGGER_PENDING", "OPEN")
            }
            
            missing_sl = []
            for pos in positions:
                sym = pos.get("tradingSymbol")
                if sym not in sl_symbols:
                    missing_sl.append(sym)
                    
            if missing_sl:
                msg = f"Positions missing SL: {', '.join(missing_sl)}"
                self.emergency_squareoff(msg)
                self.lock_system(msg)
                
        except Exception as e:
            logger.error(f"Failed to verify SL presence: {e}")

    def verify_max_loss(self):
        """Verify daily loss limit is not breached."""
        try:
            from dhan_client import get_dhan_client
            dhan = get_dhan_client()
            
            pos_resp = dhan.get_positions()
            if not pos_resp or pos_resp.get("status") != "success":
                return
                
            positions = pos_resp.get("data", [])
            total_realized = sum(p.get("realizedProfit", 0) for p in positions)
            total_unrealized = sum(p.get("unrealizedProfit", 0) for p in positions)
            daily_pnl = total_realized + total_unrealized
            
            if daily_pnl <= self.max_daily_loss:
                msg = f"Max daily loss breached! PnL: {daily_pnl} <= {self.max_daily_loss}"
                self.emergency_squareoff(msg)
                self.lock_system(msg)
                
        except Exception as e:
            logger.error(f"Failed to verify max loss: {e}")

    def run(self):
        logger.info("🛡️ Independent Risk Supervisor started.")
        while True:
            if self.is_locked():
                logger.warning("System is locked. Watchdog standing by. Please remove data/SYSTEM_LOCK manually to resume.")
                time.sleep(10)
                continue
                
            try:
                self.verify_heartbeat()
                if self.is_locked(): continue
                
                self.verify_sl_presence()
                if self.is_locked(): continue
                
                self.verify_max_loss()
            except Exception as e:
                logger.error(f"Watchdog iteration error: {e}")
                
            time.sleep(3)  # Polling interval

if __name__ == "__main__":
    # Check if inside correct directory
    if not os.path.exists("data"):
        os.makedirs("data")
    
    watchdog = WatchdogSupervisor()
    watchdog.run()
