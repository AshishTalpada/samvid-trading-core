import logging
from unittest.mock import patch

from brain_health import HealthChecker


def test_pre_market_health_failure_logging_is_rate_limited(caplog) -> None:
    checker = HealthChecker()

    with caplog.at_level(logging.DEBUG, logger="brain_health"):
        checker._log_pre_market_health_failure("Broker IBKR not connected")
        checker._log_pre_market_health_failure("Broker IBKR not connected")

    warnings = [record for record in caplog.records if record.levelno == logging.WARNING]
    debug = [record for record in caplog.records if record.levelno == logging.DEBUG]
    assert len(warnings) == 1
    assert len(debug) == 1
    assert "EXECUTION HEALTH CHECK BLOCKED" in warnings[0].message


def test_pre_market_health_failure_warning_repeats_after_default_interval(caplog) -> None:
    checker = HealthChecker()

    with (
        patch("brain_health.time.monotonic", side_effect=[100.0, 101.0, 1900.0]),
        caplog.at_level(logging.DEBUG, logger="brain_health"),
    ):
        checker._log_pre_market_health_failure("Broker IBKR not connected")
        checker._log_pre_market_health_failure("Broker IBKR not connected")
        checker._log_pre_market_health_failure("Broker IBKR not connected")

    warnings = [record for record in caplog.records if record.levelno == logging.WARNING]
    debug = [record for record in caplog.records if record.levelno == logging.DEBUG]
    assert len(warnings) == 2
    assert len(debug) == 1
