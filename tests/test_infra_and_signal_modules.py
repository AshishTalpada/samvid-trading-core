"""
tests/test_infra_and_signal_modules.py
Tests for:
  - jet_agent.CorporateJetTracker
  - hacker_feed._score_threat (pure function)
  - gc_tuner.GarbageCollectorTuner
  - latent_search.LatentSpaceSearcher
  - lock_free_log.LockFreeDecisionLog
  - logistics_sim.LogisticsChainSimulator
  - hardware_audit.HardwareAuditor
  - hardware_encryption.HardwareEncryptionLayer
"""
from __future__ import annotations

import sys
import threading
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


# ── CorporateJetTracker ───────────────────────────────────────────────────────
class TestCorporateJetTracker:
    def setup_method(self):
        from jet_agent import CorporateJetTracker
        self.jt = CorporateJetTracker()

    def test_no_logs_zero_scores(self):
        scores = self.jt.score_activity([])
        assert scores == {}

    def test_known_airport_scored(self):
        logs = [{"destination": "KSUN"}, {"destination": "KSUN"}, {"destination": "KHPN"}]
        scores = self.jt.score_activity(logs)
        assert "KSUN" in scores
        assert scores["KSUN"] == pytest.approx(0.2)

    def test_unknown_airport_not_scored(self):
        logs = [{"destination": "KJFK"}]
        scores = self.jt.score_activity(logs)
        assert "KJFK" not in scores

    def test_score_capped_at_one(self):
        logs = [{"destination": "KBFF"}] * 20
        scores = self.jt.score_activity(logs)
        assert scores["KBFF"] == pytest.approx(1.0)

    def test_ma_probability_zero_no_activity(self):
        assert self.jt.ma_probability({}) == pytest.approx(0.0)

    def test_ma_probability_increases_with_scores(self):
        scores = {"KSUN": 0.8, "KHPN": 0.6}
        prob = self.jt.ma_probability(scores)
        assert prob > 0.0


# ── hacker_feed._score_threat ─────────────────────────────────────────────────
class TestHackerFeedScorer:
    def setup_method(self):
        from hacker_feed import _score_threat
        self._score = _score_threat

    def test_no_keywords_score_zero(self):
        assert self._score("Apple reports earnings beat this quarter") == 0.0

    def test_single_keyword_low_score(self):
        score = self._score("Hack discovered in popular exchange")
        assert 0.0 < score <= 1.0

    def test_multiple_keywords_higher_score(self):
        s1 = self._score("hack at exchange")
        s2 = self._score("hack exploit breach at exchange fraud")
        assert s2 >= s1

    def test_score_capped_at_one(self):
        assert self._score("hack exploit breach ransomware fraud ponzi rug") <= 1.0

    def test_case_insensitive(self):
        assert self._score("HACK EXPLOIT BREACH") == self._score("hack exploit breach")


# ── GarbageCollectorTuner ─────────────────────────────────────────────────────
class TestGarbageCollectorTuner:
    def setup_method(self):
        import gc

        from gc_tuner import GarbageCollectorTuner
        self.gc_mod = gc
        self.tuner = GarbageCollectorTuner()

    def teardown_method(self):
        # Always re-enable GC after test
        self.gc_mod.enable()

    def test_enter_critical_disables_gc(self):
        self.tuner.enter_critical_section()
        assert not self.gc_mod.isenabled()

    def test_exit_critical_reenables_gc(self):
        self.tuner.enter_critical_section()
        self.tuner.exit_critical_section()
        assert self.gc_mod.isenabled()

    def test_tune_for_hft_sets_thresholds(self):
        self.tuner.tune_for_hft()
        t = self.gc_mod.get_threshold()
        assert t[0] == 2000

    def test_force_collect_returns_int(self):
        n = self.tuner.force_collect_non_critical()
        assert isinstance(n, int) and n >= 0

    def test_get_stats_has_keys(self):
        stats = self.tuner.get_stats()
        assert all(k in stats for k in ("threshold", "counts", "enabled"))


# ── LatentSpaceSearcher ───────────────────────────────────────────────────────
class TestLatentSpaceSearcher:
    def setup_method(self):
        from latent_search import LatentSpaceSearcher
        self.ls = LatentSpaceSearcher()

    def _add_regime(self, label, pattern):
        self.ls.add(label, np.array(pattern, dtype=float))

    def test_search_empty_returns_empty(self):
        result = self.ls.search(np.ones(4), top_k=3)
        assert result == []

    def test_find_analogous_empty_returns_none(self):
        assert self.ls.find_analogous_regime({"a": 1.0}) is None

    def test_most_similar_returned_first(self):
        self._add_regime("BULL", [1.0, 1.0, 1.0, 0.0])
        self._add_regime("BEAR", [-1.0, -1.0, -1.0, 0.0])
        results = self.ls.search(np.array([1.0, 1.0, 1.0, 0.0]), top_k=2)
        assert results[0][0] == "BULL"

    def test_top_k_respected(self):
        for i in range(10):
            self.ls.add(f"regime_{i}", np.random.randn(8))
        results = self.ls.search(np.random.randn(8), top_k=3)
        assert len(results) == 3

    def test_find_analogous_returns_label(self):
        self._add_regime("HIGH_VOL", [0.9, 0.8, 0.7])
        result = self.ls.find_analogous_regime({"v1": 0.9, "v2": 0.8, "v3": 0.7})
        assert result == "HIGH_VOL"


