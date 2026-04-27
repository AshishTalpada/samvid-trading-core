
import asyncio
import logging
import sys
from pathlib import Path

# Setup paths
sys.path.append(str(Path(__file__).parent.parent / "src"))

from mind_bridge import MindBridge
from mind_architect import MindArchitect
from mind_macros import MindMacros

async def run_resilience_test():
    print("--- 🛡️ SYSTEM RESILIENCE HARDENING TEST ---")
    bridge = MindBridge()
    architect = MindArchitect(bridge)
    
    # 1. Test Unsigned Tool Block
    print("\n[1/3] Testing Security Guardrail (Unsigned Tool)...")
    bridge.register_tool("forbidden_tool", lambda: {"status": "I am a hazard"})
    
    # This should be blocked by MindMacros check in call_tool
    result = await bridge.call_tool("forbidden_tool")
    if result.get("error") == "Unauthorized: Tool not in Signed Allowlist":
        print("✅ SUCCESS: Unsigned tool blocked by security gate.")
    else:
        print(f"❌ FAIL: Unsigned tool was allowed! Result: {result}")

    # 2. Test Precision Suture (Collision Guard)
    print("\n[2/3] Testing Suture Precision (Collision Guard)...")
    # Create a temp file with multiple instances of a string
    test_file = Path("scratch/collision_test.py")
    test_file.write_text("print('hello')\nprint('hello')\n")
    
    # Attempt to replace print('hello')
    result = await architect._tool_heal_code(str(test_file), "print('hello')", "print('world')")
    
    if "Collision" in result.get("error", ""):
        print("✅ SUCCESS: Architect blocked collision-risk replacement.")
    else:
        print(f"❌ FAIL: Architect allowed a risky multi-line replacement! Result: {result}")

    # 3. Test Signed Tool Execution
    print("\n[3/3] Testing Authorized Flow...")
    bridge.register_tool("check_syntax", lambda: {"status": "OK"})
    result = await bridge.call_tool("check_syntax")
    if result.get("status") == "OK":
        print("✅ SUCCESS: Authorized tool (check_syntax) passed.")
    else:
        print(f"❌ FAIL: Authorized tool was blocked! {result}")

    print("\n--- RESILIENCE TEST COMPLETE ---")

if __name__ == "__main__":
    asyncio.run(run_resilience_test())
