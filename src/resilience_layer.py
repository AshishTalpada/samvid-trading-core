import asyncio
import logging
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class FailedOrder:
    """An order that failed to transmit and is queued for retry."""

    symbol: str
    direction: str
    shares: float | int
    price: float
    attempt: int = 0
    max_attempts: int = 3
    reason: str = ""
    ts_first_fail: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    task_id: str = ""


class DeadLetterQueue:
    """
    Retry queue for failed order submissions.
    Uses exponential back-off: 1s → 2s → 4s before final escalation.
    After max_attempts, triggers TradingState.HALTED to prevent silent capital risk.

    Wire-in:
        from resilience_layer import DEAD_LETTER_QUEUE
        # On order failure in agent_c_ibkr:
        DEAD_LETTER_QUEUE.enqueue(order)
        # Start the retry worker as a background task:
        asyncio.create_task(DEAD_LETTER_QUEUE.run(retry_fn=agent_c.place_order))
    """

    def __init__(self, max_attempts: int = 3):
        self._queue: asyncio.Queue[FailedOrder] = asyncio.Queue(maxsize=200)
        self._max_attempts = max_attempts
        self._retry_count = 0
        self._escalation_count = 0

    def enqueue(
        self,
        symbol: str,
        direction: str,
        shares: float | int,
        price: float,
        reason: str = "",
        task_id: str = "",
        attempt: int = 0,
    ) -> None:
        """Add a failed order to the retry queue."""
        order = FailedOrder(
            symbol=symbol,
            direction=direction,
            shares=shares,
            price=price,
            reason=reason,
            task_id=task_id,
            attempt=attempt,
            max_attempts=self._max_attempts,
        )
        try:
            self._queue.put_nowait(order)
            logger.warning(
                f"DLQ: ⚠ Order queued for retry — {direction} {shares}x {symbol} "
                f"@ ${price:.2f} | Reason: {reason}"
            )
        except asyncio.QueueFull:
            logger.error(f"DLQ: Queue FULL — dropping {symbol} order. Escalating.")
            self._escalate(order, "DLQ queue full — order dropped.")

    async def run(self, retry_fn: Callable) -> None:
        """
        Background worker. Handles concurrent retries to prevent Head-of-Line blocking.
        """
        logger.info("DLQ: Concurrent retry worker started.")

        async def _process_retry(order: FailedOrder):
            order.attempt += 1
            # Exponential back-off: 1s, 2s, 4s
            delay = 2 ** (order.attempt - 1)
            await asyncio.sleep(delay)

            try:
                success = await retry_fn(order.symbol, order.direction, order.shares, order.price)
            except Exception as e:
                success = False
                order.reason = str(e)

            if success:
                self._retry_count += 1
                logger.info(
                    f"DLQ: ✅ Retry #{order.attempt} SUCCESS — "
                    f"{order.direction} {order.shares}x {order.symbol}"
                )
            elif order.attempt >= order.max_attempts:
                self._escalate(order, f"Max retries ({order.max_attempts}) exhausted.")
            else:
                # Re-queue for another attempt
                self.enqueue(
                    order.symbol, order.direction, order.shares, order.price,
                    reason=f"Retry {order.attempt} failed", task_id=order.task_id,
                    attempt=order.attempt
                )

            self._queue.task_done()

        while True:
            order = await self._queue.get()
            # Spawn a concurrent task for this specific order retry
            asyncio.create_task(_process_retry(order))

    def _escalate(self, order: FailedOrder, reason: str) -> None:
        """Final escalation: halt trading and log critical alert."""
        self._escalation_count += 1
        full_reason = (
            f"DLQ ESCALATION: {order.direction} {order.shares}x {order.symbol} "
            f"@ ${order.price:.2f} — {reason}"
        )
        logger.critical(f"🚨 {full_reason}")

        # Halt trading to prevent further capital risk
        try:
            from trading_state import TradingStateManager

            TradingStateManager.halt(full_reason)
        except Exception as e:
            logger.error(f"DLQ: Could not trigger TradingState.HALTED: {e}")

    @property
    def stats(self) -> dict:
        return {
            "queue_depth": self._queue.qsize(),
            "retry_successes": self._retry_count,
            "escalations": self._escalation_count,
        }


# Module-level singleton
DEAD_LETTER_QUEUE = DeadLetterQueue()


