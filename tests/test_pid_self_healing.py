from pathlib import Path

import main
import watchdog


def test_main_restores_missing_own_pid_file(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("SOVEREIGN_SKIP_PID_CHECK", raising=False)
    monkeypatch.setattr(main.os, "getpid", lambda: 1234)
    system = main.TradingSystem.__new__(main.TradingSystem)

    assert system._ensure_own_pid_file() is True
    assert Path("data/main.pid").read_text(encoding="utf-8") == "1234"


def test_old_watchdog_exits_when_live_owner_changed(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    Path("data").mkdir()
    Path("data/watchdog.pid").write_text("2222", encoding="utf-8")
    monkeypatch.setattr(watchdog.os, "getpid", lambda: 1111)
    monkeypatch.setattr(watchdog, "_is_live_watchdog_process", lambda pid: pid == 2222)

    assert watchdog._maintain_watchdog_pid_claim() is False
    assert Path("data/watchdog.pid").read_text(encoding="utf-8") == "2222"


def test_watchdog_reclaims_missing_pid_file(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(watchdog.os, "getpid", lambda: 3333)

    assert watchdog._maintain_watchdog_pid_claim() is True
    assert Path("data/watchdog.pid").read_text(encoding="utf-8") == "3333"
