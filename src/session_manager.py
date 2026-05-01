import asyncio
import logging
from typing import Optional

import aiohttp

logger = logging.getLogger(__name__)

class SovereignSession:
    """
    Global Shared HTTP Session Manager.
    Prevents TCP connection leakage and memory exhaustion by pinning
    all outgoing HTTP requests to a single, persistent session.
    """
    _instance: Optional[aiohttp.ClientSession] = None
    _lock = asyncio.Lock()

    @classmethod
    async def get_session(cls) -> aiohttp.ClientSession:
        """Returns the global shared aiohttp session, initializing if necessary."""
        if cls._instance is None or cls._instance.closed:
            async with cls._lock:
                if cls._instance is None or cls._instance.closed:
                    timeout = aiohttp.ClientTimeout(total=30.0)
                    cls._instance = aiohttp.ClientSession(timeout=timeout)
                    logger.info("✓ SovereignSession: Global shared HTTP session initialized.")
        return cls._instance

    @classmethod
    async def close(cls) -> None:
        """Gracefully closes the shared session."""
        if cls._instance and not cls._instance.closed:
            async with cls._lock:
                if cls._instance and not cls._instance.closed:
                    await cls._instance.close()
                    logger.info("SovereignSession: Global shared HTTP session closed.")
