import asyncio
from ib_insync import IB

async def test_connect():
    ib = IB()
    ports = [7497, 4002]
    hosts = ["localhost", "127.0.0.1", "::1"]
    
    for port in ports:
        for host in hosts:
            for client_id in range(100, 110):
                print(f"Trying {host}:{port} with ID {client_id}...")
                try:
                    await asyncio.wait_for(ib.connectAsync(host, port, clientId=client_id), timeout=3.0)
                    print(f"SUCCESS! Connected to {host}:{port} with ID {client_id}")
                    ib.disconnect()
                    return
                except Exception as e:
                    print(f"Failed: {e}")
                    try:
                        ib.disconnect()
                    except:
                        pass
    print("All attempts failed.")

if __name__ == "__main__":
    asyncio.run(test_connect())
