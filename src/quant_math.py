"""
src/quant_math.py — JIT-Compiled Math Core
All hot-path numerical functions compiled to native machine code via Numba.
Falls back to pure NumPy if Numba is not installed (CI-safe).

Import pattern:
    from quant_math import ema_array, rsi_array, atr_array, kalman_update
"""

from __future__ import annotations

import logging

import numpy as np

logger = logging.getLogger(__name__)

# ── Numba JIT bootstrap ────────────────────────────────────────────────────────
try:
    from numba import njit  # type: ignore

    _NUMBA_AVAILABLE = True
    logger.info("quant_math: Numba JIT enabled — math running at native speed.")
except ImportError as e:
    logger.warning(
        f"quant_math: Numba not installed or import failed: {e}. Running pure NumPy (slower). pip install numba"
    )
    _NUMBA_AVAILABLE = False
except Exception as e:
    logger.warning(
        f"quant_math: Unexpected error importing numba: {e}. Running pure NumPy (slower)."
    )
    _NUMBA_AVAILABLE = False

    def njit(*args, **kwargs):  # type: ignore  # noqa: E302
        """No-op decorator when Numba is unavailable."""

        def decorator(fn):
            return fn

        if args and callable(args[0]):
            return args[0]
        return decorator


# ── EMA ────────────────────────────────────────────────────────────────────────


@njit(cache=True)
def ema_array(prices: np.ndarray, period: int) -> np.ndarray:
    """
    Full-array EMA — O(n), Numba JIT compiled.
    Returns array of same length; first `period-1` values are NaN.
    """
    n = len(prices)
    out = np.empty(n, dtype=np.float64)
    alpha = 2.0 / (period + 1)
    out[0] = prices[0]
    for i in range(1, n):
        out[i] = alpha * prices[i] + (1.0 - alpha) * out[i - 1]
    # Mask warm-up values
    for i in range(min(period - 1, n)):
        out[i] = np.nan
    return out


@njit(cache=True)
def ema_scalar(prev_ema: float, price: float, alpha: float) -> float:
    """Single-tick EMA update — used in the incremental indicator library."""
    return alpha * price + (1.0 - alpha) * prev_ema


# ── RSI ────────────────────────────────────────────────────────────────────────


@njit(cache=True)
def rsi_array(prices: np.ndarray, period: int = 14) -> np.ndarray:
    """
    Wilder's RSI over a full price array.
    Returns array of same length; first `period` values are NaN.
    """
    n = len(prices)
    out = np.full(n, np.nan)
    if n < period + 1:
        return out

    gains = np.empty(n - 1)
    losses = np.empty(n - 1)
    for i in range(n - 1):
        diff = prices[i + 1] - prices[i]
        gains[i] = diff if diff > 0.0 else 0.0
        losses[i] = -diff if diff < 0.0 else 0.0

    avg_gain = np.mean(gains[:period])
    avg_loss = np.mean(losses[:period])

    for i in range(period, n - 1):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        if avg_loss < 1e-12:
            out[i + 1] = 100.0
        else:
            rs = avg_gain / avg_loss
            out[i + 1] = 100.0 - (100.0 / (1.0 + rs))

    return out


# ── ATR ────────────────────────────────────────────────────────────────────────


@njit(cache=True)
def atr_array(
    highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int = 14
) -> np.ndarray:
    """
    Wilder's Average True Range over full OHLC arrays.
    Returns ATR array; first `period` values are NaN.
    """
    n = len(closes)
    out = np.full(n, np.nan)
    if n < period + 1:
        return out

    tr = np.empty(n)
    tr[0] = highs[0] - lows[0]
    for i in range(1, n):
        hl = highs[i] - lows[i]
        hc = abs(highs[i] - closes[i - 1])
        lc = abs(lows[i] - closes[i - 1])
        tr[i] = max(hl, hc, lc)

    atr = np.mean(tr[1 : period + 1])
    out[period] = atr
    alpha = 1.0 / period
    for i in range(period + 1, n):
        atr = alpha * tr[i] + (1.0 - alpha) * atr
        out[i] = atr

    return out


