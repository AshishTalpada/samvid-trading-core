"""
Impact Model (#182 from SOVEREIGN_ULTIMATE_CHECKLIST).
Models how the market will react to YOUR trade size - Self-Referential Game Theory.
"""

import logging
import math
from collections import deque
from dataclasses import dataclass
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class TradeImpact:
    """Estimated market impact from a trade."""
    immediate_slippage: float
    delayed_impact: float
    reversal_risk: float
    total_cost: float
    recommendation: str


class ImpactModel:
    """
    Self-Referential Game Theory Model.
    
    Models how the market will react to YOUR trade size, anticipating
    counter-moves from other participants.
    """

    def __init__(self):
        self.trade_history = deque(maxlen=100)
        self.avg_slippage = 0.0
        self.market_elasticity = 1.0

    def estimate_impact(
        self,
        symbol: str,
        trade_size: float,
        current_price: float,
        avg_daily_volume: float,
        order_book_imbalance: float = 0.0,
    ) -> TradeImpact:
        """
        Estimate market impact of a proposed trade.
        
        Args:
            symbol: Trading symbol
            trade_size: Number of shares/units
            current_price: Current market price
            avg_daily_volume: Average daily volume
            order_book_imbalance: -1 (buy pressure) to 1 (sell pressure)
            
        Returns:
            TradeImpact with estimated costs and recommendation
        """
        if avg_daily_volume <= 0 or trade_size <= 0:
            return TradeImpact(
                immediate_slippage=0.0,
                delayed_impact=0.0,
                reversal_risk=0.0,
                total_cost=0.0,
                recommendation="UNKNOWN",
            )

        participation_rate = trade_size / avg_daily_volume

        self._update_elasticity(participation_rate)

        immediate_slippage = self._calculate_immediate_slippage(
            participation_rate, current_price, order_book_imbalance
        )

        delayed_impact = self._calculate_delayed_impact(
            participation_rate, current_price
        )

        reversal_risk = self._calculate_reversal_risk(
            trade_size, avg_daily_volume, order_book_imbalance
        )

        total_cost = immediate_slippage + delayed_impact + reversal_risk

        recommendation = self._get_recommendation(
            total_cost, participation_rate, reversal_risk
        )

        self.trade_history.append({
            "symbol": symbol,
            "size": trade_size,
            "participation": participation_rate,
            "slippage": immediate_slippage,
            "impact": total_cost,
        })

        self._update_averages(immediate_slippage)

        return TradeImpact(
            immediate_slippage=immediate_slippage,
            delayed_impact=delayed_impact,
            reversal_risk=reversal_risk,
            total_cost=total_cost,
            recommendation=recommendation,
        )

    def _calculate_immediate_slippage(
        self,
        participation: float,
        price: float,
        order_imbalance: float,
    ) -> float:
        """
        Calculate immediate price impact using square-root model.
        
        More aggressive for larger orders relative to volume.
        """
        base_impact = 0.1 * math.sqrt(participation) * price

        imbalance_multiplier = 1.0 + (order_imbalance * 0.5)

        directional_bias = 0.02 * participation * price if order_imbalance < 0 else 0

        return base_impact * imbalance_multiplier + directional_bias

    def _calculate_delayed_impact(
        self,
        participation: float,
        price: float,
    ) -> float:
        """
        Calculate delayed/reversible impact.
        
        Larger orders cause price to drift and then partially revert.
        """
        permanent_component = 0.05 * participation * price
        reversible_component = 0.03 * participation * price

        return permanent_component + reversible_component

    def _calculate_reversal_risk(
        self,
        trade_size: float,
        avg_volume: float,
        order_imbalance: float,
    ) -> float:
        """
        Calculate risk of market moving against you post-trade.
        
        Large trades can attract counter-traders and market makers hunting your order.
        """
        if avg_volume <= 0:
            return 0.0

        participation = trade_size / avg_volume

        if participation > 0.1:
            reversal_risk = 0.15 * participation * trade_size
        elif participation > 0.05:
            reversal_risk = 0.08 * participation * trade_size
        else:
            reversal_risk = 0.01 * participation * trade_size

        if order_imbalance != 0:
            reversal_risk *= 1.5

        return reversal_risk

    def _calculate_market_elasticity(self) -> float:
        """Estimate market elasticity from historical data."""
        if len(self.trade_history) < 5:
            return 1.0

        participations = [t["participation"] for t in self.trade_history]
        slips = [t["slippage"] for t in self.trade_history]

        if sum(participations) <= 0:
            return 1.0

        weighted_avg = sum(p * s for p, s in zip(participations, slips, strict=False)) / sum(participations)

        return max(0.1, min(3.0, weighted_avg))

    def _update_elasticity(self, participation: float):
        """Update market elasticity estimate."""
        alpha = 0.1
        new_elasticity = self._calculate_market_elasticity()
        self.market_elasticity = alpha * new_elasticity + (1 - alpha) * self.market_elasticity

    def _update_averages(self, slippage: float):
        """Update running average slippage."""
        alpha = 0.1
        self.avg_slippage = alpha * slippage + (1 - alpha) * self.avg_slippage

    def _get_recommendation(
        self,
        total_cost: float,
        participation: float,
        reversal_risk: float,
    ) -> str:
        """Get recommendation based on impact analysis."""
        if participation > 0.15:
            return "SPLIT_ORDER"
        elif participation > 0.08:
            return "REDUCE_SIZE"
        elif total_cost > 0.02:
            return "MONITOR_CLOSE"
        elif reversal_risk > 0.01:
            return "USE_ALGO"
        else:
            return "EXECUTE_NORMAL"

    def get_optimal_size(
        self,
        symbol: str,
        current_price: float,
        avg_daily_volume: float,
        max_slippage_percent: float = 0.5,
        max_reversal_risk: float = 0.5,
    ) -> dict[str, Any]:
        """
        Calculate optimal trade size to stay within risk parameters.
        
        Args:
            symbol: Trading symbol
            current_price: Current price
            avg_daily_volume: Daily volume
            max_slippage_percent: Maximum allowed slippage %
            max_reversal_risk: Maximum allowed reversal risk
            
        Returns:
            Dictionary with optimal size and analysis
        """
        if avg_daily_volume <= 0 or current_price <= 0:
            return {"optimal_size": 0, "reason": "Insufficient data"}

        max_slippage_value = current_price * (max_slippage_percent / 100)
        max_risk_value = current_price * (max_reversal_risk / 100)

        target_cost = min(max_slippage_value, max_risk_value)

        optimal_participation = min(
            (target_cost / (0.1 * current_price)) ** 2,
            0.10,
        )

        optimal_size = int(optimal_participation * avg_daily_volume)

        estimated_impact = self.estimate_impact(
            symbol, optimal_size, current_price, avg_daily_volume
        )

        return {
            "optimal_size": optimal_size,
            "participation_rate": optimal_participation,
            "estimated_slippage": estimated_impact.immediate_slippage,
            "estimated_reversal": estimated_impact.reversal_risk,
            "estimated_total_cost": estimated_impact.total_cost,
            "recommendation": estimated_impact.recommendation,
            "max_slippage_percent": max_slippage_percent,
            "max_reversal_risk": max_reversal_risk,
        }

    def get_historical_analysis(self) -> dict[str, Any]:
        """Get analysis of historical trade impacts."""
        if not self.trade_history:
            return {"analysis": "No history available"}

        total_trades = len(self.trade_history)
        avg_participation = sum(t["participation"] for t in self.trade_history) / total_trades
        avg_slippage = sum(t["slippage"] for t in self.trade_history) / total_trades
        avg_impact = sum(t["impact"] for t in self.trade_history) / total_trades

        high_impact_trades = sum(1 for t in self.trade_history if t["impact"] > 0.01)

        return {
            "total_trades": total_trades,
            "avg_participation": avg_participation,
            "avg_slippage": avg_slippage,
            "avg_impact": avg_impact,
            "high_impact_count": high_impact_trades,
            "market_elasticity": self.market_elasticity,
        }


_impact_model_instance: Optional[ImpactModel] = None


def get_impact_model() -> ImpactModel:
    """Get the singleton ImpactModel instance."""
    global _impact_model_instance
    if _impact_model_instance is None:
        _impact_model_instance = ImpactModel()
    return _impact_model_instance
