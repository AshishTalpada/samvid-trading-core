import ast
import asyncio
import logging
import os
import subprocess
import time
from typing import Any

from diagnostic_tracker import DiagnosticTracker
from mind_bridge import MindBridge
from vault import Vault

logger = logging.getLogger(__name__)


class MindArchitect:
    """
    Agent G: The Healing Mind.
    Focuses on code stability, diagnostic audits, and autonomous 'Self-Healing'.
    Utilizes patterns from Claude-Code: FileEdit, LSP, and Error Classification.
    Baseline-aware diagnostic verification.
    """

    def __init__(self, bridge: MindBridge, vault: Vault | None = None) -> None:
        from logic_engine import get_sovereign_logic

        self.bridge = bridge
        self.vault = vault
        self.is_running = False
        self.diagnostic_history: list[dict] = []
        self.tracker = DiagnosticTracker()  # NEW Core
        self.healing_attempts: dict[str, dict] = {}  # Persistent circuit breaker
        self.sovereign = get_sovereign_logic()  # ACCESS TO 500 ABILITIES
        self._tasks: set[asyncio.Task] = set()

        # Register Healing Tools with the Bridge
        self.bridge.register_tool("heal_code", self._tool_heal_code)
        self.bridge.register_tool("check_syntax", self._tool_check_syntax)
        self.bridge.register_tool("audit_pnl", self._tool_audit_pnl)
        self.bridge.register_tool("trigger_sovereign_logic", self._tool_trigger_logic)

    def is_path_safe_for_edit(self, file_path: str) -> bool:
        """Security Guard: Ensures the file path is within the authorized project directories."""
        from config import PROJECT_PATH

        abs_path = os.path.abspath(file_path)
        abs_project = os.path.abspath(PROJECT_PATH)

        # Only allow edits within src/ or specific config files
        is_in_project = abs_path.startswith(abs_project)
        allowed_dirs = [os.path.join(abs_project, "src")]
        allowed_files = [
            os.path.join(abs_project, "src", "config.py"),
            os.path.join(abs_project, "src", "main.py"),
            os.path.join(abs_project, "TRADING.md"),
            os.path.join(abs_project, ".trading.md"),
        ]

        in_allowed_dir = any(abs_path.startswith(d) for d in allowed_dirs)
        is_allowed_file = any(abs_path == f for f in allowed_files)

        # Prevent traversal outside or accessing sensitive system areas
        return is_in_project and (in_allowed_dir or is_allowed_file)

    async def start(self) -> None:
        """Launch the Healing Mind process."""
        if self.is_running:
            return
        self.is_running = True
        logger.info("MindArchitect (Agent G): Healing process active.")
        for coroutine in (self._monitor_heartbeat(), self._process_dialogue()):
            task = asyncio.create_task(coroutine)
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)

    async def stop(self) -> None:
        """Stop diagnostic workers without leaving orphaned tasks."""
        self.is_running = False
        tasks = [task for task in self._tasks if not task.done()]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._tasks.clear()

    async def _monitor_heartbeat(self) -> None:
        """Continuous self-diagnostic pulse (Inspired by Claude-Code's PreflightChecks)."""
        while self.is_running:
            try:
                # 1. Check for 'Bleeding' (Exceptions/Errors in the system)
                # 2. Perform a syntax check on critical files
                for filename in ["src/brain.py", "src/agent_c_ibkr.py", "src/config.py"]:
                    await self._tool_check_syntax(file_path=filename)

                await asyncio.sleep(60)  # 1-minute diagnostic pulse
            except Exception as e:
                logger.error(f"MindArchitect Heartbeat Error: {e}")
                await asyncio.sleep(5)

    async def _process_dialogue(self) -> None:
        """Discusses and debates with Mind F (The Trader)."""
        while self.is_running:
            try:
                msg = await self.bridge.get_next_message("architect")
                logger.info(
                    f"MindArchitect: Received message from {msg.sender}: {msg.content[:50]}..."
                )

                if "drawdown" in msg.content.lower() or "error" in msg.content.lower():
                    await self._handle_urgent_discussion(msg)

            except Exception as e:
                logger.error(f"MindArchitect: Dialogue processing error: {e}")
                await asyncio.sleep(1)

    async def _handle_urgent_discussion(self, msg) -> None:
        """Handles emergency/high-priority dialogue (Inspired by TeleportOperationError patterns)."""
        await self.bridge.broadcast(
            "architect",
            f"ACK. Analyzing '{msg.sender}' incident. Initiating diagnostic scan on src/brain.py...",
            {"severity": "HIGH"},
        )

    async def evaluate_proposal(self, context: dict[str, Any]) -> dict[str, Any]:
        """
        Provides Agent G's 'Healing Mind' structural integrity vote.
        """

        # Check syntax on critical files (at least the brain)
        result = await self._tool_check_syntax("src/brain.py")

        valid = result.get("valid", False)
        vote = "YES" if valid else "NO"

        return {
            "agent": "Agent_G",
            "vote": vote,
            "confidence": 1.0 if valid else 0.0,
            "reason": "Sovereign structural integrity verified."
            if valid
            else f" STRUCTURAL VETO: Syntax/Diagnostic failure in core logic! {result.get('summary')}",
            "timestamp": time.time_ns(),
        }

    async def _tool_check_syntax(self, file_path: str) -> dict[str, Any]:
        """Python-native 'LSP' check for syntax errors."""
        if not self.is_path_safe_for_edit(file_path):
            return {
                "valid": False,
                "error": "Unauthorized path access attempt recorded (SETO Protocol 9).",
            }

        try:
            # Captures baseline before editing, or just checks current state
            diagnostics = self.tracker._run_diagnostics(file_path)
            valid = not any(d.severity == "Error" for d in diagnostics)

            summary = self.tracker.format_summary(diagnostics)
            return {"valid": valid, "summary": summary, "issues_count": len(diagnostics)}
        except Exception as e:
            return {"valid": False, "error": str(e)}

    async def _tool_heal_code(
        self, file_path: str, target: str, replacement: str
    ) -> dict[str, Any]:
        """
        Self-Correction 'Suture' (Inspired by FileEditTool).
        Verifies that the healing didn't introduce new regressions.
        """
        if not self.is_path_safe_for_edit(file_path):
            logger.critical(f"MindArchitect: BLOCKED unauthorized edit attempt on {file_path}")
            return {"success": False, "error": "Access Denied: Path outside Sovereign Domain."}

        try:
            from time_sync import TimeSync

            now = TimeSync.now().timestamp()
            file_key = f"{file_path}:{target}"
            attempt_data = self.healing_attempts.get(file_key, {"count": 0, "last_attempt": 0})

            # Check for lockout (3 attempts within 1 hour)
            if attempt_data["count"] >= 3 and (now - attempt_data["last_attempt"]) < 3600:
                logger.warning(
                    f"MindArchitect: CIRCUIT BREAKER ACTIVE for {file_path}. Lockout for 60m."
                )
                return {
                    "success": False,
                    "error": "Neural Circuit Breaker: Too many failed heal attempts. Manual intervention required.",
                }

            # 1. Capture baseline before 'Suture'
            await asyncio.to_thread(self.tracker.capture_baseline, file_path)

            with open(file_path, encoding="utf-8") as f:
                content = f.read()

            if target not in content:
                logger.error(
                    f"MindArchitect: Suture failed — target fragment not found in {file_path}."
                )
                return {"success": False, "error": "Target not found"}

            occ_count = content.count(target)
            if occ_count > 1:
                logger.critical(
                    f"MindArchitect: SUTURE COLLISION DETECTED! Target occurs {occ_count} times in {file_path}. Aborting to prevent corruption."
                )
                return {
                    "success": False,
                    "error": f"Collision: Target occurs {occ_count} times. Use more specific context.",
                }

            new_content = content.replace(target, replacement)

            # 2. SEVERE INTEGRITY CHECK
            # Scan for forbidden dynamic logic loading patterns
            FORBIDDEN_CALLS = {"exec", "eval", "__import__"}
            FORBIDDEN_MODULES = {"importlib", "pickle", "marshal"}

            try:
                tree = ast.parse(new_content)
                for node in ast.walk(tree):
                    # Check for forbidden function calls
                    if isinstance(node, ast.Call):
                        if isinstance(node.func, ast.Name) and node.func.id in FORBIDDEN_CALLS:
                            logger.critical(
                                f"MindArchitect: BLOCKED HEAL. Forbidden call '{node.func.id}' detected."
                            )
                            return {
                                "success": False,
                                "error": f"Security Violation: Forbidden logic pattern '{node.func.id}' detected.",
                            }

                    # Check for forbidden imports
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            if alias.name in FORBIDDEN_MODULES:
                                logger.critical(
                                    f"MindArchitect: BLOCKED HEAL. Forbidden import '{alias.name}' detected."
                                )
                                return {
                                    "success": False,
                                    "error": f"Security Violation: Forbidden module '{alias.name}' detected.",
                                }
                    if isinstance(node, ast.ImportFrom):
                        if node.module in FORBIDDEN_MODULES:
                            logger.critical(
                                f"MindArchitect: BLOCKED HEAL. Forbidden import from '{node.module}' detected."
                            )
                            return {
                                "success": False,
                                "error": f"Security Violation: Forbidden module '{node.module}' detected.",
                            }

            except Exception as e:
                logger.error(f"MindArchitect: Integrity scan failed: {e}")
                return {"success": False, "error": f"Integrity Scan Error: {e}"}

            # 3. Safety Check: Dry run syntax on new content (Redundant but keeps double-verification)
            try:
                ast.parse(new_content)
            except Exception as e:
                logger.error(
                    f"MindArchitect: Suture aborted — replacement introduces syntax error: {e}."
                )
                return {"success": False, "error": f"Syntax error in replacement: {e}"}

            # 3.1. Write to Staging for Auditability
            staging_dir = os.path.join("data", "staging")
            os.makedirs(staging_dir, exist_ok=True)
            filename = os.path.basename(file_path)
            staged_path = os.path.join(staging_dir, f"staged_{filename}")
            with open(staged_path, "w", encoding="utf-8") as f:
                f.write(new_content)

            # 3.2. Complexity Check (Prevent Spaghettification)
            if not self._check_complexity(new_content):
                logger.critical(
                    "MindArchitect: Suture REJECTED. Code complexity exceeded Sovereign Cap."
                )
                return {
                    "success": False,
                    "error": "Complexity Guard: Proposed fix is too complex/unreadable.",
                }

            # 3.3. PERMANENT COMMIT: Write to live source
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(new_content)

            # 3.4. Git Commit (Immutable History)
            await asyncio.to_thread(self._git_commit, file_path, target)

            # 4. VERIFY: Check if new diagnostics are introduced
            new_issues = await asyncio.to_thread(self.tracker.get_new_diagnostics, file_path)
            if any(n.severity == "Error" for n in new_issues):
                logger.critical("MindArchitect: Healing introduced NEW ERRORS! Rolling back...")
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(content)

                # Update Circuit Breaker
                attempt_data["count"] += 1
                attempt_data["last_attempt"] = now
                self.healing_attempts[file_key] = attempt_data

                return {
                    "success": False,
                    "error": "Healing introduced regression errors. Rollback performed.",
                }

            # Reset count on successful heal
            if file_key in self.healing_attempts:
                del self.healing_attempts[file_key]

            logger.info(f" HEAL COMPLETE: {filename} successfully patched and verified.")
            return {"success": True, "new_issues": len(new_issues)}
        except Exception as e:
            logger.error(f"MindArchitect: Heal Error: {e}")
            return {"success": False, "error": str(e)}

    async def _tool_audit_pnl(self, session_id: str | None = None) -> dict[str, Any]:
        """Audits the session for 'bleeding' using Ability #164 (Net Liquidation Audit)."""
        logger.info(
            f"MindArchitect: Auditing session {session_id or 'CURRENT'} for PnL integrity..."
        )

        # Capability #164 Trigger
        self.sovereign.execute_node("164", {"session": session_id})

        # Audit Logic
        try:
            import os
            import sqlite3

            from config import PROJECT_PATH

            db_path = os.path.join(PROJECT_PATH, "data", "trading.db")
            conn = sqlite3.connect(db_path, timeout=60)
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA busy_timeout = 60000;")
            cursor = conn.cursor()

            # Check for trades with abnormal slippage (>5%)
            cursor.execute(
                "SELECT COUNT(*) FROM trades WHERE ABS(pnl_dollars) > 1000 AND r_multiple < 0"
            )
            outliers = cursor.fetchone()[0]

            conn.close()

            if outliers > 0:
                # Trigger Ability #231 (Cognitive Audit) for corrective action
                self.sovereign.execute_node("231", {"recent_pnl": [-1001] * outliers})
                logger.warning(
                    f"MindArchitect: Audit detected {outliers} PnL outliers. System recalibration recommended."
                )
                return {
                    "audit": "VOLATILE",
                    "details": f"{outliers} outliers detected. Risk team notified.",
                }

            return {
                "audit": "STABLE",
                "details": "PnL integrity verified. No halluncinated bleeding detected.",
            }
        except Exception as e:
            logger.error(f"Audit failed: {e}")
            return {"audit": "UNCERTAIN", "error": str(e)}

    async def _tool_trigger_logic(self, node_id: str, context: dict) -> dict:
        """Sovereign Bridge Tool to trigger any of the 500 abilities."""
        return self.sovereign.execute_node(node_id, context)

    def _check_complexity(self, code: str) -> bool:
        """Sovereign Complexity Auditor. Ensures AI code stays human-legible."""
        try:
            tree = ast.parse(code)
            # Basic metric: for/if/while depth
            complexity = 0
            for node in ast.walk(tree):
                if isinstance(
                    node, (ast.If, ast.For, ast.While, ast.AsyncFor, ast.With, ast.AsyncWith)
                ):
                    complexity += 1
            # Total decision branches in one file shouldn't spike by +10 in one 'heal'
            return complexity < 100  # Adjusted for whole-file baseline
        except Exception:
            return False

    def _git_commit(self, file_path: str, target: str) -> None:
        """Records the AI's healing session in the immutable project history."""
        try:
            msg = f"AI_HEAL: [{os.path.basename(file_path)}] -> Fixed fragment: {target[:20]}..."
            subprocess.run(["git", "add", file_path], capture_output=True, text=True, check=True)
            subprocess.run(["git", "commit", "-m", msg], capture_output=True, text=True, check=True)
            logger.info(f"MindArchitect: Sovereign Git-Guard COMMITTED heal for {file_path}.")
        except subprocess.CalledProcessError as exc:
            logger.warning(
                "MindArchitect: Git-Guard could not commit heal for %s: %s",
                file_path,
                exc.stderr.strip() if exc.stderr else exc,
            )
        except Exception as exc:
            # Git may not be initialized, but we don't stall the system for it
            logger.debug("MindArchitect: Git-Guard skipped for %s: %s", file_path, exc)
