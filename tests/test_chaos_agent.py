from __future__ import annotations

import os

import chaos_agent


class _FakeFunction:
    def __call__(self, *_args):
        return 0.25


class _FakeLibrary:
    def __init__(self) -> None:
        self.compute_lyapunov_exponent = _FakeFunction()


def test_chaos_agent_loads_native_library_from_build_directory(tmp_path, monkeypatch) -> None:
    extension = ".dll" if os.name == "nt" else ".so"
    library_path = tmp_path / "build" / f"libsovereign{extension}"
    library_path.parent.mkdir()
    library_path.touch()
    loaded_paths: list[str] = []

    def fake_cdll(path: str) -> _FakeLibrary:
        loaded_paths.append(path)
        return _FakeLibrary()

    monkeypatch.setattr(chaos_agent, "PROJECT_PATH", tmp_path)
    monkeypatch.setattr(chaos_agent.ctypes, "CDLL", fake_cdll)

    agent = chaos_agent.ChaosAgent()

    assert loaded_paths == [str(library_path)]
    assert agent.calculate_market_randomness(list(range(1, 51))) == 0.25
