import pytest

from backend_reliability_probe import run_backend_reliability_probe


@pytest.mark.asyncio
async def test_backend_reliability_probe_passes() -> None:
    report = await run_backend_reliability_probe()

    assert report.passed
    assert {check.name for check in report.checks} == {
        "synthetic_tick_batcher",
        "entry_data_freshness_veto",
        "order_throttle_and_notional_veto",
        "dead_letter_queue_escalates_to_halt",
    }
