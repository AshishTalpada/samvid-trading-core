import config
import safety
import vault


class _Sys:
    """Minimal stand-in for the TradingSystem instance safety operates on."""

    def __init__(self, mode: str) -> None:
        self.mode = mode


def _clear_mode_env(monkeypatch) -> None:
    for var in (
        "TRADING_MODE",
        "PAPER_MODE",
        "ALLOW_FORCE_LIVE",
        "SOVEREIGN_PROMOTION_READINESS_REPORT",
        "SOVEREIGN_REQUIRE_PROMOTION_FOR_LIVE",
    ):
        monkeypatch.delenv(var, raising=False)


def test_apply_runtime_safety_fails_closed_when_gate_errors(monkeypatch) -> None:
    # If the safety gate itself raises, the system must never be left in 'live'.
    monkeypatch.setattr(safety, "_send_safety_alert", lambda *a, **k: None)
    monkeypatch.setattr(config, "FORCED_PAPER_MODE", False, raising=False)
    _clear_mode_env(monkeypatch)

    def _boom(*_a, **_k):
        raise RuntimeError("vault unavailable")

    monkeypatch.setattr(vault.Vault, "get", staticmethod(_boom))

    system = _Sys(mode="live")
    safety.apply_runtime_safety(system)

    assert system.mode == "paper"


def test_live_mode_without_authorization_is_downgraded(monkeypatch) -> None:
    monkeypatch.setattr(safety, "_send_safety_alert", lambda *a, **k: None)
    monkeypatch.setattr(config, "FORCED_PAPER_MODE", False, raising=False)
    _clear_mode_env(monkeypatch)
    monkeypatch.setenv("TRADING_MODE", "live")
    # No ALLOW_FORCE_LIVE anywhere.
    monkeypatch.setattr(vault.Vault, "get", staticmethod(lambda key, default=None: default))

    system = _Sys(mode="paper")
    safety.apply_runtime_safety(system)

    assert system.mode == "paper"


def test_live_mode_with_authorization_but_missing_promotion_report_is_downgraded(
    monkeypatch,
) -> None:
    monkeypatch.setattr(safety, "_send_safety_alert", lambda *a, **k: None)
    monkeypatch.setattr(config, "FORCED_PAPER_MODE", False, raising=False)
    _clear_mode_env(monkeypatch)
    monkeypatch.setenv("TRADING_MODE", "live")
    monkeypatch.setenv("ALLOW_FORCE_LIVE", "1")
    monkeypatch.setattr(vault.Vault, "get", staticmethod(lambda key, default=None: default))

    system = _Sys(mode="paper")
    safety.apply_runtime_safety(system)

    assert system.mode == "paper"


def test_live_mode_with_explicit_authorization_and_promotion_report_is_honored(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(safety, "_send_safety_alert", lambda *a, **k: None)
    monkeypatch.setattr(config, "FORCED_PAPER_MODE", False, raising=False)
    _clear_mode_env(monkeypatch)
    report = tmp_path / "promotion_readiness_report.json"
    report.write_text('{"approved": true, "blockers": []}', encoding="utf-8")
    monkeypatch.setenv("TRADING_MODE", "live")
    monkeypatch.setenv("ALLOW_FORCE_LIVE", "1")
    monkeypatch.setenv("SOVEREIGN_PROMOTION_READINESS_REPORT", str(report))
    monkeypatch.setattr(vault.Vault, "get", staticmethod(lambda key, default=None: default))

    system = _Sys(mode="paper")
    safety.apply_runtime_safety(system)

    assert system.mode == "live"
