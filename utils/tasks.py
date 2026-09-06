import asyncio
import logging

logger = logging.getLogger(__name__)

def fire_and_log(coro, *, label: str = "") -> asyncio.Task:
    """
    Schedule a coroutine as a background task.
    Any exception is logged with the task label rather than silently dropped.
    """
    task = asyncio.create_task(coro)

    def _on_done(t: asyncio.Task) -> None:
        if t.cancelled():
            logger.warning("Task cancelled: %s", label)
        elif t.exception():
            logger.exception("Task failed: %s", label, exc_info=t.exception())

    task.add_done_callback(_on_done)
    return task
