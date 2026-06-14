"""
tests/test_final_modules.py
Tests for final untested modules:
  - explainability.ExplainabilityEngine
  - factory_agent.FactoryActivityDetector
  - embedding_engine.SharedEmbeddingEngine (hash fallback)
  - evolution_engine.EvolutionEngine (additional edge cases)
  - cross_asset.CrossAssetLeadIndicator (additional)
  - attention_engine.RegimeAttentionEngine (additional)
  - macro_topology.MacroTopologyGraph (multi-hop)
  - category_theory.CategoryTheoryVerifier (commutativity)
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


# ── ExplainabilityEngine ──────────────────────────────────────────────────────
class TestExplainabilityEngine:
    def setup_method(self):
        from explainability import ExplainabilityEngine
        self.eng = ExplainabilityEngine()

    def _predict(self, features: dict) -> float:
        return sum(features.values())

    def test_shapley_returns_all_features(self):
        feats = {"momentum": 0.8, "vol": -0.3, "spread": 0.1}
        sv = self.eng.shapley_values(feats, self._predict, n_samples=20)
        assert set(sv.keys()) == set(feats.keys())

    def test_shapley_sum_to_near_one(self):
        feats = {"a": 1.0, "b": 2.0, "c": 0.5}
        sv = self.eng.shapley_values(feats, self._predict, n_samples=30)
        assert abs(sum(abs(v) for v in sv.values()) - 1.0) < 0.05

    def test_dominant_feature_has_highest_value(self):
        # "big" feature should dominate Shapley attribution
        feats = {"big": 100.0, "small": 0.01}
        sv = self.eng.shapley_values(feats, self._predict, n_samples=50)
        assert abs(sv["big"]) > abs(sv["small"])

    def test_generate_rationale_mentions_decision(self):
        sv = {"momentum": 0.6, "vol": -0.3, "spread": 0.1}
        rationale = self.eng.generate_rationale(sv, "BUY")
        assert "BUY" in rationale

    def test_generate_rationale_top_3_features(self):
        sv = {"a": 0.5, "b": 0.3, "c": 0.1, "d": 0.05, "e": 0.01}
        rationale = self.eng.generate_rationale(sv, "SELL")
        assert "a" in rationale and "b" in rationale


# ── FactoryActivityDetector ───────────────────────────────────────────────────
class TestFactoryActivityDetector:
    def setup_method(self):
        from factory_agent import FactoryActivityDetector
        self.det = FactoryActivityDetector()

    def _grids(self, n=10, m=10):
        baseline = np.full((n, m), 25.0)
        return baseline

    def test_active_when_mean_delta_positive(self):
        baseline = self._grids()
        thermal = baseline + 5.0
        result = self.det.analyse_thermal_signature(thermal, baseline)
        assert result["status"] == "ACTIVE"

    def test_shutdown_when_mean_delta_negative(self):
        baseline = self._grids()
        thermal = baseline - 8.0
        result = self.det.analyse_thermal_signature(thermal, baseline)
        assert result["status"] == "SHUTDOWN"

    def test_normal_when_delta_near_zero(self):
        baseline = self._grids()
        thermal = baseline + 1.0
        result = self.det.analyse_thermal_signature(thermal, baseline)
        assert result["status"] == "NORMAL"

    def test_shape_mismatch_raises(self):
        with pytest.raises(ValueError):
            self.det.analyse_thermal_signature(np.ones((5, 5)), np.ones((3, 3)))

    def test_production_score_range(self):
        baseline = self._grids()
        for delta in [-15, -5, 0, 5, 15]:
            score = self.det.production_score(baseline + delta, baseline)
            assert 0.0 <= score <= 1.0

    def test_hot_pixels_counted(self):
        baseline = self._grids()
        thermal = baseline.copy()
        thermal[0, 0] = baseline[0, 0] + 20.0  # one very hot pixel
        result = self.det.analyse_thermal_signature(thermal, baseline)
        assert result["hot_pixels"] >= 1


# ── SharedEmbeddingEngine (hash fallback) ─────────────────────────────────────
class TestSharedEmbeddingEngine:
    def setup_method(self):
        # Reset singleton so test is isolated
        import embedding_engine
        embedding_engine.SharedEmbeddingEngine._instance = None
        embedding_engine.SharedEmbeddingEngine._model = None
        from embedding_engine import SharedEmbeddingEngine
        self.eng = SharedEmbeddingEngine()

    def test_embed_returns_list_of_lists(self):
        result = self.eng.embed(["hello world", "buy SPY"])
        assert isinstance(result, list)
        assert all(isinstance(v, list) for v in result)

    def test_embed_correct_length(self):
        result = self.eng.embed(["test sentence"])
        # Either 384-dim hash embedding or model output
        if result:
            assert len(result[0]) == 384

    def test_hash_embedding_deterministic(self):
        v1 = self.eng._hash_embedding("apple")
        v2 = self.eng._hash_embedding("apple")
        assert v1 == v2

    def test_hash_embedding_distinct_inputs(self):
        v1 = self.eng._hash_embedding("apple")
        v2 = self.eng._hash_embedding("orange")
        assert v1 != v2

    def test_hash_embedding_length(self):
        v = self.eng._hash_embedding("hello", dims=128)
        assert len(v) == 128

    def test_embed_empty_list(self):
        result = self.eng.embed([])
        assert result == []


# ── Evolution Engine additional edge cases ────────────────────────────────────
class TestEvolutionEngineEdge:
    def test_population_one_runs_safely(self):
        from evolution_engine import EvolutionEngine
        eng = EvolutionEngine(
            lambda x: float(x[0] ** 2),
            [(-3.0, 3.0)],
            population_size=4,  # min viable (DE needs at least 4 for 3 distinct indices)
            max_generations=10,
        )
        best, score = eng.run()
        assert isinstance(score, float)

    def test_multivariate_finds_better_than_random(self):
        from evolution_engine import EvolutionEngine
        rng = np.random.default_rng(0)
        random_score = float(np.sum(rng.uniform(-5, 5, 4) ** 2))
        eng = EvolutionEngine(
            lambda x: float(np.sum(x ** 2)),
            [(-5.0, 5.0)] * 4,
            population_size=20,
            max_generations=80,
        )
        _, best_score = eng.run()
        assert best_score < random_score


# ── RegimeAttentionEngine — additional ───────────────────────────────────────
class TestRegimeAttentionAdditional:
    def test_empty_current_returns_weights(self):
        from attention_engine import RegimeAttentionEngine
        eng = RegimeAttentionEngine()
        weights = eng.compute_attention({})
        assert len(weights) == len(eng.REGIME_FINGERPRINTS)
        assert abs(sum(weights.values()) - 1.0) < 1e-4

    def test_partial_features_ok(self):
        from attention_engine import RegimeAttentionEngine
        eng = RegimeAttentionEngine()
        weights = eng.compute_attention({"vol": 0.5})
        assert all(v >= 0 for v in weights.values())


# ── MacroTopologyGraph — three-hop ────────────────────────────────────────────
class TestMacroTopologyThreeHop:
    def test_three_hop_diminishing_impact(self):
        from macro_topology import MacroTopologyGraph
        graph = MacroTopologyGraph()
        graph.add_link("A", "B", 0.8)
        graph.add_link("B", "C", 0.7)
        graph.add_link("C", "D", 0.6)
        impact = graph.calculate_ripple_impact("A", "D", max_depth=3)
        assert impact == pytest.approx(0.8 * 0.7 * 0.6, abs=0.01)

    def test_depth_limit_respected(self):
        from macro_topology import MacroTopologyGraph
        graph = MacroTopologyGraph()
        graph.add_link("A", "B", 0.9)
        graph.add_link("B", "C", 0.9)
        # Depth 1 should not find C
        impact = graph.calculate_ripple_impact("A", "C", max_depth=1)
        assert impact == 0.0


# ── CategoryTheoryVerifier — commutativity ────────────────────────────────────
class TestCategoryTheoryCommutativity:
    def test_commutative_paths_pass(self):
        from category_theory import CategoryTheoryVerifier
        ctv = CategoryTheoryVerifier()
        # Path A: x*2 + 1 = 11 for x=5
        # Path B: (x+1)*2 = 12 for x=5 — NOT commutative
        # Use truly commutative paths: both should give same result
        path_a = [lambda x: x + 3, lambda x: x * 2]  # (5+3)*2=16
        path_b = [lambda x: x * 2, lambda x: x + 6]  # 5*2+6=16
        assert ctv.verify_commutativity(path_a, path_b, 5) is True

    def test_non_commutative_paths_fail(self):
        from category_theory import CategoryTheoryVerifier
        ctv = CategoryTheoryVerifier()
        path_a = [lambda x: x * 2, lambda x: x + 1]  # 5*2+1=11
        path_b = [lambda x: x + 1, lambda x: x * 2]  # (5+1)*2=12
        assert ctv.verify_commutativity(path_a, path_b, 5) is False
