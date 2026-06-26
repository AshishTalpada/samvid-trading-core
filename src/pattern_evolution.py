"""
src/pattern_evolution.py — Adaptive Pattern Evolution Engine

Mines new pattern definitions from price data using a genetic algorithm,
then registers them as first-class patterns that the main scanner can
execute. This lets the system auto-invent and adapt its pattern catalog.

Evolved patterns are persisted to disk and reloaded on startup so learned
edge survives restarts.
"""
from __future__ import annotations

import json
import logging
import os
import random
import time
from pathlib import Path
from typing import Any

import numpy as np
import polars as pl

from agent_a import PatternResult
from discovery_engine import AlphaDiscoveryEngine

logger = logging.getLogger(__name__)

DEFAULT_STORE = Path("data/evolved_patterns.json")


def _atr(prices: np.ndarray, n: int = 14) -> float:
    """Simple ATR proxy from close prices using log ranges."""
    if len(prices) < n + 1:
        return 0.5
    returns = np.diff(np.log(prices[-(n + 1) :] + 1e-9))
    return float(np.mean(np.abs(returns)) * prices[-1])


def _directional_target(entry: float, stop: float, rr: float = 2.0) -> float:
    """Return target price for a given R:R."""
    risk = abs(entry - stop)
    if entry > stop:
        return entry + risk * rr
    return entry - risk * rr


