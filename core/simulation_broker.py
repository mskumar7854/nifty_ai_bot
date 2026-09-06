import uuid
from typing import Dict, Any, Optional
from core.execution_fidelity import ExecutionFidelityEngine

class SimulationBroker:
    """
    Simulates the DhanHQ broker API interface for execution simulation.
    Delegates fill mechanics to ExecutionFidelityEngine to provide
    realistic slippage, latency, and rejections.
    """
    def __init__(self, fidelity_engine: ExecutionFidelityEngine = None):
        self.fidelity_engine = fidelity_engine or ExecutionFidelityEngine()
        self.orders: Dict[str, Dict[str, Any]] = {}
        self.context: Dict[str, Any] = {}

    def set_context(self, signal, snapshot, instrument_info):
        """Inject context needed by ExecutionFidelityEngine for the next order."""
        self.context = {
            "signal": signal,
            "snapshot": snapshot,
            "instrument": instrument_info
        }

    def place_order(self, security_id, exchange_segment, transaction_type, quantity, order_type, product_type, price=0, trigger_price=0, correlation_id=None, **kwargs):
        order_id = str(uuid.uuid4())[:8]
        
        # Simulate fill via fidelity engine if MARKET entry
        if order_type == "MARKET" and not correlation_id: # Usually Entry order
            sig = self.context.get("signal")
            snap = self.context.get("snapshot")
            inst = self.context.get("instrument", {})
            
            base_price = price if price > 0 else (sig.metadata.get("premium_entry", 100) if sig and hasattr(sig, "metadata") else 100)
            
            if sig and snap:
                res = self.fidelity_engine.simulate_entry(
                    signal_price=base_price,
                    spot_price=snap.price,
                    strike=inst.get("strike", snap.price),
                    option_type=inst.get("type", "CE"),
                    qty=quantity,
                    regime=sig.regime.value if hasattr(sig.regime, "value") else str(getattr(sig, "regime", "UNKNOWN")),
                    vix=snap.india_vix if hasattr(snap, "india_vix") else getattr(snap, "vix", 14.0),
                    expiry_date=inst.get("expiry_date")
                )
                if res.rejected:
                    # Simulate broker rejection
                    self.orders[order_id] = {
                        "status": "REJECTED",
                        "reason": res.rejection_reason
                    }
                    return {"status": "failure", "remarks": res.rejection_reason, "data": {}}
                
                fill_price = res.fill_price
            else:
                fill_price = base_price

            self.orders[order_id] = {
                "orderId": order_id,
                "orderStatus": "TRADED",
                "price": fill_price,
                "quantity": quantity,
                "transactionType": transaction_type,
                "correlationId": correlation_id
            }
        else:
            # Stop loss or target order (SL-M)
            self.orders[order_id] = {
                "orderId": order_id,
                "orderStatus": "PENDING",
                "price": price,
                "triggerPrice": trigger_price,
                "quantity": quantity,
                "transactionType": transaction_type,
                "correlationId": correlation_id
            }

        return {"status": "success", "data": {"orderId": order_id}}

    def modify_order(self, order_id, order_type, leg_name, quantity, price, trigger_price, validity, **kwargs):
        if order_id in self.orders:
            self.orders[order_id]["triggerPrice"] = trigger_price
            self.orders[order_id]["price"] = price
            return {"status": "success", "data": {"orderId": order_id}}
        return {"status": "failure"}

    def cancel_order(self, order_id, **kwargs):
        if order_id in self.orders:
            self.orders[order_id]["orderStatus"] = "CANCELLED"
            return {"status": "success"}
        return {"status": "failure"}

    def get_order_status(self, order_id, **kwargs):
        if order_id in self.orders:
            return {"status": "success", "data": self.orders[order_id]}
        return {"status": "failure"}

    def get_order_list(self, **kwargs):
        return {"status": "success", "data": list(self.orders.values())}

    def simulate_hit(self, order_id, hit_price):
        """Helper for simulation exit engine to trigger pending orders."""
        if order_id in self.orders:
            self.orders[order_id]["orderStatus"] = "TRADED"
            self.orders[order_id]["price"] = hit_price
