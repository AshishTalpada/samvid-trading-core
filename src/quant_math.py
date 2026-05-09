try:
    from numba import njit
    HAS_NUMBA = True
except ImportError:
    HAS_NUMBA = False
    def njit(f): return f

from typing import Dict, List
import numpy as np

@njit
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
    avg_win = np.mean(wins) if wins else 0.0
    avg_loss = np.mean(losses) if losses else 0.0
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
