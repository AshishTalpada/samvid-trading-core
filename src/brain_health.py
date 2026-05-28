"""Health-check and status utilities extracted from brain.py.

This mixin groups pre-market validation, throttled status reporting,
and oracle risk-modifier decay so that TradingBrain can delegate
health concerns to a focused module.
"""
from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


class HealthChecker:
    """Mixin: pre-market checks, status heartbeats, and risk-modifier decay."""

    async def _pre_market_health_check(self) -> tuple[bool, str]:
        """
        Validate all critical execution paths before the first scan cycle.
        Returns (ok, reason). If not ok, system stays in STANDBY.
        """
        checks: list[str] = []

        # 1. Position state consistency — prune corrupt restored positions instead of hard-failing.
        bad_positions = []
        for i, pos in enumerate(self.positions):
            reasons = []
            if pos.entry_price is None or pos.entry_price <= 0:
                reasons.append(f"entry_price={pos.entry_price}")
            if pos.qty is None or abs(pos.qty) < 0.0001:
                reasons.append(f"qty={pos.qty}")
            if pos.stop_loss is None or pos.stop_loss <= 0:
                reasons.append(f"stop_loss={pos.stop_loss}")
            if reasons:
                bad_positions.append((i, pos, reasons))

        if bad_positions:
            pruned_symbols = []
            for _, pos, reasons in bad_positions:
                logger.critical(
                    "Pruning corrupt restored position %s: %s",
                    pos.symbol,
                    ", ".join(reasons),
                )
                pruned_symbols.append(pos.symbol)
            self.positions = [
                p for p in self.positions if p.symbol not in pruned_symbols
            ]

        # 2. Broker connectivity sanity (paper mode always passes)
        if self.mode == "paper":
            broker_ok = True
        elif self.active_broker == "IBKR":
            broker_ok = self._broker_is_connected(self.ibkr_conn)
        elif self.active_broker == "MT5":
            broker_ok = self._broker_is_connected(self.mt5_conn)
        else:
            broker_ok = False
            checks.append(f"Unknown active_broker={self.active_broker}")

        if not broker_ok and self.mode != "paper":
            checks.append(f"Broker {self.active_broker} not connected")

        # 3. Budget generated for today
        if (
            self.last_budget_date is None
            or self.last_budget_date.date() != datetime.now(timezone.utc).date()
        ):
            checks.append("Morning budget not generated for today")

        # 4. Regime detected (not stale default)
        if self.current_regime is None or self.current_regime == "UNKNOWN":
            checks.append("Market regime not detected")

        # 5. Database connection alive (if configured)
        if self.db_conn:
            cursor = None
            try:
                cursor = self.db_conn.cursor()
                cursor.execute("SELECT 1")
                cursor.fetchone()
            except Exception as db_e:
                checks.append(f"Database connection failed: {db_e}")
            finally:
                if cursor is not None:
                    cursor.close()

        if checks:
            return False, "; ".join(checks)
        return True, "ALL_CLEAR"

    async def _maybe_send_execution_status(self, stats: dict[str, Any], vix_str: str) -> None:
        """Send a throttled Telegram heartbeat when scans produce no executable trade."""
        now = time.monotonic()
        last_sent = float(getattr(self, "_last_execution_status_notice", 0.0))
        try:
            interval = float(os.getenv("SOVEREIGN_EXECUTION_STATUS_INTERVAL_SEC", "900"))
        except ValueError:
            interval = 900.0
        if now - last_sent < max(300.0, interval):
            return

        watchlist = int(stats.get("watchlist", 0) or 0)
        scanned = int(stats.get("scanned", 0) or 0)
        gated = int(stats.get("gated", 0) or 0)
        detected = int(stats.get("patterns_detected", stats.get("detected", 0)) or 0)
        approved = int(stats.get("patterns_approved", stats.get("approved", 0)) or 0)
        pending = int(stats.get("pending", 0) or 0)

        if pending > 0:
            return
        if watchlist <= 0:
            return

        if (
            not self._is_market_open()
            and os.environ.get("SOVEREIGN_ALLOW_CLOSED_MARKET_SCANS") != "1"
        ):
            reason = "Market closed; live entries are intentionally paused."
        elif scanned == 0 and gated >= watchlist:
            reason = (
                "All symbols gated "
                f"(active={stats.get('gate_active', 0)}, "
                f"cooldown={stats.get('gate_cooldown', 0)}, "
                f"vetting={stats.get('gate_vetting', 0)})."
            )
        elif detected == 0:
            reason = "No qualifying patterns detected."
        elif approved == 0:
            reason = "Patterns detected, but none cleared approval gates."
        else:
            reason = "Approved candidates did not become executable orders."

        msg = (
            "<b>[STATUS] Execution Pulse</b>\n"
            f"Mode: {self.mode} | Broker: {self.active_broker}\n"
            f"Regime: {self.current_regime} | Dhatu: {self._oracle_dhatu} | VIX: {vix_str}\n"
            f"Watchlist: {watchlist} | Scanned: {scanned} | Gated: {gated}\n"
            f"Detected: {detected} | Approved: {approved} | Pending: {pending}\n"
            f"Trade status: no broker order sent. {reason}"
        )
        try:
            from telegram_alerts import send_telegram_alert

            await send_telegram_alert(msg)
            self._last_execution_status_notice = now
        except Exception as exc:
            logger.debug("Execution status Telegram notice skipped: %s", exc)

    async def _decay_risk_modifier(self) -> None:
        """Gradually decays the oracle risk modifier back towards baseline (Oracle State)."""
        if not self.dhatu_oracle:
            return

        current_state = self.dhatu_oracle.get_current_state()
        if not current_state:
            return

        baseline = float(current_state.risk_modifier)

        if abs(self._oracle_risk_modifier - baseline) > 0.01:
            diff = baseline - self._oracle_risk_modifier
            self._oracle_risk_modifier += diff * 0.05
            if abs(self._oracle_risk_modifier - baseline) < 0.01:
                self._oracle_risk_modifier = baseline
            logger.debug("Risk Decay: %.4f -> %.4f", self._oracle_risk_modifier, baseline)
