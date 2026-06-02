from __future__ import annotations

from pathlib import Path
from subprocess import CompletedProcess

import pytest

from scripts import build_native


def test_windows_build_uses_discovered_toolchain_and_quarantine_sources(monkeypatch) -> None:
    vcvarsall = Path(r"C:\VS\vcvarsall.bat")
    calls: list[tuple[list[str], Path, bool, str | None, bool | None]] = []

    def fake_run(
        command: list[str],
        *,
        cwd: Path,
        check: bool,
        input: str | None = None,
        text: bool | None = None,
    ) -> CompletedProcess:
        calls.append((command, cwd, check, input, text))
        return CompletedProcess(command, 0)

    monkeypatch.setattr(build_native.sys, "platform", "win32")
    monkeypatch.setattr(build_native, "_find_vcvarsall", lambda: vcvarsall)
    monkeypatch.setattr(build_native.subprocess, "run", fake_run)

    assert build_native.build_native() == 0
    command, cwd, check, script, text = calls[0]
    assert command == ["cmd.exe", "/d", "/q"]
    assert script is not None
    assert 'call "C:\\VS\\vcvarsall.bat" x64' in script
    assert "quarantine\\time_sync.c" in script
    assert "quarantine\\rng_audit.cpp" in script
    assert cwd == build_native.ROOT
    assert check is False
    assert text is True


def test_find_vcvarsall_fails_clearly_without_toolchain(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ProgramFiles(x86)", str(tmp_path))

    with pytest.raises(FileNotFoundError, match="Visual Studio Build Tools"):
        build_native._find_vcvarsall()


def test_makefile_adds_src_include_path_for_quarantine_sources() -> None:
    makefile = (build_native.ROOT / "Makefile").read_text(encoding="utf-8")

    assert "CPPFLAGS=-Isrc" in makefile
    assert "$(CC) $(CPPFLAGS) $(CFLAGS)" in makefile
    assert "$(CXX) $(CPPFLAGS) $(CXXFLAGS)" in makefile
