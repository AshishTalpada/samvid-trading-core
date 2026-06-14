"""
tests/test_system_core_modules.py
Tests for:
  - lora_manager.LoRAManager
  - memdir.MemoryManager
  - mind_macros.MindMacros
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


# ── LoRAManager ───────────────────────────────────────────────────────────────
class TestLoRAManager:
    def setup_method(self):
        from lora_manager import LoRAManager
        self.mgr = LoRAManager()

    def test_known_sector_returns_correct_path(self):
        path = self.mgr.get_adapter_path("TECH")
        assert "tech_lora" in path

    def test_unknown_sector_returns_default(self):
        path = self.mgr.get_adapter_path("UNDERWATER_BASKET_WEAVING")
        assert "base_lora" in path

    def test_case_insensitive_sector(self):
        assert self.mgr.get_adapter_path("tech") == self.mgr.get_adapter_path("TECH")

    def test_first_swap_returns_true(self):
        result = self.mgr.swap_adapter("TECH")
        assert result is True

    def test_same_adapter_returns_false(self):
        self.mgr.swap_adapter("ENERGY")
        result = self.mgr.swap_adapter("ENERGY")  # already active
        assert result is False

    def test_swap_updates_current_adapter(self):
        self.mgr.swap_adapter("MACRO")
        assert "macro_lora" in (self.mgr.current_adapter or "")

    def test_all_sectors_have_paths(self):
        from lora_manager import SECTOR_ADAPTER_MAP
        for sector in ("TECH", "ENERGY", "MACRO", "DEFAULT"):
            assert sector in SECTOR_ADAPTER_MAP


# ── MemoryManager ─────────────────────────────────────────────────────────────
class TestMemoryManager:
    def setup_method(self):
        self._tmpdir = tempfile.mkdtemp()
        from memdir import MemoryManager
        # Patch PROJECT_PATH to use tmp dir
        self.mm = MemoryManager(root_path=self._tmpdir)

    def teardown_method(self):
        # Make files writable so cleanup works
        for fname in ("TRADING.md", ".trading.md"):
            p = Path(self._tmpdir) / fname
            if p.exists():
                import stat
                p.chmod(p.stat().st_mode | stat.S_IWRITE)

    def test_prime_directive_created_on_init(self):
        assert (Path(self._tmpdir) / "TRADING.md").exists()

    def test_session_memory_created_on_init(self):
        assert (Path(self._tmpdir) / ".trading.md").exists()

    def test_get_prime_directive_returns_string(self):
        content = self.mm.get_prime_directive()
        assert isinstance(content, str) and len(content) > 0

    def test_get_session_memory_returns_string(self):
        content = self.mm.get_session_memory()
        assert isinstance(content, str)

    def test_update_session_memory_persists(self):
        # Make writable first
        p = Path(self._tmpdir) / ".trading.md"
        import stat
        p.chmod(p.stat().st_mode | stat.S_IWRITE)
        self.mm.update_session_memory("# Test update\n- Symbol: AAPL\n", mode="w")
        read_back = self.mm.get_session_memory()
        assert "AAPL" in read_back

    def test_get_full_context_has_both_sections(self):
        context = self.mm.get_full_context()
        assert "LONG-TERM MEMORY" in context
        assert "SESSION CONTEXT" in context

    def test_prime_directive_protected_read_only(self):
        import stat
        p = Path(self._tmpdir) / "TRADING.md"
        mode = p.stat().st_mode
        # Should not have user write bit
        assert not (mode & stat.S_IWRITE)


# ── MindMacros ────────────────────────────────────────────────────────────────
class TestMindMacros:
    def setup_method(self):
        from mind_macros import MindMacros
        self.mm = MindMacros

    def test_certified_tool_passes(self):
        assert self.mm.is_tool_signed("heal_code") is True

    def test_uncertified_tool_blocked(self):
        assert self.mm.is_tool_signed("delete_all_positions") is False

    def test_sensitive_tools_subset_of_certified(self):
        assert self.mm.SENSITIVE_TOOLS.issubset(
            self.mm.CERTIFIED_TOOLS | {"run_system_command"}
        )

    def test_validate_risk_passes_safe(self):
        assert self.mm.validate_risk(1.5, "SPY") is True

    def test_validate_risk_fails_over_limit(self):
        assert self.mm.validate_risk(2.0, "SPY") is False

    def test_validate_risk_crypto_higher_limit(self):
        # BTC can tolerate up to 5%
        assert self.mm.validate_risk(4.5, "BTC") is True

    def test_validate_risk_crypto_still_fails_extreme(self):
        assert self.mm.validate_risk(5.0, "ETH") is False

    def test_commission_buffer_included_in_risk(self):
        # 1.95 + 0.1 buffer = 2.05 > 2.0 limit
        assert self.mm.validate_risk(1.95, "SPY") is False

    def test_constants_are_correct(self):
        assert self.mm.ABSOLUTE_MAX_LOSS_PERCENT == 2.0
        assert self.mm.REQUIRED_CANDLE_COUNT == 50
        assert self.mm.FORCED_LATENCY_GATE_MS == 250
