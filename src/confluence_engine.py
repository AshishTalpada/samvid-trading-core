"""Multi-timeframe confluence / alignment engine.

The confluence engine answers one question before a trade is allowed:
"Do higher timeframes agree with the direction and timeframe of this pattern?"

It fetches OHLCV for the primary pattern timeframe plus the next higher
timeframes, computes trend alignment using the MultiTimeframeAligner, and
returns a pass/fail decision with a confluence score.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from agent_a import MultiTimeframeAligner

logger = logging.getLogger(__name__)


# Ordered hierarchy of timeframes from fastest to slowest.
TIMEFRAME_HIERARCHY = ["1m", "5m", "15m", "1h", "4h", "1d"]


def _higher_timeframes(primary: str) -> list[str]:
    """Return the primary timeframe plus the next two slower timeframes."""
    try:
        idx = TIMEFRAME_HIERARCHY.index(primary)
    except ValueError:
        return [primary]
    return TIMEFRAME_HIERARCHY[idx : idx + 3]


@dataclass
class ConfluenceResult:
    """Result of a multi-timeframe confluence check."""

    score: float  # 0.0 to 1.0
    passed: bool
    reasons: list[str]
    primary_timeframe: str
    checked_timeframes: list[str]
    alignment: dict[str, float]


class ConfluenceEngine:
    """Check whether higher timeframes align with a trade direction."""

    def __init__(
        self,
        min_score: float = 0.70,
        min_timeframes: int = 2,
        aligner: MultiTimeframeAligner | None = None,
    ) -> None:
        self.min_score = min_score
        self.min_timeframes = min_timeframes
        self.aligner = aligner or MultiTimeframeAligner()

    async def evaluate(
        self,
        symbol: str,
        direction: str,
        primary_timeframe: str,
        fetch_ohlcv: Any,
        min_score: float | None = None,
    ) -> ConfluenceResult:
        """Evaluate confluence for a symbol/direction.

        Args:
            symbol: Ticker symbol
            direction: "LONG" or "SHORT"
            primary_timeframe: The timeframe the pattern was detected on
            fetch_ohlcv: async callable(symbol, timeframe) -> DataFrame
        """
        reasons: list[str] = []
        checked: list[str] = []
        alignment: dict[str, float] = {}
        direction = str(direction).upper()

        timeframes = _higher_timeframes(primary_timeframe)
        bullish_votes = 0
        bearish_votes = 0
        total_votes = 0

        for tf in timeframes:
            try:
                df = await fetch_ohlcv(symbol, tf)
                if df is None or isinstance(df, str) or len(df) < 20:
                    reasons.append(f"{tf}: insufficient data")
                    continue

                checked.append(tf)
                score = self.aligner.check_alignment(symbol, [(tf, df)])
                alignment[tf] = round(score, 3)

                # Determine directional vote from the single timeframe.
                if "close" in df.columns:
                    current = float(df["close"].tail(1).item())
                    ma_window = min(20, len(df))
                    ma = float(df["close"].rolling_mean(window_size=ma_window).tail(1).item())
                    if current > ma:
                        bullish_votes += 1
                        vote = "bullish"
                    elif current < ma:
                        bearish_votes += 1
                        vote = "bearish"
                    else:
                        vote = "neutral"
                else:
                    vote = "unknown"

                logger.debug(
                    "ConfluenceEngine [%s] %s: score=%.2f vote=%s",
                    symbol,
                    tf,
                    score,
                    vote,
                )
            except Exception as exc:
                logger.debug("ConfluenceEngine [%s] %s failed: %s", symbol, tf, exc)
                reasons.append(f"{tf}: fetch error")

        total_votes = bullish_votes + bearish_votes
        if total_votes == 0:
            reasons.append("No higher-timeframe directional votes available")
            return ConfluenceResult(
                score=0.0,
                passed=False,
                reasons=reasons,
                primary_timeframe=primary_timeframe,
                checked_timeframes=checked,
                alignment=alignment,
            )

        if direction == "LONG":
            agreement = bullish_votes / total_votes
            if bearish_votes > 0:
                reasons.append(
                    f"{bearish_votes} higher timeframe(s) voting bearish against LONG"
                )
        elif direction == "SHORT":
            agreement = bearish_votes / total_votes
            if bullish_votes > 0:
                reasons.append(
                    f"{bullish_votes} higher timeframe(s) voting bullish against SHORT"
                )
        else:
            agreement = max(bullish_votes, bearish_votes) / total_votes
            reasons.append(f"Unknown direction {direction}; using pure agreement")

        # Blend with the raw alignment score from the per-timeframe scores.
        if checked:
            raw_alignment = sum(alignment.values()) / len(alignment)
        else:
            raw_alignment = 0.0

        score = 0.6 * agreement + 0.4 * raw_alignment
        threshold = min_score if min_score is not None else self.min_score
        passed = score >= threshold and len(checked) >= self.min_timeframes

        if len(checked) < self.min_timeframes:
            reasons.append(
                f"Only {len(checked)} timeframe(s) available; need {self.min_timeframes}"
            )
        if not passed and not any(r.startswith("Higher") or r.startswith("Only") for r in reasons):
            reasons.append(f"Confluence score {score:.2f} < minimum {threshold}")
        if passed:
            reasons.append(f"Confluence score {score:.2f} >= {threshold}")

        return ConfluenceResult(
            score=round(score, 3),
            passed=passed,
            reasons=reasons,
            primary_timeframe=primary_timeframe,
            checked_timeframes=checked,
            alignment=alignment,
        )
