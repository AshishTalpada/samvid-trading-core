import logging
import math
from datetime import datetime
from typing import Any, Dict

logger = logging.getLogger(__name__)

class DhatuOracle:
    '''
    Deep Dive: Dhatu Meta-Cycle Oracle.
    Based on ancient Vedic/Sanskrit elemental theory (Mahabhutas), this maps
    macro-economic shifts to 5 underlying elemental phases.
    Earth (Prithvi) = Consolidation / Accumulation
    Water (Jala) = Liquidity / Downward Cascades
    Fire (Tejas) = Explosive Breakouts / High Volatility
    Air (Vayu) = High Frequency Choppiness / Range expansion
    Ether (Akasha) = Extreme Void / Low volume dead-zones
    '''

    PHASES = ["PRITHVI", "JALA", "TEJAS", "VAYU", "AKASHA"]

    def __init__(self, cycle_duration_days: float = 27.32): # Sidereal lunar month
        self.cycle_duration = cycle_duration_days

    def compute_current_dhatu(self, timestamp: float, avg_volume: float, current_volatility: float) -> str:
        '''
        Deterministically computes the elemental resonance of the current market state
        using a combination of cosmic time cycles and empirical volume/volatility signatures.
        '''
        dt = datetime.fromtimestamp(timestamp)
        day_of_year = dt.timetuple().tm_yday

        # 1. Base phase derived from the sidereal cycle
        cycle_position = (day_of_year % self.cycle_duration) / self.cycle_duration
        base_index = int(math.floor(cycle_position * 5))
        base_dhatu = self.PHASES[base_index]

        # 2. Empirical Override (Reality Check)
        # If the market math radically contradicts the time cycle, the physical reality takes precedence.

        if current_volatility > 0.05 and avg_volume > 1.5:
            # High volatility, High volume -> Explosion
            return "TEJAS"

        elif current_volatility > 0.04 and avg_volume < 0.5:
            # High volatility, Low volume -> Choppy low liquidity sweeps
            return "VAYU"

        elif current_volatility < 0.01 and avg_volume < 0.2:
            # Dead market
            return "AKASHA"

        elif current_volatility < 0.015 and avg_volume > 1.0:
            # Heavy absorption / Accumulation
            return "PRITHVI"

        elif current_volatility > 0.02 and avg_volume > 0.8: # Default flowing trend
            return "JALA"

        return base_dhatu

    def get_strategic_alignment(self, dhatu: str) -> Dict[str, Any]:
        '''Outputs the specific strategy parameters tuned for the active elemental state.'''
        alignments = {
            "PRITHVI": {"bias": "MEAN_REVERSION", "leverage_cap": 0.5, "stop_loss_multiplier": 1.2},
            "JALA":    {"bias": "TREND_FOLLOWING", "leverage_cap": 1.0, "stop_loss_multiplier": 2.0},
            "TEJAS":   {"bias": "MOMENTUM_BREAKOUT", "leverage_cap": 1.5, "stop_loss_multiplier": 0.5}, # Tight stops during fire
            "VAYU":    {"bias": "MARKET_MAKING", "leverage_cap": 0.2, "stop_loss_multiplier": 3.0},   # Wide stops during air chop
            "AKASHA":  {"bias": "HOLD_CASH", "leverage_cap": 0.0, "stop_loss_multiplier": 0.0}
        }
        logger.info(f"[ORACLE] Market resonating with {dhatu}. Adjusting systemic alignment.")
        return alignments.get(dhatu, alignments["PRITHVI"])
