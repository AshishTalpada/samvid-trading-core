import logging
import random
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

RNG = np.random.default_rng(42)


def _rule_momentum(prices: np.ndarray, period: int = 10) -> float:
    """1 if momentum positive, -1 if negative, 0 if insufficient data."""
    if len(prices) < period + 1:
        return 0.0
    return 1.0 if prices[-1] > prices[-period] else -1.0


def _rule_rsi(prices: np.ndarray, period: int = 14, buy_thresh: float = 35.0, sell_thresh: float = 65.0) -> float:
    """RSI mean-reversion signal: 1 oversold, -1 overbought, 0 neutral."""
    if len(prices) < period + 1:
        return 0.0
    deltas = np.diff(prices[-(period + 1):])
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)
    avg_gain = float(np.mean(gains)) + 1e-9
    avg_loss = float(np.mean(losses)) + 1e-9
    rs = avg_gain / avg_loss
    rsi = 100.0 - (100.0 / (1.0 + rs))
    if rsi < buy_thresh:
        return 1.0
    if rsi > sell_thresh:
        return -1.0
    return 0.0


def _rule_bollinger(prices: np.ndarray, period: int = 20, k: float = 2.0) -> float:
    """Bollinger mean-reversion: 1 below lower band, -1 above upper band."""
    if len(prices) < period:
        return 0.0
    window = prices[-period:]
    mid = float(np.mean(window))
    std = float(np.std(window)) + 1e-9
    lower = mid - k * std
    upper = mid + k * std
    p = prices[-1]
    if p < lower:
        return 1.0
    if p > upper:
        return -1.0
    return 0.0


def _rule_macd(prices: np.ndarray, fast: int = 12, slow: int = 26) -> float:
    """MACD crossover: positive MACD → 1, negative → -1."""
    if len(prices) < slow:
        return 0.0
    ema_fast = _ema(prices, fast)
    ema_slow = _ema(prices, slow)
    return 1.0 if ema_fast > ema_slow else -1.0


def _ema(prices: np.ndarray, period: int) -> float:
    k = 2.0 / (period + 1)
    ema = float(prices[0])
    for p in prices[1:]:
        ema = p * k + ema * (1 - k)
    return ema


def _rule_higher_highs(prices: np.ndarray, period: int = 10) -> float:
    """Higher highs / lower lows trend primitive."""
    if len(prices) < period + 2:
        return 0.0
    recent_highs = prices[-period:]
    older_high = float(np.max(prices[-(period * 2):-period]))
    if np.max(recent_highs) > older_high:
        return 1.0
    if np.min(recent_highs) < older_high:
        return -1.0
    return 0.0


def _rule_breakout(prices: np.ndarray, period: int = 20) -> float:
    """Breakout above recent high / breakdown below recent low."""
    if len(prices) < period + 1:
        return 0.0
    window = prices[-(period + 1):-1]
    if prices[-1] > float(np.max(window)):
        return 1.0
    if prices[-1] < float(np.min(window)):
        return -1.0
    return 0.0


def _rule_volatility_squeeze(prices: np.ndarray, period: int = 20, threshold: float = 0.5) -> float:
    """Volatility compression primitive: low std followed by expansion."""
    if len(prices) < period + 5:
        return 0.0
    old_std = float(np.std(prices[-(period + 5):-5]))
    new_std = float(np.std(prices[-5:]))
    if old_std == 0:
        return 0.0
    if new_std / old_std > threshold:
        return 1.0 if prices[-1] > prices[-6] else -1.0
    return 0.0


# Parameter space for genetic mutation
_RULE_REGISTRY: List[Tuple[str, Callable]] = [
    ("momentum", _rule_momentum),
    ("rsi", _rule_rsi),
    ("bollinger", _rule_bollinger),
    ("macd", _rule_macd),
    ("higher_highs", _rule_higher_highs),
    ("breakout", _rule_breakout),
    ("volatility_squeeze", _rule_volatility_squeeze),
]

_PARAM_SPACE = {
    "momentum": {"period": (5, 50)},
    "rsi": {"period": (7, 28), "buy_thresh": (20.0, 45.0), "sell_thresh": (55.0, 80.0)},
    "bollinger": {"period": (10, 40), "k": (1.0, 3.0)},
    "macd": {"fast": (5, 20), "slow": (15, 40)},
    "higher_highs": {"period": (5, 30)},
    "breakout": {"period": (10, 60)},
    "volatility_squeeze": {"period": (10, 40), "threshold": (0.3, 1.5)},
}


class _Alpha:
    """A single alpha gene: rule type + parameters."""

    def __init__(self, rule_name: str, params: Dict[str, Any]):
        self.rule_name = rule_name
        self.params = params
        self.sharpe: float = 0.0
        self.n_trades: int = 0

    def signal(self, prices: np.ndarray) -> float:
        fn = dict(_RULE_REGISTRY)[self.rule_name]
        try:
            return fn(prices, **self.params)
        except Exception:
            return 0.0

    @classmethod
    def random(cls) -> "_Alpha":
        name = random.choice([r[0] for r in _RULE_REGISTRY])
        space = _PARAM_SPACE[name]
        params: Dict[str, Any] = {}
        for k, (lo, hi) in space.items():
            if isinstance(lo, int):
                params[k] = random.randint(lo, hi)
            else:
                params[k] = round(random.uniform(lo, hi), 2)
        return cls(name, params)

    def mutate(self) -> "_Alpha":
        new_params = dict(self.params)
        space = _PARAM_SPACE[self.rule_name]
        key = random.choice(list(space.keys()))
        lo, hi = space[key]
        if isinstance(lo, int):
            delta = random.randint(-3, 3)
            new_params[key] = int(np.clip(new_params[key] + delta, lo, hi))
        else:
            delta = random.uniform(-0.2, 0.2) * (hi - lo)
            new_params[key] = round(float(np.clip(new_params[key] + delta, lo, hi)), 2)
        return _Alpha(self.rule_name, new_params)


