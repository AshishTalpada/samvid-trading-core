import asyncio
import inspect
import json
import logging
import time
import traceback
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

from mind_macros import MindMacros

logger = logging.getLogger(__name__)


@dataclass
class DialogueMessage:
    """A single message in the inter-agent dialogue."""

    sender: str
    content: str
    timestamp: datetime = field(default_factory=lambda: __import__('time_sync').TimeSync.now())
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(
            {
                "sender": self.sender,
                "content": self.content,
                "timestamp": self.timestamp.isoformat(),
                "metadata": self.metadata,
            }
        )


class MindBridge:
    """
    The Nervous System (Bridge) for the SETO V4.0 Architecture.
    Inspired by Claude-Code's MCP Client and SharedIntelligenceBus.
    Provides a communication layer for the 'Trading Mind' and the 'Healing Mind'.
    """

    def __init__(self, bus=None, initial_context: str | None = None) -> None:
        self.bus = bus
        self.initial_context = initial_context  # SETO V8.0 Wisdom Seed
        self.dialogue_history: list[DialogueMessage] = []
        self.tools: dict[str, Callable] = {}
        self._lock: asyncio.Lock | None = None  # Lazy-init: created on first async use
        self.is_running = False

        # Subscriptions for the minds
        self.subscribers: dict[str, asyncio.Queue] = {
            "trader": asyncio.Queue(maxsize=100),
            "architect": asyncio.Queue(maxsize=100),
            "evolution": asyncio.Queue(maxsize=100),
            "observer": asyncio.Queue(maxsize=100),
            "experiment": asyncio.Queue(maxsize=100),
        }

        # --- NEW: TEAMMATE MAILBOX (SETO V5.0) ---
        self.teammate_mailbox: list[DialogueMessage] = []  # Persistent context
        self.call_telemetry: list[dict] = []  # Audit log for tools

    def register_tool(self, name: str, func: Callable) -> None:
        """Register a 'Self-Healing' or 'Diagnostic' tool."""
        self.tools[name] = func
        logger.info(f"MindBridge: Tool '{name}' registered.")

    async def broadcast(self, sender: str, content: str, metadata: dict | None = None) -> None:
        """Broadcast a message between the minds (Wrapped in SETO V14.6 Encoding Shield)."""
        safe_content = str(content)
        msg = DialogueMessage(sender=sender, content=safe_content, metadata=metadata or {})
        if self._lock is None:
            self._lock = asyncio.Lock()
        async with self._lock:
            self.dialogue_history.append(msg)
            # Limit history to prevent memory bloat (from Claude-Code memory-bounded history)
            if len(self.dialogue_history) > 1000:
                self.dialogue_history.pop(0)

        # Notify subscribers
        for target, queue in self.subscribers.items():
            if target != sender:  # Don't send back to sender
                try:
                    await queue.put(msg)
                except asyncio.QueueFull:
                    logger.warning(f"MindBridge: Queue for {target} is full, dropping message.")

        # Also push to the Intelligence Bus if available
        if self.bus:
            await self.bus.publish("mind.dialogue", asdict(msg))

    async def call_tool(self, tool_name: str, **kwargs) -> dict[str, Any]:
        """Invoke an autonomous healing or diagnostic tool."""
        # 0. SECURITY GUARDRAIL: Verify Tool Signature (GAP-64)
        if not MindMacros.is_tool_signed(tool_name):
            logger.critical(f"MindBridge: UNAUTHORIZED tool call blocked: {tool_name}")
            return {"error": "Unauthorized: Tool not in Signed Allowlist"}

        # 0.1 DOUBLE HANDSHAKE (GAP-64 FIX)
        if tool_name in MindMacros.SENSITIVE_TOOLS:
            justification = kwargs.get("justification")
            if not justification or len(str(justification)) < 10:
                logger.warning(f"MindBridge: SENSITIVE tool '{tool_name}' blocked - Missing/Weak Justification.")
                return {"error": "DoubleHandshake Failed: Sensitive tools require a detailed justification string."}
            logger.info(f"MindBridge: [SECURITY_AUDIT] Sensitive tool '{tool_name}' HANDSHAKE ACCEPTED. Reason: {justification}")

        if tool_name not in self.tools:
            logger.error(f"MindBridge: Tool '{tool_name}' not found.")
            return {"error": "Tool not found"}

        logger.info(f"MindBridge: Calling autonomous tool '{tool_name}'...")
        # 1. Capture Telemetry (Inspired by telemetryAttributes.ts)
        start_time = time.time()

        try:
            func = self.tools[tool_name]
            if inspect.iscoroutinefunction(func):
                result = await func(**kwargs)
            else:
                result = func(**kwargs)

            # 2. Store Audit Data
            self.call_telemetry.append(
                {
                    "tool": tool_name,
                    "duration": time.time() - start_time,
                    "success": "error" not in result,
                }
            )
            return result
        except Exception as e:
            tb = traceback.format_exc()
            logger.error(f"MindBridge: Error executing tool '{tool_name}': {e}\n{tb}")
            return {
                "error": str(e),
                "traceback": tb,
                "locals": {k: str(v) for k, v in kwargs.items()} # Capture call context
            }

    async def get_next_message(self, target: str) -> DialogueMessage:
        """Wait for the next message intended for a specific mind."""
        if target not in self.subscribers:
            raise ValueError(f"Unknown mind target: {target}")
        return await self.subscribers[target].get()

    def get_context(self, limit: int = 20) -> list[DialogueMessage]:
        """Get recent dialogue context for LLM local processing."""
        return self.dialogue_history[-limit:]
