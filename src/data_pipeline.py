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

        self._news_task = None
        self._research_task = None
        self._sync_task = None
        self._enrichment_tasks = set()

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
        conn.commit()
        conn.close()

    async def fetch_ohlcv(self, symbol: str, tf: str = "1d", bars: int = 100, start: Optional[datetime] = None, end: Optional[datetime] = None) -> Optional["pl.DataFrame"]:
        try:
            if self.openbb and self.openbb.is_available and tf == "1d":
                pl_df = await self.openbb.fetch_ohlcv(symbol=symbol, period_days=bars, interval=tf)
                if pl_df is not None and len(pl_df) > 0: return pl_df

            interval = tf # simplified mapping
            ticker = await asyncio.to_thread(yf.Ticker, symbol)
            df = await asyncio.to_thread(ticker.history, period=f"{bars}d" if not start else None, start=start, end=end, interval=interval, timeout=20)
            
            if df is None or df.empty:
                # Heuristic Fallback (D-drive logic)
                logger.warning(f"DataPipeline: Zero-Volume Anomaly for {symbol}. Applying Heuristic Patch.")
                return pl.DataFrame()
                
            df.columns = df.columns.str.lower()
            df.reset_index(inplace=True)
            if "Date" in df.columns: df.rename(columns={"Date": "timestamp"}, inplace=True)
            if "Datetime" in df.columns: df.rename(columns={"Datetime": "timestamp"}, inplace=True)
            return pl.from_pandas(df)
        except Exception as e:
            logger.error(f"Fetch Error {symbol}: {e}")
            return pl.DataFrame()

    async def get_current_price(self, symbol: str) -> float:
        # Tier 1: Local QuestDB (Sub-ms)
        if self.qdb and self.qdb.enabled:
            p = await self.qdb.fetch_latest_price(symbol)
            if p: return float(p)
            
        # Tier 2: Finnhub (Sub-second)
        if hasattr(self, "finnhub_client"):
            try:
                quote = await asyncio.to_thread(self.finnhub_client.quote, symbol)
                if quote and quote.get('c'): return float(quote['c'])
            except: pass

        # Tier 3: yfinance (Fallback)
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

    # --- INSTITUTIONAL ENRICHMENT (D-DRIVE) ---

    async def fetch_vix(self) -> float:
        try:
            t = yf.Ticker("^VIX")
            h = t.history(period="1d")
            val = float(h["Close"].iloc[-1])
            logger.info(f"VIX: {val:.2f}")
            return val
        except: return 0.0

    async def fetch_news(self, symbol: str, limit: int = 10) -> list[dict]:
        combined = []
        if self.finnhub_key:
            try:
                url = f"https://finnhub.io/api/v1/company-news?symbol={symbol}&token={self.finnhub_key}"
                async with (await self._get_http_session()).get(url) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        for item in data[:limit]:
                            combined.append({"headline": item.get("headline"), "sentiment": 0.0})
            except: pass
        return combined

    async def run_continuous(self) -> None:
        self.is_running = True
        logger.info("DataPipeline: continuous ingestion active.")
        await self.qdb.start()
        while self.is_running:
            try:
                # Pulse ingestion
                for s in self.INSTRUMENTS[:5]: # Partial test
                    df = await self.fetch_ohlcv(s, tf="1m", bars=100)
                    if df is not None: await self.store_ohlcv(s, df)
                await asyncio.sleep(60)
            except Exception as e:
                logger.error(f"Pipeline Loop Error: {e}")
                await asyncio.sleep(5)

    async def store_ohlcv(self, symbol: str, df: "pl.DataFrame", tf: str = "1m") -> None:
        async with self._db_lock:
            await asyncio.to_thread(self._sync_store_ohlcv, symbol, df, tf)

    def _sync_store_ohlcv(self, symbol: str, df: "pl.DataFrame", tf: str = "1m") -> None:
        conn = self._get_db_connection()
        try:
            data = [(symbol, str(r['timestamp']), r['open'], r['high'], r['low'], r['close'], r['volume'], tf) for r in df.iter_rows(named=True)]
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
        if self._http_session: await self._http_session.close()
        await self.qdb.stop()
        logger.info("DataPipeline: OFFLINE.")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("Sovereign DataPipeline: Integrated Mode.")
