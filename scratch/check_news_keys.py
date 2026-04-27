import yfinance as yf
import json

ticker = yf.Ticker("SPY")
news = ticker.news
if news:
    print(json.dumps(news[0], indent=2))
else:
    print("No news")