class EvolvedPatternRegistry:
    """Persist and reload evolved alphas across sessions."""

    def __init__(self, path: Path | str | None = None) -> None:
        self.path = Path(path) if path else DEFAULT_STORE
        self._alphas: list[dict[str, Any]] = []
        self._last_save = 0.0

    def load(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._alphas = data if isinstance(data, list) else []
            logger.info("[EVOLUTION] Loaded %d evolved alphas from %s", len(self._alphas), self.path)
        except Exception as e:
            logger.warning("[EVOLUTION] Failed to load registry: %s", e)
            self._alphas = []
        return list(self._alphas)

    def save(self, alphas: list[dict[str, Any]]) -> None:
        self._alphas = list(alphas)
        now = time.time()
        if now - self._last_save < 5.0:
            return  # throttle disk writes
        self._last_save = now
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(alphas, f, indent=2, default=str)
        except Exception as e:
            logger.warning("[EVOLUTION] Failed to save registry: %s", e)


class EvolvedPatternDetector:
    """
    Wraps the genetic AlphaDiscoveryEngine and exposes detect_evolved_*
    methods so the TimeframeAwareDetector discovers them automatically.

    On each scan the engine is allowed to evolve one generation using the
    latest price window. Strong out-of-sample alphas are promoted to
    executable patterns.
    """

    def __init__(
        self,
        engine: AlphaDiscoveryEngine | None = None,
        registry: EvolvedPatternRegistry | None = None,
        min_confidence: float = 55.0,
        min_signal_strength: float = 0.55,
        evolve_every_n_calls: int = 5,
    ) -> None:
        self.engine = engine or AlphaDiscoveryEngine(population_size=40)
        self.registry = registry or EvolvedPatternRegistry()
        self.min_confidence = min_confidence
        self.min_signal_strength = min_signal_strength
        self.evolve_every_n_calls = evolve_every_n_calls
        self._call_count = 0
        self._last_evolve = 0
        # Seed with previously learned alphas
        prior = self.registry.load()
        if prior:
            self.engine.active_alphas = prior

    def detect_evolved_alpha(self, df: "pl.DataFrame") -> PatternResult | None:
        """Return a PatternResult if the evolved ensemble fires."""
        if df is None or len(df) < 30:
            return None
        try:
            close = df["close"].to_numpy().astype(float)
        except Exception:
            return None

        self._call_count += 1
        if self._call_count >= self.evolve_every_n_calls:
            self._call_count = 0
            try:
                self.engine.evolve_generation(close.tolist(), baseline_sharpe=0.3)
                if self.engine.active_alphas:
                    self.registry.save(self.engine.active_alphas)
            except Exception as e:
                logger.debug("[EVOLUTION] evolve_generation failed: %s", e)

        signal = self.engine.ensemble_signal(close.tolist())
        if signal is None or abs(signal) < self.min_signal_strength:
            return None

        entry = float(close[-1])
        atr = _atr(close)
        stop = entry - atr * 1.5 if signal > 0 else entry + atr * 1.5
        target = _directional_target(entry, stop, rr=2.0)
        rr = abs(target - entry) / (abs(entry - stop) + 1e-9)
        confidence = min(95.0, abs(signal) * 100.0)
        lambda_val = int(confidence * 0.25)

        return PatternResult(
            name="Evolved Alpha",
            category="SWING",
            confidence=confidence,
            entry=entry,
            stop=stop,
            target=target,
            r_r_ratio=rr,
            confirmed=True,
            lambda_val=lambda_val,
            atr=atr,
        )

    def detect_evolved_momentum(self, df: "pl.DataFrame") -> PatternResult | None:
        """Shortcut evolved detector tuned for momentum breakouts."""
        if df is None or len(df) < 20:
            return None
        try:
            close = df["close"].to_numpy().astype(float)
            volume = df["volume"].to_numpy().astype(float)
        except Exception:
            return None
        if len(close) < 20 or len(volume) < 20:
            return None

        # Simple momentum + volume expansion primitive
        short = np.mean(close[-5:])
        long = np.mean(close[-20:])
        if short <= long:
            return None
        vol_now = float(np.mean(volume[-5:]))
        vol_base = float(np.mean(volume[-20:])) + 1e-9
        if vol_now < vol_base * 1.2:
            return None

        entry = float(close[-1])
        atr = _atr(close)
        stop = entry - atr * 1.5
        target = entry + atr * 3.0
        rr = abs(target - entry) / (abs(entry - stop) + 1e-9)
        return PatternResult(
            name="Evolved Momentum",
            category="SWING",
            confidence=65.0,
            entry=entry,
            stop=stop,
            target=target,
            r_r_ratio=rr,
            confirmed=True,
            lambda_val=20,
            atr=atr,
        )

    def detect_evolved_mean_reversion(self, df: "pl.DataFrame") -> PatternResult | None:
        """Shortcut evolved detector tuned for mean-reversion snaps."""
        if df is None or len(df) < 20:
            return None
        try:
            close = df["close"].to_numpy().astype(float)
        except Exception:
            return None

        window = close[-20:]
        mean = float(np.mean(window))
        std = float(np.std(window)) + 1e-9
        zscore = (close[-1] - mean) / std
        if abs(zscore) < 1.5:
            return None

        entry = float(close[-1])
        atr = _atr(close)
        if zscore < 0:
            # oversold -> long
            stop = entry - atr * 1.5
            target = entry + atr * 2.5
        else:
            # overbought -> short
            stop = entry + atr * 1.5
            target = entry - atr * 2.5
        rr = abs(target - entry) / (abs(entry - stop) + 1e-9)
        return PatternResult(
            name="Evolved Mean Reversion",
            category="SWING",
            confidence=min(85.0, abs(zscore) * 25.0),
            entry=entry,
            stop=stop,
            target=target,
            r_r_ratio=rr,
            confirmed=True,
            lambda_val=15,
            atr=atr,
        )

    def active_alpha_count(self) -> int:
        return len(self.engine.active_alphas)


def attach_evolved_detector(detector: Any, evolved: EvolvedPatternDetector) -> None:
    """
    Monkey-patch an existing PatternDetector instance so its detect_evolved_*
    methods are visible to TimeframeAwareDetector reflection.
    """
    detector.detect_evolved_alpha = evolved.detect_evolved_alpha
    detector.detect_evolved_momentum = evolved.detect_evolved_momentum
    detector.detect_evolved_mean_reversion = evolved.detect_evolved_mean_reversion
    detector.evolved_pattern_detector = evolved
