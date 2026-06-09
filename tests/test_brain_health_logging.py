import logging

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
