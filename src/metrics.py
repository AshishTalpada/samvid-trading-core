"""
src/metrics.py
Structured metrics emission for the Sovereign Trading System (Phase 4).

Provides a single CollectorRegistry (REGISTRY) containing all Prometheus
metrics.  An optional HTTP server can expose /metrics on a configurable port.

Usage
─────
Import and update metrics from any module:

    from metrics import METRICS
    METRICS.trades_total.labels(broker="IBKR", outcome="WIN").inc()
    METRICS.open_positions.set(len(brain.positions))
    METRICS.daily_pnl_dollars.set(brain.session_pnl)

Expose the scrape endpoint (call once at startup):

    from metrics import start_metrics_server
    start_metrics_server(port=8000)          # default port

Generate Prometheus text for embedding in existing API:

    from metrics import generate_latest_text
    text = generate_latest_text()            # returns bytes
"""

from __future__ import annotations

import logging
import threading
from typing import Any

from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
    start_http_server,
    REGISTRY as _DEFAULT_REGISTRY,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Use the default global registry so standard process collectors
# (gc, memory, cpu) are included automatically.
# ---------------------------------------------------------------------------
REGISTRY: CollectorRegistry = _DEFAULT_REGISTRY

_LATENCY_BUCKETS = (0.001, 0.005, 0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)


