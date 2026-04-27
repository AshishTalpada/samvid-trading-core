import logging
import os

from config import PROJECT_PATH

logger = logging.getLogger(__name__)


class MemoryManager:
    """
    Samvid v1.0-beta Memory Directory System.
    Inspired by Claude-Code's 'memdir' and 'CLAUDE.md' patterns.
    Provides persistent 'Trading Directives' and 'Session Memory' for the Twin-Minds.
    """

    def __init__(self, root_path: str = PROJECT_PATH) -> None:
        self.root_path = root_path
        self.prime_directive_path = os.path.join(root_path, "TRADING.md")
        self.session_memory_path = os.path.join(root_path, ".trading.md")

        # Initialize the memory files if they don't exist
        self._ensure_exists(
            self.prime_directive_path,
            "# TRADING.md — The Prime Directive\n\n- Never trade against the primary 1h trend.\n- Always respect the Drawdown Ladder (GAP-07).\n",
        )
        self._ensure_exists(
            self.session_memory_path,
            "# .trading.md — Session Context\n\n- System Status: INITIALIZING\n",
        )

        # GAP-73: Enforce RO protection on startup
        self.protect_prime_directive()

    def _ensure_exists(self, path: str, default_content: str) -> None:
        if not os.path.exists(path):
            with open(path, "w", encoding="utf-8") as f:
                f.write(default_content)
            logger.info(f"MemoryManager: Created initial memory file at {path}")

    def get_prime_directive(self) -> str:
        """Reads the user-provided 'Permanent Rules' for the minds."""
        try:
            # GAP-74 FIX: Use errors='replace' to prevent crashing on non-UTF8 noise
            with open(self.prime_directive_path, encoding="utf-8", errors="replace") as f:
                return f.read()
        except Exception as e:
            logger.error(f"MemoryManager: Error reading Prime Directive: {e}")
            return "# ERROR: Prime Directive Offline (Safety Risk)"

    def get_session_memory(self) -> str:
        """Reads the 'Dynamic Context' from the current session."""
        try:
            # GAP-74 FIX: Robust reading
            with open(self.session_memory_path, encoding="utf-8", errors="replace") as f:
                return f.read()
        except Exception as e:
            logger.error(f"MemoryManager: Error reading Session Memory: {e}")
            return ""

    def update_session_memory(self, content: str, mode: str = "w") -> None:
        """Update the session-level memory with new findings."""
        try:
            with open(self.session_memory_path, mode, encoding="utf-8") as f:
                f.write(content)
        except Exception as e:
            logger.error(f"MemoryManager: Error updating Session Memory: {e}")

    def protect_prime_directive(self) -> None:
        """
        GAP-73: Enforce 'Read-Only' permissions on TRADING.md to prevent AI/Agent tampering.
        This is a basic OS-level protection strike.
        """
        try:
            import stat
            if os.path.exists(self.prime_directive_path):
                # Set to RO for owner/group/others
                mode = os.stat(self.prime_directive_path).st_mode
                os.chmod(self.prime_directive_path, mode & ~stat.S_IWRITE)
                logger.info("MemoryManager: Prime Directive protected (Read-Only).")
        except Exception as e:
            logger.warning(f"MemoryManager: Could not protect TRADING.md: {e}")

    def get_full_context(self) -> str:
        """Constructs the 'Long-Term Memory' block for an LLM prompt (GAP-71 Hardened)."""
        directive = self.get_prime_directive()
        session = self.get_session_memory()

        # GAP-71: Apply strict truncation (5k chars each) to prevent identity thinning
        if len(directive) > 5000:
            directive = directive[:4900] + "\n... [TRUNCATED DUE TO BLOAT] ..."

        if len(session) > 5000:
            session = "... [TRUNCATED] ...\n" + session[-4900:] # Keep the latest session context

        return (
            "### LONG-TERM MEMORY (TRADING.md)\n"
            f"{directive}\n\n"
            "### SESSION CONTEXT (.trading.md)\n"
            f"{session}"
        )
