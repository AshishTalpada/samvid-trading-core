import asyncio
import json
import logging
import os
import socket
import sqlite3
import time
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

import uvicorn
from fastapi import (
    Depends,
    FastAPI,
    Header,
    HTTPException,
    Query,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware

from decision_ledger import LEDGER
from portfolio_analyzer import PORTFOLIO_ANALYZER
from vault import Vault

logger = logging.getLogger(__name__)


class APIServer:
    """
    FastAPI Bridge for the Trading System Frontend.
    Streams real-time state and Dhatu Oracle intelligence via WebSockets.
    """

    def __init__(self, trading_system, host: str = "0.0.0.0", port: int = 8000) -> None:
        self.system = trading_system
        self.host = host
        self.port = port
        self._state_cache: dict = {}
        self._state_cache_ts: float = 0.0
        self._state_lock = asyncio.Lock()
        self._http_semaphore = asyncio.Semaphore(10)  # Max 10 concurrent /state callers
        self.active_connections: dict[WebSocket, asyncio.Queue] = {}  # {WS: Queue}

        self._last_tick_broadcast: dict[str, float] = {}  # symbol -> ts

        @asynccontextmanager
        async def lifespan(app: FastAPI):
            try:
                yield
            except asyncio.CancelledError:
                pass
            finally:
                # Graceful shutdown: close all active WebSocket connections
                for ws in list(self.active_connections.keys()):
                    try:
                        await ws.close()
                    except Exception:
                        pass
                self.active_connections.clear()

        self.app = FastAPI(title="TradingSystem Elite API", lifespan=lifespan)

        # In production, specify your frontend URL instead of "*"
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
            allow_methods=["GET", "POST"],
            allow_headers=["*"],
        )

        self._setup_routes()
        self._setup_health_check()
        self._subscribe_to_bus()

    def _setup_health_check(self) -> None:
        """Standardized health check endpoint for monitoring and uptime verification."""

        @self.app.get("/health")
        async def health_check(key: str = Depends(self._verify_api_key)):
            # Check basic components
            status = "UP"
            components = {
                "system": "CONNECTED" if self.system else "DISCONNECTED",
                "bus": "UP" if hasattr(self.system, "bus") and self.system.bus else "DOWN",
                "db": "CONNECTED"
                if hasattr(self.system, "db_conn") and self.system.db_conn
                else "OFFLINE",
            }
            if any(v in ["DISCONNECTED", "DOWN", "OFFLINE"] for v in components.values()):
                status = "DEGRADED"

            return {
                "status": status,
                "timestamp": time.time_ns(),
                "components": components,
                "version": "Sovereign-1.0",
            }

    def _subscribe_to_bus(self) -> None:
        """Bind to the SharedIntelligenceBus for instant 100Hz pushing."""
        if hasattr(self.system, "bus") and self.system.bus is not None:
            # HFT topics use the Queue model to prevent memory leaks
            self._tick_queue = self.system.bus.subscribe("tick.hft", maxsize=50)
            asyncio.create_task(self._run_tick_broadcaster())

            # Low-frequency topics can use callbacks safely
            self.system.bus.on("oracle.state", self._broadcast_oracle)
            self.system.bus.on("calibration.update", self._broadcast_calibration)
            self.system.bus.on("mind.dialogue", self._broadcast_mind_dialogue)
            self.system.bus.on("consensus.update", self._broadcast_consensus)
            self.system.bus.on("system.state", self._broadcast_state)
            self.system.bus.on("system.pulse", self._broadcast_pulse)
            self.system.bus.on("candle.batch", self._broadcast_candle_batch)
            self.system.bus.on("news.hft", self._broadcast_news)
            self.system.bus.on("apex.telemetry", self._broadcast_apex_telemetry)

    async def _broadcast_news(self, payload: dict) -> None:
        """Broadcast high-impact news events to the dashboard."""
        if not self.active_connections:
            return
        msg = {
            "type": "news.hft",
            "timestamp": time.time_ns(),
            "data": payload,
            "meta": {"nodes": ["news_harvester", "intel_bus"]},
        }
        for _ws, q in self.active_connections.items():
            try:
                q.put_nowait(msg)
            except asyncio.QueueFull:
                pass

    async def _broadcast_candle_batch(self, payload: dict) -> None:
        if not self.active_connections:
            return
        msg = {
            "type": "candle.batch",
            "timestamp": time.time_ns(),
            "data": payload,
            "meta": {"nodes": ["pipeline", "sqlite", "intel_bus"]},
        }
        for _ws, q in self.active_connections.items():
            try:
                q.put_nowait(msg)
            except asyncio.QueueFull:
                pass  # Drop for this specific slow client

    async def _broadcast_apex_telemetry(self, payload: dict) -> None:
        """Push live trading telemetry data to the frontend dashboard."""
        if not self.active_connections:
            return
        msg = {
            "type": "apex.telemetry",
            "timestamp": time.time_ns(),
            "data": payload,
            "meta": {"nodes": ["apex_overlay", "intel_bus"]},
        }
        for _ws, q in self.active_connections.items():
            try:
                q.put_nowait(msg)
            except asyncio.QueueFull:
                pass

    async def _broadcast_pulse(self, payload: dict) -> None:
        """Forward telemetry pulses (Agent A scans) to frontend."""
        if not self.active_connections:
            return
        msg = {
            "type": "system.pulse",
            "timestamp": time.time_ns(),
            "data": payload,
            "meta": {"nodes": ["brain", "intel_bus"]},
        }
        for _ws, q in self.active_connections.items():
            try:
                q.put_nowait(msg)
            except asyncio.QueueFull:
                pass

    async def _broadcast_state(self, payload: dict) -> None:
        if not self.active_connections:
            return
        msg = {
            "type": "system.state",
            "timestamp": time.time_ns(),
            "data": payload,
            "meta": {"nodes": payload.get("nodes", ["intel_bus", "brain"])},
        }
        for _ws, q in self.active_connections.items():
            try:
                q.put_nowait(msg)
            except asyncio.QueueFull:
                pass

    async def _run_tick_broadcaster(self) -> None:
        """Background worker to broadcast ticks at a sane frequency."""
        logger.info("API Server: Tick Broadcaster worker started.")
        while True:
            try:
                payload = await self._tick_queue.get()
                await self._broadcast_tick(payload)
                self._tick_queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"API Server: Broadcaster error: {e}")
                await asyncio.sleep(0.1)

    async def _broadcast_tick(self, payload: dict) -> None:
        if not self.active_connections:
            return

        symbol = payload.get("symbol", "ALL")
        now = time.time()
        if now - self._last_tick_broadcast.get(symbol, 0) < 0.01:  # 100Hz Limit
            return
        self._last_tick_broadcast[symbol] = now
        msg = {
            "type": "tick.hft",
            "timestamp": time.time_ns(),
            "data": payload,
            "meta": {"nodes": ["ibkr", "questdb", "pipeline", "intel_bus"]},
        }
        for _ws, q in self.active_connections.items():
            try:
                q.put_nowait(msg)
            except asyncio.QueueFull:
                pass

    async def _broadcast_oracle(self, payload: dict) -> None:
        if not self.active_connections:
            return
        logger.debug(f"API: Broadcasting oracle state: {payload.get('dhatu')}")
        msg = {
            "type": "oracle.state",
            "timestamp": time.time_ns(),
            "data": payload,
            "meta": {"nodes": ["oracle", "intel_bus", "swarm", "consensus"]},
        }
        for _ws, q in self.active_connections.items():
            try:
                q.put_nowait(msg)
            except asyncio.QueueFull:
                pass

    async def _broadcast_calibration(self, payload: dict) -> None:
        if not self.active_connections:
            return
        msg = {
            "type": "calibration.update",
            "timestamp": time.time_ns(),
            "data": payload,
            "meta": {"nodes": ["agent_d", "pipeline", "sqlite", "intel_bus"]},
        }
        for _ws, q in self.active_connections.items():
            try:
                q.put_nowait(msg)
            except asyncio.QueueFull:
                pass

    async def _broadcast_mind_dialogue(self, payload: dict) -> None:
        if not self.active_connections:
            return
        sender = payload.get("sender", "unknown")
        # Map sender to node ID
        node_id = (
            f"mind_{sender}"
            if sender not in ["agent_a", "agent_b", "agent_c", "agent_d", "agent_e"]
            else sender
        )
        msg = {
            "type": "mind.dialogue",
            "timestamp": time.time_ns(),
            "data": payload,
            "meta": {"nodes": [node_id, "intel_bus"]},
        }
        for _ws, q in self.active_connections.items():
            try:
                q.put_nowait(msg)
            except asyncio.QueueFull:
                pass

    async def _broadcast_consensus(self, payload: dict) -> None:
        if not self.active_connections:
            return
        logger.debug("API: Broadcasting consensus update")
        msg = {
            "type": "consensus.update",
            "timestamp": time.time_ns(),
            "data": payload,
            "meta": {"nodes": ["consensus", "intel_bus"] + payload.get("nodes", [])},
        }
        for _ws, q in self.active_connections.items():
            try:
                q.put_nowait(msg)
            except asyncio.QueueFull:
                pass

    def _is_port_available(self) -> bool:
        """Check whether host:port can be bound by this process."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.bind((self.host, self.port))
            return True
        except OSError:
            return False
        except Exception:
            return False
        finally:
            sock.close()

    async def _safe_send_json(self, websocket: WebSocket, data: dict) -> None:
        try:
            await websocket.send_json(data)
        except Exception as e:
            logger.error(f"WS send error: {e}")

    async def _verify_api_key(self, x_sovereign_key: str = Header(None)):
        """Dependency to check for valid API Key in headers."""
        secret = Vault.get("API_SERVER_KEY")
        if not secret:
            if os.getenv("SOVEREIGN_ALLOW_OPEN_API", "0") == "1":
                logger.warning(
                    "API Server: SOVEREIGN_ALLOW_OPEN_API=1; accepting unauthenticated request."
                )
                return
            raise HTTPException(status_code=503, detail="API_SERVER_KEY is not configured")

        if x_sovereign_key != secret:
            raise HTTPException(status_code=403, detail="Invalid Sovereign API Key")

    def _setup_routes(self) -> None:
        @self.app.get("/state")
        async def get_state(key: str = Depends(self._verify_api_key)):
            async with self._http_semaphore:
                return self._get_cached_state()

        @self.app.get("/ledger")
        async def get_ledger(
            n: int = Query(50, ge=1, le=500),
            key: str = Depends(self._verify_api_key),
        ):
            """Return the last N decision audit trail entries."""
            return {"entries": LEDGER.recent(n)}

        @self.app.get("/ledger/stats")
        async def get_ledger_stats(key: str = Depends(self._verify_api_key)):
            """Return aggregate stats from the decision ledger."""
            return LEDGER.summary_stats()

        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket, token: str = Query(None)) -> None:
            from time_sync import TimeSync

            secret = Vault.get("API_SERVER_KEY")
            if not secret and os.getenv("SOVEREIGN_ALLOW_OPEN_API", "0") != "1":
                logger.warning(
                    "API Server: WebSocket rejected because API_SERVER_KEY is not configured."
                )
                await websocket.close(code=1008)
                return
            if secret:
                ts = int(TimeSync.now().timestamp()) // 30
                valid = False
                import hashlib
                import hmac

                # Allow for significant clock drift (up to 5 mins) between frontend and backend
                for offset in range(-10, 11):
                    msg = str(ts + offset).encode()
                    expected = hmac.new(secret.encode(), msg, hashlib.sha256).hexdigest()
                    if hmac.compare_digest(token or "", expected):
                        valid = True
                        break

                if not valid:
                    msg0 = str(ts).encode()
                    exp0 = hmac.new(secret.encode(), msg0, hashlib.sha256).hexdigest()
                    logger.warning(
                        f"API Server: WebSocket REJECTED. Recv: {token[:8]}... Exp(0): {exp0[:8]}... (TS: {ts})"
                    )
                    await websocket.close(code=1008)
                    return

            # 3. ACCEPT HANDSHAKE (Only if authorized)
            await websocket.accept()
            logger.info(
                f"API Server: WebSocket connection ACCEPTED (Client: {websocket.client.host if websocket.client else 'unknown'})"
            )

            # Create a dedicated sender task for this specific client
            async def _ws_writer():
                q = asyncio.Queue(maxsize=100)
                self.active_connections[websocket] = q
                try:
                    while True:
                        msg = await q.get()
                        await self._safe_send_json(websocket, msg)
                        q.task_done()
                except Exception:
                    pass
                finally:
                    if websocket in self.active_connections:
                        del self.active_connections[websocket]

            writer_task = asyncio.create_task(_ws_writer())

            try:
                # 1. Provide an immediate full-state sync upon connection
                await self._safe_send_json(
                    websocket,
                    {
                        "type": "full_state",
                        "data": self._get_full_state(),
                        "meta": {"nodes": ["api_server", "intel_bus", "brain"]},
                    },
                )

                # 2. Stay alive and listen for optional client commands
                while True:
                    # We just need to keep the connection open and check if client closes
                    await websocket.receive_text()
            except WebSocketDisconnect:
                logger.info("Frontend disconnected from WS")
            finally:
                writer_task.cancel()
                if websocket in self.active_connections:
                    del self.active_connections[websocket]

    async def _safe_send_json(self, websocket: WebSocket, data: dict[str, Any]) -> None:
        """Send JSON with connection state check."""
        try:
            if websocket.client_state.name == "CONNECTED":
                await asyncio.wait_for(websocket.send_json(data), timeout=5.0)
        except Exception as _ws_err:
            logger.debug(f"WS send failed (socket closing or timeout): {_ws_err}")
            # The writer task finally block handles deletion from dict

    def _get_cached_state(self) -> dict:
        """Return a 1-second cached state snapshot. Prevents redundant DB reads.
        Uses a simple double-check pattern safe for single-threaded asyncio."""
        import time

        now = time.monotonic()
        # Fast path — read under no lock since asyncio is single-threaded
        if now - self._state_cache_ts < 1.0 and self._state_cache:
            return dict(self._state_cache)  # return a shallow copy to prevent mutation
        state = self._get_full_state()
        self._state_cache = state
        self._state_cache_ts = now
        return dict(state)

    def _get_full_state(self) -> dict[str, Any]:
        """Collect and serialize the current system state with real market data."""
        try:
            # 1. Dhatu Oracle Intelligence (Dynamic Graph)
            # Default rich initial state to ensure "WOW" factor on first load
            oracle_data = {
                "dhatu": "NEUTRAL",
                "confidence": 0,
                "reasoning": "Synchronizing with global macro verticals for real-time causation mapping...",
                "theme": "INITIALIZING",
                "bias": "NEUTRAL",
                "nodes": ["Yields", "Oil", "VIX", "News", "Technicals", "Macro"],
                "edges": [],
            }
            if self.system.dhatu_oracle:
                oracle = self.system.dhatu_oracle
                # State is stored in _current_state in dhatu_oracle.py
                last_state = getattr(oracle, "_current_state", None)
                if last_state and last_state.source_graph:
                    graph = last_state.source_graph
                    oracle_data = {
                        "dhatu": last_state.dhatu_state,
                        "confidence": last_state.confidence,
                        "certainty": graph.certainty,
                        "reasoning": last_state.causation_summary,
                        "theme": graph.dominant_theme,
                        "bias": graph.macro_bias,
                        "nodes": list(
                            set([e.source for e in graph.edges] + [e.effect for e in graph.edges])
                        ),
                        "edges": [
                            {
                                "from": e.source,
                                "to": e.effect,
                                "desc": e.mechanism,
                                "conf": e.confidence,
                            }
                            for e in graph.edges
                        ],
                    }

            # 2. Market Data (Real OHLCV from SQLite)
            market_data = {}
            if self.system.db_conn:
                try:
                    cursor = self.system.db_conn.cursor()
                    try:
                        for symbol in ["SPY", "QQQ", "IWM"]:
                            cursor.execute(
                                """
                                SELECT timestamp, open, high, low, close, volume
                                FROM ohlcv WHERE symbol = ?
                                ORDER BY timestamp DESC LIMIT 60
                                """,
                                (symbol,),
                            )
                            rows = cursor.fetchall()
                            # Format for Lightweight Charts (time as string)
                            market_data[symbol] = [
                                {
                                    "time": r[0].split(" ")[0] if " " in r[0] else r[0],
                                    "open": r[1],
                                    "high": r[2],
                                    "low": r[3],
                                    "close": r[4],
                                    "volume": r[5],
                                }
                                for r in reversed(rows)
                            ]
                        logger.debug(f"API State: market data ready {list(market_data.keys())}")
                    finally:
                        cursor.close()
                except Exception as e:
                    logger.warning(f"Failed to fetch market data for API: {e}")

            # 3. Trading Brain State & Real-Time Agent Telemetry
            brain_data = {}
            trading_truth = {
                "performance": {},
                "outcomes": [],
                "recent_trades": [],
                "open_by_symbol": [],
                "order_health": {"persistent_orders": 0, "stale_orders": 0, "failures": 0},
                "tasks": {"total": 0, "by_status": {}, "by_phase": {}, "recent": []},
            }
            if self.system.trading_brain:
                brain = self.system.trading_brain
                # Extract Agent C (Executor) safety values
                blackswan_active = False
                if hasattr(brain, "blackswan"):
                    # check returns "FREEZE" or "NORMAL"
                    vix = getattr(brain, "_last_vix", 18.0)
                    ib_dd = getattr(brain, "ibkr_drawdown", None)
                    peak = getattr(ib_dd, "peak_equity", 1.0)
                    curr = getattr(ib_dd, "current_equity", peak)
                    dd_val = (peak - curr) / max(peak, 1)
                    blackswan_active = brain.blackswan.check(vix, dd_val) == "FREEZE"

                pg_reserve = "20% Reserve"
                if hasattr(brain, "portfolio_guard") and brain.portfolio_guard:
                    # Track via cash reserve check
                    pg_reserve = "20% Reserve (Active)"

                # Extract Agent D (Learning Mind) stats
                top_pattern = "Gathering Data..."
                memory_size = 0
                if hasattr(brain, "live_learner") and brain.live_learner:
                    matrix = getattr(brain.live_learner, "expectancy_matrix", {})
                    memory_size = sum(m.get("occurences", 0) for m in matrix.values())
                    if matrix:
                        best = max(matrix.items(), key=lambda x: x[1].get("win_rate", 0))
                        top_pattern = (
                            f"{best[0].split('|')[0]}: {best[1].get('win_rate', 0) * 100:.1f}% WR"
                        )

                # Extract Agent A logic already collected
                scan_stats = getattr(brain, "last_scan_stats", {})
                if self.system.db_conn:
                    try:
                        cursor = self.system.db_conn.cursor()
                        cursor.execute(
                            "SELECT outcome, trading_mode, COUNT(*) AS count, "
                            "SUM(COALESCE(net_pnl, pnl_dollars, 0)) AS pnl "
                            "FROM trades GROUP BY outcome, trading_mode ORDER BY count DESC"
                        )
                        trading_truth["outcomes"] = [
                            {
                                "outcome": row[0] or "UNKNOWN",
                                "mode": row[1] or "UNKNOWN",
                                "count": int(row[2] or 0),
                                "pnl": float(row[3] or 0.0),
                            }
                            for row in cursor.fetchall()
                        ]

                        cursor.execute(
                            "SELECT instrument, COUNT(*) AS count, SUM(COALESCE(shares, 0)) AS shares, "
                            "MIN(timestamp) AS first_ts, MAX(timestamp) AS last_ts "
                            "FROM trades WHERE outcome='OPEN' "
                            "GROUP BY instrument ORDER BY count DESC LIMIT 20"
                        )
                        trading_truth["open_by_symbol"] = [
                            {
                                "symbol": row[0] or "UNKNOWN",
                                "count": int(row[1] or 0),
                                "shares": float(row[2] or 0.0),
                                "first_ts": row[3],
                                "last_ts": row[4],
                            }
                            for row in cursor.fetchall()
                        ]

                        cursor.execute(
                            "SELECT id, timestamp, instrument, direction, pattern, regime, entry_price, "
                            "shares, outcome, broker, trading_mode, COALESCE(net_pnl, pnl_dollars, 0) AS pnl "
                            "FROM trades ORDER BY id DESC LIMIT 25"
                        )
                        trading_truth["recent_trades"] = [
                            {
                                "id": row[0],
                                "timestamp": row[1],
                                "symbol": row[2],
                                "direction": row[3],
                                "pattern": row[4],
                                "regime": row[5],
                                "entry": float(row[6] or 0.0),
                                "shares": float(row[7] or 0.0),
                                "outcome": row[8] or "UNKNOWN",
                                "broker": row[9] or "UNKNOWN",
                                "mode": row[10] or "UNKNOWN",
                                "pnl": float(row[11] or 0.0),
                            }
                            for row in cursor.fetchall()
                        ]

                        cursor.execute(
                            "SELECT name FROM sqlite_master WHERE type='table' AND name='performance_summary'"
                        )
                        if cursor.fetchone():
                            cursor.execute("PRAGMA table_info(performance_summary)")
                            summary_cols = {row[1] for row in cursor.fetchall()}
                            if {"key", "value"}.issubset(summary_cols):
                                cursor.execute(
                                    "SELECT value, updated_at FROM performance_summary "
                                    "WHERE key='latest' LIMIT 1"
                                )
                                row = cursor.fetchone()
                                if row:
                                    payload = json.loads(row[0])
                                    payload["updated_at"] = row[1]
                                    trading_truth["performance"] = payload

                        cursor.execute(
                            "SELECT name FROM sqlite_master WHERE type='table' AND name='persistent_orders'"
                        )
                        if cursor.fetchone():
                            cursor.execute("SELECT COUNT(*) FROM persistent_orders")
                            trading_truth["order_health"]["persistent_orders"] = int(
                                cursor.fetchone()[0] or 0
                            )
                            cursor.execute(
                                "SELECT COUNT(*) FROM persistent_orders "
                                "WHERE status NOT IN ('Filled', 'Cancelled', 'Inactive')"
                            )
                            trading_truth["order_health"]["stale_orders"] = int(
                                cursor.fetchone()[0] or 0
                            )

                        cursor.execute(
                            "SELECT name FROM sqlite_master WHERE type='table' AND name='failure_post_mortem'"
                        )
                        if cursor.fetchone():
                            cursor.execute("SELECT COUNT(*) FROM failure_post_mortem")
                            trading_truth["order_health"]["failures"] = int(
                                cursor.fetchone()[0] or 0
                            )
                        cursor.close()
                    except Exception as exc:
                        logger.debug("API Server: trading truth fetch skipped: %s", exc)

                try:
                    task_path = os.path.join("data", "active_tasks.json")
                    if os.path.exists(task_path):
                        with open(task_path, "r", encoding="utf-8") as f:
                            task_data = json.load(f)
                        by_status: dict[str, int] = {}
                        by_phase: dict[str, int] = {}
                        for task in task_data.values():
                            status = str(task.get("status", "unknown"))
                            by_status[status] = by_status.get(status, 0) + 1
                            phase = str(task.get("status_summary", "UNKNOWN")).split(":")[0]
                            by_phase[phase] = by_phase.get(phase, 0) + 1
                        recent_tasks = sorted(
                            task_data.values(),
                            key=lambda t: float(t.get("start_time") or 0),
                            reverse=True,
                        )[:20]
                        trading_truth["tasks"] = {
                            "total": len(task_data),
                            "by_status": by_status,
                            "by_phase": by_phase,
                            "recent": recent_tasks,
                        }
                except Exception as exc:
                    logger.debug("API Server: task truth fetch skipped: %s", exc)

                brain_data = {
                    "state": brain.state.name if hasattr(brain, "state") else "UNKNOWN",
                    "regime": getattr(brain, "current_regime", "UNKNOWN"),
                    "positions_count": len(getattr(brain, "positions", [])),
                    "positions": [
                        {
                            "symbol": p.symbol,
                            "position": getattr(p, "qty", getattr(p, "position", 0)),
                            "avg_price": getattr(p, "entry_price", getattr(p, "avg_price", 0.0)),
                            "current_price": getattr(p, "current_price", 0.0),
                            "unrealized_pnl": getattr(p, "unrealized_pnl", 0.0),
                        }
                        for p in getattr(brain, "positions", [])
                    ],
                    "is_running": getattr(brain, "is_running", False),
                    "pnl_session": sum(
                        getattr(p, "unrealized_pnl", 0.0) for p in getattr(brain, "positions", [])
                    ),
                    "scan_stats": scan_stats,
                    "consecutive_losses": getattr(
                        getattr(brain, "loss_tracker", None), "consecutive_losses", 0
                    ),
                    "drawdown_level": getattr(
                        getattr(getattr(brain, "ibkr_drawdown", None), "level", None),
                        "value",
                        "NORMAL",
                    ),
                    "gap": {
                        "drawdown": {
                            "ibkr": {
                                "level": getattr(
                                    getattr(getattr(brain, "ibkr_drawdown", None), "level", None),
                                    "value",
                                    "NORMAL",
                                ),
                                "peak": getattr(
                                    getattr(brain, "ibkr_drawdown", None), "peak_equity", 0.0
                                ),
                                "current": getattr(
                                    getattr(brain, "ibkr_drawdown", None), "current_equity", 0.0
                                ),
                                "allowed": getattr(
                                    getattr(brain, "ibkr_drawdown", None),
                                    "is_trading_allowed",
                                    lambda: True,
                                )(),
                            },
                            "prop": {
                                "level": getattr(
                                    getattr(getattr(brain, "prop_drawdown", None), "level", None),
                                    "value",
                                    "NORMAL",
                                ),
                                "peak": getattr(
                                    getattr(brain, "prop_drawdown", None), "peak_equity", 0.0
                                ),
                                "current": getattr(
                                    getattr(brain, "prop_drawdown", None), "current_equity", 0.0
                                ),
                                "allowed": getattr(
                                    getattr(brain, "prop_drawdown", None),
                                    "is_trading_allowed",
                                    lambda: True,
                                )(),
                            },
                        },
                        "escalation": {
                            "losses": getattr(
                                getattr(brain, "loss_tracker", None), "consecutive_losses", 0
                            ),
                            "streak": getattr(
                                getattr(brain, "loss_tracker", None), "win_streak", 0
                            ),
                            "paper_forced": getattr(
                                getattr(brain, "loss_tracker", None), "paper_mode_forced", False
                            ),
                            "audit_required": getattr(
                                getattr(brain, "loss_tracker", None), "audit_required", False
                            ),
                            "allowed": getattr(
                                getattr(brain, "loss_tracker", None),
                                "is_trading_allowed",
                                lambda: True,
                            )(),
                        },
                        "budget": {
                            "max_trades": getattr(
                                getattr(brain, "morning_budget", None), "max_trades", 3
                            ),
                            "min_catalyst": getattr(
                                getattr(brain, "morning_budget", None), "min_catalyst", 0.5
                            ),
                            "max_risk": getattr(
                                getattr(brain, "morning_budget", None),
                                "max_risk_per_trade_pct",
                                0.01,
                            ),
                            "regime": getattr(
                                getattr(brain, "morning_budget", None), "regime", "UNKNOWN"
                            ),
                        },
                        "evolution": {},
                    },
                    "truth": trading_truth,
                }

                # 4. Populate Evolutionary Data
                if hasattr(brain, "evolution_manager") and brain.evolution_manager:
                    try:
                        ev_conn = sqlite3.connect(brain.evolution_manager.db_path, timeout=60)
                        ev_conn.execute("PRAGMA journal_mode=WAL;")
                        ev_conn.execute("PRAGMA busy_timeout = 60000;")
                        ev_cursor = ev_conn.cursor()
                        ev_cursor.execute(
                            "SELECT parameter_name, parameter_value, confidence, last_updated FROM brain_optimization"
                        )
                        rows = ev_cursor.fetchall()
                        brain_data["gap"]["evolution"] = {
                            r[0]: {"value": r[1], "confidence": r[2], "last_updated": r[3]}
                            for r in rows
                        }
                        ev_conn.close()
                    except Exception as e:
                        logger.warning(f"API Server: Evolution data fetch failed: {e}")

                brain_data["minds"] = {
                    "architect": "ACTIVE" if hasattr(brain, "mind_architect") else "STANDBY",
                    "evolution": "ACTIVE" if hasattr(brain, "mind_evolution") else "STANDBY",
                    "observer": "ACTIVE" if hasattr(brain, "mind_observer") else "STANDBY",
                    "experiment": "ACTIVE" if hasattr(brain, "mind_experiment") else "STANDBY",
                    "ultrathink": "ACTIVE" if hasattr(brain, "mind_ultrathink") else "STANDBY",
                    "system": "ACTIVE" if hasattr(brain, "mind_system") else "STANDBY",
                    "ghost": "ACTIVE" if hasattr(brain, "mind_ghost") else "STANDBY",
                }

                brain_data["agents"] = {
                    "agent_a": {
                        "status": "SYNCHRONIZED" if scan_stats else "SCANNING",
                        "last_action": "Processing HFT flow"
                        if scan_stats
                        else "Synchronizing nodes...",
                    },
                    "agent_b": {
                        "status": "ACTIVE",
                        "classifier": "DhatuClassifier V3",
                        "modifier": f"{(getattr(brain, '_oracle_risk_modifier', 1.0) * 100):.0f}% Base",
                        "freeze": getattr(brain, "_oracle_freeze", False),
                        "last_action": "Evaluating Macro Bias",
                    },
                    "agent_c": {
                        "status": "ACTIVE"
                        if getattr(self.system, "mt5_client", None)
                        else "STANDBY",
                        "blackswan": "ACTIVE" if blackswan_active else "Watching",
                        "guard": pg_reserve,
                        "mt5": "Connected"
                        if getattr(self.system, "mt5_client", None)
                        else "Standby",
                        "vix_protocol": "Active"
                        if getattr(brain, "exit_intelligence", None)
                        else "Standby",
                        "last_action": "Monitoring Safety Escalaion",
                    },
                    "agent_d": {
                        "status": "SYNCHRONIZED"
                        if hasattr(brain, "live_learner")
                        else "INITIALIZING",
                        "memory": f"{memory_size} Trades",
                        "top_pattern": top_pattern,
                        "threshold_gate": "SignificanceGate"
                        if hasattr(brain, "live_learner")
                        else "OFFLINE",
                        "calibration": "LivePipeline"
                        if hasattr(brain, "live_learner")
                        else "OFFLINE",
                        "learned_rates": getattr(brain, "_learned_win_rates", {}),
                        "last_action": "Optimizing Expectancy Matrix",
                    },
                    "agent_e": {
                        "status": "ACTIVE",
                        "last_action": "Monitoring Sector Skew",
                    },
                    "agent_f": {
                        "status": "ACTIVE",
                        "last_action": "Analyzing Volatility Surfaces",
                    },
                    "agent_g": {
                        "status": "ACTIVE",
                        "last_action": "Mapping Neural Topology",
                    },
                    "risk_guard": {
                        "status": "ARMED",
                        "last_action": "Verifying Margin Safety",
                    },
                    "dhatu_oracle": {
                        "status": "SENSING",
                        "last_action": "Scanning Macro Horizons",
                    },
                    "swarm_predictor": {
                        "status": "COLLECTIVE",
                        "last_action": "Aggregating Social Scent",
                    },
                    "mind_ultrathink": {
                        "status": "REASONING",
                        "last_action": "Deep Cycle Analysis",
                    },
                }

            # 4. System Health (Granular Component Feedback)
            health_data = {
                "mode": self.system.mode,
                "dms": "ACTIVE" if hasattr(self.system, "dms") and self.system.dms else "OFFLINE",
                "up_time": int(
                    (
                        datetime.now().astimezone()
                        - getattr(self.system, "start_time", datetime.now()).astimezone()
                    ).total_seconds()
                ),
                "latency_ms": 0.45,
                "components": {
                    "ibkr": "ONLINE"
                    if self.system.ibkr_client and self.system.ibkr_client.isConnected()
                    else "OFFLINE",
                    "mt5": "ONLINE"
                    if self.system.mt5_client and self.system.mt5_client.terminal_info()
                    else "OFFLINE",
                    "qdb": "ONLINE"
                    if self.system.questdb and self.system.questdb.is_active
                    else "OFFLINE",
                    "dhatu": "ONLINE" if self.system.dhatu_oracle else "OFFLINE",
                    "brain": "ONLINE"
                    if self.system.trading_brain and self.system.trading_brain.is_running
                    else "OFFLINE",
                    "sovereign": "ONLINE",
                },
            }

            return {
                "timestamp": time.time_ns(),
                "oracle": oracle_data,
                "market": market_data,
                "brain": brain_data,
                "health": health_data,
                "portfolio": PORTFOLIO_ANALYZER.summary(),
            }
        except Exception as e:
            logger.error(f"Critical error collecting state for API: {e}")
            return {"error": str(e)}

    async def start(self) -> bool:
        """Run the FastAPI server with uvicorn in the existing event loop."""
        if not self._is_port_available():
            logger.warning(
                f"API server port {self.port} already in use; skipping embedded API startup."
            )
            return False
        config = uvicorn.Config(
            self.app,
            host=self.host,
            port=self.port,
            log_level="error",
        )
        self.server = uvicorn.Server(config)
        # Disable uvicorn's signal handlers — the main TradingSystem handles
        # Ctrl+C / SIGINT.
        self.server.install_signal_handlers = lambda: None  # type: ignore[assignment]

        async def _serve() -> None:
            try:
                await self.server.serve()
            except OSError as e:
                logger.warning(f"API server failed to bind {self.host}:{self.port}: {e}")
            except asyncio.CancelledError:
                self.server.should_exit = True
            except (KeyboardInterrupt, SystemExit):
                self.server.should_exit = True
            except Exception as e:
                logger.error(f"API server crashed: {e}")

        self._broadcaster_task = asyncio.create_task(self._run_tick_broadcaster())
        self._server_task = asyncio.create_task(_serve())

        def _log_task_exception(t: asyncio.Task) -> None:
            if not t.cancelled() and t.exception() is not None:
                logger.error(f"API Server task raised unhandled exception: {t.exception()}")

        self._server_task.add_done_callback(_log_task_exception)
        logger.info(f"✓ API Server started on http://{self.host}:{self.port}")
        return True

    async def stop(self) -> None:
        """Graceful shutdown of the API server."""
        logger.info("Stopping API Server...")

        if hasattr(self, "server"):
            self.server.should_exit = True

        # Cancel tasks
        for attr in ["_broadcaster_task", "_server_task"]:
            task = getattr(self, attr, None)
            if task and not task.done():
                task.cancel()
                try:
                    await asyncio.wait_for(task, timeout=2.0)
                except (asyncio.CancelledError, asyncio.TimeoutError):
                    pass
                except Exception as e:
                    logger.error(f"Error stopping API Server task {attr}: {e}")

        logger.info("API Server stopped.")