class TradingMetrics:
    """Container for all Sovereign trading metrics.

    All metrics use the ``sovereign_`` prefix and are registered on the
    global Prometheus registry.  Instantiate once via the module-level
    ``METRICS`` singleton.
    """

    def __init__(self) -> None:
        # ── Trade lifecycle ────────────────────────────────────────────
        self.trades_total = Counter(
            "sovereign_trades_total",
            "Cumulative number of trades executed",
            ["broker", "direction", "outcome"],
        )

        self.trade_pnl_dollars = Histogram(
            "sovereign_trade_pnl_dollars",
            "Per-trade P&L in CAD dollars (net)",
            ["broker"],
            buckets=(-500, -200, -100, -50, -10, 0, 10, 50, 100, 200, 500, 1000, 2000),
        )

        self.trade_r_multiple = Histogram(
            "sovereign_trade_r_multiple",
            "Per-trade R-multiple (P&L / initial risk)",
            ["broker"],
            buckets=(-3.0, -2.0, -1.0, -0.5, 0.0, 0.5, 1.0, 1.5, 2.0, 3.0, 5.0, 10.0),
        )

        # ── Session P&L / drawdown ─────────────────────────────────────
        self.daily_pnl_dollars = Gauge(
            "sovereign_daily_pnl_dollars",
            "Running daily P&L in CAD dollars",
            ["broker"],
        )

        self.session_pnl_dollars = Gauge(
            "sovereign_session_pnl_dollars",
            "Cumulative session P&L in CAD dollars",
        )

        self.drawdown_pct = Gauge(
            "sovereign_drawdown_pct",
            "Current drawdown as a fraction of peak equity (0.0–1.0)",
            ["broker"],
        )

        self.peak_equity_dollars = Gauge(
            "sovereign_peak_equity_dollars",
            "Peak NAV reached (high-water mark) in CAD dollars",
            ["broker"],
        )

        # ── Position state ─────────────────────────────────────────────
        self.open_positions = Gauge(
            "sovereign_open_positions",
            "Number of currently open positions",
        )

        self.position_unrealized_pnl = Gauge(
            "sovereign_position_unrealized_pnl_dollars",
            "Aggregate unrealized P&L across all open positions in CAD",
        )

        # ── Risk / regime ──────────────────────────────────────────────
        self.vix_level = Gauge(
            "sovereign_vix_level",
            "Latest VIX reading",
        )

        self.risk_modifier = Gauge(
            "sovereign_risk_modifier",
            "Current oracle-driven risk modifier (0.0–1.0+)",
        )

        self.belief_score = Gauge(
            "sovereign_belief_score",
            "Current Bayesian conviction score (0.0–0.9 hard cap per F17)",
        )

        self.regime = Gauge(
            "sovereign_regime_info",
            "Current market regime (label-encoded)",
            ["regime"],
        )

        # ── Order execution latency ────────────────────────────────────
        self.order_latency_seconds = Histogram(
            "sovereign_order_latency_seconds",
            "Time from signal approval to order submission (seconds)",
            ["broker", "order_type"],
            buckets=_LATENCY_BUCKETS,
        )

        # ── Scan cycle performance ─────────────────────────────────────
        self.scan_cycle_duration_seconds = Histogram(
            "sovereign_scan_cycle_duration_seconds",
            "Duration of each full scan cycle (seconds)",
            buckets=_LATENCY_BUCKETS,
        )

        self.scan_symbols_processed = Counter(
            "sovereign_scan_symbols_processed_total",
            "Number of symbols processed through the scan loop",
        )

        self.signals_approved = Counter(
            "sovereign_signals_approved_total",
            "Number of trade signals approved by the gating chain",
            ["broker", "pattern"],
        )

        self.signals_rejected = Counter(
            "sovereign_signals_rejected_total",
            "Number of trade signals rejected",
            ["reason"],
        )

        # ── Broker connectivity ────────────────────────────────────────
        self.broker_connected = Gauge(
            "sovereign_broker_connected",
            "Broker connection state (1 = connected, 0 = disconnected)",
            ["broker"],
        )

        # ── System health ──────────────────────────────────────────────
        self.emergency_halt_active = Gauge(
            "sovereign_emergency_halt_active",
            "1 if the system is in emergency halt state, 0 otherwise",
        )

        self.ftmo_trades_today = Gauge(
            "sovereign_ftmo_trades_today",
            "Number of trades executed today against the FTMO 2-trade daily limit",
        )

    # ── Convenience helpers ────────────────────────────────────────────────

    def record_trade(
        self,
        *,
        broker: str,
        direction: str,
        outcome: str,
        pnl: float,
        r_multiple: float,
    ) -> None:
        """Record a completed trade result."""
        self.trades_total.labels(
            broker=broker, direction=direction, outcome=outcome
        ).inc()
        self.trade_pnl_dollars.labels(broker=broker).observe(pnl)
        self.trade_r_multiple.labels(broker=broker).observe(r_multiple)

    def update_from_brain(self, brain: Any) -> None:
        """Bulk-update all position/risk gauges from a TradingBrain instance.

        Designed to be called periodically (e.g. every 30s) from the scan loop.
        All attribute access is guarded so the function never raises.
        """
        # Open positions
        try:
            positions = getattr(brain, "positions", [])
            self.open_positions.set(len(positions))
            total_upnl = sum(getattr(p, "unrealized_pnl", 0.0) for p in positions)
            self.position_unrealized_pnl.set(total_upnl)
        except Exception as exc:
            logger.warning("metrics.update_from_brain: positions: %s", exc)

        # Session P&L
        try:
            self.session_pnl_dollars.set(float(getattr(brain, "session_pnl", 0.0)))
        except Exception as exc:
            logger.warning("metrics.update_from_brain: session_pnl: %s", exc)

        # Risk modifier & belief
        try:
            self.risk_modifier.set(float(getattr(brain, "_oracle_risk_modifier", 1.0)))
        except Exception as exc:
            logger.debug("metrics.update_from_brain: risk_modifier: %s", exc)

        try:
            tracker = getattr(brain, "belief_tracker", None)
            if tracker is not None:
                self.belief_score.set(float(getattr(tracker, "current_belief", 0.5)))
        except Exception as exc:
            logger.debug("metrics.update_from_brain: belief: %s", exc)

        # Regime label gauge (set the current regime to 1, others to 0)
        try:
            current_regime = str(getattr(brain, "current_regime", "UNKNOWN"))
            for r in ("BULL", "BEAR", "VOLATILE", "CHOPPY", "TRENDING", "UNKNOWN"):
                self.regime.labels(regime=r).set(1.0 if r == current_regime else 0.0)
        except Exception as exc:
            logger.debug("metrics.update_from_brain: regime: %s", exc)

        # Drawdown
        try:
            ibkr_dd = getattr(brain, "ibkr_drawdown", None)
            if ibkr_dd is not None:
                dd_pct = getattr(ibkr_dd, "current_drawdown_pct", 0.0)
                peak = getattr(ibkr_dd, "peak_equity", 0.0)
                self.drawdown_pct.labels(broker="IBKR").set(float(dd_pct))
                self.peak_equity_dollars.labels(broker="IBKR").set(float(peak))
        except Exception as exc:
            logger.debug("metrics.update_from_brain: ibkr_drawdown: %s", exc)

        # Emergency halt
        try:
            halted = getattr(brain, "emergency_halted", False)
            self.emergency_halt_active.set(1.0 if halted else 0.0)
        except Exception as exc:
            logger.debug("metrics.update_from_brain: emergency_halt: %s", exc)

        # Broker connectivity
        try:
            ibkr_conn = getattr(brain, "ibkr_conn", None)
            if ibkr_conn is not None:
                connected = 1.0 if ibkr_conn.is_connected() else 0.0
                self.broker_connected.labels(broker="IBKR").set(connected)
        except Exception as exc:
            logger.debug("metrics.update_from_brain: ibkr_connected: %s", exc)

        try:
            mt5_conn = getattr(brain, "mt5_conn", None)
            if mt5_conn is not None:
                connected = 1.0 if mt5_conn.is_connected() else 0.0
                self.broker_connected.labels(broker="MT5").set(connected)
        except Exception as exc:
            logger.debug("metrics.update_from_brain: mt5_connected: %s", exc)


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
METRICS: TradingMetrics = TradingMetrics()


# ---------------------------------------------------------------------------
# HTTP scrape server
# ---------------------------------------------------------------------------
_metrics_server_started = False
_server_lock = threading.Lock()


def start_metrics_server(port: int = 8000) -> None:
    """Start a background HTTP server exposing /metrics on ``port``.

    Safe to call multiple times — subsequent calls are no-ops.
    """
    global _metrics_server_started
    with _server_lock:
        if _metrics_server_started:
            logger.debug("Metrics server already running.")
            return
        try:
            start_http_server(port, registry=REGISTRY)
            _metrics_server_started = True
            logger.info("Prometheus metrics server started on port %d", port)
        except OSError as exc:
            logger.warning("Could not start metrics server on port %d: %s", port, exc)


def generate_latest_text() -> bytes:
    """Return the current Prometheus metrics as UTF-8 encoded text."""
    return generate_latest(REGISTRY)
