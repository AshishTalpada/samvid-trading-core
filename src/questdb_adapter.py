import asyncio
import concurrent.futures
import logging
import socket
import time
from datetime import datetime, timezone
from typing import Any, Optional

try:
    import pandas as pd
    import polars as pl
    import psycopg2
    from psycopg2 import pool

    HAS_PSYCOPG2 = True
except ImportError:
    HAS_PSYCOPG2 = False

logger = logging.getLogger(__name__)


class QuestDBAdapter:
    """
    Elite Status: High-performance time-series logger using InfluxDB Line Protocol (ILP)
    and PostgreSQL wire protocol for fast querying.
    """

    def __init__(
        self,
        host: str = "localhost",
        ilp_port: int = 9009,
        pg_port: int = 8812,
        user: str = "admin",
        password: str = "quest",
        enabled: bool = False,
        connect_timeout_sec: float = 5.0,
    ) -> None:
        self.host = host
        self.ilp_port = ilp_port
        self.pg_port = pg_port
        self.user = user
        self.password = password
        self.enabled = enabled
        self._connect_timeout_sec = max(0.5, connect_timeout_sec)
        self._sock: socket.socket | None = None
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=10000)
        self._worker_task: asyncio.Task | None = None
        self._started: bool = False
        self.is_active: bool = False  # Track ILP connectivity for API status
        self.is_simulated: bool = False
        self._logged_missing_psycopg: bool = False
        # Retry state for exponential backoff
        self._retry_count: int = 0
        self._retry_delay: float = 5.0

        # We fence QuestDB's blocking I/O into a private pool to prevent engine starvation.
        self._executor: Optional[concurrent.futures.ThreadPoolExecutor] = concurrent.futures.ThreadPoolExecutor(
            max_workers=10, thread_name_prefix="QuestDB_IO"
        )
        self._pg_pool: pool.SimpleConnectionPool | None = None

    async def start(self) -> None:
        """Start the background worker for async logging."""
        if not self.enabled:
            return
        if self._started:
            return
        # Fast startup probe: if ILP is unreachable, switch to Simulation mode.
        await self._connect()
        if self._sock is None:
            logger.info(
                f"QuestDB: Could not connect to {self.host}:{self.ilp_port} — Switching to SIMULATED (Memory-Only) mode."
            )
            self.is_simulated = True
            # We don't disable anymore, just run as simulation

        self._worker_task = asyncio.create_task(self._worker())
        self._started = True
        self._next_reconnect_attempt: float = 0.0  # For simulated mode reconnect
        _mode = "LIVE" if not self.is_simulated else "SIMULATED (Memory-Only)"
        logger.info(f"QuestDBAdapter initialized ({_mode}) at {self.host}:{self.ilp_port}")

    async def _worker(self) -> None:
        """Background worker to drain the queue and send to QuestDB."""
        while self.enabled:
            try:
                if self.is_simulated and time.monotonic() > getattr(
                    self, "_next_reconnect_attempt", 0
                ):
                    await self._connect()
                    if self._sock is not None:
                        self.is_simulated = False
                        logger.info("QuestDB: Reconnected from SIMULATED to LIVE mode.")
                    else:
                        self._next_reconnect_attempt = time.monotonic() + 60.0

                # Batch processing
                batch = []

                # We NO LONGER wait forever at queue.get().
                # We use a timeout so the reconnection logic at the top of the loop can trigger
                # even when the system is quiet (no trades/signals).
                try:
                    msg = await asyncio.wait_for(self._queue.get(), timeout=10.0)
                    batch.append(msg)
                    while len(batch) < 5000 and not self._queue.empty():
                        batch.append(self._queue.get_nowait())
                except asyncio.TimeoutError:
                    # Timeout reached — loop restarts to allow reconnection/simulated check
                    continue

                if not self._sock:
                    await self._connect()

                sock = self._sock
                if sock is not None:
                    try:
                        payload = "\n".join(batch) + "\n"
                        loop = asyncio.get_running_loop()
                        await loop.run_in_executor(self._executor, lambda: sock.sendall(payload.encode()))

                        # Reset backoff on success
                        if self._retry_count > 0:
                            logger.info("QuestDB: Reconnected successfully.")
                            self._retry_count = 0
                            self._retry_delay = 5.0
                    except (OSError, ConnectionRefusedError) as e:
                        logger.debug(f"QuestDB send failed: {e}")
                        self._sock = None
                        raise  # Re-raise to trigger the existing backoff logic
                else:
                    # Log only on first failure and every 10th retry to avoid spam
                    if self._retry_count == 0:
                        logger.warning(
                            f"QuestDB: Cannot reach {self.host}:{self.ilp_port} — "
                            "messages will be dropped until reconnected. "
                            "(Suppressing further retries — set QUESTDB_ENABLED=False in config.py to silence entirely)"
                        )
                    elif self._retry_count % 10 == 0:
                        logger.debug(
                            f"QuestDB: Still unreachable after {self._retry_count} retries "
                            f"(next backoff: {self._retry_delay:.0f}s)"
                        )
                    self._retry_count += 1

                for _ in range(len(batch)):
                    self._queue.task_done()

            except (OSError, ConnectionRefusedError):
                self._sock = None
                if self._retry_count == 0:
                    logger.warning("QuestDB: Connection lost — entering backoff retry.")
                self._retry_count += 1

                if self._retry_count >= 3 and not self.is_simulated:
                    logger.warning(
                        "QuestDB: Persistent connection failure. Switching to SIMULATED mode."
                    )
                    self.is_simulated = True
                    self._next_reconnect_attempt = time.monotonic() + 300.0  # Try again in 5 mins

                # Exponential backoff capped at 120s
                self._retry_delay = min(self._retry_delay * 2, 120.0)
                await asyncio.sleep(self._retry_delay)
            except Exception as e:
                logger.error(f"QuestDB worker error: {e}")
                await asyncio.sleep(1)

    async def _connect(self) -> None:
        try:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock = self._sock
            if sock is not None:
                sock.settimeout(self._connect_timeout_sec)
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(self._executor, sock.connect, (self.host, self.ilp_port))
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                self.is_active = True

                # Initialize PG Pool if possible
                if HAS_PSYCOPG2 and self._pg_pool is None:
                    try:
                        conn_str = f"host={self.host} port={self.pg_port} user={self.user} password={self.password} dbname=qdb connect_timeout=3"
                        self._pg_pool = pool.SimpleConnectionPool(2, 10, conn_str)
                        logger.debug("QuestDB: PG Connection Pool online.")
                    except Exception as e:
                        logger.warning(f"QuestDB: PG Pool failed: {e}")
        except Exception as e:
            logger.debug(f"QuestDB: Could not connect to {self.host}:{self.ilp_port}: {e}")
            self._sock = None
            self.is_active = False

    def log_event(self, table: str, data: dict[str, Any]) -> None:
        """
        Log a generic system event or metric to QuestDB.
        Example: log_event("system_metrics", {"cpu": 45.2, "ram": 1024})
        """
        if not self.enabled:
            return

        ts = int(datetime.now(timezone.utc).timestamp() * 1e9)

        # Sanitize table name
        safe_table = table.replace(",", "\\,").replace(" ", "\\ ").replace("=", "\\=")

        # Prepare fields (ILP format: key=value)
        fields = []
        for k, v in data.items():
            safe_k = k.replace(",", "\\,").replace(" ", "\\ ").replace("=", "\\=")
            if isinstance(v, bool):
                fields.append(f"{safe_k}={'true' if v else 'false'}")
            elif isinstance(v, (int, float)):
                # QuestDB ILP uses 'f' suffix for floats sometimes, but usually just a dot is enough
                # For integers, it uses 'i' suffix.
                if isinstance(v, int):
                    fields.append(f"{safe_k}={v}i")
                else:
                    fields.append(f"{safe_k}={v}")
            else:
                # String field (quoted)
                safe_v = str(v).replace('"', '\\"')
                fields.append(f'{safe_k}="{safe_v}"')

        if not fields:
            return

        line = f"{safe_table} {','.join(fields)} {ts}"
        try:
            self._queue.put_nowait(line)
        except asyncio.QueueFull:
            pass

    def log_signal(
        self,
        agent_id: str,
        symbol: str,
        signal_type: str,
        confidence: float,
        metadata: dict[str, Any],
    ) -> None:
        """
        Log an agent signal to QuestDB.
        Format: signals,agent=A,symbol=SPY,type=SCALP confidence=0.85,meta="details" [timestamp]
        """
        if not self.enabled:
            return

        # Prepare ILP string
        # table,tags fields timestamp

        ts = int(datetime.now(timezone.utc).timestamp() * 1e9)
        safe_symbol = symbol.replace(",", "\\,").replace(" ", "\\ ").replace("=", "\\=")
        safe_agent = agent_id.replace(",", "\\,").replace(" ", "\\ ").replace("=", "\\=")
        safe_type = signal_type.replace(",", "\\,").replace(" ", "\\ ").replace("=", "\\=")
        line = f"signals,agent={safe_agent},symbol={safe_symbol},type={safe_type} confidence={confidence}f {ts}"

        try:
            self._queue.put_nowait(line)
        except asyncio.QueueFull:
            pass  # Drop logs if queue is overflowing (prioritize execution over logging)

    def log_trade(
        self, symbol: str, side: str, price: float, quantity: float, strategy: str
    ) -> None:
        """Log a trade execution."""
        if not self.enabled:
            return

        ts = int(time.time() * 1e9)
        safe_symbol = symbol.replace(",", "\\,").replace(" ", "\\ ").replace("=", "\\=")
        safe_side = side.replace(",", "\\,").replace(" ", "\\ ").replace("=", "\\=")
        safe_strategy = strategy.replace(",", "\\,").replace(" ", "\\ ").replace("=", "\\=")
        line = f"trades,symbol={safe_symbol},side={safe_side},strategy={safe_strategy} price={price},quantity={quantity} {ts}"
        try:
            self._queue.put_nowait(line)
        except asyncio.QueueFull:
            pass

    def log_tick(self, symbol: str, price: float, size: float) -> None:
        """Log a real-time HFT tick to QuestDB via the managed ILP queue."""
        if not self.enabled:
            return

        ts = int(datetime.now(timezone.utc).timestamp() * 1e9)
        safe_symbol = symbol.replace(",", "\\,").replace(" ", "\\ ").replace("=", "\\=")

        # ILP Format: table,tags fields timestamp
        line = f"ticks,symbol={safe_symbol} price={price},size={size} {ts}"
        try:
            self._queue.put_nowait(line)
        except asyncio.QueueFull:
            pass  # Drop ticks during extreme saturation to protect engine heartbeat

    def insert_ohlcv(self, df, symbol: str, timeframe: str = "1m") -> None:
        """Stream OHLCV from Polars/Pandas to QuestDB via ILP."""
        if not self.enabled or df is None:
            return

        # Explicitly check for empty status
        is_empty = False
        if hasattr(df, "empty"):
            is_empty = bool(df.empty)
        elif hasattr(df, "is_empty"):
            is_empty = bool(df.is_empty())
        else:
            is_empty = len(df) == 0

        if is_empty:
            return

        try:
            safe_symbol = symbol.replace(",", "\\,").replace(" ", "\\ ").replace("=", "\\=")
            safe_tf = timeframe.replace(",", "\\,").replace(" ", "\\ ").replace("=", "\\=")

            # Polars implementation (Ultra-Fast)
            if hasattr(df, "with_columns"):
                # Vectorize the string construction in Polars C++ core
                ilp_df = df.with_columns(
                    [
                        (
                            pl.lit("ohlcv,symbol=")
                            + pl.lit(safe_symbol)
                            + pl.lit(",timeframe=")
                            + pl.lit(safe_tf)
                            + pl.lit(" open=")
                            + pl.col("open").cast(pl.String)
                            + pl.lit(",high=")
                            + pl.col("high").cast(pl.String)
                            + pl.lit(",low=")
                            + pl.col("low").cast(pl.String)
                            + pl.lit(",close=")
                            + pl.col("close").cast(pl.String)
                            + pl.lit(",volume=")
                            + pl.col("volume").cast(pl.Int64).cast(pl.String)
                            + pl.lit("i ")
                            + (pl.col("timestamp").cast(pl.Int64)).cast(pl.String)
                        ).alias("ilp_line")
                    ]
                )
                lines = ilp_df["ilp_line"].to_list()
                for line in lines:
                    self._queue.put_nowait(line)
            else:
                # Pandas fallback (Manual but safe)
                for row in df.itertuples():
                    ts_val = getattr(
                        row,
                        "timestamp",
                        getattr(row, "Date", getattr(row, "Datetime", time.time())),
                    )
                    if hasattr(ts_val, "timestamp"):
                        ts_ns = int(ts_val.timestamp() * 1e9)
                    else:
                        ts_ns = int(ts_val) if ts_val is not None else 0  # Assume already ns or unix

                    def _get_f(name):
                        v = getattr(row, name, getattr(row, name.lower(), 0.0))
                        return float(v) if v is not None else 0.0

                    line = f"ohlcv,symbol={safe_symbol},timeframe={safe_tf} open={_get_f('Open')},high={_get_f('High')},low={_get_f('Low')},close={_get_f('Close')},volume={int(getattr(row, 'Volume', getattr(row, 'volume', 0)))}i {ts_ns}"
                    self._queue.put_nowait(line)

        except asyncio.QueueFull:
            logger.warning(f"QuestDBILP Queue Full: dropped {symbol} OHLCV batch")
        except Exception as e:
            logger.error(f"Error ILP encoding OHLCV for {symbol}: {e}")

    async def fetch_ohlcv_pandas(
        self, symbol: str, timeframe: str = "1m", limit: int = 200
    ) -> Optional["pd.DataFrame"]:
        """Read OHLCV synchronously via Postgres dialect (to be called via to_thread)."""
        if not self.enabled or self.is_simulated:
            return None
        if not HAS_PSYCOPG2:
            if not self._logged_missing_psycopg:
                self._logged_missing_psycopg = True
                logger.warning(
                    "QuestDB: psycopg2 not installed — brain cannot read OHLCV from QuestDB "
                    "(install: pip install psycopg2-binary)"
                )
            return None

        safe_limit = max(1, min(limit, 5000))

        def _sync_fetch():
            conn = None
            try:
                # Use pool if available
                if self._pg_pool:
                    conn = self._pg_pool.getconn()
                else:
                    conn_str = f"host={self.host} port={self.pg_port} user={self.user} password={self.password} dbname=qdb connect_timeout=3"
                    conn = psycopg2.connect(conn_str)

                query = """
                    SELECT timestamp, open, high, low, close, volume
                    FROM ohlcv
                    WHERE symbol = %s AND timeframe = %s
                    ORDER BY timestamp DESC
                    LIMIT %s
                """
                cursor = conn.cursor() if conn else None
                if cursor:
                    cursor.execute(query, (symbol, timeframe, safe_limit))
                    rows = cursor.fetchall()
                    if rows and cursor.description:
                        col_names = [desc[0] for desc in cursor.description]
                        df = pd.DataFrame(rows, columns=col_names)
                        return df.sort_values("timestamp").reset_index(drop=True)
                return None
            except Exception as e:
                logger.debug(f"QuestDB native fetch failed for {symbol}: {e}")
                return None
            finally:
                if conn:
                    if self._pg_pool:
                        self._pg_pool.putconn(conn)
                    else:
                        conn.close()

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self._executor, _sync_fetch)

    async def fetch_latest_price(self, symbol: str) -> Optional[float]:
        """Fetch the most recent tick price for a symbol from QuestDB."""
        if not self.enabled or self.is_simulated or not HAS_PSYCOPG2:
            return None

        def _sync_fetch():
            conn = None
            try:
                if self._pg_pool:
                    conn = self._pg_pool.getconn()
                else:
                    conn_str = f"host={self.host} port={self.pg_port} user={self.user} password={self.password} dbname=qdb connect_timeout=3"
                    conn = psycopg2.connect(conn_str)

                # Use LATEST ON for performance in QuestDB
                cursor = conn.cursor() if conn else None
                if cursor:
                    query = "SELECT price FROM ticks WHERE symbol = %s ORDER BY timestamp DESC LIMIT 1"
                    cursor.execute(query, (symbol,))
                    row = cursor.fetchone()
                    return float(row[0]) if row else None
            except Exception:
                return None
            finally:
                if conn:
                    if self._pg_pool:
                        self._pg_pool.putconn(conn)
                    else:
                        conn.close()

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self._executor, _sync_fetch)

    async def prune_historical_ticks(self, days_to_keep: int = 30) -> None:
        """
        Database Bloat Guard: QuestDB maintenance loop.
        Increased retention to 30 days to prevent premature telemetry loss.
        """
        if not self.enabled or not HAS_PSYCOPG2:
            return

        def _sync_prune() -> None:
            conn = None
            try:
                if self._pg_pool:
                    conn = self._pg_pool.getconn()
                else:
                    conn_str = f"host={self.host} port={self.pg_port} user={self.user} password={self.password} dbname=qdb"
                    conn = psycopg2.connect(conn_str)
                cursor = conn.cursor() if conn else None
                if cursor is None:
                    return

                # In QuestDB, we can drop partitions string-formatted as 'YYYY-MM-DD'
                # Generate a list of dates older than `days_to_keep`
                for i in range(days_to_keep, days_to_keep + 14):
                    stale_date = (pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=i)).strftime(
                        "%Y-%m-%d"
                    )

                    import re

                    if not re.match(r"^\d{4}-\d{2}-\d{2}$", stale_date):
                        logger.error(
                            f"QuestDB: Invalid partition date format detected: {stale_date}"
                        )
                        continue

                    try:
                        cursor.execute(f"ALTER TABLE ohlcv DROP PARTITION '{stale_date}';")
                        cursor.execute(f"ALTER TABLE ticks DROP PARTITION '{stale_date}';")
                        conn.commit()
                        logger.debug(f"QuestDB: Pruned historical partition {stale_date}")
                    except Exception:
                        # Ignore errors if partition does not exist
                        conn.rollback()

            except Exception as e:
                logger.error(f"QuestDB Prune failed: {e}")
            finally:
                if conn:
                    if self._pg_pool:
                        self._pg_pool.putconn(conn)
                    else:
                        conn.close()

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(self._executor, _sync_prune)

    async def stop(self) -> None:
        """Sovereign Shutdown: Idempotent resource release."""
        self.enabled = False
        self._started = False

        # 1. Cancel background worker
        worker = self._worker_task
        if worker is not None:
            worker.cancel()
            try:
                await worker
            except asyncio.CancelledError:
                pass
            self._worker_task = None

        # 2. Close ILP Socket
        sock = self._sock
        if sock is not None:
            try:
                sock.close()
            except Exception:
                pass
            self._sock = None

        # 3. Shutdown PG Pool and Executor
        if self._pg_pool:
            try:
                # Double-check closed state if library supports it, or just wrap
                self._pg_pool.closeall()
                logger.debug("QuestDB: PG Pool closed.")
            except Exception as e:
                # Catch PoolError if already closed
                logger.debug(f"QuestDB: Pool close skipped: {e}")
            finally:
                self._pg_pool = None

        if self._executor is not None:
            try:
                self._executor.shutdown(wait=False)
            except Exception:
                pass
            self._executor = None


        self.is_active = False
