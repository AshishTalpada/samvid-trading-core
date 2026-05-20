import asyncio
import logging
from typing import Dict

import requests

logger = logging.getLogger(__name__)

FRED_API = "https://fred.stlouisfed.org/graph/fredgraph.json"


class DebtCycleTracker:
    """
    Tracks Ray Dalio's long-term debt cycle metrics via FRED economic data.
    Key indicators: Total credit / GDP ratio, debt service ratio, M2 growth.
    When credit/GDP > 200% and M2 growth decelerates -> major deleveraging risk.
    """

    FRED_SERIES = {
        "total_credit_gdp": "TCMDO",
        "household_debt_service": "TDSP",
        "m2_money_supply": "M2SL",
        "federal_debt_gdp": "GFDEGDQ188S",
    }

    async def get_fred_series(self, series_id: str) -> float:
        def _fetch():
            r = requests.get(f"{FRED_API}?id={series_id}", timeout=5)
            obs = r.json().get("observations", [])
            return float(obs[-1]["value"]) if obs else 0.0

        try:
            return await asyncio.to_thread(_fetch)
        except Exception as e:
            logger.error(f"[DEBT] FRED fetch failed ({series_id}): {e}")
            return 0.0

    async def debt_cycle_stage(self) -> Dict[str, float | str]:
        # Fetch both series concurrently instead of sequentially
        credit_gdp, m2 = await asyncio.gather(
            self.get_fred_series("GFDEGDQ188S"),
            self.get_fred_series("M2SL"),
        )
        stage = "EXPANSION" if credit_gdp < 100 else "PEAK" if credit_gdp < 130 else "DELEVERAGING"
        logger.info(f"[DEBT] Fed Debt/GDP={credit_gdp:.1f}% | Stage={stage}")
        return {"credit_to_gdp": credit_gdp, "m2": m2, "cycle_stage": stage}

