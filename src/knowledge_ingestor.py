import asyncio
import logging
import os
import re
from datetime import datetime

from swarm_predictor import ChromaDeepMemory
from vault import Vault

logger = logging.getLogger(__name__)

class KnowledgeIngestor:
    """
    Hardened for safe recursive harvesting and secret redaction.
    """

    def __init__(self, memory: ChromaDeepMemory) -> None:
        self.memory = memory
        self.ingested_count = 0
        self.visited_paths = set()
        self.redaction_patterns = self._init_redaction()

    def _init_redaction(self):
        """Initialize redaction patterns from vault credentials to prevent secret leakage."""
        secrets = Vault.get_all_redactable_values()
        escaped = [re.escape(s) for s in secrets if len(s) > 3]
        if not escaped:
            return None

        # Pattern: [any text](url_containing_secret) -> [REDACTED]
        patterns = list(escaped)
        for s in escaped:
             patterns.append(rf'\[[^\]]*\]\([^\)]*{s}[^\)]*\)')

        return re.compile("|".join(patterns))

    async def ingest_directory(self, path: str, extensions: list[str] | None = None, max_depth: int = 5) -> None:
        """Crawl a directory and ingest content into Swarm Memory."""
        if extensions is None:
            extensions = [".md", ".txt", ".json", ".log"]

        logger.info(f"Ingestor: Harvesting intelligence from {path}...")

        if not os.path.exists(path):
            logger.warning(f"Ingestor: Path {path} not found. Skipping.")
            return

        # Start recursion
        await self._recursive_ingest(path, extensions, max_depth, 0)

        logger.info(
            f"Ingestor: Successfully absorbed {self.ingested_count} intelligence fragments."
        )

    async def _recursive_ingest(self, current_path: str, extensions: list[str], max_depth: int, current_depth: int):
        """Safe recursive directory crawler with configurable depth and cycle detection."""
        if current_depth > max_depth: return

        real_path = os.path.realpath(current_path)
        if real_path in self.visited_paths: return
        self.visited_paths.add(real_path)

        try:
            for entry in os.scandir(current_path):
                if entry.is_dir(follow_symlinks=False):
                    await self._recursive_ingest(entry.path, extensions, max_depth, current_depth + 1)
                elif entry.is_file():
                    if any(entry.name.endswith(ext) for ext in extensions):
                        await self._process_file(entry.path)
        except Exception as e:
            logger.error(f"Ingestor: Error scanning {current_path}: {e}")

    async def _process_file(self, full_path: str):
        """Process and redact a single file."""
        try:
            with open(full_path, encoding="utf-8", errors="ignore") as f:
                content = f.read()
                if self.redaction_patterns:
                    content = self.redaction_patterns.sub("[REDACTED]", content)

                # We chunk in 2000-char windows with 200-char overlap for context continuity.
                chunk_size = 2000
                overlap = 200
                for i in range(0, len(content), chunk_size - overlap):
                    chunk = content[i:i + chunk_size]
                    if len(chunk) < 50: continue # Skip tiny fragments

                    await self.memory.store_memory(
                        symbol="BRAIN_EVOLUTION",
                        debate_summary=f"SOURCE: {os.path.basename(full_path)} [Part {i//(chunk_size-overlap)+1}]\nCONTENT: {chunk}",
                        bias_str="REASONING_UPGRADE",
                        confidence=0.85
                    )
                    self.ingested_count += 1

                logger.debug(f"Ingestor: Absorbed {os.path.basename(full_path)} into Matrix DNA ({self.ingested_count} chunks).")
        except Exception as e:
            logger.error(f"Ingestor: Failed to read {full_path}: {e}")

    async def trigger_evolution_shift(self) -> None:
        """Signals to the Matrix that a 'Cognitive Shift' has occurred."""
        from intelligence_bus import get_bus
        bus = get_bus()
        await bus.publish(
            "evolution.knowledge_shift",
            {
                "timestamp": datetime.now().isoformat(),
                "new_fragments": self.ingested_count,
                "theme": "Sovereign Intelligence Synthesis",
            },
        )
        logger.info("Evolution: Knowledge Shift SIGNAL PUBLISHED.")

async def run_full_ingestion() -> None:
    from swarm_predictor import ChromaDeepMemory
    memory = ChromaDeepMemory()
    ingestor = KnowledgeIngestor(memory)
    source_dir = Vault.get("KNOWLEDGE_SOURCE_DIR", "data/knowledge")
    await ingestor.ingest_directory(source_dir)
    await ingestor.trigger_evolution_shift()

if __name__ == "__main__":
    asyncio.run(run_full_ingestion())
