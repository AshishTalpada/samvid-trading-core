import asyncio
import websockets
import json
import sys
import hmac, hashlib
import time

async def test_ws():
    # 1. Get the secret
    try:
        from vault import Vault
        secret = Vault.get("API_SERVER_KEY")
    except:
        secret = "_4##VyFGjF(WdKPjDxcg3aNn!6)IHdnTIsCd3ew)*E@kDxpc"

    # 2. Generate HMAC
    ts = int(time.time()) // 30
    msg = str(ts).encode()
    token = hmac.new(secret.encode(), msg, hashlib.sha256).hexdigest()

    uri = f"ws://127.0.0.1:8000/ws?token={token}"
    print(f"Connecting to {uri}")
    
    try:
        async with websockets.connect(uri) as websocket:
            print("Connected! Waiting for first message (full_state)...")
            msg = await websocket.recv()
            data = json.loads(msg)
            print(f"Received type: {data.get('type')}")
            
            if data.get('type') == 'full_state':
                print(f"Keys in data: {list(data.get('data', {}).keys())}")
                if 'error' in data.get('data', {}):
                    print(f"ERROR DETAILS: {data.get('data', {}).get('error')}")
                brain = data.get('data', {}).get('brain', {})
                print(f"Agents in brain: {list(brain.get('agents', {}).keys())}")
            
            print("Waiting for next message...")
            msg2 = await websocket.recv()
            data2 = json.loads(msg2)
            print(f"Received type: {data2.get('type')}")
            
            # Wait for one more
            msg3 = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            data3 = json.loads(msg3)
            print(f"Received type: {data3.get('type')}")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_ws())
