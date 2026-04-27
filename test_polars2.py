import polars as pl # type: ignore
import pandas as pd # type: ignore

df_pd = pd.DataFrame({"low": [5, 2, 3, 1, 4]})
df_pl = pl.DataFrame({"low": [5, 2, 3, 1, 4]})

try:
    print("pd idxmin:", df_pd['low'].idxmin())
    print("pl arg_min:", df_pl['low'].arg_min())
except Exception as e:
    print("err:", e)

try:
    print("pd quantile:", df_pd['low'].quantile(0.75))
    print("pl quantile:", df_pl['low'].quantile(0.75))
except Exception as e:
    print("err:", e)
