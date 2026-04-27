import asyncio
import logging
import sys
import os

# Ensure project root and src are in path
_here = os.path.dirname(__file__)
_root = os.path.abspath(os.path.join(_here, ".."))
_src = os.path.join(_root, "src")
if _root not in sys.path: sys.path.append(_root)
if _src not in sys.path: sys.path.append(_src)

from mind_bridge import MindBridge
from mind_system import MindSystem
from mind_macros import MindMacros
from vault import Vault

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_security():
    bridge = MindBridge()
    system = MindSystem(bridge)
    
    # 1. Test GAP-64: Double Handshake for heal_code
    print("\n--- Testing GAP-64: Sensitive Tool Gate ---")
    
    # Attempt without justification
    res = await bridge.call_tool("heal_code", code="print('bad')")
    print(f"Result (No Justification): {res}")
    
    # Attempt with weak justification
    res = await bridge.call_tool("heal_code", code="print('bad')", justification="fix")
    print(f"Result (Weak Justification): {res}")

    # Attempt with strong justification
    # First, we need to register heal_code since it's usually registered by MindArchitect
    bridge.register_tool("heal_code", lambda code, justification: {"success": True, "msg": "Healed."})
    res = await bridge.call_tool("heal_code", code="print('good')", justification="Fixing critical logic error in MindMath.")
    print(f"Result (Strong Justification): {res}")

    # 2. Test GAP-59: Binary Trust Scent
    print("\n--- Testing GAP-59: Binary Trust Scent ---")
    
    # Search for something in a trusted zone (Program Files handles naturally)
    res = await system._tool_find_executable("notepad") # Note: find_executable prepends .exe
    print(f"Result (Standard Binary): {res}")

    # Mock a suspicious path by manually setting Vault
    Vault.set("MALICIOUS_PATH", "C:\\Users\\Public\\malicious.exe")
    res = await system._tool_find_executable("malicious")
    print(f"Result (Suspicious Zone): {res}")

if __name__ == "__main__":
    asyncio.run(test_security())
