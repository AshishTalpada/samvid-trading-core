import yfinance as yf
import asyncio

async def test_news():
    print("Testing yfinance news fetch for SPY...")
    ticker = yf.Ticker("SPY")
    news = ticker.news
    if news:
        print(f"Success! Found {len(news)} news items.")
        for item in news[:3]:
            print(f"- {item.get('title')}")
    else:
        print("Failure: No news items found via yfinance.")

    print("\nTesting Finnhub fetch (if key provided)...")
    # We won't test finnhub here to avoid exposing the key in console if not needed
    # but we've already enabled it in .env

if __name__ == "__main__":
    asyncio.run(test_news())
