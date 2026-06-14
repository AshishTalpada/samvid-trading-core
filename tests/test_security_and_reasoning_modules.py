"""
tests/test_security_and_reasoning_modules.py
Tests for:
  - database_security.DatabaseSecurity (Fernet encryption)
  - llm_circuit_breaker.LLMCircuitBreaker
  - knowledge_graph.MacroKnowledgeGraph
  - feature_engine.RecursiveFeatureEliminator
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


# ── DatabaseSecurity ──────────────────────────────────────────────────────────
class TestDatabaseSecurity:
    def setup_method(self):
        """Inject a fresh valid Fernet key into the Vault before each test."""
        from cryptography.fernet import Fernet
        from vault import Vault
        from database_security import DatabaseSecurity

        # Reset any cached Fernet instance
        DatabaseSecurity._fernet = None
        DatabaseSecurity._hmac_key = None

        self._key = Fernet.generate_key().decode()
        Vault.set("DB_ENCRYPTION_KEY", self._key)
        self.ds = DatabaseSecurity

    def test_encrypt_returns_nonempty_string(self):
        enc = self.ds.encrypt("test_secret")
        assert isinstance(enc, str) and len(enc) > 0

    def test_encrypt_decrypt_roundtrip(self):
        plain = "my_api_key_12345"
        enc = self.ds.encrypt(plain)
        dec = self.ds.decrypt(enc)
        assert dec == plain

    def test_encrypt_empty_returns_empty(self):
        assert self.ds.encrypt("") == ""

    def test_decrypt_empty_returns_empty(self):
        assert self.ds.decrypt("") == ""

    def test_hmac_included_in_encrypted_string(self):
        enc = self.ds.encrypt("something")
        assert ":" in enc

    def test_tampered_hmac_raises(self):
        enc = self.ds.encrypt("secure_value")
        hmac_part, data_part = enc.split(":", 1)
        tampered = "DEADBEEF" * 8 + ":" + data_part
        with pytest.raises(RuntimeError, match="HMAC"):
            self.ds.decrypt(tampered)

    def test_encrypt_float_and_decrypt_float(self):
        val = 3.14159
        enc = self.ds.encrypt_float(val)
        dec = self.ds.decrypt_float(enc)
        assert dec == pytest.approx(val)

    def test_rotate_key_clears_cache(self):
        from cryptography.fernet import Fernet
        from vault import Vault
        from database_security import DatabaseSecurity

        new_key = Fernet.generate_key().decode()
        DatabaseSecurity.rotate_key(new_key)
        assert DatabaseSecurity._fernet is None
        # Confirm new key is in vault
        assert Vault.get("DB_ENCRYPTION_KEY") == new_key


# ── LLMCircuitBreaker ─────────────────────────────────────────────────────────
class TestLLMCircuitBreaker:
    def setup_method(self):
        from llm_circuit_breaker import LLMCircuitBreaker
        self.cb = LLMCircuitBreaker(
            failure_threshold=3, window_s=60.0, cooldown_s=5.0, default_timeout_s=0.1
        )

    def _fallback(self):
        return {"signal": "HOLD", "source": "fallback"}

    async def _fast_coro(self):
        return {"signal": "BUY", "source": "llm"}

    async def _slow_coro(self):
        await asyncio.sleep(10)  # far beyond timeout
        return {"signal": "BUY"}

    async def _failing_coro(self):
        raise ValueError("LLM API error")

    def test_initial_state_closed(self):
        from llm_circuit_breaker import CircuitState
        assert self.cb.state == CircuitState.CLOSED

    def test_success_returns_llm_result(self):
        result, is_fallback = asyncio.run(self.cb.call(self._fast_coro(), self._fallback))
        assert is_fallback is False
        assert result["source"] == "llm"

    def test_timeout_triggers_fallback(self):
        result, is_fallback = asyncio.run(self.cb.call(self._slow_coro(), self._fallback))
        assert is_fallback is True
        assert result["source"] == "fallback"

    def test_exception_triggers_fallback(self):
        result, is_fallback = asyncio.run(self.cb.call(self._failing_coro(), self._fallback))
        assert is_fallback is True

    def test_three_failures_trip_breaker(self):
        from llm_circuit_breaker import CircuitState
        for _ in range(3):
            asyncio.run(self.cb.call(self._failing_coro(), self._fallback))
        assert self.cb.state == CircuitState.OPEN

    def test_open_breaker_uses_fallback_instantly(self):
        from llm_circuit_breaker import CircuitState
        for _ in range(3):
            asyncio.run(self.cb.call(self._failing_coro(), self._fallback))
        assert self.cb.state == CircuitState.OPEN
        result, is_fallback = asyncio.run(self.cb.call(self._fast_coro(), self._fallback))
        assert is_fallback is True

    def test_stats_has_required_keys(self):
        stats = self.cb.stats
        assert all(k in stats for k in ("state", "recent_failures", "total_timeouts",
                                         "total_fallbacks", "threshold"))

    def test_total_timeouts_increments(self):
        asyncio.run(self.cb.call(self._slow_coro(), self._fallback))
        assert self.cb.stats["total_timeouts"] == 1


# ── MacroKnowledgeGraph ───────────────────────────────────────────────────────
class TestMacroKnowledgeGraph:
    def setup_method(self):
        from knowledge_graph import MacroKnowledgeGraph
        self.kg = MacroKnowledgeGraph()

    def test_add_and_traverse_single_level(self):
        self.kg.add_relation("FED_RATE_HIKE", "FINANCIALS")
        impacted = self.kg.traverse("FED_RATE_HIKE", depth=1)
        assert "FINANCIALS" in impacted

    def test_two_depth_traversal(self):
        self.kg.add_relation("FED_RATE_HIKE", "FINANCIALS")
        self.kg.add_relation("FINANCIALS", "JPM")
        impacted = self.kg.traverse("FED_RATE_HIKE", depth=2)
        assert "FINANCIALS" in impacted
        assert "JPM" in impacted

    def test_root_not_in_impacted(self):
        self.kg.add_relation("OIL_SHOCK", "ENERGY")
        impacted = self.kg.traverse("OIL_SHOCK", depth=1)
        assert "OIL_SHOCK" not in impacted

    def test_no_relations_returns_empty(self):
        impacted = self.kg.traverse("UNKNOWN_EVENT", depth=2)
        assert impacted == []

    def test_cycle_handling(self):
        self.kg.add_relation("A", "B")
        self.kg.add_relation("B", "A")
        # Should not loop infinitely
        impacted = self.kg.traverse("A", depth=3)
        assert isinstance(impacted, list)

    def test_depth_limits_traversal(self):
        self.kg.add_relation("EVENT", "L1")
        self.kg.add_relation("L1", "L2")
        self.kg.add_relation("L2", "L3")
        impacted_1 = self.kg.traverse("EVENT", depth=1)
        impacted_3 = self.kg.traverse("EVENT", depth=3)
        assert len(impacted_3) >= len(impacted_1)


# ── RecursiveFeatureEliminator ─────────────────────────────────────────────────
class TestRecursiveFeatureEliminator:
    def setup_method(self):
        from feature_engine import RecursiveFeatureEliminator
        self.rfe = RecursiveFeatureEliminator()
        rng = np.random.default_rng(42)
        # X: 100 samples, 5 features; y: only depends on col 0
        self.X = rng.standard_normal((100, 5))
        self.y = self.X[:, 0] * 2.0 + rng.standard_normal(100) * 0.1
        # Simple linear predictor using only col 0
        self._model = lambda X_: X_[:, 0] * 2.0

    def test_compute_importance_shape(self):
        imp = self.rfe.compute_importance(self.X, self.y, self._model)
        assert imp.shape == (5,)

    def test_important_feature_has_positive_importance(self):
        imp = self.rfe.compute_importance(self.X, self.y, self._model)
        # Shuffling col 0 should increase error
        assert imp[0] > 0.0

    def test_irrelevant_features_close_to_zero(self):
        imp = self.rfe.compute_importance(self.X, self.y, self._model)
        # Cols 1-4 are noise; their importance should be near zero or even negative
        for i in range(1, 5):
            assert abs(imp[i]) < imp[0]

    def test_eliminate_keeps_important_features(self):
        imp = np.array([5.0, -1.0, 0.0, 2.0, -0.5])
        names = ["A", "B", "C", "D", "E"]
        kept = self.rfe.eliminate(names, imp, threshold=0.0)
        assert "A" in kept
        assert "D" in kept

    def test_eliminate_removes_zero_importance(self):
        imp = np.array([5.0, 0.0, 1.0])
        names = ["alpha", "beta", "gamma"]
        kept = self.rfe.eliminate(names, imp, threshold=0.0)
        assert "beta" not in kept

    def test_eliminate_all_above_threshold(self):
        imp = np.array([0.5, 0.5, 0.5])
        names = ["x", "y", "z"]
        kept = self.rfe.eliminate(names, imp, threshold=1.0)
        assert kept == []
