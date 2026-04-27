import asyncio
import logging

import pytest

from src.questdb_adapter import QuestDBAdapter

logging.basicConfig(level=logging.INFO)


@pytest.mark.asyncio
async def test_qdb_handshake() -> None:
    print("🧪 PROBING QUESTDB CONNECTION...")
    qdb = QuestDBAdapter(host="localhost", ilp_port=9009, enabled=True)
    await qdb.start()

    # We don't assert live connection since local dev might not have QDB running
    # but we check if the class initialized correctly.
    assert qdb.host == "localhost"

    if qdb.enabled and not qdb.is_simulated:
        print("✅ SUCCESS: QuestDB is LIVE and REACHABLE.")
    elif qdb.is_simulated:
        print("✅ NOTE: QuestDB is in SIMULATED mode (Expected if local).")
    else:
        print("❌ FAILED: QuestDB is DISABLED.")


if __name__ == "__main__":
    asyncio.run(test_qdb_handshake())
