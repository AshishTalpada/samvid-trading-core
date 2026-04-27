# pyre-ignore-all-errors[21]
"""
src/api_cache.py - Thread-Safe TTL In-Memory Cache

Prevents redundant API calls (Gemini 429, yfinance rate limits) by
caching responses with automatic time-based expiry.

Usage:
    cache = TTLCache(default_ttl=300)
    cache.set("SPY_price", 560.25, ttl=60)
    val = cache.get("SPY_price")  # Returns 560.25 or None if expired

    # Async fetch-or-cache pattern:
    val = await cache.get_or_fetch("SPY_price", fetch_spy_price, ttl=60)
"""

import asyncio
import hashlib
import logging
import threading
import time
from collections.abc import Callable, Coroutine
from typing import Any

logger = logging.getLogger(__name__)


class TTLCache:
    """
    Thread-safe in-memory cache with per-key TTL expiry.

    Designed for high-frequency trading systems where:
    - API rate limits (429) must be avoided
    - Data freshness windows are well-defined (e.g. 5min for tickers, 10min for LLM)
    - Memory must be bounded (max_size evicts oldest entries)
    """

    def __init__(self, default_ttl: float = 300.0, max_size: int = 1000) -> None:
        self._store: dict[str, tuple[Any, float]] = {}  # key -> (value, expires_at)
        self._lock = asyncio.Lock()
        self._default_ttl = default_ttl
        self._max_size = max_size
        self._hits = 0
        self._misses = 0
        self._is_running = True
        
        # GAP-46: Periodic Scavenger (Anti-Zombie Task)
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def _cleanup_loop(self) -> None:
        """Background loop to periodically prune stale entries (Samvid v1.0-beta-beta)."""
        while self._is_running:
            try:
                await asyncio.sleep(60) # Scavenge every minute
                await self.prune()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"TTLCache: Cleanup error: {e}")

    async def prune(self) -> int:
        """Remove all expired entries from the cache. Returns count of pruned items."""
        now = time.monotonic()
        pruned = 0
        async with self._lock:
            # We must convert keys to list to avoid 'size changed during iteration' error
            expired_keys = [k for k, v in self._store.items() if now > v[1]]
            for k in expired_keys:
                del self._store[k]
                pruned += 1
        if pruned > 0:
            logger.debug(f"TTLCache: Pruned {pruned} zombie entries.")
        return pruned

    async def stop(self) -> None:
        """Gracefully stop the background cleanup task."""
        self._is_running = False
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

    async def get(self, key: str) -> Any | None:
        """Return cached value if it exists and hasn't expired, else None."""
        async with self._lock:
            entry = self._store.get(key)
            if entry is None:
                self._misses += 1
                return None
            value, expires_at = entry
            if time.monotonic() > expires_at:
                del self._store[key]  # pyre-ignore[16]
                self._misses += 1
                return None
            self._hits += 1
            return value

    async def set(self, key: str, value: Any, ttl: float | None = None) -> None:
        """Store a value with an optional per-key TTL override."""
        effective_ttl = ttl if ttl is not None else self._default_ttl
        async with self._lock:
            # Evict oldest if at capacity
            if len(self._store) >= self._max_size:
                self._evict_oldest()
            self._store[key] = (value, time.monotonic() + effective_ttl)

    async def get_or_fetch(
        self,
        key: str,
        fetch_fn: Callable[[], Coroutine[Any, Any, Any]],
        ttl: float | None = None,
    ) -> Any:
        """
        Return cached value if fresh; otherwise call fetch_fn, cache result, and return it.

        This is the primary interface for DhatuOracle ingestion methods.
        """
        cached = await self.get(key)
        if cached is not None:
            logger.debug(f"Cache HIT: {key}")
            return cached

        # Cache miss — fetch live
        result = await fetch_fn()
        if result is not None:
            await self.set(key, result, ttl)
        return result

    async def invalidate(self, key: str) -> None:
        """Remove a specific key from the cache."""
        async with self._lock:
            self._store.pop(key, None)

    async def clear(self) -> None:
        """Flush the entire cache."""
        async with self._lock:
            self._store.clear()
            self._hits = 0
            self._misses = 0

    def _evict_oldest(self) -> None:
        """Remove the entry with the earliest expiry time."""
        if not self._store:
            return
        oldest_key = min(self._store, key=lambda k: self._store[k][1])
        del self._store[oldest_key]  # pyre-ignore[16]

    @property
    def stats(self) -> dict[str, int]:
        """Return cache hit/miss statistics."""
        return {
            "hits": self._hits,
            "misses": self._misses,
            "size": len(self._store),
            "hit_rate_pct": int(self._hits / max(self._hits + self._misses, 1) * 100),
        }

    @staticmethod
    def hash_key(*args: Any) -> str:
        """Generate a deterministic cache key from arbitrary arguments."""
        raw = "|".join(str(a) for a in args)
        return hashlib.md5(raw.encode()).hexdigest()  # nosec B324
