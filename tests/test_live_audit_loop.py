import json
from pathlib import Path

from scripts import live_audit_loop


def test_analyse_classifies_errors_warnings_and_tracebacks(tmp_path) -> None:
    log_path = tmp_path / "cycle.log"
    log_path.write_text(
        "\n".join(
            [
                "2026-05-30 - service - WARNING - degraded dependency",
                "2026-05-30 - service - ERROR - failed startup",
                "Traceback (most recent call last):",
                '  File "runner.py", line 1, in <module>',
                "RuntimeError: synthetic failure",
            ]
        ),
        encoding="utf-8",
    )

    result = live_audit_loop.analyse(log_path)

    assert len(result["warnings"]) == 1
    assert len(result["errors"]) == 1
    assert len(result["tracebacks"]) == 1


def test_analyse_separates_fallback_paths_from_true_outages(tmp_path) -> None:
    log_path = tmp_path / "cycle.log"
    log_path.write_text(
        "\n".join(
            [
                "OpenBB SDK not available - using yfinance provider.",
                "Native SLM runtime missing; deterministic fallback online.",
                "IBKR connection failed: refused",
            ]
        ),
        encoding="utf-8",
    )

    result = live_audit_loop.analyse(log_path)

    assert result["degraded"] == [
        "OpenBB SDK not available - using yfinance provider.",
        "Native SLM runtime missing; deterministic fallback online.",
    ]
    assert result["offline"] == ["IBKR connection failed: refused"]


def test_save_summary_emits_machine_readable_cycle_evidence(tmp_path, monkeypatch) -> None:
    root = tmp_path
    log_dir = root / "logs"
    log_dir.mkdir()
    log_path = log_dir / "cycle.log"
    log_path.write_text("clean startup\n", encoding="utf-8")
    monkeypatch.setattr(live_audit_loop, "ROOT", root)
    monkeypatch.setattr(live_audit_loop, "LOG_DIR", log_dir)
    result = {
        "errors": [],
        "warnings": [],
        "degraded": [],
        "offline": [],
        "tracebacks": [],
        "service_status": {},
        "total_lines": 1,
    }
    evidence = {
        "cycle": 1,
        "preflight": {"passed": True},
        "fault_probe": {"passed": True},
        "timed_out": True,
        "process_returncode": 0,
    }

    summary_path = live_audit_loop.save_summary([result], [log_path], [evidence])
    payload = json.loads(Path(summary_path).read_text(encoding="utf-8"))

    assert summary_path.suffix == ".json"
    assert payload["passed"] is True
    assert payload["cycles_run"] == 1
    assert payload["cycles"][0]["passed"] is True
    assert payload["cycles"][0]["log_path"] == "logs/cycle.log"


def test_save_summary_fails_cycle_when_fault_probe_fails(tmp_path, monkeypatch) -> None:
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    log_path = log_dir / "cycle.log"
    log_path.write_text("clean startup\n", encoding="utf-8")
    monkeypatch.setattr(live_audit_loop, "ROOT", tmp_path)
    monkeypatch.setattr(live_audit_loop, "LOG_DIR", log_dir)
    result = {
        "errors": [],
        "warnings": [],
        "degraded": [],
        "offline": [],
        "tracebacks": [],
        "service_status": {},
        "total_lines": 1,
    }
    evidence = {
        "cycle": 1,
        "preflight": {"passed": True},
        "fault_probe": {"passed": False},
        "timed_out": True,
        "process_returncode": 0,
    }

    summary_path = live_audit_loop.save_summary([result], [log_path], [evidence])
    payload = json.loads(Path(summary_path).read_text(encoding="utf-8"))

    assert payload["passed"] is False
    assert payload["cycles"][0]["passed"] is False
