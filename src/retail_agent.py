import logging
from typing import Dict

logger = logging.getLogger(__name__)

class FootfallAnalysisAgent:
    """
    Retail foot traffic analyser using public camera feeds and parking lot density.
    Retail same-store-sales correlates with foot traffic 2-4 weeks in advance.
    """
    RETAIL_TICKERS = {"walmart": "WMT", "target": "TGT", "costco": "COST", "macys": "M"}

    def estimate_traffic_trend(self, retailer: str, weekly_counts: list[int]) -> Dict:
        if len(weekly_counts) < 4:
            return {"retailer": retailer, "trend": "UNKNOWN", "yoy_change": 0.0}
        recent_avg = sum(weekly_counts[-2:]) / 2
        prior_avg = sum(weekly_counts[-6:-4]) / 2 if len(weekly_counts) >= 6 else weekly_counts[0]
        yoy_change = (recent_avg - prior_avg) / (prior_avg or 1)
        trend = "BULLISH" if yoy_change > 0.05 else "BEARISH" if yoy_change < -0.05 else "NEUTRAL"
        ticker = self.RETAIL_TICKERS.get(retailer.lower(), "UNKNOWN")
        logger.info(f"[FOOTFALL] {retailer}({ticker}): YoY={yoy_change:+.1%} -> {trend}")
        return {"retailer": retailer, "ticker": ticker, "yoy_change": round(yoy_change, 4), "trend": trend}