class AlphaDiscoveryEngine:
    """
    Mines for new market edges using a Genetic Algorithm.
    Generates a population of parameterized trading rules, evaluates each
    against in-sample data using Sharpe ratio, and evolves the best
    candidates through mutation. Promotes out-of-sample survivors to
    the active ensemble.
    """

    def __init__(self, population_size: int = 50, elite_frac: float = 0.2):
        self.population_size = population_size
        self.elite_frac = elite_frac
        self._population: List[_Alpha] = []
        self.active_alphas: List[Dict[str, Any]] = []

    def evaluate_alpha(self, rule: Callable, prices: np.ndarray) -> float:
        """Evaluate an arbitrary callable rule and return annualised Sharpe."""
        signals = np.array([rule(prices[:i]) for i in range(14, len(prices))])
        price_returns = np.diff(prices[13:])  # len = len(prices) - 14
        n = min(len(price_returns), len(signals))
        if n < 2:
            return 0.0
        pnl = price_returns[:n] * signals[:n]
        if np.std(pnl) == 0:
            return 0.0
        return float(np.mean(pnl) / np.std(pnl) * np.sqrt(252))

    def _score(self, alpha: _Alpha, prices: np.ndarray, start: int = 14) -> float:
        """Score an _Alpha gene over a price window, returning annualised Sharpe."""
        signals = np.array([alpha.signal(prices[:i]) for i in range(start, len(prices))])
        if len(signals) < 2:
            return 0.0
        # returns[i] = price change at bar (start+i), signal[i] = decision at bar start+i
        price_returns = np.diff(prices[start - 1:])  # len = len(prices) - start
        n = min(len(price_returns), len(signals))
        if n < 2:
            return 0.0
        pnl = price_returns[:n] * signals[:n]
        if np.std(pnl) == 0:
            return 0.0
        alpha.n_trades = int(np.count_nonzero(signals[:n]))
        return float(np.mean(pnl) / np.std(pnl) * np.sqrt(252))

    def _seed_population(self) -> None:
        self._population = [_Alpha.random() for _ in range(self.population_size)]

    def evolve_generation(self, prices: List[float], baseline_sharpe: float = 0.5) -> None:
        """One GA generation: evaluate → select elites → mutate → promote survivors."""
        arr = np.array(prices, dtype=float)
        if len(arr) < 60:
            return

        if not self._population:
            self._seed_population()

        # --- In-sample: first 70% of bars -------
        split = max(30, int(len(arr) * 0.70))
        in_sample = arr[:split]
        out_sample = arr[split:]

        logger.info(
            "[DISCOVERY] Evolving %d candidates | in=%d out=%d bars",
            len(self._population),
            len(in_sample),
            len(out_sample),
        )

        # Score each gene on in-sample
        for a in self._population:
            a.sharpe = self._score(a, in_sample)

        # Rank by Sharpe, keep elite fraction
        self._population.sort(key=lambda a: a.sharpe, reverse=True)
        n_elite = max(1, int(len(self._population) * self.elite_frac))
        elites = self._population[:n_elite]

        # Mutate elites to fill next generation
        children = [e.mutate() for e in elites for _ in range(self.population_size // n_elite)]
        self._population = elites + children
        self._population = self._population[: self.population_size]

        # Validate elites out-of-sample before promoting
        if len(out_sample) < 15:
            return

        for elite in elites:
            oos_sharpe = self._score(elite, out_sample)
            if oos_sharpe > baseline_sharpe and elite.n_trades >= 3:
                entry: Dict[str, Any] = {
                    "rule": elite.rule_name,
                    "params": dict(elite.params),
                    "sharpe_is": round(elite.sharpe, 3),
                    "sharpe_oos": round(oos_sharpe, 3),
                    "weight": round(oos_sharpe / (abs(elite.sharpe) + 1e-6), 3),
                }
                self.active_alphas.append(entry)
                logger.info(
                    "[DISCOVERY] Promoted alpha: %s params=%s OOS_Sharpe=%.2f",
                    elite.rule_name, elite.params, oos_sharpe,
                )

        # Prune ensemble: keep only alphas that beat 80% of baseline
        self.active_alphas = [a for a in self.active_alphas if a["sharpe_oos"] > baseline_sharpe * 0.8]

    def ensemble_signal(self, prices: List[float]) -> Optional[float]:
        """
        Weighted average signal from all promoted alphas.
        Returns a float in [-1, 1] or None if no alphas available.
        """
        if not self.active_alphas:
            return None
        arr = np.array(prices, dtype=float)
        total_weight = sum(a["weight"] for a in self.active_alphas)
        if total_weight <= 0:
            return None
        composite = 0.0
        for entry in self.active_alphas:
            fn = dict(_RULE_REGISTRY).get(entry["rule"])
            if fn is None:
                continue
            try:
                sig = fn(arr, **entry["params"])
            except Exception:
                sig = 0.0
            composite += sig * entry["weight"]
        return float(np.clip(composite / total_weight, -1.0, 1.0))