# ── Bollinger Bands ────────────────────────────────────────────────────────────


@njit(cache=True)
def bollinger_bands(
    prices: np.ndarray, period: int = 20, k: float = 2.0
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Returns (upper, middle, lower) Bollinger Band arrays."""
    n = len(prices)
    upper = np.full(n, np.nan)
    middle = np.full(n, np.nan)
    lower = np.full(n, np.nan)

    for i in range(period - 1, n):
        window = prices[i - period + 1 : i + 1]
        mu = np.mean(window)
        sigma = np.std(window)
        middle[i] = mu
        upper[i] = mu + k * sigma
        lower[i] = mu - k * sigma

    return upper, middle, lower


# ── MACD ───────────────────────────────────────────────────────────────────────


@njit(cache=True)
def macd_array(
    prices: np.ndarray, fast: int = 12, slow: int = 26, signal: int = 9
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Returns (macd_line, signal_line, histogram) arrays.
    All NaN until slow + signal bars have elapsed.
    """
    fast_ema = ema_array(prices, fast)
    slow_ema = ema_array(prices, slow)
    macd_line = fast_ema - slow_ema
    sig_line = ema_array(macd_line, signal)
    histogram = macd_line - sig_line
    return macd_line, sig_line, histogram


# ── Kalman Filter ──────────────────────────────────────────────────────────────


@njit(cache=True)
def kalman_update(
    x: float, p: float, price: float, q: float = 1e-4, r: float = 1e-2
) -> tuple[float, float]:
    """
    One-step scalar Kalman filter update.
    Returns (new_x, new_P): updated state estimate and error covariance.
    """
    p_pred = p + q
    k = p_pred / (p_pred + r)
    x_new = x + k * (price - x)
    p_new = (1.0 - k) * p_pred
    return x_new, p_new


# ── MultiFactorAlpha core ──────────────────────────────────────────────────────


@njit(cache=True)
def multi_factor_score(
    returns: np.ndarray,
    volumes: np.ndarray,
    w_mom_mid: float = 0.30,
    w_mom_short: float = 0.20,
    w_mean_rev: float = 0.20,
    w_vol_regime: float = 0.15,
    w_vol_surge: float = 0.15,
) -> float:
    """
    JIT-compiled MultiFactorAlpha score.
    Accepts pre-computed log-return array and volume array.
    Returns composite score in [-1, 1].
    """
    n = len(returns)
    if n < 25:
        return 0.0

    # Momentum
    lookback_mid = min(n, 60)
    mom_mid = float(np.sum(returns[-lookback_mid:]))

    lookback_short = min(n, 15)
    mom_short = float(np.sum(returns[-lookback_short:]))

    # Mean reversion
    if n >= 10:
        mu = np.mean(returns[-10:])
        sigma = np.std(returns[-10:]) + 1e-10
        mean_rev = -float((returns[-1] - mu) / sigma)
    else:
        mean_rev = 0.0

    # Volatility regime
    if n >= 30:
        vol_now = float(np.std(returns[-10:]))
        vol_base = float(np.std(returns[-30:]))
        vol_regime = -1.0 if vol_now > vol_base * 1.8 else 0.5
    else:
        vol_regime = 0.0

    # Volume surge
    nv = len(volumes)
    if nv >= 20 and volumes[-1] > 0.0:
        vol_surge = float(volumes[-1] / (np.mean(volumes[-20:]) + 1e-10)) - 1.0
        vol_surge = max(-1.0, min(1.0, vol_surge))
    else:
        vol_surge = 0.0

    # Normalise
    f_mom_mid = max(-1.0, min(1.0, mom_mid * 80.0))
    f_mom_short = max(-1.0, min(1.0, mom_short * 150.0))
    f_mean_rev = max(-1.0, min(1.0, mean_rev * 0.5))

    score = (
        w_mom_mid * f_mom_mid
        + w_mom_short * f_mom_short
        + w_mean_rev * f_mean_rev
        + w_vol_regime * vol_regime
        + w_vol_surge * vol_surge
    )

    return max(-1.0, min(1.0, float(score)))


# ── Warm-up trigger (Numba compiles on first call) ────────────────────────────


def warmup() -> None:
    """
    Pre-trigger Numba JIT compilation during system startup.
    Call once at boot so the first live tick doesn't pay the compile cost.
    """
    if not _NUMBA_AVAILABLE:
        return
    dummy = np.linspace(100.0, 110.0, 200)
    ema_array(dummy, 20)
    rsi_array(dummy, 14)
    atr_array(dummy, dummy * 0.99, dummy * 0.995, 14)
    bollinger_bands(dummy, 20, 2.0)
    macd_array(dummy, 12, 26, 9)
    kalman_update(100.0, 1.0, 100.5)
    returns = np.diff(np.log(dummy + 1e-10))
    multi_factor_score(returns, np.ones(len(returns)) * 1000)
    logger.info("quant_math: Numba warmup complete — all kernels compiled.")


NUMBA_AVAILABLE = _NUMBA_AVAILABLE

# ── LOCAL-ONLY QUANT EXTENSIONS (recovered from local system) ────────────


def _internal_kelly(win_rate: float, win_loss_ratio: float, fraction: float) -> float:
    if win_loss_ratio <= 0:
        return 0.0
    kelly_pct = win_rate - ((1.0 - win_rate) / win_loss_ratio)
    safe_kelly = max(0.0, kelly_pct * fraction)
    return float(safe_kelly)


def calculate_kelly_criterion(win_rate: float, win_loss_ratio: float, fraction: float = 0.5) -> float:
    """Calculates the optimal bet size based on the Kelly Criterion. Includes fractional Kelly for safety."""
    return _internal_kelly(win_rate, win_loss_ratio, fraction)

@njit


def _internal_sortino(ret_array: np.ndarray, risk_free_rate: float, target_return: float) -> float:
    mean_return = np.mean(ret_array)

    # Filter downside returns (Numba optimized)
    downside_sum = 0.0
    downside_count = 0
    for r in ret_array:
        if r < target_return:
            downside_sum += (r - target_return)**2
            downside_count += 1

    if downside_count == 0:
        return 100.0 # High value for no downside

    downside_deviation = np.sqrt(downside_sum / len(ret_array))
    if downside_deviation == 0:
        return 0.0
    return (mean_return - risk_free_rate) / downside_deviation


def calculate_sortino_ratio(returns: List[float], risk_free_rate: float = 0.0, target_return: float = 0.0) -> float:
    """Sortino ratio only penalizes downside volatility."""
    if not returns:
        return 0.0
    return float(_internal_sortino(np.array(returns, dtype=np.float64), risk_free_rate, target_return))


def calculate_value_at_risk(returns: List[float], confidence_level: float = 0.99, portfolio_value: float = 1.0) -> float:
    """Historical Value at Risk (VaR)."""
    if not returns:
        return 0.0
    var_percentile = (1.0 - confidence_level) * 100.0
    var_pct = np.percentile(returns, var_percentile)
    return float(abs(var_pct) * portfolio_value)


def get_portfolio_metrics(returns: List[float]) -> Dict[str, float]:
    wins = [r for r in returns if r > 0]
    losses = [abs(r) for r in returns if r < 0]

    win_rate = len(wins) / len(returns) if returns else 0.0
    avg_win = float(np.mean(wins)) if wins else 0.0
    avg_loss = float(np.mean(losses)) if losses else 0.0
    wlr = avg_win / avg_loss if avg_loss > 0 else 0.0

    return {
        "kelly_pct": calculate_kelly_criterion(win_rate, wlr),
        "sortino": calculate_sortino_ratio(returns),
        "var_99": calculate_value_at_risk(returns)
    }

def warmup():
    """JIT Warmup for Sovereign Numba pre-compilation."""
    if HAS_NUMBA:
        # Trigger compilation for core kernels
        _internal_kelly(0.5, 2.0, 0.5)
        _internal_sortino(np.array([0.01, -0.02, 0.015], dtype=np.float64), 0.0, 0.0)

