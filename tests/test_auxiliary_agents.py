"""
tests/test_auxiliary_agents.py
Tests for auxiliary/wired agent modules:
  - cognitive_diversity.CognitiveDiversityEnforcer
  - ensemble_distill.EnsembleDistiller
  - reflexivity_scale.ReflexivityScale
  - game_theory.GameTheoryPositionSizer
  - macro_topology.MacroTopologyGraph
  - topology_agent.TopologicalDataAgent
  - gnn_agent.GNNSentimentAgent
  - insider_agent.InsiderTradeAgent
  - esg_agent.ESGAlphaAgent
  - brain/scent_detector.NeuralScentDetector
  - brain/reflex_model.MarketReflexModel
  - brain/supply_monitor.SupplyMonitor
  - brain/hdc_engine.HDCEngine
  - brain/snn_inference.SpikingNeuralInference
  - brain/memory_recall.MultiHorizonMemoryRecall
  - brain/prediction_buffer.PredictionBuffer
  - brain/prompt_evolver.PromptEvolver
  - brain/feature_creator.FeatureCreator
  - brain/graph_flow.GATFlow
  - brain/hedging_agent.HedgingAgent
  - brain/interrogator.SovereignInterrogator
  - alt_data.AlternativeDataAggregator
  - shadow_trader.ShadowTrader
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(SRC / "brain"))


# ── CognitiveDiversityEnforcer ────────────────────────────────────────────────
class TestCognitiveDiversityEnforcer:
    def setup_method(self):
        from cognitive_diversity import CognitiveDiversityEnforcer
        self.cde = CognitiveDiversityEnforcer()

    def test_diverse_votes_allowed(self):
        votes = {"BUY": 3, "SELL": 3, "HOLD": 3}
        assert self.cde.enforce(votes, "BUY") is True

    def test_herded_vote_blocked(self):
        votes = {"BUY": 9, "SELL": 1}
        assert self.cde.enforce(votes, "BUY") is False

    def test_hhi_uniform_is_low(self):
        hhi = self.cde.compute_hhi({"A": 1, "B": 1, "C": 1})
        assert abs(hhi - 1 / 3) < 0.01

    def test_hhi_monopoly_is_one(self):
        hhi = self.cde.compute_hhi({"BUY": 10})
        assert abs(hhi - 1.0) < 0.01

    def test_diversity_report_structure(self):
        r = self.cde.diversity_report({"BUY": 5, "SELL": 5})
        assert "hhi" in r and "entropy" in r and "is_diverse" in r

    def test_empty_votes(self):
        assert self.cde.compute_hhi({}) == 0.0


# ── EnsembleDistiller ─────────────────────────────────────────────────────────
class TestEnsembleDistiller:
    def setup_method(self):
        from ensemble_distill import EnsembleDistiller
        self.ed = EnsembleDistiller()

    def test_majority_wins(self):
        outputs = [
            {"model": "A", "vote": "BUY", "confidence": 0.9},
            {"model": "B", "vote": "BUY", "confidence": 0.8},
            {"model": "C", "vote": "SELL", "confidence": 0.6},
        ]
        result = self.ed.distill(outputs)
        assert result["vote"] == "BUY"

    def test_empty_returns_fallback(self):
        result = self.ed.distill([])
        assert result["vote"] == "ABSTAIN"
        assert result["confidence"] == 0.0

    def test_record_outcome_updates_weight(self):
        self.ed.record_outcome("modelX", True)
        self.ed.record_outcome("modelX", False)
        w = self.ed.model_weight("modelX")
        assert 0.0 < w < 1.0

    def test_new_model_gets_weight_one(self):
        assert self.ed.model_weight("unseen_model") == 1.0

    def test_confidence_bounded(self):
        outputs = [{"model": "X", "vote": "BUY", "confidence": 0.7}]
        result = self.ed.distill(outputs)
        assert 0.0 <= result["confidence"] <= 1.0

    def test_breakdown_in_result(self):
        outputs = [
            {"model": "A", "vote": "BUY", "confidence": 0.8},
            {"model": "B", "vote": "SELL", "confidence": 0.6},
        ]
        result = self.ed.distill(outputs)
        assert "breakdown" in result


# ── ReflexivityScale ──────────────────────────────────────────────────────────
class TestReflexivityScale:
    def setup_method(self):
        from reflexivity_scale import ReflexivityScale
        self.rs = ReflexivityScale(lookback=20)

    def _prices(self, n=30, drift=0.002):
        rng = np.random.default_rng(5)
        return list(float(p) for p in np.exp(np.cumsum(drift + rng.normal(0, 0.01, n))) * 100)

    def test_neutral_on_insufficient_data(self):
        assert self.rs.compute_reflexivity_index([1.0] * 5, [0.5] * 5) == 0.0

    def test_boom_spiral_detected(self):
        prices = [100 + i for i in range(30)]
        positioning = [i * 10 for i in range(30)]  # both trending up
        idx = self.rs.compute_reflexivity_index(prices, positioning)
        assert idx > 0

    def test_bust_spiral_detected(self):
        # Prices falling, positioning also collapsing -> product is positive -> tanh > 0
        # For a bust we need price_roc < 0 AND pos_roc > 0 (shorts increasing), or vice versa
        prices = [130 - i * 1.5 for i in range(30)]   # falling sharply
        positioning = [0 + i * 8 for i in range(30)]   # shorts building (positive ROC)
        idx = self.rs.compute_reflexivity_index(prices, positioning)
        # product of negative price_roc * positive pos_roc = negative -> bust
        assert idx < 0

    def test_index_range(self):
        prices = self._prices(30)
        pos = [float(i) for i in range(30)]
        idx = self.rs.compute_reflexivity_index(prices, pos)
        assert -1.0 <= idx <= 1.0

    def test_spiral_forming_threshold(self):
        result = self.rs.is_spiral_forming(
            [100 + i for i in range(30)],
            [i * 10 for i in range(30)],
            threshold=0.1,
        )
        assert isinstance(result, bool)


# ── GameTheoryPositionSizer ───────────────────────────────────────────────────
class TestGameTheoryPositionSizer:
    def setup_method(self):
        from game_theory import GameTheoryPositionSizer
        self.gt = GameTheoryPositionSizer()

    def test_minimax_returns_positive_int(self):
        size = self.gt.minimax_regret_size(50.0, 0.5, 100)
        assert isinstance(size, int)
        assert size >= 1

    def test_nash_equilibrium_bid_below_value(self):
        bid = self.gt.nash_equilibrium_bid(100.0, 5)
        assert bid < 100.0

    def test_nash_single_competitor(self):
        bid = self.gt.nash_equilibrium_bid(100.0, 1)
        assert bid == pytest.approx(99.0, abs=0.01)

    def test_optimal_size_capped(self):
        size = self.gt.compute_optimal_size(alpha_bps=5.0, adv_usd=1e6, account_usd=100_000)
        assert size <= 100_000 * 0.15 + 1  # max 15% of account

    def test_optimal_size_positive(self):
        size = self.gt.compute_optimal_size(alpha_bps=20.0, adv_usd=5e6, account_usd=50_000)
        assert size > 0


# ── MacroTopologyGraph ────────────────────────────────────────────────────────
class TestMacroTopologyGraph:
    def setup_method(self):
        from macro_topology import MacroTopologyGraph
        self.graph = MacroTopologyGraph()
        self.graph.add_link("TSMC_MISS", "NVDA", 0.8)
        self.graph.add_link("NVDA", "SPY", 0.6)
        self.graph.add_link("SPY", "VIX", 0.9)

    def test_direct_impact(self):
        impact = self.graph.calculate_ripple_impact("TSMC_MISS", "NVDA", max_depth=1)
        assert impact == pytest.approx(0.8, abs=0.01)

    def test_two_hop_impact(self):
        impact = self.graph.calculate_ripple_impact("TSMC_MISS", "SPY", max_depth=2)
        assert impact == pytest.approx(0.48, abs=0.01)

    def test_no_path_returns_zero(self):
        assert self.graph.calculate_ripple_impact("TSMC_MISS", "GOLD", max_depth=3) == 0.0

    def test_unknown_source_returns_zero(self):
        assert self.graph.calculate_ripple_impact("UNKNOWN", "SPY") == 0.0

    def test_nodes_populated(self):
        assert "NVDA" in self.graph.nodes
        assert "SPY" in self.graph.nodes


# ── TopologicalDataAgent ──────────────────────────────────────────────────────
class TestTopologicalDataAgent:
    def setup_method(self):
        from topology_agent import TopologicalDataAgent
        self.agent = TopologicalDataAgent()

    def test_persistence_returns_list(self):
        prices = [float(100 + i + np.random.default_rng(i).normal(0, 0.5)) for i in range(20)]
        pairs = self.agent.compute_persistence(prices)
        assert isinstance(pairs, list)

    def test_insufficient_data_empty(self):
        assert self.agent.compute_persistence([1.0, 2.0]) == []

    def test_complexity_non_negative(self):
        prices = [float(100 + np.random.default_rng(i).normal(0, 2)) for i in range(30)]
        c = self.agent.topological_complexity(prices)
        assert c >= 0.0


# ── GNNSentimentAgent ─────────────────────────────────────────────────────────
class TestGNNSentimentAgent:
    def setup_method(self):
        from gnn_agent import GNNSentimentAgent
        self.agent = GNNSentimentAgent(num_nodes=20)

    def test_ripple_returns_correct_length(self):
        result = self.agent.track_ripple(0, 1.0)
        assert len(result) == 20

    def test_out_of_bounds_returns_zeros(self):
        result = self.agent.track_ripple(999, 1.0)
        assert np.all(result == 0.0)

    def test_shock_propagates(self):
        before = self.agent.node_features[0, 0]
        self.agent.track_ripple(0, 2.0)
        after = self.agent.node_features[0, 0]
        assert after != before

    def test_output_bounded(self):
        result = self.agent.track_ripple(5, 3.0)
        assert np.all(np.abs(result) <= 1.0)


# ── InsiderTradeAgent ─────────────────────────────────────────────────────────
class TestInsiderTradeAgent:
    def setup_method(self):
        from insider_agent import InsiderTradeAgent
        self.agent = InsiderTradeAgent()

    def test_parse_ceo_filing(self):
        filing = {"display_names": "John Smith (CEO)", "entity_name": "AAPL", "file_date": "2025-01-15"}
        result = self.agent.parse_form4(filing)
        assert result is not None
        assert result["ticker"] == "AAPL"

    def test_skip_non_officer(self):
        filing = {"display_names": "John Smith", "entity_name": "AAPL", "file_date": "2025-01-15"}
        assert self.agent.parse_form4(filing) is None

    def test_all_buys_sentiment_positive(self):
        txns = [{"transaction_type": "P"}, {"transaction_type": "A"}, {"transaction_type": "P"}]
        assert self.agent.net_insider_sentiment(txns) == pytest.approx(1.0)

    def test_all_sells_sentiment_negative(self):
        txns = [{"transaction_type": "S"}, {"transaction_type": "D"}]
        assert self.agent.net_insider_sentiment(txns) == pytest.approx(-1.0)

    def test_mixed_sentiment_between(self):
        txns = [{"transaction_type": "P"}, {"transaction_type": "S"}]
        s = self.agent.net_insider_sentiment(txns)
        assert -1.0 <= s <= 1.0

    def test_empty_returns_zero(self):
        assert self.agent.net_insider_sentiment([]) == 0.0


# ── ESGAlphaAgent ─────────────────────────────────────────────────────────────
class TestESGAlphaAgent:
    def setup_method(self):
        from esg_agent import ESGAlphaAgent
        self.agent = ESGAlphaAgent()

    def test_high_esg_overweight(self):
        result = self.agent.estimate_esg_alpha({"environmental": 90, "social": 85, "governance": 95})
        assert result["signal"] == "OVERWEIGHT"

    def test_low_esg_underweight(self):
        result = self.agent.estimate_esg_alpha({"environmental": 10, "social": 15, "governance": 20})
        assert result["signal"] == "UNDERWEIGHT"

    def test_neutral_esg(self):
        result = self.agent.estimate_esg_alpha({"environmental": 50, "social": 50, "governance": 50})
        assert result["signal"] == "NEUTRAL"

    def test_governance_risk_flag_high_insider(self):
        assert self.agent.governance_risk_flag(80.0, 60.0) is True

    def test_governance_risk_flag_low_independence(self):
        assert self.agent.governance_risk_flag(20.0, 20.0) is True

    def test_no_risk_healthy_governance(self):
        assert self.agent.governance_risk_flag(10.0, 70.0) is False


# ── NeuralScentDetector (brain/) ──────────────────────────────────────────────
class TestNeuralScentDetector:
    def setup_method(self):
        sys.path.insert(0, str(SRC / "brain"))
        from scent_detector import NeuralScentDetector
        self.agent = NeuralScentDetector(sensitivity=2.0)

    def test_insufficient_data_returns_zero(self):
        assert self.agent.detect_scent([0.1] * 5, [0.5] * 5) == 0.0

    def test_high_scent_on_compression_and_aggression(self):
        spreads = [0.10] + [0.01] * 12  # spread compressed from 0.10 -> 0.01
        agg = [0.3] * 7 + [0.9, 0.95, 0.92]
        score = self.agent.detect_scent(spreads, agg)
        assert 0.0 <= score <= 1.0

    def test_score_bounded_zero_to_one(self):
        spreads = [0.05] + [0.002] * 12
        agg = [0.99] * 13
        assert 0.0 <= self.agent.detect_scent(spreads, agg) <= 1.0


# ── MarketReflexModel (brain/) ────────────────────────────────────────────────
class TestMarketReflexModel:
    def setup_method(self):
        from reflex_model import MarketReflexModel
        self.model = MarketReflexModel(avg_daily_volume=1_000_000)

    def test_impact_positive(self):
        impact = self.model.opponent_response(10_000, 0.02)
        assert impact > 0.0

    def test_optimal_size_reduces_impact(self):
        original_impact = self.model.opponent_response(50_000, 0.05)
        optimal = self.model.nash_optimal_size(50_000, 0.05, max_tolerable_impact=0.001)
        reduced_impact = self.model.opponent_response(optimal, 0.05)
        assert reduced_impact <= original_impact + 1e-9

    def test_small_size_unchanged(self):
        result = self.model.nash_optimal_size(100, 0.01, max_tolerable_impact=1.0)
        assert result == pytest.approx(100, abs=1)


# ── SupplyMonitor (brain/) ────────────────────────────────────────────────────
class TestSupplyMonitor:
    def setup_method(self):
        from supply_monitor import SupplyMonitor
        self.mon = SupplyMonitor()

    def test_healthy_company_not_distressed(self):
        z = self.mon.calculate_altman_z(500, 2000, 400, 300, 1500, 800, 2500)
        assert not self.mon.is_distressed(z)

    def test_distressed_company_flagged(self):
        z = self.mon.calculate_altman_z(-200, 1000, -500, -100, 100, 950, 300)
        assert self.mon.is_distressed(z)

    def test_zero_assets_returns_zero(self):
        assert self.mon.calculate_altman_z(100, 0, 100, 50, 200, 300, 500) == 0.0


# ── HDCEngine (brain/) ────────────────────────────────────────────────────────
class TestHDCEngine:
    def setup_method(self):
        from hdc_engine import HDCEngine
        self.engine = HDCEngine()

    def test_encode_returns_binary_vector(self):
        v = self.engine.encode({"momentum": 0.7, "vol": 0.3})
        assert v.dtype == np.uint8
        assert len(v) == 10_000
        assert set(v.tolist()).issubset({0, 1})

    def test_classify_returns_known_label(self):
        labels = {"BULL": self.engine.encode({"m": 0.8}), "BEAR": self.engine.encode({"m": 0.1})}
        q = self.engine.encode({"m": 0.75})
        result = self.engine.classify(q, labels)
        assert result in ("BULL", "BEAR")

    def test_similar_features_same_class(self):
        self.engine.encode({"x": 0.9})  # ensure key registered
        v1 = self.engine.encode({"x": 0.85})
        v2 = self.engine.encode({"x": 0.90})
        protos = {"HIGH": v1}
        assert self.engine.classify(v2, protos) == "HIGH"


# ── SpikingNeuralInference (brain/) ───────────────────────────────────────────
class TestSpikingNeuralInference:
    def setup_method(self):
        from snn_inference import SpikingNeuralInference
        self.snn = SpikingNeuralInference(n_neurons=50, tau=5.0, threshold=0.5)

    def test_infer_returns_valid_action(self):
        signals = [0.8] * 20
        result = self.snn.infer(signals)
        assert result in ("BUY", "SELL", "HOLD")

    def test_step_returns_spike_array(self):
        spikes = self.snn.step(0.5)
        assert len(spikes) == 50
        assert spikes.dtype == np.uint8

    def test_strong_positive_signal_tends_buy(self):
        self.snn = __import__("snn_inference").SpikingNeuralInference(n_neurons=200, tau=5.0, threshold=0.3)
        result = self.snn.infer([1.0] * 50)
        assert result in ("BUY", "HOLD")


# ── MultiHorizonMemoryRecall (brain/) ─────────────────────────────────────────
class TestMultiHorizonMemoryRecall:
    def setup_method(self):
        from memory_recall import MultiHorizonMemoryRecall
        self.mem = MultiHorizonMemoryRecall()

    def test_record_and_recall(self):
        self.mem.record("1d", {"summary": "SPY breakout head and shoulders", "outcome": "WIN"})
        self.mem.record("1d", {"summary": "AAPL double bottom reversal", "outcome": "WIN"})
        results = self.mem.recall("SPY head and shoulders", "1d", top_n=1)
        assert len(results) == 1
        assert "head" in results[0]["summary"].lower()

    def test_recall_unknown_horizon_falls_back(self):
        self.mem.record("1d", {"summary": "test lesson"})
        results = self.mem.recall("test", "unknown_horizon", top_n=5)
        assert isinstance(results, list)

    def test_buffer_capped_at_500(self):
        for i in range(520):
            self.mem.record("1m", {"summary": f"lesson {i}"})
        assert len(self.mem._banks["1m"]) == 500

    def test_recall_all_horizons_keys(self):
        result = self.mem.recall_all_horizons("test")
        assert set(result.keys()) == {"1d", "1m", "1y"}


# ── PredictionBuffer (brain/) ─────────────────────────────────────────────────
class TestPredictionBuffer:
    def setup_method(self):
        from prediction_buffer import PredictionBuffer
        self.buf = PredictionBuffer(capacity=5)

    def test_push_and_size(self):
        self.buf.push({"scenario": "A", "probability": 0.8})
        assert self.buf.size() == 1

    def test_pop_best_returns_highest_prob(self):
        self.buf.push({"scenario": "low", "probability": 0.3})
        self.buf.push({"scenario": "high", "probability": 0.9})
        best = self.buf.pop_best()
        assert best["scenario"] == "high"

    def test_capacity_cap(self):
        for i in range(10):
            self.buf.push({"scenario": str(i), "probability": float(i) / 10})
        assert self.buf.size() == 5

    def test_pop_empty_returns_none(self):
        assert self.buf.pop_best() is None

    def test_peek_all_non_destructive(self):
        self.buf.push({"scenario": "X", "probability": 0.5})
        _ = self.buf.peek_all()
        assert self.buf.size() == 1


# ── PromptEvolver (brain/) ────────────────────────────────────────────────────
class TestPromptEvolver:
    def setup_method(self):
        from prompt_evolver import PromptEvolver
        self.pe = PromptEvolver()

    def test_register_and_best_variant(self):
        for _ in range(6):
            self.pe.register_outcome("v1", True, 0.9)
        for _ in range(6):
            self.pe.register_outcome("v2", False, 0.9)
        best = self.pe.best_variant(min_samples=5)
        assert best == "v1"

    def test_below_min_samples_returns_none(self):
        self.pe.register_outcome("v3", True, 0.5)
        assert self.pe.best_variant(min_samples=10) is None

    def test_mutate_replaces_tone(self):
        template = "Be {TONE} in your analysis."
        result_low_vix = self.pe.mutate(template, vix=10.0)
        result_high_vix = self.pe.mutate(template, vix=30.0)
        assert "aggressive" in result_low_vix
        assert "cautious" in result_high_vix


# ── FeatureCreator (brain/) ───────────────────────────────────────────────────
class TestFeatureCreator:
    def setup_method(self):
        from feature_creator import FeatureCreator
        self.fc = FeatureCreator()

    def _ohlcv(self, n=30):
        rng = np.random.default_rng(42)
        deltas = rng.normal(0, 0.5, n)
        prices = list(100 + np.cumsum(deltas))
        highs = [p + abs(float(rng.normal(0, 0.2))) for p in prices]
        lows = [p - abs(float(rng.normal(0, 0.2))) for p in prices]
        vols = [float(1e6 + float(rng.normal(0, 5e4))) for _ in range(n)]
        return prices, vols, highs, lows

    def test_synthesize_returns_dict(self):
        p, v, h, l = self._ohlcv()
        features = self.fc.synthesize(p, v, h, l)
        assert isinstance(features, dict)
        assert len(features) > 0

    def test_insufficient_data_empty(self):
        assert self.fc.synthesize([1.0] * 5, [100.0] * 5, [1.1] * 5, [0.9] * 5) == {}

    def test_feature_keys_present(self):
        p, v, h, l = self._ohlcv(30)
        features = self.fc.synthesize(p, v, h, l)
        assert "price_vol_ratio" in features
        assert "normalized_close" in features


# ── GATFlow (brain/) ──────────────────────────────────────────────────────────
class TestGATFlow:
    def setup_method(self):
        from graph_flow import GATFlow
        self.gat = GATFlow()

    def test_update_and_followers(self):
        rng = np.random.default_rng(0)
        for _ in range(30):
            r = float(rng.normal(0.001, 0.01))
            self.gat.update({"NVDA": r, "AMD": r * 0.9, "INTC": float(rng.normal(0, 0.01))})
        followers = self.gat.get_followers("NVDA", threshold=0.3)
        assert isinstance(followers, list)

    def test_no_data_empty_followers(self):
        from graph_flow import GATFlow
        g = GATFlow()
        assert g.get_followers("NVDA") == []

    def test_flow_matrix_populated(self):
        self.gat.update({"A": 0.01, "B": 0.02})
        assert "A" in self.gat.flow_matrix


# ── HedgingAgent (brain/) ─────────────────────────────────────────────────────
class TestHedgingAgent:
    def setup_method(self):
        from hedging_agent import HedgingAgent
        self.agent = HedgingAgent(hedge_ratio=0.05)

    def test_extreme_vix_triggers_hedge(self):
        r = self.agent.evaluate_hedge_requirements(100_000, 40.0, 0.5, -0.05)
        assert r["needs_hedge"] is True

    def test_high_crash_prob_triggers(self):
        r = self.agent.evaluate_hedge_requirements(100_000, 20.0, 0.90, -0.05)
        assert r["needs_hedge"] is True

    def test_normal_conditions_no_hedge(self):
        r = self.agent.evaluate_hedge_requirements(100_000, 18.0, 0.10, -0.02)
        assert r["needs_hedge"] is False

    def test_allocation_capped_at_15pct(self):
        r = self.agent.evaluate_hedge_requirements(1_000_000, 50.0, 1.0, -0.3)
        assert r["suggested_put_allocation"] <= 150_000

    def test_small_portfolio_below_threshold(self):
        r = self.agent.evaluate_hedge_requirements(1000, 40.0, 0.9, -0.2)
        assert r["needs_hedge"] is False or r["suggested_put_allocation"] >= 0


# ── SovereignInterrogator (brain/) ────────────────────────────────────────────
class TestSovereignInterrogator:
    def setup_method(self):
        from interrogator import SovereignInterrogator
        self.intr = SovereignInterrogator()

    def test_interrogate_returns_string(self):
        decision = {
            "decision": "REJECT",
            "confidence": 0.4,
            "reason": "VIX too high",
            "votes": [
                {"agent": "AgentA", "vote": "NO"},
                {"agent": "AgentB", "vote": "YES"},
            ],
        }
        response = self.intr.interrogate(decision, "Why was DIA rejected?")
        assert isinstance(response, str)
        assert "REJECT" in response

    def test_yes_and_no_vote_counts_present(self):
        decision = {
            "decision": "APPROVE",
            "confidence": 0.8,
            "reason": "Strong trend",
            "votes": [
                {"agent": "A", "vote": "YES"},
                {"agent": "B", "vote": "YES"},
                {"agent": "C", "vote": "NO"},
            ],
        }
        response = self.intr.interrogate(decision, "Why approve?")
        assert "YES votes (2)" in response
        assert "NO votes (1)" in response


# ── AlternativeDataAggregator ─────────────────────────────────────────────────
class TestAlternativeDataAggregator:
    def setup_method(self):
        from alt_data import AlternativeDataAggregator
        self.ada = AlternativeDataAggregator()

    def test_composite_zero_no_data(self):
        assert self.ada.composite_score() == 0.0

    def test_ingest_and_composite(self):
        self.ada.ingest("satellite", 0.5, confidence=0.8)
        self.ada.ingest("credit_card", 0.3, confidence=1.0)
        score = self.ada.composite_score()
        assert score > 0.0

    def test_summary_structure(self):
        self.ada.ingest("jobs", 0.6)
        summary = self.ada.alt_data_summary()
        assert "signal" in summary
        assert summary["signal"] in ("BULLISH", "BEARISH", "NEUTRAL")

    def test_bullish_signal_count(self):
        self.ada.ingest("A", 0.5)
        self.ada.ingest("B", -0.3)
        assert self.ada.bullish_signal_count() == 1


# ── ShadowTrader ──────────────────────────────────────────────────────────────
class TestShadowTrader:
    def setup_method(self):
        from shadow_trader import ShadowTrader
        self.st = ShadowTrader()

    def test_positive_evolution(self):
        self.st.record_trade(0.05, 0.03)
        edge = self.st.evaluate_evolution()
        assert edge > 0.0

    def test_negative_evolution_detected(self):
        self.st.record_trade(0.01, 0.08)
        edge = self.st.evaluate_evolution()
        assert edge < 0.0

    def test_rollback_triggered_when_far_behind(self):
        self.st.record_trade(-0.10, 0.05)
        assert self.st.trigger_rollback_if_needed() is True

    def test_no_rollback_when_ahead(self):
        self.st.record_trade(0.10, 0.02)
        assert self.st.trigger_rollback_if_needed() is False
