import logging
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class ExitAction(Enum):
    EXIT = "EXIT"
    TIGHTEN = "TIGHTEN"
    CASCADE = "CASCADE"
    EVALUATE = "EVALUATE"
    HOLD = "HOLD"
    PARTIAL = "PARTIAL"


@dataclass
class ExitDecision:
    action: ExitAction
    priority: int
    reason: str
    new_stop: float | None = None
    confidence: float = 1.0
    pct_out: float = 1.0
    metadata: dict = field(default_factory=dict)


class ExitIntelligence:
    """Cost-Aware High-RR Exit Engine (Sovereign v1.0-beta)"""

    def __init__(self, config: dict | None = None) -> None:
        self.config = config or {}
        self.belief_threshold = self.config.get("belief_threshold", 0.35)
        self.daily_loss_limit = self.config.get("daily_loss_limit", 0.04)
        self.vix_spike_threshold = self.config.get("vix_spike_threshold", 0.15)
        self.safety_factor = 2.0  # Require expected profit to be 2x slippage+comm

    def evaluate(self, position: dict, market: dict, account: dict, dhatu_state: str = "Sthiti") -> ExitDecision:
        """
        Evaluate exit conditions in strict priority order (PROFITABILITY CORRECTED):
        P1: Hard stop hit -> EXIT (immediate)
        P2: Trailing Stop -> EXIT (runs after +1R)
        P3: Target / Partial -> PARTIAL (delay P1, 30-50% runner)
        P4: Emergency / Daily Loss -> EXIT
        P5: VIX spike / Cascade -> TIGHTEN
        P6: Default -> HOLD
        """

        # Unpack critical fields
        current_price = market.get("price", 0.0)
        entry_price = position.get("entry_price", 0.0)
        stop_loss = position.get("stop_loss", 0.0)
        side = position.get("side", "long")
        qty = position.get("quantity", 0.0)

        # Audit Fix [C5]: Zero-Quantity Guard
        if qty == 0:
            return ExitDecision(action=ExitAction.HOLD, priority=0, reason="Zero quantity position detected")

        # --- GAP-38: Dhatu-Adaptive Multiples (Samvid v1.0-beta) ---
        partial_r_target = 1.5
        trail_activation_r = 1.0
        trail_tightness = 0.5 # R-distance

        if dhatu_state == "Chala":
            # Volatile: Take partials early, trail tight
            partial_r_target = 1.0
            trail_activation_r = 0.7
            trail_tightness = 0.3
            logger.debug("ExitIntelligence [REWIRE]: Chala regime detected -> Tightening targets.")
        elif dhatu_state == "Vriddhi":
             # Super-Trend: Let it run
             partial_r_target = 2.0
             trail_tightness = 0.7

        commission_est = position.get("commission", 2.0)
        slippage_est = position.get("slippage", current_price * 0.0005 * qty)
        total_costs = commission_est + slippage_est

        # Calculate R
        initial_risk = abs(entry_price - position.get("initial_stop", stop_loss))
        if initial_risk <= 0:
            initial_risk = current_price * 0.01

        r_multiple = (
            ((current_price - entry_price) / initial_risk) if side == "long"
            else ((entry_price - current_price) / initial_risk)
        )

        expected_profit = r_multiple * initial_risk * qty
        is_profitable_enough = expected_profit > (total_costs * self.safety_factor)

        # Priority 1: Hard Stop Loss
        decision = self._check_stop_loss(position, current_price, side)
        if decision:
             return decision

        # Priority 2: Targets and Partial Exits (Proactive Profit Locking)
        mfe_r = position.get("mfe_r", 0.0)
        take_profit = position.get("take_profit", 0.0)
        runner_active = position.get("runner_active", False)

        # --- SUB-PRIORITY 2.1: Hard Take Profit ---
        if side == "long" and take_profit > 0 and current_price >= take_profit:
            return ExitDecision(action=ExitAction.EXIT, priority=2, reason=f"Target Hit: ${take_profit}")
        if side == "short" and take_profit > 0 and current_price <= take_profit:
            return ExitDecision(action=ExitAction.EXIT, priority=2, reason=f"Target Hit: ${take_profit}")

        # --- SUB-PRIORITY 2.2: Partial Scale-Out (Adaptive Runner Setup) ---
        if mfe_r >= partial_r_target and r_multiple >= partial_r_target:
            if is_profitable_enough:
                if not runner_active:
                     return ExitDecision(
                         action=ExitAction.PARTIAL,
                         priority=2,
                         reason=f"Adaptive Partial at +{r_multiple:.1f}R in {dhatu_state} regime",
                         pct_out=0.5,
                         metadata={"runner_setup": True}
                     )
            else:
                 # GAP-205: Notify the Bus/Brain that we reached target but skipped due to costs
                 return ExitDecision(
                     action=ExitAction.HOLD,
                     priority=2,
                     reason=f"SKIPPED_EXIT: Partial target reached (+{r_multiple:.1f}R) but expected profit (${expected_profit:.2f}) < cost threshold (${(total_costs * self.safety_factor):.2f})",
                     metadata={"skipped_exit": True}
                 )

        # Priority 3: Trailing Stop Logic (Reactive Profit Protection)
        if mfe_r > trail_activation_r:
            trail_dist = initial_risk * trail_tightness
            new_trail = current_price - trail_dist if side == "long" else current_price + trail_dist
            current_stop = position.get("stop_loss")

            # If current price touches broken trailing stop
            if side == "long" and current_price <= current_stop and current_stop > entry_price:
                 return ExitDecision(action=ExitAction.EXIT, priority=3, reason="Trailing stop hit", pct_out=1.0)
            elif side == "short" and current_price >= current_stop and current_stop < entry_price:
                 return ExitDecision(action=ExitAction.EXIT, priority=3, reason="Trailing stop hit", pct_out=1.0)

            # Tighten trail
            if side == "long" and new_trail > current_stop:
                return ExitDecision(action=ExitAction.TIGHTEN, priority=3, reason="Trailing active after +1R", new_stop=new_trail)
            if side == "short" and new_trail < current_stop:
                return ExitDecision(action=ExitAction.TIGHTEN, priority=3, reason="Trailing active after +1R", new_stop=new_trail)

        # Priority 4: Cost-Aware Profit Protection / Emergency
        decision = self._check_daily_loss(account)
        if decision:
            return decision

        # Priority 5: VIX / Cascades (Tighten only)
        decision = self._check_vix_spike(position, market)
        if decision:
            return decision

        # Cost-Aware Failsafe: Do NOT exit randomly if poor RR, unless thesis is totally dead
        thesis_dead = self._check_belief_collapse(position, market)
        if thesis_dead:
            # Only exit if we aren't getting chopped out by costs
            return thesis_dead

        # P6: Default HOLD
        return ExitDecision(
            action=ExitAction.HOLD,
            priority=6,
            reason="All conditions nominal - maximizing RR",
            confidence=1.0,
        )

    def _check_stop_loss(self, position: dict, current_price: float, side: str) -> ExitDecision | None:
        stop_loss = position.get("stop_loss")
        if stop_loss is None:
            return None
        if side == "long" and current_price <= stop_loss:
            return ExitDecision(action=ExitAction.EXIT, priority=1, reason="Hard Stop Hit")
        if side == "short" and current_price >= stop_loss:
            return ExitDecision(action=ExitAction.EXIT, priority=1, reason="Hard Stop Hit")
        return None

    def _check_daily_loss(self, account: dict) -> ExitDecision | None:
        daily_pnl = account.get("daily_pnl", 0)
        account_value = account.get("equity", 1000)
        if account_value <= 0:
            return None
        daily_loss_pct = abs(daily_pnl) / account_value if daily_pnl < 0 else 0
        if daily_loss_pct >= self.daily_loss_limit:
            return ExitDecision(action=ExitAction.EXIT, priority=4, reason="Daily loss budget exceeded")
        return None

    def _check_belief_collapse(self, position: dict, market: dict) -> ExitDecision | None:
        belief = position.get("bayesian_belief")
        if belief is None:
            belief = market.get("belief")
        if belief is not None and belief < self.belief_threshold:
            return ExitDecision(action=ExitAction.EXIT, priority=5, reason="Bayesian belief collapsed", confidence=belief)
        return None

    def _check_vix_spike(self, position: dict, market: dict) -> ExitDecision | None:
        vix_current = market.get("vix")
        vix_baseline = market.get("vix_baseline") or 15.0
        if vix_current is None or vix_baseline == 0:
            return None
        vix_change = (vix_current - vix_baseline) / vix_baseline
        if vix_change >= self.vix_spike_threshold:
            current_price = market.get("price", 0)
            initial_stop = position.get("initial_stop") or position.get("stop_loss")
            if initial_stop:
                distance = abs(current_price - initial_stop) * 0.5
                new_stop = current_price - distance if position.get("side", "long") == "long" else current_price + distance
                return ExitDecision(action=ExitAction.TIGHTEN, priority=5, reason="Volatility tightening", new_stop=new_stop)
        return None
