import asyncio
import logging
import os
import sys
import traceback

# Add project root to sys.path
sys.path.append(os.getcwd())

from src.brain import TradingBrain

# Set up logging for the test
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("VERIFY_SETO")


async def main() -> None:
    logger.info("--- Samvid v1.0-beta-beta Integration Verification ---")

    # Mock dependencies
    class MockDB:
        pass

    class MockIBKR:
        pass

    class MockMT5:
        pass

    db = MockDB()
    ibkr = MockIBKR()
    mt5 = MockMT5()

    logger.info("1. Instantiating TradingBrain...")
    try:
        brain = TradingBrain(db_conn=db, ibkr_client=ibkr, mt5_client=mt5, mode="paper")
        logger.info("SUCCESS: TradingBrain instantiated.")

        # Check components
        assert hasattr(brain, "mind_ghost"), "Missing Agent J (Ghost Monitor)"
        assert hasattr(brain, "mind_bridge"), "Missing MindBridge"
        assert hasattr(brain, "mind_architect"), "Missing Agent G (Architect)"
        assert hasattr(brain, "mind_ultrathink"), "Missing Ultrathink"

        logger.info("2. Checking MindBridge Tool Registration...")
        # Tools are registered when agents are instantiated
        # MindSystem (Agent I) should be in brain.mind_system
        tools = brain.mind_bridge.tools.keys()
        logger.info(f"Registered Tools: {list(tools)}")

        required_tools = ["heal_code", "reboot_service", "pause_and_reason"]
        for tool in required_tools:
            assert tool in tools, f"Missing tool: {tool}"

        logger.info("SUCCESS: All 'Infinity Matrix' tools registered.")

        logger.info("3. Snapshot-Freezing Preflight Check...")
        state = {"test": "state", "v": "7.0"}
        freeze_success = brain.session_restorer.freeze_state(state)
        assert freeze_success, "SessionRestorer: Freeze failed."

        thaw_state = brain.session_restorer.thaw_state()
        assert thaw_state == state, (
            f"SessionRestorer: State mismatch after thaw! Expected {state}, got {thaw_state}"
        )
        logger.info("SUCCESS: SessionRestorer (Quantum Thaw) verified.")

        logger.info("4. Ghost Monitor Audit Check...")
        # Manually pulse the ghost monitor to ensure no crash
        await brain.mind_ghost.update_heartbeat("IBKR")
        logger.info("SUCCESS: Ghost Monitor heartbeat verified.")

        logger.info("--- ALL Samvid v1.0-beta-beta INTEGRATIONS VERIFIED ---")

    except Exception as e:
        logger.error(f"VERIFICATION FAILED: {e}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
