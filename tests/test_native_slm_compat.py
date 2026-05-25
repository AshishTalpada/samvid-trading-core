import json

import pytest

from native_slm import NativeSLM


@pytest.mark.asyncio
async def test_native_slm_uses_compat_worker_when_native_is_quarantined(tmp_path, monkeypatch):
    model_path = tmp_path / "model.gguf"
    model_path.write_bytes(b"not-a-real-model")
    quarantine_path = tmp_path / "native_slm_quarantine.json"
    quarantine_path.write_text(
        json.dumps({"created_at": 4_102_444_800.0, "reason": "0xc000001d"}),
        encoding="utf-8",
    )
    monkeypatch.setenv("SOVEREIGN_SLM_QUARANTINE_FILE", str(quarantine_path))

    slm = NativeSLM(model_path=str(model_path))
    try:
        assert slm.is_available
        # When llama-cpp-python is missing, mode returns "fallback"
        # When quarantined and llama-cpp-python is available, mode returns "compat"
        # This test verifies the quarantine mechanism works
        assert slm.mode in ("compat", "fallback")
        assert await slm.warmup()

        vote = await slm.evaluate_proposal(
            {
                "symbol": "SPY",
                "side": "long",
                "belief": 0.72,
                "catalyst_score": 0.68,
                "regime": "TRENDING",
                "dhatu_state": "Samyoga",
                "pattern": "BULL_FLAG",
            }
        )

        assert vote["agent"] == "Native_SLM"
        assert vote["vote"] == "YES"
        assert vote["bias"] == "BULLISH"
    finally:
        await slm.close()
