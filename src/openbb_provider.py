"""
src/openbb_provider.py - OpenBB Multi-Source Financial Data Provider
Wraps the OpenBB SDK to provide a unified data access layer for:
  - Equity OHLCV (historical + real-time)
  - Technical indicators (RSI, MACD, Bollinger Bands, ATR)
  - Macro economic data (Treasury yields, DXY, VIX)
  - News & sentiment aggregation
  - Crypto & Forex data
Designed as a drop-in enhancement for the existing yfinance-based DataPipeline.
Falls back gracefully when OpenBB is not installed or PAT is unavailable.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any

from vault import Vault

logger = logging.getLogger(__name__)

# Previously loaded at module scope, consuming 500+ MB of RAM and taking
# minutes to import. Now lazy-loaded only when initialize() is called.
_OPENBB_AVAILABLE = None  # None = not yet checked, True/False = checked
obb = None  # type: ignore[assignment]

def _try_load_openbb():
    """Lazy-load OpenBB SDK. Returns (is_available, obb_module)."""
    global _OPENBB_AVAILABLE, obb
    if _OPENBB_AVAILABLE is not None:
        return _OPENBB_AVAILABLE
    try:
        import importlib
        openbb = importlib.import_module("openbb")
        obb = openbb.obb
        _OPENBB_AVAILABLE = True
        logger.info("✓ OpenBB SDK loaded (deferred)")
    except ImportError:
        obb = None
        _OPENBB_AVAILABLE = False
    return _OPENBB_AVAILABLE


class OpenBBProvider:
    """
    Multi-source financial data provider powered by the OpenBB SDK.
    If OpenBB is not installed or the PAT is invalid the provider silently
    returns ``None`` / empty results so callers can fall back to yfinance.
    """

    def __init__(self, preferred_provider: str = "yfinance") -> None:
        """
        Args:
            preferred_provider: Default data provider (yfinance, polygon, tiingo, …).
        """
        self._provider = preferred_provider
        self._initialized = False
        import os
        self._disabled_by_env = os.getenv("SOVEREIGN_DISABLE_OPENBB", "0") == "1"
        self._load_lock = asyncio.Lock()

        # Note: We do not eagerly load OpenBB here. We do it in initialize().

    async def initialize(self) -> None:
        """Asynchronously authenticate and inject provider keys (non-blocking matrix init)."""
        if self._initialized:
            return

        # Do NOT load OpenBB SDK here during startup to avoid hanging the system.
        # It takes ~5 minutes to load and consumes 1GB RAM.
        # We will load it on first use inside the fetch_ methods instead.

        # If PAT is provided, we can't login yet because `obb` isn't loaded.
        # We will defer PAT login.

        # Trigger a non-blocking availability check (pre-warms the cache)
        asyncio.create_task(self._ensure_obb())
        self._initialized = True
        logger.info(f"✓ OpenBB Provider initialized (pre-warming SDK, provider={self._provider})")

    # Public helpers

    @property
    def is_available(self) -> bool:
        # Returns True if initialized and not explicitly disabled,
        # even if SDK is still loading in background.
        if self._disabled_by_env:
            return False
        return self._initialized

    @property
    def status(self) -> str:
        """Returns the current connectivity status (ONLINE, PROBING, or OFFLINE)."""
        if not self._initialized:
            return "OFFLINE"
        if _OPENBB_AVAILABLE is True:
            return "ONLINE"
        if _OPENBB_AVAILABLE is False:
            return "OFFLINE"
        return "PROBING"

    async def _ensure_obb(self) -> bool:
        """
        Non-blocking lazy loader for the OpenBB SDK.
        All fetch methods call this instead of checking `is_available` directly.
        The 5-minute OpenBB import is run in a thread pool, so it never blocks
        the event loop. After first successful load the result is cached globally.
        """
        global _OPENBB_AVAILABLE
        if _OPENBB_AVAILABLE is True:
            return True
        if _OPENBB_AVAILABLE is False:
            return False

        async with self._load_lock:
            # Re-check after acquiring lock
            if _OPENBB_AVAILABLE is not None:
                return _OPENBB_AVAILABLE

            try:
                # OpenBB takes ~15-30s to load on first use, increased timeout accordingly.
                # We allow 30s for the initial ingestion to avoid yfinance fallback.
                logger.info("OpenBB: SDK ingestion initiated (30s speed-gate active)...")
                loaded = await asyncio.wait_for(asyncio.to_thread(_try_load_openbb), timeout=30.0)
                if not loaded:
                    logger.warning("OpenBB SDK not available — falling back to yfinance.")
                    return False
            except asyncio.TimeoutError:
                logger.warning("OpenBB SDK ingestion timed out (Slow Load) — falling back to yfinance for this cycle.")
                return False
            except Exception as e:
                logger.error(f"OpenBB Loader Error: {e}")
                _OPENBB_AVAILABLE = False
                return False
        try:
            from vault import Vault
            pat = Vault.get("OPENBB_PAT")

            # This enables 'Active PAT' mode requested by the user.
            if pat:
                try:
                    # Attempt Hub Login if supported by the installed version
                    if hasattr(obb, "account") and hasattr(obb.account, "login"):
                        obb.account.login(token=pat)
                        logger.info("✓ OpenBB Hub Session ACTIVE (via PAT)")
                    else:
                        # Fallback for older ODP versions: Environment variable injection
                        import os
                        os.environ["OPENBB_PLATFORM_PAT"] = pat
                        logger.info("✓ OpenBB PAT injected into environment (ODP Legacy Mode)")
                except Exception as login_err:
                    logger.warning(f"OpenBB PAT activation failed: {login_err}")

            # Map standard Vault keys to OpenBB Platform v4 credential attributes
            # Even with PAT, we inject these as local overrides for robustness.
            creds = {
                "fmp_api_key": Vault.get("FMP_API_KEY"),
                "tiingo_token": Vault.get("TIINGO_API_KEY"),
                "benzinga_api_key": Vault.get("BENZINGA_API_KEY"),
                "polygon_api_key": Vault.get("POLYGON_API_KEY"),
                "intrinio_api_key": Vault.get("INTRINIO_API_KEY"),
                "av_api_key": Vault.get("ALPHA_VANTAGE_API_KEY"),
            }

            for key, val in creds.items():
                if val:
                    setattr(obb.user.credentials, key, val)

            logger.info("✓ OpenBB Provider synchronized with Sovereign Vault.")
        except Exception as e:
            logger.warning(f"OpenBB credential injection failed (non-fatal): {e}")

        return True

    # Equity OHLCV

    async def fetch_ohlcv(
        self,
        symbol: str,
        period_days: int = 365,
        interval: str = "1d",
    ) -> Any | None:
        """
        Fetch historical OHLCV data and return as a Polars DataFrame.
        Returns ``None`` on error so the caller can fall back to yfinance.
        """
        if not await self._ensure_obb():
            return None

        try:
            import polars as pl

            start_date = (datetime.now() - timedelta(days=period_days)).strftime("%Y-%m-%d")

            result = await asyncio.to_thread(
                lambda: obb.equity.price.historical(  # type: ignore[union-attr]
                    symbol=symbol,
                    provider=self._provider,
                    start_date=start_date,
                    interval=interval,
                )
            )

            if result is None:
                return None

            df_pd = result.to_df()
            if df_pd.empty:
                return None

            # Standardise column names to lowercase
            df_pd.columns = df_pd.columns.str.lower()
            df_pd.reset_index(inplace=True)

            # Rename 'date' → 'timestamp' to match pipeline convention
            for col in ("date", "datetime", "time"):
                if col in df_pd.columns:
                    df_pd.rename(columns={col: "timestamp"}, inplace=True)
                    break

            pl_df = pl.from_pandas(df_pd)
            logger.debug(f"OpenBB fetched {len(pl_df)} bars for {symbol}")
            return pl_df

        except Exception as e:
            logger.debug(f"OpenBB OHLCV fetch failed for {symbol}: {e}")
            return None

    # Current price

    async def get_current_price(self, symbol: str) -> float | None:
        """Return the latest closing price or ``None``."""
        if not await self._ensure_obb():
            return None

        try:
            result = await asyncio.to_thread(
                lambda: obb.equity.price.quote(  # type: ignore[union-attr]
                    symbol=symbol,
                    provider=self._provider,
                )
            )
            if result is None:
                return None

            df = result.to_df()
            if df.empty:
                return None

            # Try several common column names
            for col in ("last_price", "price", "close", "lastPrice"):
                if col in df.columns:
                    val = df[col].iloc[0]
                    if val and float(val) > 0:
                        return float(val)

            return None
        except Exception as e:
            logger.debug(f"OpenBB price quote failed for {symbol}: {e}")
            return None

    # Technical indicators (computed from OHLCV)

    async def fetch_technical_indicators(
        self, symbol: str, period_days: int = 365
    ) -> dict[str, Any]:
        """
        Calculate RSI, MACD, Bollinger Bands, ATR for *symbol*.
        Returns a dict with keys: rsi, macd, macd_signal, bb_upper,
        bb_lower, bb_width, atr.  Empty dict on failure.
        """
        if not await self._ensure_obb():
            return {}

        try:
            import numpy as np

            if period_days > 100:
                logger.warning(f"RSI/Technical period {period_days} too high, capping at 100 to prevent lag.")
                period_days = 100

            start = (datetime.now() - timedelta(days=period_days)).strftime("%Y-%m-%d")

            result = await asyncio.to_thread(
                lambda: obb.equity.price.historical(  # type: ignore[union-attr]
                    symbol=symbol,
                    provider=self._provider,
                    start_date=start,
                )
            )
            if result is None:
                return {}

            df = result.to_df()
            if df.empty or len(df) < 30:
                return {}

            # Indicators can produce NaNs at the start or during gaps.
            # We enforce forward-filling to ensure continuity during low-liquidity/holidays.
            close = df["close"].ffill().bfill()
            high = df["high"].ffill().bfill()
            low = df["low"].ffill().bfill()

            # RSI (14)
            delta = close.diff()
            gain = delta.where(delta > 0, 0.0).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0.0)).rolling(14).mean()
            rs = gain / loss.replace(0, np.nan)
            rsi = (100 - (100 / (1 + rs))).ffill().fillna(50.0)

            # MACD (12, 26, 9)
            exp1 = close.ewm(span=12).mean()
            exp2 = close.ewm(span=26).mean()
            macd = (exp1 - exp2).ffill().fillna(0.0)
            macd_signal = macd.ewm(span=9).mean().ffill().fillna(0.0)

            # Bollinger Bands (20, 2)
            bb_mid = close.rolling(20).mean()
            bb_std = close.rolling(20).std()
            bb_upper = (bb_mid + 2 * bb_std).ffill().fillna(0.0)
            bb_lower = (bb_mid - 2 * bb_std).ffill().fillna(0.0)
            bb_width = ((bb_upper - bb_lower) / bb_mid.replace(0, np.nan)).ffill().fillna(0.0)

            # ATR (14)
            tr = np.maximum(
                high - low,
                np.maximum(abs(high - close.shift()), abs(low - close.shift())),
            ).ffill()
            atr_series = tr.rolling(14).mean().ffill().fillna(0.0)

            def _safe_float(val, default=0.0):
                try:
                    v = float(val)
                    return v if not np.isnan(v) else default
                except Exception:
                    return default

            return {
                "rsi": _safe_float(rsi.iloc[-1], 50.0) if not rsi.empty else 50.0,
                "macd": _safe_float(macd.iloc[-1]) if not macd.empty else 0.0,
                "macd_signal": _safe_float(macd_signal.iloc[-1]) if not macd_signal.empty else 0.0,
                "bb_upper": _safe_float(bb_upper.iloc[-1]) if not bb_upper.empty else 0.0,
                "bb_lower": _safe_float(bb_lower.iloc[-1]) if not bb_lower.empty else 0.0,
                "bb_width": _safe_float(bb_width.iloc[-1]) if not bb_width.empty else 0.0,
                "atr": _safe_float(atr_series.iloc[-1]) if len(atr_series) > 0 else 0.0,
            }

        except Exception as e:
            logger.debug(f"OpenBB technical indicators failed for {symbol}: {e}")
            return {}

    # Macro economic snapshot

    async def fetch_macro_data(self) -> dict[str, Any]:
        """
        Fetch a macro snapshot: VIX, DXY, 10Y yield, oil, gold.
        Returns a dict of key→value pairs.  Empty dict on failure.
        """
        if not await self._ensure_obb():
            return {}

        macro: dict[str, Any] = {}

        # Helper to fetch a single ticker's last close
        async def _last_close(sym: str, key: str) -> None:
            try:
                result = await asyncio.to_thread(
                    lambda: obb.equity.price.historical(  # type: ignore[union-attr]
                        symbol=sym,
                        provider=self._provider,
                        start_date=(datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d"),
                    )
                )
                if result is not None:
                    df = result.to_df()
                    if not df.empty:
                        macro[key] = float(df["close"].iloc[-1])
            except Exception:
                pass

        await asyncio.gather(
            _last_close("^VIX", "vix"),
            _last_close("^TNX", "treasury_10y"),
            _last_close("DX-Y.NYB", "dxy"),
            _last_close("CL=F", "crude_oil"),
            _last_close("GC=F", "gold"),
            return_exceptions=True,
        )

        logger.debug(f"OpenBB macro snapshot: {macro}")
        return macro

    # News

    async def fetch_news(self, symbol: str, limit: int = 10) -> list[dict[str, str]]:
        """
        Fetch recent news for *symbol* via OpenBB.
        Returns a list of dicts with keys: headline, summary, source, url, published_at.
        """
        if not await self._ensure_obb():
            return []

        try:
            # Check for available news providers (prioritize those with keys)
            news_provider = None
            for p in ["benzinga", "tiingo", "fmp"]:
                key_val = Vault.get(f"{p.upper()}_API_KEY")
                if key_val:
                    news_provider = p
                    break

            # If no provider with a key is found, skip the OpenBB call to avoid
            # the "Provider fallback failed" error spam.
            if not news_provider:
                logger.debug("OpenBB news skipped (no Benzinga/Tiingo/FMP keys in Vault)")
                return []

            result = await asyncio.to_thread(
                lambda: obb.news.world(  # type: ignore[union-attr]
                    limit=limit, provider=news_provider
                )
            )
            if result is None:
                return []

            df = result.to_df()
            if df.empty:
                return []

            articles: list[dict[str, str]] = []
            for _, row in df.iterrows():
                articles.append(
                    {
                        "headline": str(row.get("title", "")),
                        "summary": str(row.get("text", ""))[:500] if row.get("text") else "",
                        "source": f"OpenBB ({row.get('source', 'unknown')})",
                        "url": str(row.get("url", "")),
                        "published_at": str(row.get("date", "")),
                        "symbol": symbol,
                        "sentiment": "0.0",
                    }
                )

            logger.debug(f"OpenBB fetched {len(articles)} news articles")
            return articles

        except Exception as e:
            logger.debug(f"OpenBB news fetch failed: {e}")
            return []

    # Crypto

    async def fetch_crypto_ohlcv(self, symbol: str = "BTCUSD", period_days: int = 90) -> Any | None:
        """Fetch crypto OHLCV — returns Polars DataFrame or None."""
        if not await self._ensure_obb():
            return None

        try:
            import polars as pl

            start = (datetime.now() - timedelta(days=period_days)).strftime("%Y-%m-%d")

            result = await asyncio.to_thread(
                lambda: obb.crypto.price.historical(  # type: ignore[union-attr]
                    symbol=symbol,
                    provider=self._provider,
                    start_date=start,
                )
            )
            if result is None:
                return None

            df_pd = result.to_df()
            if df_pd.empty:
                return None

            df_pd.columns = df_pd.columns.str.lower()
            df_pd.reset_index(inplace=True)
            for col in ("date", "datetime", "time"):
                if col in df_pd.columns:
                    df_pd.rename(columns={col: "timestamp"}, inplace=True)
                    break

            return pl.from_pandas(df_pd)

        except Exception as e:
            logger.debug(f"OpenBB crypto fetch failed for {symbol}: {e}")
            return None
