import logging
import math
from typing import Dict, List

logger = logging.getLogger(__name__)


class MultiHorizonHedger:
    """
    Simultaneously hedges short-term (5-min) volatility dips and medium-term (daily) crash risk.
    Maintains two hedge layers:
    - Layer 1: Short-dated ATM puts (5-30 DTE) for immediate tail protection
    - Layer 2: OTM LEAP puts (90+ DTE) for macro crash insurance
    """

    def compute_hedge_budget_pct(self, portfolio_vega: float, vix: float) -> float:
        base_budget = 0.005  # 0.5% of NAV
        vix_adj = max(1.0, vix / 20.0)
        vega_adj = min(2.0, abs(portfolio_vega) / 1000.0 + 1.0)
        return min(0.02, base_budget * vix_adj * vega_adj)

    def select_hedge_instruments(self, spot: float, vix: float, horizon: str) -> Dict:
        if horizon == "short":
            strike_pct = 0.98
            dte = 14
        else:
            strike_pct = 0.90
            dte = 90
        strike = round(spot * strike_pct, 2)
        logger.info(
            f"[HEDGER] {horizon} hedge: {dte}DTE {strike_pct:.0%} strike={strike} at VIX={vix:.1f}"
        )
        return {"strike": strike, "dte": dte, "instrument": "PUT", "horizon": horizon}

    def hedge_ratio(
        self, position_delta: float, put_delta: float, coverage_pct: float = 0.5
    ) -> int:
        if abs(put_delta) < 1e-6:
            return 0
        contracts = int(-position_delta * coverage_pct / (put_delta * 100))
        return abs(contracts)
