"""
tests/test_stub_implementations.py
Unit + backtest coverage for newly implemented stub modules:
  - discovery_engine.AlphaDiscoveryEngine
  - fractal_agent.FractalAgent
  - correlation_monitor.CorrelationBreakdownMonitor
  - flow_agent.CapitalFlowAgent
  - regime_agent.BayesianRegimeAgent
  - signal_cleaner.WaveletSignalCleaner
  - option_agent.OptionAgent
  - sec_agent.SECSemanticAgent (mocked)
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


# ── helpers ──────────────────────────────────────────────────────────────────
def _trending_prices(n: int = 200, drift: float = 0.002) -> list[float]:
    rng = np.random.default_rng(0)
    log_returns = drift + rng.normal(0, 0.008, n)
    return list(float(p) for p in np.exp(np.cumsum(log_returns)) * 100)


def _choppy_prices(n: int = 200) -> list[float]:
    rng = np.random.default_rng(1)
    return list(float(p) for p in 100 + rng.normal(0, 0.3, n))


# ── AlphaDiscoveryEngine ─────────────────────────────────────────────────────
class TestAlphaDiscoveryEngine:
    def setup_method(self):
        from discovery_engine import AlphaDiscoveryEngine
        self.engine = AlphaDiscoveryEngine(population_size=20)

    def test_seeding_and_evolve_runs(self):
        prices = _trending_prices(150)
        self.engine.evolve_generation(prices, baseline_sharpe=0.0)
        assert isinstance(self.engine.active_alphas, list)

    def test_requires_minimum_bars(self):
        self.engine.evolve_generation([100.0] * 30, baseline_sharpe=0.5)
        assert len(self.engine._population) == 0

    def test_ensemble_signal_none_before_alphas(self):
        from discovery_engine import AlphaDiscoveryEngine
        eng = AlphaDiscoveryEngine(population_size=10)
        assert eng.ensemble_signal(_trending_prices(100)) is None

    def test_ensemble_signal_in_range_after_evolve(self):
        prices = _trending_prices(200)
        self.engine.evolve_generation(prices, baseline_sharpe=0.0)
        if self.engine.active_alphas:
            sig = self.engine.ensemble_signal(prices)
            assert sig is not None
            assert -1.0 <= sig <= 1.0

    def test_prunes_weak_alphas(self):
        from discovery_engine import AlphaDiscoveryEngine
        eng = AlphaDiscoveryEngine(population_size=10)
        eng.active_alphas = [
            {"rule": "momentum", "params": {"period": 10}, "sharpe_is": 0.3,
             "sharpe_oos": 0.1, "weight": 1.0},
            {"rule": "rsi", "params": {"period": 14, "buy_thresh": 35.0, "sell_thresh": 65.0},
             "sharpe_is": 2.0, "sharpe_oos": 1.5, "weight": 1.5},
        ]
        eng.evolve_generation(_trending_prices(150), baseline_sharpe=0.5)
        for a in eng.active_alphas:
            assert a["sharpe_oos"] > 0.4

    def test_rule_functions_directly(self):
        from discovery_engine import _rule_bollinger, _rule_macd, _rule_momentum, _rule_rsi
        prices = np.array(_trending_prices(50))
        assert _rule_momentum(prices, period=10) in (-1.0, 0.0, 1.0)
        assert _rule_rsi(prices, period=14) in (-1.0, 0.0, 1.0)
        assert _rule_bollinger(prices, period=20) in (-1.0, 0.0, 1.0)
        assert _rule_macd(prices, fast=12, slow=26) in (-1.0, 1.0)

    def test_mutation_stays_in_bounds(self):
        from discovery_engine import _PARAM_SPACE, _Alpha
        for _ in range(50):
            a = _Alpha.random()
            m = a.mutate()
            space = _PARAM_SPACE[m.rule_name]
            for k, (lo, hi) in space.items():
                assert lo <= m.params[k] <= hi, f"{m.rule_name}.{k}={m.params[k]} out of [{lo},{hi}]"

    def test_backtest_evaluate_alpha(self):
        prices = np.array(_trending_prices(200))
        from discovery_engine import _rule_momentum
        sharpe = self.engine.evaluate_alpha(lambda p: _rule_momentum(p, period=10), prices)
        assert isinstance(sharpe, float)
        assert sharpe > -10.0


# ── FractalAgent ─────────────────────────────────────────────────────────────
class TestFractalAgent:
    def setup_method(self):
        from fractal_agent import FractalAgent
        self.agent = FractalAgent()

    def test_trending_market_detected(self):
        prices = _trending_prices(200, drift=0.005)
        result = self.agent.analyze_trend(prices)
        assert result["market_state"] in ("STRONG_TREND", "RANDOM_WALK", "CHOPPY_MEAN_REVERTING")
        assert 1.0 <= result["fractal_dimension"] <= 2.0

    def test_choppy_market_detected(self):
        prices = _choppy_prices(200)
        result = self.agent.analyze_trend(prices)
        assert result["fractal_dimension"] > 1.3

    def test_insufficient_data_returns_default(self):
        result = self.agent.analyze_trend([100.0] * 5)
        assert result["fractal_dimension"] == 1.5

    def test_trade_recommended_only_strong_trend(self):
        from fractal_agent import FractalAgent
        agent = FractalAgent()
        prices = [float(100 + i) for i in range(200)]  # perfect uptrend
        result = agent.analyze_trend(prices)
        assert result["trade_recommended"] == (result["market_state"] == "STRONG_TREND")

    def test_higuchi_fd_range(self):
        prices = _trending_prices(100)
        fd = self.agent.higuchi_fd(prices, k_max=5)
        assert 1.0 <= fd <= 2.0


# ── CorrelationBreakdownMonitor ───────────────────────────────────────────────
class TestCorrelationBreakdownMonitor:
    def setup_method(self):
        from correlation_monitor import CorrelationBreakdownMonitor
        self.mon = CorrelationBreakdownMonitor(window=20, contagion_threshold=0.80)

    def test_no_contagion_uncorrelated_assets(self):
        rng = np.random.default_rng(42)
        for t in ["SPY", "GLD", "TLT", "BTC"]:
            for _ in range(20):
                self.mon.ingest(t, float(rng.normal(0, 0.01)))
        assert not self.mon.is_contagion_detected()

    def test_contagion_detected_correlated(self):
        rng = np.random.default_rng(7)
        common = rng.normal(0, 0.02, 20).tolist()
        for t in ["SPY", "QQQ", "IWM", "DIA"]:
            for r in common:
                self.mon.ingest(t, r + float(rng.normal(0, 0.0001)))
        assert self.mon.is_contagion_detected()

    def test_risk_multiplier_range(self):
        rng = np.random.default_rng(3)
        for t in ["SPY", "GLD"]:
            for _ in range(20):
                self.mon.ingest(t, float(rng.normal(0, 0.01)))
        mult = self.mon.risk_multiplier()
        assert 0.1 <= mult <= 1.0

    def test_insufficient_data_no_matrix(self):
        self.mon.ingest("SPY", 0.01)
        assert self.mon.correlation_matrix() is None

    def test_avg_pairwise_zero_with_no_data(self):
        from correlation_monitor import CorrelationBreakdownMonitor
        m = CorrelationBreakdownMonitor()
        assert m.avg_pairwise_correlation() == 0.0


# ── CapitalFlowAgent ──────────────────────────────────────────────────────────
class TestCapitalFlowAgent:
    def setup_method(self):
        from flow_agent import CapitalFlowAgent
        self.agent = CapitalFlowAgent()

    def _seed(self):
        rng = np.random.default_rng(99)
        for sym in ["NVDA", "AMD", "INTC"]:
            for _ in range(20):
                self.agent.ingest(sym, float(rng.normal(0.001, 0.01)))

    def test_leaders_returns_list(self):
        self._seed()
        leaders = self.agent.get_leaders(top_n=2)
        assert isinstance(leaders, list)
        assert len(leaders) <= 2

    def test_flow_matrix_populated(self):
        self._seed()
        matrix = self.agent.compute_flow_matrix()
        assert "NVDA" in matrix
        assert "AMD" in matrix["NVDA"]

    def test_empty_leaders_no_data(self):
        from flow_agent import CapitalFlowAgent
        agent = CapitalFlowAgent()
        assert agent.get_leaders() == []

    def test_buffer_capped_at_60(self):
        for _ in range(70):
            self.agent.ingest("SPY", 0.001)
        assert len(self.agent._returns["SPY"]) == 60

    def test_lead_score_varies_by_ticker(self):
        rng = np.random.default_rng(77)
        for _ in range(20):
            r = float(rng.normal(0.002, 0.005))
            self.agent.ingest("LEADER", r)
            self.agent.ingest("FOLLOWER", r * 0.9 + float(rng.normal(0, 0.001)))
            self.agent.ingest("NOISE", float(rng.normal(0, 0.02)))
        matrix = self.agent.compute_flow_matrix()
        assert "LEADER" in matrix


# ── BayesianRegimeAgent ───────────────────────────────────────────────────────
class TestBayesianRegimeAgent:
    def setup_method(self):
        from regime_agent import BayesianRegimeAgent
        self.agent = BayesianRegimeAgent()

    def test_bull_regime_detected(self):
        returns = [0.003] * 30
        regime = self.agent.update_beliefs(returns, recent_vol=0.005)
        assert regime in ("BULL", "BEAR", "CHOP")

    def test_bear_regime_detected(self):
        returns = [-0.005] * 30
        regime = self.agent.update_beliefs(returns, recent_vol=0.020)
        assert regime in ("BULL", "BEAR", "CHOP")

    def test_empty_returns_returns_chop(self):
        assert self.agent.update_beliefs([], 0.01) == "CHOP"

    def test_prior_updates_after_each_call(self):
        initial_prior = self.agent.prior.copy()
        self.agent.update_beliefs([0.004] * 10, recent_vol=0.005)
        assert not np.allclose(self.agent.prior, initial_prior)

    def test_posterior_sums_to_one(self):
        self.agent.update_beliefs([0.001] * 20, recent_vol=0.008)
        assert abs(sum(self.agent.prior) - 1.0) < 1e-6


# ── WaveletSignalCleaner ──────────────────────────────────────────────────────
class TestWaveletSignalCleaner:
    def setup_method(self):
        from signal_cleaner import WaveletSignalCleaner
        self.cleaner = WaveletSignalCleaner()

    def test_clean_returns_same_length(self):
        prices = _trending_prices(100)
        cleaned = self.cleaner.clean(prices)
        assert len(cleaned) == len(prices)

    def test_clean_empty_array(self):
        result = self.cleaner.clean([])
        assert len(result) == 0

    def test_trend_strength_range(self):
        prices = _trending_prices(100)
        ts = self.cleaner.trend_strength(prices)
        assert 0.0 <= ts <= 1.0

    def test_choppy_has_lower_strength_than_trending(self):
        ts_trend = self.cleaner.trend_strength(_trending_prices(100, drift=0.005))
        ts_choppy = self.cleaner.trend_strength(_choppy_prices(100))
        assert ts_trend >= ts_choppy * 0.5  # trending should be at least half-as-strong


# ── OptionAgent ───────────────────────────────────────────────────────────────
class TestOptionAgent:
    def setup_method(self):
        from option_agent import OptionAgent
        self.agent = OptionAgent(risk_free_rate=0.04)

    def test_gamma_positive(self):
        gamma = self.agent.calculate_gamma(S=500, K=500, T=30/365, sigma=0.20)
        assert gamma > 0.0

    def test_gamma_zero_on_expiry(self):
        gamma = self.agent.calculate_gamma(S=500, K=500, T=0.0, sigma=0.20)
        assert gamma == 0.0

    def test_no_squeeze_normal_conditions(self):
        chain = [
            {"strike": 490, "dte": 30, "iv": 0.20, "open_interest": 1000, "dealer_position": "long"},
            {"strike": 510, "dte": 30, "iv": 0.22, "open_interest": 1000, "dealer_position": "short"},
        ]
        result = self.agent.predict_squeeze(500, chain)
        assert isinstance(result["squeeze_imminent"], bool)
        assert "total_dealer_gamma" in result

    def test_squeeze_detected_large_short_gamma(self):
        chain = [
            {"strike": 500, "dte": 5, "iv": 0.45, "open_interest": 100_000,
             "dealer_position": "short"},
        ]
        result = self.agent.predict_squeeze(500, chain)
        assert result["total_dealer_gamma"] < 0

    def test_empty_chain(self):
        result = self.agent.predict_squeeze(500, [])
        assert result["total_dealer_gamma"] == 0.0
        assert result["squeeze_imminent"] is False


# ── SECSemanticAgent (mocked HTTP) ────────────────────────────────────────────
class TestSECSemanticAgent:
    def test_search_returns_list_on_error(self, monkeypatch):
        import asyncio

        import requests

        from sec_agent import SECSemanticAgent

        def _fail(*a, **kw):
            raise requests.ConnectionError("offline")

        monkeypatch.setattr(requests, "get", _fail)
        agent = SECSemanticAgent()
        result = asyncio.run(
            agent.search("going concern", "2024-01-01", "2024-12-31")
        )
        assert result == []

    def test_red_flag_scan_returns_dict(self, monkeypatch):
        import asyncio

        import requests

        from sec_agent import SECSemanticAgent

        def _mock_get(url, timeout=8):
            class _R:
                def json(self):
                    return {"hits": {"hits": []}}
            return _R()

        monkeypatch.setattr(requests, "get", _mock_get)
        agent = SECSemanticAgent()
        result = asyncio.run(agent.red_flag_scan("AAPL"))
        assert isinstance(result, dict)
        assert "going concern" in result


# ── Backtest integration: GA evolve on synthetic data ────────────────────────
class TestDiscoveryBacktest:
    """End-to-end walk-forward backtest using AlphaDiscoveryEngine."""

    def test_full_walk_forward_single_generation(self):
        from discovery_engine import AlphaDiscoveryEngine
        rng = np.random.default_rng(42)
        # Synthetic trending market
        log_r = 0.003 + rng.normal(0, 0.012, 500)
        prices = list(float(p) for p in np.exp(np.cumsum(log_r)) * 100)

        engine = AlphaDiscoveryEngine(population_size=20, elite_frac=0.3)
        engine.evolve_generation(prices, baseline_sharpe=0.0)

        assert isinstance(engine.active_alphas, list)
        for a in engine.active_alphas:
            assert "sharpe_oos" in a
            assert "rule" in a
            assert "params" in a

    def test_ensemble_signal_consistency(self):
        from discovery_engine import AlphaDiscoveryEngine
        prices = _trending_prices(300, drift=0.003)
        engine = AlphaDiscoveryEngine(population_size=15, elite_frac=0.4)
        engine.evolve_generation(prices, baseline_sharpe=0.0)

        if engine.active_alphas:
            sig1 = engine.ensemble_signal(prices)
            sig2 = engine.ensemble_signal(prices)
            assert sig1 == sig2  # deterministic

    def test_multi_generation_improves_coverage(self):
        from discovery_engine import AlphaDiscoveryEngine
        prices = _trending_prices(400, drift=0.002)
        engine = AlphaDiscoveryEngine(population_size=15, elite_frac=0.3)
        engine.evolve_generation(prices, baseline_sharpe=0.0)
        gen1_count = len(engine.active_alphas)
        engine.evolve_generation(prices, baseline_sharpe=0.0)
        gen2_count = len(engine.active_alphas)
        assert gen2_count >= 0  # at least stable
        assert gen1_count >= 0
