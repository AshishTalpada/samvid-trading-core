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

        from database_security import DatabaseSecurity
        from vault import Vault

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

        from database_security import DatabaseSecurity
        from vault import Vault

        new_key = Fernet.generate_key().decode()
        DatabaseSecurity.rotate_key(new_key)
        assert DatabaseSecurity._fernet is None
        # Confirm new key is in vault
        assert Vault.get("DB_ENCRYPTION_KEY") == new_key


# ── Vault Tests ───────────────────────────────────────────────────────────────
class TestVault:
    def setup_method(self):
        """Clear cache before each test."""
        from vault import Vault

        Vault.clear_cache()

    def test_is_sensitive_detects_known_keys(self):
        from vault import Vault

        assert Vault._is_sensitive("ANTHROPIC_API_KEY") is True
        assert Vault._is_sensitive("OPENAI_API_KEY") is True
        assert Vault._is_sensitive("TELEGRAM_BOT_TOKEN") is True

    def test_is_sensitive_detects_pattern_keys(self):
        from vault import Vault

        assert Vault._is_sensitive("SOME_API_KEY") is True
        assert Vault._is_sensitive("DB_PASSWORD") is True
        assert Vault._is_sensitive("AUTH_TOKEN") is True
        assert Vault._is_sensitive("SECRET_KEY") is True

    def test_is_sensitive_allows_non_sensitive(self):
        from vault import Vault

        assert Vault._is_sensitive("LOG_LEVEL") is False
        assert Vault._is_sensitive("PORT") is False
        assert Vault._is_sensitive("DEBUG") is False

    def test_get_returns_cached_value(self):
        from vault import Vault

        Vault._cache["TEST_KEY"] = "cached_value"
        assert Vault.get("TEST_KEY") == "cached_value"

    def test_get_falls_to_env_for_non_sensitive(self):
        from vault import Vault

        import os

        os.environ["NON_SENSITIVE_VAR"] = "env_value"
        assert Vault.get("NON_SENSITIVE_VAR") == "env_value"
        del os.environ["NON_SENSITIVE_VAR"]

    def test_get_returns_default_when_missing(self):
        from vault import Vault

        assert Vault.get("MISSING_KEY", default="default_val") == "default_val"

    def test_set_populates_cache(self):
        from vault import Vault

        Vault.set("CACHE_TEST", "value123")
        assert Vault._cache["CACHE_TEST"] == "value123"

    def test_set_graceful_on_keyring_failure(self):
        from vault import Vault

        # Mock keyring to raise exception
        import keyring

        original_set = keyring.set_password

        def mock_set_error(*args, **kwargs):
            raise Exception("Keyring unavailable")

        keyring.set_password = mock_set_error

        Vault.set("FAIL_TEST", "value")  # Should not crash, just log warning

        # Should still be in cache
        assert Vault._cache["FAIL_TEST"] == "value"

        keyring.set_password = original_set

    def test_delete_removes_from_cache(self):
        from vault import Vault

        Vault._cache["DELETE_TEST"] = "value"
        Vault.delete("DELETE_TEST")
        assert "DELETE_TEST" not in Vault._cache

    def test_clear_cache_empties_all(self):
        from vault import Vault

        Vault._cache["KEY1"] = "val1"
        Vault._cache["KEY2"] = "val2"
        Vault.clear_cache()
        assert len(Vault._cache) == 0

    def test_get_all_redactable_filters_short_values(self):
        from vault import Vault

        # Set actual sensitive keys in Vault
        Vault.set("OPENAI_API_KEY", "ab")  # Too short, should be filtered
        Vault.set("ANTHROPIC_API_KEY", "valid_secret_key_12345")

        values = Vault.get_all_redactable_values()
        assert "ab" not in values
        assert "valid_secret_key_12345" in values