# ── LockFreeDecisionLog ───────────────────────────────────────────────────────
class TestLockFreeDecisionLog:
    def setup_method(self):
        from lock_free_log import LockFreeDecisionLog
        self.log = LockFreeDecisionLog(capacity=8)

    def test_append_and_pop(self):
        self.log.append({"action": "BUY"})
        rec = self.log.pop()
        assert rec is not None
        assert rec["action"] == "BUY"

    def test_pop_empty_returns_none(self):
        assert self.log.pop() is None

    def test_size_tracks_entries(self):
        for i in range(3):
            self.log.append({"i": i})
        assert self.log.size() == 3

    def test_drain_empties_buffer(self):
        for i in range(5):
            self.log.append({"i": i})
        records = self.log.drain()
        assert len(records) == 5
        assert self.log.size() == 0

    def test_fifo_ordering(self):
        for i in range(4):
            self.log.append({"seq": i})
        first = self.log.pop()
        assert first["seq"] == 0

    def test_full_buffer_returns_false(self):
        # Capacity 8 means 7 usable slots (head+1 == tail = full)
        results = [self.log.append({"x": i}) for i in range(8)]
        assert False in results  # at least one append dropped

    def test_timestamp_added(self):
        self.log.append({"event": "test"})
        rec = self.log.pop()
        assert "_ts" in rec

    def test_thread_safety(self):
        errors = []

        def _writer():
            try:
                for i in range(50):
                    self.log.append({"i": i})
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=_writer) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert errors == []


# ── LogisticsChainSimulator ───────────────────────────────────────────────────
class TestLogisticsChainSimulator:
    def setup_method(self):
        from logistics_sim import LogisticsChainSimulator
        self.sim = LogisticsChainSimulator(n_simulations=200, rng_seed=7)

    def test_returns_all_keys(self):
        result = self.sim.simulate_disruption(100.0, 1.0, 10)
        assert all(k in result for k in ("expected_price", "p5_price", "p95_price",
                                         "expected_pct_change", "var_95"))

    def test_positive_disruption_raises_price(self):
        result = self.sim.simulate_disruption(100.0, 2.0, 30)
        assert result["expected_price"] > 100.0

    def test_percentile_ordering(self):
        result = self.sim.simulate_disruption(100.0, 1.0, 10)
        assert result["p5_price"] <= result["expected_price"] <= result["p95_price"]

    def test_var_95_negative(self):
        # VaR at 95% of (price - base) — most adverse tail should be negative
        result = self.sim.simulate_disruption(100.0, 0.0, 5)
        assert result["var_95"] < result["expected_price"]

    def test_deterministic_with_seed(self):
        from logistics_sim import LogisticsChainSimulator
        sim2 = LogisticsChainSimulator(n_simulations=200, rng_seed=7)
        r1 = self.sim.simulate_disruption(100.0, 1.0, 5)
        r2 = sim2.simulate_disruption(100.0, 1.0, 5)
        assert r1["expected_price"] == pytest.approx(r2["expected_price"])


# ── HardwareAuditor ───────────────────────────────────────────────────────────
class TestHardwareAuditor:
    def setup_method(self):
        from hardware_audit import HardwareAuditor
        self.auditor = HardwareAuditor()

    def test_fingerprint_is_64_char_hex(self):
        fp = self.auditor.fingerprint()
        assert len(fp) == 64 and all(c in "0123456789abcdef" for c in fp)

    def test_fingerprint_deterministic(self):
        assert self.auditor.fingerprint() == self.auditor.fingerprint()

    def test_verify_integrity_true_for_own_fingerprint(self):
        fp = self.auditor.fingerprint()
        assert self.auditor.verify_integrity(fp) is True

    def test_verify_integrity_false_for_wrong_fingerprint(self):
        assert self.auditor.verify_integrity("a" * 64) is False

    def test_audit_report_keys(self):
        report = self.auditor.audit_report()
        assert all(k in report for k in ("cpu", "arch", "os", "fingerprint"))

    def test_audit_report_fingerprint_truncated(self):
        report = self.auditor.audit_report()
        assert report["fingerprint"].endswith("...")


# ── HardwareEncryptionLayer ───────────────────────────────────────────────────
class TestHardwareEncryptionLayer:
    def setup_method(self):
        from hardware_encryption import HardwareEncryptionLayer
        self.enc = HardwareEncryptionLayer()

    def test_encrypt_decrypt_roundtrip(self):
        plaintext = b"sovereign_alpha_signal"
        ct = self.enc.encrypt(plaintext)
        if self.enc.is_hardware_accelerated():
            recovered = self.enc.decrypt(ct)
            assert recovered == plaintext
        else:
            assert ct == plaintext  # fallback returns raw

    def test_encrypt_different_nonce_each_time(self):
        if not self.enc.is_hardware_accelerated():
            pytest.skip("cryptography not installed")
        data = b"hello"
        ct1 = self.enc.encrypt(data)
        ct2 = self.enc.encrypt(data)
        assert ct1 != ct2  # different nonces

    def test_ciphertext_longer_than_plaintext(self):
        if not self.enc.is_hardware_accelerated():
            pytest.skip("cryptography not installed")
        pt = b"trade_decision"
        ct = self.enc.encrypt(pt)
        assert len(ct) > len(pt)

    def test_is_hardware_accelerated_returns_bool(self):
        assert isinstance(self.enc.is_hardware_accelerated(), bool)