class ApexExoskeleton:
    """
    The Apex Exoskeleton.
    Wraps the Sovereign Core with hardware-optimized resilience layers.
    Handles: Cortex Cache, Parallel CPU Tiering, and Dictatorship of Talent.
    """

    def __init__(self, brain: Any):
        self.brain = brain
        self._cortex_cache: Dict[str, Dict[str, Any]] = {}
        logger.info("Apex Exoskeleton: Cognitive Wrapper INITIALIZED.")

    async def check_cortex_cache(
        self, symbol: str, current_price: float
    ) -> Optional[Dict[str, Any]]:
        """Phase 0: SSS-Tier Cortex Cache Bypass."""
        if symbol not in self._cortex_cache:
            return None

        cache = self._cortex_cache[symbol]
        # Prevent ZeroDivisionError in the Cortex Bypass
        denom = cache["price"] if cache["price"] > 0 else 1.0
        price_delta = abs(current_price - cache["price"]) / denom
        age = (datetime.now() - cache["timestamp"]).total_seconds()

        if price_delta < 0.0005 and age < 60:
            logger.info(
                f"Apex Exoskeleton: 🧠 CORTEX HIT for {symbol}. Price stable ({price_delta:.4%})."
            )

            if hasattr(self.brain, "bus"):
                await self.brain.bus.publish(
                    "apex.telemetry",
                    {
                        "type": "CORTEX_HIT",
                        "symbol": symbol,
                        "price_delta": price_delta,
                        "age": age,
                        "timestamp": datetime.now().isoformat(),
                    },
                )

            return cache
        return None

    def store_cortex_cache(
        self,
        symbol: str,
        price: float,
        decision: Dict[str, Any],
        all_votes: List[Dict[str, Any]],
        shares: float | int,
    ):
        """Zone B: Persist decision outcome to regional cache."""
        self._cortex_cache[symbol] = {
            "price": price,
            "decision": decision,
            "all_votes": all_votes,
            "shares": shares,
            "timestamp": datetime.now(),
        }

    async def run_parallel_tier(self, shared_context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Stage 1: Deterministic FAST-PATH (Parallel CPU Quorum)."""
        pattern = shared_context["pattern"]
        timestamp = shared_context["timestamp"]

        async def poll_agent_d():
            """Agent D: Historical Learning with Imperial Guard Veto."""
            try:
                # Direct call to standardized consensus (Alpha Brain Integration)
                vote = self.brain.live_learner.evaluate_proposal(
                    pattern.name, self.brain.current_regime
                )

                # --- IMPERIAL GUARD: Internal Stats VETO ---
                learned = getattr(self.brain, "_learned_win_rates", {})
                regime_key = f"{pattern.name}:{self.brain.current_regime}"
                learned_wr = learned.get(regime_key) or learned.get(pattern.name)

                if learned_wr is not None and isinstance(learned_wr, float) and learned_wr < 0.40:
                    vote["vote"] = "NO"
                    vote["reason"] = f"🛑 IMPERIAL VETO: Internal WR too low ({learned_wr:.2%})"

                    if hasattr(self.brain, "bus"):
                        await self.brain.bus.publish(
                            "apex.telemetry",
                            {
                                "type": "IMPERIAL_VETO",
                                "pattern": pattern.name,
                                "regime": self.brain.current_regime,
                                "win_rate": learned_wr,
                                "timestamp": timestamp,
                            },
                        )

                vote["timestamp"] = timestamp
                return vote
            except Exception as e:
                logger.error(f"Exoskeleton: Agent D poll failed: {e}")
                return {
                    "agent": "Agent_D",
                    "vote": "YES",
                    "confidence": 0.5,
                    "reason": "Fallback",
                    "timestamp": timestamp,
                }

        async def _poll_syntax_guard() -> dict[str, Any]:
            """Agent G: Normalizes MindArchitect syntax checks into a Quorum Vote."""
            try:
                res = await self.brain.mind_architect._tool_check_syntax("src/brain.py")
                is_valid = res.get("valid", False)
                return {
                    "vote": "YES" if is_valid else "NO",
                    "confidence": 1.0 if is_valid else 0.0,
                    "reason": "Syntax Verified"
                    if is_valid
                    else f"🚨 SYNTAX ERROR: {res.get('summary', 'Unknown Fracture')}",
                    "timestamp": datetime.now().isoformat(),
                }
            except Exception as e:
                return {"vote": "NO", "confidence": 0.0, "reason": f"Syntax Guard Failure: {e}"}

        fast_voting_map = {
            "Agent_B": lambda: self.brain.belief_tracker.evaluate_proposal(shared_context),
            "Agent_C": lambda: (
                self.brain.dms.record_heartbeat("AGENT_C") if (hasattr(self.brain, "dms") and self.brain.dms) else None,
                self.brain.portfolio_guard.evaluate_proposal(shared_context, "Agent_C")
            )[1],
            "Risk_Guard": lambda: self.brain.correlation_guard.evaluate_proposal(shared_context, "Risk_Guard"),
            "Agent_D": poll_agent_d,
            "Agent_E": lambda: self.brain.correlation_guard.evaluate_proposal(shared_context, "Agent_E"),
            "Agent_F": lambda: self.brain.vix_protocol.evaluate_proposal(shared_context, "Agent_F"),
            "Agent_G": lambda: self.brain.mind_architect.evaluate_proposal(shared_context),
        }

        async def _poll_safe(name, func):
            try:
                import inspect
                if inspect.iscoroutinefunction(func):
                    res = await func()
                else:
                    # Sync-safe bridge: run in thread pool to prevent blocking the event loop
                    res = await asyncio.to_thread(func)
                    # Support for sync functions that return coroutine objects (e.g. lambdas)
                    if asyncio.iscoroutine(res) or hasattr(res, "__await__"):
                        res = await res

                # --- IDENTITY INJECTION ---
                if isinstance(res, dict):
                    res["agent"] = name
                return res
            except Exception as e:
                logger.warning(f"Exoskeleton: {name} poll failed: {e}")
                return {
                    "agent": name,
                    "vote": "YES",
                    "confidence": 0.5,
                    "reason": f"Exoskeleton Fallback: {e}",
                }

        logger.info("Apex Exoskeleton: Launching Stage 1 Parallel Quorum (7-Guards Tier)...")
        return await asyncio.gather(  # type: ignore
            *[_poll_safe(name, func) for name, func in fast_voting_map.items()]
        )

    def evaluate_dictatorship(
        self, tier1_votes: List[Dict[str, Any]], timestamp: str
    ) -> Optional[List[Dict[str, Any]]]:
        """Zone A: The Dictatorship of Talent (Agent D Bypass)."""
        agent_d_res = next((v for v in tier1_votes if v["agent"] == "Agent_D"), None)

        # This force the Quorum to wait for the GPU Agents (Oracle/Swarm) in almost all scenarios.
        if (
            agent_d_res
            and agent_d_res["vote"] == "YES"
            and agent_d_res.get("confidence", 0) >= 0.99
        ):
            logger.info(
                f"Apex Exoskeleton: 👑 EMERGENCY DICTATORSHIP TRIGGERED by Agent D ({agent_d_res['confidence']:.2%})."
            )

            # Synthetic Signal Generation for GPU agents
            return [
                {
                    "agent": "Dhatu_Oracle",
                    "vote": "YES",
                    "confidence": 0.8,
                    "reason": "Exoskeleton Fast-Path",
                    "timestamp": timestamp,
                },
                {
                    "agent": "Swarm_Predictor",
                    "vote": "YES",
                    "confidence": 0.8,
                    "reason": "Exoskeleton Fast-Path",
                    "timestamp": timestamp,
                },
                {
                    "agent": "Mind_Ultrathink",
                    "vote": "YES",
                    "confidence": 0.8,
                    "reason": "Exoskeleton Fast-Path",
                    "timestamp": timestamp,
                },
            ]
        return None


class CorrelationWatchdog:
    """
    Monitors the 'Lead-Lag' relationship between a symbol and its sector ETF.
    If correlation drops below 0.4 during a trade, it signals a 'DECAY' exit.
    """

    def __init__(self, decay_threshold: float = 0.4):
        self.decay_threshold = decay_threshold
        self._history: Dict[str, deque] = {}  # symbol -> deque of (price, sector_price)

    def record(self, symbol: str, price: float, sector_price: float):
        from collections import deque

        if symbol not in self._history:
            self._history[symbol] = deque(maxlen=50)
        self._history[symbol].append((price, sector_price))

    def evaluate(self, symbol: str) -> bool:
        """Returns True if correlation is healthy, False if decayed."""
        import numpy as np

        hist = self._history.get(symbol)
        if not hist or len(hist) < 20:
            return True  # Assume healthy during warmup

        prices = np.array([x[0] for x in hist])
        sector_prices = np.array([x[1] for x in hist])

        # Calculate rolling correlation
        if len(np.unique(prices)) < 2 or len(np.unique(sector_prices)) < 2:
            return True

        correlation = np.corrcoef(prices, sector_prices)[0, 1]

        if correlation < self.decay_threshold:
            logger.warning(
                f"🚨 CORRELATION DECAY: {symbol} decoupled from sector (Corr: {correlation:.2f})."
            )
            return False
        return True
