import json
import logging
import os
from typing import Any

from config import PROJECT_PATH

logger = logging.getLogger(__name__)


class WorkloadManager:
    """
    Persistent Mission Mission Board (Samvid v1.0-beta-beta-beta).
    Inspired by Claude-Code's 'workloadContext.tss' and 'teammateMailbox.ts'.
    Ensures 'Absolute Step-by-Step Task Completion' across restarts.
    """

    def __init__(
        self, bridge=None, path: str = os.path.join(PROJECT_PATH, ".mission.json")
    ) -> None:
        import threading
        self._lock = threading.Lock()
        self.bridge = bridge
        self.path = path
        self.mission_board: dict[str, Any] = {
            "current_mission": "UNSPECIFIED",
            "steps": [],
            "status": "INITIALIZING",
        }
        self._ensure_exists()
        self.load()

    @property
    def current_mission(self) -> str:
        """Expose current mission name (Samvid v1.0-beta-beta-beta)."""
        with self._lock:
            return self.mission_board.get("current_mission", "UNKNOWN")

    def _ensure_exists(self) -> None:
        """GAP-116 FIX: Ensure mission directory exists before save."""
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        if not os.path.exists(self.path):
            self.save()
            logger.info(f"WorkloadManager: Mission board initialized at {self.path}")

    def load(self) -> None:
        """Sovereign Loading: Thread-safe mission recovery."""
        with self._lock:
            try:
                if os.path.exists(self.path):
                    with open(self.path, encoding="utf-8") as f:
                        self.mission_board = json.load(f)
            except Exception as e:
                logger.error(f"WorkloadManager: Error loading mission board: {e}")

    def save(self) -> None:
        """ATOMIC SAVE (GAP-113 Hardened): Verified atomic write protocol."""
        with self._lock:
            try:
                temp_path = f"{self.path}.tmp"
                # Ensure directory exists (Defensive)
                os.makedirs(os.path.dirname(self.path), exist_ok=True)

                with open(temp_path, "w", encoding="utf-8") as f:
                    # GAP-231 FIX: Restricted permissions (User-only read/write)
                    try:
                        os.chmod(temp_path, 0o600)
                    except Exception:
                        pass # Non-critical failure on Windows
                    json.dump(self.mission_board, f, indent=2)
                    f.flush()
                    os.fsync(f.fileno()) # Force write to physical media

                # GAP-113: Verify temp file is non-empty before swap
                if os.path.getsize(temp_path) > 0:
                    os.replace(temp_path, self.path)
                else:
                    raise IOError("Atomic write failed: Temp file is empty.")
            except Exception as e:
                logger.error(f"WorkloadManager: Error saving mission board: {e}")

    async def save_async(self) -> None:
        """GAP-245 FIX: Non-blocking atomic save via thread offloading."""
        import asyncio
        await asyncio.to_thread(self.save)

    async def update_mission(self, mission_name: str, steps: list[str]) -> None:
        """Sets a long-term goal with multiple granular steps."""
        self.mission_board["current_mission"] = mission_name
        # GAP-115 Preparation: Assign steps to specific agent IDs if present in format "ID: Task"
        new_steps = []
        for i, step in enumerate(steps):
            owner = "ALL"
            task_text = step
            if ":" in step and len(step.split(":")[0]) < 10:
                owner, task_text = step.split(":", 1)
                owner = owner.strip().upper()
                task_text = task_text.strip()
            new_steps.append({"id": i, "task": task_text, "owner": owner, "done": False})

        self.mission_board["steps"] = new_steps
        self.mission_board["status"] = "ACTIVE"
        await self.save_async()
        logger.info(f"WorkloadManager: NEW MISSION ACCEPTED: {mission_name} ({len(steps)} steps).")

    async def complete_step(self, step_id: int) -> None:
        """Mark a granular mission step as completed (GAP-114 Hardened)."""
        for step in self.mission_board["steps"]:
            if step["id"] == step_id:
                # In a full SE-11 system, we'd verify the 'task_result' here
                step["done"] = True
                logger.info(f"WorkloadManager: Step {step_id} COMPLETED: {step['task']}")
                break
        await self.save_async()
        if all(s["done"] for s in self.mission_board["steps"]):
            self.mission_board["status"] = "FINISHED"
            logger.info(
                f"WorkloadManager: MISSION {self.mission_board['current_mission']} COMPLETE."
            )
            await self.save_async()

    def get_mailbox(self, mind_id: str) -> list[dict]:
        """Simulation of a teammate's incoming task mailbox (GAP-115 Secured)."""
        # GAP-115: Only return tasks assigned to this mind_id or 'ALL'
        mid = str(mind_id).strip().upper()
        return [
            s for s in self.mission_board["steps"]
            if not s["done"] and (s.get("owner", "ALL") == mid or s.get("owner", "ALL") == "ALL")
        ]
