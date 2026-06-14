"""
tests/test_archive_and_sim.py
Tests for:
  - apex_archive.ApexArchive (immutable decision audit trail)
  - shadow_sim.GhostShadowSim (virtual PnL tracker)
  - crypto_bridge.CryptoBridgeAgent (mocked HTTP)
  - mind_experiment.MindExperiment (evolution methods)
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


# ── ApexArchive ───────────────────────────────────────────────────────────────
class TestApexArchive:
    def setup_method(self):
        self._tmpdir = tempfile.mkdtemp()
        from apex_archive import ApexArchive
        self.archive = ApexArchive(path=f"{self._tmpdir}/archive.jsonl")

    def test_record_returns_hash_string(self):
        h = self.archive.record({"decision": "BUY", "symbol": "AAPL"})
        assert isinstance(h, str) and len(h) == 64  # sha3-256 hex

    def test_record_writes_to_disk(self):
        self.archive.record({"decision": "SELL", "symbol": "MSFT"})
        p = Path(f"{self._tmpdir}/archive.jsonl")
        assert p.exists() and p.stat().st_size > 0

    def test_chain_hashes_are_linked(self):
        import json
        h1 = self.archive.record({"x": 1})
        h2 = self.archive.record({"x": 2})
        lines = Path(f"{self._tmpdir}/archive.jsonl").read_text().strip().splitlines()
        e2 = json.loads(lines[1])
        assert e2["prev_hash"] == h1

    def test_verify_chain_on_valid_archive(self):
        for i in range(5):
            self.archive.record({"i": i})
        assert self.archive.verify_chain() is True

    def test_verify_chain_detects_tampering(self):
        import json
        self.archive.record({"step": 1})
        self.archive.record({"step": 2})
        self.archive.record({"step": 3})
        p = Path(f"{self._tmpdir}/archive.jsonl")
        lines = p.read_text().splitlines()
        # Tamper the prev_hash of entry[1] — this is checked by the loop
        entry = json.loads(lines[1])
        entry["prev_hash"] = "TAMPERED_HASH"
        lines[1] = json.dumps(entry)
        p.write_text("\n".join(lines))
        from apex_archive import ApexArchive
        reader = ApexArchive(path=str(p))
        assert reader.verify_chain() is False

    def test_each_hash_is_unique(self):
        h1 = self.archive.record({"a": 1})
        h2 = self.archive.record({"a": 1})  # same payload but chained
        assert h1 != h2  # prev_hash differs so hash must differ

    def test_genesis_is_first_prev_hash(self):
        import json
        self.archive.record({"genesis": True})
        p = Path(f"{self._tmpdir}/archive.jsonl")
        first = json.loads(p.read_text().splitlines()[0])
        assert first["prev_hash"] == "GENESIS"


# ── GhostShadowSim ────────────────────────────────────────────────────────────
class TestGhostShadowSim:
    def setup_method(self):
        from shadow_sim import GhostShadowSim
        self.sim = GhostShadowSim()

    def test_fork_creates_active_trade(self):
        self.sim.fork_signal("AAPL", 180.0, "BUY")
        assert "AAPL" in self.sim.active_trades

    def test_duplicate_fork_ignored(self):
        self.sim.fork_signal("AAPL", 180.0, "BUY")
        self.sim.fork_signal("AAPL", 190.0, "BUY")  # second call should be ignored
        assert self.sim.active_trades["AAPL"].entry_price == 180.0

    def test_update_buy_positive_pnl(self):
        self.sim.fork_signal("TSLA", 100.0, "BUY")
        self.sim.update("TSLA", 101.0)
        assert self.sim.active_trades["TSLA"].pnl == pytest.approx(0.01)

    def test_update_sell_positive_pnl(self):
        self.sim.fork_signal("MSFT", 200.0, "SELL")
        self.sim.update("MSFT", 198.0)
        assert self.sim.active_trades["MSFT"].pnl == pytest.approx(0.01)

    def test_auto_close_on_profit_target(self):
        self.sim.fork_signal("NVDA", 100.0, "BUY")
        self.sim.update("NVDA", 103.0)  # +3% -> exceeds 2% target
        assert "NVDA" not in self.sim.active_trades
        assert len(self.sim.history) == 1

    def test_auto_close_on_stop_loss(self):
        self.sim.fork_signal("AMD", 100.0, "BUY")
        self.sim.update("AMD", 98.5)  # -1.5% -> exceeds -1% stop
        assert "AMD" not in self.sim.active_trades

    def test_manual_close_works(self):
        self.sim.fork_signal("GOOG", 150.0, "BUY")
        self.sim.close_shadow_trade("GOOG", 152.0)
        assert "GOOG" not in self.sim.active_trades
        assert self.sim.history[-1].is_closed is True

    def test_get_stats_win_rate(self):
        # update() sets pnl before auto-close; use prices that trigger auto-close
        self.sim.fork_signal("A", 100.0, "BUY")
        self.sim.update("A", 103.0)  # +3% > 2% -> auto-closed as WIN (pnl=0.03)
        self.sim.fork_signal("B", 100.0, "BUY")
        self.sim.update("B", 98.5)   # -1.5% < -1% -> auto-closed as LOSS
        stats = self.sim.get_stats()
        assert stats["win_rate"] == pytest.approx(0.5)

    def test_get_stats_active_count(self):
        self.sim.fork_signal("X", 50.0, "SELL")
        stats = self.sim.get_stats()
        assert stats["active_count"] == 1

    def test_update_unknown_symbol_noop(self):
        self.sim.update("UNKNOWN_TICKER", 100.0)  # should not raise


# ── CryptoBridgeAgent ─────────────────────────────────────────────────────────
class TestCryptoBridgeAgent:
    def test_risk_signal_risk_off(self):
        from crypto_bridge import CryptoBridgeAgent
        agent = CryptoBridgeAgent()
        assert agent.risk_signal(-0.08) == "RISK_OFF"

    def test_risk_signal_risk_on(self):
        from crypto_bridge import CryptoBridgeAgent
        agent = CryptoBridgeAgent()
        assert agent.risk_signal(0.07) == "RISK_ON"

    def test_risk_signal_neutral(self):
        from crypto_bridge import CryptoBridgeAgent
        agent = CryptoBridgeAgent()
        assert agent.risk_signal(0.02) == "NEUTRAL"

    def test_get_crypto_returns_on_error(self, monkeypatch):
        import asyncio
        import requests
        from crypto_bridge import CryptoBridgeAgent
        monkeypatch.setattr(requests, "get", lambda *a, **kw: (_ for _ in ()).throw(requests.ConnectionError()))
        agent = CryptoBridgeAgent()
        result = asyncio.run(agent.get_crypto_returns())
        assert result == {}

    def test_get_crypto_returns_mocked(self, monkeypatch):
        import asyncio
        import requests
        from crypto_bridge import CryptoBridgeAgent

        def _mock_get(url, params=None, timeout=5):
            class _R:
                def json(self):
                    return {
                        "bitcoin": {"usd_24h_change": 5.0},
                        "ethereum": {"usd_24h_change": -3.0},
                    }
            return _R()

        monkeypatch.setattr(requests, "get", _mock_get)
        agent = CryptoBridgeAgent()
        result = asyncio.run(agent.get_crypto_returns())
        assert result["bitcoin"] == pytest.approx(0.05)
        assert result["ethereum"] == pytest.approx(-0.03)


# ── MindExperiment evolution methods ─────────────────────────────────────────
class TestMindExperimentEvolution:
    def setup_method(self):
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

    def _make_experiment(self):
        from unittest.mock import MagicMock
        bridge = MagicMock()
        bridge.register_tool = MagicMock()
        from mind_experiment import MindExperiment
        return MindExperiment(bridge)

    def test_init_population_creates_clones(self):
        exp = self._make_experiment()
        base = np.array([0.5, -0.3, 0.1])
        exp.init_population(base)
        assert len(exp.population) == exp.pop_size

    def test_clones_are_mutated_from_base(self):
        exp = self._make_experiment()
        base = np.zeros(5)
        exp.init_population(base)
        weights = [c["weights"] for c in exp.population]
        # At least some clones should differ from exact zero
        assert any(not np.allclose(w, base) for w in weights)

    def test_evaluate_fitness_scores_all_clones(self):
        exp = self._make_experiment()
        base = np.random.randn(3)
        exp.init_population(base)
        data = np.random.randn(50, 3)
        labels = np.random.randn(50)
        exp.evaluate_fitness(data, labels)
        assert all(0.0 <= c["fitness"] <= 1.0 for c in exp.population)

    def test_population_sorted_by_fitness(self):
        exp = self._make_experiment()
        base = np.random.randn(4)
        exp.init_population(base)
        data = np.random.randn(30, 4)
        labels = np.random.randn(30)
        exp.evaluate_fitness(data, labels)
        fitnesses = [c["fitness"] for c in exp.population]
        assert fitnesses == sorted(fitnesses, reverse=True)

    def test_breed_next_generation_increments_generation(self):
        exp = self._make_experiment()
        base = np.random.randn(3)
        exp.init_population(base)
        data = np.random.randn(20, 3)
        exp.evaluate_fitness(data, np.random.randn(20))
        exp.breed_next_generation()
        assert exp.generation == 2

    def test_breed_returns_best_weights(self):
        exp = self._make_experiment()
        base = np.ones(4)
        exp.init_population(base)
        data = np.random.randn(20, 4)
        exp.evaluate_fitness(data, np.random.randn(20))
        apex = exp.breed_next_generation()
        assert apex.shape == (4,)

    def test_population_stays_same_size_after_breed(self):
        exp = self._make_experiment()
        base = np.random.randn(3)
        exp.init_population(base)
        data = np.random.randn(20, 3)
        exp.evaluate_fitness(data, np.random.randn(20))
        exp.breed_next_generation()
        assert len(exp.population) == exp.pop_size

    def test_shape_mismatch_gives_zero_fitness(self):
        exp = self._make_experiment()
        base = np.random.randn(3)
        exp.init_population(base)
        data = np.random.randn(20, 5)  # wrong feature count
        labels = np.random.randn(20)
        exp.evaluate_fitness(data, labels)
        assert all(c["fitness"] == 0.0 for c in exp.population)
