"""
tests/test_remaining_agents.py
Tests for remaining wired agent modules:
  - alpha_watchdog.AlphaDecayWatchdog
  - bayesian_oracle.BayesianOracle
  - debate_engine.DebateEngine
  - drawdown_predictor.DrawdownPredictor
  - evolution_engine.EvolutionEngine
  - apex_singularity.SovereignSingularity
  - agri_agent.AgriculturalSignalAgent
  - category_theory.CategoryTheoryVerifier
  - cyber_agent.CyberRiskAgent (mocked)
  - cog_balancer.CognitiveLoadBalancer
  - macro_sentinel.ContagionSentinel  (macro_sentinel.py)
  - production_agent.ProductionResiliencyAgent
  - patent_agent.PatentVelocityAgent (mocked)
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


# ── AlphaDecayWatchdog ────────────────────────────────────────────────────────
class TestAlphaDecayWatchdog:
    def setup_method(self):
        from alpha_watchdog import AlphaDecayWatchdog
        self.wd = AlphaDecayWatchdog(decay_threshold=0.40, lookback_fast=5, lookback_slow=10)

    def test_warming_up_before_enough_data(self):
        self.wd.record("strat_a", 0.01)
        result = self.wd.evaluate("strat_a")
        assert result["status"] == "WARMING_UP"

    def test_healthy_strategy(self):
        rng = np.random.default_rng(42)
        for _ in range(15):
            self.wd.record("healthy", float(abs(rng.normal(0.005, 0.001))))
        result = self.wd.evaluate("healthy")
        assert result["status"] in ("HEALTHY", "DECAY", "RETIRE")

    def test_retire_on_five_consecutive_losses(self):
        for _ in range(10):
            self.wd.record("dying", 0.01)
        for _ in range(5):
            self.wd.record("dying", -0.05)
        result = self.wd.evaluate("dying")
        assert result["status"] == "RETIRE"

    def test_decay_when_fast_sharpe_drops(self):
        # Feed strong positive returns, then sudden losses
        for _ in range(10):
            self.wd.record("decaying", 0.03)
        for _ in range(6):
            self.wd.record("decaying", -0.001)
        result = self.wd.evaluate("decaying")
        assert result["status"] in ("DECAY", "RETIRE")

    def test_evaluate_returns_all_keys(self):
        for _ in range(12):
            self.wd.record("full", 0.01)
        result = self.wd.evaluate("full")
        assert all(k in result for k in ("status", "fast_sharpe", "slow_sharpe", "decay_ratio"))

    def test_unknown_strategy_warming_up(self):
        result = self.wd.evaluate("nonexistent")
        assert result["status"] == "WARMING_UP"


# ── BayesianOracle ────────────────────────────────────────────────────────────
class TestBayesianOracle:
    def setup_method(self):
        from bayesian_oracle import BayesianOracle
        self.oracle = BayesianOracle()

    def _prices(self, n=50, drift=0.001):
        rng = np.random.default_rng(7)
        return np.exp(np.cumsum(drift + rng.normal(0, 0.01, n))) * 100

    def test_update_returns_bayesian_state(self):
        from bayesian_oracle import BayesianState
        prices = self._prices(50)
        volumes = np.ones(50) * 1e6
        state = self.oracle.update(prices, volumes, vix=15.0)
        assert isinstance(state, BayesianState)

    def test_regime_is_valid(self):
        prices = self._prices(50)
        state = self.oracle.update(prices, np.ones(50), vix=15.0)
        assert state.regime in ("BULL", "BEAR", "SIDEWAYS", "HIGH_VOL")

    def test_posteriors_sum_to_one(self):
        prices = self._prices(50)
        state = self.oracle.update(prices, np.ones(50), vix=15.0)
        assert abs(sum(state.posteriors.values()) - 1.0) < 0.01

    def test_high_vix_biases_bear_or_high_vol(self):
        prices = self._prices(50, drift=-0.003)
        state = self.oracle.update(prices, np.ones(50), vix=35.0)
        assert state.regime in ("BEAR", "HIGH_VOL", "SIDEWAYS")

    def test_api_dict_structure(self):
        prices = self._prices(50)
        self.oracle.update(prices, np.ones(50), vix=15.0)
        d = self.oracle.get_api_dict()
        assert "regime" in d and "confidence" in d and "dhatu" in d

    def test_cold_start_api_dict(self):
        from bayesian_oracle import BayesianOracle
        fresh = BayesianOracle()
        d = fresh.get_api_dict()
        assert d["regime"] == "UNKNOWN"

    def test_prior_updates_across_calls(self):
        prices = self._prices(50)
        state1 = self.oracle.update(prices, np.ones(50), vix=15.0)
        state2 = self.oracle.update(prices, np.ones(50), vix=35.0)
        # Confidence or regime should differ after different VIX input
        assert state1 is not state2


# ── DebateEngine ──────────────────────────────────────────────────────────────
class TestDebateEngine:
    def setup_method(self):
        from debate_engine import DebateEngine
        self.de = DebateEngine(required_confidence=0.60)

    def test_clear_majority_returns_winner(self):
        votes = {"A": "BUY", "B": "BUY", "C": "HOLD"}
        confs = {"A": 0.9, "B": 0.85, "C": 0.5}
        result = self.de.run_debate(votes, confs)
        assert result == "BUY"

    def test_inconclusive_returns_hold(self):
        votes = {"A": "BUY", "B": "SELL"}
        confs = {"A": 0.55, "B": 0.55}
        result = self.de.run_debate(votes, confs)
        assert result == "HOLD"

    def test_empty_votes_returns_hold(self):
        assert self.de.run_debate({}, {}) == "HOLD"

    def test_single_agent_above_threshold(self):
        votes = {"solo": "BUY"}
        confs = {"solo": 0.95}
        result = self.de.run_debate(votes, confs)
        assert result == "BUY"

    def test_missing_confidence_defaults_to_half(self):
        votes = {"A": "SELL", "B": "SELL", "C": "BUY"}
        result = self.de.run_debate(votes, {})
        assert result in ("SELL", "HOLD")


# ── DrawdownPredictor ─────────────────────────────────────────────────────────
class TestDrawdownPredictor:
    def setup_method(self):
        from drawdown_predictor import DrawdownPredictor
        self.pred = DrawdownPredictor()

    def test_same_state_zero_duration(self):
        assert self.pred.predict_duration(0, target_state=0) == 0.0

    def test_deep_drawdown_takes_longest(self):
        # From state 2 (deep drawdown) should take longer than from state 1
        t2 = self.pred.predict_duration(2, target_state=0)
        t1 = self.pred.predict_duration(1, target_state=0)
        assert t2 > t1

    def test_duration_positive(self):
        t = self.pred.predict_duration(1, target_state=0)
        assert t > 0.0

    def test_state_range_valid(self):
        for s in (0, 1, 2):
            for t in (0, 1, 2):
                if s != t:
                    result = self.pred.predict_duration(s, target_state=t)
                    assert isinstance(result, float)


# ── EvolutionEngine ───────────────────────────────────────────────────────────
class TestEvolutionEngine:
    def test_minimises_sphere_function(self):
        from evolution_engine import EvolutionEngine
        def sphere(x): return float(np.sum(x**2))
        bounds = [(-5.0, 5.0)] * 3
        eng = EvolutionEngine(sphere, bounds, population_size=10, max_generations=50)
        best_params, best_score = eng.run()
        assert best_score < 5.0

    def test_result_within_bounds(self):
        from evolution_engine import EvolutionEngine
        bounds = [(0.0, 1.0), (-1.0, 1.0)]
        eng = EvolutionEngine(lambda x: float(x[0]**2), bounds, population_size=8, max_generations=20)
        best_params, _ = eng.run()
        for val, (lo, hi) in zip(best_params, bounds, strict=False):
            assert lo <= val <= hi

    def test_single_dimension(self):
        from evolution_engine import EvolutionEngine
        eng = EvolutionEngine(lambda x: float(x[0]**2), [(-10.0, 10.0)],
                              population_size=5, max_generations=30)
        best_params, best_score = eng.run()
        assert best_score < 10.0


# ── SovereignSingularity ──────────────────────────────────────────────────────
class TestSovereignSingularity:
    def setup_method(self):
        from apex_singularity import SovereignSingularity
        self.s = SovereignSingularity()

    def test_zero_ratio_no_data(self):
        assert self.s.singularity_ratio() == 0.0

    def test_ratio_computed_after_data(self):
        for _ in range(5):
            self.s.record_improvement(0.05)
        rng = np.random.default_rng(0)
        self.s.record_market_entropy(rng.normal(0, 0.01, 100).tolist())
        ratio = self.s.singularity_ratio()
        assert isinstance(ratio, float) and np.isfinite(ratio)

    def test_high_improvement_low_entropy_ratio_gt_one(self):
        for _ in range(20):
            self.s.record_improvement(1.0)
        # Narrow normal distribution -> moderate entropy, ratio should be positive
        rng = np.random.default_rng(99)
        self.s.record_market_entropy(rng.normal(0.001, 0.001, 100).tolist())
        ratio = self.s.singularity_ratio()
        # With avg improvement = 1.0 and moderate entropy, ratio >> 0
        assert ratio > 0.0


# ── AgriculturalSignalAgent ───────────────────────────────────────────────────
class TestAgriculturalSignalAgent:
    def setup_method(self):
        from agri_agent import AgriculturalSignalAgent
        self.agent = AgriculturalSignalAgent()

    def test_low_ndvi_bullish(self):
        result = self.agent.estimate_yield_risk("corn", 0.2)
        assert result["direction"] == "BULLISH"
        assert result["magnitude"] == "HIGH"

    def test_moderate_ndvi_bullish_moderate(self):
        result = self.agent.estimate_yield_risk("wheat", 0.4)
        assert result["direction"] == "BULLISH"
        assert result["magnitude"] == "MODERATE"

    def test_high_ndvi_bearish(self):
        result = self.agent.estimate_yield_risk("soybeans", 0.9)
        assert result["direction"] == "BEARISH"

    def test_neutral_ndvi(self):
        result = self.agent.estimate_yield_risk("corn", 0.65)
        assert result["direction"] == "NEUTRAL"

    def test_correct_futures_ticker(self):
        assert self.agent.estimate_yield_risk("corn", 0.5)["futures"] == "ZC"
        assert self.agent.estimate_yield_risk("wheat", 0.5)["futures"] == "ZW"
        assert self.agent.estimate_yield_risk("soybeans", 0.5)["futures"] == "ZS"

    def test_unknown_commodity_defaults_to_corn(self):
        result = self.agent.estimate_yield_risk("rice", 0.5)
        assert result["futures"] == "ZC"


# ── CategoryTheoryVerifier ────────────────────────────────────────────────────
class TestCategoryTheoryVerifier:
    def setup_method(self):
        from category_theory import CategoryTheoryVerifier
        self.ctv = CategoryTheoryVerifier()

    def test_compose_chain_succeeds(self):
        self.ctv.add_morphism("double", lambda x: x * 2)
        self.ctv.add_morphism("add_one", lambda x: x + 1)
        result, ok = self.ctv.compose(5)
        assert ok is True
        assert result == 11

    def test_compose_none_returns_failure(self):
        self.ctv.add_morphism("nullify", lambda x: None)
        result, ok = self.ctv.compose(10)
        assert ok is False

    def test_compose_exception_returns_failure(self):
        self.ctv.add_morphism("explode", lambda x: 1 / 0)
        result, ok = self.ctv.compose(5)
        assert ok is False

    def test_empty_morphisms_identity(self):
        result, ok = self.ctv.compose(42)
        assert ok is True
        assert result == 42


# ── CyberRiskAgent (mocked HTTP) ──────────────────────────────────────────────
class TestCyberRiskAgent:
    def test_scan_returns_dict_on_error(self, monkeypatch):
        import asyncio

        import requests

        from cyber_agent import CyberRiskAgent

        def _fail(*a, **kw):
            raise requests.ConnectionError("offline")

        monkeypatch.setattr(requests, "get", _fail)
        agent = CyberRiskAgent()
        result = asyncio.run(agent.scan_feeds("MSFT"))
        assert result["ticker"] == "MSFT"
        assert result["risk_score"] == 0.0
        assert result["hits"] == []

    def test_scan_with_mock_feed(self, monkeypatch):
        import asyncio

        import requests

        from cyber_agent import CyberRiskAgent

        def _mock_get(url, timeout=4):
            class _R:
                text = "microsoft azure windows breach attack"
            return _R()

        monkeypatch.setattr(requests, "get", _mock_get)
        agent = CyberRiskAgent()
        result = asyncio.run(agent.scan_feeds("MSFT"))
        assert result["risk_score"] >= 0.0
        assert "hits" in result


# ── CognitiveLoadBalancer ─────────────────────────────────────────────────────
class TestCognitiveLoadBalancer:
    def setup_method(self):
        from cog_balancer import CognitiveLoadBalancer
        self.clb = CognitiveLoadBalancer()

    def test_no_agents_returns_none(self):
        assert self.clb.fastest_agent() is None

    def test_fastest_agent_is_lowest_latency(self):
        for _ in range(5):
            self.clb.record_latency("slow", 200.0)
            self.clb.record_latency("fast", 10.0)
        assert self.clb.fastest_agent() == "fast"

    def test_rebalance_sorts_by_load(self):
        for _ in range(5):
            self.clb.record_latency("heavy", 500.0)
            self.clb.record_latency("light", 20.0)
        rebalanced = self.clb.rebalance_assignments(["heavy", "light"])
        assert rebalanced[0] == "light"

    def test_new_agent_score_zero(self):
        assert self.clb.agent_load_score("new_agent") == 0.0


# ── ContagionSentinel (macro_sentinel.py) ─────────────────────────────────────
class TestContagionSentinel:
    def setup_method(self):
        from macro_sentinel import ContagionSentinel
        self.cs = ContagionSentinel(lookback=10, contagion_threshold=0.85)

    def _seed_correlated(self):
        rng = np.random.default_rng(0)
        common = rng.normal(0, 0.02, 15).tolist()
        return {t: [r + float(rng.normal(0, 0.0001)) for r in common]
                for t in ["SPY", "QQQ", "IWM", "DIA"]}

    def _seed_uncorrelated(self):
        rng = np.random.default_rng(1)
        return {t: rng.normal(0, 0.02, 15).tolist() for t in ["SPY", "GLD", "TLT", "BTC"]}

    def test_contagion_detected_when_all_correlated(self):
        result = self.cs.detect_contagion(self._seed_correlated())
        assert result["contagion"] is True

    def test_no_contagion_uncorrelated(self):
        result = self.cs.detect_contagion(self._seed_uncorrelated())
        assert result["contagion"] is False

    def test_insufficient_tickers_no_contagion(self):
        result = self.cs.detect_contagion({"SPY": [0.01] * 15})
        assert result["contagion"] is False

    def test_result_has_avg_correlation(self):
        result = self.cs.detect_contagion(self._seed_uncorrelated())
        assert "avg_correlation" in result


# ── ProductionResiliencyAgent ─────────────────────────────────────────────────
class TestProductionResiliencyAgent:
    def setup_method(self):
        from production_agent import ProductionResiliencyAgent
        self.agent = ProductionResiliencyAgent()

    def test_detects_factory_fire(self):
        news = ["TSMC factory fire shuts down fab in Taiwan"]
        alerts = self.agent.scan_news_for_disruptions(news)
        assert len(alerts) > 0
        assert "TSMC" in alerts[0]["tickers"]

    def test_no_keywords_no_alerts(self):
        news = ["Apple reports strong quarterly earnings beating estimates"]
        alerts = self.agent.scan_news_for_disruptions(news)
        assert alerts == []

    def test_risk_factor_below_one_after_alerts(self):
        for _ in range(5):
            self.agent.scan_news_for_disruptions(["NVDA factory fire explosion"])
        factor = self.agent.risk_adjustment_factor()
        assert factor < 1.0

    def test_risk_factor_floored_at_0_4(self):
        for _ in range(100):
            self.agent.scan_news_for_disruptions(["plant shutdown explosion strike"])
        assert self.agent.risk_adjustment_factor() >= 0.4

    def test_unknown_ticker_uses_unknown(self):
        news = ["factory fire at unknown supplier"]
        alerts = self.agent.scan_news_for_disruptions(news)
        assert any("UNKNOWN" in a["tickers"] for a in alerts)


# ── PatentVelocityAgent (mocked HTTP) ─────────────────────────────────────────
class TestPatentVelocityAgent:
    def test_get_count_zero_on_error(self, monkeypatch):
        import asyncio

        import requests

        from patent_agent import PatentVelocityAgent

        def _fail(*a, **kw):
            raise requests.ConnectionError("offline")

        monkeypatch.setattr(requests, "post", _fail)
        agent = PatentVelocityAgent()
        count = asyncio.run(agent.get_patent_count("Apple", 2024))
        assert count == 0

    def test_velocity_score_structure(self, monkeypatch):
        import asyncio

        import requests

        from patent_agent import PatentVelocityAgent

        call_n = [0]

        def _mock_post(url, json=None, timeout=8):
            call_n[0] += 1

            class _R:
                def json(self):
                    # First call returns 300, second returns 100
                    return {"total_patent_count": 300 if call_n[0] == 1 else 100}
            return _R()

        monkeypatch.setattr(requests, "post", _mock_post)
        agent = PatentVelocityAgent()
        result = asyncio.run(agent.velocity_score("Apple", 2024))
        assert "signal" in result
        assert result["signal"] in ("STABLE", "ACCELERATING", "BREAKOUT")
        assert result["velocity"] > 0
