from typing import Dict, List

import numpy as np

def warmup():
    """JIT Warmup placeholder for Sovereign Numba pre-compilation."""
    pass

def calculate_kelly_criterion(win_rate: float, win_loss_ratio: float, fraction: float = 0.5) -> float:
    '''Calculates the optimal bet size based on the Kelly Criterion. Includes fractional Kelly for safety.'''
    if win_loss_ratio <= 0:
        return 0.0
    kelly_pct = win_rate - ((1.0 - win_rate) / win_loss_ratio)
    safe_kelly = max(0.0, kelly_pct * fraction)
    return float(safe_kelly)

def calculate_sortino_ratio(returns: List[float], risk_free_rate: float = 0.0, target_return: float = 0.0) -> float:
    '''Sortino ratio only penalizes downside volatility.'''
    if not returns:
        return 0.0
    ret_array = np.array(returns)
    mean_return = np.mean(ret_array)

    downside_returns = ret_array[ret_array < target_return]
    if len(downside_returns) == 0:
        return float('inf')

    downside_deviation = np.sqrt(np.mean((downside_returns - target_return)**2))
    return float((mean_return - risk_free_rate) / downside_deviation)

def calculate_value_at_risk(returns: List[float], confidence_level: float = 0.99, portfolio_value: float = 1.0) -> float:
    '''Historical Value at Risk (VaR).'''
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
