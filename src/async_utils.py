import asyncio
import logging

logger = logging.getLogger(__name__)
_background_tasks = set()


def create_task_safe(coro):
    """
    Safely creates an asyncio task and maintains a strong reference to it.
    Adds a callback to log any unhandled exceptions.
    """
    task = asyncio.create_task(coro)
    _background_tasks.add(task)

    def _handle_task_result(t):
        _background_tasks.discard(t)
        try:
            t.result()
        except asyncio.CancelledError as e:
            logger.debug("BackgroundTask: cancelled as expected: %s", e)
        except Exception as e:
            task_name = getattr(t, "get_name", lambda: "Unknown")()
            logger.critical(f"BackgroundTask: CRITICAL FAILURE in {task_name}: {e}")
            # In production, we should trigger a system halt here
            try:
                from trading_state import TradingStateManager

                TradingStateManager.halt(f"Critical background task failed: {e}")
            except Exception as halt_error:
                logger.error(f"BackgroundTask: Failed to trigger HALT: {halt_error}")

    task.add_done_callback(_handle_task_result)
    return task
