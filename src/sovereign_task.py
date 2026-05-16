import asyncio
import json
import logging
import os
import time
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List

logger = logging.getLogger("SovereignTask")


class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    KILLED = "killed"


class SovereignTask:
    """
    A first-class, persistent unit of work (Trade or Monitor).
    """

    def __init__(self, task_id: str, task_type: str, description: str, metadata: dict = None):
        self.id = task_id
        self.type = task_type  # 'trade', 'monitor', 'dream'
        self.status = TaskStatus.PENDING
        self.description = description
        self.metadata = metadata or {}
        from datetime import timezone as _timezone

        self.start_time = datetime.now(_timezone.utc).timestamp()
        self.end_time = None
        self.output_file = f"data/tasks/{self.id}.log"

        self.baseline_state = {}  # Snapshot at creation
        self.delta_metrics = {}  # Tracks shifts
        self.reflection_log = []  # Post-mortem notes
        self.status_summary = "Initializing"

        # Ensure directory exists
        os.makedirs("data/tasks", exist_ok=True)

    def transition(self, new_status: TaskStatus):
        logger.info(f"Task {self.id}: {self.status.value} -> {new_status.value}")
        self.status = new_status
        if new_status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.KILLED]:
            from datetime import timezone as _timezone

            self.end_time = datetime.now(_timezone.utc).timestamp()
        self.save()

    def record_shift(self, metric: str, current_value: Any):
        """Records a shift from the baseline as a diagnostic pulse."""
        if metric in self.baseline_state:
            base = self.baseline_state[metric]
            if base != current_value:
                self.delta_metrics[metric] = {
                    "base": base,
                    "now": current_value,
                    "drift": (current_value - base) if isinstance(base, (int, float)) else "N/A",
                }
                self.log(f"DIAGNOSTIC_PULSE: '{metric}' shifted. Drift detected.")

    def finalize(self, final_state: str):
        mapping = {
            "SUCCESS": TaskStatus.COMPLETED,
            "FAILED": TaskStatus.FAILED,
            "VETOED": TaskStatus.KILLED,
        }
        self.transition(mapping.get(final_state, TaskStatus.FAILED))
        self.log(f"TASK_FINALIZED: State set to {final_state}.")

    def log(self, message: str):
        try:
            with open(self.output_file, "a", encoding="utf-8") as f:
                from datetime import timezone as _timezone

                timestamp = datetime.now(_timezone.utc).isoformat()
                f.write(f"[{timestamp}] {message}\n")
        except Exception as e:
            logger.error(f"Task {self.id}: Log write failed: {e}")

        logger.info(f"Task {self.id}: {message}")

    def save(self):
        state_file = f"data/tasks/{self.id}.json"
        state = self.to_dict()
        import time as _time

        for attempt in range(5):
            try:
                temp_file = f"{state_file}.tmp"
                with open(temp_file, "w", encoding="utf-8") as f:
                    json.dump(state, f, indent=2)
                if os.path.exists(state_file):
                    try:
                        os.replace(temp_file, state_file)
                    except PermissionError:
                        # Fallback: Windows sometimes holds the handle too long
                        _time.sleep(0.05 * (attempt + 1))
                        continue
                else:
                    os.replace(temp_file, state_file)
                break
            except Exception as e:
                if attempt == 4:
                    logger.error(f"Task {self.id}: Save failed after 5 attempts: {e}")
                _time.sleep(0.05)

    def to_dict(self) -> dict:
        """Returns a serializable dictionary of the task state."""
        return {
            "id": self.id,
            "type": self.type,
            "status": self.status.value,
            "description": self.description,
            "metadata": self.metadata,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "status_summary": self.status_summary,
            "delta_metrics": self.delta_metrics,
        }


