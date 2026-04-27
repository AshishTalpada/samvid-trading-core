import asyncio
import websockets
import json

async def test_ws():
    uri = "ws://127.0.0.1:8000/ws"
    try:
        async with websockets.connect(uri) as websocket:
            print("Connected!")
            greeting = await websocket.recv()
            print(f"Received: {greeting[:100]}...")
    except Exception as e:
        print(f"Failed to connect: {e}")

asyncio.run(test_ws())
