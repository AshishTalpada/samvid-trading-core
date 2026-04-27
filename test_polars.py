import polars as pl # type: ignore
import pandas as pd # type: ignore

# Pandas
df_pd = pd.DataFrame({"close": [1, 2, 3, 4, 5], "high": [2, 3, 4, 5, 6], "volume": [10, 20, 30, 40, 50]})
# Polars
df_pl = pl.DataFrame({"close": [1, 2, 3, 4, 5], "high": [2, 3, 4, 5, 6], "volume": [10, 20, 30, 40, 50]})

# 1. iloc[-20]
try:
    print("pd iloc:", df_pd['close'].iloc[-2])
    print("pl [-2]:", df_pl['close'][-2])
except Exception as e:
    print("pl [-2] err:", e)

# 2. iloc[-10:] mean
try:
    print("pd mean:", df_pd['volume'].iloc[-3:].mean())
    print("pl mean:", df_pl['volume'][-3:].mean())
except Exception as e:
    print("pl mean err:", e)

# 3. max, min
try:
    print("pd max:", df_pd.iloc[-3:]['high'].max())
    print("pl max:", df_pl[-3:]['high'].max())
except Exception as e:
    print("pl max err:", e)
    
# 4. rolling mean
try:
    print("pd rolling:", df_pd['close'].rolling(2).mean().iloc[-1])
    print("pl rolling:", df_pl['close'].rolling_mean(window_size=2)[-1])
except Exception as e:
    print("pl rolling err:", e)
