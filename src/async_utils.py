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
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"BackgroundTask: Unhandled exception in {t.get_coro()}: {e}")

    task.add_done_callback(_handle_task_result)
    return task
