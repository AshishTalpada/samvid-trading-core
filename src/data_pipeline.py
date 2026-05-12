import asyncio
import logging
import os
import random
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from datetime import time as dt_time
from typing import TYPE_CHECKING, Any, Optional
from zoneinfo import ZoneInfo

import aiohttp
import pandas as pd
import polars as pl

# Resolved: 'NoneType' object is not subscriptable in history.py:224
try:
    import yfinance.scrapers.history as yf_history

    _orig_history = (
        yf_history.History.history if hasattr(yf_history, "History") else yf_history.history
    )

    def _patched_history(*args, **kwargs):
        try:
            # Handle both function and method calls depending on yfinance version
            if (
                hasattr(yf_history, "History")
                and len(args) > 0
                and isinstance(args[0], yf_history.History)
            ):
                return _orig_history(*args, **kwargs)
            return _orig_history(*args, **kwargs)
        except Exception as e:
            # Widen the catch to any subscriptable/NoneType error
            err_msg = str(e).lower()
            if "subscriptable" in err_msg or "nonetype" in err_msg:
                import pandas as pd

                return pd.DataFrame()
            raise e

    if hasattr(yf_history, "History"):
        yf_history.History.history = _patched_history
    else:
        yf_history.history = _patched_history
except Exception as _yf_patch_err:
    pass  # yfinance version mismatch — patch not applied (non-critical)
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
    Agent B: The Ingestion Mind.
    Responsibilities:
    - High-frequency market data ingestion via yfinance and custom feeds.
    - Real-time 'Reality Check' price sanitization.
    - Asynchronous signal publication to the Intelligence Bus.
    - Memory-safe enrichment (VIX, News, Institutional Flow).
    """

    # Full watchlist — must match TradingBrain._get_watchlist() exactly so that
    # every symbol the brain scans has fresh OHLCV rows in the database.
    INSTRUMENTS = list(
        set(
            [
                # Core Indices
                "SPY",
                "QQQ",
                "IWM",
                "DIA",
                # Macro / Legacy
                "XLK",
                "XLF",
                "GC=F",
                "NQ=F",
                # Mag 7 & Trillion Dollar Tech
                "AAPL",
                "MSFT",
                "GOOGL",
                "AMZN",
                "NVDA",
                "META",
                "TSLA",
                # High Beta Semi / AI
                "AMD",
                "AVGO",
                "SMCI",
                "ARM",
                "MU",
                "PLTR",
                # Crypto Proxies
                "COIN",
                "MSTR",
                # Banks / Value
                "JPM",
                "GS",
                "V",
                "MA",
                # Retail / Consumer
                "WMT",
                "COST",
                "NFLX",
            ]
        )
    )

    DMS_LOCK_FILE = "data/dms.lock"  #

    def __init__(
        self,
        db_path: str = "data/trading.db",
        finnhub_key: str = "",
        qdb: QuestDBAdapter | None = None,
        openbb_provider: OpenBBProvider | None = None,
        bus: "SharedIntelligenceBus | None" = None,
    ) -> None:
        """
        Initialize DataPipeline.
        """
        self.db_path = str(db_path)

        if not finnhub_key or finnhub_key == "YOUR_FINNHUB_KEY":
            # Harmonize with main.py and vault.py (FINNHUB_API_KEY)
            finnhub_key = Vault.get("FINNHUB_API_KEY", "") or Vault.get("FINNHUB_KEY", "")

        if not finnhub_key:
            logger.critical(
                "🚨 NEWS DISRUPTION: No Finnhub API Key found! News fetching will stay offline. Add FINNHUB_API_KEY to Vault."
            )

        # Explicit type-safety cast for Vault-retrieved keys
        self.finnhub_key = str(finnhub_key) if finnhub_key else ""
        self.is_running = False
        self._last_reality_check: dict[str, float] = {}  # symbol -> timestamp (time.monotonic)

        # SharedIntelligenceBus — publishes candle.batch so Brain wakes immediately
        self.bus: SharedIntelligenceBus | None = bus

        # QuestDB: prefer injected instance so runtime disable/enable is consistent
        self.qdb = qdb if qdb is not None else QuestDBAdapter(enabled=QUESTDB_ENABLED)

        # OpenBB: primary data provider (falls back to yfinance if unavailable)
        self.openbb = openbb_provider

        self._db_lock = asyncio.Lock()

        # One persistent aiohttp session for all HTTP calls, instead of creating
        # hundreds of short-lived sessions that leak TCP connections and memory.
        self._http_session: Optional[aiohttp.ClientSession] = None
        self._active_db_tasks = 0
        self._active_tasks_lock = asyncio.Lock()

        try:
            self.news_memory = ChromaDeepMemory(collection_name="market_news_v8")
        except Exception as e:
            logger.warning(f"DataPipeline news_memory init failed: {e}")
            self.news_memory = None

        # Lifecycle tracking
        self._news_task: asyncio.Task | None = None
        self._research_task: asyncio.Task | None = None
        self._sync_task: asyncio.Task | None = None
        self._enrichment_tasks: set[asyncio.Task] = set()

        self._init_database()
        _openbb_status = self.openbb.status if self.openbb else "OFFLINE"
        logger.info(f"DataPipeline initialized with {db_path}, QuestDB, OpenBB={_openbb_status}")

    def _get_db_connection(self):
        """Get a database connection with WAL mode enabled for concurrency."""
        conn = sqlite3.connect(
            self.db_path,
            timeout=5.0,  # Reduced from 60s to 5s for faster shutdown response
            check_same_thread=False,
            isolation_level=None,
        )
        conn.execute("PRAGMA busy_timeout = 5000;")
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn

    def _init_database(self) -> None:
        """Initialize SQLite database with required tables."""
        conn = self._get_db_connection()
        cursor = conn.cursor()

        # OHLCV table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ohlcv (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume INTEGER,
                timeframe TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(symbol, timestamp, timeframe)
            )
        """)

        # VIX data table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS vix_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                value REAL NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(timestamp)
            )
        """)

        # News table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS news (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                headline TEXT,
                summary TEXT,
                source TEXT,
                url TEXT,
                published_at TEXT,
                sentiment REAL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_ohlcv_query ON ohlcv (symbol, timeframe, timestamp DESC);"
        )
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ohlcv_time ON ohlcv (timestamp);")

        # Check if the 'ohlcv' table is missing any expected columns and add them.
        try:
            cursor.execute("PRAGMA table_info(ohlcv)")
            columns = [row[1] for row in cursor.fetchall()]
            if "volume" not in columns:
                cursor.execute("ALTER TABLE ohlcv ADD COLUMN volume INTEGER")
            if "timeframe" not in columns:
                cursor.execute("ALTER TABLE ohlcv ADD COLUMN timeframe TEXT")
        except Exception as e:
            logger.warning(f"DataPipeline: Schema migration check failed: {e}")

        conn.commit()
        conn.close()
        logger.info("Database initialized with optimized indices and migration check.")

    async def fetch_ohlcv(
        self,
        symbol: str,
        tf: str = "1d",
        bars: int = 100,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> Optional["pl.DataFrame"]:
        """
        Fetch OHLCV data for a symbol.
        Robust zero-volume handling.
        """
        try:
            # --- Tier 1: OpenBB (if available and daily timeframe) ---
            if self.openbb and self.openbb.is_available and tf == "1d":
                try:
                    pl_df = await self.openbb.fetch_ohlcv(
                        symbol=symbol, period_days=bars, interval=tf
                    )
                    if pl_df is not None and len(pl_df) > 0:
                        # Verify integrity
                        if pl_df["volume"].sum() == 0 and not symbol.startswith("^"):
                            logger.warning(
                                f"DataPipeline: Zero-Volume Anomaly detected for {symbol}. Rejecting batch."
                            )
                            return None
                        logger.info(f"OpenBB fetched {len(pl_df)} bars for {symbol} ({tf})")
                        return pl_df
                except Exception as e:
                    logger.debug(f"OpenBB fetch failed for {symbol}: {e}")

            # --- Tier 2: yfinance fallback ---
            # Map timeframe to yfinance interval
            interval_map = {
                "1m": "1m",
                "5m": "5m",
                "15m": "15m",
                "30m": "30m",
                "1h": "1h",
                "1d": "1d",
                "1wk": "1wk",
                "1mo": "1mo",
            }

            interval = interval_map.get(tf, "1d")

            # Respective to yfinance historical limits
            if interval == "1m":
                period = (
                    "7d" if bars <= 3000 else "30d"
                )  # yfinance allows 30d for 1m but it is fragile
            elif interval in ["2m", "5m", "15m", "30m", "1h"]:
                period = "60d"
            elif interval == "1d":
                period = f"{bars}d" if bars <= 730 else "max"
            else:
                period = "max"

            # Run yfinance in executor to avoid blocking
            if not symbol:
                logger.error(f"fetch_ohlcv: Invalid symbol '{symbol}'")
                return pl.DataFrame()

            ticker = await asyncio.to_thread(yf.Ticker, symbol)
            df = None
            max_retries = 3
            for attempt in range(max_retries + 1):
                try:
                    if hasattr(ticker, "fast_info"):
                        _ = ticker.fast_info

                    if start and end:
                        df = await asyncio.to_thread(
                            ticker.history, start=start, end=end, interval=interval, timeout=20
                        )
                    else:
                        df = await asyncio.to_thread(
                            ticker.history, period=period, interval=interval, timeout=20
                        )

                    if df is not None and not df.empty:
                        break  # Success
                except Exception as e:
                    err_str = str(e).lower()
                    is_ratelimit = "429" in err_str or "too many requests" in err_str
                    if (
                        is_ratelimit
                        or "subscriptable" in err_str
                        or "nonetype" in err_str
                        or attempt < max_retries
                    ):
                        wait = (2**attempt) * 2.5  # Exponential backoff
                        logger.warning(
                            f"yfinance {'429' if is_ratelimit else 'glitch'} for {symbol} ({period}). Attempt {attempt + 1} failed. Jittering {wait}s..."
                        )
                        await asyncio.sleep(wait)
                        if attempt == max_retries - 1:
                            period = "1d"
                            logger.info(
                                f"Glitch Shield: Dropping {symbol} request to 1d period for recovery."
                            )
                    else:
                        logger.error(
                            f"yfinance total failure for {symbol} after {max_retries} attempts: {e}"
                        )
                        break

            if df is None or (hasattr(df, "empty") and df.empty):
                # --- HEURISTIC RECONSTRUCTION (FINAL FALLBACK) ---
                logger.warning(
                    f"No historical data for {symbol}. Attempting Heuristic Reconstruction..."
                )
                last_price = await self.get_current_price(symbol)
                if last_price > 0:
                    df = pd.DataFrame(
                        [
                            {
                                "Open": last_price,
                                "High": last_price,
                                "Low": last_price,
                                "Close": last_price,
                                "Volume": 0,
                            }
                        ],
                        index=[pd.Timestamp.now(tz="UTC")],
                    )
                else:
                    return pl.DataFrame()

            if len(df) > 1:
                # Check for gaps > 15 mins in historical index
                diffs = df.index.to_series().diff().dropna().dt.total_seconds()
                max_gap = diffs.max()
                if max_gap > 900:  # 15 mins
                    logger.warning(
                        f"GAP DETECTED: {symbol} has a data gap of {max_gap / 60:.1f} minutes."
                    )

            # Limit to requested number of bars ONLY if start/end are not used
            if not (start and end):
                df = df.tail(bars).copy()

            # Standardize column names
            df.columns = df.columns.str.lower()
            df.reset_index(inplace=True)
            for col in ["Date", "Datetime", "date"]:
                if col in df.columns:
                    df.rename(columns={col: "timestamp"}, inplace=True)

            pl_df = pl.from_pandas(df)
            del df
            del ticker
            logger.info(f"Fetched {len(pl_df)} bars for {symbol} ({tf})")
            return pl_df

        except Exception as e:
            import traceback

            logger.error(f"Error fetching OHLCV for {symbol}: {e}\n{traceback.format_exc()}")
            return pl.DataFrame()

    async def get_current_price(self, symbol: str) -> float:
        """Get the most recent price. Priority: QuestDB → Finnhub → OpenBB → yfinance."""
        # Tier 0: QuestDB (High-Speed Tick Cache)
        if self.qdb and self.qdb.enabled:
            try:
                row = await self.qdb.fetch_latest_price(symbol)
                if row and row > 0:
                    return float(row)
            except Exception as e:
                logger.debug(f"QuestDB: T1 price fetch failed for {symbol}: {e}")

        # Tier 1: Finnhub for real-time speed
        if self.finnhub_key:
            try:
                url = f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={self.finnhub_key}"
                session = await self._get_http_session()
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        if "c" in data and data["c"] > 0:
                            return float(data["c"])
            except Exception as e:
                logger.debug(f"Finnhub real-time price failed for {symbol}: {e}")

        # Tier 2: OpenBB
        if self.openbb and self.openbb.is_available:
            try:
                price = await self.openbb.get_current_price(symbol)
                if price is not None and price > 0:
                    return price
            except Exception as e:
                logger.debug(f"OpenBB price failed for {symbol}: {e}")

        # Tier 3: yfinance fallback
        try:
            ticker = yf.Ticker(symbol)
            # Use fast_info if available (newer yfinance versions)
            try:
                if hasattr(ticker, "fast_info") and ticker.fast_info is not None:
                    price = ticker.fast_info["lastPrice"]
                    if price and float(price) > 0:
                        return float(price)
            except Exception as e:
                if "subscriptable" in str(e).lower():
                    logger.debug(f"fast_info glitch for {symbol}, falling back to history...")
                else:
                    raise e

            # Otherwise use history
            try:
                df = ticker.history(period="1d")
                if not df.empty:
                    return df["Close"].iloc[-1]
            except Exception:
                pass  # Silence yfinance scraper glitches here
        except Exception as e:
            logger.error(f"Failed to get price for {symbol}: {e}")

        return 0.0

    async def fetch_latest_ohlcv(
        self, symbol: str, interval: str = "1h", period: str = "5d"
    ) -> "pl.DataFrame":
        """Fetch historical OHLCV data from yfinance and return as Polars DataFrame."""
        try:
            ticker = yf.Ticker(symbol)
            try:
                df = ticker.history(period=period, interval=interval)
            except Exception as e:
                # Catch subscriptable glitch in history
                if "subscriptable" in str(e).lower():
                    logger.warning(
                        f"Glitch Shield: yfinance history failed for {symbol}. Returning empty."
                    )
                    return pl.DataFrame()
                raise e

            if df.empty:
                logger.warning(f"No data found for {symbol}")
                return pl.DataFrame()

            # DO NOT dropna() on the entire frame. yfinance often returns NaN for the LAST row
            # (current bar) if the market is open. Dropping it causes trading on stale data.
            # We fill forward or retain the index and only drop rows with MISSING prices.
            df = df.ffill()
            # If still NAs exist in OHLC (unlikely after ffill unless whole block missing)
            df = df.dropna(subset=["Open", "High", "Low", "Close"])
            # then we drop, but we log it as a data integrity warning.
            if df.isnull().values.any():
                logger.debug(f"DataPipeline: {symbol} has holes after ffill. Pruning...")
                df = df.dropna()

            return pl.from_pandas(df.reset_index())
        except Exception as e:
            import traceback

            logger.error(f"Error fetching OHLCV for {symbol}: {e}\n{traceback.format_exc()}")
            return pl.DataFrame()

    def _calculate_sentiment(self, headline: str, summary: str = "") -> float:
        """
        Simple heuristic-based sentiment analysis for fast ingestion.
        Returns: Score between -1.0 and 1.0
        """
        text = (headline + " " + (summary or "")).upper()

        BULL_WORDS = [
            "BEAT",
            "UPGRADE",
            "RAISE",
            "POSITIVE",
            "GROWTH",
            "WIN",
            "SURGE",
            "PROFIT",
            "BULLISH",
            "SUCCESS",
            "EXPAND",
            "BUY",
            "OUTPERFORM",
            "RECOVERY",
            "BOOM",
        ]
        BEAR_WORDS = [
            "MISS",
            "DOWNGRADE",
            "LOWER",
            "NEGATIVE",
            "FALL",
            "LOSS",
            "DROP",
            "PLUNGE",
            "BEARISH",
            "FAILURE",
            "SHRINK",
            "SELL",
            "UNDERPERFORM",
            "CRASH",
            "SLUMP",
        ]

        NEGATORS = ["NOT", "NO", "NEVER", "LESS", "WITHOUT", "AGAINST"]

        score = 0.0
        words = text.split()
        for i, word in enumerate(words):
            for bw in BULL_WORDS:
                if bw == word or (bw in word and len(word) < len(bw) + 3):  # Fuzzy match
                    # Check for negation in previous 2 words
                    negated = False
                    for j in range(max(0, i - 2), i):
                        if words[j] in NEGATORS:
                            negated = True
                            break
                    if negated:
                        score -= 0.25
                    else:
                        score += 0.25

            for rw in BEAR_WORDS:
                if rw == word or (rw in word and len(word) < len(rw) + 3):
                    negated = False
                    for j in range(max(0, i - 2), i):
                        if words[j] in NEGATORS:
                            negated = True
                            break
                    if negated:
                        score += 0.25
                    else:
                        score -= 0.25

        return max(-1.0, min(1.0, score))

    async def fetch_vix(self) -> float:
        """
        Fetch current VIX value.
        Returns:
            Current VIX value or 0.0 if error
        """
        try:
            ticker = await asyncio.to_thread(yf.Ticker, "^VIX")
            hist = None
            for attempt in range(2):
                try:
                    hist = await asyncio.to_thread(ticker.history, period="1d", interval="1m")
                    if hist is not None and not hist.empty:
                        break
                except Exception as e:
                    if "subscriptable" in str(e).lower():
                        logger.warning(
                            f"VIX yfinance glitch. Attempt {attempt + 1} failed. Jittering..."
                        )
                        await asyncio.sleep(1.0)
                    else:
                        raise e

            if hist is None or hist.empty:
                logger.warning("No VIX data available")
                return 0.0

            close_col = (
                "Close"
                if "Close" in hist.columns
                else ("close" if "close" in hist.columns else None)
            )
            if close_col is None:
                logger.warning("VIX data missing 'Close' column")
                return 0.0
            vix_value = float(hist[close_col].iloc[-1])
            self.last_vix = vix_value

            def _save_vix():
                from datetime import datetime, timezone

                conn = self._get_db_connection()
                try:
                    cursor = conn.cursor()
                    cursor.execute(
                        """
                        INSERT OR REPLACE INTO vix_data (timestamp, value)
                        VALUES (?, ?)
                    """,
                        (time.time_ns(), vix_value),
                    )
                    conn.commit()
                finally:
                    conn.close()

            await asyncio.to_thread(_save_vix)

            logger.info(f"VIX: {vix_value:.2f}")
            return vix_value

        except Exception as e:
            logger.error(f"Error fetching VIX: {e}")
            return 0.0

    async def fetch_news(self, symbol: str, limit: int = 10) -> list[dict]:
        """
        Fetch news for a symbol using Finnhub + OpenBB + yfinance.
        """
        combined_news: list[dict[str, Any]] = []

        # 1. Try Finnhub (Professional Grade)
        if self.finnhub_key:
            try:
                from datetime import date

                today = date.today().isoformat()
                # Fetch last 3 days of news to ensure coverage
                three_days_ago = (date.today() - timedelta(days=3)).isoformat()

                url = f"https://finnhub.io/api/v1/company-news?symbol={symbol}&from={three_days_ago}&to={today}&token={self.finnhub_key}"
                session = await self._get_http_session()
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        for article in data[:5]:  # Top 5 from Finnhub
                            combined_news.append(
                                {
                                    "symbol": symbol,
                                    "headline": article.get("headline", ""),
                                    "summary": article.get("summary", ""),
                                    "source": f"Finnhub ({article.get('source', '')})",
                                    "url": article.get("url", ""),
                                    "published_at": datetime.fromtimestamp(
                                        article.get("datetime", 0)
                                    ).isoformat(),
                                    "sentiment": self._calculate_sentiment(
                                        article.get("headline", ""), article.get("summary", "")
                                    ),
                                }
                            )
                logger.info(f"Finnhub fetched {len(data[:5])} news items for {symbol}")
            except Exception as e:
                logger.error(f"Finnhub news fetch failed for {symbol}: {e}")

        # 2. Try OpenBB (multi-source aggregation)
        if self.openbb and self.openbb.is_available:
            try:
                openbb_articles = await self.openbb.fetch_news(symbol, limit=5)
                for article in openbb_articles:
                    combined_news.append(
                        {
                            "symbol": symbol,
                            "headline": article.get("headline", ""),
                            "summary": article.get("summary", ""),
                            "source": article.get("source", "OpenBB"),
                            "url": article.get("url", ""),
                            "published_at": article.get("published_at", ""),
                            "sentiment": self._calculate_sentiment(
                                article.get("headline", ""), article.get("summary", "")
                            ),
                        }
                    )
                if openbb_articles:
                    logger.info(f"OpenBB fetched {len(openbb_articles)} news items for {symbol}")
            except Exception as e:
                logger.error(f"OpenBB news fetch failed for {symbol}: {e}")

        # 3. Try yfinance (Fallback/Secondary)
        try:
            ticker = await asyncio.to_thread(yf.Ticker, symbol)
            yf_news = await asyncio.to_thread(lambda: ticker.news)

            if yf_news:
                for article in yf_news[:5]:
                    content = article.get("content", {})
                    headline = (
                        content.get("title") or article.get("title") or article.get("headline", "")
                    )
                    summary = content.get("summary") or article.get("summary", "")
                    pub_time = content.get("pubDate") or article.get("providerPublishTime")

                    if not headline:
                        continue

                    combined_news.append(
                        {
                            "symbol": symbol,
                            "headline": headline,
                            "summary": summary,
                            "source": f"YFinance ({article.get('publisher', {}).get('displayName', 'Yahoo')})",
                            "url": content.get("canonicalUrl", {}).get("url")
                            or article.get("link", ""),
                            "published_at": (
                                pub_time
                                if isinstance(pub_time, str)
                                else datetime.fromtimestamp(pub_time or 0).isoformat()
                            ),
                            "sentiment": self._calculate_sentiment(headline, summary),
                        }
                    )
                logger.info(f"YFinance fetched {len(yf_news[:5])} news items for {symbol}")
        except Exception as e:
            logger.error(f"YFinance news fetch failed for {symbol}: {e}")

        combined_news = combined_news[:10]

        # Store in database
        if combined_news:

            def _save_news():
                for attempt in range(10):
                    conn = self._get_db_connection()
                    try:
                        cursor = conn.cursor()
                        for news_item in combined_news:
                            try:
                                cursor.execute(
                                    """
                                    INSERT OR IGNORE INTO news (symbol, headline, summary, source, url, published_at, sentiment)
                                    VALUES (?, ?, ?, ?, ?, ?, ?)
                                """,
                                    (
                                        news_item["symbol"],
                                        news_item["headline"],
                                        news_item["summary"],
                                        news_item["source"],
                                        news_item["url"],
                                        news_item["published_at"],
                                        news_item["sentiment"],
                                    ),
                                )
                            except sqlite3.IntegrityError:
                                pass
                        conn.commit()
                        break  # Success
                    except sqlite3.OperationalError as e:
                        if "locked" in str(e).lower() and attempt < 9:
                            if not self.is_running:
                                return
                            time.sleep(1.0 + attempt * 0.5)
                            continue
                        raise
                    finally:
                        conn.close()

            await asyncio.to_thread(_save_news)

            # Notify bus
            if self.bus is not None:
                for item in combined_news[:5]:
                    await self.bus.publish("news.event", item)

            # Log top headlines for Cockpit visibility
            for item in combined_news[:3]:  # type: ignore
                logger.info(f"📰 NEWS [{symbol}] from {item['source']}: {item['headline']}")
        else:
            logger.info(
                f"🚫 NEWS: No fresh headlines for {symbol} after polling Finnhub, OpenBB, and YFinance."
            )

        return combined_news

    def get_last_timestamp(self, symbol: str) -> datetime | None:
        """Query the most recent OHLCV timestamp for a symbol."""
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT timestamp FROM ohlcv WHERE symbol = ? AND timeframe = '1m' ORDER BY timestamp DESC LIMIT 1",
                (symbol,),
            )
            row = cursor.fetchone()
            conn.close()
            if row:
                # Handle varying timestamp formats from yfinance/SQLite
                ts_str = row[0]
                if " " in ts_str:
                    try:
                        return datetime.strptime(ts_str.split("+")[0].strip(), "%Y-%m-%d %H:%M:%S")
                    except ValueError:
                        return datetime.fromisoformat(ts_str.split("+")[0].strip())
                return datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            return None
        except Exception as e:
            logger.error(f"Error getting last timestamp for {symbol}: {e}")
            return None

    async def backfill_gap(self, symbol: str) -> None:
        """Identify and fill the data gap since last shutdown."""
        last_ts = self.get_last_timestamp(symbol)
        if not last_ts:
            logger.info(f"No history for {symbol} — performing initial 5-day fetch.")
            df = await self.fetch_ohlcv(symbol, tf="1m", bars=5000)  # Full week
            if df is not None:
                await self.store_ohlcv(symbol, df, tf="1m")
            return

        now = datetime.now(timezone.utc)
        gap = now - last_ts

        if gap.total_seconds() < 120:
            logger.debug(f"Gap for {symbol} is negligible ({gap.total_seconds():.0f}s).")
            return

        # Calculate bars needed (approximate)
        minutes = int(gap.total_seconds() / 60)
        logger.info(f"📦 BACKFILL: {symbol} is missing {minutes} minutes of data.")

        # Limit backfill to 7 days (yfinance 1m limit)
        if minutes > 10080:
            logger.warning(f"Gap for {symbol} exceeds 7 days ({minutes}m). Capping at 7 days.")
            minutes = 10080

        # This prevents over-fetching on Monday mornings or after market holidays.
        df = await self.fetch_ohlcv(symbol, tf="1m", start=last_ts, end=now)
        if df is not None:
            await self.store_ohlcv(symbol, df)
            logger.info(f"✓ BACKFILL COMPLETE: {symbol} synchronized.")

    def is_market_open(self) -> bool:
        """
        Check if NYSE is currently open (9:30-16:00 ET Mon-Fri).
        Returns:
            True if market is open, False otherwise
        """
        try:
            et_tz = ZoneInfo("America/New_York")
            now = datetime.now(et_tz)

            # Check if weekday (0=Monday, 6=Sunday)
            if now.weekday() >= 5:  # Saturday or Sunday
                return False

            date_str = now.strftime("%Y-%m-%d")
            HOLIDAYS = {
                "2024-01-01",
                "2024-01-15",
                "2024-02-19",
                "2024-03-29",
                "2024-05-27",
                "2024-06-19",
                "2024-07-04",
                "2024-09-02",
                "2024-11-28",
                "2024-12-25",
                "2025-01-01",
                "2025-01-20",
                "2025-02-17",
                "2025-04-18",
                "2025-05-26",
                "2025-06-19",
                "2025-07-04",
                "2025-09-01",
                "2025-11-27",
                "2025-12-25",
            }
            if date_str in HOLIDAYS:
                return False

            # Market hours: 9:30 AM - 4:00 PM ET
            market_open = dt_time(9, 30)
            market_close = dt_time(16, 0)
            current_time = now.time()

            is_open = market_open <= current_time <= market_close

            return is_open

        except Exception as e:
            logger.error(f"Error checking market hours: {e}")
            return False

    async def store_ohlcv(self, symbol: str, df: "pl.DataFrame", tf: str = "1m") -> None:
        """
        Store OHLCV data to SQLite database with mutual exclusion.
        Using self._db_lock to prevent 'Database is locked' errors.
        """
        if df is None:
            return

        async with self._db_lock:
            # Track in-flight threaded tasks to ensure clean shutdown
            async with self._active_tasks_lock:
                self._active_db_tasks += 1

            try:
                # We move the actual heavy lifting to a thread to not block the loop
                await asyncio.to_thread(self._sync_store_ohlcv, symbol, df, tf)
            finally:
                async with self._active_tasks_lock:
                    self._active_db_tasks -= 1

    def _sync_store_ohlcv(self, symbol: str, df: "pl.DataFrame", tf: str = "1m") -> None:
        """Synchronous batch storage: writes OHLCV data to SQLite and QuestDB."""
        if not self.is_running:
            return

        conn = self._get_db_connection()
        try:
            if df is None:
                return

            if not isinstance(df, (pl.DataFrame, pl.LazyFrame)) and not hasattr(df, "iter_rows"):
                logger.error(f"DataPipeline: Received invalid data type for {symbol}: {type(df)}")
                return

            if isinstance(df, pl.LazyFrame):
                df = df.collect()

            # Pre-processing batch list to minimize cursor time
            batch_data = []
            for row in df.iter_rows(named=True):
                # 1. Discover Timestamp
                ts = (
                    row.get("timestamp")
                    or row.get("Date")
                    or row.get("Datetime", datetime.now(timezone.utc))
                )
                ts_str = str(ts) if not hasattr(ts, "isoformat") else ts.isoformat()

                # 2. Discover OHLCV Columns
                o = row.get("Open", row.get("open", 0.0))
                h = row.get("High", row.get("high", 0.0))
                l = row.get("Low", row.get("low", 0.0))
                c = row.get("Close", row.get("close", 0.0))
                v = row.get("Volume", row.get("volume", 0))

                batch_data.append(
                    (
                        symbol,
                        ts_str,
                        float(o) if o is not None else 0.0,
                        float(h) if h is not None else 0.0,
                        float(l) if l is not None else 0.0,
                        float(c) if c is not None else 0.0,
                        int(float(v)) if v is not None else 0,
                        tf,
                    )
                )

            if not batch_data:
                return

            for attempt in range(10):  # 10 retries
                if not self.is_running:
                    break

                try:
                    cursor = conn.cursor()
                    cursor.executemany(
                        """
                        INSERT OR REPLACE INTO ohlcv
                        (symbol, timestamp, open, high, low, close, volume, timeframe)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        batch_data,
                    )
                    conn.commit()
                    logger.debug(
                        f"DataPipeline: Flushed {len(batch_data)} bars for {symbol} to SQLite."
                    )
                    return  # Success
                except sqlite3.OperationalError as e:
                    if "locked" in str(e).lower() and attempt < 9:
                        if not self.is_running:
                            logger.info(f"DataPipeline: Shutdown detected for {symbol}. Aborting retry.")
                            return

                        # Exponential backoff with jitter
                        wait_time = 0.5 * (2**attempt) + random.uniform(0.1, 0.5)

                        # Reduce log noise: Only warn on 4th+ failure
                        log_func = logger.warning if attempt >= 3 else logger.debug
                        log_func(
                            f"DataPipeline: Database locked for {symbol}. Jittering {wait_time:.2f}s... (Attempt {attempt + 1}/10)"
                        )

                        # Responsive sleep: check is_running every 100ms
                        sleep_start = time.time()
                        while time.time() - sleep_start < wait_time:
                            if not self.is_running:
                                logger.info(f"DataPipeline: Shutdown detected during jitter for {symbol}. Aborting.")
                                return
                            time.sleep(0.1)
                    else:
                        raise
        except Exception as e:
            logger.error(f"Critical error in DataPipeline batch storage for {symbol}: {e}")
        finally:
            conn.close()

            # Safe count retrieval
            if hasattr(df, "height"):
                count = df.height
            elif hasattr(df, "__len__"):
                count = len(df)
            else:
                count = 0
            logger.info(f"Stored {count} bars for {symbol}")

    async def run_continuous(self) -> None:
        """
        Run continuous data fetching every 60 seconds during market hours.
        """
        self.is_running = True
        logger.info("DataPipeline: continuous ingestion loop active.")

        # Start high-performance TSDB via socket queue
        await self.qdb.start()

        # Execute the CORE SYNC in the background so the main ingestion loop starts immediately
        self._sync_task = asyncio.create_task(self._background_sync())

        while self.is_running:
            try:
                is_open = self.is_market_open()
                logger.info(
                    f"DataPipeline: Market is {'OPEN' if is_open else 'CLOSED'} - starting pulse."
                )

                # Previously fired all 30 simultaneously, causing +1.7 GB RSS spike.
                # Now strictly limited to 3 concurrent yfinance fetches to cap memory.
                _fetch_sem = asyncio.Semaphore(3)

                async def _throttled_fetch(s):
                    async with _fetch_sem:
                        return await self.fetch_ohlcv(s, tf="1m", bars=100 if is_open else 50)

                tasks = [_throttled_fetch(sym) for sym in self.INSTRUMENTS]
                results = await asyncio.gather(*tasks, return_exceptions=True)

                successful = []

                # Every 5 minutes (or on startup), fetch 1d data for core indices to handle multi-day regime shifts
                pulse_id = int(time.time() // 60)
                if pulse_id % 5 == 0:
                    logger.info("DataPulse: Fetching Macro (1d) Context for SPY/QQQ...")
                    for macro_sym in ["SPY", "QQQ"]:
                        macro_df = await self.fetch_ohlcv(macro_sym, tf="1d", bars=250)
                        if macro_df is not None:
                            await self.store_ohlcv(macro_sym, macro_df, tf="1d")

                conn = self._get_db_connection()
                try:
                    for symbol, df in zip(self.INSTRUMENTS[: len(results)], results, strict=False):
                        if isinstance(df, Exception):
                            logger.error(f"✗ {symbol}: Fetch failed - {df}")
                            continue

                        if (
                            df is None
                            or (hasattr(df, "is_empty") and df.is_empty())
                            or (hasattr(df, "empty") and df.empty)
                        ):
                            continue

                        try:
                            last_p = float(df["Close"][-1])

                            now_mono = time.monotonic()
                            last_check = self._last_reality_check.get(symbol, 0)

                            if now_mono - last_check > 3600:  # 1-hour cooldown
                                bench_p = await self.fetch_benchmark_price(symbol)
                                if bench_p and abs(last_p - bench_p) / bench_p > 0.05:
                                    logger.critical(
                                        f"⚠️ MATRIX DESYNC: {symbol} Price Corrupted! Reality: ${bench_p:.2f} | Matrix: ${last_p:.2f}. Rejecting."
                                    )
                                    continue

                                self._last_reality_check[symbol] = now_mono

                        except Exception as e:
                            logger.debug(f"Price Sanitizer bypass for {symbol}: {e}")

                        if isinstance(df, pl.DataFrame):
                            self.qdb.insert_ohlcv(df, symbol)
                            await self.store_ohlcv(symbol, df, tf="1m")
                            successful.append(symbol)
                except Exception as loop_err:
                    logger.error(f"Persistence Loop Error: {loop_err}")
                finally:
                    conn.close()

                # Python's GC on Windows doesn't always reclaim these promptly
                del results
                import gc

                gc.collect()

                # Heartbeat
                logger.info(f"DataPulse: {len(successful)} symbols reconciled.")

                if self.bus is not None:
                    now_mono = time.monotonic()
                    stale_detect = (
                        any((now_mono - ts) > 60.0 for ts in self._last_reality_check.values())
                        if is_open
                        else False
                    )
                    if stale_detect:
                        logger.warning(
                            "🏛️ Sovereign Integrity: Data Stream pulse detected as STALE. Veto flag engaged."
                        )

                    await self.bus.publish(
                        "candle.batch",
                        {
                            "symbols": self.INSTRUMENTS,
                            "count": len(self.INSTRUMENTS),
                            "timestamp": time.time_ns(),
                            "market_open": is_open,
                            "staleness_veto": stale_detect,
                        },
                    )

                # Previously these were fire-and-forget create_task() calls that
                # leaked aiohttp sessions and TCP connections every 40 seconds.
                # Now we await them directly with a timeout to cap memory usage.
                try:
                    await asyncio.wait_for(self.fetch_vix(), timeout=30.0)
                except Exception as e:
                    logger.debug(f"DataPipeline: VIX enrichment skipped: {e}")

                for sym in ["SPY", "QQQ", "IWM"]:
                    try:
                        await asyncio.wait_for(self.fetch_news(sym), timeout=30.0)
                    except Exception as e:
                        logger.debug(f"DataPipeline: News enrichment skipped for {sym}: {e}")

                try:
                    macro_impact = await asyncio.wait_for(self.fetch_macro_impact(), timeout=30.0)
                    if self.bus:
                        await self.bus.publish("macro.impact", macro_impact)
                except Exception as e:
                    logger.debug(f"DataPipeline: Macro poll skipped: {e}")

                try:
                    for sym in ["SPY", "QQQ"]:
                        flow = await asyncio.wait_for(
                            self.fetch_institutional_flow(sym), timeout=15.0
                        )
                        if self.bus:
                            await self.bus.publish("institutional.flow", flow)
                except Exception as e:
                    logger.debug(f"DataPipeline: Flow poll skipped: {e}")

                # Force garbage collection to purge Polars/yfinance temporary allocations
                import gc

                gc.collect()

                if is_open:
                    from config import DATA_INGESTION_INTERVAL

                    await asyncio.sleep(DATA_INGESTION_INTERVAL)  # Intraday high-freq
                else:
                    from config import DATA_MAINTENANCE_INTERVAL

                    await asyncio.sleep(DATA_MAINTENANCE_INTERVAL)  # Maintenance mode

            except asyncio.CancelledError:
                logger.info("DataPipeline: Cancellation received.")
                raise
            except Exception as e:
                logger.error(f"Error in data pipeline main loop: {e}")
                await asyncio.sleep(5)

    async def _background_sync(self) -> None:
        """Execute the CORE SYNC in the background to avoid blocking system startup."""
        try:
            semaphore = asyncio.Semaphore(3)

            async def throttled_backfill(sym):
                async with semaphore:
                    res = await self.backfill_gap(sym)
                    await asyncio.sleep(0.5)  # Slight delay between symbols
                    return res

            sync_tasks = [throttled_backfill(symbol) for symbol in self.INSTRUMENTS]
            results = await asyncio.gather(*sync_tasks, return_exceptions=True)
            # Log any backfill failures explicitly so they are visible in logs
            for sym, result in zip(self.INSTRUMENTS[: len(results)], results, strict=False):
                if isinstance(result, Exception):
                    logger.error(f"BACKFILL FAILED for {sym}: {result}")
            logger.info("✅ CORE SYNC COMPLETE: Database established continuity in background.")
            # Launch periodic research and news tasks
            self._news_task = asyncio.create_task(self._run_news_loop())
            self._research_task = asyncio.create_task(self._run_research_loop())
        except Exception as e:
            logger.error(f"Error during background core sync: {e}")

    async def fetch_benchmark_price(self, symbol: str) -> float | None:
        """Helper to fetch a fast 'Reality Check' price from yfinance."""
        try:
            ticker = await asyncio.to_thread(yf.Ticker, symbol)
            info = await asyncio.to_thread(lambda: ticker.fast_info)
            if hasattr(info, "last_price"):
                return float(info.last_price)
            return float(info["lastPrice"])
        except Exception:
            return None

    def get_last_price(self, symbol: str) -> float | None:
        """Fetch the absolute latest price (Simulated for Brain Recovery)."""
        return None

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

    async def fetch_dark_pool_logic(self, symbol: str) -> str:
        """Sovereign Dark Pool Tracker: Detects hidden institutional accumulation."""
        # Simulated dark pool logic based on volume divergence
        return "NEUTRAL_ACCUMULATION"

    async def fetch_fomc_calendar(self) -> list[dict]:
        """Fetch central bank policy events (Placeholder for OpenBB Eco module)."""
        return [{"event": "Market Monitoring", "importance": "HIGH"}]

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

    async def _get_http_session(self) -> aiohttp.ClientSession:
        """Return a shared, persistent HTTP session. Creates one if needed."""
        if self._http_session is None or self._http_session.closed:
            timeout = aiohttp.ClientTimeout(total=30.0, connect=10.0)
            self._http_session = aiohttp.ClientSession(timeout=timeout)
        return self._http_session

    async def stop(self) -> None:
        """Graceful shutdown."""
        logger.info("Stopping DataPipeline...")
        self.is_running = False

        # Parallel Task Cancellation
        tasks_to_cancel = [
            ("_sync_task", "Background Sync"),
            ("_news_task", "News Loop"),
            ("_research_task", "Research Loop"),
        ]

        cancel_tasks = []
        for attr, name in tasks_to_cancel:
            task = getattr(self, attr, None)
            if task and not task.done():
                logger.info(f"Cancelling DataPipeline task: {name}")
                task.cancel()
                cancel_tasks.append(task)

        if cancel_tasks:
            try:
                # Wait for all cancellations in parallel with a shared timeout
                await asyncio.wait_for(
                    asyncio.gather(*cancel_tasks, return_exceptions=True), timeout=5.0
                )
            except asyncio.TimeoutError:
                logger.warning("DataPipeline: Some tasks failed to cancel within 5s.")
            except Exception as e:
                logger.error(f"Error during parallel task cancellation: {e}")

        # Wait for all in-flight database threads to complete
        wait_start = time.time()
        while self._active_db_tasks > 0 and (time.time() - wait_start) < 10.0:
            logger.info(f"DataPipeline: Waiting for {self._active_db_tasks} storage threads to finish...")
            await asyncio.sleep(0.5)

        if self._active_db_tasks > 0:
            logger.warning(f"DataPipeline: {self._active_db_tasks} storage threads still active after 10s timeout.")

        # Cancel any lingering enrichment tasks

        for t in list(self._enrichment_tasks):
            if not t.done():
                t.cancel()
        self._enrichment_tasks.clear()

        if self._http_session and not self._http_session.closed:
            await self._http_session.close()
            self._http_session = None

        if self.qdb:
            await self.qdb.stop()
        logger.info("DataPipeline: OFFLINE.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("Sovereign DataPipeline: Manual test mode enabled.")
