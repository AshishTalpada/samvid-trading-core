from pathlib import Path

import watchdog


def test_silence_timeout_allows_one_watchdog_interval_of_scheduler_jitter() -> None:
    assert watchdog.SILENCE_TIMEOUT >= 60 + watchdog.CHECK_INTERVAL


def test_startup_silence_timeout_allows_slow_broker_probes() -> None:
    assert watchdog.STARTUP_SILENCE_TIMEOUT >= 2 * watchdog.LIVENESS_TIMEOUT


def test_soft_task_live_lock_does_not_force_engine_restart() -> None:
    stale = {"AGENT_D": 180.0, "tv_quote_streamer": 181.0}

    assert watchdog.hard_restart_stale_tasks(stale) == {}


def test_core_task_live_lock_can_force_engine_restart() -> None:
    stale = {"AGENT_D": 180.0, "BRAIN_PRIMARY": 181.0}

    assert watchdog.hard_restart_stale_tasks(stale) == {"BRAIN_PRIMARY": 181.0}


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


def _proc(pid, ppid, cmdline=""):
    return {"pid": pid, "ppid": ppid, "cmdline": cmdline}


def test_select_orphan_workers_picks_engine_spawned_workers() -> None:
    main_pid = 1000
    processes = [
        _proc(1000, 1, "uv-python src/main.py"),
        _proc(1001, 1000, "uv-python src/neural_sandbox.py --worker model.gguf"),
        _proc(1002, 1000, "uv-python src/master_trainer.py"),
        _proc(2000, 1000, "uv-python src/watchdog.py"),  # watchdog subtree (protected)
        _proc(2001, 2000, "uv-python src/watchdog.py"),
        _proc(3000, 1, "uv-python src/main.py"),  # unrelated tree
    ]
    protected = {2000, 2001}

    victims = watchdog.select_orphan_worker_pids(processes, main_pid, protected)

    assert sorted(victims) == [1001, 1002]


def test_select_orphan_workers_never_returns_protected_or_main() -> None:
    main_pid = 1000
    processes = [
        _proc(1000, 1, "uv-python src/main.py"),
        _proc(2000, 1000, "uv-python src/neural_sandbox.py --worker m"),  # protected worker
        _proc(1001, 1000, "uv-python src/main.py"),  # non-worker child, ignored
    ]
    protected = {2000}

    victims = watchdog.select_orphan_worker_pids(processes, main_pid, protected)

    assert victims == []


def test_select_orphan_workers_finds_nested_descendants() -> None:
    main_pid = 1000
    processes = [
        _proc(1000, 1, "main.py"),
        _proc(1500, 1000, "venv-trampoline neural_sandbox.py"),  # trampoline
        _proc(1501, 1500, "uv neural_sandbox.py --worker m"),  # nested engine worker
    ]

    victims = watchdog.select_orphan_worker_pids(processes, main_pid, set())

    assert sorted(victims) == [1500, 1501]
