from pathlib import Path

import watchdog


def test_watchdog_pid_claim_refuses_live_existing_owner(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    data_dir = Path("data")
    data_dir.mkdir()
    (data_dir / "watchdog.pid").write_text("123", encoding="utf-8")
    monkeypatch.setattr(watchdog, "_is_live_watchdog_process", lambda pid: pid == 123)

    assert watchdog._write_watchdog_pid() is False
    assert (data_dir / "watchdog.pid").read_text(encoding="utf-8") == "123"


def test_watchdog_pid_claim_replaces_stale_owner(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    data_dir = Path("data")
    data_dir.mkdir()
    (data_dir / "watchdog.pid").write_text("123", encoding="utf-8")
    monkeypatch.setattr(watchdog, "_is_live_watchdog_process", lambda _pid: False)
    monkeypatch.setattr(watchdog.os, "getpid", lambda: 456)

    assert watchdog._write_watchdog_pid() is True
    assert (data_dir / "watchdog.pid").read_text(encoding="utf-8") == "456"


def test_run_watchdog_exits_when_singleton_claim_fails(monkeypatch) -> None:
    monkeypatch.setattr(watchdog, "_write_watchdog_pid", lambda: False)

    assert watchdog.run_watchdog() is None
