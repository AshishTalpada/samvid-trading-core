import numpy as np

class FractalAgent:
    """
    Distinguish between a "Real Trend" and a "Fake-out" by measuring the Fractal Dimension.
    """
    def higuchi_fd(self, data: list[float], k_max: int = 10) -> float:
        """
        Calculates the Higuchi Fractal Dimension (HFD) of a time series.
        HFD ~ 1.0 means it's a perfectly smooth trend.
        HFD ~ 1.5 means it's a random walk (noise).
        HFD ~ 2.0 means it's highly mean-reverting / choppy.
        
        Args:
            data: Time series price data.
            k_max: Maximum interval time.
            
        Returns:
            Fractal dimension as a float.
        """
        L = []
        x = []
        N = len(data)
        if N < k_max * 2:
            return 1.5 # Default random walk if not enough data
            
        data_arr = np.array(data)
        
        for k in range(1, k_max + 1):
            Lk = []
            for m in range(0, k):
                Lmk = 0
                max_i = int(np.floor((N - m - 1) / k))
                if max_i > 0:
                    for i in range(1, max_i + 1):
                        Lmk += abs(data_arr[m + i * k] - data_arr[m + (i - 1) * k])
                    
                    Lmk = Lmk * (N - 1) / (max_i * k) / k
                    Lk.append(Lmk)
            
            if Lk:
                # Average length for this k
                L.append(np.log(np.mean(Lk)))
                x.append(np.log(1.0 / k))
            
        if len(x) < 2:
            return 1.5
            
        # Fit a line: L = m*x + c, the slope 'm' is the fractal dimension
        coeffs = np.polyfit(x, L, 1)
        return float(coeffs[0])
        
    def analyze_trend(self, data: list[float]) -> dict[str, any]:
        fd = self.higuchi_fd(data)
        
        if fd < 1.3:
            state = "STRONG_TREND"
        elif fd < 1.55:
            state = "RANDOM_WALK"
        else:
            state = "CHOPPY_MEAN_REVERTING"
            
        return {
            "fractal_dimension": fd,
            "market_state": state,
            "trade_recommended": state == "STRONG_TREND"
        }
