from __future__ import annotations

from typing import Any

import pandas as pd
import polars as pl


def _plain_series(series: pd.Series) -> pd.Series:
    if pd.api.types.is_datetime64_any_dtype(series):
        return pd.to_datetime(series, errors="coerce")
    if pd.api.types.is_bool_dtype(series):
        return series.fillna(False).astype(bool)
    if pd.api.types.is_numeric_dtype(series):
        return pd.to_numeric(series, errors="coerce").astype(float)
    return series.astype(object).where(pd.notna(series), None)


def safe_polars_from_pandas(df: pd.DataFrame, *args: Any, **kwargs: Any) -> pl.DataFrame:
    """Convert pandas to Polars without requiring pyarrow for nullable extension dtypes."""
    plain = df.copy()
    plain.columns = [str(col) for col in plain.columns]
    for col in plain.columns:
        plain[col] = _plain_series(plain[col])
    try:
        return pl.from_pandas(plain, *args, **kwargs)
    except ImportError:
        return pl.DataFrame(plain.to_dict(orient="list"))
