import asyncio
from src.questdb_adapter import QuestDBAdapter

async def test():
    q = QuestDBAdapter(enabled=True)
    df = await q.fetch_ohlcv_pandas('GOOGL')
    print("DataFrame snippet:")
    print(df)
    
asyncio.run(test())
