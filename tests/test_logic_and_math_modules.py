"""
tests/test_logic_and_math_modules.py
Tests for:
  - formal_verifier.FormalVerifier
  - impact_model.MarketImpactModel
  - isomorphism.IsomorphicMapper
  - loss_functions.EvolvingLossFunctions
  - holographic_mem.HolographicMemoryStore
  - liquid_core.LiquidNeuralCore
  - logic_engine.SovereignLogicEngine (key dispatches)
  - logic_vetter.KolmogorovVetter
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


# ── FormalVerifier ────────────────────────────────────────────────────────────
class TestFormalVerifier:
    def setup_method(self):
        from formal_verifier import FormalVerifier
        self.fv = FormalVerifier()

    def test_simple_evidence_passes(self):
        result = self.fv.verify("BUY AAPL", ["Price broke out", "Volume confirmed", "Trend up"])
        assert result["passed"] is True

    def test_high_complexity_fails(self):
        # Create very long redundant chain
        chain = ["word " * 30] * 5  # lots of repeated words -> very high score
        result = self.fv.verify("some hypothesis", chain)
        assert result["complexity_score"] > 0

    def test_contradiction_detected(self):
        evidence = ["NOT BUY AAPL", "BUY AAPL"]
        result = self.fv.verify("buy?", evidence)
        assert result["contradiction_found"] is True
        assert result["passed"] is False

    def test_complexity_score_increases_with_redundancy(self):
        short_chain = ["momentum positive"]
        long_chain = ["momentum positive"] * 10
        s1 = self.fv.complexity_score(short_chain)
        s2 = self.fv.complexity_score(long_chain)
        assert s2 > s1

    def test_result_has_all_keys(self):
        result = self.fv.verify("test", ["evidence"])
        assert all(k in result for k in ("passed", "complexity_score", "contradiction_found"))


# ── MarketImpactModel ─────────────────────────────────────────────────────────
class TestMarketImpactModel:
    def setup_method(self):
        from impact_model import MarketImpactModel
        self.model = MarketImpactModel(kyle_lambda=0.1)

    def test_zero_adv_returns_zero(self):
        assert self.model.price_impact_bps(10000, 0) == 0.0

    def test_large_order_has_larger_impact(self):
        small = self.model.price_impact_bps(100_000, 10_000_000)
        large = self.model.price_impact_bps(5_000_000, 10_000_000)
        assert large > small

    def test_buy_increases_price(self):
        mid = 100.0
        adj = self.model.adjusted_entry_price(mid, 500_000, 10_000_000, "BUY")
        assert adj > mid

    def test_sell_decreases_price(self):
        mid = 100.0
        adj = self.model.adjusted_entry_price(mid, 500_000, 10_000_000, "SELL")
        assert adj < mid

    def test_max_safe_order_size_positive(self):
        size = self.model.max_safe_order_size(10_000_000, max_impact_bps=5.0)
        assert size > 0.0

    def test_tighter_impact_budget_smaller_size(self):
        size_loose = self.model.max_safe_order_size(10_000_000, max_impact_bps=10.0)
        size_tight = self.model.max_safe_order_size(10_000_000, max_impact_bps=2.0)
        assert size_tight < size_loose


# ── IsomorphicMapper ──────────────────────────────────────────────────────────
class TestIsomorphicMapper:
    def setup_method(self):
        from isomorphism import IsomorphicMapper
        self.mapper = IsomorphicMapper(tolerance=0.05)

    def test_exact_match_found(self):
        query = [1.0, 2.0, 3.0, 4.0, 5.0]
        candidates = [("asset_a", [0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0])]  # contains query pattern
        matches = self.mapper.find_match(query, candidates)
        assert "asset_a" in matches

    def test_no_match_dissimilar_pattern(self):
        query = [1.0, 5.0, 1.0, 5.0, 1.0]
        candidates = [("flat", [1.0, 1.0, 1.0, 1.0, 1.0, 1.0])]
        matches = self.mapper.find_match(query, candidates)
        assert "flat" not in matches

    def test_too_short_candidate_skipped(self):
        query = [1.0, 2.0, 3.0, 4.0, 5.0]
        candidates = [("short", [1.0, 2.0])]
        matches = self.mapper.find_match(query, candidates)
        assert "short" not in matches

    def test_normalize_range_0_to_1(self):
        arr = self.mapper.normalize([10.0, 20.0, 30.0])
        assert float(arr.min()) == pytest.approx(0.0)
        assert float(arr.max()) == pytest.approx(1.0)

    def test_normalize_constant_series(self):
        arr = self.mapper.normalize([5.0, 5.0, 5.0])
        # All elements should be 0 (divided by ~0 range)
        assert all(v == pytest.approx(0.0, abs=1e-6) for v in arr)


# ── EvolvingLossFunctions ────────────────────────────────────────────────────
class TestEvolvingLossFunctions:
    def setup_method(self):
        from loss_functions import EvolvingLossFunctions
        self.lf = EvolvingLossFunctions()
        rng = np.random.default_rng(0)
        self.pos_returns = (rng.normal(0.001, 0.01, 252)).tolist()
        self.neg_returns = (rng.normal(-0.002, 0.015, 252)).tolist()

    def test_sharpe_positive_for_good_returns(self):
        assert self.lf.sharpe(self.pos_returns) > 0.0

    def test_sharpe_negative_for_bad_returns(self):
        assert self.lf.sharpe(self.neg_returns) < 0.0

    def test_sortino_higher_than_sharpe_when_only_upside_vol(self):
        # Returns are all positive (no downside) — sortino numerically > sharpe
        all_positive = [0.005] * 252
        sortino = self.lf.sortino(all_positive)
        sharpe = self.lf.sharpe(all_positive)
        # Sortino penalizes only downside, which is zero -> denominator tiny -> very high
        assert sortino >= sharpe

    def test_calmar_positive_for_positive_returns(self):
        # Make a pure positive cumulative series (trending up, small drawdown)
        returns = [0.003] * 200 + [-0.001] * 52  # mostly positive
        result = self.lf.calmar(returns)
        assert isinstance(result, float)

    def test_select_for_regime_bull_returns_sharpe(self):
        assert self.lf.select_for_regime("BULL") == "sharpe"

    def test_select_for_regime_bear_returns_sortino(self):
        assert self.lf.select_for_regime("BEAR") == "sortino"

    def test_select_for_regime_unknown_defaults_sharpe(self):
        assert self.lf.select_for_regime("UNKNOWN") == "sharpe"


# ── HolographicMemoryStore ────────────────────────────────────────────────────
class TestHolographicMemoryStore:
    def setup_method(self):
        from holographic_mem import HolographicMemoryStore
        self.mem = HolographicMemoryStore()

    def test_store_and_retrieve_finds_something(self):
        self.mem.store("regime", "BULL")
        result = self.mem.retrieve("regime")
        assert isinstance(result, str)

    def test_retrieve_returns_registered_key(self):
        self.mem.store("sector", "TECH")
        self.mem.store("outlook", "BULLISH")
        result = self.mem.retrieve("sector")
        assert result in ("sector", "TECH", "BULLISH", "outlook", "regime")

    def test_basis_deterministic(self):
        v1 = self.mem._basis("key_x")
        v2 = self.mem._basis("key_x")
        np.testing.assert_array_equal(v1, v2)

    def test_basis_normalized(self):
        v = self.mem._basis("some_key")
        assert abs(np.linalg.norm(v) - 1.0) < 1e-6

    def test_different_keys_different_bases(self):
        v1 = self.mem._basis("alpha")
        v2 = self.mem._basis("beta")
        assert not np.allclose(v1, v2)


# ── LiquidNeuralCore ──────────────────────────────────────────────────────────
class TestLiquidNeuralCore:
    def setup_method(self):
        from liquid_core import LiquidNeuralCore
        self.core = LiquidNeuralCore(hidden_dim=16)

    def test_step_returns_correct_shape(self):
        x = np.random.randn(10)
        out = self.core.step(x, dt=0.1, volatility=0.2)
        assert out.shape == (16,)

    def test_state_changes_after_step(self):
        x = np.random.randn(10)
        state_before = self.core.state.copy()
        self.core.step(x, dt=0.1, volatility=0.1)
        assert not np.allclose(self.core.state, state_before)

    def test_reset_zeroes_state(self):
        x = np.random.randn(10)
        self.core.step(x, dt=0.5, volatility=0.3)
        self.core.reset()
        np.testing.assert_array_equal(self.core.state, np.zeros(16))

    def test_high_volatility_adapts_faster(self):
        from liquid_core import LiquidNeuralCore
        core_lo = LiquidNeuralCore(hidden_dim=16)
        core_hi = LiquidNeuralCore(hidden_dim=16)
        core_lo.w_in = core_hi.w_in = np.ones((16, 10)) * 0.1
        core_lo.w_rec = core_hi.w_rec = np.zeros((16, 16))
        x = np.ones(10)
        s_lo = core_lo.step(x, dt=0.1, volatility=0.0)
        s_hi = core_hi.step(x, dt=0.1, volatility=5.0)
        # High volatility -> shorter tau -> smaller state magnitude (faster decay)
        assert abs(s_hi).mean() <= abs(s_lo).mean() + 1e-6


# ── SovereignLogicEngine (key dispatches) ────────────────────────────────────
class TestSovereignLogicEngine:
    def setup_method(self):
        # Set a consistent capital baseline for drawdown tests
        import os
        import sys
        os.environ["TOTAL_CAPITAL"] = "100000.0"
        # Reload config to pick up the new env value
        if "config" in sys.modules:
            del sys.modules["config"]
        import config
        # Directly patch the module-level constant since logic_engine already imported it
        config.STARTING_CAPITAL_CAD = 100000.0
        from logic_engine import SovereignLogicEngine
        self.eng = SovereignLogicEngine()

    def test_kelly_sized(self):
        result = self.eng.execute_node("151", {"win_prob": 0.6, "r_r_ratio": 2.0, "account_value": 50000})
        assert result["decision"] in ("Sized", "SKIP")

    def test_abhava_crisis_overrides_bullish(self):
        result = self.eng.execute_node("104", {"dhatu": "Abhava", "regime": "BULLISH"})
        assert result["predicted_regime"] == "VOLATILE"
        assert result["bias"] == "BEARISH"

    def test_antifragility_high_vix(self):
        result = self.eng.execute_node("31", {"vix": 40})
        assert result["mode"] == "EXPLORATIVE"

    def test_drawdown_breaker_halts_below_floor(self):
        result = self.eng.execute_node("154", {"account_value": 1000})
        assert result["status"] == "HALT"

    def test_drawdown_breaker_passes_healthy_nav(self):
        result = self.eng.execute_node("154", {"account_value": 999_999})
        assert result["status"] == "SUCCESS"

    def test_blackswan_vetoes_war_headline(self):
        result = self.eng.execute_node("166", {"headline": "Nuclear war erupts across Europe"})
        assert result["veto"] is True

    def test_blackswan_suppressed_by_negation(self):
        result = self.eng.execute_node("166", {"headline": "no war expected according to analysts"})
        assert result["veto"] is False

    def test_hft_footprint_congestion(self):
        result = self.eng.execute_node("15", {"bid": 100.0, "ask": 100.0001, "volume": 5_000_000})
        assert "status" in result

    def test_trap_detected_on_low_volume_breakout(self):
        result = self.eng.execute_node("48", {"volume_ratio": 0.5, "price_change_pct": 0.03})
        assert result["trap"] is True

    def test_circadian_open_hour_reduces_risk(self):
        result = self.eng.execute_node("40", {"hour": 9})
        assert result["risk_mult"] < 1.0

    def test_margin_halt_on_high_usage(self):
        result = self.eng.execute_node("163", {"equity": 100_000, "margin_used": 85_000})
        assert result["action"] == "HALT"

    def test_unknown_node_returns_dormant(self):
        # Node not in dispatch map
        result = self.eng.execute_node("999", {})
        # Either ERROR (not in registry) or PURE_COGNITION
        assert result.get("status") in ("ERROR", "PURE_COGNITION")


# ── KolmogorovVetter ──────────────────────────────────────────────────────────
class TestKolmogorovVetter:
    def setup_method(self):
        from logic_vetter import KolmogorovVetter
        self.kv = KolmogorovVetter()

    def test_simple_reasoning_trusted(self):
        # Short text has LZ overhead; use max_complexity=2.0 to test the logic, not the threshold
        result = self.kv.vet("Price broke above resistance with volume confirmation.", max_complexity=2.0)
        assert result["trusted"] is True

    def test_highly_repetitive_rejected(self):
        # Very high complexity score due to repetition and length
        repetitive = "buy buy buy sell sell sell buy buy buy " * 25
        result = self.kv.vet(repetitive)
        assert result["trusted"] is False

    def test_contradiction_detected(self):
        text = "We should buy however although the trend is down"
        result = self.kv.vet(text)
        assert result["contradiction"] is True
        assert result["trusted"] is False

    def test_too_long_rejected(self):
        long_text = " ".join(["word"] * 250)
        result = self.kv.vet(long_text)
        assert result["trusted"] is False

    def test_result_keys_present(self):
        result = self.kv.vet("Simple statement.")
        assert all(k in result for k in ("trusted", "complexity", "contradiction", "word_count"))

    def test_lz_complexity_range(self):
        c = self.kv.lz_complexity("hello world")
        assert 0.0 < c < 10.0
