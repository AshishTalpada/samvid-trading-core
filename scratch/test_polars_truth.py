import polars as pl
import numpy as np

df = pl.DataFrame({
    "high": [10.1, 10.2, 10.3],
    "low": [9.9, 9.8, 9.7],
    "close": [10.0, 10.1, 10.2]
})

tr = pl.max_horizontal(
    (df["high"] - df["low"]).abs(),
    (df["high"] - df["close"].shift(1)).abs(),
    (df["low"] - df["close"].shift(1)).abs()
)

print(f"Type of tr: {type(tr)}")
_m_atr = tr.tail(20).mean()
print(f"Type of _m_atr: {type(_m_atr)}")

try:
    if _m_atr is not None and _m_atr != 0:
        print("Logic 1 works")
except Exception as e:
    print(f"Logic 1 failed: {e}")

# Try with Expressions
tr_expr = pl.max_horizontal(
    (pl.col("high") - pl.col("low")).abs(),
    (pl.col("high") - pl.col("close").shift(1)).abs(),
    (pl.col("low") - pl.col("close").shift(1)).abs()
)
print(f"Type of tr_expr: {type(tr_expr)}")
_m_atr_expr = tr_expr.mean()
print(f"Type of _m_atr_expr: {type(_m_atr_expr)}")

try:
    if _m_atr_expr is not None and _m_atr_expr != 0:
        print("Logic 2 works")
except Exception as e:
    print(f"Logic 2 failed: {e}")
