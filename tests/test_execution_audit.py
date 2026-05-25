import json

from execution_audit import ExecutionAuditLog


def test_execution_audit_is_hash_chained(tmp_path) -> None:
    path = tmp_path / "audit.jsonl"
    audit = ExecutionAuditLog(path)

    first = audit.append(
        event="ORDER_INTENT",
        symbol="spy",
        side="buy",
        quantity=1,
        order_type="LMT",
        details={"price": 500.0},
    )
    second = audit.append(
        event="ORDER_INTENT",
        symbol="qqq",
        side="sell",
        quantity=2,
        order_type="MKT",
        details={"urgency": "HIGH"},
    )

    records = [json.loads(line) for line in path.read_text().splitlines()]
    assert records[0]["previous_hash"] == "GENESIS"
    assert records[1]["previous_hash"] == first["hash"]
    assert records[1]["hash"] == second["hash"]
    assert records[0]["symbol"] == "SPY"
    assert records[1]["side"] == "SELL"
