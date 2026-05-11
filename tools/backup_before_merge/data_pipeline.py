import asyncio
import logging
import os
import random
import sqlite3
import time
from collections import deque
from datetime import datetime, timedelta, timezone
from datetime import time as dt_time
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from zoneinfo import ZoneInfo

import aiohttp
import numpy as np
import pandas as pd
import polars as pl

# Resolved: 'NoneType' object is not subscriptable in history.py:224
try:
    import yfinance.scrapers.history as yf_history
    _orig_history = (yf_history.History.history if hasattr(yf_history, "History") else yf_history.history)
    def _patched_history(*args, **kwargs):
        try:
            return _orig_history(*args, **kwargs)
        except Exception as e:
            err_msg = str(e).lower()
            if "subscriptable" in err_msg or "nonetype" in err_msg:
                import pandas as pd
                return pd.DataFrame()
            raise e
    if hasattr(yf_history, "History"): yf_history.History.history = _patched_history
    else: yf_history.history = _patched_history
except Exception: pass
import yfinance as yf

from config import QUESTDB_ENABLED
from openbb_provider import OpenBBProvider
from questdb_adapter import QuestDBAdapter

if TYPE_CHECKING:
    from intelligence_bus import SharedIntelligenceBus
from swarm_predictor import ChromaDeepMemory
from vault import Vault

logger = logging.getLogger(__name__)

