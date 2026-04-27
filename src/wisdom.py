import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from system_types import Position

logger = logging.getLogger(__name__)


class WisdomRepository:
    """
    Samvid v1.0-beta 'Wisdom' Repository (Agent L).
    Implements 'Session Wisdom Preservation' directly from the Claude-Code memdir pattern.
    Stores and retrieves 'Post-Mortem' markdown analytics for every trade.
    """

    def __init__(self, memory_dir: str = "data/memory") -> None:
        self.memory_dir = Path(memory_dir)
    async def load_all_wisdom_async(self) -> str:
        """Asynchronously load wisdom context to prevent startup hangs."""
        import asyncio
        return await asyncio.to_thread(self.load_all_wisdom)

    def load_all_wisdom(self) -> str:
        """
        Loads the most recent post-mortems into a high-context string.
        GAP-63 FIX: Optimized file scanning to avoid startup hangs.
        """
        full_context = ""
        scent_path = self.memory_dir / "SESSION_DENSITY_SCENT.md"
        if scent_path.exists():
            try:
                full_context += f"### RECENT DENSITY SCENT:\n{scent_path.read_text()}\n"
            except Exception: pass

        # 1. Iterative Scan (Anti-DoS)
        # Instead of list(glob), we iterate and collect mtimes for sorting
        wisdom_data = []
        try:
            if self.memory_dir.exists():
                for wf in self.memory_dir.iterdir():
                    if wf.suffix == ".md" and "SESSION_DENSITY_SCENT" not in wf.name:
                        # Only collect what we need to sort
                        wisdom_data.append((wf, wf.stat().st_mtime))
        except Exception as e:
            logger.error(f"Wisdom: Directory iteration failed: {e}")
            return full_context

        # 2. Sort and Limit to Top 50 (Samvid v1.0-beta)
        # We only read the files we actually intend to use
        for wf, _mtime in sorted(wisdom_data, key=lambda x: x[1], reverse=True)[:50]:
            try:
                full_context += f"\n--- WISDOM: {wf.name} ---\n{wf.read_text()}"
            except Exception as e:
                logger.error(f"Wisdom: Failed to read {wf.name}: {e}")
        return full_context

    async def compress_session_wisdom(self, bridge: Any) -> None:
        """PILLAR 5: Context Thinning (9.99 Upgrade)
        Recursively summarizes recent wisdom into a high-density 'Density Scent' file.
        """
        all_wisdom = self.load_all_wisdom()
        # GAP-62 FIX: Increased threshold to 5000 to avoid aggressive 'Amnesia'
        if len(all_wisdom) < 5000:
            return  # Only thin if context is bloating

        logger.info("📚 Wisdom: Initiating Context Thinning (Density Scent Generation)...")
        # GAP-110 FIX: Explicitly forbid removal of Alpha/Technical findings
        prompt = (
            f"TASK: RECURSIVE ALPHA-PRESERVING SUMMARIZATION\nCONTEXT:\n{all_wisdom}\n\n"
            "INSTRUCTION: Synthesize these post-mortems into a 10-bullet 'Density Scent'.\n"
            "CRITICAL: Do NOT remove technical alpha findings (e.g. specific RSI levels, Dhatu states, or Catalyst scores).\n"
            "Only remove redundant formatting and boilerplate text."
        )

        # Use the bridge to access the Ultrathink reasoning model
        scent = await bridge.call_tool("pause_and_reason", task=prompt)
        summary = scent.get("summary") or scent.get("reasoning", "")

        if summary:
            scent_path = self.memory_dir / "SESSION_DENSITY_SCENT.md"
            scent_path.write_text(f"### DENSITY SCENT (Last Updated: {datetime.now()})\n{summary}")
            logger.info("✅ Wisdom: Global Density Scent synthesized. Old context thinned.")

    def write_post_mortem(self, pos: Position, outcome: str, pnl: float, reasoning: str) -> None:
        """Generates a high-fidelity Post-Mortem Markdown file for Agent D to inhale."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = self.memory_dir / f"PM_{pos.symbol}_{timestamp}.md"

        content = f"""# TRADE POST-MORTEM: {pos.symbol}
- **ID**: {pos.trade_id}
- **Timestamp**: {timestamp}
- **Pattern**: {pos.pattern}
- **Regime**: {pos.regime_at_entry}
- **Outcome**: {outcome} (PnL: ${pnl:,.2f})
- **Catalyst Score**: {pos.catalyst_score:.1f}
- **Dhatu State**: {pos.dhatu_state}

## COGNITIVE REASONING:
{reasoning}

## SOVEREIGN INSIGHT:
- If PnL < 0: Why was the signal faulty? Was there a regime shift or an 'Abhava' condition missed?
- If PnL > 0: What was the primary alpha-driver? Did it reach the first R-Multiple target cleanly?
"""
        try:
            filename.write_text(content)
            logger.info(f"📚 Wisdom: Post-Mortem synthesized for {pos.symbol} at {filename}")
        except Exception as e:
            logger.error(f"Wisdom: Failed to write post-mortem: {e}")


class SkillTreeManager:
    """
    Samvid v1.0-beta 'Autonomy Skill Tree' (Agent M).
    Manages the 'unlocked' capabilities of the Matrix based on performance.
    """

    def __init__(self, config_path: str = "data/skills.json") -> None:
        self.path = Path(config_path)
        self.skills = self._load()

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return self._get_default_skills()
        try:
            content = self.path.read_text()
            if not content.strip():
                return self._get_default_skills()
            data = json.loads(content)
            return data if data is not None else self._get_default_skills()
        except (json.JSONDecodeError, Exception):
            return self._get_default_skills()

    def _get_default_skills(self) -> dict[str, Any]:
        """GAP-111 FIX: Scaled thresholds for realistic account progress."""
        return {
            "autonomy_level": 1,
            "unlocked": ["discovery", "analysis", "vetting"],
            "pnl_to_next": 250.0,  # Reduced from 1000.0 for $500 accounts
            "drawdown_limit": 150.0,
        }

    def is_unlocked(self, skill: str) -> bool:
        return skill in self.skills.get("unlocked", [])

    def unlock(self, skill: str) -> None:
        if skill not in self.skills["unlocked"]:
            self.skills["unlocked"].append(skill)
            self._save()
            logger.info(f"✨ SKILL UNLOCKED: The Matrix has learned '{skill}' mastery. ✨")

    def _save(self) -> None:
        """GAP-112 FIX: Atomic save protocol for skills configuration."""
        try:
            temp_path = self.path.with_suffix(".tmp")
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(self.skills, f, indent=4)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temp_path, self.path)
        except Exception as e:
            logger.error(f"SkillTreeManager: Failed to save skills: {e}")
