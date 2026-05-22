from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

OPT_NON_STR_KEYS = 1
OPT_SERIALIZE_NUMPY = 2


def _default(value: Any) -> Any:
    try:
        import numpy as np

        if isinstance(value, np.generic):
            return value.item()
        if isinstance(value, np.ndarray):
            return value.tolist()
    except Exception:
        pass

    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, set):
        return list(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def dumps(obj: Any, *, option: int = 0) -> bytes:
    """Small orjson-compatible fallback for environments where the DLL is blocked."""
    return json.dumps(
        obj,
        default=_default,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")


def loads(data: bytes | bytearray | str) -> Any:
    if isinstance(data, (bytes, bytearray)):
        data = data.decode("utf-8")
    return json.loads(data)
