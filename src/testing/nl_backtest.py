from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class StrategySpec:
    side: str
    indicator: str
    operator: str
    threshold: float
    hold_bars: int = 10


class NaturalLanguageBacktester:
    """Parse a constrained strategy sentence and run a cost-aware backtest.

    This intentionally supports a small declarative grammar. Arbitrary generated
    Python is never executed inside the trading process.
    """

    _SMA = re.compile(
        r"\b(?P<side>buy|long|sell|short)\b.*?"
        r"(?P<cross>cross(?:es)?\s+)?(?P<operator>above|below).*?"
        r"(?P<period>\d{1,4})\s*(?:sma|moving average)\b",
        re.IGNORECASE,
    )
    _RSI = re.compile(
        r"\b(?P<side>buy|long|sell|short)\b.*?rsi.*?"
        r"(?P<operator>above|over|below|under)\s*(?P<threshold>\d{1,3}(?:\.\d+)?)",
        re.IGNORECASE,
    )
    _HOLD = re.compile(r"\bhold(?:\s+for)?\s+(?P<bars>\d{1,4})\s+bars?\b", re.IGNORECASE)

    def __init__(self, llm_bridge: Any = None, round_trip_cost_bps: float = 2.0):
        self.llm = llm_bridge
        self.round_trip_cost_bps = max(0.0, float(round_trip_cost_bps))

    @staticmethod
    def _normalize_side(value: str) -> str:
        return "LONG" if value.lower() in {"buy", "long"} else "SHORT"

    def parse_query(self, nl_query: str) -> StrategySpec:
        query = " ".join(str(nl_query).split())
        if not query:
            raise ValueError("strategy query is empty")

        hold_match = self._HOLD.search(query)
        hold_bars = int(hold_match.group("bars")) if hold_match else 10
        if not 1 <= hold_bars <= 10_000:
            raise ValueError("hold period must be between 1 and 10000 bars")

        sma_match = self._SMA.search(query)
        if sma_match:
            period = int(sma_match.group("period"))
            if period < 2:
                raise ValueError("SMA period must be at least 2")
            operator = sma_match.group("operator").lower()
            if sma_match.group("cross"):
                operator = f"cross_{operator}"
            return StrategySpec(
                side=self._normalize_side(sma_match.group("side")),
                indicator="SMA",
                operator=operator,
                threshold=float(period),
                hold_bars=hold_bars,
            )

        rsi_match = self._RSI.search(query)
        if rsi_match:
            threshold = float(rsi_match.group("threshold"))
            if not 0.0 <= threshold <= 100.0:
                raise ValueError("RSI threshold must be between 0 and 100")
            operator = rsi_match.group("operator").lower()
            operator = "above" if operator in {"above", "over"} else "below"
            return StrategySpec(
                side=self._normalize_side(rsi_match.group("side")),
                indicator="RSI",
                operator=operator,
                threshold=threshold,
                hold_bars=hold_bars,
            )

        raise ValueError(
            "unsupported strategy; use BUY/SELL with SMA above/below/cross or RSI above/below"
        )

    def translate_to_code(self, nl_query: str) -> str:
        """Return a canonical description, not executable generated code."""
        spec = self.parse_query(nl_query)
        return (
            f"{spec.side} when {spec.indicator} {spec.operator} {spec.threshold:g}; "
            f"hold {spec.hold_bars} bars"
        )

    @staticmethod
    def _sma(values: np.ndarray, period: int) -> np.ndarray:
        result = np.full(len(values), np.nan, dtype=float)
        if len(values) < period:
            return result
        cumulative = np.cumsum(np.insert(values, 0, 0.0))
        result[period - 1 :] = (cumulative[period:] - cumulative[:-period]) / period
        return result

    @staticmethod
    def _rsi(values: np.ndarray, period: int = 14) -> np.ndarray:
        result = np.full(len(values), np.nan, dtype=float)
        if len(values) <= period:
            return result
        deltas = np.diff(values)
        gains = np.maximum(deltas, 0.0)
        losses = np.maximum(-deltas, 0.0)
        avg_gain = float(np.mean(gains[:period]))
        avg_loss = float(np.mean(losses[:period]))
        for index in range(period, len(values)):
            if index > period:
                avg_gain = (avg_gain * (period - 1) + gains[index - 1]) / period
                avg_loss = (avg_loss * (period - 1) + losses[index - 1]) / period
            if avg_loss == 0.0:
                result[index] = 100.0 if avg_gain > 0.0 else 50.0
            else:
                result[index] = 100.0 - 100.0 / (1.0 + avg_gain / avg_loss)
        return result

    def _signals(self, spec: StrategySpec, prices: np.ndarray) -> np.ndarray:
        if spec.indicator == "SMA":
            indicator = self._sma(prices, int(spec.threshold))
        else:
            indicator = self._rsi(prices)

        if spec.operator == "above":
            return prices > indicator if spec.indicator == "SMA" else indicator > spec.threshold
        if spec.operator == "below":
            return prices < indicator if spec.indicator == "SMA" else indicator < spec.threshold
        if spec.operator == "cross_above":
            return (prices > indicator) & (np.roll(prices, 1) <= np.roll(indicator, 1))
        if spec.operator == "cross_below":
            return (prices < indicator) & (np.roll(prices, 1) >= np.roll(indicator, 1))
        raise ValueError(f"unsupported operator: {spec.operator}")

    def run_backtest(self, nl_query: str, data: dict[str, Any]) -> dict[str, float | int | str]:
        spec = self.parse_query(nl_query)
        raw_prices = data.get("close", data.get("prices"))
        if raw_prices is None:
            raise ValueError("data must contain 'close' or 'prices'")
        prices = np.asarray(raw_prices, dtype=float)
        opens = np.asarray(data.get("open", prices), dtype=float)
        if prices.ndim != 1 or len(prices) != len(opens):
            raise ValueError("open and close prices must be one-dimensional and equal length")
        if len(prices) < max(20, int(spec.threshold) if spec.indicator == "SMA" else 15) + 2:
            raise ValueError("insufficient bars for requested strategy")
        if not np.all(np.isfinite(prices)) or not np.all(np.isfinite(opens)):
            raise ValueError("price data contains non-finite values")
        if np.any(prices <= 0.0) or np.any(opens <= 0.0):
            raise ValueError("price data must be positive")

        signals = self._signals(spec, prices)
        signals[0] = False
        direction = 1.0 if spec.side == "LONG" else -1.0
        cost = self.round_trip_cost_bps / 10_000.0
        returns: list[float] = []
        index = 0
        last_entry = len(prices) - spec.hold_bars - 2
        while index <= last_entry:
            if not bool(signals[index]):
                index += 1
                continue
            entry_index = index + 1
            exit_index = entry_index + spec.hold_bars
            gross_return = direction * (prices[exit_index] - opens[entry_index]) / opens[entry_index]
            returns.append(float(gross_return - cost))
            index = exit_index + 1

        values = np.asarray(returns, dtype=float)
        if len(values) == 0:
            return {
                "strategy": self.translate_to_code(nl_query),
                "signals": int(np.count_nonzero(signals)),
                "trades": 0,
                "win_rate": 0.0,
                "avg_return": 0.0,
                "total_return": 0.0,
                "sharpe_per_trade": 0.0,
                "max_drawdown": 0.0,
            }

        equity = np.concatenate(([1.0], np.cumprod(1.0 + values)))
        peaks = np.maximum.accumulate(equity)
        std = float(np.std(values, ddof=1)) if len(values) > 1 else 0.0
        result: dict[str, float | int | str] = {
            "strategy": self.translate_to_code(nl_query),
            "signals": int(np.count_nonzero(signals)),
            "trades": int(len(values)),
            "win_rate": round(float(np.mean(values > 0.0)), 4),
            "avg_return": round(float(np.mean(values)), 6),
            "total_return": round(float(equity[-1] - 1.0), 6),
            "sharpe_per_trade": round(float(np.mean(values) / std), 4) if std else 0.0,
            "max_drawdown": round(float(np.min((equity - peaks) / peaks)), 6),
        }
        logger.info(
            "NL backtest: %s trades=%d win_rate=%.1f%% total_return=%.2f%%",
            result["strategy"],
            result["trades"],
            float(result["win_rate"]) * 100.0,
            float(result["total_return"]) * 100.0,
        )
        return result
