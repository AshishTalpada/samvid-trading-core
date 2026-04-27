import websockets
import inspect

print(f"Websockets version: {websockets.__version__}")
try:
    print(f"Connect signature: {inspect.signature(websockets.connect)}")
except Exception as e:
    print(f"Error getting signature: {e}")