# ── RiskInvariants Tests ───────────────────────────────────────────────────────────
class TestRiskInvariants:
    def setup_method(self):
        from risk_invariants import RiskInvariants

        self.ri = RiskInvariants

    def test_order_throttler_allows_within_limit(self):
        from risk_invariants import OrderThrottler

        ot = OrderThrottler(max_orders=3, per_seconds=60)
        assert ot.can_submit() is True
        assert ot.can_submit() is True
        assert ot.can_submit() is True
        assert ot.can_submit() is False  # 4th submission throttled

    def test_order_throttler_resets_after_window(self):
        from risk_invariants import OrderThrottler
        from datetime import datetime, timedelta, timezone
        from collections import deque

        ot = OrderThrottler(max_orders=2, per_seconds=1)
        assert ot.can_submit() is True
        assert ot.can_submit() is True
        assert ot.can_submit() is False

        # Manually set old timestamps to simulate window expiry
        ot._timestamps = deque([datetime.now(timezone.utc) - timedelta(seconds=2)])
        assert ot.can_submit() is True  # Should allow after window expiry

    def test_order_throttler_reset_clears_state(self):
        from risk_invariants import OrderThrottler

        ot = OrderThrottler(max_orders=1, per_seconds=60)
        ot.can_submit()
        assert ot.can_submit() is False
        ot.reset()
        assert ot.can_submit() is True

    def test_verify_config_detects_missing_constant(self):
        import config

        original_val = getattr(config, "SYSTEM_MAX_RISK", None)
        if hasattr(config, "SYSTEM_MAX_RISK"):
            delattr(config, "SYSTEM_MAX_RISK")

        result = self.ri.verify_config()
        assert result is False  # Should detect missing constant

        if original_val is not None:
            config.SYSTEM_MAX_RISK = original_val

    def test_verify_config_detects_out_of_bounds(self):
        import config

        original_val = getattr(config, "SYSTEM_MAX_RISK", 0.01)
        config.SYSTEM_MAX_RISK = 0.5  # Way above max of 0.05

        result = self.ri.verify_config()
        assert result is False

        config.SYSTEM_MAX_RISK = original_val

    def test_is_mutation_safe_accepts_valid_value(self):
        assert self.ri.is_mutation_safe("SYSTEM_MAX_RISK", 0.01) is True
        assert self.ri.is_mutation_safe("RISK_PER_TRADE_PCT", 0.005) is True

    def test_is_mutation_safe_rejects_invalid_value(self):
        assert self.ri.is_mutation_safe("SYSTEM_MAX_RISK", 0.1) is False  # Above max
        assert self.ri.is_mutation_safe("RISK_PER_TRADE_PCT", 0.0001) is False  # Below min

    def test_is_mutation_safe_rejects_unknown_key(self):
        assert self.ri.is_mutation_safe("UNKNOWN_KEY", 0.01) is False

    def test_audit_trade_parameters_rejects_non_numeric(self):
        assert self.ri.audit_trade_parameters("invalid", 10000) is False
        assert self.ri.audit_trade_parameters(100, "invalid") is False

    def test_audit_trade_parameters_rejects_non_finite(self):
        import math

        assert self.ri.audit_trade_parameters(float("inf"), 10000) is False
        assert self.ri.audit_trade_parameters(100, float("nan")) is False

    def test_audit_trade_parameters_rejects_negative_balance(self):
        assert self.ri.audit_trade_parameters(100, -1000) is False
        assert self.ri.audit_trade_parameters(-100, 1000) is False

    def test_audit_trade_parameters_rejects_excessive_risk(self):
        assert self.ri.audit_trade_parameters(400, 10000) is False  # 4% > 3% hard limit

    def test_audit_trade_parameters_accepts_valid(self):
        assert self.ri.audit_trade_parameters(100, 10000) is True  # 1% risk
        assert self.ri.audit_trade_parameters(200, 10000) is True  # 2% risk

    def test_check_notional_rejects_non_numeric(self):
        assert self.ri.check_notional("AAPL", "invalid", 150) is False
        assert self.ri.check_notional("AAPL", 100, "invalid") is False

    def test_check_notional_rejects_invalid_economics(self):
        import math

        assert self.ri.check_notional("AAPL", 0, 150) is False
        assert self.ri.check_notional("AAPL", 100, 0) is False
        assert self.ri.check_notional("AAPL", float("inf"), 150) is False

    def test_check_notional_enforces_cap(self):
        # SPY cap is $200,000
        assert self.ri.check_notional("SPY", 1000, 150) is True  # $150,000
        assert self.ri.check_notional("SPY", 2000, 150) is False  # $300,000 > cap

    def test_check_notional_uses_default_for_unknown(self):
        # DEFAULT cap is $40,000
        assert self.ri.check_notional("UNKNOWN", 200, 150) is True  # $30,000
        assert self.ri.check_notional("UNKNOWN", 500, 150) is False  # $75,000 > cap

    def test_check_notional_case_insensitive(self):
        assert self.ri.check_notional("spy", 1000, 150) is True
        assert self.ri.check_notional("Spy", 1000, 150) is True


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
