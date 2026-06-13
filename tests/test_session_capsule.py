from __future__ import annotations

import json
import time

from session_restorer import SessionRestorer


def _restorer(tmp_path, monkeypatch) -> SessionRestorer:
    monkeypatch.setenv("SESSION_SECRET", "test-session-secret")
    from vault import Vault

    Vault.clear_cache()
    return SessionRestorer(
        path=str(tmp_path / "session.bin"),
        capsule_path=str(tmp_path / "capsule.json"),
    )


def test_cognitive_capsule_round_trip_is_atomic_and_fresh(tmp_path, monkeypatch) -> None:
    restorer = _restorer(tmp_path, monkeypatch)

    restorer.save_cognitive_capsule({"regime": "TRENDING", "session_pnl": 999.0})

    assert restorer.load_cognitive_capsule() == {
        "regime": "TRENDING",
        "session_pnl": 999.0,
    }
    assert not list(tmp_path.glob("*.tmp"))


def test_stale_cognitive_capsule_is_ignored(tmp_path, monkeypatch) -> None:
    restorer = _restorer(tmp_path, monkeypatch)
    with open(restorer.capsule_path, "w", encoding="utf-8") as capsule:
        json.dump(
            {"timestamp": time.time_ns() - 10_000_000_000, "payload": {"regime": "STALE"}},
            capsule,
        )

    assert restorer.load_cognitive_capsule(max_age_seconds=5) == {}


def test_future_cognitive_capsule_is_ignored(tmp_path, monkeypatch) -> None:
    restorer = _restorer(tmp_path, monkeypatch)
    with open(restorer.capsule_path, "w", encoding="utf-8") as capsule:
        json.dump(
            {"timestamp": time.time_ns() + 600_000_000_000, "payload": {"regime": "FUTURE"}},
            capsule,
        )

    assert restorer.load_cognitive_capsule() == {}


def test_structurally_invalid_cognitive_capsule_is_ignored(tmp_path, monkeypatch) -> None:
    restorer = _restorer(tmp_path, monkeypatch)
    with open(restorer.capsule_path, "w", encoding="utf-8") as capsule:
        json.dump({"timestamp": time.time_ns(), "payload": ["not", "a", "mapping"]}, capsule)

    assert restorer.load_cognitive_capsule() == {}
