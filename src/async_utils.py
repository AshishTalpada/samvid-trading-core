import asyncio

_background_tasks = set()

def create_task_safe(coro):
    """
    Safely creates an asyncio task and maintains a strong reference to it.
    This prevents Python 3.11+ garbage collector from aggressively destroying
    background tasks mid-execution if no hard reference is kept.
    """
    task = asyncio.create_task(coro)
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    return task
