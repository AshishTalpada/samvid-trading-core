"""
tests/test_cache_and_async.py
Tests for:
  - api_cache.TTLCache (TTL in-memory cache)
  - async_utils.create_task_safe (background task helper)
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


# ── TTLCache ──────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_ttl_set_and_get():
    from api_cache import TTLCache
    c = TTLCache(default_ttl=60.0)
    await c.set("key1", "value1")
    assert await c.get("key1") == "value1"


@pytest.mark.asyncio
async def test_ttl_missing_key_returns_none():
    from api_cache import TTLCache
    c = TTLCache()
    assert await c.get("nonexistent") is None


@pytest.mark.asyncio
async def test_ttl_expired_returns_none():
    from api_cache import TTLCache
    c = TTLCache()
    await c.set("key_exp", "data", ttl=0.001)
    await asyncio.sleep(0.02)
    assert await c.get("key_exp") is None


@pytest.mark.asyncio
async def test_ttl_hit_counter():
    from api_cache import TTLCache
    c = TTLCache()
    await c.set("x", 42)
    await c.get("x")
    await c.get("x")
    assert c.stats["hits"] == 2


@pytest.mark.asyncio
async def test_ttl_miss_counter():
    from api_cache import TTLCache
    c = TTLCache()
    await c.get("missing_a")
    await c.get("missing_b")
    assert c.stats["misses"] == 2


@pytest.mark.asyncio
async def test_ttl_invalidate():
    from api_cache import TTLCache
    c = TTLCache()
    await c.set("del_me", "value")
    await c.invalidate("del_me")
    assert await c.get("del_me") is None


@pytest.mark.asyncio
async def test_ttl_clear():
    from api_cache import TTLCache
    c = TTLCache()
    await c.set("a", 1)
    await c.set("b", 2)
    await c.clear()
    assert c.stats["size"] == 0


@pytest.mark.asyncio
async def test_ttl_prune_expired():
    from api_cache import TTLCache
    c = TTLCache()
    await c.set("stale", "old", ttl=0.001)
    await asyncio.sleep(0.02)
    pruned = await c.prune()
    assert pruned >= 1


@pytest.mark.asyncio
async def test_ttl_max_size_eviction():
    from api_cache import TTLCache
    c = TTLCache(default_ttl=60.0, max_size=3)
    for i in range(4):
        await c.set(f"k{i}", i)
    assert c.stats["size"] <= 3


@pytest.mark.asyncio
async def test_ttl_get_or_fetch_miss():
    from api_cache import TTLCache
    c = TTLCache()
    called = []

    async def _fetch():
        called.append(True)
        return "fetched"

    result = await c.get_or_fetch("fresh_key", _fetch)
    assert result == "fetched"
    assert len(called) == 1


@pytest.mark.asyncio
async def test_ttl_get_or_fetch_hit():
    from api_cache import TTLCache
    c = TTLCache()
    called = []

    async def _fetch():
        called.append(True)
        return "fresh"

    await c.set("cached_key", "cached_value")
    result = await c.get_or_fetch("cached_key", _fetch)
    assert result == "cached_value"
    assert len(called) == 0


def test_ttl_hash_key_deterministic():
    from api_cache import TTLCache
    assert TTLCache.hash_key("SPY", 100.0, "BULL") == TTLCache.hash_key("SPY", 100.0, "BULL")


def test_ttl_hash_key_different_args():
    from api_cache import TTLCache
    assert TTLCache.hash_key("SPY", 100.0) != TTLCache.hash_key("QQQ", 100.0)


@pytest.mark.asyncio
async def test_ttl_stats_hit_rate():
    from api_cache import TTLCache
    c = TTLCache()
    await c.set("r", 1)
    await c.get("r")  # hit
    await c.get("r")  # hit
    await c.get("z")  # miss
    assert c.stats["hit_rate_pct"] == 66  # 2/3 = 66%


# ── async_utils.create_task_safe ─────────────────────────────────────────────
@pytest.mark.asyncio
async def test_create_task_safe_runs_coro():
    from async_utils import create_task_safe

    completed = []

    async def _work():
        completed.append(True)

    create_task_safe(_work())
    await asyncio.sleep(0.05)
    assert completed == [True]


@pytest.mark.asyncio
async def test_create_task_safe_handles_exception_gracefully():
    from async_utils import create_task_safe

    async def _fail():
        raise RuntimeError("deliberate error")

    task = create_task_safe(_fail())
    await asyncio.sleep(0.05)
    assert task.done()
