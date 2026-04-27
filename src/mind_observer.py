import asyncio
import logging
import time
from typing import Any

from mind_bridge import MindBridge

logger = logging.getLogger(__name__)


class MindObserver:
    """
    Agent H: The Observation Mind.
    Focuses on 'Global Contextual State' and 'Information Scent'.
    Inspired by Claude-Code's WebFetch and Search patterns.
    """

    def __init__(self, bridge: MindBridge, qdb: Any = None) -> None:
        self.bridge = bridge
        self.qdb = qdb
        self.is_running = False
        self.current_market_sentiment: str = "NEUTRAL"
        self.market_beta: float = 1.0
        self._task: asyncio.Task | None = None

        # Register Observation Tools
        self.bridge.register_tool("fetch_sentiment", self._tool_fetch_sentiment)
        self.bridge.register_tool("scan_environment", self._tool_scan_environment)

    async def start(self) -> None:
        """Launch the Observation Mind."""
        self.is_running = True
        logger.info("MindObserver (Agent H): Information gathering active.")
        self._task = asyncio.create_task(self._run_observation_loop())

    def stop(self) -> None:
        """Gracefully stop the Observation Mind (Samvid v1.0-beta-beta)."""
        self.is_running = False
        if self._task and not self._task.done():
            self._task.cancel()
            logger.info("MindObserver: Background observation loop terminated.")

    async def _run_observation_loop(self) -> None:
        """Continuously pulls contextual 'Scent' via Bus Events."""
        if not self.bridge.bus:
            logger.warning("MindObserver: No Intelligence Bus found. Running in fallback mode.")
            return

        # Subscribe to news updates from the DataPipeline
        news_queue = self.bridge.bus.subscribe("news.update")
        self._last_broadcast_time = 0.0

        while self.is_running:
            try:
                # Wait for news update from the Bus
                payload = await news_queue.get()
                sentiment_val = payload.get("avg_sentiment", 0.0)
                headlines = payload.get("headlines", [])

                # Convert numeric sentiment to classification with HYSTERESIS (GAP-69 Fix)
                # We require a stronger move to flip states (0.3 -> 0.2 buffer)
                new_sentiment = self.current_market_sentiment
                if sentiment_val > 0.35:
                    new_sentiment = "BULLISH"
                elif sentiment_val < -0.35:
                    new_sentiment = "BEARISH"
                elif -0.2 < sentiment_val < 0.2:
                    new_sentiment = "NEUTRAL"

                # Debounce: Prevent 'Sentiment Oscillation Bomb' (GAP-69)
                # GAP-11 FIX: Use Sovereign TimeSync for global consistency
                from time_sync import TimeSync
                now = TimeSync.now().timestamp()
                if new_sentiment != self.current_market_sentiment and (now - self._last_broadcast_time > 300):
                    self.current_market_sentiment = new_sentiment
                    self._last_broadcast_time = now
                    await self.bridge.broadcast(
                        "observer",
                        f"CONTEXTURE SHIFT: Market sentiment is now {self.current_market_sentiment} (based on {len(headlines)} headlines).",
                        {
                            "type": "SENTIMENT",
                            "value": self.current_market_sentiment,
                            "headlines": headlines[:3],
                        },
                    )

                logger.debug(
                    f"MindObserver: Global scent updated (Val: {sentiment_val:.2f}, Sentiment: {self.current_market_sentiment})."
                )
            except Exception as e:
                logger.error(f"MindObserver: Observation loop error: {e}")
                await asyncio.sleep(10)

    # --- OBSERVATION TOOLS (Inspired by Claude-Code WebFetch) ---

    async def _tool_fetch_sentiment(self) -> dict[str, Any]:
        """Simulates fetching global sentiment from external feeds (MCP-compatible)."""
        # GAP-68 FIX: Replaced hardcoded 'BULLISH' fraud with actual sensed state
        from time_sync import TimeSync
        return {
            "sentiment": self.current_market_sentiment,
            "timestamp": TimeSync.now().timestamp(),
            "status": "LIVE_SENSE"
        }

    async def _tool_scan_environment(self) -> dict[str, Any]:
        """Scans the local database for staleness or 'Dirty Data' (GAP-254)."""
        if not self.qdb or not self.qdb.enabled:
             return {"status": "OFFLINE", "reason": "QuestDB not active"}
             
        from data_pipeline import DataPipeline
        import pandas as pd
        from time_sync import TimeSync
        
        stale_symbols = []
        now_ts = TimeSync.now().timestamp()
        
        # Optimized Pulse Check: Monitor Top 5 Core Indices
        core_symbols = ["SPY", "QQQ", "IWM", "DIA", "XLK"]
        for symbol in core_symbols:
            try:
                df = await self.qdb.fetch_ohlcv_pandas(symbol, timeframe="1m", limit=1)
                if df is not None and not df.empty:
                    # QuestDB timestamps are typically UTC
                    last_ts = pd.to_datetime(df['timestamp'].iloc[0]).timestamp()
                    if now_ts - last_ts > 300: # 5 minute staleness threshold
                        stale_symbols.append(symbol)
                else:
                    stale_symbols.append(symbol) # No data in DB for core instrument
            except Exception as e:
                logger.debug(f"MindObserver: Pulse check failed for {symbol}: {e}")
                continue
                
        status = "DIRTY" if stale_symbols else "CLEAN"
        return {
            "stale_count": len(stale_symbols),
            "stale_symbols": stale_symbols,
            "status": status,
            "timestamp": now_ts
        }
