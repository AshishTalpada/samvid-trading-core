"""Market data helpers extracted from brain.py.

Provides the DataProvider mixin with methods for fetching OHLCV data,
VIX levels, the watchlist, regime classification, and market snapshots.
All methods rely solely on self.* attributes set up in TradingBrain.__init__.
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Any, cast

import pandas as pd
import polars as pl

from market_calendar import is_us_equity_market_open
from pandas_safety import safe_polars_from_pandas

logger = logging.getLogger(__name__)


class DataProvider:
    """Mixin: VIX, OHLCV, watchlist, regime detection, and market snapshots."""

    EXECUTION_WATCHLIST = (
        "SPY", "QQQ", "IWM", "DIA",
        "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA",
        "AMD", "AVGO", "SMCI", "ARM", "MU", "PLTR",
        "COIN", "MSTR",
        "JPM", "GS", "V", "MA",
        "WMT", "COST", "NFLX",
    )

    @staticmethod
    def _live_bar_staleness_limit_sec() -> float:
        """Maximum age of a one-minute bar while the market is open."""
        try:
            configured = float(os.getenv("SOVEREIGN_MAX_LIVE_BAR_AGE_SEC", "180"))
        except ValueError:
            configured = 180.0
        return max(60.0, min(configured, 900.0))

    # ------------------------------------------------------------------
    # VIX
    # ------------------------------------------------------------------
    async def _get_vix(self) -> float:
        """Get current VIX level from database (populated by data pipeline)."""

        def _sync_get_vix() -> float:
            cursor = None
            try:
                if self.db_conn:
                    cursor = self.db_conn.cursor()
                    cursor.execute("SELECT value FROM vix_data ORDER BY timestamp DESC LIMIT 1")
                    row = cursor.fetchone()
                    if row and row[0] is not None and float(row[0]) > 0:
                        vix_val = min(100.0, float(row[0]))
                        self._last_vix = vix_val
                        return vix_val
                return getattr(self, "_last_vix", 18.0)
            except Exception:
                return getattr(self, "_last_vix", 18.0)
            finally:
                if cursor is not None:
                    cursor.close()

        return await asyncio.to_thread(_sync_get_vix)  # type: ignore[arg-type]

    # ------------------------------------------------------------------
    # Watchlist & market-open gate
    # ------------------------------------------------------------------
    async def _get_watchlist(self) -> list[str]:
        """Get current watchlist from database or config."""
        return list(self.EXECUTION_WATCHLIST)

    def _is_market_open(self) -> bool:
        """Return True if NYSE is currently in the regular 9:30-16:00 ET session."""
        if os.environ.get("FORCED_MARKET_OPEN") == "1":
            return True
        return is_us_equity_market_open()

    # ------------------------------------------------------------------
    # OHLCV fetch (SQLite + QuestDB with circuit-breaker fallback)
    # ------------------------------------------------------------------
    async def _fetch_ohlcv(self, symbol: str) -> pl.DataFrame | pd.DataFrame | str | None:
        """
        Fetch OHLCV data for a symbol from the projection database.
        Returns:
            - pd.DataFrame  -> usable rows found
            - "STALE"        -> rows exist but are too old for the current session
            - None           -> symbol has zero rows in DB
        """
        try:
            if not self.db_conn and not os.path.exists(self.db_path):
                return None

            # Hot cache: skip repeated DB hits within 5 s
            now_mono = time.monotonic()
            if symbol in self._hot_cache and (now_mono - self._hot_cache_time.get(symbol, 0)) < 5.0:
                return self._hot_cache[symbol]

            df_qdb = None

            # QuestDB circuit-breaker
            if self._qdb_circuit_broken and (now_mono - self._qdb_last_failure_time) < 300:
                pass  # circuit open — fall through to SQLite
            elif self.qdb.enabled:
                try:
                    from config import QUESTDB_CONNECT_TIMEOUT_SEC

                    df_qdb = await asyncio.wait_for(
                        self.qdb.fetch_ohlcv_pandas(symbol, timeframe="1m", limit=200),
                        timeout=QUESTDB_CONNECT_TIMEOUT_SEC,
                    )
                    self._qdb_failure_count = 0
                    if self._qdb_circuit_broken:
                        logger.info("QuestDB circuit breaker RESET — connection recovered.")
                        self._qdb_circuit_broken = False
                except (asyncio.TimeoutError, TimeoutError):
                    self._qdb_failure_count += 1
                    self._qdb_last_failure_time = now_mono
                    if self._qdb_failure_count >= 3:
                        self._qdb_circuit_broken = True
                        logger.critical(
                            "QuestDB SLOWNESS DETECTED. Circuit Broken for 5 minutes. "
                            "Failing over to SQLite/Cache."
                        )
                    else:
                        logger.warning(
                            "QuestDB timeout for %s (%s/3) — failing over to SQLite",
                            symbol,
                            self._qdb_failure_count,
                        )
                    df_qdb = None
                except Exception as q_err:
                    logger.debug("QuestDB read error for %s: %s", symbol, q_err)
                    df_qdb = None

            use_fallback = True
            if df_qdb is not None and not df_qdb.empty:
                qdb_max_ts = pd.to_datetime(df_qdb["timestamp"], utc=True).max()
                now_utc = pd.Timestamp.utcnow()
                qdb_staleness = (now_utc - qdb_max_ts).total_seconds()
                market_open = self._is_market_open()
                staleness_limit = (
                    self._live_bar_staleness_limit_sec() if market_open else 259200
                )
                if qdb_staleness <= staleness_limit:
                    use_fallback = False
                else:
                    logger.debug(
                        "QuestDB returned stale data for %s (%.1fm old), falling back to SQLite",
                        symbol,
                        qdb_staleness / 60,
                    )

            if use_fallback:
                if self.qdb.enabled:
                    logger.debug("QuestDB returned empty for %s, falling back to SQLite", symbol)
                query = (
                    "SELECT timestamp, open, high, low, close, volume "
                    "FROM ohlcv WHERE symbol=? AND timeframe='1m' "
                    "ORDER BY timestamp DESC LIMIT 200"
                )
                try:

                    def _read_sqlite_ohlcv() -> pd.DataFrame:
                        import sqlite3

                        with sqlite3.connect(self.db_path, timeout=60.0) as conn:
                            conn.execute("PRAGMA query_only = ON")
                            return pd.read_sql_query(query, conn, params=[symbol])

                    df = await asyncio.wait_for(
                        asyncio.to_thread(_read_sqlite_ohlcv),
                        timeout=30.0,
                    )
                except (asyncio.TimeoutError, TimeoutError):
                    logger.warning("SQLite timeout for %s after 30s — skipping symbol", symbol)
                    return None
                except Exception as sqlite_err:
                    if "closed database" in str(sqlite_err).lower():
                        logger.warning(
                            "SQLite OHLCV read skipped for %s because the runtime DB handle "
                            "is closing.",
                            symbol,
                        )
                        return None
                    raise
            else:
                df = df_qdb

            if df is None:
                logger.warning("NO DATA: %s — both QuestDB and SQLite returned None", symbol)
                return None

            df_frame: pd.DataFrame = cast(pd.DataFrame, df)
            if df_frame.empty:
                logger.warning(
                    "NO DATA: %s — SQLite ohlcv table returned empty dataframe", symbol
                )
                return None

            # Re-sort to ascending chronological order
            df_frame = df_frame.iloc[::-1].reset_index(drop=True)

            # Staleness check (normalised to UTC on both sides)
            try:
                latest_bar_ts = pd.to_datetime(df_frame["timestamp"], utc=True).max()
                now_utc = pd.Timestamp.utcnow()
                staleness = (now_utc - latest_bar_ts).total_seconds()

                market_open = self._is_market_open()
                staleness_limit = (
                    self._live_bar_staleness_limit_sec() if market_open else 259200
                )
                if os.environ.get("FORCED_MARKET_OPEN") == "1":
                    staleness_limit = 1_000_000

                if staleness > staleness_limit:
                    staleness_min = staleness / 60
                    if market_open:
                        logger.info(
                            "STALE DATA: %s newest bar is %.1fmin old — skipping",
                            symbol,
                            staleness_min,
                        )
                    else:
                        last_alert = getattr(self, "_last_stale_alert", {})
                        now_t = time.time()
                        if now_t - last_alert.get(symbol, 0) > 14400:
                            logger.info(
                                "STALE (MARKET CLOSED): %s newest bar is %.0fmin old (>24h) — skipping",
                                symbol,
                                staleness_min,
                            )
                            last_alert[symbol] = now_t
                            self._last_stale_alert = last_alert
                    return cast(pd.DataFrame, "STALE")
                else:
                    logger.debug(
                        "FRESH DATA: %s newest bar is %.1fmin old (passed staleness gate)",
                        symbol,
                        staleness / 60,
                    )
            except Exception as e:
                if self._is_market_open():
                    logger.warning(
                        "INVALID DATA TIMESTAMP: %s cannot prove bar freshness (%s) - skipping",
                        symbol,
                        e,
                    )
                    return cast(pd.DataFrame, "STALE")
                logger.debug("Staleness check skipped for %s after hours: %s", symbol, e)

            final_df = safe_polars_from_pandas(df_frame)
            self._hot_cache[symbol] = final_df
            self._hot_cache_time[symbol] = time.monotonic()
            freshness_proofs = getattr(self, "_last_fresh_bar_at", None)
            if freshness_proofs is None:
                freshness_proofs = {}
                self._last_fresh_bar_at = freshness_proofs
            freshness_proofs[symbol] = time.monotonic()
            return final_df
        except Exception as e:
            import traceback

            logger.error("Error fetching OHLCV for %s: %s\n%s", symbol, e, traceback.format_exc())
            return None

    # ------------------------------------------------------------------
    # Market snapshot
    # ------------------------------------------------------------------
    async def _fetch_market_snapshot(self, symbol: str) -> dict | None:
        """Get latest price, VIX, and breadth for Agent B evaluation."""
        try:
            snapshot: dict[str, Any] = {
                "symbol": symbol,
                "price": None,
                "price_change_pct": 0.0,
                "vix": await self._get_vix(),
                "breadth": 0.55,
                "volume_ratio": 1.0,
                "momentum": 0.1,
            }

            # HFT tick cache
            if (
                hasattr(self, "_last_tick_price")
                and self._last_tick_price
                and symbol in self._last_tick_price
            ):
                snapshot["price"] = float(self._last_tick_price[symbol])
            elif symbol in self.last_tick_prices:
                snapshot["price"] = float(self.last_tick_prices[symbol])

            # Fallback to OHLCV
            if snapshot["price"] is None:
                df = await self._fetch_ohlcv(symbol)  # type: ignore[arg-type]
                if df is not None and not isinstance(df, str) and len(df) > 0:
                    latest_close = float(df["close"].tail(1).item())
                    prev_close = (
                        float(df["close"].tail(2).to_numpy()[-1]) if len(df) > 1 else latest_close
                    )
                    snapshot["price"] = latest_close
                    snapshot["price_change_pct"] = (latest_close - prev_close) / (prev_close + 1e-10)

            return snapshot
        except Exception as e:
            logger.error("Error fetching market snapshot for %s: %s", symbol, e)
            return None

    # ------------------------------------------------------------------
    # Safe buying power (VIX-adjusted equity)
    # ------------------------------------------------------------------
    async def get_safe_buying_power(self, account_type: str = "ibkr") -> float:
        """
        Defensive Equity Engine.
        Calculates buying power with a VIX-weighted volatility haircut.
        Ensures the sizer never acts on 'hallucinated' equity during crashes.
        """
        raw_equity = await self._get_account_value(account_type, force_fresh=True)
        vix = await self._get_vix()

        # Volatility Haircut: 2% base + (VIX / 2.5)%
        # e.g., VIX 20 -> 10% Haircut | VIX 40 -> 18% Haircut
        haircut_pct = 0.02 + (vix / 250.0)
        safe_equity = raw_equity * (1.0 - haircut_pct)

        logger.debug(
            "Defensive Equity: Raw $%.2f | VIX %.1f | Haircut %.1f%% | Safe $%.2f",
            raw_equity,
            vix,
            haircut_pct * 100,
            safe_equity,
        )
        return safe_equity

    # ------------------------------------------------------------------
    # Regime classification
    # ------------------------------------------------------------------
    async def _detect_regime(self) -> str:
        """Use Agent D's regime classifier with REAL market data from database."""
        _t0 = time.perf_counter()
        try:
            vix = await self._get_vix()
            logger.debug("Regime step 'vix_fetch' took %.2fs", time.perf_counter() - _t0)

            momentum = 0.0
            spy_above_200ma = True
            if len(self.spy_buffer) >= 20:
                l_spy = list(self.spy_buffer)
                momentum = (l_spy[-1] - l_spy[-20]) / l_spy[-20] if l_spy[-20] != 0 else 0
                if len(l_spy) >= 200:
                    sma_200 = sum(l_spy) / 200
                    spy_above_200ma = l_spy[-1] > sma_200
            elif self.db_conn:
                try:
                    spy_df = await asyncio.to_thread(
                        pd.read_sql_query,
                        "SELECT close FROM ohlcv WHERE symbol='SPY' AND timeframe='1d' "
                        "ORDER BY timestamp DESC LIMIT 250",
                        self.db_conn,
                    )
                    if not spy_df.empty:
                        closes = spy_df["close"].iloc[::-1].tolist()
                        if len(closes) >= 20:
                            momentum = (
                                (closes[-1] - closes[-20]) / closes[-20]
                                if closes[-20] != 0
                                else 0
                            )
                        if len(closes) >= 200:
                            sma_200 = sum(closes[-200:]) / 200
                            spy_above_200ma = closes[-1] > sma_200
                            logger.debug(
                                "True Daily SMA 200: %.2f (Price: %.2f)", sma_200, closes[-1]
                            )
                except Exception as e:
                    logger.debug("Regime data fallback (1d): %s", e)
            logger.debug("Regime step 'ma_check' took %.2fs", time.perf_counter() - _t0)

            breadth = 0.55
            if self.db_conn:

                def _sync_breadth() -> float:
                    try:
                        total = 0
                        positive = 0
                        major_indices = [
                            "SPY", "QQQ", "IWM", "DIA", "XLK",
                            "NVDA", "MSFT", "AAPL", "TSLA", "META",
                        ]
                        for sym in major_indices:
                            if sym in self.last_tick_prices:
                                total += 1
                                positive += 1
                            else:
                                row = pd.read_sql_query(
                                    "SELECT close FROM ohlcv WHERE symbol=? "
                                    "ORDER BY timestamp DESC LIMIT 2",
                                    self.db_conn,
                                    params=(sym,),
                                )
                                if not row.empty and len(row) >= 2:
                                    total += 1
                                    if row["close"].iloc[0] > row["close"].iloc[1]:
                                        positive += 1
                        return positive / total if total > 0 else 0.55
                    except Exception:
                        return 0.55

                breadth = await asyncio.to_thread(_sync_breadth)
            logger.debug("Regime step 'breadth_check' took %.2fs", time.perf_counter() - _t0)

            regime = self.regime_classifier.classify(
                vix=vix,
                spy_above_200ma=spy_above_200ma,
                breadth=breadth,
                momentum=momentum,
            )
            logger.debug("Regime step 'classify' took %.2fs", time.perf_counter() - _t0)
            logger.info(
                "Regime: %s (VIX=%.1f, Mom=%.4f, Breadth=%.2f, SPY>200MA=%s)",
                regime, vix, momentum, breadth, spy_above_200ma,
            )
            # Persist for state capsule
            self.session_restorer.save_cognitive_capsule(
                {
                    "regime": regime,
                    "conviction_state": self.conviction_state,
                    "session_pnl": self.session_pnl,
                    "session_stats": self.session_stats,
                    "timestamp": time.time_ns(),
                }
            )
            logger.debug("Regime step 'capsule_save' took %.2fs", time.perf_counter() - _t0)
            return regime
        except Exception as e:
            logger.warning("Regime detection TIMEOUT/FAIL after %.2fs: %s", time.perf_counter() - _t0, e)
            return "CHOPPY"
