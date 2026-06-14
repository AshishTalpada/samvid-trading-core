"""
tests/test_quantitative_engines.py
Tests for quantitative engine modules:
  - attention_engine.RegimeAttentionEngine
  - ode_predictor.ContinuousNeuralODE
  - sparse_attention.SparseAttentionEngine
  - cross_asset.CrossAssetLeadIndicator
  - quantum_tuning.QuantumInspiredOptimizer
  - tuner.QuantumTuner
  - live_trainer.OnlineLiveTrainer
  - rlhf_trainer.RLHFOnlineTrainer
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


# ── RegimeAttentionEngine ─────────────────────────────────────────────────────
class TestRegimeAttentionEngine:
    def setup_method(self):
        from attention_engine import RegimeAttentionEngine
        self.eng = RegimeAttentionEngine()

    def test_returns_dict_with_all_regimes(self):
        current = {"vol": 0.85, "credit_spread": 0.8, "correlation": 0.90}
        weights = self.eng.compute_attention(current)
        assert "2008_GFC" in weights
        assert "NORMAL_BULL" in weights

    def test_weights_sum_to_one(self):
        current = {"vol": 0.5, "credit_spread": 0.4, "correlation": 0.6}
        weights = self.eng.compute_attention(current)
        assert abs(sum(weights.values()) - 1.0) < 1e-4

    def test_crisis_conditions_match_gfc(self):
        current = {"vol": 0.9, "credit_spread": 0.9, "correlation": 0.95}
        weights = self.eng.compute_attention(current)
        assert weights["2008_GFC"] == max(weights.values())

    def test_bull_conditions_match_normal(self):
        current = {"vol": 0.15, "credit_spread": 0.08, "correlation": 0.25}
        weights = self.eng.compute_attention(current)
        assert weights["NORMAL_BULL"] == max(weights.values())

    def test_all_weights_non_negative(self):
        weights = self.eng.compute_attention({"vol": 0.3})
        assert all(v >= 0 for v in weights.values())


# ── ContinuousNeuralODE ───────────────────────────────────────────────────────
class TestContinuousNeuralODE:
    def setup_method(self):
        from ode_predictor import ContinuousNeuralODE
        np.random.seed(42)
        self.ode = ContinuousNeuralODE(hidden_dim=8)

    def test_predict_returns_3tuple(self):
        state = [500.0, 0.01, 0.05]
        result = self.ode.predict_trajectory(state, 60.0)
        assert len(result) == 3

    def test_invalid_state_returns_zeros(self):
        result = self.ode.predict_trajectory([500.0, 0.01], 60.0)
        assert result == (0.0, 0.0, 0.0)

    def test_price_stays_near_input(self):
        state = [200.0, 0.0, 0.0]
        price_out, _, _ = self.ode.predict_trajectory(state, 10.0)
        # Shouldn't diverge wildly with friction
        assert abs(price_out - 200.0) < 50.0

    def test_short_dt_minimal_drift(self):
        state = [300.0, 0.0, 0.0]
        price_short, _, _ = self.ode.predict_trajectory(state, 1.0)
        price_long, _, _ = self.ode.predict_trajectory(state, 100.0)
        assert abs(price_short - 300.0) <= abs(price_long - 300.0) + 1e-3


# ── SparseAttentionEngine ─────────────────────────────────────────────────────
class TestSparseAttentionEngine:
    def setup_method(self):
        from sparse_attention import SparseAttentionEngine
        self.eng = SparseAttentionEngine(window_size=4, n_global_tokens=2)

    def _qkv(self, n=10, d=8):
        rng = np.random.default_rng(0)
        return rng.normal(0, 1, (n, d)), rng.normal(0, 1, (n, d)), rng.normal(0, 1, (n, d))

    def test_sliding_window_output_shape(self):
        Q, K, V = self._qkv()
        out = self.eng.sliding_window_attention(Q, K, V)
        assert out.shape == Q.shape

    def test_global_token_attention_shape(self):
        Q, K, V = self._qkv()
        out = self.eng.global_token_attention(Q, K, V, global_indices=[0, 3])
        assert out.shape == Q.shape

    def test_sliding_output_finite(self):
        Q, K, V = self._qkv()
        out = self.eng.sliding_window_attention(Q, K, V)
        assert np.all(np.isfinite(out))

    def test_global_tokens_capped_at_n_global(self):
        Q, K, V = self._qkv(n=10, d=4)
        # Provide more indices than n_global; should only process first 2
        out = self.eng.global_token_attention(Q, K, V, global_indices=list(range(8)))
        assert out.shape == Q.shape


# ── CrossAssetLeadIndicator ───────────────────────────────────────────────────
class TestCrossAssetLeadIndicator:
    def setup_method(self):
        from cross_asset import CrossAssetLeadIndicator
        self.ca = CrossAssetLeadIndicator()

    def test_risk_on_conditions(self):
        returns = {"TLT": -0.01, "GLD": -0.005, "DXY": -0.003, "SPY": 0.02}
        score = self.ca.compute_risk_appetite(returns)
        assert score > 0

    def test_risk_off_conditions(self):
        returns = {"TLT": 0.02, "GLD": 0.015, "DXY": 0.01, "SPY": -0.03}
        score = self.ca.compute_risk_appetite(returns)
        assert score < 0

    def test_score_bounded(self):
        returns = {"TLT": 1.0, "GLD": 1.0, "DXY": 1.0, "SPY": 1.0}
        score = self.ca.compute_risk_appetite(returns)
        assert -1.0 <= score <= 1.0

    def test_yield_curve_slope(self):
        slope = self.ca.yield_curve_slope(4.5, 5.0)
        assert slope == pytest.approx(-0.5)

    def test_inverted_curve_risk_off_signal(self):
        returns = {"TLT": 0.0, "GLD": 0.0, "DXY": 0.0, "SPY": 0.0}
        signal = self.ca.leading_signal(returns, y10=3.5, y2=4.5)  # inverted
        assert signal == "RISK_OFF"

    def test_normal_curve_positive_appetite(self):
        # Large magnitudes needed so tanh(score * 10) > 0.3
        returns = {"TLT": -0.05, "GLD": -0.04, "DXY": -0.03, "SPY": 0.06}
        signal = self.ca.leading_signal(returns, y10=4.5, y2=3.5)
        assert signal == "RISK_ON"


# ── QuantumInspiredOptimizer ──────────────────────────────────────────────────
class TestQuantumInspiredOptimizer:
    def test_minimises_quadratic(self):
        from quantum_tuning import QuantumInspiredOptimizer
        def objective(x): return float(x[0]**2 + x[1]**2)
        opt = QuantumInspiredOptimizer(objective, [(-5.0, 5.0), (-5.0, 5.0)], n_steps=500)
        best_params, best_score = opt.run()
        assert best_score < 5.0  # Should find something close to 0

    def test_output_within_bounds(self):
        from quantum_tuning import QuantumInspiredOptimizer
        bounds = [(-2.0, 2.0), (0.0, 3.0)]
        opt = QuantumInspiredOptimizer(lambda x: float(x[0]), bounds, n_steps=200)
        best_params, _ = opt.run()
        for val, (lo, hi) in zip(best_params, bounds):
            assert lo <= val <= hi

    def test_tunnel_prob_positive(self):
        from quantum_tuning import QuantumInspiredOptimizer
        opt = QuantumInspiredOptimizer(lambda x: 0.0, [(-1.0, 1.0)], n_steps=10)
        prob = opt._quantum_tunnel_prob(0.5, 0.5, 0.5)
        assert 0.0 < prob <= 1.0


# ── QuantumTuner ──────────────────────────────────────────────────────────────
class TestQuantumTuner:
    def setup_method(self):
        from tuner import QuantumTuner
        self.tuner = QuantumTuner(transverse_field_strength=1.0)

    def test_search_reduces_cost(self):
        def cost(params): return params[0]**2 + params[1]**2
        start = [3.0, 4.0]
        result = self.tuner.search_optima(start, cost, iterations=200)
        assert cost(result) <= cost(start)

    def test_returns_same_length(self):
        result = self.tuner.search_optima([1.0, 2.0, 3.0], lambda p: sum(p), iterations=50)
        assert len(result) == 3

    def test_single_param(self):
        result = self.tuner.search_optima([5.0], lambda p: p[0]**2, iterations=300)
        assert isinstance(result, list)
        assert len(result) == 1


# ── OnlineLiveTrainer ─────────────────────────────────────────────────────────
class TestOnlineLiveTrainer:
    def setup_method(self):
        from live_trainer import OnlineLiveTrainer
        self.trainer = OnlineLiveTrainer(learning_rate=0.01)

    def test_register_agent(self):
        self.trainer.register_agent("AgentA", 1.0)
        assert "AgentA" in self.trainer.get_weights()

    def test_positive_trade_increases_weight(self):
        self.trainer.register_agent("AgentA", 1.0)
        self.trainer.update_from_trade(0.05, {"AgentA": 1.0})
        assert self.trainer.agent_weights["AgentA"] > 1.0

    def test_negative_trade_decreases_weight(self):
        self.trainer.register_agent("AgentB", 1.0)
        self.trainer.update_from_trade(-0.05, {"AgentB": 1.0})
        assert self.trainer.agent_weights["AgentB"] < 1.0

    def test_weight_clamped_at_min(self):
        self.trainer.register_agent("AgentC", 0.11)
        for _ in range(100):
            self.trainer.update_from_trade(-0.10, {"AgentC": 1.0})
        assert self.trainer.agent_weights["AgentC"] >= 0.1

    def test_weight_clamped_at_max(self):
        self.trainer.register_agent("AgentD", 4.9)
        for _ in range(100):
            self.trainer.update_from_trade(0.10, {"AgentD": 1.0})
        assert self.trainer.agent_weights["AgentD"] <= 5.0

    def test_auto_registers_new_agent(self):
        self.trainer.update_from_trade(0.02, {"NewAgent": 0.8})
        assert "NewAgent" in self.trainer.agent_weights

    def test_empty_votes_no_error(self):
        self.trainer.update_from_trade(0.03, {})


# ── RLHFOnlineTrainer ─────────────────────────────────────────────────────────
class TestRLHFOnlineTrainer:
    def setup_method(self):
        self._tmpdir = tempfile.mkdtemp()
        from rlhf_trainer import RLHFOnlineTrainer
        self.rlhf = RLHFOnlineTrainer(feedback_path=f"{self._tmpdir}/rlhf.jsonl")

    def test_record_feedback_updates_scores(self):
        self.rlhf.record_feedback("d1", ["AgentA", "AgentB"], ["AgentC"], "WIN", 1.0)
        assert self.rlhf.get_agent_preference_weight("AgentA") > 1.0

    def test_negative_feedback_reduces_yes_agents(self):
        self.rlhf.record_feedback("d2", ["BadAgent"], [], "LOSS", -1.0)
        assert self.rlhf.get_agent_preference_weight("BadAgent") < 1.0

    def test_weight_clamped_min(self):
        for i in range(30):
            self.rlhf.record_feedback(f"d{i}", ["WeakAgent"], [], "LOSS", -1.0)
        assert self.rlhf.get_agent_preference_weight("WeakAgent") >= 0.1

    def test_weight_clamped_max(self):
        for i in range(30):
            self.rlhf.record_feedback(f"d{i}", ["StrongAgent"], [], "WIN", 1.0)
        assert self.rlhf.get_agent_preference_weight("StrongAgent") <= 3.0

    def test_unknown_agent_returns_one(self):
        assert self.rlhf.get_agent_preference_weight("unknown") == 1.0

    def test_top_agents_sorted(self):
        self.rlhf.record_feedback("x1", ["A"], [], "WIN", 1.0)
        self.rlhf.record_feedback("x2", ["B"], [], "WIN", 0.5)
        top = self.rlhf.top_agents(n=2)
        assert top[0][1] >= top[1][1]

    def test_feedback_written_to_disk(self):
        self.rlhf.record_feedback("disk_test", ["AgentX"], [], "WIN", 0.8)
        path = Path(self._tmpdir) / "rlhf.jsonl"
        assert path.exists()
        assert path.stat().st_size > 0
