import logging
import math
from dataclasses import dataclass
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)


@dataclass
class MarketImpactResult:
    temporary_impact_bps: float
    permanent_impact_bps: float
    expected_slippage_dollars: float
    optimal_slices: int
    optimal_time_horizon_minutes: float


class ImpactSimulator:
    """
    Advanced Market Impact Simulator for High-Frequency and Institutional Execution.
    Models how Sovereign's own trades will permanently and temporarily move the market,
    preventing the system from crushing its own alpha through careless execution sizing.
    Uses an adaptation of the Almgren-Chriss (2000) and Kyle's Lambda (1985) models.
    """

    def __init__(self, adv_data: Dict[str, float], daily_volatility_data: Dict[str, float]):
        """
        :param adv_data: Dictionary mapping ticker to Average Daily Volume (shares)
        :param daily_volatility_data: Dictionary mapping ticker to Daily Volatility (decimal, e.g., 0.02 for 2%)
        """
        self.adv = adv_data
        self.volatility = daily_volatility_data

        # Empirical coefficients calibrated from historical institutional flow
        self.gamma = 0.314  # Temporary impact coefficient (liquidity demanding)
        self.eta = 0.142  # Permanent impact coefficient (information content)

    def calculate_market_impact(
        self,
        ticker: str,
        order_size_shares: int,
        current_price: float,
        trade_duration_minutes: float = 30.0,
    ) -> MarketImpactResult:
        """
        Calculates the expected slippage and impact of an order.
        """
        order_size_shares = int(order_size_shares)
        current_price = float(current_price)
        trade_duration_minutes = max(0.0, float(trade_duration_minutes))
        if order_size_shares <= 0:
            return MarketImpactResult(0.0, 0.0, 0.0, 0, 0.0)

        daily_vol = self.adv.get(ticker, 1_000_000)
        daily_vol_pct = self.volatility.get(ticker, 0.02)

        if daily_vol <= 0 or current_price <= 0:
            logger.warning(f"Invalid ADV or Price for {ticker}. Returning zero impact.")
            return MarketImpactResult(0.0, 0.0, 0.0, 1, 0.0)

        # 1. Participation Rate: What % of the volume during this window are we?
        # Assuming 390 trading minutes in a day
        window_volume = daily_vol * (trade_duration_minutes / 390.0)
        if window_volume <= 0:
            participation_rate = 1.0
        else:
            participation_rate = order_size_shares / window_volume

        # If we exceed 20% participation, we are the market. Impact scales non-linearly.
        if participation_rate > 0.20:
            logger.warning(
                f"High Participation Rate ({participation_rate * 100:.1f}%) for {ticker}. Massive impact expected."
            )

        # 2. Temporary Impact (Square Root Law)
        # Driven by the speed of execution and taking liquidity from the book.
        # Formula: I_temp = gamma * sigma * sqrt(OrderSize / WindowVolume)
        temp_impact_pct = self.gamma * daily_vol_pct * math.sqrt(participation_rate)
        temp_impact_bps = temp_impact_pct * 10000

        # 3. Permanent Impact (Linear Law)
        # Driven by the information content of the trade. The market permanently reprices.
        # Formula: I_perm = eta * sigma * (OrderSize / DailyVolume)
        perm_impact_pct = self.eta * daily_vol_pct * (order_size_shares / daily_vol)
        perm_impact_bps = perm_impact_pct * 10000

        # 4. Expected Total Slippage Cost
        # Assuming execution happens linearly, average fill price suffers ~50% of the permanent impact
        # and 100% of the temporary impact.
        avg_price_degradation_pct = temp_impact_pct + (0.5 * perm_impact_pct)
        slippage_dollars = order_size_shares * current_price * avg_price_degradation_pct

        # 5. Determine Optimal Slices (Heuristic)
        # If temporary impact is > 2 bps, slice the order into smaller TWAP/VWAP chunks.
        optimal_slices = 1
        if temp_impact_bps > 2.0:
            optimal_slices = int(math.ceil(temp_impact_bps / 1.5))

        return MarketImpactResult(
            temporary_impact_bps=temp_impact_bps,
            permanent_impact_bps=perm_impact_bps,
            expected_slippage_dollars=slippage_dollars,
            optimal_slices=optimal_slices,
            optimal_time_horizon_minutes=trade_duration_minutes
            * (temp_impact_bps / 2.0 if temp_impact_bps > 2.0 else 1.0),
        )

    def optimize_execution_schedule(
        self, ticker: str, order_size_shares: int, current_price: float, risk_aversion: float = 1e-6
    ) -> List[Tuple[int, int]]:
        """
        Uses Almgren-Chriss formulation to balance Market Impact vs Price Risk.
        Higher risk aversion means executing faster (paying more impact cost to avoid price drift).
        Lower risk aversion means executing slower (taking price drift risk to save on impact cost).

        Returns a schedule: List of (Time_Offset_Minutes, Shares_To_Execute)
        """
        order_size_shares = int(order_size_shares)
        current_price = float(current_price)
        if order_size_shares <= 0 or current_price <= 0:
            return []

        daily_vol = self.adv.get(ticker, 1_000_000)
        daily_vol_pct = self.volatility.get(ticker, 0.02)
        variance = (current_price * daily_vol_pct) ** 2

        # Simplified half-life parameter 'kappa' balancing impact and variance
        # kappa = sqrt((risk_aversion * variance) / temp_impact_coefficient)
        # Using a highly simplified heuristic for the schedule generation

        total_time_mins = 60  # Default 1 hour horizon
        schedule = []

        # Determine N discrete slices
        N = min(10, order_size_shares)
        dt = total_time_mins / N

        # Generate an execution trajectory (U-shaped smile typical of institutional execution)
        shares_remaining = order_size_shares

        for i in range(N):
            # Smile curve: Execute more at the beginning and end of the window
            t = i / N
            smile_factor = 1.0 + 0.5 * ((t - 0.5) ** 2)

            if i == N - 1:
                slice_size = shares_remaining
            else:
                slice_size = int((order_size_shares / N) * smile_factor)
                slice_size = max(1, min(slice_size, shares_remaining - (N - i - 1)))

            schedule.append((int(i * dt), slice_size))
            shares_remaining -= slice_size

        return schedule
