import logging
from typing import Callable, Dict, List, Type
from models.events import DomainEvent

logger = logging.getLogger("event_manager")

class EventManager:
    """
    Central pub/sub message bus for domain events.
    Events are treated as immutable domain facts.
    """
    def __init__(self):
        # Maps Event classes to a list of handler functions
        self._handlers: Dict[Type[DomainEvent], List[Callable[[DomainEvent], None]]] = {}

    def subscribe(self, event_type: Type[DomainEvent], handler: Callable[[DomainEvent], None]):
        """Subscribe a handler to a specific domain event type."""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        if handler not in self._handlers[event_type]:
            self._handlers[event_type].append(handler)
            logger.debug(f"Subscribed {handler.__name__} to {event_type.__name__}")

    def publish(self, event: DomainEvent):
        """Publish an event to all registered handlers."""
        event_type = type(event)
        
        logger.debug(f"[EVENT] {event_type.__name__} | source={event.source} | correlation_id={event.correlation_id}")
        
        handlers = self._handlers.get(event_type, [])
        for handler in handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error(f"Error handling event {event_type.__name__} in {handler.__name__}: {e}", exc_info=True)