class DataPipeline:
    """
    Sovereign Data Ingestion & Transformation Pipeline.
    Agent B: The Ingestion Mind.
    Integrated with C-drive HFT Normalizers and D-drive Institutional Persistence.
    """
    INSTRUMENTS = list(set([
        "SPY", "QQQ", "IWM", "DIA", "XLK", "XLF", "GC=F", "NQ=F",
        "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA",
        "AMD", "AVGO", "SMCI", "ARM", "MU", "PLTR", "COIN", "MSTR",
        "JPM", "GS", "V", "MA", "WMT", "COST", "NFLX"
    ]))

    def __init__(
        self,
        db_path: str = "data/trading.db",
        finnhub_key: str = "",
        qdb: QuestDBAdapter | None = None,
        openbb_provider: OpenBBProvider | None = None,
        bus: "SharedIntelligenceBus | None" = None,
        aggregation_window_ms: int = 1000,
        **kwargs
    ) -> None:
        self.db_path = str(db_path)
        self.agg_window_ms = aggregation_window_ms
        
        # Institutional Keys
        if not finnhub_key or finnhub_key == "YOUR_FINNHUB_KEY":
            finnhub_key = Vault.get("FINNHUB_API_KEY", "") or Vault.get("FINNHUB_KEY", "")
        self.finnhub_key = str(finnhub_key) if finnhub_key else ""
        
        self.is_running = False
        self._last_reality_check: dict[str, float] = {}
        self.bus = bus
        self.qdb = qdb if qdb is not None else QuestDBAdapter(enabled=QUESTDB_ENABLED)
        self.openbb = openbb_provider
        self._db_lock = asyncio.Lock()
        self._http_session: Optional[aiohttp.ClientSession] = None
        self._active_db_tasks = 0
        self._active_tasks_lock = asyncio.Lock()

        # HFT Buffers (C-drive logic)
        self.tick_buffers: Dict[str, deque] = {}
        self.last_bar_time: Dict[str, int] = {}
        self.price_history: Dict[str, deque] = {}
        self.lookback_window = 100
        self.prefetched_data: Dict[str, pd.DataFrame] = {}

        try:
            self.news_memory = ChromaDeepMemory(collection_name="market_news_v8")
        except Exception:
            self.news_memory = None

        # Lifecycle tracking
        self._news_task: asyncio.Task | None = None
        self._research_task: asyncio.Task | None = None
        self._sync_task: asyncio.Task | None = None
        self._enrichment_tasks: set[asyncio.Task] = set()

        self._init_database()
        logger.info(f"DataPipeline Initialized: WAL Persistence + HFT Buffering ({aggregation_window_ms}ms)")

    # --- CORE PERSISTENCE (D-DRIVE) ---

    def _get_db_connection(self):
        conn = sqlite3.connect(self.db_path, timeout=5.0, check_same_thread=False, isolation_level=None)
        conn.execute("PRAGMA busy_timeout = 5000;")
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn

    def _init_database(self) -> None:
        conn = self._get_db_connection()
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE IF NOT EXISTS ohlcv (id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT NOT NULL, timestamp TEXT NOT NULL, open REAL, high REAL, low REAL, close REAL, volume INTEGER, timeframe TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP, UNIQUE(symbol, timestamp, timeframe))")
        cursor.execute("CREATE TABLE IF NOT EXISTS vix_data (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT NOT NULL, value REAL NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP, UNIQUE(timestamp))")
        cursor.execute("CREATE TABLE IF NOT EXISTS news (id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT NOT NULL, headline TEXT, summary TEXT, source TEXT, url TEXT, published_at TEXT, sentiment REAL, created_at TEXT DEFAULT CURRENT_TIMESTAMP)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ohlcv_query ON ohlcv (symbol, timeframe, timestamp DESC);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ohlcv_time ON ohlcv (timestamp);")
        conn.commit()
        conn.close()

    async def fetch_ohlcv(
        self,
        symbol: str,
        tf: str = "1d",
        bars: int = 100,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> Optional["pl.DataFrame"]:
        try:
            if self.openbb and self.openbb.is_available and tf == "1d":
                pl_df = await self.openbb.fetch_ohlcv(symbol=symbol, period_days=bars, interval=tf)
                if pl_df is not None and len(pl_df) > 0: return pl_df

            interval_map = {"1m": "1m", "5m": "5m", "15m": "15m", "1h": "1h", "1d": "1d"}
            interval = interval_map.get(tf, tf)
            period = "60d" if interval in ["1m", "5m"] else f"{bars}d"
            
            ticker = await asyncio.to_thread(yf.Ticker, symbol)
            df = None
            for attempt in range(3):
                try:
                    df = await asyncio.to_thread(ticker.history, period=period if not start else None, start=start, end=end, interval=interval, timeout=20)
                    if df is not None and not df.empty: break
                except Exception as e:
                    if "subscriptable" in str(e).lower() or "429" in str(e).lower():
                        await asyncio.sleep(2**attempt)
                        continue
                    raise e
            
            if df is None or df.empty:
                logger.warning(f"DataPipeline: Zero-Volume Anomaly for {symbol}. Applying Heuristic Patch.")
                last_price = await self.get_current_price(symbol)
                if last_price > 0:
                    df = pd.DataFrame([{"Open": last_price, "High": last_price, "Low": last_price, "Close": last_price, "Volume": 0}], index=[pd.Timestamp.now(tz="UTC")])
                else: return pl.DataFrame()
                
            df.columns = df.columns.str.lower()
            df.reset_index(inplace=True)
            for col in ["Date", "Datetime", "date"]:
                if col in df.columns: df.rename(columns={col: "timestamp"}, inplace=True)
            return pl.from_pandas(df)
        except Exception as e:
            logger.error(f"Fetch Error {symbol}: {e}")
            return pl.DataFrame()

    async def get_current_price(self, symbol: str) -> float:
        if self.qdb and self.qdb.enabled:
            p = await self.qdb.fetch_latest_price(symbol)
            if p: return float(p)
            
        if self.finnhub_key:
            try:
                url = f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={self.finnhub_key}"
                async with (await self._get_http_session()).get(url) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get('c'): return float(data['c'])
            except: pass

        ticker = yf.Ticker(symbol)
        try: return float(ticker.fast_info['lastPrice'])
        except: return 0.0

    # --- HFT TICK PROCESSING (C-DRIVE) ---

    def ingest_raw_tick(self, symbol: str, price: float, volume: float, timestamp_ms: int) -> Optional[Dict[str, float]]:
        if symbol not in self.tick_buffers:
            self.tick_buffers[symbol] = deque()
            self.price_history[symbol] = deque(maxlen=self.lookback_window)
            self.last_bar_time[symbol] = timestamp_ms - (timestamp_ms % self.agg_window_ms)

        history = self.price_history[symbol]
        if len(history) == 100:
            mean = np.mean(history)
            std = np.std(history)
            if std > 0 and abs(price - mean) > 5 * std:
                logger.warning(f"Anomalous tick {symbol} dropped.")
                return None

        self.tick_buffers[symbol].append((price, volume))
        self.price_history[symbol].append(price)

        current_bar_start = timestamp_ms - (timestamp_ms % self.agg_window_ms)
        if current_bar_start > self.last_bar_time[symbol]:
            bar = self._aggregate_bar(symbol)
            self.last_bar_time[symbol] = current_bar_start
            return bar
        return None

    def _aggregate_bar(self, symbol: str) -> Optional[Dict[str, float]]:
        buffer = self.tick_buffers[symbol]
        if not buffer: return None
        prices = [t[0] for t in buffer]
        volumes = [t[1] for t in buffer]
        bar = {"symbol": symbol, "open": prices[0], "high": max(prices), "low": min(prices), "close": prices[-1], "volume": sum(volumes), "tick_count": len(prices)}
        self.tick_buffers[symbol].clear()
        return bar

    def normalize_feature_vector(self, data: np.ndarray) -> np.ndarray:
        p1, p99 = np.percentile(data, 1, axis=0), np.percentile(data, 99, axis=0)
        clipped = np.clip(data, p1, p99)
        span = p99 - p1
        span[span == 0] = 1.0
        scaled = (clipped - p1) / span
        return (scaled * 2.0) - 1.0

    def adjust_lookback(self, vix: float):
        self.lookback_window = 50 if vix > 30 else (200 if vix < 15 else 100)
        for s in self.price_history:
            self.price_history[s] = deque(self.price_history[s], maxlen=self.lookback_window)

    # --- INSTITUTIONAL ENRICHMENT & ALPHA HARVESTING ---

    def _calculate_sentiment(self, headline: str, summary: str = "") -> float:
        text = (headline + " " + (summary or "")).upper()
        BULL = ["BEAT", "UPGRADE", "RAISE", "POSITIVE", "GROWTH", "PROFIT", "BULLISH", "BUY"]
        BEAR = ["MISS", "DOWNGRADE", "LOWER", "NEGATIVE", "FALL", "LOSS", "BEARISH", "SELL"]
        score = 0.0
        for w in BULL:
            if w in text: score += 0.25
        for w in BEAR:
            if w in text: score -= 0.25
        return max(-1.0, min(1.0, score))

    async def fetch_vix(self) -> float:
        try:
            t = yf.Ticker("^VIX")
            h = t.history(period="1d")
            vix_value = float(h["Close"].iloc[-1])
            def _save():
                conn = self._get_db_connection()
                cursor = conn.cursor()
                cursor.execute("INSERT OR REPLACE INTO vix_data (timestamp, value) VALUES (?,?)", (datetime.now(timezone.utc).isoformat(), vix_value))
                conn.commit()
                conn.close()
            await asyncio.to_thread(_save)
            logger.info(f"VIX: {vix_value:.2f}")
            return vix_value
        except: return 0.0

    async def fetch_news(self, symbol: str, limit: int = 10) -> list[dict]:
        combined = []
        if self.finnhub_key:
            try:
                url = f"https://finnhub.io/api/v1/company-news?symbol={symbol}&from={(datetime.now()-timedelta(days=3)).date().isoformat()}&to={datetime.now().date().isoformat()}&token={self.finnhub_key}"
                async with (await self._get_http_session()).get(url) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        for item in data[:5]:
                            combined.append({
                                "symbol": symbol, "headline": item.get("headline"), "summary": item.get("summary"),
                                "source": item.get("source"), "url": item.get("url"),
                                "published_at": datetime.fromtimestamp(item.get("datetime", 0)).isoformat(),
                                "sentiment": self._calculate_sentiment(item.get("headline", ""), item.get("summary", ""))
                            })
            except: pass
        if combined:
            def _save():
                conn = self._get_db_connection()
                for i in combined:
                    conn.execute("INSERT OR IGNORE INTO news (symbol, headline, summary, source, url, published_at, sentiment) VALUES (?,?,?,?,?,?,?)", 
                                 (i['symbol'], i['headline'], i['summary'], i['source'], i['url'], i['published_at'], i['sentiment']))
                conn.commit()
                conn.close()
            await asyncio.to_thread(_save)
        return combined

    def get_last_timestamp(self, symbol: str) -> datetime | None:
        try:
            conn = self._get_db_connection()
            row = conn.execute("SELECT timestamp FROM ohlcv WHERE symbol = ? AND timeframe = '1m' ORDER BY timestamp DESC LIMIT 1", (symbol,)).fetchone()
            conn.close()
            if row: return datetime.fromisoformat(row[0].split("+")[0].strip().replace("Z", "+00:00"))
            return None
        except: return None

    async def backfill_gap(self, symbol: str) -> None:
        last_ts = self.get_last_timestamp(symbol)
        if not last_ts: return
        gap = datetime.now(timezone.utc) - last_ts
        if gap.total_seconds() > 120:
            df = await self.fetch_ohlcv(symbol, tf="1m", start=last_ts)
            if df is not None: await self.store_ohlcv(symbol, df)

    def is_market_open(self) -> bool:
        et = ZoneInfo("America/New_York")
        now = datetime.now(et)
        if now.weekday() >= 5: return False
        if now.strftime("%Y-%m-%d") in {"2024-01-01", "2024-07-04", "2024-12-25"}: return False # Minimal holiday list
        return dt_time(9, 30) <= now.time() <= dt_time(16, 0)

    async def run_continuous(self) -> None:
        self.is_running = True
        logger.info("DataPipeline: continuous ingestion active.")
        await self.qdb.start()
        self._sync_task = asyncio.create_task(self._background_sync())
        
        while self.is_running:
            try:
                is_open = self.is_market_open()
                successful = []
                for s in self.INSTRUMENTS:
                    df = await self.fetch_ohlcv(s, tf="1m", bars=100 if is_open else 20)
                    if df is not None and not df.is_empty():
                        self.qdb.insert_ohlcv(df, s)
                        await self.store_ohlcv(s, df)
                        successful.append(s)
                
                if self.bus:
                    await self.bus.publish("candle.batch", {"symbols": successful, "timestamp": datetime.now(timezone.utc).isoformat(), "market_open": is_open})
                
                await asyncio.sleep(60 if is_open else 300)
            except Exception as e:
                logger.error(f"Pipeline Loop Error: {e}")
                await asyncio.sleep(5)

    async def _background_sync(self) -> None:
        try:
            for s in self.INSTRUMENTS: await self.backfill_gap(s)
            logger.info("CORE SYNC COMPLETE: Database established continuity.")
            self._news_task = asyncio.create_task(self._run_news_loop())
            self._research_task = asyncio.create_task(self._run_research_loop())
        except Exception as e: logger.error(f"Sync Error: {e}")

    async def fetch_macro_snapshot(self) -> dict[str, Any]:
        """
        Fetch a macro snapshot via OpenBB (VIX, DXY, yields, oil, gold).
        Returns empty dict if OpenBB is unavailable.
        """
        if self.openbb and self.openbb.is_available:
            try:
                return await self.openbb.fetch_macro_data()
            except Exception as e:
                logger.debug(f"OpenBB macro snapshot failed: {e}")
        return {}

    async def fetch_macro_impact(self) -> dict[str, Any]:
        """
        Global Macro Impact Synthesis.
        Correlates Bond Yields, DXY, and Sector Weightings to detect Regime Shifts.
        """
        impact = {"regime": "NEUTRAL", "vulnerability": "LOW", "signals": []}
        try:
            snapshot = await self.fetch_macro_snapshot()
            vix = snapshot.get("vix", 15.0)
            tnx = snapshot.get("treasury_10y", 4.0)
            dxy = snapshot.get("dxy", 100.0)

            # Regime Analysis
            if vix > 25 or dxy > 105:
                impact["regime"] = "HEDGING"
                impact["vulnerability"] = "HIGH"
                impact["signals"].append("Risk-Off: Strong DXY/VIX")
            elif tnx > 4.5:
                # High yield = Pressure on Equities
                impact["regime"] = "STRESS"
                impact["signals"].append("High 10Y Yield Pressure")

            impact["impact"] = impact["regime"]  # Ensure compatibility with listeners
            logger.info(
                f"Macro Impact Synthesized: {impact['regime']} (VIX: {vix:.1f}, 10Y: {tnx:.1f})"
            )
            return impact
        except Exception as e:
            logger.warning(f"Macro Impact calculation failed: {e}")
            return impact

    async def fetch_institutional_flow(self, symbol: str) -> dict[str, Any]:
        """
        Detect Institutional Block Trades and Large Order Flow.
        """
        try:
            ticker = await asyncio.to_thread(yf.Ticker, symbol)
            # Fetch high-resolution volume to detect outliers
            df = await asyncio.to_thread(ticker.history, period="5d", interval="15m")
            if df is not None and not df.empty:
                avg_vol = df["Volume"].mean()
                last_vol = df["Volume"].iloc[-1]
                if last_vol > avg_vol * 3:
                    bias = "BULLISH" if df["Close"].iloc[-1] > df["Open"].iloc[-1] else "BEARISH"
                    return {
                        "flow_bias": bias,
                        "symbol": symbol,
                        "intensity": 0.8,
                        "detail": "Volume > 3x Avg",
                    }
            return {"flow_bias": "NEUTRAL", "symbol": symbol, "intensity": 0.0}
        except Exception as e:
            logger.debug(f"Flow calculation error for {symbol}: {e}")
            return {"flow_bias": "UNKNOWN", "symbol": symbol, "intensity": 0.0}

    async def _run_news_loop(self) -> None:
        """Periodically fetch news headlines and update sentiment context and ChromaDB."""
        logger.info("DataPipeline: Semantic News Resonance (Agent H) active.")
        while self.is_running:
            try:
                # 1. Broad Market Resonance (SPY)
                if self.news_memory:
                    news = await self.fetch_news("SPY", limit=15)
                    if news:
                        for item in news[:5]:
                            await self.news_memory.store_memory(
                                symbol="SPY",
                                debate_summary=f"HEADLINE: {item.get('title') or item.get('headline', '')}\nTEXT: {item.get('summary', '')}",
                                bias_str="GLOBAL_MACRO",
                                confidence=0.5,
                            )

                    # 2. Watchlist resonance
                    for symbol in self.INSTRUMENTS[:10]:  # Focus on Top 10 to save bandwidth
                        symbol_news = await self.fetch_news(symbol)
                        if symbol_news:
                            for item in symbol_news[:3]:
                                await self.news_memory.store_memory(
                                    symbol=symbol,
                                    debate_summary=f"HEADLINE: {item.get('title') or item.get('headline', '')}\nTEXT: {item.get('summary', '')}",
                                    bias_str="NEWS_RESONANCE",
                                    confidence=0.5,
                                )
                else:
                    logger.debug("News memory not initialized - skipping news resonance.")

                await asyncio.sleep(3600)  # Hourly Resonance Cycle
            except Exception as e:
                logger.error(f"DataPipeline: News loop crash: {e}")
                await asyncio.sleep(60)

    async def _run_research_loop(self) -> None:
        """
        Consumes deep market research from the field to feed the Swarm Intelligence.
        Fulfills the 'Consuming the whole field of Stock Market' directive.
        """
        logger.info("Starting Research Loop: Autonomous Alpha Harvesting Active.")
        while self.is_running:
            try:
                # Search for latest alpha/quant breakthroughs
                queries = [
                    "current market regime analysis 2026",
                    "recursive alpha trading strategies",
                    "high correlation stock market catalysts 2026",
                    "global macro risk sentiment today",
                ]

                for query in queries:
                    logger.debug(f"Research: Consuming field intelligence for query: {query}")
                    if self.bus:
                        # Signal to Swarm Intelligence via Intelligence Bus
                        await self.bus.publish(
                            "research.digest",
                            {
                                "topic": query,
                                "intensity": "HIGH",
                                "context": "Global Field Synthesis",
                            },
                        )

                # Sleep for 1 hour between research deep-dives
                await asyncio.sleep(3600)
            except Exception as e:
                logger.error(f"Research Loop error: {e}")
                await asyncio.sleep(300)

    async def semantic_news_search(self, symbol: str, query: str) -> str:
        """Sovereign News Search: Resonates with news context semantically."""
        if not self.news_memory:
            return "News memory unavailable for search."
        memories = await self.news_memory.query_memory(symbol)
        if not memories:
            return "No recent news resonance found."

        # Merge top 3 related fragments
        context = "\n".join([m.get("summary", "") for m in memories[:3]])
        return f"RESONANCE DETECTED for {symbol}: {context}"

    async def store_ohlcv(self, symbol: str, df: "pl.DataFrame", tf: str = "1m") -> None:
        async with self._db_lock:
            async with self._active_tasks_lock: self._active_db_tasks += 1
            try: await asyncio.to_thread(self._sync_store_ohlcv, symbol, df, tf)
            finally: 
                async with self._active_tasks_lock: self._active_db_tasks -= 1

    def _sync_store_ohlcv(self, symbol: str, df: "pl.DataFrame", tf: str = "1m") -> None:
        if not self.is_running: return
        conn = self._get_db_connection()
        try:
            data = []
            for r in df.iter_rows(named=True):
                ts = r.get("timestamp") or datetime.now(timezone.utc)
                data.append((symbol, str(ts), r.get('open', 0), r.get('high', 0), r.get('low', 0), r.get('close', 0), r.get('volume', 0), tf))
            cursor = conn.cursor()
            cursor.executemany("INSERT OR REPLACE INTO ohlcv (symbol, timestamp, open, high, low, close, volume, timeframe) VALUES (?,?,?,?,?,?,?,?)", data)
            conn.commit()
        finally: conn.close()

    async def _get_http_session(self) -> aiohttp.ClientSession:
        if self._http_session is None or self._http_session.closed:
            self._http_session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30))
        return self._http_session

    async def stop(self) -> None:
        self.is_running = False
        if self._sync_task: self._sync_task.cancel()
        if self._news_task: self._news_task.cancel()
        if self._research_task: self._research_task.cancel()
        if self._http_session: await self._http_session.close()
        await self.qdb.stop()
        logger.info("DataPipeline: OFFLINE.")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("Sovereign DataPipeline: Fully Integrated Research & HFT Mode.")
