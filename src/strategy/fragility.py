import numpy as np
import logging
from typing import List

logger = logging.getLogger(__name__)

class AntiFragilityEngine:
    '''
    Identifies if an asset exhibits anti-fragile properties 
    (gains disproportionately from volatility/chaos).
    Based on Nassim Taleb's mathematical definition of convexity.
    '''
    def __init__(self, window: int = 60):
        self.window = window

    def calculate_antifragility(self, asset_returns: List[float], market_volatility: List[float]) -> dict:
        '''
        Measures the correlation between asset returns and market volatility spikes.
        Calculates the Second Derivative (Convexity) of the asset's payoff profile 
        with respect to systemic market stress.
        '''
        if len(asset_returns) < self.window or len(market_volatility) < self.window:
            return {"score": 0.0, "is_antifragile": False, "convexity": 0.0}

        ret_array = np.array(asset_returns[-self.window:])
        vol_array = np.array(market_volatility[-self.window:])

        # 1. Asymmetric Beta Profile (Upside Capture vs Downside Capture during High Volatility)
        # Find periods of extremely high systemic volatility (top 20th percentile)
        vol_threshold = np.percentile(vol_array, 80)
        high_vol_mask = vol_array >= vol_threshold
        
        returns_in_high_vol = ret_array[high_vol_mask]
        returns_in_low_vol = ret_array[~high_vol_mask]

        if len(returns_in_high_vol) == 0 or len(returns_in_low_vol) == 0:
            return {"score": 0.0, "is_antifragile": False, "convexity": 0.0}

        mean_high_vol_ret = np.mean(returns_in_high_vol)
        mean_low_vol_ret = np.mean(returns_in_low_vol)

        # 2. Local Convexity Estimation
        # Fit a 2nd degree polynomial: Return = a + b(Vol) + c(Vol^2)
        # If 'c' (the second derivative) is strongly positive, the asset is strictly anti-fragile.
        poly_fit = np.polyfit(vol_array, ret_array, 2)
        convexity_coeff = poly_fit[0]  # The 'c' term in ax^2 + bx + c

        # 3. Fragility Score
        # Bounded between -1.0 (Highly Fragile) and 1.0 (Highly Anti-Fragile)
        # A positive score means the asset makes MORE money when the market is crashing/volatile.
        
        volatility_capture_spread = mean_high_vol_ret - mean_low_vol_ret
        
        # Normalize the score somewhat heuristically based on the spread and convexity
        raw_score = (volatility_capture_spread * 100) + (convexity_coeff * 1000)
        score = np.clip(raw_score, -1.0, 1.0)
        
        is_anti = score > 0.4 and convexity_coeff > 0.001

        if is_anti:
            logger.info(f"[FRAGILITY] Anti-Fragile asset detected. Score: {score:.2f}, Convexity: {convexity_coeff:.4f}")
        elif score < -0.6:
            logger.warning(f"[FRAGILITY] HIGHLY FRAGILE asset detected. Avoid holding during VIX spikes.")

        return {
            "score": float(score),
            "is_antifragile": bool(is_anti),
            "convexity": float(convexity_coeff),
            "high_vol_avg_return": float(mean_high_vol_ret)
        }
