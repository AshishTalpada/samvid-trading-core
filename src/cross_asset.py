import logging
from typing import Dict

import numpy as np

logger = logging.getLogger(__name__)


class CrossAssetLeadIndicator:
    """
    Uses Bond, Gold, and DXY movements as leading indicators for equity entries.
    Classic macro relationships:
    - Falling yields + rising gold -> risk-off, reduce equity exposure
    - Rising DXY -> EM equity headwind
    - Yield curve inversion -> recession signal (lag 12-18 months)
    """

    def compute_risk_appetite(self, asset_returns: Dict[str, float]) -> float:
        tlt = asset_returns.get("TLT", 0.0)  # 20yr Treasury (falling = risk-on)
        gld = asset_returns.get("GLD", 0.0)  # Gold (rising = risk-off)
        dxy = asset_returns.get("DXY", 0.0)  # Dollar (rising = EM risk-off)
        spy = asset_returns.get("SPY", 0.0)  # Equity
        risk_on_score = -tlt * 0.4 - gld * 0.3 - dxy * 0.2 + spy * 0.1
        return float(np.tanh(risk_on_score * 10))

    def yield_curve_slope(self, y10: float, y2: float) -> float:
        slope = y10 - y2
        if slope < 0:
            logger.warning(f"[CROSS ASSET] Inverted yield curve: slope={slope:.2f}bps")
        return slope

    def leading_signal(self, asset_returns: Dict[str, float], y10: float, y2: float) -> str:
        appetite = self.compute_risk_appetite(asset_returns)
        slope = self.yield_curve_slope(y10, y2)
        if appetite > 0.3 and slope > 0:
            return "RISK_ON"
        if appetite < -0.3 or slope < 0:
            return "RISK_OFF"
        return "NEUTRAL"
