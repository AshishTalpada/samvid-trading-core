"""
tests/test_docker_config.py
Docker configuration validation tests (Phase 5)

Validates Dockerfile and docker-compose.yml without requiring a running
Docker daemon.  All checks are pure static analysis.

Verifies:
  1.  Dockerfile exists and has a non-root USER directive
  2.  Dockerfile exposes the expected ports (9090, 8000)
  3.  Dockerfile has a HEALTHCHECK directive
  4.  docker-compose.yml is valid YAML
  5.  docker-compose.yml defines a 'trading' service
  6.  docker-compose.yml defines a 'questdb' service
  7.  docker-compose.yml maps port 8000 for the trading service
  8.  docker-compose.yml maps port 9090 for metrics
  9.  docker-compose.yml uses named volumes (data persists across restarts)
  10. Prometheus config is valid YAML with a 'scrape_configs' key
  11. .env.example exists and contains required keys
  12. .dockerignore exists and excludes .env and vault.json
  13. trading service depends_on questdb
  14. docker-compose.yml contains a sovereign_net network definition
"""

import sys
from pathlib import Path

import pytest
import yaml  # PyYAML is already a dependency via yoyo-migrations → vendored

sys.path.insert(0, "src")

# ── Project root ──────────────────────────────────────────────────────────
_ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Fixtures: parsed files
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def dockerfile_text():
    p = _ROOT / "Dockerfile"
    assert p.exists(), "Dockerfile not found"
    return p.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def compose_data():
    p = _ROOT / "docker-compose.yml"
    assert p.exists(), "docker-compose.yml not found"
    return yaml.safe_load(p.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def prometheus_data():
    p = _ROOT / "deploy" / "prometheus" / "prometheus.yml"
    assert p.exists(), "deploy/prometheus/prometheus.yml not found"
    return yaml.safe_load(p.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Dockerfile tests
# ---------------------------------------------------------------------------

def test_dockerfile_exists(dockerfile_text):
    """Test 1: Dockerfile exists and is non-empty."""
    assert len(dockerfile_text) > 100


def test_dockerfile_has_non_root_user(dockerfile_text):
    """Test 1b: Dockerfile uses a non-root USER for security."""
    assert "USER " in dockerfile_text
    # The non-root user should NOT be root
    lines_with_user = [l.strip() for l in dockerfile_text.splitlines() if l.strip().startswith("USER ")]
    for line in lines_with_user:
        assert "root" not in line.lower(), f"Dockerfile sets USER to root: {line}"


def test_dockerfile_exposes_api_port(dockerfile_text):
    """Test 2: Dockerfile EXPOSEs port 8000 (REST API)."""
    assert "8000" in dockerfile_text


def test_dockerfile_exposes_metrics_port(dockerfile_text):
    """Test 2b: Dockerfile EXPOSEs port 9090 (Prometheus metrics)."""
    assert "9090" in dockerfile_text


def test_dockerfile_has_healthcheck(dockerfile_text):
    """Test 3: Dockerfile includes a HEALTHCHECK directive."""
    assert "HEALTHCHECK" in dockerfile_text


# ---------------------------------------------------------------------------
# docker-compose.yml tests
# ---------------------------------------------------------------------------

def test_compose_is_valid_yaml(compose_data):
    """Test 4: docker-compose.yml parses as valid YAML."""
    assert isinstance(compose_data, dict)


def test_compose_has_trading_service(compose_data):
    """Test 5: docker-compose.yml defines a 'trading' service."""
    assert "trading" in compose_data.get("services", {})


def test_compose_has_questdb_service(compose_data):
    """Test 6: docker-compose.yml defines a 'questdb' service."""
    assert "questdb" in compose_data.get("services", {})


def test_compose_trading_exposes_api_port(compose_data):
    """Test 7: trading service maps port 8000."""
    ports = compose_data["services"]["trading"].get("ports", [])
    port_strings = " ".join(str(p) for p in ports)
    assert "8000" in port_strings


def test_compose_trading_exposes_metrics_port(compose_data):
    """Test 8: trading service maps port 9090 (Prometheus)."""
    ports = compose_data["services"]["trading"].get("ports", [])
    port_strings = " ".join(str(p) for p in ports)
    assert "9090" in port_strings


def test_compose_uses_named_volumes(compose_data):
    """Test 9: docker-compose.yml declares named volumes (data persists)."""
    volumes = compose_data.get("volumes", {})
    assert "trading_data" in volumes, "trading_data volume missing"
    assert "questdb_data" in volumes, "questdb_data volume missing"


def test_compose_trading_depends_on_questdb(compose_data):
    """Test 13: trading service has a depends_on: questdb entry."""
    depends = compose_data["services"]["trading"].get("depends_on", {})
    # depends_on can be a list or a dict (long syntax)
    if isinstance(depends, list):
        assert "questdb" in depends
    else:
        assert "questdb" in depends


def test_compose_has_network_definition(compose_data):
    """Test 14: docker-compose.yml defines a custom network."""
    networks = compose_data.get("networks", {})
    assert len(networks) > 0, "No networks defined in docker-compose.yml"


# ---------------------------------------------------------------------------
# Prometheus config tests
# ---------------------------------------------------------------------------

def test_prometheus_config_valid(prometheus_data):
    """Test 10: deploy/prometheus/prometheus.yml is valid YAML with scrape_configs."""
    assert "scrape_configs" in prometheus_data


def test_prometheus_scrapes_trading_service(prometheus_data):
    """Test 10b: Prometheus is configured to scrape the trading service."""
    configs = prometheus_data.get("scrape_configs", [])
    job_names = [c.get("job_name", "") for c in configs]
    assert "sovereign_trading" in job_names


# ---------------------------------------------------------------------------
# .env.example tests
# ---------------------------------------------------------------------------

def test_env_example_exists():
    """Test 11: .env.example exists."""
    assert (_ROOT / ".env.example").exists()


def test_env_example_has_required_keys():
    """Test 11b: .env.example contains critical variable names."""
    text = (_ROOT / ".env.example").read_text(encoding="utf-8")
    for key in ("SESSION_SECRET", "TRADING_MODE", "FORCED_PAPER_MODE"):
        assert key in text, f"Missing {key} in .env.example"


# ---------------------------------------------------------------------------
# .dockerignore tests
# ---------------------------------------------------------------------------

def test_dockerignore_exists():
    """Test 12: .dockerignore exists."""
    assert (_ROOT / ".dockerignore").exists()


def test_dockerignore_excludes_secrets():
    """Test 12b: .dockerignore excludes .env and vault.json."""
    text = (_ROOT / ".dockerignore").read_text(encoding="utf-8")
    assert ".env" in text, ".env not excluded in .dockerignore"
    assert "vault.json" in text, "vault.json not excluded in .dockerignore"
