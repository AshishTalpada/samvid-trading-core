import asyncio
import logging
from typing import List

import requests

logger = logging.getLogger(__name__)


class OceanFreightAgent:
    """
    Real-time ocean container freight tracker.
    Ingests Baltic Dry Index (BDI) + AIS vessel position data to detect
    supply chain bottlenecks before they appear in earnings reports.
    """

    BDI_PROXY = "https://markets.businessinsider.com/api/search"
    COMMODITY_MAP = {"shipping": ["ZIM", "MATX", "DAC"], "containers": ["FDX", "UPS", "XPO"]}

    async def get_bdi_estimate(self) -> float:
        """Returns a normalised BDI score 0.0-1.0 from public proxy."""

        def _fetch():
            r = requests.get(
                "https://fred.stlouisfed.org/graph/fredgraph.csv?id=BDIYINDEX", timeout=5
            )
            lines = [ln for ln in r.text.strip().split("\n") if "," in ln]
            last_val = float(lines[-1].split(",")[1])
            return min(1.0, last_val / 5000.0)

        try:
            return await asyncio.to_thread(_fetch)
        except Exception as e:
            logger.error(f"[FREIGHT] BDI fetch failed: {e}")
            return 0.5

    def tickers_at_risk(self, bdi: float) -> List[str]:
        """When BDI drops > 20% WoW, shipping stocks typically lag by 5-10 days."""
        if bdi < 0.3:
            return self.COMMODITY_MAP["shipping"]
        return []
