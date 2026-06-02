from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_runtime_image_uses_locked_virtualenv_without_live_data() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert "FROM python:3.11-slim AS runtime" in dockerfile
    assert 'PATH="/app/.venv/bin:$PATH"' in dockerfile
    assert "COPY --from=base /app/.venv /app/.venv" in dockerfile
    assert "COPY --chown=sovereign:sovereign data" not in dockerfile
    assert "http://localhost:8000/health/live" in dockerfile
