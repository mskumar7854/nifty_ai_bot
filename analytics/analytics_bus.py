import logging
from typing import Dict, List, Callable, Any
from datetime import datetime

logger = logging.getLogger("analytics_bus")

class AnalyticsBus:
    """
    Central event bus for the Nifty AI analytics framework.
    Publishers emit events (e.g., trade_opened, signal_generated).
    Subscribers (diagnostic engines) listen and process them independently.
    This prevents fragmented logging and tightly coupled analytics code.
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AnalyticsBus, cls).__new__(cls)
            cls._instance._subscribers = {}
            cls._instance.logger = logger
        return cls._instance

    def subscribe(self, event_type: str, handler: Callable[[Dict[str, Any]], None]):
        """Register a handler for a specific event type."""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        if handler not in self._subscribers[event_type]:
            self._subscribers[event_type].append(handler)
            self.logger.debug(f"Subscribed {handler.__name__} to '{event_type}'")

    def publish(self, event_type: str, payload: Dict[str, Any]):
        """Publish an event to all registered subscribers."""
        if "timestamp" not in payload:
            payload["timestamp"] = datetime.now().isoformat()
            
        handlers = self._subscribers.get(event_type, [])
        if not handlers:
            return

        for handler in handlers:
            try:
                handler(payload)
            except Exception as e:
                self.logger.error(f"Error in subscriber {handler.__name__} for event {event_type}: {e}")

# Global instance
analytics_bus = AnalyticsBus()
