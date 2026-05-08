import numpy as np


class ExtendedTailRisk:
    """Extended tail risk model computing both VaR and Conditional VaR at multiple confidence levels."""
    def compute(self, returns: list[float], levels: list[float] = [0.95, 0.99]) -> dict[str, float]:
        if len(returns) < 20:
            return {}
        arr = np.sort(np.array(returns))
        result = {}
        for level in levels:
            idx = int((1 - level) * len(arr))
            var = float(arr[idx])
            cvar = float(np.mean(arr[:idx])) if idx > 0 else var
            result[f"VaR_{int(level*100)}"] = var
            result[f"CVaR_{int(level*100)}"] = cvar
        return result