class TaskManager:
    """Orchestrates the lifecycle of Sovereign Tasks."""

    def __init__(self, registry_path: str = "data/active_tasks.json"):
        self.registry_path = registry_path
        self.tasks: Dict[str, SovereignTask] = {}
        self._symbol_index: Dict[str, List[str]] = {}  # Symbol -> List of Task IDs
        self._save_lock = asyncio.Lock()
        os.makedirs(os.path.dirname(self.registry_path), exist_ok=True)
        self.load_registry()

    def spawn_trade(self, symbol: str, setup: dict) -> SovereignTask:
        # Proactive memory management
        if len(self.tasks) > 500:
            self.purge_completed(max_age_days=1)  # Aggressive purge

        # If a task for this symbol is already PENDING or RUNNING, return it instead of spawning a new one.
        if symbol in self._symbol_index:
            for tid in self._symbol_index[symbol]:
                existing_task = self.tasks.get(tid)
                if existing_task and existing_task.status in [TaskStatus.PENDING, TaskStatus.RUNNING]:
                    logger.debug(f"TaskManager: Skipping spawn for {symbol}. Task {tid} is already {existing_task.status.value}.")
                    return existing_task

        task_id = f"t_{symbol}_{int(time.time())}"
        task = SovereignTask(task_id, "trade", f"Executing {symbol} Trade", setup)
        task.transition(TaskStatus.RUNNING)
        self.tasks[task_id] = task

        if symbol not in self._symbol_index:
            self._symbol_index[symbol] = []
        self._symbol_index[symbol].append(task_id)
        asyncio.create_task(self.save_registry())
        return task

    def get_task(self, task_id: str) -> SovereignTask | None:
        return self.tasks.get(task_id)

    def load_registry(self):
        """Reconstruct full task state from registry on startup."""
        if not os.path.exists(self.registry_path):
            return

        try:
            with open(self.registry_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                for tid, state in data.items():
                    try:
                        task = SovereignTask(
                            task_id=tid,
                            task_type=state.get("type", "unknown"),
                            description=state.get("description", "Restored Task"),
                            metadata=state.get("metadata", {}),
                        )
                        task.status = TaskStatus(state.get("status", "pending"))
                        task.start_time = state.get("start_time", time.time())
                        task.end_time = state.get("end_time")
                        task.delta_metrics = state.get("delta_metrics", {})
                        self.tasks[tid] = task

                        # Rebuild index
                        symbol = tid.split("_")[1] if "_" in tid else "UNKNOWN"
                        if symbol not in self._symbol_index:
                            self._symbol_index[symbol] = []
                        self._symbol_index[symbol].append(tid)
                    except Exception as e:
                        logger.error(f"TaskManager: Failed to restore task {tid}: {e}")
            logger.info(f"✓ Task Registry restored ({len(self.tasks)} tasks).")
        except Exception as e:
            logger.error(f"TaskManager: Registry load failed: {e}")

    async def save_registry(self, allow_empty: bool = False):
        """Atomically save task registry with Windows-safe retry logic (Async)."""
        async with self._save_lock:
            if not self.tasks and os.path.exists(self.registry_path) and not allow_empty:
                logger.error(
                    "TaskManager: SAFETY VETO! Attempted to save empty registry over existing data. Standing down."
                )
                return

            data = {tid: t.to_dict() for tid, t in self.tasks.items()}
            temp_path = f"{self.registry_path}.tmp"
            backup_path = f"{self.registry_path}.bak"

            def _sync_save():
                try:
                    import shutil
                    import time as _time

                    for attempt in range(5):
                        try:
                            if os.path.exists(self.registry_path):
                                shutil.copy2(self.registry_path, backup_path)

                            with open(temp_path, "w", encoding="utf-8") as f:
                                json.dump(data, f, indent=2)

                            os.replace(temp_path, self.registry_path)
                            return True
                        except PermissionError as e:
                            if attempt == 4:
                                raise
                            _time.sleep(0.1 * (attempt + 1))
                            continue
                        except Exception as e:
                            if attempt == 4:
                                raise
                            _time.sleep(0.1)
                            continue
                    return False
                except Exception as e:
                    logger.error(f"TaskManager: Registry sync-save failed: {e}")
                    return False

            await asyncio.to_thread(_sync_save)

    def purge_dormant_tasks(self, max_age_minutes: int = 15):
        """
        Sovereign Garbage Collection: Clears finished tasks that have exceeded their
        allotted memory TTL. This prevents the active task registry from bloating.
        """
        now = time.time()
        max_age_sec = max_age_minutes * 60
        to_remove = []

        for tid, task in self.tasks.items():
            # Only purge finished tasks for 'dormancy'
            if task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.KILLED]:
                # If end_time is missing (shouldn't happen), use start_time as fallback
                ref_time = task.end_time or task.start_time
                if (now - ref_time) > max_age_sec:
                    to_remove.append(tid)

        for tid in to_remove:
            self._delete_task_reference(tid)

        if to_remove:
            logger.info(f"TaskManager: Purged {len(to_remove)} dormant tasks.")
            # Run background save
            asyncio.create_task(self.save_registry(allow_empty=True))

    def purge_completed(self, max_age_days: int = 7):
        """Clear old finished and stale tasks to prevent memory leaks."""
        now = time.time()
        max_age_sec = max_age_days * 86400
        stale_threshold_sec = 86400  # 24 hours for non-finished tasks
        to_remove = []

        # 1. Standard Finished Purge
        for tid, task in self.tasks.items():
            if task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.KILLED]:
                if task.end_time and (now - task.end_time) > max_age_sec:
                    to_remove.append(tid)
            # 2. Stale Task Purge (Orphaned Pending/Running)
            elif (now - task.start_time) > stale_threshold_sec:
                to_remove.append(tid)

        for tid in to_remove:
            self._delete_task_reference(tid)

        if to_remove:
            logger.info(f"TaskManager: Purged {len(to_remove)} stale/finished tasks from memory.")

        # 3. Hard Ceiling Purge — keep only the 500 newest if registry exceeds 1000 tasks.
        if len(self.tasks) > 1000:
            logger.warning(
                f"TaskManager: Registry overflow detected ({len(self.tasks)} tasks). Executing Hard Purge."
            )
            sorted_tasks = sorted(self.tasks.items(), key=lambda x: x[1].start_time)
            purge_count = len(self.tasks) - 500
            for i in range(purge_count):
                tid = sorted_tasks[i][0]
                self._delete_task_reference(tid)
            logger.info(f"TaskManager: Hard Purge complete. Removed {purge_count} oldest tasks.")

        if to_remove or len(self.tasks) > 1000:
            asyncio.create_task(self.save_registry(allow_empty=True))

    def _delete_task_reference(self, tid: str):
        """Internal helper to clean up all index references for a task ID."""
        task = self.tasks.get(tid)
        if task:
            # Remove from index
            symbol = tid.split("_")[1] if "_" in tid else "UNKNOWN"
            if symbol in self._symbol_index and tid in self._symbol_index[symbol]:
                self._symbol_index[symbol].remove(tid)
            del self.tasks[tid]
